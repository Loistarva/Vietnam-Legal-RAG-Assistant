"""Measure real BM25-only, Dense-only, and weighted Hybrid latency on Dev."""
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

from reranking.pipeline import build_hybrid_retriever, load_retrieval_settings  # noqa: E402


def percentile(values: list[float], p: float) -> float | None:
    return values[max(0, math.ceil(p * len(values)) - 1)] if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, default=ROOT / "data/benchmark/queries_dev.json")
    parser.add_argument("--retrieval-config", type=Path, default=ROOT / "retrieval/config.yaml")
    parser.add_argument("--elasticsearch-url", default="http://localhost:9200")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants/E/dev_latency.json")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số query Dev; mặc định chạy toàn bộ.")
    args = parser.parse_args()
    try:
        if "test" in args.queries.stem.casefold():
            raise ValueError("Từ chối đo latency trên file Test; script này chỉ chạy Dev")
        queries = json.loads(args.queries.read_text(encoding="utf-8-sig"))
        if not isinstance(queries, list) or not queries:
            raise ValueError("Dev query file phải là JSON list không rỗng")
        if any(isinstance(row, dict) and str(row.get("split", "")).casefold() == "test" for row in queries):
            raise ValueError("Từ chối chạy latency runner trên query có split=Test")
        rows = []
        for index, row in enumerate(queries, 1):
            if isinstance(row, str):
                qid, question = f"Q_{index:03d}", row
            else:
                qid = str(row.get("query_id") or row.get("id") or f"Q_{index:03d}")
                question = row.get("question") or row.get("query")
            if not isinstance(question, str) or not question.strip():
                raise ValueError(f"Dev query #{index} thiếu question")
            rows.append((qid, question.strip()))
        if args.limit is not None:
            if args.limit < 1:
                raise ValueError("--limit phải lớn hơn 0")
            rows = rows[:args.limit]

        settings = load_retrieval_settings(args.retrieval_config)
        retriever = build_hybrid_retriever(
            settings,
            elasticsearch_url=args.elasticsearch_url,
            qdrant_path=settings["qdrant_path"],
            collection=settings["dense_collection"],
        )
        candidate_k = settings["retrieval_top_k"]
        per_query = []
        methods = {"bm25_only": [], "dense_only": [], "hybrid": []}
        errors = []
        for index, (qid, question) in enumerate(rows, 1):
            measured = {"query_id": qid}
            for name, operation in (
                ("bm25_only", lambda: retriever.bm25_index.search(question, candidate_k)),
                ("dense_only", lambda: retriever.dense_retriever.search(question, candidate_k)),
                ("hybrid", lambda: retriever.retrieve(question)),
            ):
                started = time.perf_counter()
                try:
                    operation()
                    latency = round((time.perf_counter() - started) * 1000.0, 3)
                    methods[name].append(latency)
                    measured[f"{name}_latency_ms"] = latency
                except Exception as exc:
                    errors.append({"query_id": qid, "method": name,
                                   "error": f"{type(exc).__name__}: {exc}"})
                    measured[f"{name}_error"] = f"{type(exc).__name__}: {exc}"
            per_query.append(measured)
            if index % 10 == 0 or index == len(rows):
                print(f"Dev latency: {index}/{len(rows)}", flush=True)

        summaries: dict[str, Any] = {}
        for name, values in methods.items():
            summaries[name] = {
                "queries_measured": len(values),
                "mean_ms": statistics.fmean(values) if values else None,
                "median_ms": statistics.median(values) if values else None,
                "p95_ms": percentile(sorted(values), 0.95),
            }
        payload = {
            "run_date": date.today().isoformat(),
            "split": "dev",
            "query_file": str(args.queries),
            "queries_requested": len(rows),
            "candidate_k": candidate_k,
            "config": {
                "bm25_index": settings["bm25_index"],
                "dense_collection": settings["dense_collection"],
                "dense_model": settings["dense_model"],
                "rrf_k": settings["rrf_k"],
                "bm25_weight": settings["bm25_weight"],
                "dense_weight": settings["dense_weight"],
            },
            "methods": summaries,
            "errors": errors,
            "per_query": per_query,
            "notes": [
                "Latency-only run on Dev; does not read labels or Test data.",
                "Each method is timed separately; Hybrid includes parallel BM25 + Dense search and weighted RRF.",
                "No reranking or parent-context resolution is included in these three measurements.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "methods": summaries,
                          "errors": len(errors)}, ensure_ascii=False))
        return 0
    except (OSError, KeyError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
