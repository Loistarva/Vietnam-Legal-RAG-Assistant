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


@pytest.mark.req("FR2.11-AC1")
def test_handoff_trace_matches_bundle_without_raw_text_or_shared_state():
    import json

    pipeline = FakePipeline([candidate()])
    adapter = make_adapter(pipeline)
    bundle, trace = adapter.retrieve_with_trace(
        "private query", "2026-10-15", {"query_id": "Q-TRACE", "top_k": 3},
        corpus_version="corpus-v1", as_of_date_source="benchmark",
        filters={"document_id": "law-2014"},
    )
    assert pipeline.call["query_id"] == bundle.query_id == trace["query_id"] == "Q-TRACE"
    assert trace["as_of_date"] == bundle.as_of_date
    assert trace["metadata_filters"] == {"document_id": "law-2014"}
    assert trace["corpus_hash"] == bundle.corpus_hash
    assert trace["corpus_version"] == "corpus-v1"
    assert trace["as_of_date_source"] == "benchmark"
    assert trace["retrieval_config_version"] == bundle.retrieval_config_version
    assert trace["latency_breakdown"] == bundle.latency_breakdown.model_dump(mode="json")
    assert trace["latency_breakdown"]["parent_context_ms"] is None
    assert trace["returned_candidate_count"] == 1
    assert trace["result_top_k"] == 3
    assert trace["outcome"] == "RETRIEVED"
    assert trace["candidates"][0]["retrieval_sources"] == ["bm25", "dense"]
    encoded = json.dumps(trace, ensure_ascii=False)
    assert "private query" not in encoded and candidate()["chunk_text"] not in encoded

    pipeline.results = []
    _, empty_trace = adapter.retrieve_with_trace(
        "other query", "2026-10-15", corpus_version="corpus-v1", as_of_date_source="benchmark",
    )
    assert empty_trace["outcome"] == "EMPTY"
    assert empty_trace["returned_candidate_count"] == 0
    assert empty_trace["candidates"] == []
    assert trace["outcome"] == "RETRIEVED"  # No shared last_trace across requests.


@pytest.mark.req("FR2.11-AC1")
def test_handoff_trace_preserves_unknown_latency_and_precomputed_provenance():
    class SavedPipeline(FakePipeline):
        def run(self, **kwargs):
            result = super().run(**kwargs)
            result["precomputed"] = True
            result["stats"].pop("latency_breakdown")
            return result

    _, trace = make_adapter(SavedPipeline([])).retrieve_with_trace(
        "query", "2026-10-15", corpus_version="corpus-v1", as_of_date_source="benchmark",
    )
    assert trace["precomputed"] is True
    assert trace["latency_breakdown"] is None


@pytest.mark.req("FR2.11-AC1")
def test_handoff_trace_does_not_turn_pipeline_error_into_empty_result():
    class BrokenPipeline:
        def run(self, **kwargs):
            raise RuntimeError("backend unavailable")

    with pytest.raises(RuntimeError, match="backend unavailable"):
        make_adapter(BrokenPipeline()).retrieve_with_trace(
            "query", "2026-10-15", corpus_version="corpus-v1", as_of_date_source="benchmark",
        )


@pytest.mark.req("FR2.11-AC1")
@pytest.mark.parametrize("source,day", [
    ("query_text", "2010-12-31"), ("user_input", "2015-06-01"),
    ("system_today", "2026-11-23"), ("benchmark", "2026-10-15"),
])
def test_trace_preserves_resolved_date_source_and_branch_scores(source, day):
    row = candidate()
    row.update(source_ranks={"bm25": 1, "dense": 2}, source_scores={"bm25": 8.0, "dense": 0.8},
               rrf_score=0.03, reranker_score=0.91)
    _, trace = make_adapter(FakePipeline([row])).retrieve_with_trace(
        "Năm 2000", day, corpus_version="corpus-release-1", as_of_date_source=source,
    )
    assert trace["as_of_date"] == day  # Adapter never extracts a different date from the query.
    assert trace["as_of_date_source"] == source
    assert trace["candidates"][0]["source_scores"] == row["source_scores"]
    assert trace["candidates"][0]["source_ranks"] == row["source_ranks"]
    assert trace["candidates"][0]["rrf_score"] == row["rrf_score"]
    assert trace["candidates"][0]["reranker_score"] == row["reranker_score"]


