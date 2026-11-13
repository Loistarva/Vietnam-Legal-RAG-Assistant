"""
Zero-shot LLM baseline (Run A) through the shared Qwen Gateway.

- Input: an explicitly selected question-set JSON (``id``, ``question``, ``as_of_date``).
- Output: an explicitly selected predictions JSON plus ``<output stem>_manifest.json``.
- No RAG context, no retrieval.

Run A uses the same gateway, generation parameters (``model_gateway/config/local_qwen.yaml``:
temperature, repeat_penalty, num_predict, num_ctx) and benchmark ``as_of_date`` as Run B, with
Prompt A (``build_zero_shot_prompt``, ``PROMPT_A_VERSION``) in place of Prompt B (P45-9). Each
record keeps done_reason, latency, token usage and the Ollama durations so A and B are measured
the same way. An existing output file is never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from generation.prompt_builder import PROMPT_A_VERSION, build_zero_shot_prompt, get_prompt_hash  # noqa: E402
from model_gateway.llm_gateway import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    QwenGateway,
    normalize_model_name,
)
from orchestration.rag_pipeline import count_cjk_chars  # noqa: E402
from schemas.models import LLMResponse  # noqa: E402

RUN_MODE = "A_zero_shot"
METHOD = "zero_shot"


# ============================================================
# 1. LOAD QUESTIONS
# ============================================================

def load_questions(path: Path) -> list[dict[str, Any]]:
    """Load and validate questions from a JSON array; every question needs its benchmark as_of_date."""

    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file câu hỏi: {path}")

    with path.open("r", encoding="utf-8-sig") as f:
        questions = json.load(f)

    if not isinstance(questions, list):
        raise ValueError(f"{path} phải chứa một JSON array.")

    seen_ids: set[str] = set()

    for position, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Phần tử thứ {position} không phải JSON object.")

        question_id = item.get("id")
        question = item.get("question")

        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"Phần tử thứ {position} thiếu id hợp lệ.")

        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Câu hỏi {question_id} thiếu question hợp lệ.")

        as_of_date = item.get("as_of_date")
        try:
            date.fromisoformat(str(as_of_date))
        except ValueError:
            raise ValueError(f"Câu hỏi {question_id} thiếu as_of_date ISO (YYYY-MM-DD) từ benchmark.") from None

        if question_id in seen_ids:
            raise ValueError(f"ID câu hỏi bị trùng: {question_id}")

        seen_ids.add(question_id)

    return questions


# ============================================================
# 2. GENERATE ZERO-SHOT ANSWER
# ============================================================

def build_gateway(model: str | None = None, config_path: str | Path | None = None) -> QwenGateway:
    """Gateway with the shared Run A/B config; refuses a --model that differs from it,
    so generation parameters cannot drift between A and B."""
    gateway = QwenGateway(config_path or DEFAULT_CONFIG_PATH)
    if model and normalize_model_name(model) != normalize_model_name(gateway.config.model):
        raise ValueError(f"--model {model!r} khác model cấu hình {gateway.config.model!r} "
                         f"({config_path or DEFAULT_CONFIG_PATH}); Run A phải dùng cùng cấu hình với Run B.")
    return gateway


def answer_question(question: str, *, query_id: str, as_of_date: str, gateway: QwenGateway) -> tuple[LLMResponse, str]:
    """Prompt A (question + as_of_date, no retrieved context) through the gateway."""
    prompt = build_zero_shot_prompt(question, as_of_date)
    response = gateway.generate(prompt, query_id, RUN_MODE, PROMPT_A_VERSION, structured_output=False)
    return response, prompt


def build_record(item: dict[str, Any], response: LLMResponse, prompt: str) -> dict[str, Any]:
    """Run A record with the same latency/token/provenance keys as a Run B record."""
    return {
        "query_id": item["id"],
        "question": item["question"],
        "as_of_date": item["as_of_date"],
        "as_of_date_source": "benchmark",
        "answer": response.answer,
        "method": METHOD,
        "run_mode": RUN_MODE,
        "model": response.model,
        "context_used": False,
        "prompt_version": response.prompt_version,
        "prompt_sha256": get_prompt_hash(prompt),
        "temperature": response.temperature,
        "repeat_penalty": response.repeat_penalty,
        "num_ctx": response.num_ctx,
        "num_predict": response.num_predict,
        "done_reason": response.done_reason,
        "truncated": response.truncated,
        "context_truncated": response.context_truncated,
        "latency_ms": response.latency_ms,
        "llm_calls": 1,
        "latency_breakdown": {
            "retrieval_ms": None,
            "llm_total_ms": response.latency_ms,
            "ttft_model_ms": response.ttft_model_ms,
            "load_ms": response.load_duration_ms,
            "prompt_eval_ms": response.prompt_eval_duration_ms,
            "eval_ms": response.eval_duration_ms,
        },
        "token_usage": response.token_usage.model_dump(),
        "cjk_chars": count_cjk_chars(response.answer),
        "ollama_version": response.ollama_version,
        "model_digest": response.model_digest,
    }


# ============================================================
# 3. RUN ZERO-SHOT BENCHMARK
# ============================================================

def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT_DIR, check=True, capture_output=True,
                              text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def manifest_path_for(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_manifest.json")


def build_manifest(questions_path: Path, output_path: Path, gateway: QwenGateway,
                   config_path: Path, results: list[dict[str, Any]], started_at: str) -> dict[str, Any]:
    config = gateway.config
    status = _git("status", "--porcelain")
    failed = sum(r.get("answer") is None for r in results)
    return {
        "manifest_version": "run_a.zero_shot.v1",
        "run_mode": RUN_MODE,
        "git_branch": _git("branch", "--show-current"),
        "git_sha": _git("rev-parse", "HEAD"),
        "working_tree_dirty": None if status is None else bool(status),
        "questions_path": questions_path.resolve().as_posix(),
        "questions_sha256": _sha256_file(questions_path),
        "results_path": output_path.resolve().as_posix(),
        "as_of_date_source": "benchmark",
        "runtime": {
            "provider": config.provider,
            "base_url": config.base_url,
            "model": config.model,
            "model_config_path": config_path.resolve().as_posix(),
            "model_config_sha256": _sha256_file(config_path),
            "model_digest": gateway.model_digest,
            "ollama_version": gateway.ollama_version,
            "temperature": config.temperature,
            "repeat_penalty": config.repeat_penalty,
            "num_predict": config.num_predict,
            "num_ctx": config.num_ctx,
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
            "cache_enabled": config.cache_enabled,
            "fallback_locked": config.fallback_locked,
            "prompt_version": PROMPT_A_VERSION,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "total": len(results),
        "succeeded": len(results) - failed,
        "failed": failed,
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED" if failed else "SUCCESS",
    }


def run_benchmark(
    questions_path: Path,
    output_path: Path,
    model: str | None = None,
    *,
    gateway: QwenGateway | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    """Run zero-shot inference for every question; write results + manifest (never overwrite)."""

    questions = load_questions(questions_path)
    manifest_path = manifest_path_for(output_path)
    existing = [p for p in (output_path, manifest_path) if p.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Đã có {existing[0]}; dùng tên output mới, không ghi đè kết quả cũ.")
    gateway = gateway or build_gateway(model, config_path)
    started_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []

    print(f"Model: {gateway.config.model} | prompt {PROMPT_A_VERSION} | repeat_penalty "
          f"{gateway.config.repeat_penalty} | num_predict {gateway.config.num_predict}")
    print(f"Questions: {questions_path}")
    print(f"Total questions: {len(questions)}")
    print("-" * 60)

    for i, item in enumerate(questions, start=1):
        question_id = item["id"]
        try:
            response, prompt = answer_question(item["question"], query_id=question_id,
                                               as_of_date=item["as_of_date"], gateway=gateway)
            results.append(build_record(item, response, prompt))
            print(f"[{i}/{len(questions)}] {question_id}: OK ({response.done_reason}, {response.latency_ms} ms)")
        except Exception as exc:
            results.append({
                "query_id": question_id,
                "question": item["question"],
                "as_of_date": item["as_of_date"],
                "answer": None,
                "method": METHOD,
                "run_mode": RUN_MODE,
                "model": gateway.config.model,
                "context_used": False,
                "prompt_version": PROMPT_A_VERSION,
                "error": str(exc),
            })
            print(f"[{i}/{len(questions)}] {question_id}: ERROR - {exc}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = build_manifest(questions_path, output_path, gateway, Path(config_path), results, started_at)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("-" * 60)
    print(f"Total: {manifest['total']}")
    print(f"Successful: {manifest['succeeded']}")
    print(f"Failed: {manifest['failed']}")
    print(f"Output: {output_path.resolve()}")
    print(f"Manifest: {manifest_path.resolve()}")

    return results


# ============================================================
# 4. CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Run zero-shot LLM baseline (Run A) through the Qwen Gateway.")
    parser.add_argument("--questions", type=Path, required=True,
                        help="Path to the question-set JSON (Dev, Test, or another split).")
    parser.add_argument("--output", type=Path, required=True, help="Path to save generated answers (new file).")
    parser.add_argument("--model", default=None, help="Must match the gateway config model (default: from config).")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Gateway config (shared with Run B).")

    args = parser.parse_args()

    try:
        run_benchmark(questions_path=args.questions, output_path=args.output, model=args.model,
                      config_path=args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    except Exception as exc:
        parser.error(f"Không thể chạy benchmark: {exc}")


if __name__ == "__main__":
    main()
