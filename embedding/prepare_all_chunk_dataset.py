"""Chunk every parsed legal JSON file into one retrieval dataset."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKING_DIR = ROOT / "chunking"
SOURCE_DIR = ROOT / "parser" / "parsed_jsons"
CHUNKS_JSONL = ROOT / "data" / "chunking_output" / "chunks.jsonl"
CONFIG = {
    "parent_max_chars": 1500,
    "child_max_tokens": 256,
    "child_max_units": 200,
    "child_min_words": 20,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    sys.path.insert(0, str(CHUNKING_DIR))
    from chunking_rules import chunk_legal_document

    files = sorted(SOURCE_DIR.glob("*.json"))
    if not files:
        raise RuntimeError(f"Không tìm thấy JSON trong {SOURCE_DIR}")

    all_chunks = []
    document_stats = []
    seen_ids = set()
    source_id_counts: dict[str, int] = {}
    for source in files:
        document = json.loads(source.read_text(encoding="utf-8-sig"))
        result = chunk_legal_document(document, CONFIG)
        chunks = result.get_qdrant_payloads()
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise RuntimeError(f"Chunk thiếu ID hợp lệ trong {source.name}")
            namespaced_id = f"{source.stem}__{chunk_id}"
            source_id_counts[namespaced_id] = source_id_counts.get(namespaced_id, 0) + 1
            if source_id_counts[namespaced_id] > 1:
                namespaced_id += f"__dup{source_id_counts[namespaced_id]}"
            if not isinstance(chunk.get("text") or chunk.get("chunk_text"), str):
                raise RuntimeError(f"Chunk rỗng: {chunk_id}")
            seen_ids.add(namespaced_id)
            chunk["id"] = namespaced_id
            chunk["chunk_id"] = namespaced_id
            if chunk.get("parent_id"):
                chunk["parent_id"] = f"{source.stem}__{chunk['parent_id']}"
            all_chunks.append(chunk)
        document_stats.append({
            "source_file": source.relative_to(ROOT).as_posix(),
            "source_sha256": sha256(source),
            "doc_id": result.doc_id,
            "title": result.title,
            "num_parents": len(result.parents),
            "num_chunks": len(chunks),
            "stats": result.stats,
        })

    if not all_chunks:
        raise RuntimeError("Chunking không sinh child chunk nào")
    try:
        import underthesea  # noqa: F401
        tokenization_backend = "underthesea"
    except ImportError:
        tokenization_backend = "fallback whitespace segmentation (underthesea is not installed)"

    print(f"Documents: {len(document_stats)} | Chunks: {len(all_chunks)} | Parents: {sum(d['num_parents'] for d in document_stats)}")
    print(f"Tokenization: {tokenization_backend}")


if __name__ == "__main__":
    main()
