"""Run BM25, dense, and RRF retrieval over one shared Dev query JSON file."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding.vector_store import EmbeddingService, VectorStore, chunk_file_sha256, load_chunks
from retrieval.hybrid_retriever import (
    EmbeddingQdrantAdapter,
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
        query = row if isinstance(row, str) else row.get("query") if isinstance(row, dict) else None
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"Dev query #{index} phải là chuỗi hoặc object có query không rỗng")
        queries.append(query.strip())
    return queries


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
    parser.add_argument("--model", default="BAAI/bge-m3",
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
        chunks = load_chunks(args.chunks)
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
        embedding = EmbeddingService(args.model)
        slug = re.sub(r"[^a-z0-9]+", "_", args.model.lower()).strip("_")
        default_collection = f"legal_embedding_{slug}_{chunk_file_sha256(args.chunks)[:12]}"
        collection = args.collection or default_collection
        store = VectorStore(collection, embedding.dimension)
        count = store.count()
        if count != len(chunks):
            raise ValueError(f"Collection {collection} có {count} points, fixture có {len(chunks)} chunks")
        config = HybridSearchConfig(top_k=args.top_k, candidate_k=args.candidate_k, rrf_k=args.rrf_k)
        hybrid_retriever = HybridRetriever(sparse, EmbeddingQdrantAdapter(embedding, store), config)

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
