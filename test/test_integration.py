"""Integration tests for Vietnam-Legal-RAG-Assistant.

Validates end-to-end integration across:
1. Parser output metadata and schema compliance.
2. Chunking output payloads and schema compliance.
3. Vector Store payload normalization, ingestion, and temporal filtering.
4. Hybrid retrieval and Sprint 6 retrieval envelope schema compliance.
5. Benchmark dataset integrity and schema compliance.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import jsonschema
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def test_parser_to_metadata_schema_integration():
    """Verify all parsed JSONs comply with schemas/metadata_schema.json."""
    schema = load_json(ROOT / "schemas" / "metadata_schema.json")
    parsed_files = list((ROOT / "parser" / "parsed_jsons").glob("*.json"))
    assert len(parsed_files) == 11, f"Expected 11 parsed files, found {len(parsed_files)}"

    for f in parsed_files:
        data = load_json(f)
        assert "document_id" in data
        assert "metadata" in data
        jsonschema.validate(instance=data, schema=schema)
        meta = data["metadata"]
        assert meta["source_url"] != "", f"{f.name} missing source_url"
        if meta["validity_status"] == "Hết hiệu lực":
            assert meta.get("expiry_date") is not None, f"Expired doc {f.name} missing expiry_date"

def test_chunking_to_chunk_payload_schema_integration():
    """Verify chunks.jsonl complies with schemas/chunk_payload_schema.json."""
    schema = load_json(ROOT / "schemas" / "chunk_payload_schema.json")
    chunks_path = ROOT / "data" / "chunking_output" / "chunks.jsonl"
    assert chunks_path.exists(), "data/chunking_output/chunks.jsonl not found"

    lines = [line.strip() for line in chunks_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    assert len(lines) > 0

    expired_count = 0
    for line in lines:
        chunk = json.loads(line)
        jsonschema.validate(instance=chunk, schema=schema)
        meta = chunk["metadata"]
        assert meta["source_url"] != ""
        assert meta["effective_from"] != ""
        if chunk["validity_status"] == "Hết hiệu lực":
            assert meta["effective_to"] is not None
            expired_count += 1

    assert expired_count > 0, "Expected expired chunks with effective_to != None"

def test_vector_store_payload_normalization_and_temporal_filtering():
    """Verify vector_store payload normalization and temporal filtering logic."""
    from embedding.vector_store import normalize_chunk_record, LegalVectorStore
    from embedding.dense_retriever import DenseRetriever

    valid_record = {
        "chunk_id": "test_chunk_1",
        "chunk_text": "Nội dung điều luật kiểm thử",
        "embed_text": "Nội dung điều luật kiểm thử",
        "document_id": "test_doc",
        "article_id": "test_doc_art_1",
        "clause_id": "test_doc_art_1_clause_1",
        "parent_clause_id": "test_doc_art_1_clause_1",
        "validity_status": "Còn hiệu lực",
        "effective_from": "2015-01-01",
        "effective_to": None,
        "source_url": "https://example.com/law",
        "metadata": {
            "validity_status": "Còn hiệu lực",
            "effective_from": "2015-01-01",
            "effective_to": None,
            "source_url": "https://example.com/law",
            "article_number": "1"
        }
    }

    norm = normalize_chunk_record(valid_record)
    assert norm["chunk_id"] == "test_chunk_1"
    assert norm["metadata"]["effective_from"] == "2015-01-01"
    assert norm["metadata"]["source_url"] == "https://example.com/law"

    # Test invalid validity_status rejection
    invalid_record = dict(valid_record)
    invalid_record["validity_status"] = "Hết hiệu lực toàn bộ"  # Not in 5-enum set
    with pytest.raises(ValueError):
        normalize_chunk_record(invalid_record)

    # Test storage and retrieval
    store = LegalVectorStore(
        collection_name="test_integration_col",
        dimension=64,
        storage_path=":memory:"
    )
    retriever = DenseRetriever(
        vector_store=store,
        use_mock=True,
        use_word_segmentation=False
    )

    chunks = [
        {
            "chunk_id": "chunk_valid_current",
            "document_id": "l_52_2014_qh13",
            "article_id": "l_52_2014_qh13_art_8",
            "clause_id": "l_52_2014_qh13_art_8_clause_1",
            "parent_clause_id": "l_52_2014_qh13_art_8_clause_1",
            "chunk_text": "Quy định còn hiệu lực hiện hành về hôn nhân.",
            "embed_text": "Quy định còn hiệu lực hiện hành về hôn nhân.",
            "metadata": {
                "document_number": "52/2014/QH13",
                "validity_status": "Còn hiệu lực",
                "effective_from": "2015-01-01",
                "effective_to": None,
                "source_url": "https://vbpl.vn/example",
                "article_number": "8"
            }
        },
        {
            "chunk_id": "chunk_expired_old",
            "document_id": "l_22_2000_qh10",
            "article_id": "l_22_2000_qh10_art_8",
            "clause_id": "l_22_2000_qh10_art_8_clause_1",
            "parent_clause_id": "l_22_2000_qh10_art_8_clause_1",
            "chunk_text": "Quy định hết hiệu lực của luật cũ năm 2000.",
            "embed_text": "Quy định hết hiệu lực của luật cũ năm 2000.",
            "metadata": {
                "document_number": "22/2000/QH10",
                "validity_status": "Hết hiệu lực",
                "effective_from": "2001-01-01",
                "effective_to": "2015-01-01",
                "source_url": "https://vbpl.vn/old",
                "article_number": "8"
            }
        }
    ]

    retriever.index_chunks(chunks)

    # Search filtering expired documents automatically
    active_results = retriever.search("hôn nhân", top_k=5)
    active_ids = [r["chunk_id"] for r in active_results]
    assert "chunk_valid_current" in active_ids
    assert "chunk_expired_old" not in active_ids

def test_retrieval_envelope_schema_integration():
    """Verify hybrid retrieval envelope conforms to schemas/retrieval_schema.json."""
    retrieval_schema = load_json(ROOT / "schemas" / "retrieval_schema.json")

    envelope = {
        "query_id": "HN_001",
        "retriever": "hybrid",
        "results": [
            {
                "chunk_id": "l_52_2014_qh13_art_8_clause_1_chunk_1",
                "document_id": "l_52_2014_qh13",
                "article_id": "l_52_2014_qh13_art_8",
                "clause_id": "l_52_2014_qh13_art_8_clause_1",
                "parent_clause_id": "l_52_2014_qh13_art_8_clause_1",
                "rank": 1,
                "score": 0.032,
                "chunk_text": "Điều kiện kết hôn: Nam từ đủ 20 tuổi trở lên...",
                "metadata": {
                    "validity_status": "Còn hiệu lực",
                    "article_number": "8",
                    "effective_from": "2015-01-01",
                    "effective_to": None,
                    "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=36870"
                },
                "bm25_rank": 1,
                "dense_rank": 2,
                "rrf_score": 0.032
            }
        ]
    }

    validator = Draft202012Validator(retrieval_schema)
    validator.validate(envelope)

def test_benchmark_schema_integration():
    """Verify queries_dev.json and queries_test.json comply with schemas/benchmark_schema.json."""
    schema = load_json(ROOT / "schemas" / "benchmark_schema.json")
    query_subschema = schema["$defs"]["query"]
    validator = Draft202012Validator(query_subschema)

    dev_queries = load_json(ROOT / "data" / "benchmark" / "queries_dev.json")
    test_queries = load_json(ROOT / "data" / "benchmark" / "queries_test.json")

    for q in dev_queries:
        assert q.get("split") == "dev"
        validator.validate(q)

    for q in test_queries:
        assert q.get("split") == "test"
        validator.validate(q)
