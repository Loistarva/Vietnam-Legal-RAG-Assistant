"""Load normalized child chunks into a local Elasticsearch BM25 index."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from embedding.vector_store import load_chunks


MAPPINGS: dict[str, Any] = {
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
            # Some source records have an empty effective_date; keyword avoids
            # date parsing failures while preserving it as metadata.
            "effective_date": {"type": "keyword"},
            "document_type": {"type": "keyword"},
            "document_number": {"type": "keyword"},
            "issuing_body": {"type": "keyword"},
        }},
    }
}


def build_document(chunk: dict[str, Any]) -> dict[str, Any]:
    metadata = chunk["metadata"]
    return {
        "chunk_id": chunk["chunk_id"],
        "parent_id": metadata.get("parent_id", ""),
        "doc_id": metadata.get("doc_id", ""),
        "title": metadata.get("title", ""),
        "content": chunk["text"],
        "content_segmented": chunk.get("seg_text") or chunk["text"],
        "breadcrumb": metadata.get("breadcrumb", ""),
        "article_ref": metadata.get("article_ref", ""),
        "metadata": metadata,
    }


def index_chunks(client: Any, *, index: str, chunks: list[dict[str, Any]], recreate: bool = False) -> int:
    from elasticsearch.helpers import bulk

    exists = client.indices.exists(index=index)
    if exists and recreate:
        client.indices.delete(index=index)
        exists = False
    if not exists:
        client.indices.create(index=index, mappings=MAPPINGS)

    actions = ({"_index": index, "_id": chunk["chunk_id"], "_source": build_document(chunk)}
               for chunk in chunks)
    indexed_count, errors = bulk(client, actions, raise_on_error=False)
    if errors:
        raise RuntimeError(f"Elasticsearch báo lỗi khi lập chỉ mục: {errors[:3]}")
    client.indices.refresh(index=index)
    actual_count = int(client.count(index=index)["count"])
    if actual_count < len(chunks):
        raise RuntimeError(f"Index có {actual_count} documents, yêu cầu ít nhất {len(chunks)}")
    return int(indexed_count)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"))
    parser.add_argument("--index", default=os.getenv("ELASTICSEARCH_INDEX", "legal-child-chunks-dev"))
    parser.add_argument("--chunks", type=Path,
                        default=repo_root / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json")
    parser.add_argument("--recreate", action="store_true",
                        help="Xóa và tạo lại đúng index đích trước khi nạp chunks")
    args = parser.parse_args()
    try:
        from elasticsearch import Elasticsearch
        client = Elasticsearch(args.url)
        if not client.ping():
            raise ConnectionError(f"Không kết nối được Elasticsearch tại {args.url}")
        chunks = load_chunks(args.chunks)
        count = index_chunks(client, index=args.index, chunks=chunks, recreate=args.recreate)
        print(f"Indexed {count} chunks into {args.index}; total={client.count(index=args.index)['count']}")
        client.close()
        return 0
    except Exception as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
