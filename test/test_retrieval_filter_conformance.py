"""Offline filter parity: production ES adapter, local Qdrant and saved candidates.

ES uses an independent minimal DSL evaluator, not the shared Python predicate.
These tests verify eligible chunks, not ranking equality or a live ES cluster.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from embedding.vector_store import LegalVectorStore, normalize_chunk_record
from reranking.pipeline import PrecomputedRetriever, RetrievalPipeline
from retrieval.adapter import RetrievalAdapter
from retrieval.hybrid_retriever import ElasticsearchBM25Retriever


def _value(record, dotted_key):
    value = record
    for key in dotted_key.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def _es_matches(record, condition):
    if "term" in condition:
        return all(_value(record, key) == value for key, value in condition["term"].items())
    if "exists" in condition:
        return _value(record, condition["exists"]["field"]) is not None
    if "range" in condition:
        for key, bounds in condition["range"].items():
            actual = _value(record, key)
            if actual is None:
                return False
            if "lte" in bounds and actual > bounds["lte"]:
                return False
            if "gt" in bounds and actual <= bounds["gt"]:
                return False
        return True
    if "bool" in condition:
        clauses = condition["bool"]
        return (
            not any(_es_matches(record, c) for c in clauses.get("must_not", []))
            and sum(_es_matches(record, c) for c in clauses.get("should", []))
            >= clauses.get("minimum_should_match", 0)
        )
    raise AssertionError(f"Unexpected Elasticsearch filter: {condition}")


@pytest.fixture()
def branches(monkeypatch):
    specs = [
        ("old", "law-A", "2000-01-01", "2020-01-01", "Hết hiệu lực"),
        ("future", "law-A", "2030-01-01", None, "Còn hiệu lực"),
        ("other", "law-B", "2000-01-01", None, "Còn hiệu lực"),
        ("current", "law-A", "2020-01-01", None, "Còn hiệu lực"),
        ("open", "law-A", None, None, "Không xác định"),
    ]
    records = []
    for index, (chunk_id, doc, start, end, status) in enumerate(specs, 1):
        row = normalize_chunk_record({
            "chunk_id": chunk_id, "chunk_text": "Synthetic legal text",
            "embed_text": "Synthetic legal text",
            "parent_id": "parent", "parent_clause_id": "clause",
            "document_id": doc, "article_id": "article", "clause_id": "clause",
            "effective_from": start, "effective_to": end, "validity_status": status,
            "metadata": {"document_type": "law", "document_number": "SYNTHETIC"},
        })
        row.update(rank=index, score=1.0 / index)
        records.append(row)

    class ElasticsearchFixture:
        def search(self, *, index, size, query):
            # Interpret the actual filter built by ElasticsearchBM25Retriever.
            eligible = [r for r in records if all(
                _es_matches(r, condition) for condition in query["bool"]["filter"]
            )]
            return {"hits": {"hits": [
                {"_id": r["chunk_id"], "_source": r, "_score": r["score"]}
                for r in eligible[:size]
            ]}}

    client = ElasticsearchFixture()
    es = ElasticsearchBM25Retriever(client, "synthetic-index")
    client.indices = SimpleNamespace(get_mapping=lambda index: {index: {"mappings": {"_meta": {
        "bm25_tokenizer": es.tokenizer, "bm25_tokenizer_version": es.tokenizer_version,
        "bm25_text_field": es.text_field,
    }}}})
    monkeypatch.setattr("retrieval.hybrid_retriever._segment_bm25_query", lambda query, **kw: query)
    store = LegalVectorStore(
        collection_name="dev4-filter-conformance", dimension=2,
        storage_path=":memory:", use_qdrant=True,
    )
    # Require the real local Qdrant filter engine; never silently use memory fallback.
    assert store.use_qdrant and store.client is not None
    store.upsert_chunks(records, [[1.0, index / 10] for index in range(len(records))])
    try:
        yield es, store, records
    finally:
        store.client.close()


@pytest.mark.req("FR2.4-AC4")
@pytest.mark.parametrize("as_of_date,filters,expected", [
    ("2019-12-31", {"document_id": "law-A"}, {"old", "open"}),
    ("2020-01-01", {"document_id": "law-A"}, {"current", "open"}),
    ("2030-01-01", {"document_id": "law-A"}, {"future", "current", "open"}),
    ("2020-01-01", {"document_id": "law-B"}, {"other"}),
    ("2020-01-01", {"document_id": "missing"}, set()),
    ("2020-01-01", {"document_number": "SYNTHETIC", "document_type": "law",
                    "article_id": "article", "clause_id": "clause",
                    "validity_status": "Còn hiệu lực"}, {"other", "current"}),
    ("2020-01-01", {}, {"other", "current", "open"}),
])
def test_same_eligible_chunks_across_three_branches(branches, as_of_date, filters, expected):
    es, store, records = branches
    saved = PrecomputedRetriever([{
        "query_id": "Q", "query": "query", "top_k": len(records),
        "config": {"as_of_date": as_of_date}, "results": records,
    }])
    sparse = es.search("query", len(records), as_of_date=as_of_date, metadata_filters=filters)
    dense = store.search([1.0, 0.0], len(records), as_of_date=as_of_date, filters=filters)
    precomputed = saved.search("query", len(records), query_id="Q", as_of_date=as_of_date,
                               metadata_filters=filters)
    assert {r["chunk_id"] for r in sparse} == expected
    assert {r["chunk_id"] for r in dense} == expected
    assert {r["chunk_id"] for r in precomputed} == expected


def test_filters_before_top_k_and_saved_pool_reaches_canonical_adapter(branches):
    es, store, records = branches
    saved = PrecomputedRetriever([{
        "query_id": "Q", "query": "query", "top_k": len(records),
        "config": {"as_of_date": "2020-01-01"}, "results": records,
    }])
    filters = {"document_id": "law-A", "validity_status": "Còn hiệu lực"}
    assert [r["chunk_id"] for r in es.search(
        "query", 1, as_of_date="2020-01-01", metadata_filters=filters,
    )] == ["current"]
    assert [r["chunk_id"] for r in store.search(
        [1.0, 0.0], 1, as_of_date="2020-01-01", filters=filters,
    )] == ["current"]
    pipeline = RetrievalPipeline(saved, None, retrieval_top_k=len(records), retriever_name="precomputed")
    adapter = RetrievalAdapter(pipeline, corpus_hash="a" * 64, retrieval_config_version="fixture-v1")
    bundle, trace = adapter.retrieve_with_trace(
        "query", "2020-01-01", {"query_id": "Q", "top_k": 1}, filters=filters,
        corpus_version="synthetic-v1", as_of_date_source="benchmark",
    )
    assert [r.chunk_id for r in bundle.candidates] == ["current"]
    assert trace["returned_candidate_count"] == 1


def test_precomputed_rejects_wrong_date_and_unknown_filters(branches):
    _, _, records = branches
    saved = PrecomputedRetriever([{
        "query_id": "Q", "query": "query", "top_k": len(records),
        "config": {"as_of_date": "2020-01-01"}, "results": records,
    }])
    with pytest.raises(ValueError, match="as_of_date"):
        saved.search("query", 5, query_id="Q", as_of_date="2020-01-02")
    with pytest.raises(ValueError, match="không hỗ trợ"):
        saved.search("query", 5, query_id="Q", as_of_date="2020-01-01",
                     metadata_filters={"unsupported": "value"})
