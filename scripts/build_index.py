# -*- coding: utf-8 -*-
"""
scripts/build_index.py
Script tạo và cập nhật Vector Index cho Dense Retriever (Sprint 6).
Mặc định đọc corpus chunks từ `data/chunking_output/chunks.jsonl`.
Cách chạy:
    python scripts/build_index.py
    python scripts/build_index.py --model BAAI/bge-m3
    python scripts/build_index.py --model bkai-foundation-models/vietnamese-bi-encoder --mock
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from embedding.dense_retriever import (  # noqa: E402
    DEFAULT_MODEL_NAME,
    DenseRetriever,
    get_model_spec,
    underthesea_version,
)
from embedding.vector_store import (  # noqa: E402
    LegalVectorStore,
    chunk_file_sha256,
    index_metadata_path,
    normalize_chunk_record,
)
from retrieval.build_bm25_index import _validate_parent_links  # noqa: E402

DEFAULT_CHUNKS_FILE = BASE_DIR / "data" / "chunking_output" / "chunks.jsonl"


def load_chunks_from_repo(input_path: Path | str | None = None) -> List[Dict[str, Any]]:
    """
    Đọc danh sách chunks từ file JSON hoặc JSONL chuẩn.
    Báo lỗi dừng ngay nếu file không tồn tại; loại bỏ toàn bộ cơ chế tự động chunking lại
    hoặc fallback sang thư mục processed/parser cũ (Lỗi E12).
    """
    if input_path is None:
        target_path = DEFAULT_CHUNKS_FILE
    else:
        target_path = Path(input_path)

    if not target_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file chunks đầu vào tại: {target_path}")

    raw_text = target_path.read_text(encoding="utf-8-sig")
    if target_path.suffix.lower() == ".jsonl":
        raw_data = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    else:
        raw_data = json.loads(raw_text)

    if isinstance(raw_data, list):
        chunks = raw_data
    elif isinstance(raw_data, dict) and "chunks" in raw_data and isinstance(raw_data["chunks"], list):
        chunks = raw_data["chunks"]
    else:
        raise ValueError(
            f"Dữ liệu chunks trong {target_path} không đúng định dạng list hoặc object có trường 'chunks'."
        )

    if not chunks:
        raise ValueError(f"File chunks {target_path} rỗng.")

    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description="Xây dựng Vector Index cho Dense Retriever")
    parser.add_argument(
        "--input",
        type=str,
        default=str(DEFAULT_CHUNKS_FILE),
        help="Đường dẫn file JSON/JSONL chứa danh sách chunks đầu vào (mặc định data/chunking_output/chunks.jsonl)",
    )
    parser.add_argument(
        "--index-dir",
        type=str,
        default=str(BASE_DIR / "data" / "indexes"),
        help="Thư mục lưu trữ Vector Index",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="vietnam_legal_chunks",
        help="Tên collection trong Qdrant",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL_NAME,
        help="Model ID dùng để tạo embedding (mặc định đọc từ retrieval/config.yaml)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Sử dụng vector giả lập tất định (Mock mode) để kiểm thử nhanh",
    )
    args = parser.parse_args()

    try:
        spec = get_model_spec(args.model)
    except ValueError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    dim = spec["dimension"]
    use_word_seg = spec["use_word_segmentation"]

    index_dir = Path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    qdrant_path = index_dir / "qdrant_storage"

    print("=" * 65)
    print("BẮT ĐẦU XÂY DỰNG VECTOR INDEX (SPRINT 6 - DENSE RETRIEVAL)")
    print("=" * 65)

    input_path = Path(args.input) if args.input else DEFAULT_CHUNKS_FILE
    if not input_path.is_file():
        print(f"LỖI: File input không tồn tại: {input_path}", file=sys.stderr)
        return 1

    try:
        chunks = load_chunks_from_repo(input_path)
        _validate_parent_links(Path(input_path), [normalize_chunk_record(chunk) for chunk in chunks])
    except Exception as exc:
        print(f"LỖI: Không thể nạp chunks từ {input_path}: {exc}", file=sys.stderr)
        return 1

    # [1/3] Xác thực 100% chunks trước khi khởi tạo model
    for i, chunk in enumerate(chunks):
        try:
            normalize_chunk_record(chunk)
        except Exception as exc:
            cid = chunk.get("chunk_id") or chunk.get("id") or f"index_{i}"
            print(f"LỖI: Chunk '{cid}' không hợp lệ: {exc}", file=sys.stderr)
            return 1

    corpus_sha = chunk_file_sha256(input_path)
    print(f"[1/3] Đã nạp và xác thực {len(chunks)} chunks hợp lệ (SHA256={corpus_sha[:12]}...).")

    try:
        # Dựng lại toàn bộ collection: xoá point của corpus cũ và collection khác số chiều
        store = LegalVectorStore(
            collection_name=args.collection,
            dimension=dim,
            storage_path=str(qdrant_path),
            use_qdrant=not args.mock,
            create_if_missing=True,
            recreate=True,
        )
        retriever = DenseRetriever(
            vector_store=store,
            model_name=args.model,
            use_mock=args.mock,
            use_word_segmentation=use_word_seg,
        )
    except Exception as exc:
        print(f"LỖI: Khởi tạo VectorStore/Retriever thất bại: {exc}", file=sys.stderr)
        return 1

    print(f"[2/3] Đang tạo embedding với model '{args.model}' (dim={dim}, word_seg={use_word_seg}, mock={args.mock})...")
    t0 = time.perf_counter()
    try:
        indexed_count = retriever.index_chunks(chunks)
    except Exception as exc:
        print(f"LỖI: Lập chỉ mục chunks thất bại: {exc}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - t0
    throughput = indexed_count / elapsed if elapsed > 0 else 0.0

    snapshot_file = index_dir / "index_snapshot.json"
    if not store.use_qdrant:
        store.save_snapshot_json(snapshot_file)

    meta_info = {
        "collection_name": args.collection,
        "model_name": args.model,
        "dimension": dim,
        "use_word_segmentation": use_word_seg,
        "text_field": retriever.text_field,
        "underthesea_version": underthesea_version() if use_word_seg else None,
        "corpus_sha256": corpus_sha,
        "chunk_count": indexed_count,
        "indexed_chunks": indexed_count,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_chunks_per_sec": round(throughput, 2),
        "mock_mode": args.mock,
        "storage_path": str(qdrant_path if store.use_qdrant else snapshot_file),
    }

    # Một file metadata cho mỗi collection; DenseRetriever đọc lại khi mở collection để truy vấn
    if store.use_qdrant:
        coll_meta_file = index_metadata_path(qdrant_path, args.collection)
    else:
        coll_meta_file = snapshot_file.with_name("index_snapshot_metadata.json")
    coll_meta_file.write_text(json.dumps(meta_info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[3/3] Hoàn tất lập chỉ mục {indexed_count} chunks trong {elapsed:.2f}s ({throughput:.2f} chunks/s).")
    print(f"      Đã lưu metadata cấu hình tại: {coll_meta_file}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