def test_trace_rejects_missing_version_and_invalid_date_source_before_retrieval():
    pipeline = FakePipeline([])
    adapter = make_adapter(pipeline)
    with pytest.raises(ValueError, match="corpus_version"):
        adapter.retrieve_with_trace("query", "2026-10-15", corpus_version=" ",
                                    as_of_date_source="benchmark")
    with pytest.raises(ValueError, match="as_of_date_source"):
        adapter.retrieve_with_trace("query", "2026-10-15", corpus_version="v1",
                                    as_of_date_source="invented")
    assert pipeline.call is None


@pytest.mark.req("FR2.11-AC1")
@pytest.mark.parametrize("filters", [None, {}])
def test_handoff_without_filters_explicitly_records_no_filter(filters):
    pipeline = FakePipeline([candidate()])
    bundle, trace = make_adapter(pipeline).retrieve_with_trace(
        "synthetic query", "2026-10-15", filters=filters,
        corpus_version="synthetic-v1", as_of_date_source="benchmark",
    )
    assert pipeline.call["metadata_filters"] is None
    assert bundle.metadata_filters is None
    assert trace["metadata_filters"] == {}


@pytest.mark.req("FR2.11-AC1")
def test_handoff_keeps_unmeasured_stages_null_and_measured_zero():
    class PartialTimingPipeline(FakePipeline):
        def run(self, **kwargs):
            result = super().run(**kwargs)
            result["stats"]["latency_breakdown"] = {"bm25_ms": 0.0, "dense_ms": None}
            return result

    bundle, trace = make_adapter(PartialTimingPipeline([])).retrieve_with_trace(
        "synthetic query", "2026-10-15",
        corpus_version="synthetic-v1", as_of_date_source="benchmark",
    )
    assert bundle.latency_ms == 12.5
    assert trace["latency_breakdown"] == {
        "bm25_ms": 0.0, "dense_ms": None, "rrf_ms": None, "reranking_ms": None,
        "parent_context_ms": None, "total_retrieval_ms": None,
    }


@pytest.mark.req("FR2.11-AC1")
@pytest.mark.parametrize("reported_total", [None, 0.0, 7.5])
def test_unknown_total_is_rejected_without_inventing_zero(reported_total):
    class TimingPipeline(FakePipeline):
        def run(self, **kwargs):
            result = super().run(**kwargs)
            result["stats"]["total_latency_ms"] = None
            result["latency_ms"] = reported_total
            return result

    adapter = make_adapter(TimingPipeline([]))
    if reported_total is None:
        with pytest.raises(ValueError, match="Thiếu latency_ms đã đo"):
            adapter.retrieve("synthetic query", "2026-10-15")
    else:
        assert adapter.retrieve("synthetic query", "2026-10-15").latency_ms == reported_total


@pytest.mark.req("FR2.11-AC1")
def test_handoff_fixture_roundtrips_canonical_bundle_and_preserves_trace():
    import json
    from pathlib import Path

    path = Path(__file__).parent / "fixtures/sprint12/retrieval_handoff_samples.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    assert fixture["synthetic"] is True
    for sample in fixture["cases"]:
        bundle = RetrievalBundle.model_validate(sample["bundle"])
        trace = sample["trace"]
        assert bundle.model_dump(mode="json") == sample["bundle"]
        assert trace["query_id"] == bundle.query_id
        assert trace["as_of_date"] == bundle.as_of_date
        assert trace["corpus_hash"] == bundle.corpus_hash
        assert trace["retrieval_config_version"] == bundle.retrieval_config_version
        assert trace["metadata_filters"] == (
            bundle.metadata_filters.model_dump(exclude_none=True) if bundle.metadata_filters else {}
        )
        assert trace["returned_candidate_count"] == len(bundle.candidates)
        assert trace["outcome"] == ("RETRIEVED" if bundle.candidates else "EMPTY")
        assert trace["latency_breakdown"] == (
            bundle.latency_breakdown.model_dump() if bundle.latency_breakdown else None
        )
        assert [row["chunk_id"] for row in trace["candidates"]] == [row.chunk_id for row in bundle.candidates]
        encoded = json.dumps(trace, ensure_ascii=False)
        assert bundle.query not in encoded
        for row in bundle.candidates:
            assert row.chunk_text not in encoded
