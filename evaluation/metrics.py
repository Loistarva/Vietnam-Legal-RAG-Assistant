"""Shared retrieval metrics: chunk/parent Recall, MRR, and NDCG."""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_KS = (5, 10)
BOOTSTRAP_CONFIDENCE_LEVEL = 0.95
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 42


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


def _top_k_unique_indices(retrieved: Sequence[str], k: int) -> list[int]:
    """Vị trí (trong danh sách gốc) của top-k chunk sau khi bỏ id trùng.

    Dùng chung cho Strict và Parent Match để hai metric nhìn cùng một tập K chunk.
    """
    seen: set[str] = set()
    indices: list[int] = []
    for index, chunk_id in enumerate(retrieved):
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        indices.append(index)
        if len(indices) == k:
            break
    return indices


def strict_match_recall_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    """Fraction of gold chunks retrieved in the unique top-k."""
    if not gold:
        raise ValueError("gold không được rỗng")
    hits = sum(chunk_id in gold for chunk_id in _top_k_unique(retrieved, k))
    return hits / len(gold)


def parent_match_recall_at_k(
    top_parent_ids: Sequence[str], gold_parent_ids: set[str]
) -> float:
    """Fraction of unique gold parent clauses retrieved in top-K chunks.

    ``top_parent_ids`` là parent của top-K chunk đã bỏ trùng chunk ID
    (xem ``_top_k_unique_indices``). Các parent ID trùng nhau chỉ được
    tính một lần.
    """
    if not gold_parent_ids:
        raise ValueError("gold_parent_ids không được rỗng")

    retrieved_parents = set(top_parent_ids)
    hits = len(retrieved_parents & gold_parent_ids)
    return hits / len(gold_parent_ids)


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
        top = _top_k_unique(retrieved, k)
        scores[f"strict_match_recall@{k}"] = strict_match_recall_at_k(
            top, gold, k
        )
        scores[f"mrr@{k}"] = mrr_at_k(top, gold, k)
        scores[f"ndcg@{k}"] = ndcg_at_k(top, gold, k)
        scores[f"precision@{k}"] = sum(chunk_id in gold for chunk_id in top) / k
    return scores


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]
    fraction = position - lower_index
    return (
        sorted_values[lower_index] * (1 - fraction)
        + sorted_values[upper_index] * fraction
    )


def _bootstrap_mean_confidence_interval(
    values: Sequence[float | None], rng: random.Random
) -> dict[str, float | int | None]:
    """Percentile-bootstrap CI for a macro mean, resampling questions."""
    observed = [value for value in values if value is not None]
    count = len(observed)
    if not count:
        return {"lower": None, "upper": None, "num_questions": 0}

    bootstrap_means = [
        sum(rng.choices(observed, k=count)) / count
        for _ in range(BOOTSTRAP_RESAMPLES)
    ]
    bootstrap_means.sort()
    alpha = (1 - BOOTSTRAP_CONFIDENCE_LEVEL) / 2
    return {
        "lower": _percentile(bootstrap_means, alpha),
        "upper": _percentile(bootstrap_means, 1 - alpha),
        "num_questions": count,
    }


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


