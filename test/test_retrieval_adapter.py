from __future__ import annotations

import pytest

from retrieval.adapter import RetrievalAdapter
from schemas.models import RetrievalBundle


class FakePipeline:
    def __init__(self, results):
        self.results = results
        self.call = None

    def run(self, **kwargs):
        self.call = kwargs
        return {
            "query_id": kwargs["query_id"],
            "retriever": "hybrid_reranker",
            "results": self.results,
            "top_k": kwargs.get("top_k") or 5,
            "latency_ms": 12.5,
            "stats": {
                "retrieved_candidates": len(self.results),
                "total_latency_ms": 12.5,
                "latency_breakdown": {
                    "bm25_ms": 3.0, "dense_ms": 5.0, "rrf_ms": 0.2,
                    "reranking_ms": 2.0, "parent_context_ms": None,
                    "total_retrieval_ms": 12.5,
                },
            },
        }


def make_adapter(pipeline):
    return RetrievalAdapter(
        pipeline,
        corpus_hash="f" * 64,
        retrieval_config_version="hybrid-reranker-v1",
    )


def candidate():
    return {
        "chunk_id": "chunk-1", "chunk_text": "Nội dung pháp luật.", "score": 0.91,
        "rank": 1, "document_id": "law-2014", "article_id": "article-8",
        "clause_id": "clause-1", "validity_status": "active",
        "effective_from": "2015-01-01", "effective_to": None,
        "retrieval_sources": ["bm25", "dense"], "metadata": {},
    }


def test_adapter_returns_canonical_bundle_and_propagates_temporal_date():
    pipeline = FakePipeline([candidate()])
    bundle = make_adapter(pipeline).retrieve("Điều kiện kết hôn?", "2026-10-15", {"query_id": "Q-1"})

    assert isinstance(bundle, RetrievalBundle)
    assert bundle.schema_version == "week10_v1.1"
    assert bundle.query_id == "Q-1"
    assert bundle.as_of_date == "2026-10-15"
    assert bundle.candidates[0].query_id == "Q-1"
    assert bundle.candidates[0].as_of_date == "2026-10-15"
    assert bundle.candidates[0].retrieval_source == "hybrid_reranker"
    assert bundle.candidates[0].retrieval_sources == ["bm25", "dense"]
    assert bundle.corpus_hash == "f" * 64
    assert bundle.retrieval_config_version == "hybrid-reranker-v1"
    assert bundle.latency_ms == 12.5
    assert bundle.query == "Điều kiện kết hôn?"
    assert bundle.top_k == 5
    assert bundle.latency_breakdown.bm25_ms == 3.0
    assert bundle.latency_breakdown.parent_context_ms is None
    assert pipeline.call["as_of_date"] == "2026-10-15"


def test_adapter_returns_empty_canonical_bundle_without_fabricating_context():
    bundle = make_adapter(FakePipeline([])).retrieve("query", "2026-10-15")

    assert isinstance(bundle, RetrievalBundle)
    assert bundle.candidates == []
    assert bundle.as_of_date == "2026-10-15"
    assert bundle.query_id.startswith("retrieval-")


def test_adapter_serializes_and_propagates_metadata_filters():
    pipeline = FakePipeline([candidate()])
    bundle = make_adapter(pipeline).retrieve(
        "query", "2026-10-15", filters={"document_id": "law-2014", "article_id": "article-8"},
    )

    assert pipeline.call["metadata_filters"] == {
        "document_id": "law-2014", "article_id": "article-8",
    }
    assert bundle.metadata_filters.model_dump(exclude_none=True) == pipeline.call["metadata_filters"]
    assert bundle.model_dump(mode="json")["metadata_filters"]["document_id"] == "law-2014"


def test_adapter_rejects_invalid_metadata_filters():
    adapter = make_adapter(FakePipeline([]))
    with pytest.raises(ValueError, match="không hỗ trợ"):
        adapter.retrieve("query", "2026-10-15", filters={"unknown": "value"})
    with pytest.raises(ValueError, match="không rỗng"):
        adapter.retrieve("query", "2026-10-15", filters={"document_id": " "})


def test_adapter_requires_provenance_and_explicit_valid_date():
    pipeline = FakePipeline([])
    with pytest.raises(ValueError, match="corpus_hash"):
        RetrievalAdapter(pipeline, corpus_hash="", retrieval_config_version="v1")
    with pytest.raises(ValueError, match="retrieval_config_version"):
        RetrievalAdapter(pipeline, corpus_hash="f" * 64, retrieval_config_version=" ")
    adapter = make_adapter(pipeline)
    with pytest.raises(ValueError, match="as_of_date bắt buộc"):
        adapter.retrieve("query", None)
    with pytest.raises(ValueError, match="ngày hợp lệ"):
        adapter.retrieve("query", "2026-02-30")
    with pytest.raises(ValueError, match="canonical contract"):
        adapter.retrieve("query", "2026-10-15", {"locale": "vi"})


def test_adapter_factory_uses_canonical_crlf_safe_corpus_hash(tmp_path):
    from embedding.vector_store import chunk_file_sha256

    corpus = tmp_path / "chunks.jsonl"
    corpus.write_bytes(b'{"chunk_id":"c1"}\r\n')
    adapter = RetrievalAdapter.from_corpus_artifact(
        FakePipeline([]), corpus_path=corpus, retrieval_config_version="hybrid-reranker-v1",
    )
    assert adapter.corpus_hash == chunk_file_sha256(corpus)
    assert len(adapter.corpus_hash) == 64


def test_adapter_rejects_incomplete_candidate_instead_of_fabricating_required_fields():
    pipeline = FakePipeline([{"chunk_id": "incomplete", "chunk_text": "text", "score": 1, "rank": 1}])
    with pytest.raises(ValueError, match="validity_status"):
        make_adapter(pipeline).retrieve("query", "2026-10-15")
