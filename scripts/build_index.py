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
    DenseRetriever,
    underthesea_version,
)
from embedding.vector_store import (  # noqa: E402
    LegalVectorStore,
    chunk_file_sha256,
    index_metadata_path,
    normalize_chunk_record,
    read_index_metadata,
)
from retrieval.settings import DEFAULT_CONFIG_PATH, load_settings  # noqa: E402
from retrieval.build_bm25_index import _validate_parent_links  # noqa: E402

def resolve_build_config(settings: dict[str, Any], *, input_override: str | None = None,
                         model_override: str | None = None,
                         collection_override: str | None = None,
                         index_dir_override: str | None = None) -> dict[str, Any]:
    """Resolve build inputs from shared settings, allowing explicit CLI overrides."""
    dense = settings["dense"]
    model = model_override or dense["model"]
    spec = dense["supported_models"].get(model)
    if spec is None:
        raise ValueError(f"Model Dense chưa được đăng ký trong config: {model}")
    input_path = Path(input_override or settings["retrieval"]["corpus_path"])
    if not input_path.is_absolute():
        input_path = BASE_DIR / input_path
    index_dir = Path(index_dir_override or dense["index_dir"])
    if not index_dir.is_absolute():
        index_dir = BASE_DIR / index_dir
    return {
        "input": input_path,
        "model": model,
        "dimension": spec["dimension"],
        "use_word_segmentation": spec["use_word_segmentation"],
        "collection": collection_override or dense["collection"],
        "index_dir": index_dir,
    }


def validate_existing_index_for_build(
    *,
    point_count: int,
    metadata: Dict[str, Any] | None,
    expected: Dict[str, Any],
    recreate: bool,
) -> None:
    """Refuse to mix a new model/corpus into an existing collection without explicit recreate."""
    if recreate or point_count == 0:
        return
    if metadata is None:
        raise ValueError(
            "Collection Qdrant hiện có point nhưng thiếu metadata kiểm chứng; "
            "dùng --recreate để thay toàn bộ collection sau khi xác nhận đúng đích."
        )
    mismatches = {
        key: (metadata.get(key), expected_value)
        for key, expected_value in expected.items()
        if metadata.get(key) != expected_value
    }
    if point_count != expected["chunk_count"]:
        mismatches["collection_point_count"] = (point_count, expected["chunk_count"])
    if mismatches:
        raise ValueError(
            f"Collection Qdrant hiện có không khớp cấu hình/corpus ({mismatches}); "
            "dùng --recreate để thay toàn bộ collection sau khi xác nhận đúng đích."
        )


def load_chunks_from_repo(input_path: Path | str | None = None, *,
                          config_path: str | Path | None = None) -> List[Dict[str, Any]]:
    """
    Đọc danh sách chunks từ file JSON hoặc JSONL chuẩn.
    Báo lỗi dừng ngay nếu file không tồn tại; loại bỏ toàn bộ cơ chế tự động chunking lại
    hoặc fallback sang thư mục processed/parser cũ (Lỗi E12).
    """
    if input_path is None:
        settings = load_settings(config_path)
        target_path = Path(settings["retrieval"]["corpus_path"])
        if not target_path.is_absolute():
            target_path = BASE_DIR / target_path
    else:
        target_path = Path(input_path)
        if not target_path.is_absolute():
            target_path = BASE_DIR / target_path

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
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH,
                        help="Shared Retrieval YAML config")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Corpus override; mặc định lấy retrieval.corpus_path từ shared config",
    )
    parser.add_argument(
        "--index-dir",
        type=str,
        default=None,
        help="Thư mục lưu Vector Index (mặc định dense.index_dir trong shared config)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Tên collection trong Qdrant",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model ID dùng để tạo embedding (mặc định đọc từ retrieval/config.yaml)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Sử dụng vector giả lập tất định (Mock mode) để kiểm thử nhanh",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="XÓA collection Qdrant hiện tại trước khi dựng lại toàn bộ index",
    )
    args = parser.parse_args()

    try:
        settings = load_settings(args.config)
        resolved = resolve_build_config(
            settings, input_override=args.input, model_override=args.model,
            collection_override=args.collection, index_dir_override=args.index_dir,
        )
        input_path = resolved["input"]
        model_name = resolved["model"]
        collection = resolved["collection"]
    except ValueError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    dim = resolved["dimension"]
    use_word_seg = resolved["use_word_segmentation"]

    index_dir = Path(resolved["index_dir"])
    index_dir.mkdir(parents=True, exist_ok=True)
    qdrant_path = index_dir / "qdrant_storage"

    print("=" * 65)
    print("BẮT ĐẦU XÂY DỰNG VECTOR INDEX (SPRINT 6 - DENSE RETRIEVAL)")
    print("=" * 65)

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
        # Recreate chỉ xảy ra khi người chạy chủ động truyền --recreate.
        store = LegalVectorStore(
            collection_name=collection,
            dimension=dim,
            storage_path=str(qdrant_path),
            use_qdrant=not args.mock,
            create_if_missing=True,
            recreate=args.recreate,
        )
        retriever = DenseRetriever(
            vector_store=store,
            model_name=model_name,
            use_mock=args.mock,
            use_word_segmentation=use_word_seg,
            corpus_path=input_path,
            settings=settings,
        )
        validate_existing_index_for_build(
            point_count=store.count(),
            metadata=read_index_metadata(qdrant_path, collection) if store.persistent else None,
            expected={
                "collection_name": collection,
                "model_name": model_name,
                "dimension": dim,
                "use_word_segmentation": use_word_seg,
                "text_field": retriever.text_field,
                "underthesea_version": underthesea_version() if use_word_seg else None,
                "corpus_sha256": corpus_sha,
                "chunk_count": len(chunks),
                "mock_mode": args.mock,
            },
            recreate=args.recreate,
        )
    except Exception as exc:
        print(f"LỖI: Khởi tạo VectorStore/Retriever thất bại: {exc}", file=sys.stderr)
        return 1

    print(f"[2/3] Đang tạo embedding với model '{model_name}' (dim={dim}, word_seg={use_word_seg}, mock={args.mock})...")
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
        "collection_name": collection,
        "model_name": model_name,
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
        coll_meta_file = index_metadata_path(qdrant_path, collection)
    else:
        coll_meta_file = snapshot_file.with_name("index_snapshot_metadata.json")
    coll_meta_file.write_text(json.dumps(meta_info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[3/3] Hoàn tất lập chỉ mục {indexed_count} chunks trong {elapsed:.2f}s ({throughput:.2f} chunks/s).")
    print(f"      Đã lưu metadata cấu hình tại: {coll_meta_file}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
