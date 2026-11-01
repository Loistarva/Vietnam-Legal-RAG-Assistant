"""Build the Elasticsearch BM25 index from a prepared legal chunk JSON file."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from typing import Any

from retrieval.temporal import normalize_date

try:
    from elasticsearch import Elasticsearch, helpers
    HAS_ELASTICSEARCH = True
except ImportError:
    HAS_ELASTICSEARCH = False
    Elasticsearch = None
    class _DummyHelpers:
        @staticmethod
        def bulk(*args, **kwargs):
            return 0, []
    helpers = _DummyHelpers()

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
from retrieval.settings import DEFAULT_CONFIG_PATH, load_settings


def resolve_bm25_build_config(settings: dict[str, Any], *, chunks_override: str | Path | None = None,
                              index_override: str | None = None) -> dict[str, Any]:
    """Resolve BM25 corpus/index from the shared config, applying explicit overrides."""
    chunks_path = Path(chunks_override or settings["retrieval"]["corpus_path"])
    if not chunks_path.is_absolute():
        chunks_path = ROOT_DIR / chunks_path
    bm25 = settings["bm25"]
    return {
        "chunks_file": chunks_path,
        "index_name": index_override or bm25["index"],
        "tokenizer": bm25["tokenizer"],
        "tokenizer_version": str(bm25["tokenizer_version"]),
        "text_field": bm25["text_field"],
    }
DEFAULT_INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX", "legal-child-chunks-dev")
BM25_TOKENIZER = "underthesea"
BM25_TOKENIZER_VERSION = "9.5.0"

INDEX_MAPPINGS: dict[str, Any] = {
    "_meta": {
        "bm25_tokenizer": BM25_TOKENIZER,
        "bm25_tokenizer_version": BM25_TOKENIZER_VERSION,
        "bm25_text_field": "content_segmented",
    },
    "properties": {
        "chunk_id": {"type": "keyword"},
        "parent_id": {"type": "keyword"},
        "doc_id": {"type": "keyword"},
        "document_id": {"type": "keyword"},
        "article_id": {"type": "keyword"},
        "clause_id": {"type": "keyword"},
        "parent_clause_id": {"type": "keyword"},
        "effective_from": {"type": "date", "format": "yyyy-MM-dd||strict_date_optional_time"},
        "effective_to": {"type": "date", "format": "yyyy-MM-dd||strict_date_optional_time"},
        "title": {"type": "text"},
        "content": {"type": "text"},
        "content_segmented": {"type": "text"},
        "breadcrumb": {"type": "text"},
        "article_ref": {"type": "keyword"},
        "metadata": {"properties": {
            "document_id": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            "article_id": {"type": "keyword"},
            "clause_id": {"type": "keyword"},
            "parent_clause_id": {"type": "keyword"},
            "parent_id": {"type": "keyword"},
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


def _verify_chunking_provenance(chunks_path: Path, *, tokenizer: str = BM25_TOKENIZER,
                                tokenizer_version: str = BM25_TOKENIZER_VERSION) -> dict[str, str]:
    """Require the adjacent chunking report to prove the BM25 tokenizer version."""
    report_path = chunks_path.with_name("chunking_report.json")
    if not report_path.is_file():
        raise FileNotFoundError(
            f"Thiếu báo cáo provenance tokenizer: {report_path}. "
            "Không thể xác nhận content_segmented được tạo bằng underthesea==9.5.0."
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được báo cáo chunking {report_path}: {exc}") from exc
    backend = report.get("tokenization_backend")
    version = str(report.get("tokenization_version", ""))
    if backend != tokenizer or version != tokenizer_version:
        raise ValueError(
            "Tokenizer corpus không khớp cấu hình BM25: "
            f"báo cáo ghi {backend!r} phiên bản {version!r}, yêu cầu "
            f"{tokenizer}=={tokenizer_version}. Hãy tái tạo corpus bằng đúng tokenizer."
        )
    return {"bm25_tokenizer": backend, "bm25_tokenizer_version": version}


def _validate_parent_links(chunks_path: Path, chunks: list[dict[str, Any]]) -> None:
    """Check each ChildChunk parent_id against the adjacent ParentChunk registry."""
    parents_path = chunks_path.with_name("parents.json")
    if not parents_path.is_file():
        raise FileNotFoundError(
            f"Thiếu {parents_path}; không thể xác minh parent_id trỏ tới ParentChunk thật."
        )
    try:
        parents = json.loads(parents_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được ParentChunk file {parents_path}: {exc}") from exc
    if not isinstance(parents, list):
        raise ValueError(f"{parents_path} phải là danh sách ParentChunk")
    parent_children: dict[str, set[str]] = {}
    for row in parents:
        if not isinstance(row, dict) or not row.get("parent_id"):
            raise ValueError(f"ParentChunk trong {parents_path} thiếu parent_id")
        parent_id = str(row["parent_id"]).strip()
        child_ids = row.get("child_ids")
        if not isinstance(child_ids, list):
            raise ValueError(f"ParentChunk {parent_id!r} thiếu danh sách child_ids")
        if parent_id in parent_children:
            raise ValueError(f"parent_id bị trùng trong {parents_path}: {parent_id}")
        parent_children[parent_id] = {str(child_id) for child_id in child_ids}

    for chunk in chunks:
        parent_id = chunk["parent_id"]
        if parent_id not in parent_children:
            raise ValueError(f"Chunk {chunk['chunk_id']!r} trỏ tới ParentChunk không tồn tại: {parent_id!r}")
        if chunk["chunk_id"] not in parent_children[parent_id]:
            raise ValueError(
                f"Chunk {chunk['chunk_id']!r} không nằm trong child_ids của ParentChunk {parent_id!r}"
            )


def load_chunks(path: str | Path | None = None, *,
                config_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read and validate prepared chunks, mapping fields for Elasticsearch."""
    settings = load_settings(config_path)
    chunks_path = Path(path) if path is not None else Path(settings["retrieval"]["corpus_path"])
    if not chunks_path.is_absolute():
        chunks_path = ROOT_DIR / chunks_path
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
                "id", "chunk_id", "parent_id", "parent_clause_id", "doc_id", "document_id",
                "article_id", "clause_id", "text", "content", "chunk_text", "metadata",
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
        # Giữ các khóa ngoại riêng biệt: parent_id trỏ tới ParentChunk, còn
        # parent_clause_id/clause_id trỏ tới Khoản chứa ChildChunk.
        parent_id = item.get("parent_id") or metadata.get("parent_id") or ""
        doc_id = (item.get("document_id") or metadata.get("document_id")
                  or item.get("doc_id") or metadata.get("doc_id") or "")
        article_id = item.get("article_id") or metadata.get("article_id") or ""
        clause_id = item.get("clause_id") or metadata.get("clause_id") or ""
        parent_clause_id = item.get("parent_clause_id") or metadata.get("parent_clause_id") or ""
        required_ids = {
            "document_id": doc_id,
            "article_id": article_id,
            "clause_id": clause_id,
            "parent_clause_id": parent_clause_id,
            "parent_id": parent_id,
        }
        missing_ids = [name for name, value in required_ids.items()
                       if not isinstance(value, (str, int)) or not str(value).strip()]
        if missing_ids:
            raise ValueError(f"Chunk {chunk_id!r} thiếu trường contract bắt buộc: {missing_ids}")
        effective_from = normalize_date(
            item.get("effective_from") or metadata.get("effective_from")
            or item.get("effective_date") or metadata.get("effective_date"),
            field_name="effective_from", chunk_id=chunk_id,
        )
        effective_to = normalize_date(
            item.get("effective_to") or metadata.get("effective_to")
            or item.get("expiry_date") or metadata.get("expiry_date"),
            field_name="effective_to", chunk_id=chunk_id,
        )
        validity_status = item.get("validity_status") or metadata.get("validity_status")
        if validity_status == "Hết hiệu lực" and effective_to is None:
            raise ValueError(
                f"Chunk {chunk_id!r} có validity_status='Hết hiệu lực' nhưng thiếu effective_to; "
                "không thể xác định thời điểm áp dụng cho truy vấn lịch sử."
            )
        title = str(metadata.get("document_title") or metadata.get("title")
                    or item.get("document_title") or item.get("title") or "")
        content_seg = item.get("content_segmented") or item.get("seg_text")
        if not isinstance(content_seg, str) or not content_seg.strip():
            raise ValueError(
                f"Chunk {chunk_id!r} thiếu content_segmented/seg_text đã được tách từ; "
                "BM25 không fallback sang embed_text hoặc văn bản gốc."
            )

        chunks.append({
            "chunk_id": chunk_id,
            "parent_id": str(parent_id),
            "doc_id": str(doc_id),
            "document_id": str(doc_id),
            "article_id": str(article_id),
            "clause_id": str(clause_id),
            "parent_clause_id": str(parent_clause_id),
            "effective_from": effective_from,
            "effective_to": effective_to,
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
    chunks_file: str | Path | None = None,
    es_url: str | None = None,
    index_name: str | None = None,
    *,
    recreate: bool = False,
    client: Any | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load chunks and index them in Elasticsearch; return indexing statistics.

    Pass an existing Elasticsearch client to reuse a connection. This function
    closes clients that it creates itself, but leaves injected clients open.
    Existing chunks are upserted by chunk_id. Set recreate=True to replace the
    whole index and remove documents that are absent from the input file.
    """
    if not HAS_ELASTICSEARCH and client is None:
        raise RuntimeError("Cần cài elasticsearch để dùng build_bm25_index khi không truyền client")
    settings = load_settings(config_path)
    resolved = resolve_bm25_build_config(
        settings, chunks_override=chunks_file, index_override=index_name,
    )
    resolved_es_url = es_url or os.getenv("ELASTICSEARCH_URL", DEFAULT_ES_URL)
    resolved_index_name = resolved["index_name"]
    if not resolved_index_name or not resolved_index_name.strip():
        raise ValueError("index_name không được rỗng")
    
    chunks_path = Path(resolved["chunks_file"])
    if resolved["text_field"] != "content_segmented":
        raise ValueError(
            "BM25 builder hiện chỉ hỗ trợ bm25.text_field='content_segmented', "
            "vì corpus đã chuẩn hóa trường này."
        )

    chunks = load_chunks(chunks_path, config_path=config_path)
    _validate_parent_links(chunks_path, chunks)

    tokenizer_provenance = _verify_chunking_provenance(
        chunks_path, tokenizer=resolved["tokenizer"],
        tokenizer_version=resolved["tokenizer_version"],
    )
    tokenizer_provenance["corpus_sha256"] = hashlib.sha256(
        chunks_path.read_bytes()
    ).hexdigest()
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
            client.indices.create(index=resolved_index_name, mappings={
                "properties": INDEX_MAPPINGS["properties"],
            })
        else:
            try:
                client.indices.put_mapping(
                    index=resolved_index_name,
                    properties=INDEX_MAPPINGS["properties"],
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Không thể đồng bộ mapping contract vào index {resolved_index_name!r}. "
                    "Nếu các trường đã có mapping không tương thích, hãy build index mới hoặc "
                    "chạy lại với --recreate để index lại corpus."
                ) from exc
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
        if errors or indexed != len(chunks) or count != len(chunks):
            raise RuntimeError(
                "BM25 index chưa khớp hoàn toàn với corpus: "
                f"input_chunks={len(chunks)}, indexed={int(indexed)}, "
                f"errors={len(errors)}, index_count={count}. "
                "Kiểm tra error_details; nếu index có tài liệu cũ hoặc mapping ngày không tương thích, "
                "hãy dùng một index mới cô lập hoặc chủ động chạy với --recreate. "
                f"Chi tiết lỗi bulk: {stats['error_details']}"
            )
        client.indices.put_mapping(
            index=resolved_index_name,
            _meta={
                **tokenizer_provenance,
                "bm25_text_field": resolved["text_field"],
            },
        )
        _verify_index_tokenizer(
            client, resolved_index_name, tokenizer=resolved["tokenizer"],
            tokenizer_version=resolved["tokenizer_version"],
            text_field=resolved["text_field"],
        )
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return stats
    finally:
        if owns_client:
            client.close()


def _verify_index_tokenizer(client: Any, index_name: str, *,
                            tokenizer: str = BM25_TOKENIZER,
                            tokenizer_version: str = BM25_TOKENIZER_VERSION,
                            text_field: str = "content_segmented") -> None:
    """Fail closed unless Elasticsearch mapping metadata matches the expected corpus tokenizer."""
    try:
        mapping_response = client.indices.get_mapping(index=index_name)
        mapping = mapping_response[index_name]["mappings"]
        metadata = mapping.get("_meta", {})
    except Exception as exc:
        raise RuntimeError(
            f"Không xác minh được tokenizer metadata của Elasticsearch index {index_name!r}."
        ) from exc
    expected = {
        "bm25_tokenizer": tokenizer,
        "bm25_tokenizer_version": tokenizer_version,
        "bm25_text_field": text_field,
    }
    mismatches = {key: (metadata.get(key), value) for key, value in expected.items()
                  if metadata.get(key) != value}
    if mismatches:
        raise RuntimeError(
            f"Tokenizer metadata của index {index_name!r} không khớp: {mismatches}. "
            "Hãy dựng lại index BM25 từ corpus đã xác minh provenance."
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Dựng index BM25 Elasticsearch từ corpus chunk.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH,
                        help="Shared Retrieval YAML config")
    parser.add_argument("--chunks", type=Path, default=None,
                        help="Corpus override; mặc định lấy retrieval.corpus_path")
    parser.add_argument("--es-url", default=None, help="Mặc định lấy từ ELASTICSEARCH_URL")
    parser.add_argument("--index", default=None, help="Index override; mặc định lấy bm25.index")
    parser.add_argument("--recreate", action="store_true",
                        help="Xóa index cũ trước khi nạp, để không còn chunk của corpus trước")
    args = parser.parse_args()
    build_bm25_index(args.chunks, args.es_url, args.index, recreate=args.recreate,
                     config_path=args.config)


if __name__ == "__main__":
    main()
