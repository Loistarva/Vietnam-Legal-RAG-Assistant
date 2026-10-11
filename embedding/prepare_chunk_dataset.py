"""Export a frozen child-chunk dataset from the repository's L01 parser JSON."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKING_DIR = ROOT / "chunking"
SOURCE = ROOT / "parser" / "parsed_jsons" / "L01.json"
OUTPUT = ROOT / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json"
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

    document = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    result = chunk_legal_document(document, CONFIG)
    try:
        import underthesea  # noqa: F401
        tokenization_backend = "underthesea"
    except ImportError:
        tokenization_backend = "fallback whitespace segmentation (underthesea is not installed)"
    chunks = result.get_qdrant_payloads()
    if not chunks:
        raise RuntimeError("Chunking không sinh child chunk nào")
    ids = [chunk.get("id") for chunk in chunks]
    if any(not isinstance(chunk_id, str) or not chunk_id for chunk_id in ids):
        raise RuntimeError("Có child chunk thiếu ID hợp lệ")
    if len(ids) != len(set(ids)):
        raise RuntimeError("Chunking sinh chunk ID bị trùng")
    for chunk in chunks:
        if not isinstance(chunk.get("text"), str) or not chunk["text"].strip():
            raise RuntimeError(f"Child chunk rỗng: {chunk.get('id')}")
        if not chunk.get("doc_id") or not chunk.get("title"):
            raise RuntimeError(f"Child chunk thiếu metadata tài liệu: {chunk.get('id')}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    dataset = {
        "dataset_name": "luat_hon_nhan_gia_dinh_chunking_config_a",
        "source_file": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(SOURCE),
        "chunker": "chunking/chunking_rules.py::chunk_legal_document",
        "chunking_config": CONFIG,
        "tokenization_backend": tokenization_backend,
        "stats": result.stats,
        "num_parents": len(result.parents),
        "num_chunks": len(chunks),
        "note": "Child chunk được tạo từ parser JSON L01 có sẵn bằng engine chunking trong repo. Dùng làm tập đầu vào smoke/thử nghiệm; chưa có nhãn độ liên quan.",
        "chunks": chunks,
    }
    OUTPUT.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Output: {OUTPUT.relative_to(ROOT).as_posix()}")
    print(f"Chunks: {len(chunks)} | Parents: {len(result.parents)}")
    print(f"Source SHA-256: {dataset['source_sha256']}")
    print(f"Dataset SHA-256: {sha256(OUTPUT)}")


if __name__ == "__main__":
    main()
