"""Các metric truy xuất: Recall@K, MRR@K, NDCG@K."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence

DEFAULT_KS = (1, 3, 5)


# ----------------------------------------------------------------------
# Metric cho MỘT câu hỏi
# ----------------------------------------------------------------------
def _top_k_unique(retrieved: Sequence[str], k: int) -> list[str]:
    """Lấy top-k theo thứ hạng, bỏ id trùng để một gold không bị đếm hai lần."""
    seen: set[str] = set()
    top: list[str] = []
    for chunk_id in retrieved:
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        top.append(chunk_id)
        if len(top) == k:
            break
    return top


def recall_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    """Tỉ lệ chunk gold xuất hiện trong top-k."""
    if not gold:
        raise ValueError("gold không được rỗng")
    hits = sum(1 for chunk_id in _top_k_unique(retrieved, k) if chunk_id in gold)
    return hits / len(gold)


def mrr_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    """1 / hạng của chunk gold đầu tiên trong top-k (0 nếu không có)."""
    if not gold:
        raise ValueError("gold không được rỗng")
    for rank, chunk_id in enumerate(_top_k_unique(retrieved, k), start=1):
        if chunk_id in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    """NDCG@K với mức liên quan nhị phân."""
    if not gold:
        raise ValueError("gold không được rỗng")
    top = _top_k_unique(retrieved, k)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, chunk_id in enumerate(top, start=1)
        if chunk_id in gold
    )
    ideal_hits = min(len(gold), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg


def score_question(
    retrieved: Sequence[str], gold: set[str], ks: Sequence[int] = DEFAULT_KS
) -> dict[str, float]:
    """Tính toàn bộ metric cho một câu hỏi."""
    scores: dict[str, float] = {}
    for k in ks:
        scores[f"recall@{k}"] = recall_at_k(retrieved, gold, k)
        scores[f"mrr@{k}"] = mrr_at_k(retrieved, gold, k)
        scores[f"ndcg@{k}"] = ndcg_at_k(retrieved, gold, k)
    return scores


# ----------------------------------------------------------------------
# Đọc dữ liệu
# ----------------------------------------------------------------------
def _read_json_array(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} phải chứa một JSON array.")
    return data


def load_gold(ground_truth_path: str | Path) -> dict[str, set[str]]:
    """Đọc ground_truth.json: id -> tập gold_context_ids (có thể rỗng)."""
    gold: dict[str, set[str]] = {}
    for position, item in enumerate(_read_json_array(ground_truth_path), start=1):
        question_id = item.get("id")
        gold_ids = item.get("gold_context_ids")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"Phần tử thứ {position} thiếu id hợp lệ.")
        if not isinstance(gold_ids, list):
            raise ValueError(f"Câu hỏi {question_id!r} thiếu gold_context_ids.")
        if question_id in gold:
            raise ValueError(f"ID trùng trong ground truth: {question_id}")
        gold[question_id] = {str(chunk_id) for chunk_id in gold_ids}
    return gold


# ----------------------------------------------------------------------
# Metric cho CẢ TẬP
# ----------------------------------------------------------------------
def load_categories(queries_paths: Sequence[str | Path]) -> dict[str, str]:
    """Đọc category theo id từ các file câu hỏi được truyền vào; lỗi đọc file thì báo lỗi."""
    categories: dict[str, str] = {}
    for path in queries_paths:
        for position, row in enumerate(_read_json_array(path), start=1):
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                raise ValueError(f"{path}: phần tử thứ {position} thiếu id hợp lệ.")
            if row.get("category"):
                categories[row["id"]] = row["category"]
    return categories


def evaluate(
    results_path: str | Path,
    ground_truth_path: str | Path,
    output_path: str | Path | None = None,
    ks: Sequence[int] = DEFAULT_KS,
    queries_paths: Sequence[str | Path] = (),
) -> dict[str, Any]:
    """Chấm điểm file kết quả retrieval so với ground_truth.json.

    Chỉ chấm những câu có trong file kết quả. Câu có gold rỗng (chưa map)
    được bỏ qua và ghi lại trong 'skipped'. Mỗi kết quả phải có ``query_id``
    (docs/sprint6_benchmark.md mục 10). Số đo theo category lấy category từ
    kết quả hoặc từ ``queries_paths``.
    """
    categories_by_id = load_categories(queries_paths)

    gold_by_id = load_gold(ground_truth_path)
    results = _read_json_array(results_path)

    per_question: list[dict[str, Any]] = []
    skipped: list[str] = []

    for item in results:
        question_id = item.get("query_id")
        if not question_id:
            if "question_id" in item:
                raise ValueError(f"Kết quả dùng question_id; đầu ra phải dùng query_id: {item.get('question_id')}")
            raise ValueError(f"Mỗi kết quả phải có query_id: {item}")
        if question_id not in gold_by_id:
            raise ValueError(
                f"Câu hỏi {question_id!r} có trong kết quả nhưng không có trong "
                "ground truth."
            )
        gold = gold_by_id[question_id]
        if not gold:
            skipped.append(question_id)
            continue

        scores = score_question(item["retrieved_chunk_ids"], gold, ks)
        entry = {"query_id": question_id, **scores}
        cat = item.get("category") or categories_by_id.get(question_id)
        if cat:
            entry["category"] = cat
        per_question.append(entry)

    if not per_question:
        raise ValueError("Không có câu hỏi nào có gold để chấm điểm.")

    metric_names = [key for key in per_question[0] if key not in ("query_id", "category")]
    average = {
        name: sum(row[name] for row in per_question) / len(per_question)
        for name in metric_names
    }

    category_scores: dict[str, list[dict[str, Any]]] = {}
    for row in per_question:
        cat = row.get("category")
        if cat:
            category_scores.setdefault(cat, []).append(row)

    by_category: dict[str, dict[str, float]] = {}
    if category_scores:
        for cat, rows in category_scores.items():
            by_category[cat] = {
                name: sum(r[name] for r in rows) / len(rows)
                for name in metric_names
            }

    report = {
        "num_questions": len(per_question),
        "num_skipped": len(skipped),
        "skipped": skipped,
        "average": average,
        "per_question": per_question,
    }
    if by_category:
        report["by_category"] = by_category

    print(f"Đã chấm {len(per_question)} câu (bỏ qua {len(skipped)} câu chưa có gold)")
    for name, value in average.items():
        print(f"  {name}: {value:.4f}")

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Đã lưu báo cáo vào: {output.resolve()}")

    return report