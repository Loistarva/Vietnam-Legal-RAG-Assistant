"""
Evaluate generated answers with traditional Exact Match, token-level F1,
and Rubric evaluation (Answer Relevance & Faithfulness).
No LLM/API is required (Deterministic Rubric Scorer with LLM-Judge hook).

Default inputs:
  data/benchmark/ground_truth.json
  evaluation/results/zero_shot_dev_results.json

Outputs:
  evaluation/results/zero_shot_dev_metrics.json
  evaluation/results/zero_shot_dev_scored.json
  evaluation/results/zero_shot_dev_rubric_table.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import string
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
RUBRIC_CSV_PATH = (
    ROOT_DIR / "evaluation" / "results" / "zero_shot_dev_rubric_table.csv"
)

ID_KEYS = ("query_id", "id")
ANSWER_KEYS = ("answer", "expected_answer")
# Tên khoá (relevance, faithfulness) theo nguồn điểm rubric
RUBRIC_KEYS = {
    "manual": ("answer_relevance", "faithfulness"),
    "lexical": ("lexical_relevance", "lexical_faithfulness"),
}


def rubric_means(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Trung bình điểm rubric tách theo nguồn: chấm tay và lexical; nguồn không có câu nào thì None."""
    output: dict[str, Any] = {}
    for source, (rel_key, faith_key) in RUBRIC_KEYS.items():
        subset = [r for r in rows if r.get("rubric_source") == source]
        prefix = "mean_" if source == "manual" else ""
        for key, digits in ((rel_key, 4), (faith_key, 4), (f"{rel_key}_score", 2), (f"{faith_key}_score", 2)):
            output[prefix + key] = round(sum(r[key] for r in subset) / len(subset), digits) if subset else None
        output["rubric_scored_questions" if source == "manual" else "lexical_scored_questions"] = len(subset)
    return output


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    """Normalize text for EM/F1: lowercase, normalize Unicode, remove punctuation."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = "".join(" " if ch in string.punctuation else ch for ch in text)
    text = re.sub(r"[“”‘’.,;:!?(){}\[\]<>/\\|~`@#$%^&*_+=—–-]", " ", text)
    return " ".join(text.split())


def tokenize(text: str) -> list[str]:
    """Whitespace tokenization after normalization."""
    normalized = normalize_text(text)
    return normalized.split() if normalized else []


def exact_match(prediction: str, reference: str) -> float:
    """Exact match after normalization."""
    return float(normalize_text(prediction) == normalize_text(reference))


def token_f1(prediction: str, reference: str) -> float:
    """Token-overlap F1 (multiset overlap)."""
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


def compute_rubric_scores(
    question: str,
    prediction: str,
    references: list[str],
    category: str = "",
    ground_truth_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Chấm điểm theo Rubric cho câu trả lời Zero-shot:
    - answer_relevance (1-5 và chuẩn hóa 0.0-1.0): mức độ bao phủ trọng tâm câu hỏi.
    - faithfulness (1-5 và chuẩn hóa 0.0-1.0): mức độ trung thực, căn cứ pháp lý, phạt văn bản hết hiệu lực.
    """
    pred_str = str(prediction or "").strip()
    q_str = str(question or "").strip()
    ref_str = references[0] if references else ""
    best_f1 = max(token_f1(pred_str, ref) for ref in references) if references else 0.0

    # 1. Answer Relevance (1-5)
    if not pred_str:
        rel_score = 1
        rel_rationale = "Câu trả lời rỗng hoặc không có nội dung."
    else:
        # Kiểm tra câu từ chối trả lời né tránh
        refusal_patterns = [
            r"tôi không biết",
            r"không có thông tin",
            r"không thể trả lời",
            r"chưa rõ quy định",
            r"xin lỗi",
        ]
        is_refusal = any(re.search(pat, pred_str.lower()) for pat in refusal_patterns)

        # Trích xuất từ khóa nội dung từ câu hỏi
        stop_words = {
            "là", "gì", "thế", "nào", "như", "được", "không", "ai", "bao", "nhiêu",
            "có", "hay", "với", "cho", "ở", "tại", "theo", "quy", "định", "của",
            "về", "trong", "phải", "khi", "để", "ra", "sao", "các", "những",
        }
        q_tokens = [tok for tok in tokenize(q_str) if tok not in stop_words and len(tok) >= 2]
        pred_norm = normalize_text(pred_str)

        matched_q = sum(1 for tok in q_tokens if tok in pred_norm)
        cov = matched_q / len(q_tokens) if q_tokens else 1.0

        if is_refusal and cov < 0.3:
            rel_score = 2
            rel_rationale = "Từ chối trả lời hoặc né tránh câu hỏi."
        elif cov >= 0.6 or best_f1 >= 0.45:
            rel_score = 5
            rel_rationale = "Đi thẳng vào trọng tâm, bao quát đầy đủ chủ đề và thuật ngữ trong câu hỏi."
        elif cov >= 0.35 or best_f1 >= 0.25:
            rel_score = 4
            rel_rationale = "Đúng trọng tâm câu hỏi, đề cập các khía cạnh chính."
        elif cov >= 0.15 or best_f1 >= 0.1:
            rel_score = 3
            rel_rationale = "Đề cập một phần chủ đề nhưng còn thiếu trọng tâm."
        else:
            rel_score = 2
            rel_rationale = "Câu trả lời ít liên quan đến nội dung câu hỏi."

    # 2. Faithfulness (1-5)
    gt_item = ground_truth_item or {}
    outdated_docs = gt_item.get("outdated_document_ids") or []
    is_historical = category == "historical_law" or "lịch sử" in q_str.lower() or "2000" in q_str

    if not pred_str:
        faith_score = 1
        faith_rationale = "Không có câu trả lời."
    else:
        # Kiểm tra phạt trích dẫn luật cũ/hết hiệu lực khi hỏi luật hiện hành
        cites_expired = False
        expired_patterns = [
            r"luật hôn nhân và gia đình (năm )?2000",
            r"22/2000/qh10",
            r"nghị định 70/2001",
        ]
        if not is_historical:
            for pat in expired_patterns:
                if re.search(pat, pred_str.lower()):
                    cites_expired = True
                    break

        if cites_expired and not is_historical:
            faith_score = 1
            faith_rationale = "Vi phạm nghiêm trọng tính trung thực: viện dẫn văn bản/luật đã hết hiệu lực cho câu hỏi hiện hành."
        else:
            # Kiểm tra số liệu cụ thể (tuổi, số năm, tỷ lệ)
            nums_in_ref = set(re.findall(r"\b\d+\b", ref_str))
            nums_in_pred = set(re.findall(r"\b\d+\b", pred_str))
            conflicting_nums = False
            if nums_in_ref and nums_in_pred:
                overlap_nums = nums_in_ref & nums_in_pred
                if not overlap_nums and len(nums_in_ref) <= 3:
                    conflicting_nums = True

            if best_f1 >= 0.6 and not conflicting_nums:
                faith_score = 5
                faith_rationale = "Hoàn toàn trung thực với căn cứ pháp lý, khớp nội dung chuẩn."
            elif best_f1 >= 0.35 and not conflicting_nums:
                faith_score = 4
                faith_rationale = "Khớp các ý chính của căn cứ pháp lý, kết luận chính xác."
            elif best_f1 >= 0.15:
                faith_score = 3
                faith_rationale = "Đúng một phần nội dung quy định nhưng còn thiếu sót hoặc chưa chuẩn xác."
            elif best_f1 > 0.0:
                faith_score = 2
                faith_rationale = "Nội dung mâu thuẫn một phần hoặc sai lệch số liệu so với đáp án chuẩn."
            else:
                faith_score = 1
                faith_rationale = "Sai lệch hoàn toàn căn cứ pháp lý so với đáp án chuẩn."

    # Chuẩn hóa về 0.0 - 1.0 theo thang 1-5: (score - 1) / 4.0
    rel_norm = round((rel_score - 1.0) / 4.0, 4)
    faith_norm = round((faith_score - 1.0) / 4.0, 4)
    full_rationale = f"Relevance: {rel_rationale} | Faithfulness: {faith_rationale}"

    return {
        "answer_relevance_score": rel_score,
        "faithfulness_score": faith_score,
        "answer_relevance": rel_norm,
        "faithfulness": faith_norm,
        "rubric_rationale": full_rationale,
    }


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
    """Return ID -> record/value."""
    if isinstance(data, dict):
        for wrapper in ("data", "items", "questions", "ground_truth", "results"):
            if isinstance(data.get(wrapper), list):
                data = data[wrapper]
                break
        else:
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
            raise ValueError(f"Phần tử thứ {index + 1} thiếu query_id hoặc id hợp lệ.")
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


