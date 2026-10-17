# -*- coding: utf-8 -*-
"""
scripts/build_index.py
Script tạo và cập nhật Vector Index cho Dense Retriever (Sprint 6).
Cách chạy:
    python scripts/build_index.py
    python scripts/build_index.py --model bkai-foundation-models/vietnamese-bi-encoder --mock
"""
from __future__ import annotations

import argparse
import glob
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
    MODEL_DIMENSIONS,
    DenseRetriever,
)
from embedding.vector_store import LegalVectorStore  # noqa: E402


def load_chunks_from_repo(input_path: Path | None = None) -> List[Dict[str, Any]]:
    """
    Ưu tiên đọc file JSON chứa danh sách chunks đã xử lý.
    Nếu chưa có file phẳng, tự động đọc từ parser/parsed_jsons/*.json và chạy chunking_rules.
    """
    if input_path and input_path.exists():
        raw_data = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict) and "chunks" in raw_data:
            return raw_data["chunks"]

    processed_candidates = sorted(glob.glob(str(BASE_DIR / "data" / "processed" / "*.json")))
    if processed_candidates:
        chunks: List[Dict[str, Any]] = []
        for fpath in processed_candidates:
            data = json.loads(Path(fpath).read_text(encoding="utf-8"))
            if isinstance(data, list):
                chunks.extend(data)
        if chunks:
            return chunks

    parsed_files = sorted(glob.glob(str(BASE_DIR / "parser" / "parsed_jsons" / "*.json")))
    if parsed_files:
        from chunking.chunking_rules import chunk_legal_document

        all_payloads: List[Dict[str, Any]] = []
        for fpath in parsed_files:
            doc_json = json.loads(Path(fpath).read_text(encoding="utf-8"))
            res = chunk_legal_document(doc_json)
            for payload in res.get_qdrant_payloads():
                cid = payload.get("chunk_id") or payload.get("id")
                parent_cid = (
                    payload.get("parent_clause_id")
                    or payload.get("clause_id")
                    or f"{payload.get('article_id', 'art')}_clause_1"
                )
                all_payloads.append(
                    {
                        "chunk_id": cid,
                        "document_id": payload.get("document_id"),
                        "article_id": payload.get("article_id"),
                        "clause_id": parent_cid,
                        "parent_clause_id": parent_cid,
                        "chunk_text": payload.get("chunk_text") or payload.get("content") or "",
                        "embed_text": payload.get("embed_text"),
                        "metadata": {
                            "document_number": payload.get("document_number", ""),
                            "document_title": payload.get("title", ""),
                            "article_number": payload.get("article_number", ""),
                            "clause_number": payload.get("clause_number", ""),
                            "validity_status": payload.get("validity_status", "Không xác định"),
                            "breadcrumb": payload.get("breadcrumb", ""),
                        },
                    }
                )
        return all_payloads

    raise FileNotFoundError(
        "Không tìm thấy dữ liệu chunks trong data/processed/ hoặc parser/parsed_jsons/."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Xây dựng Vector Index cho Dense Retriever")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Đường dẫn file JSON chứa danh sách chunks đầu vào",
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
        help="Model ID dùng để tạo embedding",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=None,
        help="Số chiều vector (mặc định tự suy từ model)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Sử dụng vector giả lập tất định (Mock mode) để kiểm thử nhanh",
    )
    args = parser.parse_args()

    dim = args.dimension or MODEL_DIMENSIONS.get(args.model, 768)
    index_dir = Path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    qdrant_path = index_dir / "qdrant_storage"

    print("=" * 65)
    print("BẮT ĐẦU XÂY DỰNG VECTOR INDEX (SPRINT 6 - DENSE RETRIEVAL)")
    print("=" * 65)

    input_path = Path(args.input) if args.input else None
    chunks = load_chunks_from_repo(input_path)
    print(f"[1/3] Đã nạp {len(chunks)} chunks hợp lệ.")

    store = LegalVectorStore(
        collection_name=args.collection,
        dimension=dim,
        storage_path=str(qdrant_path),
        use_qdrant=not args.mock,
    )
    retriever = DenseRetriever(
        vector_store=store,
        model_name=args.model,
        use_mock=args.mock,
    )

    print(f"[2/3] Đang tạo embedding với model '{args.model}' (dim={dim}, mock={args.mock})...")
    t0 = time.perf_counter()
    indexed_count = retriever.index_chunks(chunks)
    elapsed = time.perf_counter() - t0
    throughput = indexed_count / elapsed if elapsed > 0 else 0.0

    snapshot_file = index_dir / "index_snapshot.json"
    if not store.use_qdrant:
        store.save_snapshot_json(snapshot_file)

    meta_file = index_dir / "index_metadata.json"
    meta_info = {
        "model_name": args.model,
        "dimension": dim,
        "collection_name": args.collection,
        "indexed_chunks": indexed_count,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_chunks_per_sec": round(throughput, 2),
        "mock_mode": args.mock,
        "storage_path": str(qdrant_path if store.use_qdrant else snapshot_file),
    }
    meta_file.write_text(json.dumps(meta_info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[3/3] Hoàn tất lập chỉ mục {indexed_count} chunks trong {elapsed:.2f}s ({throughput:.2f} chunks/s).")
    print(f"      Đã lưu metadata cấu hình tại: {meta_file}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())