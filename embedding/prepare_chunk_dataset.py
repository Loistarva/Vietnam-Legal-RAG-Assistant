"""Export a frozen child-chunk dataset from the repository's L01 parser JSON."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKING_DIR = ROOT / "chunking"
SOURCE = ROOT / "parser" / "parsed_jsons" / "l_52_2014_qh13.json"
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
        raise RuntimeError("Có chunk thiếu id hợp lệ")
    if len(ids) != len(set(ids)):
        raise RuntimeError("Tồn tại chunk_id bị trùng")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_name": "luat_hon_nhan_gia_dinh_chunking_config_a",
        "source_file": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "chunker": "chunking/chunking_rules.py::chunk_legal_document",
        "chunking_config": CONFIG,
        "tokenization_backend": tokenization_backend,
        "stats": {
            "strategy": "hierarchical_structured_parent_child",
            "num_articles": len(document.get("articles", [])),
            "num_parents": len(result.parents),
            "num_children": len(result.children),
            "avg_children_per_parent": round(len(result.children) / max(len(result.parents), 1), 2),
        },
        "num_parents": len(result.parents),
        "num_chunks": len(chunks),
        "note": "Child chunk được tạo từ parser JSON l_52_2014_qh13 có sẵn bằng engine chunking trong repo. Dùng làm tập đầu vào smoke/thử nghiệm; chưa có nhãn độ liên quan.",
        "chunks": chunks,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(chunks)} chunks from {SOURCE} to {OUTPUT}")


if __name__ == "__main__":
    main()