def load_categories(queries_paths: list[Path] | tuple[Path, ...]) -> dict[str, str]:
    """Read category by id from the given question files."""
    categories: dict[str, str] = {}
    for path in queries_paths:
        rows = load_json(path)
        if not isinstance(rows, list):
            raise ValueError(f"{path} phải chứa một JSON array.")
        for position, row in enumerate(rows, start=1):
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                raise ValueError(f"{path}: phần tử thứ {position} thiếu id hợp lệ.")
            if row.get("category"):
                categories[row["id"]] = row["category"]
    return categories


def evaluate(
    predictions_path: Path,
    ground_truth_path: Path,
    metrics_output_path: Path,
    scored_output_path: Path,
    rubric_csv_path: Path | None = None,
    queries_paths: list[Path] | tuple[Path, ...] = (),
    rubric_input_path: Path | None = None,
) -> dict[str, Any]:
    predictions_data = load_json(predictions_path)
    ground_truth_data = load_json(ground_truth_path)

    predictions = records_by_id(predictions_data, is_ground_truth=False)
    ground_truth = records_by_id(ground_truth_data, is_ground_truth=True)

    manual_rubric: dict[str, dict[str, Any]] = {}
    if rubric_input_path and Path(rubric_input_path).exists():
        p_rub = Path(rubric_input_path)
        if p_rub.suffix.lower() == ".csv":
            with p_rub.open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    qid = row.get("query_id") or row.get("id")
                    if qid:
                        manual_rubric[qid] = row
        else:
            rub_data = load_json(p_rub)
            manual_rubric = records_by_id(rub_data, is_ground_truth=False)

    scored: list[dict[str, Any]] = []
    missing_reference_ids: list[str] = []
    missing_prediction_ids: list[str] = []

    em_values: list[float] = []
    f1_values: list[float] = []

    categories_by_id = load_categories(queries_paths)

    for question_id, prediction_record in predictions.items():
        if question_id not in ground_truth:
            missing_reference_ids.append(question_id)
            continue

        prediction = get_prediction(prediction_record)
        gt_item = ground_truth[question_id] if isinstance(ground_truth[question_id], dict) else {}
        references = get_references(ground_truth[question_id])

        if not references:
            missing_reference_ids.append(question_id)
            continue

        em = max(exact_match(prediction, ref) for ref in references)
        f1 = max(token_f1(prediction, ref) for ref in references)

        em_values.append(em)
        f1_values.append(f1)

        cat = None
        if isinstance(prediction_record, dict):
            cat = prediction_record.get("category")
        if not cat and isinstance(gt_item, dict):
            cat = gt_item.get("category")
        if not cat:
            cat = categories_by_id.get(question_id)

        q_text = ""
        if isinstance(prediction_record, dict):
            q_text = prediction_record.get("question") or ""
        if not q_text and isinstance(gt_item, dict):
            q_text = gt_item.get("question") or gt_item.get("query") or ""

        # Rubric scoring: điểm chấm tay (rubric_input_path) ghi dưới tên answer_relevance,
        # faithfulness; điểm compute_rubric_scores suy từ từ vựng chỉ là số tham khảo,
        # ghi dưới tên lexical_* để không bị lấy nhầm vào báo cáo (F6)
        if question_id in manual_rubric:
            m_row = manual_rubric[question_id]
            rel_1_5 = int(m_row.get("answer_relevance_score", 3))
            faith_1_5 = int(m_row.get("faithfulness_score", 3))
            rel_norm = float(m_row.get("answer_relevance", (rel_1_5 - 1.0) / 4.0))
            faith_norm = float(m_row.get("faithfulness", (faith_1_5 - 1.0) / 4.0))
            rationale = str(m_row.get("rubric_rationale", "Chấm điểm thủ công từ bảng ngoài."))
            source = "manual"
        else:
            rub_result = compute_rubric_scores(
                question=q_text,
                prediction=prediction,
                references=references,
                category=cat or "",
                ground_truth_item=gt_item,
            )
            rel_1_5 = rub_result["answer_relevance_score"]
            faith_1_5 = rub_result["faithfulness_score"]
            rel_norm = rub_result["answer_relevance"]
            faith_norm = rub_result["faithfulness"]
            rationale = rub_result["rubric_rationale"]
            source = "lexical"

        rel_key, faith_key = RUBRIC_KEYS[source]
        scored.append({
            "query_id": question_id,
            "category": cat,
            "question": q_text,
            "prediction": prediction,
            "expected_answer": references[0] if references else "",
            "references": references,
            "exact_match": em,
            "token_f1": f1,
            "rubric_source": source,
            f"{rel_key}_score": rel_1_5,
            f"{faith_key}_score": faith_1_5,
            rel_key: rel_norm,
            faith_key: faith_norm,
            "rubric_rationale": rationale,
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
                "exact_match": round(sum(r["exact_match"] for r in rows) / len(rows), 4),
                "token_f1": round(sum(r["token_f1"] for r in rows) / len(rows), 4),
                **rubric_means(rows),
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
        "metric_type": "lexical_overlap_and_rubric_evaluation",
        "normalization": (
            "Unicode NFKC, case-insensitive, punctuation removed, "
            "whitespace tokenization"
        ),
        "exact_match": round(sum(em_values) / evaluated_count, 4) if evaluated_count else 0.0,
        "token_f1": round(sum(f1_values) / evaluated_count, 4) if evaluated_count else 0.0,
        **rubric_means(scored),
        "evaluated_questions": evaluated_count,
        "prediction_records": len(predictions),
        "ground_truth_records": len(ground_truth),
        "prediction_ids_without_reference": missing_reference_ids,
        "ground_truth_ids_without_prediction": missing_prediction_ids,
        "note": (
            "Kết quả đánh giá gồm Lexical Overlap (Exact Match, Token F1) và Rubric Scoring "
            "(thang 1-5 và chuẩn hóa 0.0-1.0). mean_answer_relevance*, mean_faithfulness* chỉ tính trên "
            "các câu chấm tay (rubric_scored_questions); lexical_* là điểm suy từ từ vựng, chỉ để tham khảo."
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

    # Xuất bảng CSV Rubric chi tiết, chỉ khi được truyền đường dẫn (main truyền RUBRIC_CSV_PATH)
    if rubric_csv_path is not None:
        rubric_csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_columns = [
            "query_id",
            "category",
            "question",
            "prediction",
            "expected_answer",
            "exact_match",
            "token_f1",
            "rubric_source",
            "answer_relevance_score",
            "faithfulness_score",
            "lexical_relevance_score",
            "lexical_faithfulness_score",
            "rubric_rationale",
        ]
        with rubric_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction="ignore")
            writer.writeheader()
            for row in scored:
                writer.writerow(row)

    def fmt(key: str, digits: int) -> str:
        value = summary.get(key)
        return "n/a" if value is None else f"{value:.{digits}f}"

    print("=== Answer Evaluation ===")
    print(f"Evaluated questions: {evaluated_count}")
    print(f"Exact Match:             {summary['exact_match']:.4f}")
    print(f"Token F1:                {summary['token_f1']:.4f}")
    print(f"Rubric (chấm tay):       {summary['rubric_scored_questions']} câu")
    print(f"Mean Answer Relevance:   {fmt('mean_answer_relevance', 4)} (Score: {fmt('mean_answer_relevance_score', 2)}/5)")
    print(f"Mean Faithfulness:       {fmt('mean_faithfulness', 4)} (Score: {fmt('mean_faithfulness_score', 2)}/5)")
    print(f"Lexical (tham khảo):     relevance {fmt('lexical_relevance', 4)}, faithfulness {fmt('lexical_faithfulness', 4)}")
    print(f"Metrics:                 {metrics_output_path.resolve()}")
    print(f"Per-question scores:     {scored_output_path.resolve()}")
    if rubric_csv_path is not None:
        print(f"Rubric CSV table:        {rubric_csv_path.resolve()}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate generated answers with Exact Match, token F1, and Rubric."
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
    parser.add_argument(
        "--rubric-csv",
        type=Path,
        default=RUBRIC_CSV_PATH,
        help="Detailed Rubric CSV output path.",
    )
    parser.add_argument(
        "--rubric-input",
        type=Path,
        default=None,
        help="Optional manual Rubric grades CSV/JSON to aggregate.",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        nargs="*",
        default=[ROOT_DIR / "data" / "benchmark" / "queries_dev.json"],
        help="Question files giving each id its category (by_category).",
    )
    args = parser.parse_args()

    evaluate(
        predictions_path=args.predictions,
        ground_truth_path=args.ground_truth,
        metrics_output_path=args.metrics_output,
        scored_output_path=args.scored_output,
        rubric_csv_path=args.rubric_csv,
        queries_paths=args.queries,
        rubric_input_path=args.rubric_input,
    )


if __name__ == "__main__":
    main()
