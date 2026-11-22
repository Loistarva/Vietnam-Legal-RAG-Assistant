"""Run the Prompt A zero-shot baseline through the shared Qwen gateway."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generation.prompt_builder import PROMPT_A_VERSION, build_zero_shot_prompt
from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH, QwenGateway

RUN_MODE = "A_zero_shot"
METRICS_VERSION = "zero_shot_metrics_v1"


def load_questions(path: Path) -> list[dict[str, Any]]:
    """Load question rows and require the same per-question date used by Run B."""
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file câu hỏi: {path}")
    with path.open("r", encoding="utf-8-sig") as file:
        questions = json.load(file)
    if not isinstance(questions, list):
        raise ValueError(f"{path} phải chứa một JSON array.")

    seen_ids: set[str] = set()
    for position, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Phần tử thứ {position} không phải JSON object.")
        question_id, question, as_of_date = item.get("id"), item.get("question"), item.get("as_of_date")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"Phần tử thứ {position} thiếu id hợp lệ.")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Câu hỏi {question_id} thiếu question hợp lệ.")
        if not isinstance(as_of_date, str) or not as_of_date.strip():
            raise ValueError(f"Câu hỏi {question_id} thiếu as_of_date; cần dùng ngày từ benchmark như Run B.")
        if question_id in seen_ids:
            raise ValueError(f"ID câu hỏi bị trùng: {question_id}")
        seen_ids.add(question_id)
    return questions


def count_cjk_chars(text: str) -> int:
    return sum(unicodedata.name(char, "").startswith(("CJK", "HIRAGANA", "KATAKANA", "HANGUL")) for char in text)


def _sha256_file(path: Path) -> str:
    """Hash text with LF newlines so a CRLF checkout gives the same value as the Git blob."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _canonical_sha256(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_text_file_content(text: str) -> str:
    """Hash written text the same way ``_sha256_file`` hashes the file on disk."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def manifest_path_for(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_manifest.json")


def build_manifest(
    questions_path: Path,
    output_path: Path,
    gateway: QwenGateway,
    config_path: Path,
    results: list[dict[str, Any]],
    started_at: str,
    *,
    results_sha256: str,
    split: str = "unspecified",
) -> dict[str, Any]:
    config = gateway.config
    git_status = _git("status", "--porcelain")
    failed = sum(result.get("answer") is None for result in results)
    truncated = sum(result.get("truncated") is True for result in results)
    done_reason_counts: dict[str, int] = {}
    for result in results:
        done_reason = result.get("done_reason")
        if isinstance(done_reason, str):
            done_reason_counts[done_reason] = done_reason_counts.get(done_reason, 0) + 1
    question_ids = [result["query_id"] for result in results]
    prompt_path = ROOT / "generation" / "prompt_builder.py"
    metrics_path = ROOT / "evaluation" / "evaluate_zero_shot.py"
    return {
        "manifest_version": "run_a.zero_shot.v1",
        "run_id": output_path.stem,
        "experiment": RUN_MODE,
        "split": split,
        "git_branch": _git("branch", "--show-current"),
        "git_sha": _git("rev-parse", "HEAD"),
        "working_tree_dirty": None if git_status is None else bool(git_status),
        "questions_path": _manifest_path(questions_path),
        "questions_sha256": _sha256_file(questions_path),
        "dataset_ids_hash": _canonical_sha256(question_ids),
        "dataset_question_count": len(question_ids),
        "results_path": _manifest_path(output_path),
        "results_sha256": results_sha256,
        "as_of_date_source": "benchmark",
        "as_of_date_policy": {"source": "benchmark"},
        "retrieval_enabled": False,
        "corpus_version": None,
        "corpus_sha256": None,
        "retrieval_config_version": None,
        "retrieval_config_sha256": None,
        "rerank_config_version": None,
        "rerank_config_sha256": None,
        "prompt_version": PROMPT_A_VERSION,
        "prompt_sha256": _sha256_file(prompt_path),
        "metrics_version": METRICS_VERSION,
        "metrics_sha256": _sha256_file(metrics_path),
        "runtime": {
            "provider": config.provider,
            "base_url": config.base_url,
            "model": config.model,
            "model_config_path": _manifest_path(config_path),
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
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "cache_enabled": config.cache_enabled,
        "fallback_locked": config.fallback_locked,
        "hyde_enabled": False,
        "judge_enabled": False,
        "total": len(results),
        "succeeded": len(results) - failed,
        "failed": failed,
        "done_reason_counts": done_reason_counts,
        "truncated_count": truncated,
        "truncation_rate": truncated / len(results) if results else 0.0,
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED" if failed else "SUCCESS",
    }


def rebuild_manifest_from_jsonl(output_path: Path, *, split: str = "unknown") -> dict[str, Any]:
    """Reconstruct only verifiable run metadata from an existing JSONL artifact.

    This function deliberately does not inspect the current model/config/code to
    fill historical fields. The JSONL remains untouched.
    """
    if output_path.suffix.casefold() != ".jsonl":
        raise ValueError("Chỉ hỗ trợ tái tạo manifest từ file .jsonl.")
    results: list[dict[str, Any]] = []
    with output_path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL lỗi tại dòng {line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Dòng {line_number} không phải JSON object.")
            if not isinstance(row.get("query_id"), str) or not row["query_id"].strip():
                raise ValueError(f"Dòng {line_number} thiếu query_id hợp lệ.")
            results.append(row)

    ids = [row["query_id"] for row in results]
    if len(set(ids)) != len(ids):
        raise ValueError("JSONL chứa query_id trùng; không thể tạo manifest đáng tin cậy.")
    failed = sum(row.get("answer") is None for row in results)
    done_reason_counts: dict[str, int] = {}
    for row in results:
        reason = row.get("done_reason")
        if isinstance(reason, str):
            done_reason_counts[reason] = done_reason_counts.get(reason, 0) + 1

    def one_value(key: str) -> Any:
        values = {json.dumps(row.get(key), sort_keys=True, ensure_ascii=False) for row in results}
        if not results or len(values) != 1:
            return None
        return results[0].get(key)

    unknown_fields = [
        "git_branch", "git_sha", "working_tree_dirty", "questions_path",
        "questions_sha256", "prompt_sha256", "metrics_version", "metrics_sha256",
        "runtime.provider", "runtime.base_url", "runtime.model_config_path",
        "runtime.model_config_sha256", "runtime.timeout_seconds",
        "runtime.max_retries", "runtime.cache_enabled", "runtime.fallback_locked",
        "runtime.python_version", "runtime.python_implementation", "runtime.platform",
        "started_at_utc", "finished_at_utc",
    ]
    runtime = {
        "provider": None, "base_url": None, "model": one_value("model"),
        "model_config_path": None, "model_config_sha256": None,
        "model_digest": one_value("model_digest"),
        "ollama_version": one_value("ollama_version"),
        "temperature": one_value("temperature"),
        "repeat_penalty": one_value("repeat_penalty"),
        "num_predict": one_value("num_predict"), "num_ctx": one_value("num_ctx"),
        "timeout_seconds": None, "max_retries": None,
        "cache_enabled": None, "fallback_locked": None,
        "prompt_version": one_value("prompt_version"),
        "python_version": None, "python_implementation": None, "platform": None,
    }
    return {
        "manifest_version": "run_a.zero_shot.v1",
        "manifest_reconstruction": "from_existing_jsonl_v1",
        "run_id": output_path.stem,
        "experiment": RUN_MODE,
        "split": split,
        "git_branch": None, "git_sha": None, "working_tree_dirty": None,
        "questions_path": None, "questions_sha256": None,
        "dataset_ids_hash": _canonical_sha256(ids),
        "dataset_question_count": len(ids),
        "results_path": _manifest_path(output_path),
        "results_sha256": _sha256_file(output_path),
        "as_of_date_source": "unknown",
        "as_of_date_policy": None,
        "retrieval_enabled": False,
        "corpus_version": None, "corpus_sha256": None,
        "retrieval_config_version": None, "retrieval_config_sha256": None,
        "rerank_config_version": None, "rerank_config_sha256": None,
        "prompt_version": one_value("prompt_version"), "prompt_sha256": None,
        "metrics_version": None, "metrics_sha256": None,
        "runtime": runtime,
        "cache_enabled": None, "fallback_locked": None,
        "hyde_enabled": False, "judge_enabled": False,
        "total": len(results), "succeeded": len(results) - failed,
        "failed": failed, "done_reason_counts": done_reason_counts,
        "truncated_count": sum(row.get("truncated") is True for row in results),
        "truncation_rate": (sum(row.get("truncated") is True for row in results) / len(results)) if results else 0.0,
        "started_at_utc": None, "finished_at_utc": None,
        "status": "FAILED" if failed else "SUCCESS",
        "unknown_historical_fields": unknown_fields,
    }


def run_benchmark(
    questions_path: Path,
    output_path: Path,
    model: str | None = None,
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    gateway: QwenGateway | None = None,
    split: str = "unspecified",
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    """Run Prompt A and write immutable results plus a provenance manifest.

    ``model`` is accepted for compatibility with older callers; model and all
    generation parameters are intentionally read from the shared gateway YAML.
    Existing output and manifest files are rejected unless ``overwrite=True``.
    """
    del model
    questions = load_questions(questions_path)
    manifest_path = manifest_path_for(output_path)
    existing = [path for path in (output_path, manifest_path) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            f"Đã có {existing[0]}; dùng tên output mới, không ghi đè kết quả cũ."
        )

    gateway = gateway or QwenGateway(config_path)
    config = gateway.config
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Model: {config.model}")
    print(f"Prompt: {PROMPT_A_VERSION}")
    print(f"Gateway config: {config_path}")
    print(f"Questions: {questions_path}")
    print(f"Total questions: {len(questions)}")
    print("-" * 60)

    results: list[dict[str, Any]] = []
    for i, item in enumerate(questions, start=1):
        question_id, question, as_of_date = item["id"], item["question"], item["as_of_date"].strip()
        started = time.perf_counter()
        try:
            prompt = build_zero_shot_prompt(query=question, as_of_date=as_of_date)
            response = gateway.generate(
                prompt=prompt,
                query_id=question_id,
                run_mode=RUN_MODE,
                prompt_version=PROMPT_A_VERSION,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            answer = response.answer
            results.append({
                "query_id": question_id, "question": question, "as_of_date": as_of_date,
                "answer": answer, "method": "zero_shot", "run_mode": response.run_mode,
                "prompt_version": response.prompt_version, "model": response.model,
                "context_used": False, "num_ctx": response.num_ctx,
                "num_predict": response.num_predict, "temperature": response.temperature,
                "repeat_penalty": response.repeat_penalty, "done_reason": response.done_reason,
                "truncated": response.truncated, "context_truncated": response.context_truncated,
                "latency_ms": elapsed_ms, "llm_calls": 1,
                "latency_breakdown": {
                    "retrieval_ms": None, "llm_total_ms": response.latency_ms,
                    "load_ms": response.load_duration_ms,
                    "prompt_eval_ms": response.prompt_eval_duration_ms,
                    "eval_ms": response.eval_duration_ms,
                    "ttft_model_ms": response.ttft_model_ms,
                },
                "token_usage": response.token_usage.model_dump(),
                "cjk_chars": count_cjk_chars(answer), "fallback_status": response.fallback_status,
                "ollama_version": response.ollama_version, "model_digest": response.model_digest,
            })
            print(f"[{i}/{len(questions)}] {question_id}: OK")
        except Exception as exc:
            results.append({
                "query_id": question_id, "question": question, "as_of_date": as_of_date,
                "answer": None, "method": "zero_shot", "run_mode": RUN_MODE,
                "prompt_version": PROMPT_A_VERSION, "model": config.model,
                "context_used": False, "llm_calls": 1,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": str(exc),
            })
            print(f"[{i}/{len(questions)}] {question_id}: ERROR - {exc}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = (
        "".join(json.dumps(result, ensure_ascii=False) + "\n" for result in results)
        if output_path.suffix.casefold() == ".jsonl"
        else json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    )
    manifest = build_manifest(
        questions_path, output_path, gateway, Path(config_path), results, started_at,
        results_sha256=_sha256_text_file_content(output_text),
        split=split,
    )
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    output_bytes = output_text.encode("utf-8")
    manifest_bytes = manifest_text.encode("utf-8")
    if overwrite:
        output_path.write_bytes(output_bytes)
    else:
        with output_path.open("xb") as file:
            file.write(output_bytes)
    if overwrite:
        manifest_path.write_bytes(manifest_bytes)
    else:
        with manifest_path.open("xb") as file:
            file.write(manifest_bytes)

    print("-" * 60)
    print(
        f"Total: {manifest['total']}\nSuccessful: {manifest['succeeded']}"
        f"\nFailed: {manifest['failed']}"
    )
    print(f"Output: {output_path.resolve()}")
    print(f"Manifest: {manifest_path.resolve()}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Prompt A zero-shot through the shared Qwen gateway.")
    parser.add_argument("--questions", type=Path, required=True, help="Benchmark question JSON with as_of_date per question.")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for generated answers; a companion _manifest.json is also written.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Shared gateway config (defaults to Run B config).")
    args = parser.parse_args()
    try:
        run_benchmark(args.questions, args.output, config_path=args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    except Exception as exc:
        parser.error(f"Không thể chạy benchmark: {exc}")


if __name__ == "__main__":
    main()
