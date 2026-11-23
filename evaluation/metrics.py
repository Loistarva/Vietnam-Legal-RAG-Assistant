"""Shared retrieval metrics: chunk/parent Recall, MRR, and NDCG."""
from __future__ import annotations

import json
import math
import random
import re
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


# ----------------------------------------------------------------------
# Answer/run metrics. These are additive and do not alter retrieval metrics above.
# ----------------------------------------------------------------------
def citation_match_scores(
    parsed_citations: Any, ground_truth_item: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Score generated citations against reviewed gold clauses.

    Precision is the fraction of citation mentions matching a gold clause.
    Recall is the fraction of gold clauses cited exactly or by an article-level
    citation to the same canonical document and article. No legal inference is
    made; records without reviewed ``gold_clause_ids`` are unscored.
    """
    import re

    if not isinstance(parsed_citations, list):
        return None
    clause_pattern = re.compile(
        r"^(?P<document>.+?)_art_(?P<article>\d+[a-z]?)_clause_(?P<clause>\d+[a-z]?)$"
    )
    gold_targets: dict[str, tuple[str, str]] = {}
    gold_ids = ground_truth_item.get("gold_clause_ids") or []
    if isinstance(gold_ids, list):
        for clause_id in gold_ids:
            if isinstance(clause_id, str):
                match = clause_pattern.fullmatch(clause_id)
                if match:
                    gold_targets[clause_id] = (
                        match.group("document"), match.group("article")
                    )
    if not gold_targets:
        return None

    generated = [citation for citation in parsed_citations if isinstance(citation, dict)]
    matched_gold: set[str] = set()
    correct_count = 0
    for citation in generated:
        clause_id = citation.get("clause_id")
        document_id = citation.get("document_id")
        article = citation.get("article_number")
        hits: set[str] = set()
        if isinstance(clause_id, str) and clause_id in gold_targets:
            hits.add(clause_id)
        elif (
            isinstance(document_id, str)
            and isinstance(article, (str, int))
            and citation.get("clause_number") is None
        ):
            article_key = (document_id, str(article))
            hits.update(
                gold_id for gold_id, target in gold_targets.items()
                if target == article_key
            )
        # Run B already supplies canonical clause IDs, while parsers may also
        # provide only an article ID. Resolve the latter from its canonical ID.
        if not hits and isinstance(citation.get("article_id"), str):
            article_match = re.fullmatch(
                r"(?P<document>.+?)_art_(?P<article>\d+[a-z]?)",
                citation["article_id"],
            )
            if article_match and citation.get("clause_number") is None:
                article_key = (article_match.group("document"), article_match.group("article"))
                hits.update(
                    gold_id for gold_id, target in gold_targets.items()
                    if target == article_key
                )
        if hits:
            correct_count += 1
            matched_gold.update(hits)

    return {
        "citation_precision": correct_count / len(generated) if generated else 0.0,
        "citation_recall": len(matched_gold) / len(gold_targets),
        "generated_citations": len(generated),
        "correct_citations": correct_count,
        "gold_clauses_cited": len(matched_gold),
        "gold_clauses": len(gold_targets),
        "matched_gold_clause_ids": sorted(matched_gold),
    }


def summarize_citation_scores(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Macro-average available per-question citation scores and sum counts."""
    subset = [row for row in rows if row.get("citation_precision") is not None]
    if not subset:
        return {}
    return {
        "citation_precision": round(sum(float(row["citation_precision"]) for row in subset) / len(subset), 4),
        "citation_recall": round(sum(float(row["citation_recall"]) for row in subset) / len(subset), 4),
        "citation_scored_questions": len(subset),
        "generated_citations": sum(int(row["generated_citations"]) for row in subset),
        "correct_citations": sum(int(row["correct_citations"]) for row in subset),
        "gold_clauses_cited": sum(int(row.get("gold_clauses_cited", 0)) for row in subset),
        "gold_clauses": sum(int(row.get("gold_clauses", 0)) for row in subset),
    }


def _percentile_value(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return _percentile(ordered, probability)


def evaluate_answer_run(
    records: Sequence[Mapping[str, Any]],
    ground_truth: Sequence[Mapping[str, Any]],
    *,
    run: str,
) -> dict[str, Any]:
    """Calculate code-based answer/run metrics for a normalized A or B result set.

    Supports Run A records and Run B envelopes shaped as ``{status, query_id,
    result: {...}}``. Human rubric metrics are intentionally excluded.
    """
    run_label = run.strip().upper()
    if run_label not in {"A", "B"}:
        raise ValueError("run must be 'A' or 'B'")

    truth_by_id = {
        str(item.get("id")): item for item in ground_truth
        if isinstance(item.get("id"), str)
    }
    flattened: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, envelope in enumerate(records):
        if not isinstance(envelope, Mapping):
            raise ValueError(f"record at index {index} must be an object")
        result = envelope.get("result")
        row = dict(result) if isinstance(result, Mapping) else dict(envelope)
        query_id = row.get("query_id") or envelope.get("query_id") or row.get("id")
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"record at index {index} is missing query_id")
        if query_id not in truth_by_id:
            raise ValueError(f"query_id {query_id!r} is absent from ground truth")
        if query_id in seen_ids:
            raise ValueError(f"duplicate query_id: {query_id}")
        seen_ids.add(query_id)
        row["query_id"] = query_id
        flattened.append(row)

    answerable_ids = {
        query_id for query_id, item in truth_by_id.items()
        if isinstance(item.get("gold_clause_ids"), list) and item["gold_clause_ids"]
    }
    citation_rows: list[dict[str, Any]] = []
    per_question: list[dict[str, Any]] = []
    abstentions = clarifications = false_abstentions = 0
    cjk_rows = 0
    called_rows = 0
    latencies: list[float] = []
    steady_latencies: list[float] = []
    warmup_rows: list[dict[str, Any]] = []
    llm_latencies: list[float] = []
    input_tokens: list[float] = []
    output_tokens: list[float] = []
    total_cost = 0.0
    cost_seen = False
    validity_attempts = validity_passes = 0

    def citations_for_record(row: Mapping[str, Any]) -> list[dict[str, Any]]:
        citations = row.get("citations")
        if isinstance(citations, list) and citations:
            return [item for item in citations if isinstance(item, dict)]
        if run_label != "B":
            return citations if isinstance(citations, list) else []
        # For a Gate-rejected B answer, the public citation list is empty. Recover
        # attempted references from evidence indices + selected context so Citation
        # Precision and Citation Validity remain separate measures.
        trace = row.get("retrieval_trace") or {}
        llm_trace = trace.get("llm") if isinstance(trace, Mapping) else {}
        attempts = row.get("evidence_indices")
        if not isinstance(attempts, list) and isinstance(llm_trace, Mapping):
            attempts = llm_trace.get("evidence_indices", [])
        context_trace = trace.get("context") if isinstance(trace, Mapping) else {}
        evidence_rows = context_trace.get("evidence", []) if isinstance(context_trace, Mapping) else []
        by_index = {
            evidence.get("evidence_index"): evidence
            for evidence in evidence_rows
            if isinstance(evidence, Mapping)
        }
        recovered: list[dict[str, Any]] = []
        for evidence_index in attempts if isinstance(attempts, list) else []:
            evidence = by_index.get(evidence_index)
            if not isinstance(evidence, Mapping):
                recovered.append({"evidence_index": evidence_index})
                continue
            chunk_id = evidence.get("chunk_id")
            if not isinstance(chunk_id, str):
                continue
            clause_id = re.sub(r"_chunk_\d+$", "", chunk_id)
            article_match = re.match(r"^(.+_art_\d+[a-z]?)", clause_id)
            recovered.append({
                "evidence_index": evidence_index,
                "chunk_id": chunk_id,
                "document_id": clause_id.split("_art_", 1)[0] if "_art_" in clause_id else None,
                "article_id": article_match.group(1) if article_match else None,
                "clause_id": clause_id if "_clause_" in clause_id else None,
                "article_number": article_match.group(1).rsplit("_art_", 1)[-1] if article_match else None,
                "clause_number": clause_id.rsplit("_clause_", 1)[-1] if "_clause_" in clause_id else None,
            })
        rejected = llm_trace.get("rejected_evidence_values", []) if isinstance(llm_trace, Mapping) else []
        if isinstance(rejected, list):
            recovered.extend({"rejected_evidence_value": value} for value in rejected)
        return recovered

    for row in flattened:
        query_id = row["query_id"]
        truth = truth_by_id[query_id]
        citation_result = citation_match_scores(citations_for_record(row), truth)
        if citation_result is not None:
            citation_rows.append(citation_result)
        question_metrics: dict[str, Any] = {"query_id": query_id}
        if citation_result is not None:
            question_metrics.update(citation_result)

        calls = row.get("llm_calls", 1 if run_label == "A" else 0)
        calls = calls if isinstance(calls, int) and not isinstance(calls, bool) else 0
        called = calls > 0
        if called:
            called_rows += 1
            cjk = row.get("cjk_chars")
            if cjk is None:
                trace = row.get("retrieval_trace") or {}
                llm_trace = trace.get("llm") if isinstance(trace, Mapping) else {}
                cjk = llm_trace.get("cjk_chars_before_gate", 0) if isinstance(llm_trace, Mapping) else 0
            if isinstance(cjk, (int, float)) and cjk > 0:
                cjk_rows += 1
            question_metrics["cjk_chars"] = cjk

        latency = row.get("latency_ms")
        if called and isinstance(latency, (int, float)) and not isinstance(latency, bool):
            latencies.append(float(latency))
            question_metrics["latency_ms"] = float(latency)
            breakdown = row.get("latency_breakdown") or {}
            load_ms = breakdown.get("load_ms") if isinstance(breakdown, Mapping) else None
            if isinstance(load_ms, (int, float)) and load_ms > 1000:
                warmup_rows.append({"query_id": query_id, "load_ms": load_ms})
            else:
                steady_latencies.append(float(latency))
        if called:
            breakdown = row.get("latency_breakdown") or {}
            llm_ms = breakdown.get("llm_total_ms") if isinstance(breakdown, Mapping) else None
            if isinstance(llm_ms, (int, float)):
                llm_latencies.append(float(llm_ms))
            usage = row.get("token_usage") or {}
            if isinstance(usage, Mapping):
                if isinstance(usage.get("input"), (int, float)):
                    input_tokens.append(float(usage["input"]))
                if isinstance(usage.get("output"), (int, float)):
                    output_tokens.append(float(usage["output"]))
        if isinstance(row.get("cost_usd"), (int, float)):
            total_cost += float(row["cost_usd"])
            cost_seen = True

        if run_label == "B":
            abstained = row.get("abstained") is True
            clarification = row.get("needs_clarification") is True
            abstentions += int(abstained)
            clarifications += int(clarification)
            if query_id in answerable_ids and (abstained or clarification):
                false_abstentions += 1
            question_metrics.update({
                "abstained": abstained,
                "needs_clarification": clarification,
                "false_abstention": query_id in answerable_ids and (abstained or clarification),
            })
            trace = row.get("retrieval_trace") or {}
            llm_trace = trace.get("llm") if isinstance(trace, Mapping) else {}
            attempts = row.get("evidence_indices")
            if not isinstance(attempts, list) and isinstance(llm_trace, Mapping):
                attempts = llm_trace.get("evidence_indices", [])
            context_trace = trace.get("context") if isinstance(trace, Mapping) else {}
            evidence_rows = context_trace.get("evidence", []) if isinstance(context_trace, Mapping) else []
            allowed = {
                item.get("evidence_index") for item in evidence_rows
                if isinstance(item, Mapping) and isinstance(item.get("evidence_index"), int)
            }
            invalid = set()
            gate = trace.get("gate") if isinstance(trace, Mapping) else {}
            if isinstance(gate, Mapping) and isinstance(gate.get("invalid_indices"), list):
                invalid = set(gate["invalid_indices"])
            if isinstance(attempts, list):
                for evidence_index in attempts:
                    if isinstance(evidence_index, int) and not isinstance(evidence_index, bool):
                        validity_attempts += 1
                        validity_passes += int(evidence_index in allowed and evidence_index not in invalid)
            rejected = llm_trace.get("rejected_evidence_values", []) if isinstance(llm_trace, Mapping) else []
            if isinstance(rejected, list):
                validity_attempts += len(rejected)
        per_question.append(question_metrics)

    citation_summary: dict[str, Any] = {}
    if citation_rows:
        citation_summary = {
            "citation_precision": round(sum(row["citation_precision"] for row in citation_rows) / len(citation_rows), 4),
            "citation_recall": round(sum(row["citation_recall"] for row in citation_rows) / len(citation_rows), 4),
            "citation_scored_questions": len(citation_rows),
            "generated_citations": sum(row["generated_citations"] for row in citation_rows),
            "correct_citations": sum(row["correct_citations"] for row in citation_rows),
        }

    report: dict[str, Any] = {
        "run": run_label,
        "num_questions": len(flattened),
        "llm_called_questions": called_rows,
        "non_vietnamese_answer_rate": cjk_rows / called_rows if called_rows else None,
        "non_vietnamese_answer_questions": cjk_rows,
        "latency_ms": {
            "p50": _percentile_value(latencies, 0.50),
            "p95": _percentile_value(latencies, 0.95),
            "steady_p50": _percentile_value(steady_latencies, 0.50),
            "steady_p95": _percentile_value(steady_latencies, 0.95),
            "n_llm_called": len(latencies),
            "n_excluded_warmup": len(warmup_rows),
            "warmup_questions": warmup_rows,
        },
        "llm_total_latency_ms": {
            "mean": sum(llm_latencies) / len(llm_latencies) if llm_latencies else None,
            "n": len(llm_latencies),
        },
        "token_usage": {
            "input_mean": sum(input_tokens) / len(input_tokens) if input_tokens else None,
            "output_mean": sum(output_tokens) / len(output_tokens) if output_tokens else None,
            "input_total": sum(input_tokens) if input_tokens else 0,
            "output_total": sum(output_tokens) if output_tokens else 0,
        },
        "per_question": per_question,
        **citation_summary,
    }
    if run_label == "B":
        answerable_count = sum(query_id in answerable_ids for query_id in (row["query_id"] for row in flattened))
        report["abstention_rate"] = abstentions / len(flattened) if flattened else None
        report["abstained_questions"] = abstentions
        report["clarification_rate"] = clarifications / len(flattened) if flattened else None
        report["clarification_questions"] = clarifications
        report["false_abstention_rate"] = false_abstentions / answerable_count if answerable_count else None
        report["false_abstentions"] = false_abstentions
        report["answerable_questions"] = answerable_count
        report["citation_validity_rate"] = validity_passes / validity_attempts if validity_attempts else None
        report["valid_evidence_indices"] = validity_passes
        report["attempted_evidence_indices"] = validity_attempts
    if cost_seen:
        report["cost_usd"] = total_cost
    else:
        model_names = {
            str(row.get("model", "")).casefold()
            for row in flattened
            if isinstance(row.get("model"), str) and row.get("model")
        }
        if model_names and all("qwen2.5:7b" in name for name in model_names):
            report["cost_usd"] = 0.0
            report["cost_basis"] = "local Ollama inference; no API charge"
    return report
