"""Run chunk JSON/JSONL -> DenseRetriever -> LegalVectorStore -> Top-K retrieval."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding.dense_retriever import (
    DEFAULT_MODEL_NAME,
    DenseRetriever,
    get_model_spec,
)
from embedding.vector_store import (
    LegalVectorStore,
    chunk_file_sha256,
    load_chunks,
)

DEFAULT_CHUNKS = ROOT / "data" / "chunking_output" / "chunks.jsonl"
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
    parser.add_argument(
        "--chunks",
        type=Path,
        default=DEFAULT_CHUNKS,
        help="Đường dẫn file chunks JSON/JSONL (mặc định: data/chunking_output/chunks.jsonl)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        choices=[
            "AITeamVN/Vietnamese_Embedding",
            "bkai-foundation-models/vietnamese-bi-encoder",
            "BAAI/bge-m3",
        ],
        help="Model Dense Embedding",
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Câu hỏi truy vấn mẫu")
    parser.add_argument("--top-k", type=int, default=5, help="Số lượng kết quả Top-K")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size khi tạo embedding")
    parser.add_argument("--device", default=None, help="Device (cpu/cuda)")
    parser.add_argument("--collection", default=None, help="Tên Qdrant collection")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Chạy ở chế độ Mock không tải model thật và dùng in-memory Qdrant",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help='JSON list: [{"query":"...", "relevant_chunk_ids":["..."]}]',
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=None,
        help="Optional path to save machine-readable run measurements",
    )
    args = parser.parse_args()

    try:
        chunks = load_chunks(args.chunks)
        source_hash = chunk_file_sha256(args.chunks)
        print(f"Chunks: {len(chunks)} | SHA-256: {source_hash}")

        spec = get_model_spec(args.model)
        dim = spec["dimension"]
        use_word_seg = spec["use_word_segmentation"]

        collection = args.collection or collection_name_for(args.model, source_hash)
        qdrant_path = None if args.mock else str(ROOT / "data" / "indexes" / "qdrant_storage")

        store = LegalVectorStore(
            collection_name=collection,
            dimension=dim,
            storage_path=qdrant_path,
            use_qdrant=not args.mock,
            create_if_missing=True,
        )

        retriever = DenseRetriever(
            vector_store=store,
            model_name=args.model,
            use_mock=args.mock,
            use_word_segmentation=use_word_seg,
            batch_size=args.batch_size,
        )

        t0 = time.perf_counter()
        indexed_count = retriever.index_chunks(chunks)
        embed_seconds = time.perf_counter() - t0
        print(f"Index created: {indexed_count} chunks in {embed_seconds:.3f}s ({indexed_count / max(embed_seconds, 1e-12):.2f} chunks/s)")

        t_search_0 = time.perf_counter()
        hits = retriever.search(args.query, top_k=args.top_k)
        total_latency_ms = (time.perf_counter() - t_search_0) * 1000.0

        latency = retriever.last_latency_ms
        print(
            f"Query latency: encode={latency['query_encode_ms']:.2f}ms | "
            f"search={latency['vector_search_ms']:.2f}ms | "
            f"total={total_latency_ms:.2f}ms"
        )

        if not hits and len(chunks) > 0:
            raise RuntimeError("Retriever không trả về kết quả; kiểm tra collection và dữ liệu đã nạp")

        for rank, hit in enumerate(hits, 1):
            chunk_txt = hit.get("chunk_text") or ""
            print(f"\n#{rank} {hit['chunk_id']} | score={hit['score']:.5f}")
            print(f"Metadata: {json.dumps(hit.get('metadata', {}), ensure_ascii=False)}")
            print(f"Chunk text: {chunk_txt[:120]}...")

        run_result = {
            "model": args.model,
            "collection": collection,
            "chunk_count": len(chunks),
            "chunk_file_sha256": source_hash,
            "dimension": dim,
            "mock_mode": args.mock,
            "embedding_seconds": round(embed_seconds, 3),
            "throughput_chunks_per_sec": round(indexed_count / max(embed_seconds, 1e-12), 2),
            "query_latency_ms": latency,
            "top_k": hits,
        }

        if args.ground_truth:
            judgments = json.loads(args.ground_truth.read_text(encoding="utf-8-sig"))
            if not isinstance(judgments, list) or not judgments:
                raise ValueError("Ground truth phải là list không rỗng")
            dataset_chunk_ids = {c["chunk_id"] for c in chunks}
            recall_scores = []
            reciprocal_ranks = []
            for item in judgments:
                q = item.get("query") or item.get("question")
                relevant = item.get("relevant_chunk_ids") or item.get("gold_context_ids") or []
                if not q or not relevant:
                    continue
                relevant_set = set(relevant)
                ranked = retriever.search(q, top_k=10)
                ranked_ids = [h["chunk_id"] for h in ranked]
                recall_scores.append(recall_at_k(ranked_ids, relevant_set, 5))
                reciprocal_ranks.append(
                    next((1.0 / rank for rank, cid in enumerate(ranked_ids, 1) if rank <= 10 and cid in relevant_set), 0.0)
                )
            if recall_scores:
                r5 = sum(recall_scores) / len(recall_scores)
                mrr10 = sum(reciprocal_ranks) / len(reciprocal_ranks)
                print(f"\nGround truth evaluation: Recall@5={r5:.4f} | MRR@10={mrr10:.4f}")
                run_result["evaluation"] = {"recall_at_5": r5, "mrr_at_10": mrr10}

        if args.results:
            args.results.parent.mkdir(parents=True, exist_ok=True)
            args.results.write_text(json.dumps(run_result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nSaved measurements: {args.results}")

        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
