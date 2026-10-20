
"""
Zero-shot LLM baseline using local Ollama.

- Input: data/benchmark/queries_dev.json
- Ground truth: data/benchmark/ground_truth.json
- Output: evaluation/results/zero_shot_dev_results.json
- No RAG context, no retrieval.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import ollama


# ============================================================
# PATH CONFIGURATION
# ============================================================

# Project root: Vietnam-Legal-RAG-Assistant/
ROOT_DIR = Path(__file__).resolve().parents[1]

QUERIES_DEV_PATH = (
    ROOT_DIR / "data" / "benchmark" / "queries_dev.json"
)

GROUND_TRUTH_PATH = (
    ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "evaluation"
    / "results"
    / "zero_shot_dev_results.json"
)


# ============================================================
# 1. LOAD QUESTIONS
# ============================================================

def load_questions(path: Path) -> list[dict[str, Any]]:
    """Load and validate questions from a JSON array."""

    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file câu hỏi: {path}"
        )

    with path.open("r", encoding="utf-8") as f:
        questions = json.load(f)

    if not isinstance(questions, list):
        raise ValueError(
            f"{path} phải chứa một JSON array."
        )

    seen_ids: set[str] = set()

    for position, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"Phần tử thứ {position} không phải JSON object."
            )

        question_id = item.get("id")
        question = item.get("question")

        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(
                f"Phần tử thứ {position} thiếu id hợp lệ."
            )

        if not isinstance(question, str) or not question.strip():
            raise ValueError(
                f"Câu hỏi {question_id} thiếu question hợp lệ."
            )

        if question_id in seen_ids:
            raise ValueError(
                f"ID câu hỏi bị trùng: {question_id}"
            )

        seen_ids.add(question_id)

    return questions


# ============================================================
# 2. GENERATE ZERO-SHOT ANSWER
# ============================================================

def answer_question(
    question: str,
    model: str,
) -> str:
    """
    Generate an answer using Ollama.

    Only the question and system instructions are provided.
    No retrieved chunks or RAG context are used.
    """

    response = ollama.chat(
    model=model,
    messages=[
        {
            "role": "system",
            "content": (
                "Bạn là trợ lý trả lời câu hỏi pháp luật Việt Nam. "
                "Trả lời bằng tiếng Việt, rõ ràng và trực tiếp. "
                "Không bịa số điều, khoản hoặc điểm pháp luật. "
                "Nếu không chắc chắn, hãy nói rõ giới hạn kiến thức."
            ),
        },
        {
            "role": "user",
            "content": question,
        },
    ],
    options={
        "temperature": 0,
        "num_predict": 512,
        "repeat_penalty": 1.15,     # Phạt nặng các token bị lặp lại (thường dùng từ 1.1 đến 1.2)
        "repeat_last_n": 64,        # Số lượng token gần nhất cần kiểm tra lặp
    },
)

    return response["message"]["content"].strip()


# ============================================================
# 3. RUN ZERO-SHOT BENCHMARK
# ============================================================

def run_benchmark(
    questions_path: Path,
    output_path: Path,
    model: str,
) -> list[dict[str, Any]]:
    """Run zero-shot inference for every question."""

    questions = load_questions(questions_path)
    results: list[dict[str, Any]] = []

    print(f"Model: {model}")
    print(f"Questions: {questions_path}")
    print(f"Total questions: {len(questions)}")
    print("-" * 60)

    for i, item in enumerate(questions, start=1):
        question_id = item["id"]
        question = item["question"]

        try:
            answer = answer_question(
                question=question,
                model=model,
            )

            results.append({
                "question_id": question_id,
                "question": question,
                "answer": answer,
                "method": "zero_shot",
                "model": model,
                "context_used": False,
            })

            print(
                f"[{i}/{len(questions)}] "
                f"{question_id}: OK"
            )

        except Exception as exc:
            results.append({
                "question_id": question_id,
                "question": question,
                "answer": None,
                "method": "zero_shot",
                "model": model,
                "context_used": False,
                "error": str(exc),
            })

            print(
                f"[{i}/{len(questions)}] "
                f"{question_id}: ERROR - {exc}"
            )

    # Create output directory if it does not exist.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Save generated answers.
    output_path.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    success = sum(
        result["answer"] is not None
        for result in results
    )

    failed = len(results) - success

    print("-" * 60)
    print(f"Total: {len(results)}")
    print(f"Successful: {success}")
    print(f"Failed: {failed}")
    print(f"Output: {output_path.resolve()}")

    return results


# ============================================================
# 4. CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run zero-shot LLM baseline "
            "using local Ollama without RAG."
        )
    )

    parser.add_argument(
        "--questions",
        type=Path,
        default=QUERIES_DEV_PATH,
        help="Path to the development questions JSON.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Path to save generated answers.",
    )

    parser.add_argument(
        "--model",
        default="qwen2.5:7b",
        help="Ollama model name.",
    )

    args = parser.parse_args()

    try:
        run_benchmark(
            questions_path=args.questions,
            output_path=args.output,
            model=args.model,
        )

    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    except Exception as exc:
        parser.error(
            f"Không thể chạy benchmark: {exc}"
        )


if __name__ == "__main__":
    main()