def load_gold(
    ground_truth_path: str | Path,
) -> dict[str, set[str]]:
    """Read only explicitly verified ground chunk IDs."""
    gold: dict[str, set[str]] = {}
    for position, item in enumerate(_read_json_array(ground_truth_path), start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Phần tử thứ {position} trong ground truth phải là object.")
        question_id = item.get("id")
        gold_ids = item.get("gold_context_ids")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"Phần tử thứ {position} thiếu id hợp lệ.")
        if not isinstance(gold_ids, list):
            raise ValueError(f"Câu hỏi {question_id!r} thiếu gold_context_ids.")
        if item.get("gold_context_ids_confirmed") is not True:
            gold_ids = []
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
    *,
    parent_by_chunk: Mapping[str, str] | None = None,
    verified_only: bool = True,
    report_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Chấm điểm file kết quả retrieval so với ground_truth.json.

    Chỉ chấm những câu có trong file kết quả. Câu có gold rỗng (chưa map)
    được bỏ qua và ghi lại trong 'skipped'. Mỗi kết quả phải có ``query_id``
    (docs/sprint6_benchmark.md mục 10). Số đo theo category lấy category từ
    kết quả hoặc từ ``queries_paths``.

    Chỉ chấm trên ``gold_context_ids``; câu không có gold phù hợp bị bỏ qua.
    Báo cáo khoảng tin cậy 95% percentile bootstrap cho trung bình macro,
    resampling câu hỏi độc lập với seed cố định để tái lập kết quả.
    """
    if not ks or any(isinstance(k, bool) or not isinstance(k, int) or k < 1 for k in ks):
        raise ValueError("ks phải chứa các số nguyên dương.")
    if not verified_only:
        raise ValueError("Metric chỉ chấm trên gold_context_ids đã xác nhận.")
    categories_by_id = load_categories(queries_paths)

    gold_by_id = load_gold(ground_truth_path)
    verified_by_id = gold_by_id
    results = _read_json_array(results_path)

    per_question: list[dict[str, Any]] = []
    skipped: list[str] = []

    for position, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Kết quả thứ {position} phải là JSON object.")
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

        retrieved = item.get("retrieved_chunk_ids")
        if not isinstance(retrieved, list) or not all(
            isinstance(chunk_id, str) for chunk_id in retrieved
        ):
            raise ValueError(
                f"Kết quả {question_id!r} thiếu retrieved_chunk_ids hợp lệ."
            )
        scores = score_question(retrieved, gold, ks)
        retrieved_parent_ids = item.get("retrieved_parent_clause_ids")
        if retrieved_parent_ids is None:
            retrieved_parent_ids = [None] * len(retrieved)
        if (
            not isinstance(retrieved_parent_ids, list)
            or len(retrieved_parent_ids) != len(retrieved)
        ):
            raise ValueError(
                f"Kết quả {question_id!r} có retrieved_parent_clause_ids không khớp."
            )

        verified_gold = verified_by_id[question_id]
        gold_parent_ids = {
            parent_by_chunk[chunk_id]
            for chunk_id in verified_gold
            if parent_by_chunk is not None
            and isinstance(parent_by_chunk.get(chunk_id), str)
            and parent_by_chunk[chunk_id].strip()
        }
        # Thiếu metadata nếu: không có map cha, chưa có gold xác minh,
        # hoặc có gold chunk không có parent.
        gold_parent_metadata_missing = (
            parent_by_chunk is None
            or not verified_gold
            or any(
                not isinstance(parent_by_chunk.get(chunk_id), str)
                or not parent_by_chunk[chunk_id].strip()
                for chunk_id in verified_gold
            )
        )
        entry = {"query_id": question_id, **scores}
        parent_metadata_missing_by_k: dict[int, bool] = {}
        for k in ks:
            indices = _top_k_unique_indices(retrieved, k)
            top_parents = [retrieved_parent_ids[i] for i in indices]
            missing = gold_parent_metadata_missing or any(
                not isinstance(parent_id, str) or not parent_id.strip()
                for parent_id in top_parents
            )
            parent_metadata_missing_by_k[k] = missing
            entry[f"parent_match_metadata_missing@{k}"] = missing
            entry[f"parent_match_recall@{k}"] = (
                None
                if missing or not gold_parent_ids
                else parent_match_recall_at_k(top_parents, gold_parent_ids)
            )
        entry["parent_match_metadata_missing"] = any(
            parent_metadata_missing_by_k.values()
        )
        cat = item.get("category") or categories_by_id.get(question_id)
        if cat:
            entry["category"] = cat
        per_question.append(entry)

    if not per_question:
        raise ValueError("Không có câu hỏi nào có gold để chấm điểm.")

    metric_names = [
        key for key in per_question[0]
        if key not in (
            "query_id", "category", "parent_match_metadata_missing"
        )
        and not key.startswith("parent_match_metadata_missing@")
    ]
    average = {
        name: (
            sum(row[name] for row in per_question if row[name] is not None)
            / sum(row[name] is not None for row in per_question)
            if any(row[name] is not None for row in per_question)
            else None
        )
        for name in metric_names
    }

    category_scores: dict[str, list[dict[str, Any]]] = {}
    for row in per_question:
        cat = row.get("category")
        if cat:
            category_scores.setdefault(cat, []).append(row)

    by_category: dict[str, dict[str, float | None]] = {}
    if category_scores:
        for cat, rows in category_scores.items():
            by_category[cat] = {}
            for name in metric_names:
                available = [row[name] for row in rows if row[name] is not None]
                by_category[cat][name] = (
                    sum(available) / len(available) if available else None
                )

    rng = random.Random(BOOTSTRAP_SEED)

    def confidence_intervals_for(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
        return {
            name: _bootstrap_mean_confidence_interval(
                [row[name] for row in rows], rng
            )
            for name in metric_names
        }

    confidence_intervals = {
        "method": "percentile_bootstrap",
        "confidence_level": BOOTSTRAP_CONFIDENCE_LEVEL,
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "average": confidence_intervals_for(per_question),
        "by_category": {
            cat: confidence_intervals_for(rows)
            for cat, rows in category_scores.items()
        },
    }

    parent_scored_by_k = {
        str(k): sum(row[f"parent_match_recall@{k}"] is not None for row in per_question)
        for k in ks
    }
    parent_metadata_missing_by_k = {
        str(k): sum(row[f"parent_match_metadata_missing@{k}"] for row in per_question)
        for k in ks
    }
    max_k = max(ks)

    report = {
        "num_questions": len(per_question),
        "num_scored_questions": len(per_question),
        "num_skipped": len(skipped),
        "skipped": skipped,
        "num_parent_scored_questions": parent_scored_by_k[str(max_k)],
        "num_parent_metadata_missing_questions": parent_metadata_missing_by_k[str(max_k)],
        "num_parent_scored_questions_by_k": parent_scored_by_k,
        "num_parent_metadata_missing_questions_by_k": parent_metadata_missing_by_k,
        "average": average,
        "confidence_intervals": confidence_intervals,
        "per_question": per_question,
    }
    if report_metadata is not None:
        report.update(report_metadata)
    if by_category:
        report["by_category"] = by_category

    print(f"Scored {len(per_question)} questions (skipped {len(skipped)} without gold)")
    for name, value in average.items():
        formatted = f"{value:.4f}" if value is not None else "N/A"
        print(f"  {name}: {formatted}")

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Saved metrics report: {output.resolve()}")

    return report