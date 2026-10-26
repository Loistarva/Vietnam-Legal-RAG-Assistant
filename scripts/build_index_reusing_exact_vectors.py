"""Build a Qdrant collection, reusing vectors only for identical embed_text values."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding.dense_retriever import MODEL_DIMENSIONS, DenseRetriever  # noqa: E402
from embedding.vector_store import LegalVectorStore  # noqa: E402


def read_chunks(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    ids = [row.get("chunk_id") or row.get("id") for row in rows]
    if any(not isinstance(cid, str) or not cid for cid in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"chunk_id thiếu hoặc trùng trong {path}")
    if any(not isinstance(row.get("embed_text"), str) or not row["embed_text"].strip() for row in rows):
        raise ValueError(f"Thiếu embed_text trong {path}")
    return rows


def load_vector_cache(source_path: Path, collection: str) -> dict[str, list[float]]:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("Cần qdrant-client để đọc vector cache") from exc
    client = QdrantClient(path=str(source_path))
    try:
        names = {item.name for item in client.get_collections().collections}
        if collection not in names:
            raise ValueError(f"Collection nguồn không tồn tại: {collection} tại {source_path}")
        cache: dict[str, list[float]] = {}
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for point in points:
                payload = point.payload or {}
                text = payload.get("embed_text")
                vector = point.vector
                if isinstance(vector, dict):
                    vector = next(iter(vector.values())) if vector else None
                if isinstance(text, str) and text and vector is not None:
                    cache.setdefault(text, [float(value) for value in vector])
            if offset is None:
                break
        return cache
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-index-dir", type=Path, default=ROOT / "data/indexes")
    parser.add_argument("--source-collection", default="vietnam_legal_chunks_current")
    parser.add_argument("--target-index-dir", type=Path, required=True)
    parser.add_argument("--target-collection", required=True)
    parser.add_argument("--model", default="bkai-foundation-models/vietnamese-bi-encoder")
    args = parser.parse_args()
    try:
        if args.model not in MODEL_DIMENSIONS:
            raise ValueError(f"Model chưa được hỗ trợ: {args.model}")
        chunks = read_chunks(args.input)
        source_path = args.source_index_dir / "qdrant_storage"
        cache = load_vector_cache(source_path, args.source_collection)
        dimension = MODEL_DIMENSIONS[args.model]
        target_storage = args.target_index_dir / "qdrant_storage"
        target_storage.mkdir(parents=True, exist_ok=True)
        store = LegalVectorStore(
            collection_name=args.target_collection,
            dimension=dimension,
            storage_path=str(target_storage),
        )
        if store.count() != 0:
            raise ValueError(f"Collection đích không rỗng: {args.target_collection}")

        vectors: list[list[float] | None] = [None] * len(chunks)
        missing_indices: list[int] = []
        cache_hits = 0
        for i, row in enumerate(chunks):
            cached = cache.get(row["embed_text"])
            if cached is None:
                missing_indices.append(i)
            else:
                if len(cached) != dimension:
                    raise ValueError(f"Vector cache sai dimension ở chunk {row.get('chunk_id')}")
                vectors[i] = cached
                cache_hits += 1

        started = time.perf_counter()
        if missing_indices:
            dense = DenseRetriever(vector_store=store, model_name=args.model)
            encoded = dense.encode_texts([chunks[i]["embed_text"] for i in missing_indices], is_query=False)
            for index, vector in zip(missing_indices, encoded):
                vectors[index] = vector
        complete_vectors = [vector for vector in vectors if vector is not None]
        if len(complete_vectors) != len(chunks):
            raise ValueError("Số vector sau khi ghép cache và embedding không khớp số chunk")
        indexed = store.upsert_chunks(chunks, complete_vectors)
        elapsed = time.perf_counter() - started
        metadata = {
            "model_name": args.model,
            "dimension": dimension,
            "collection_name": args.target_collection,
            "indexed_chunks": indexed,
            "cache_source_collection": args.source_collection,
            "cache_source_index_dir": str(args.source_index_dir),
            "cache_key": "embed_text exact string; model giữ nguyên",
            "reused_vectors": cache_hits,
            "new_embeddings": len(missing_indices),
            "elapsed_seconds": round(elapsed, 3),
            "storage_path": str(target_storage),
        }
        args.target_index_dir.mkdir(parents=True, exist_ok=True)
        (args.target_index_dir / "index_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
