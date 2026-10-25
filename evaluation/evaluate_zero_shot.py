"""
Evaluate generated answers with traditional Exact Match and token-level F1.
No LLM/API is called.

Default inputs:
  data/benchmark/ground_truth.json
  evaluation/results/zero_shot_dev_results.json

Outputs:
  evaluation/results/zero_shot_dev_metrics.json
  evaluation/results/zero_shot_dev_scored.json

Ground-truth JSON formats supported:
1) [{"id": "HN_001", "answer": "..."}]
2) {"HN_001": "...", "HN_002": "..."}
3) [{"question_id": "HN_001", "answers": ["...", "..."]}]
4) {"data": [{"id": "HN_001", "ground_truth": "..."}]}
"""

from __future__ import annotations

import argparse
import json
import re
import string
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]

GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
PREDICTIONS_PATH = (
    ROOT_DIR / "evaluation" / "results" / "zero_shot_dev_results.json"
)
METRICS_OUTPUT_PATH = (
    ROOT_DIR / "evaluation" / "results" / "zero_shot_dev_metrics.json"
)
SCORED_OUTPUT_PATH = (
    ROOT_DIR / "evaluation" / "results" / "zero_shot_dev_scored.json"
)

ID_KEYS = ("query_id", "id")
ANSWER_KEYS = ("answer", "expected_answer")


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    """Normalize text for EM/F1: lowercase, normalize Unicode, remove punctuation."""
    text = unicodedata.normalize("NFKC", text).casefold()
    # Replace punctuation with spaces so tokens do not accidentally merge.
    text = "".join(" " if ch in string.punctuation else ch for ch in text)
    text = re.sub(r"[“”‘’.,;:!?(){}\[\]<>/\\|~`@#$%^&*_+=—–-]", " ", text)
    return " ".join(text.split())


def tokenize(text: str) -> list[str]:
    """Whitespace tokenization after normalization; suitable as a simple baseline."""
    normalized = normalize_text(text)
    return normalized.split() if normalized else []


def exact_match(prediction: str, reference: str) -> float:
    """Exact match after normalization."""
    return float(normalize_text(prediction) == normalize_text(reference))


def token_f1(prediction: str, reference: str) -> float:
    """Token-overlap F1 (multiset overlap), without any model or external library."""
    pred_tokens = tokenize(prediction)
    ref_tokens = tokenize(reference)

    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0

    overlap = sum((Counter(pred_tokens) & Counter(ref_tokens)).values())
    if overlap == 0:
        return 0.0

    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def as_text_list(value: Any) -> list[str]:
    """Convert a reference answer or a list of reference answers into strings."""
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                output.append(item)
            elif isinstance(item, dict):
                nested = extract_answer_value(item)
                output.extend(nested)
        return output
    if isinstance(value, dict):
        return extract_answer_value(value)
    return []


def extract_answer_value(item: dict[str, Any]) -> list[str]:
    for key in ANSWER_KEYS:
        if key in item:
            values = as_text_list(item[key])
            if values:
                return values
    return []


def extract_id(item: dict[str, Any]) -> str | None:
    for key in ID_KEYS:
        value = item.get(key)
        if isinstance(value, (str, int)):
            return str(value)
    return None


def records_by_id(data: Any, *, is_ground_truth: bool) -> dict[str, Any]:
    """
    Return ID -> record/value. Supports list-of-objects and ID-keyed dictionaries.
    """
    if isinstance(data, dict):
        # Common wrapper keys.
        for wrapper in ("data", "items", "questions", "ground_truth", "results"):
            if isinstance(data.get(wrapper), list):
                data = data[wrapper]
                break
        else:
            # ID -> string/list/object mapping.
            if all(isinstance(k, str) for k in data):
                return {str(k): v for k, v in data.items()}

    if not isinstance(data, list):
        raise ValueError("JSON phải là list hoặc object ánh xạ ID.")

    output: dict[str, Any] = {}
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Phần tử thứ {index + 1} không phải object JSON.")
        item_id = extract_id(item)
        if item_id is None:
            raise ValueError(
                f"Phần tử thứ {index + 1} thiếu query_id hoặc id hợp lệ."
            )
        if item_id in output:
            raise ValueError(f"ID bị trùng trong file: {item_id}")
        output[item_id] = item
    return output


def get_prediction(record: Any) -> str:
    if isinstance(record, str):
        return record
    if isinstance(record, dict):
        for key in ("answer", "prediction", "generated_answer", "response"):
            value = record.get(key)
            if isinstance(value, str):
                return value
    return ""


def get_references(record: Any) -> list[str]:
    if isinstance(record, str):
        return [record] if record.strip() else []
    if isinstance(record, dict):
        return extract_answer_value(record)
    return as_text_list(record)


