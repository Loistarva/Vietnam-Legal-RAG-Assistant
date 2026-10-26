"""Evaluate the configured real Cross-Encoder on the frozen Dev split only."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reranking.reranker import build_reranker, load_reranker_config  # noqa: E402
from retrieval.rrf import reciprocal_rank_fusion  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def percentile(values: list[float], p: float) -> float | None:
    return values[max(0, math.ceil(p * len(values)) - 1)] if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("A", "B", "C", "E"), default="E")
    parser.add_argument("--labels-map", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants/label_mapping.json")
    parser.add_argument("--queries", type=Path, default=ROOT / "data/benchmark/queries_dev.json")
    parser.add_argument("--config", type=Path, default=ROOT / "reranking/config.yaml")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants/E/dev_cross_encoder.json")
    parser.add_argument("--bm25-weight", type=float, default=0.35)
    parser.add_argument("--dense-weight", type=float, default=0.65)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn query để chạy thử; mặc định chạy toàn bộ Dev có nhãn.")
    parser.add_argument("--progress-file", type=Path, default=None)
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit phải lớn hơn 0")
    if args.rrf_k < 0 or args.candidate_k < 1 or args.top_k < 1:
        parser.error("rrf-k phải không âm; candidate-k và top-k phải lớn hơn 0")

    try:
        if "test" in args.queries.stem.casefold():
            raise ValueError("Từ chối dùng file Test; Cross-Encoder evaluator này chỉ chạy Dev")
        mapping = read_json(args.labels_map)
        labels_info = mapping["configs"][args.variant]
        labels = {qid: set(ids) for qid, ids in labels_info["query_labels"].items()}
        query_rows = read_json(args.queries)
        queries = {
            str(row.get("query_id") or row.get("id")): row.get("question") or row.get("query")
            for row in query_rows if isinstance(row, dict)
        }
        if not labels:
            raise ValueError(f"Không có nhãn chunk cho variant {args.variant}")
        missing_queries = sorted(set(labels) - set(queries))
        if missing_queries:
            raise ValueError(f"Dev query thiếu trong input: {missing_queries[:5]}")
        scored_ids = sorted(labels)
        if args.limit:
            scored_ids = scored_ids[:args.limit]

        variant_dir = ROOT / "retrieval/results/dev_tuning/chunking_variants" / args.variant
        sparse_rows = {row["query_id"]: row for row in read_json(variant_dir / "results/dev_bm25.json")}
        dense_rows = {row["query_id"]: row for row in read_json(variant_dir / "results/dev_dense.json")}
        for qid in scored_ids:
            if qid not in sparse_rows or qid not in dense_rows:
                raise ValueError(f"Thiếu Top-50 BM25/Dense cho {qid}")

        config = load_reranker_config(args.config, backend="cross_encoder", rerank_top_k=max(args.top_k, 1))
        if config.max_candidates < args.candidate_k:
            raise ValueError(f"reranker.max_candidates={config.max_candidates} nhỏ hơn candidate_k={args.candidate_k}")
        reranker = build_reranker(config)
        if reranker is None or reranker.backend != "cross_encoder":
            raise ValueError("Không tạo được Cross-Encoder thật")

        per_query = []
        rrf_latencies: list[float] = []
        rerank_latencies: list[float] = []
        model_load_ms = 0.0
        progress = {"split": "dev", "variant": args.variant, "completed": 0, "total": len(scored_ids)}
        for index, qid in enumerate(scored_ids, 1):
            query = queries[qid]
            if not isinstance(query, str) or not query.strip():
                raise ValueError(f"Query rỗng: {qid}")
            rrf_started = time.perf_counter()
            candidates = reciprocal_rank_fusion(
                [sparse_rows[qid]["results"], dense_rows[qid]["results"]],
                top_k=args.candidate_k, rrf_k=args.rrf_k,
                weights=[args.bm25_weight, args.dense_weight],
            )
            rrf_ms = (time.perf_counter() - rrf_started) * 1000
            ranked = reranker.rerank(query, candidates, top_k=args.top_k)
            stats = dict(reranker.last_stats)
            rrf_latencies.append(rrf_ms)
            rerank_latencies.append(float(stats.get("rerank_latency_ms", 0.0)))
            model_load_ms += float(stats.get("model_load_ms", 0.0))
            retrieved_ids = [row["chunk_id"] for row in ranked]
            relevant = labels[qid]
            hits = list(dict.fromkeys(cid for cid in retrieved_ids if cid in relevant))
            first_rank = next((rank for rank, cid in enumerate(retrieved_ids, 1) if cid in relevant), None)
            per_query.append({
                "query_id": qid,
                "candidate_count": len(candidates),
                "retrieved_chunk_ids": retrieved_ids,
                "reranker_scores": [row["score"] for row in ranked],
                "hit_chunk_ids": hits,
                "relevant_chunk_count": len(relevant),
                "recall_at_5": len(hits) / len(relevant),
                "reciprocal_rank_at_5": 1 / first_rank if first_rank else 0.0,
                "rrf_latency_ms": round(rrf_ms, 3),
                "rerank_latency_ms": stats.get("rerank_latency_ms", 0.0),
                "scored_candidates": stats.get("scored_candidates", 0),
            })
            progress["completed"] = index
            if args.progress_file and (index % 5 == 0 or index == len(scored_ids)):
                args.progress_file.parent.mkdir(parents=True, exist_ok=True)
                args.progress_file.write_text(json.dumps(progress, ensure_ascii=False) + "\n", encoding="utf-8")
            if index % 10 == 0 or index == len(scored_ids):
                print(f"Dev Cross-Encoder: {index}/{len(scored_ids)}", flush=True)

        recalls = [row["recall_at_5"] for row in per_query]
        reciprocal_ranks = [row["reciprocal_rank_at_5"] for row in per_query]
        payload = {
            "run_date": date.today().isoformat(),
            "split": "dev",
            "labels_source": mapping["labels_source"],
            "variant": args.variant,
            "query_file": str(args.queries.relative_to(ROOT)) if args.queries.is_relative_to(ROOT) else str(args.queries),
            "queries_scored": len(per_query),
            "config": {
                "backend": config.backend,
                "model": config.model,
                "device": config.device or "auto",
                "batch_size": config.batch_size,
                "max_length": config.max_length,
                "candidate_text": config.candidate_text,
                "bm25_weight": args.bm25_weight,
                "dense_weight": args.dense_weight,
                "rrf_k": args.rrf_k,
                "candidate_k": args.candidate_k,
                "top_k": args.top_k,
            },
            "metrics": {
                "recall_at_5": statistics.fmean(recalls) if recalls else 0.0,
                "mrr_at_5": statistics.fmean(reciprocal_ranks) if reciprocal_ranks else 0.0,
            },
            "latency_ms": {
                "rrf_mean": statistics.fmean(rrf_latencies) if rrf_latencies else 0.0,
                "rerank_mean": statistics.fmean(rerank_latencies) if rerank_latencies else 0.0,
                "rerank_median": statistics.median(rerank_latencies) if rerank_latencies else 0.0,
                "rerank_p95": percentile(rerank_latencies, 0.95),
                "model_load_total": round(model_load_ms, 3),
            },
            "notes": [
                "Chỉ dùng queries_dev.json và proposal chunk labels đã ánh xạ; không đọc Test hoặc ground_truth.json.",
                "Cross-Encoder thật rerank cùng Top-50 RRF; metric tính trên Top-5 sau rerank.",
                "Nhãn proposal còn provisional; loại các query không có chunk ID hợp lệ khỏi metric.",
            ],
            "per_query": per_query,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "metrics": payload["metrics"],
                          "latency_ms": payload["latency_ms"]}, ensure_ascii=False))
        return 0
    except (OSError, KeyError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
