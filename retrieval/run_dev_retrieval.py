"""Run BM25, dense, and RRF retrieval over one shared Dev query JSON file."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding.dense_retriever import DEFAULT_MODEL_NAME, MODEL_DIMENSIONS, DenseRetriever
from embedding.vector_store import LegalVectorStore, read_index_metadata
from reranking.pipeline import to_contract_result
from retrieval.hybrid_retriever import (
    ElasticsearchBM25Retriever,
    HybridRetriever,
    HybridSearchConfig,
)
from retrieval.temporal import normalize_as_of_date


def read_queries(path: Path) -> list[tuple[str, str, str]]:
    """Return (query_id, query, as_of_date) rows; missing dates use today's date."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được Dev query file {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ValueError("Dev set phải là JSON list không rỗng")
    queries = []
    for index, row in enumerate(data, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Dev query #{index} phải là object có id và question")
        query_id = row.get("id") or row.get("query_id")
        query = row.get("query") or row.get("question")
        try:
            as_of_date = normalize_as_of_date(row.get("as_of_date"))
        except ValueError as exc:
            raise ValueError(f"Dev query #{index} ({query_id or 'chưa có id'}) có as_of_date sai: {exc}") from exc
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"Dev query #{index} thiếu id")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"Dev query {query_id} thiếu question không rỗng")
        queries.append((query_id.strip(), query.strip(), as_of_date))
    if len({query_id for query_id, _, _ in queries}) != len(queries):
        raise ValueError("Dev query file có id trùng lặp")
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


def to_envelope(method: str, query_id: str, query: str, hits: list[dict[str, Any]],
                config: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    """One RetrievalEnvelope per query and method (data_contract.md mục 5.4)."""
    results = []
    for rank, hit in enumerate(hits, 1):
        row = to_contract_result(hit)
        row["rank"] = rank
        results.append(row)
    return {
        "query_id": query_id,
        "query": query,
        "retriever": method,
        "results": results,
        "latency_ms": latency_ms,
        "top_k": config["top_k"],
        "config": config,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, default=ROOT / "data" / "benchmark" / "queries_dev.json",
                        help='Benchmark query file: JSON objects with id, question, and optional as_of_date')
    parser.add_argument("--chunks", type=Path,
                        default=ROOT / "data" / "chunking_output" / "chunks.jsonl")
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
        corpus_sha256 = hashlib.sha256(args.chunks.read_bytes()).hexdigest()
        bm25_meta = sparse._verify_index_tokenizer()
        if bm25_meta.get("corpus_sha256") != corpus_sha256:
            raise ValueError(
                "Elasticsearch index không được dựng từ đúng file corpus của lần chạy này "
                "(corpus_sha256 không khớp)."
            )
        dense_meta = read_index_metadata(qdrant_path, collection)
        if not dense_meta or dense_meta.get("corpus_sha256") != corpus_sha256:
            raise ValueError(
                "Qdrant collection thiếu metadata corpus hoặc được dựng từ file khác "
                "(corpus_sha256 không khớp)."
            )
        dense = DenseRetriever(vector_store=store, model_name=args.model)
        config = HybridSearchConfig(top_k=args.top_k, candidate_k=args.candidate_k, rrf_k=args.rrf_k)
        hybrid_retriever = HybridRetriever(sparse, dense, config)

        run_config = {
            "top_k": args.top_k, "candidate_k": args.candidate_k, "rrf_k": args.rrf_k,
            "dense_model": args.model, "collection": collection,
            "embedding_dimension": dimension,
            "elasticsearch_index": args.elasticsearch_index, "chunks": str(args.chunks),
            "corpus_sha256": corpus_sha256,
        }
        saved: dict[str, list[dict[str, Any]]] = {"bm25": [], "dense": [], "hybrid": []}
        for query_id, query, query_as_of_date in queries:
            started = time.perf_counter()
            ranked = hybrid_retriever.retrieve(query, as_of_date=query_as_of_date)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            for method in saved:
                query_config = {**run_config, "as_of_date": query_as_of_date}
                saved[method].append(
                    to_envelope(method, query_id, query, ranked[method], query_config, latency_ms)
                )

        args.output_dir.mkdir(parents=True, exist_ok=True)
        for method, envelopes in saved.items():
            destination = args.output_dir / f"dev_{method}.json"
            destination.write_text(json.dumps(envelopes, ensure_ascii=False, indent=2), encoding="utf-8")
            hits = sum(len(envelope["results"]) for envelope in envelopes)
            print(f"{method}: {hits} hits / {len(envelopes)} queries -> {destination}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