def evaluate(
    predictions_path: Path,
    ground_truth_path: Path,
    metrics_output_path: Path,
    scored_output_path: Path,
) -> dict[str, Any]:
    predictions_data = load_json(predictions_path)
    ground_truth_data = load_json(ground_truth_path)

    predictions = records_by_id(predictions_data, is_ground_truth=False)
    ground_truth = records_by_id(ground_truth_data, is_ground_truth=True)

    scored: list[dict[str, Any]] = []
    missing_reference_ids: list[str] = []
    missing_prediction_ids: list[str] = []

    em_values: list[float] = []
    f1_values: list[float] = []

    categories_by_id: dict[str, str] = {}
    for qpath in (ROOT_DIR / "data" / "benchmark" / "queries_dev.json", ROOT_DIR / "data" / "benchmark" / "queries_test.json"):
        if qpath.is_file():
            try:
                for qrow in json.loads(qpath.read_text(encoding="utf-8")):
                    if isinstance(qrow, dict) and "id" in qrow and "category" in qrow:
                        categories_by_id[qrow["id"]] = qrow["category"]
            except Exception:
                pass

    # Evaluate every prediction with a matching ground-truth ID.
    for question_id, prediction_record in predictions.items():
        if question_id not in ground_truth:
            missing_reference_ids.append(question_id)
            continue

        prediction = get_prediction(prediction_record)
        references = get_references(ground_truth[question_id])

        if not references:
            missing_reference_ids.append(question_id)
            continue

        # If multiple references exist, take the best score for each metric.
        em = max(exact_match(prediction, ref) for ref in references)
        f1 = max(token_f1(prediction, ref) for ref in references)

        em_values.append(em)
        f1_values.append(f1)
        cat = None
        if isinstance(prediction_record, dict):
            cat = prediction_record.get("category")
        if not cat and isinstance(ground_truth.get(question_id), dict):
            cat = ground_truth[question_id].get("category")
        if not cat:
            cat = categories_by_id.get(question_id)

        scored.append({
            "query_id": question_id,
            "question_id": question_id,
            "category": cat,
            "prediction": prediction,
            "references": references,
            "exact_match": em,
            "token_f1": f1,
        })

    for question_id in ground_truth:
        if question_id not in predictions:
            missing_prediction_ids.append(question_id)

    evaluated_count = len(scored)
    category_scores: dict[str, list[dict[str, Any]]] = {}
    for row in scored:
        c = row.get("category")
        if c:
            category_scores.setdefault(c, []).append(row)

    by_category: dict[str, dict[str, Any]] = {}
    if category_scores:
        for c, rows in category_scores.items():
            by_category[c] = {
                "exact_match": sum(r["exact_match"] for r in rows) / len(rows),
                "token_f1": sum(r["token_f1"] for r in rows) / len(rows),
                "count": len(rows),
            }

    summary = {
        "method": (
            predictions_data[0].get("method", "unknown")
            if isinstance(predictions_data, list)
            and predictions_data
            and isinstance(predictions_data[0], dict)
            else "unknown"
        ),
        "metric_type": "traditional_text_overlap",
        "normalization": (
            "Unicode NFKC, case-insensitive, punctuation removed, "
            "whitespace tokenization"
        ),
        "exact_match": sum(em_values) / evaluated_count if evaluated_count else 0.0,
        "token_f1": sum(f1_values) / evaluated_count if evaluated_count else 0.0,
        "evaluated_questions": evaluated_count,
        "prediction_records": len(predictions),
        "ground_truth_records": len(ground_truth),
        "prediction_ids_without_reference": missing_reference_ids,
        "ground_truth_ids_without_prediction": missing_prediction_ids,
        "note": (
            "Exact Match and token F1 are lexical-overlap metrics. "
            "They do not call an LLM and may penalize semantically correct "
            "answers that use different wording."
        ),
    }
    if by_category:
        summary["by_category"] = by_category

    metrics_output_path.parent.mkdir(parents=True, exist_ok=True)
    scored_output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    scored_output_path.write_text(
        json.dumps(scored, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== Answer Evaluation ===")
    print(f"Evaluated questions: {evaluated_count}")
    print(f"Exact Match: {summary['exact_match']:.4f}")
    print(f"Token F1:    {summary['token_f1']:.4f}")
    print(f"Metrics: {metrics_output_path.resolve()}")
    print(f"Per-question scores: {scored_output_path.resolve()}")

    if missing_reference_ids:
        print(
            "Warning: predictions missing matching reference: "
            + ", ".join(missing_reference_ids)
        )
    if missing_prediction_ids:
        print(
            "Warning: references missing predictions: "
            + ", ".join(missing_prediction_ids)
        )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate generated answers with Exact Match and token F1."
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=PREDICTIONS_PATH,
        help="JSON output from zero-shot/RAG generation.",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=GROUND_TRUTH_PATH,
        help="Reference answers JSON.",
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=METRICS_OUTPUT_PATH,
        help="Summary metrics JSON output.",
    )
    parser.add_argument(
        "--scored-output",
        type=Path,
        default=SCORED_OUTPUT_PATH,
        help="Per-question score JSON output.",
    )
    args = parser.parse_args()

    evaluate(
        predictions_path=args.predictions,
        ground_truth_path=args.ground_truth,
        metrics_output_path=args.metrics_output,
        scored_output_path=args.scored_output,
    )


if __name__ == "__main__":
    main()
