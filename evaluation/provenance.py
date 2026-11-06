"""Input and run provenance for saved retrieval evaluation reports."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from evaluation.metrics import DEFAULT_KS
from evaluation.run_evaluation import read_json_array
from evaluation.test_run_freeze import _file_sha256


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric_cutoffs(top_k: int) -> tuple[int, ...]:
    if top_k < 1:
        raise ValueError("top_k phải lớn hơn 0")
    return tuple(k for k in DEFAULT_KS if k < top_k) + (top_k,)


def build_report_metadata(
    results_path: Path,
    queries_path: Path,
    ground_truth_path: Path,
    chunks_path: Path,
    queries: list[dict[str, Any]],
    method: str,
    split: str,
    top_k: int,
) -> dict[str, Any]:
    """Validate saved retrieval provenance and describe the exact inputs scored."""
    corpus_sha256 = sha256_file(chunks_path)
    queries_by_id = {query.get("id"): query for query in queries}
    envelopes = read_json_array(results_path)
    common_config: dict[str, Any] | None = None
    as_of_date_by_query: dict[str, Any] = {}
    seen_query_ids: set[str] = set()

    for envelope in envelopes:
        query_id = envelope.get("query_id")
        if not isinstance(query_id, str) or query_id not in queries_by_id:
            raise ValueError(
                f"{results_path} chứa query_id không thuộc query set: {query_id!r}"
            )
        if query_id in seen_query_ids:
            raise ValueError(f"{results_path} có query_id trùng: {query_id}")
        seen_query_ids.add(query_id)

        query = queries_by_id[query_id]
        query_text = query.get("question") or query.get("query")
        if not isinstance(query_text, str) or envelope.get("query") != query_text:
            raise ValueError(
                f"{results_path}: query text không khớp queries cho query_id={query_id}"
            )
        if envelope.get("retriever") != method:
            raise ValueError(
                f"{results_path}: query {query_id} khai báo retriever "
                f"{envelope.get('retriever')!r}, mong đợi {method!r}."
            )

        config = envelope.get("config")
        if not isinstance(config, dict):
            raise ValueError(f"{results_path}: query {query_id} thiếu config.")
        retriever_config = config.get("retriever")
        recorded_corpus_sha256 = config.get("corpus_sha256")
        if isinstance(retriever_config, dict):
            recorded_corpus_sha256 = retriever_config.get("corpus_sha256")
        if recorded_corpus_sha256 != corpus_sha256:
            raise ValueError(
                f"{results_path}: corpus_sha256 không khớp với corpus hiện tại "
                f"(query_id={query_id})."
            )
        if envelope.get("top_k") != top_k:
            raise ValueError(
                f"{results_path}: top_k kết quả ({envelope.get('top_k')!r}) "
                f"không khớp top_k đánh giá ({top_k})."
            )
        if config.get("top_k") != envelope.get("top_k"):
            raise ValueError(
                f"{results_path}: config.top_k không khớp top_k "
                f"(query_id={query_id})."
            )
        if "as_of_date" in query and config.get("as_of_date") != query["as_of_date"]:
            raise ValueError(
                f"{results_path}: as_of_date không khớp queries cho query_id={query_id}"
            )

        comparable_config = {
            key: value for key, value in config.items() if key != "as_of_date"
        }
        if common_config is None:
            common_config = comparable_config
        elif comparable_config != common_config:
            raise ValueError(
                f"{results_path}: config không nhất quán giữa các query."
            )
        as_of_date_by_query[query_id] = config.get("as_of_date")

    missing_query_ids = set(queries_by_id) - seen_query_ids
    if missing_query_ids:
        raise ValueError(
            f"{results_path} thiếu query: {', '.join(sorted(missing_query_ids))}"
        )
    if common_config is None:
        raise ValueError(f"{results_path} không có kết quả retrieval.")

    return {
        "label_source": "ground_truth.gold_context_ids",
        "input_sha256": {
            "corpus": corpus_sha256,
            "queries": _file_sha256(queries_path),
            "ground_truth": _file_sha256(ground_truth_path),
            "retrieval_results": _file_sha256(results_path),
        },
        "run_config": {
            **common_config,
            "as_of_date_by_query": as_of_date_by_query,
        },
        "evaluation_config": {
            "method": method,
            "split": split,
            "top_k": top_k,
            "ks": list(metric_cutoffs(top_k)),
        },
    }
