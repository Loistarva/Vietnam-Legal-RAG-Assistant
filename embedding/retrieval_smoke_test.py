"""Run chunk JSON -> SentenceTransformer -> Qdrant -> Top-K retrieval."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from vector_store import EmbeddingService, VectorStore, load_chunks, chunk_file_sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS = ROOT / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json"
DEFAULT_QUERY = "Điều kiện về độ tuổi kết hôn được quy định như thế nào?"


def collection_name_for(model_name: str, dataset_hash: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")
    return f"legal_embedding_{slug}_{dataset_hash[:12]}"


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        raise ValueError("relevant_ids phải chứa ít nhất một chunk")
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--model", default="bkai-foundation-models/vietnamese-bi-encoder",
                        choices=["AITeamVN/Vietnamese_Embedding", "bkai-foundation-models/vietnamese-bi-encoder", "BAAI/bge-m3"])
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--ground-truth", type=Path, default=None,
                        help='JSON list: [{"query":"...", "relevant_chunk_ids":["..."]}]')
    parser.add_argument("--results", type=Path, default=None,
                        help="Optional path to save machine-readable run measurements")
    args = parser.parse_args()
    try:
        chunks = load_chunks(args.chunks)
        source_hash = chunk_file_sha256(args.chunks)
        print(f"Chunks: {len(chunks)} | SHA-256: {source_hash}")
        service = EmbeddingService(args.model, device=args.device, batch_size=args.batch_size)
        print(f"Model load: {service.load_seconds:.3f}s | dimension: {service.dimension} | max tokens: {service.model.max_seq_length}")
        texts = [chunk["embed_text"] for chunk in chunks]
        vectors = service.embed_documents(texts)
        embed_seconds = service.last_embedding_seconds
        print(f"Embedding: {embed_seconds:.3f}s | {len(chunks) / max(embed_seconds, 1e-12):.2f} chunks/s")
        collection = args.collection or collection_name_for(args.model, source_hash)
        store = VectorStore(collection, service.dimension)
        store.add_chunks(chunks, vectors)
        point_count = store.count()
        if point_count != len(chunks):
            raise RuntimeError(
                f"Collection {collection} có {point_count} points sau khi nạp, "
                f"nhưng dataset hiện tại có {len(chunks)} chunks. "
                "Dùng collection riêng cho dataset này; không tự động xóa dữ liệu cũ."
            )
        print(f"Qdrant collection: {collection} | points: {point_count}")
        query_vector = service.embed_query(args.query)
        query_embedding_seconds = service.last_query_embedding_seconds
        hits = store.search(query_vector, args.top_k)
        query_latency = query_embedding_seconds + store.last_search_seconds
        print(f"Query embedding: {query_embedding_seconds * 1000:.2f} ms | Qdrant search: {store.last_search_seconds * 1000:.2f} ms | query latency (embedding + search): {query_latency * 1000:.2f} ms")
        if not hits:
            raise RuntimeError("Qdrant không trả về kết quả; kiểm tra collection và dữ liệu đã nạp")
        for rank, hit in enumerate(hits, 1):
            if not hit["text"] or not isinstance(hit["metadata"], dict):
                raise RuntimeError(f"Payload Top-K thiếu text/metadata: {hit['chunk_id']}")
            print(f"\n#{rank} {hit['chunk_id']} | score={hit['score']:.5f}")
            print(f"Metadata: {json.dumps(hit['metadata'], ensure_ascii=False)}")
            print(f"Text: {hit['text']}")
        run_result = {
            "model": args.model,
            "collection": collection,
            "chunk_count": len(chunks),
            "chunk_file_sha256": source_hash,
            "dimension": service.dimension,
            "load_seconds": service.load_seconds,
            "embedding_seconds": embed_seconds,
            "chunks_per_second": len(chunks) / max(embed_seconds, 1e-12),
            "vector_bytes_float32_estimate": len(chunks) * service.dimension * 4,
            "query_embedding_seconds": query_embedding_seconds,
            "qdrant_search_seconds": store.last_search_seconds,
            "query_embedding_plus_search_seconds": query_latency,
            "query_latency_scope": "query embedding + Qdrant vector search; excludes model loading, document embedding, reranking, and LLM",
            "top_k": hits,
        }
        if args.ground_truth:
            try:
                judgments = json.loads(args.ground_truth.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Không đọc được ground truth {args.ground_truth}: {exc}") from exc
            if not isinstance(judgments, list) or not judgments:
                raise ValueError("Ground truth phải là list không rỗng")
            dataset_chunk_ids = {chunk["chunk_id"] for chunk in chunks}
            recall_scores = []
            reciprocal_ranks = []
            query_encode_total = 0.0
            qdrant_search_total = 0.0
            for index, judgment in enumerate(judgments, 1):
                if not isinstance(judgment, dict):
                    raise ValueError(f"Ground truth record #{index} phải là object")
                q = judgment.get("query")
                relevant = judgment.get("relevant_chunk_ids")
                if (not isinstance(q, str) or not q.strip() or not isinstance(relevant, list)
                        or not relevant or not all(isinstance(cid, str) and cid for cid in relevant)):
                    raise ValueError(f"Ground truth record #{index} cần query và relevant_chunk_ids không rỗng")
                relevant_ids = set(relevant)
                unknown_ids = relevant_ids - dataset_chunk_ids
                if unknown_ids:
                    raise ValueError(
                        f"Ground truth record #{index} tham chiếu chunk không có trong dataset: "
                        f"{', '.join(sorted(unknown_ids))}"
                    )
                q_vector = service.embed_query(q)
                query_encode_total += service.last_query_embedding_seconds
                ranked = store.search(q_vector, 10)
                qdrant_search_total += store.last_search_seconds
                ranked_ids = [item["chunk_id"] for item in ranked]
                recall_scores.append(recall_at_k(ranked_ids, relevant_ids, 5))
                reciprocal_ranks.append(next((1 / rank for rank, chunk_id in enumerate(ranked_ids, 1)
                                              if rank <= 10 and chunk_id in relevant_ids), 0.0))
            metrics = {"query_count": len(judgments),
                       "recall_at_5": sum(recall_scores) / len(recall_scores),
                       "mrr_at_10": sum(reciprocal_ranks) / len(reciprocal_ranks),
                       "mean_query_embedding_seconds": query_encode_total / len(judgments),
                       "mean_qdrant_search_seconds": qdrant_search_total / len(judgments),
                       "mean_query_embedding_plus_search_seconds": (query_encode_total + qdrant_search_total) / len(judgments)}
            run_result["ground_truth_metrics"] = metrics
            print(f"\nGround truth: {metrics['query_count']} queries | Recall@5={metrics['recall_at_5']:.4f} | MRR@10={metrics['mrr_at_10']:.4f} | mean query latency (embedding + search)={metrics['mean_query_embedding_plus_search_seconds'] * 1000:.2f} ms")
        if args.results:
            args.results.parent.mkdir(parents=True, exist_ok=True)
            args.results.write_text(json.dumps(run_result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved measurements: {args.results}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
