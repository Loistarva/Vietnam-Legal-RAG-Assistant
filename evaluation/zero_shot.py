"""Run the Prompt A zero-shot baseline through the shared Qwen gateway."""
from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generation.prompt_builder import PROMPT_A_VERSION, build_zero_shot_prompt
from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH, QwenGateway


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


def run_benchmark(
    questions_path: Path,
    output_path: Path,
    model: str | None = None,
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    gateway: QwenGateway | None = None,
) -> list[dict[str, Any]]:
    """Run Prompt A using the exact gateway config shared with Run B.

    ``model`` is accepted for compatibility with older callers; model and all
    generation parameters are intentionally read from the shared gateway YAML.
    """
    del model
    questions = load_questions(questions_path)
    gateway = gateway or QwenGateway(config_path)
    config = gateway.config
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
                run_mode="A_zero_shot",
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
                "answer": None, "method": "zero_shot", "run_mode": "A_zero_shot",
                "prompt_version": PROMPT_A_VERSION, "model": config.model,
                "context_used": False, "llm_calls": 1,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": str(exc),
            })
            print(f"[{i}/{len(questions)}] {question_id}: ERROR - {exc}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    success = sum(result["answer"] is not None for result in results)
    print("-" * 60)
    print(f"Total: {len(results)}\nSuccessful: {success}\nFailed: {len(results) - success}")
    print(f"Output: {output_path.resolve()}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Prompt A zero-shot through the shared Qwen gateway.")
    parser.add_argument("--questions", type=Path, required=True, help="Benchmark question JSON with as_of_date per question.")
    parser.add_argument("--output", type=Path, required=True, help="Path to save generated answers.")
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
