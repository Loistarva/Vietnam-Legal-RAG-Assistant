"""Build the Elasticsearch BM25 index from a prepared legal chunk JSON file."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch, helpers

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS_FILE = ROOT_DIR / "data" / "chunking_output" / "chunks.jsonl"
DEFAULT_ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
DEFAULT_INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX", "legal-child-chunks-dev")

INDEX_MAPPINGS: dict[str, Any] = {
    "properties": {
        "chunk_id": {"type": "keyword"},
        "parent_id": {"type": "keyword"},
        "doc_id": {"type": "keyword"},
        "title": {"type": "text"},
        "content": {"type": "text"},
        "content_segmented": {"type": "text"},
        "breadcrumb": {"type": "text"},
        "article_ref": {"type": "keyword"},
        "metadata": {"properties": {
            "article_number": {"type": "keyword"},
            "clause_ref": {"type": "keyword"},
            "validity_status": {"type": "keyword"},
            "effective_date": {"type": "keyword"},
            "document_type": {"type": "keyword"},
            "document_number": {"type": "keyword"},
            "issuing_body": {"type": "keyword"},
        }},
    }
}


def load_chunks(path: str | Path = DEFAULT_CHUNKS_FILE) -> list[dict[str, Any]]:
    """Read and validate prepared chunks, mapping fields for Elasticsearch."""
    chunks_path = Path(path)
    if not chunks_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file chunks: {chunks_path}")

    raw_chunks: list[dict[str, Any]] = []
    try:
        if chunks_path.suffix.lower() == ".jsonl":
            with chunks_path.open("r", encoding="utf-8-sig") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        if isinstance(item, dict):
                            raw_chunks.append(item)
                        else:
                            raise ValueError(f"Dòng {line_num} không phải là object JSON")
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"JSON không hợp lệ tại dòng {line_num} trong {chunks_path}: {exc}") from exc
        else:
            data = json.loads(chunks_path.read_text(encoding="utf-8-sig"))
            if isinstance(data, list):
                raw_chunks = data
            elif isinstance(data, dict) and isinstance(data.get("chunks"), list):
                raw_chunks = data["chunks"]
            else:
                raise ValueError("JSON phải là danh sách chunks hoặc object có trường 'chunks'")
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"Không thể đọc file chunks tại {chunks_path}: {exc}") from exc

    chunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, item in enumerate(raw_chunks, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Chunk thứ {position} không phải object")

        raw_id = item.get("chunk_id", item.get("id"))
        text = item.get("chunk_text") or item.get("text") or item.get("content")
        metadata = item.get("metadata")
        if metadata is None:
            reserved = {
                "id", "chunk_id", "text", "content", "chunk_text", "metadata",
                "content_segmented", "seg_text", "embed_text", "embed_text_raw",
            }
            metadata = {key: value for key, value in item.items() if key not in reserved}
        if not isinstance(raw_id, (str, int)) or not str(raw_id).strip():
            raise ValueError(f"Chunk thứ {position} thiếu chunk_id hợp lệ")
        chunk_id = str(raw_id)
        if chunk_id in seen_ids:
            raise ValueError(f"chunk_id bị trùng: {chunk_id}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Chunk {chunk_id!r} thiếu text/content hợp lệ")
        if not isinstance(metadata, dict):
            raise ValueError(f"metadata của chunk {chunk_id!r} phải là object")
        seen_ids.add(chunk_id)

        article_ref = (metadata.get("article_ref") or metadata.get("article_number")
                       or item.get("article_ref") or item.get("article_number") or "")
        parent_id = (item.get("parent_clause_id") or metadata.get("parent_clause_id")
                     or item.get("parent_id") or metadata.get("parent_id") or "")
        doc_id = (item.get("document_id") or metadata.get("document_id")
                  or item.get("doc_id") or metadata.get("doc_id") or "")
        title = str(metadata.get("document_title") or metadata.get("title")
                    or item.get("document_title") or item.get("title") or "")
        content_seg = (item.get("content_segmented") or item.get("seg_text")
                       or item.get("embed_text") or text)

        chunks.append({
            "chunk_id": chunk_id,
            "parent_id": str(parent_id),
            "doc_id": str(doc_id),
            "title": title,
            "content": text,
            "content_segmented": content_seg,
            "breadcrumb": str(metadata.get("breadcrumb") or item.get("breadcrumb") or ""),
            "article_ref": str(article_ref),
            "metadata": metadata,
        })

    if not chunks:
        raise ValueError(f"Không có chunk hợp lệ trong {chunks_path}")
    return chunks


def build_bm25_index(
    chunks_file: str | Path = DEFAULT_CHUNKS_FILE,
    es_url: str | None = None,
    index_name: str | None = None,
    *,
    recreate: bool = False,
    client: Any | None = None,
) -> dict[str, Any]:
    """Load chunks and index them in Elasticsearch; return indexing statistics.

    Pass an existing Elasticsearch client to reuse a connection. This function
    closes clients that it creates itself, but leaves injected clients open.
    Existing chunks are upserted by chunk_id. Set recreate=True to replace the
    whole index and remove documents that are absent from the input file.
    """
    resolved_es_url = es_url or os.getenv("ELASTICSEARCH_URL", DEFAULT_ES_URL)
    resolved_index_name = index_name or os.getenv("ELASTICSEARCH_INDEX", DEFAULT_INDEX_NAME)
    if not resolved_index_name or not resolved_index_name.strip():
        raise ValueError("index_name không được rỗng")
    chunks_path = Path(chunks_file)
    chunks = load_chunks(chunks_path)
    owns_client = client is None
    if client is None:
        client = Elasticsearch(resolved_es_url, request_timeout=60)

    try:
        if not client.ping():
            raise ConnectionError(f"Không kết nối được Elasticsearch tại {resolved_es_url}")

        exists = client.indices.exists(index=resolved_index_name)
        if exists:
            if recreate:
                client.indices.delete(index=resolved_index_name)
                exists = False

        if not exists:
            client.indices.create(index=resolved_index_name, mappings=INDEX_MAPPINGS)
        actions = (
            {"_op_type": "index", "_index": resolved_index_name,
             "_id": chunk["chunk_id"], "_source": chunk}
            for chunk in chunks
        )
        indexed, errors = helpers.bulk(
            client.options(request_timeout=120), actions,
            chunk_size=500, raise_on_error=False,
        )
        client.indices.refresh(index=resolved_index_name)
        count = int(client.count(index=resolved_index_name)["count"])

        stats = {
            "input_chunks": len(chunks),
            "indexed": int(indexed),
            "errors": len(errors),
            "index_count": count,
            "index_name": resolved_index_name,
            "chunks_file": str(chunks_path),
            "error_details": errors[:5] if errors else [],
        }
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return stats
    finally:
        if owns_client:
            client.close()


def main() -> None:
    build_bm25_index()


if __name__ == "__main__":
    main()
