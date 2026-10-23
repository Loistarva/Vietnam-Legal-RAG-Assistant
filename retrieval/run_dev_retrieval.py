"""Run BM25, dense, and RRF retrieval over one shared Dev query JSON file."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding.dense_retriever import DEFAULT_MODEL_NAME, MODEL_DIMENSIONS, DenseRetriever
from embedding.vector_store import LegalVectorStore
from retrieval.hybrid_retriever import (
    ElasticsearchBM25Retriever,
    HybridRetriever,
    HybridSearchConfig,
)


def read_queries(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được Dev query file {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ValueError("Dev set phải là JSON list không rỗng")
    queries = []
    for index, row in enumerate(data, 1):
        query = (row if isinstance(row, str) else
                 (row.get("query") or row.get("question")) if isinstance(row, dict) else None)
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"Dev query #{index} phải là chuỗi hoặc object có query không rỗng")
        queries.append(query.strip())
    return queries


def count_chunks(path: Path) -> int:
    """Count and validate chunk IDs without requiring a dense-index payload schema."""
    try:
        if path.suffix.lower() == ".jsonl":
            data = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip()]
        else:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được chunk file {path}: {exc}") from exc
    chunks = data if isinstance(data, list) else data.get("chunks") if isinstance(data, dict) else None
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Chunk file phải là JSON list không rỗng hoặc object có trường chunks")
    chunk_ids = [str(row.get("chunk_id") or row.get("id") or "").strip()
                 for row in chunks if isinstance(row, dict)]
    if len(chunk_ids) != len(chunks) or any(not chunk_id for chunk_id in chunk_ids):
        raise ValueError("Mỗi chunk phải là object có chunk_id hoặc id không rỗng")
    if len(set(chunk_ids)) != len(chunk_ids):
        raise ValueError("Chunk file có chunk_id trùng lặp")
    return len(chunks)


def compact(method: str, query: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    score_key = "rrf_score" if method == "hybrid" else "score"
    return [{"query": query, "chunk_id": hit["chunk_id"], "score": hit[score_key], "rank": rank}
            for rank, hit in enumerate(hits, 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, default=ROOT / "data" / "benchmark" / "queries_dev.json",
                        help='JSON list of query strings or objects: [{"query":"..."}]')
    parser.add_argument("--chunks", type=Path,
                        default=ROOT / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME,
                        choices=["AITeamVN/Vietnamese_Embedding", "bkai-foundation-models/vietnamese-bi-encoder", "BAAI/bge-m3"])
    parser.add_argument("--collection", default=None,
                        help="Qdrant collection đã nạp đúng model và chunk fixture")
    parser.add_argument("--elasticsearch-url", default=os.getenv("ELASTICSEARCH_URL"),
                        help="URL Elasticsearch (hoặc đặt biến ELASTICSEARCH_URL)")
    parser.add_argument("--elasticsearch-index", default=os.getenv("ELASTICSEARCH_INDEX", "legal-child-chunks-dev"),
                        help="Index Elasticsearch đã chứa cùng corpus chunks")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "retrieval" / "results")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    args = parser.parse_args()
    try:
        if args.top_k < 1 or args.candidate_k < args.top_k:
            raise ValueError("Cần top_k >= 1 và candidate_k >= top_k")
        queries = read_queries(args.queries)
        chunk_count = count_chunks(args.chunks)
        if not args.elasticsearch_url:
            raise ValueError("Cần --elasticsearch-url hoặc biến ELASTICSEARCH_URL; sparse/BM25 được Elasticsearch xử lý")
        try:
            from elasticsearch import Elasticsearch
        except ImportError as exc:
            raise RuntimeError("Cần cài elasticsearch client để chạy retrieval theo kiến trúc") from exc
        es_client = Elasticsearch(args.elasticsearch_url)
        if not es_client.ping():
            raise ConnectionError(f"Không kết nối được Elasticsearch tại {args.elasticsearch_url}")
        if not es_client.indices.exists(index=args.elasticsearch_index):
            raise ValueError(f"Elasticsearch index không tồn tại: {args.elasticsearch_index}; nạp child chunks trước")
        sparse = ElasticsearchBM25Retriever(es_client, args.elasticsearch_index)
        dimension = MODEL_DIMENSIONS[args.model]
        collection = args.collection or "vietnam_legal_chunks"
        qdrant_path = os.getenv("QDRANT_PATH", str(ROOT / "data" / "indexes" / "qdrant_storage"))
        store = LegalVectorStore(
            collection_name=collection,
            dimension=dimension,
            storage_path=qdrant_path,
        )
        count = store.count()
        if count != chunk_count:
            raise ValueError(f"Collection {collection} có {count} points, fixture có {chunk_count} chunks")
        dense = DenseRetriever(vector_store=store, model_name=args.model)
        config = HybridSearchConfig(top_k=args.top_k, candidate_k=args.candidate_k, rrf_k=args.rrf_k)
        hybrid_retriever = HybridRetriever(sparse, dense, config)

        saved: dict[str, list[dict[str, Any]]] = {"bm25": [], "dense": [], "hybrid": []}
        for query in queries:
            ranked = hybrid_retriever.retrieve(query)
            saved["bm25"].extend(compact("bm25", query, ranked["bm25"]))
            saved["dense"].extend(compact("dense", query, ranked["dense"]))
            saved["hybrid"].extend(compact("hybrid", query, ranked["hybrid"]))

        args.output_dir.mkdir(parents=True, exist_ok=True)
        for method, rows in saved.items():
            destination = args.output_dir / f"dev_{method}.json"
            destination.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{method}: {len(rows)} hits / {len(queries)} queries -> {destination}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
