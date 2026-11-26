"""Evaluate Top-5 vs Top-10 cutoffs on the same verified Dev reranking output.

This performs no retrieval, reranking, or LLM inference. It verifies the saved
G3 artifact and evaluates only source-checked Dev Gold queries outside the
official 30-ID A/B set. The only experimental variable is the output cutoff.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding.vector_store import chunk_file_sha256
from evaluation.metrics import evaluate
from scripts.precompute_dev30_retrieval import normalized_file_sha256

SOURCE_RESULTS = ROOT / "retrieval" / "results" / "dev_hybrid_reranker.json"
PRECOMPUTE_MANIFEST = ROOT / "reports" / "retrieval" / "precompute_manifest.json"
QUERIES_PATH = ROOT / "data" / "benchmark" / "queries_dev.json"
GROUND_TRUTH_PATH = ROOT / "data" / "benchmark" / "ground_truth.json"
OFFICIAL_IDS_PATH = ROOT / "evaluation" / "rubrics" / "dev_gold_30_ids_v1.txt"
CORPUS_PATH = ROOT / "data" / "chunking_output" / "chunks.jsonl"
METRICS_PATH = ROOT / "evaluation" / "results" / "dev" / "topk_cutoff_20261116_metrics.json"
MANIFEST_PATH = ROOT / "reports" / "week10" / "topk_experiment_20261116_manifest.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired_cutoff_deltas(per_question: list[dict[str, Any]]) -> dict[str, Any]:
    """Bootstrap paired Top-10 minus Top-5 deltas across the same questions."""
    metric_pairs = {
        "strict_match_recall": ("strict_match_recall@5", "strict_match_recall@10"),
        "mrr": ("mrr@5", "mrr@10"),
        "ndcg": ("ndcg@5", "ndcg@10"),
        "precision": ("precision@5", "precision@10"),
        "parent_match_recall": ("parent_match_recall@5", "parent_match_recall@10"),
    }
    rng = random.Random(42)
    output: dict[str, Any] = {}
    for metric, (top5_key, top10_key) in metric_pairs.items():
        deltas = [
            float(row[top10_key]) - float(row[top5_key])
            for row in per_question
            if row.get(top5_key) is not None and row.get(top10_key) is not None
        ]
        if not deltas:
            output[metric] = {"mean_delta_top10_minus_top5": None, "ci95": None, "n": 0}
            continue
        samples = sorted(sum(rng.choices(deltas, k=len(deltas))) / len(deltas) for _ in range(10_000))
        output[metric] = {
            "mean_delta_top10_minus_top5": sum(deltas) / len(deltas),
            "ci95": {"lower": samples[249], "upper": samples[9749]},
            "n": len(deltas),
        }
    return output


def main() -> None:
    source_rows = read_json(SOURCE_RESULTS)
    precompute = read_json(PRECOMPUTE_MANIFEST)
    queries = read_json(QUERIES_PATH)
    gold_rows = read_json(GROUND_TRUTH_PATH)
    official_ids = {
        line.strip() for line in OFFICIAL_IDS_PATH.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    }

    current_corpus_sha = chunk_file_sha256(CORPUS_PATH)
    source_sha = sha256_file(SOURCE_RESULTS)
    expected_source_sha = precompute["source_artifact"]["source_artifact_sha256"]
    if source_sha != expected_source_sha:
        raise SystemExit(f"Artifact SHA không khớp precompute manifest: {source_sha} != {expected_source_sha}")
    if current_corpus_sha != precompute["corpus_sha256"]:
        raise SystemExit("Corpus SHA hiện tại không khớp precompute manifest.")
    if normalized_file_sha256(ROOT / "retrieval" / "config.yaml") != precompute["retrieval_config"]["sha256"]:
        raise SystemExit("Retrieval config hiện tại không khớp precompute manifest.")
    if normalized_file_sha256(ROOT / "reranking" / "config.yaml") != precompute["rerank_config"]["sha256"]:
        raise SystemExit("Rerank config hiện tại không khớp precompute manifest.")

    retrieval_config = yaml.safe_load((ROOT / "retrieval" / "config.yaml").read_text(encoding="utf-8"))
    rerank_config = yaml.safe_load((ROOT / "reranking" / "config.yaml").read_text(encoding="utf-8"))
    retrieval_top_k = retrieval_config["retrieval"]["retrieval_top_k"]
    result_top_k_configured = retrieval_config["retrieval"]["result_top_k"]
    rerank_top_k_configured = rerank_config["reranker"]["rerank_top_k"]

    query_by_id = {row["id"]: row for row in queries if isinstance(row, dict) and isinstance(row.get("id"), str)}
    gold_by_id = {row["id"]: row for row in gold_rows if isinstance(row, dict) and isinstance(row.get("id"), str)}
    source_by_id = {row["query_id"]: row for row in source_rows if isinstance(row, dict)}
    if len(source_by_id) != len(source_rows):
        raise SystemExit("Artifact có query_id thiếu hoặc trùng.")

    selected_ids = sorted(
        query_id for query_id, query in query_by_id.items()
        if query.get("split") == "dev"
        and query_id not in official_ids
        and gold_by_id.get(query_id, {}).get("review_status") == "source_checked"
        and gold_by_id.get(query_id, {}).get("gold_context_ids_confirmed") is True
        and gold_by_id.get(query_id, {}).get("gold_context_ids")
    )
    if not selected_ids:
        raise SystemExit("Không có câu Dev source_checked phù hợp sau khi loại official IDs.")

    selected_queries: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    parent_by_chunk: dict[str, str] = {}
    rank_checks: dict[str, Any] = {}
    raw_candidate_pool_available: set[bool] = set()
    for query_id in selected_ids:
        query = query_by_id[query_id]
        row = source_by_id.get(query_id)
        if row is None:
            raise SystemExit(f"Thiếu query {query_id} trong artifact reranker.")
        results = row.get("results")
        stats = row.get("stats") or {}
        config = row.get("config") or {}
        retriever_config = config.get("retriever") or {}
        reranker_config = config.get("reranker") or {}
        if not isinstance(results, list) or len(results) != 10 or row.get("top_k") != 10:
            raise SystemExit(f"{query_id}: artifact không có đúng Top-10 đã lưu.")
        if (stats.get("retrieved_candidates") != 50 or stats.get("scored_candidates") != 50
                or stats.get("output_candidates") != 10):
            raise SystemExit(f"{query_id}: không xác minh được 50 candidate đã chấm và 10 kết quả đầu ra.")
        if retriever_config.get("retrieval_top_k") != 50 or reranker_config.get("backend") != "cross_encoder":
            raise SystemExit(f"{query_id}: cấu hình truy xuất/reranker không khớp thí nghiệm.")
        if reranker_config.get("model") != "BAAI/bge-reranker-v2-m3":
            raise SystemExit(f"{query_id}: model reranker không khớp baseline đã pin.")
        if (retriever_config.get("rrf_k") != 60 or retriever_config.get("dense_model") != "BAAI/bge-m3"
                or retriever_config.get("collection") != "vietnam_legal_chunks"):
            raise SystemExit(f"{query_id}: cấu hình Hybrid/RRF/Dense không khớp baseline đã pin.")
        if retriever_config.get("corpus_sha256") != current_corpus_sha:
            raise SystemExit(f"{query_id}: corpus SHA trong record không khớp corpus hiện tại.")
        if row.get("query") != query.get("question") or config.get("as_of_date") != query.get("as_of_date"):
            raise SystemExit(f"{query_id}: query hoặc as_of_date trong artifact không khớp benchmark.")
        if reranker_config.get("candidate_text") != precompute.get("candidate_text"):
            raise SystemExit(f"{query_id}: candidate_text không khớp precompute manifest.")
        candidate_pool_path = retriever_config.get("candidates")
        raw_candidate_pool_available.add(
            bool(candidate_pool_path and Path(candidate_pool_path).is_file())
        )

        ids = [candidate.get("chunk_id") for candidate in results]
        scores = [candidate.get("reranker_score") for candidate in results]
        ranks = [candidate.get("rank") for candidate in results]
        if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != 10:
            raise SystemExit(f"{query_id}: chunk_id thiếu hoặc trùng trong Top-10.")
        if ranks != list(range(1, 11)):
            raise SystemExit(f"{query_id}: rank không liên tục từ 1 đến 10.")
        if any(not isinstance(score, (int, float)) for score in scores):
            raise SystemExit(f"{query_id}: thiếu reranker_score.")
        if any(scores[index] < scores[index + 1] for index in range(9)):
            raise SystemExit(f"{query_id}: thứ tự điểm reranker không giảm dần.")

        selected_queries.append(query)
        metric_rows.append({
            "query_id": query_id,
            "retriever": "hybrid_reranker",
            "retrieved_chunk_ids": ids,
            "retrieved_parent_clause_ids": [candidate.get("parent_clause_id") for candidate in results],
        })
        for candidate in results:
            parent_id = candidate.get("parent_clause_id")
            chunk_id = candidate.get("chunk_id")
            if isinstance(parent_id, str) and parent_id and isinstance(chunk_id, str):
                parent_by_chunk[chunk_id] = parent_id
        rank_checks[query_id] = {
            "candidate_pool_scored_reported": 50,
            "raw_candidate_pool_available": bool(candidate_pool_path and Path(candidate_pool_path).is_file()),
            "saved_output_count": 10,
        }

    metadata = {
        "experiment_id": "d4_5_topk_output_cutoff_20261116",
        "experiment_scope": "reranked_output_cutoff_only",
        "selected_query_count": len(selected_ids),
        "selected_query_ids": selected_ids,
        "excluded_official_id_count": len(official_ids),
        "selection_rule": "split=dev; review_status=source_checked; gold_context_ids_confirmed=true; non-empty gold_context_ids; exclude dev_gold_30_ids_v1.txt",
        "source_artifact_path": SOURCE_RESULTS.relative_to(ROOT).as_posix(),
        "source_artifact_sha256": source_sha,
        "precompute_manifest_path": PRECOMPUTE_MANIFEST.relative_to(ROOT).as_posix(),
        "precompute_manifest_sha256": sha256_file(PRECOMPUTE_MANIFEST),
        "corpus_sha256_normalized": current_corpus_sha,
        "retrieval_config_sha256_normalized": precompute["retrieval_config"]["sha256"],
        "rerank_config_sha256_normalized": precompute["rerank_config"]["sha256"],
        "retriever": "Hybrid BM25 + Dense BGE-M3 + RRF (rrf_k=60)",
        "retrieval_top_k": retrieval_top_k,
        "result_top_k": result_top_k_configured,
        "rerank_top_k": rerank_top_k_configured,
        "observed_result_top_k": 10,
        "result_top_k_configured": result_top_k_configured,
        "rerank_top_k_configured": rerank_top_k_configured,
        "baseline_effective_output_top_k": 5,
        "experiment_effective_output_top_k": 10,
        "top_k_interpretation": {
            "retrieval_top_k": "50 raw Hybrid candidates fetched before reranking",
            "rerank_top_k_configured": "5 default output cutoff configured in reranking/config.yaml",
            "result_top_k_configured": "10 output cutoff configured in retrieval/config.yaml; CLI/pipeline may override the reranker default",
            "experiment_effective_output_top_k": "10 observed in each saved artifact row and in its 10 saved ranked results",
        },
        "candidate_pool_50_provenance": {
            "reported_scored_candidates": 50,
            "raw_candidate_artifact_available_for_all_selected_queries": (
                raw_candidate_pool_available == {True}
            ),
            "verification_status": (
                "AVAILABLE" if raw_candidate_pool_available == {True}
                else "NOT_INDEPENDENTLY_VERIFIABLE"
            ),
            "note": "The saved artifact retains only 10 ranked outputs per query; candidate-pool count 50 is recorded in stats, while the configured source path is unavailable in this workspace.",
        },
        "reranker": "BAAI/bge-reranker-v2-m3",
        "candidate_text": precompute["candidate_text"],
        "cutoffs_compared": [5, 10],
        "controlled_variable": "post-reranking output cutoff only; Top-5 is a prefix of the same saved Top-10 ranking and scores",
        "unchanged_variables": ["query set", "corpus", "saved Top-10 ranking and scores", "retriever metadata", "reranker model metadata", "temporal date", "gold labels"],
        "no_llm_inference": True,
        "no_retrieval_or_reranking_rerun": True,
        "per_query_validation": rank_checks,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    with tempfile.TemporaryDirectory(prefix="topk-cutoff-eval-") as temp_dir:
        temp = Path(temp_dir)
        selected_queries_path = temp / "queries_dev_selected.json"
        selected_results_path = temp / "results_top10.json"
        selected_queries_path.write_text(json.dumps(selected_queries, ensure_ascii=False), encoding="utf-8")
        selected_results_path.write_text(json.dumps(metric_rows, ensure_ascii=False), encoding="utf-8")
        report = evaluate(
            selected_results_path,
            GROUND_TRUTH_PATH,
            output_path=METRICS_PATH,
            ks=(5, 10),
            queries_paths=(selected_queries_path,),
            parent_by_chunk=parent_by_chunk,
            verified_only=True,
            report_metadata=metadata,
        )

    manifest = {
        **metadata,
        "metrics_path": METRICS_PATH.relative_to(ROOT).as_posix(),
        "metrics_sha256": sha256_file(METRICS_PATH),
        "metrics_average": report["average"],
        "paired_bootstrap_delta_top10_minus_top5": paired_cutoff_deltas(report["per_question"]),
        "interpretation": "Chỉ đo thay đổi của cutoff Top-5 so với Top-10 trên cùng ranking đã lưu. Không đánh giá chất lượng câu trả lời, độ trễ end-to-end hoặc hiệu quả của lần chạy retrieval mới.",
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Top-k cutoff analysis complete: {len(selected_ids)} verified Dev queries")
    print(f"Metrics: {METRICS_PATH.relative_to(ROOT)}")
    print(f"Manifest: {MANIFEST_PATH.relative_to(ROOT)}")
    for name, value in report["average"].items():
        print(f"{name}: {value}")


if __name__ == "__main__":
    main()
