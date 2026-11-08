"""D5.3: evidence numbering [1]..[n], index -> child chunk mapping, query_id end to end."""
from __future__ import annotations

import json

import pytest

from orchestration import rag_pipeline
from orchestration.rag_pipeline import PrecomputedRerankedSource, RunVersions, compute_run_versions
from reranking.context_builder import build_context_payload
from reranking.parent_context import ParentContextResolver


def test_evidence_follows_rank_and_maps_back_to_child(rag):
    rows = [rag.make_row(i) for i in range(1, 11)]
    pipeline, gen = rag.make_pipeline(rows)
    gen.response = {"evidence_indices": [2, 4], "answer": "Theo [2] và [4]."}
    result = rag.run(pipeline)
    payload = result.payload
    assert [e.evidence_index for e in payload.evidence_items] == [1, 2, 3, 4, 5]
    assert [e.chunk_id for e in payload.evidence_items] == [r["chunk_id"] for r in rows[:5]]
    record = result.record
    assert record.grounding_status == "PASS"
    assert [(c.evidence_index, c.chunk_id, c.clause_id, c.parent_clause_id) for c in record.citations] == [
        (2, rows[1]["chunk_id"], rows[1]["clause_id"], rows[1]["parent_clause_id"]),
        (4, rows[3]["chunk_id"], rows[3]["clause_id"], rows[3]["parent_clause_id"]),
    ]
    assert "[1] Luật Hôn nhân và gia đình 2014 (52/2014/QH13) | Điều 1 > Khoản 1" in gen.prompts[0]
    assert "[6]" not in gen.prompts[0]
    assert "từ [1] đến [5]" in gen.prompts[0]


def test_query_id_is_kept_end_to_end(rag):
    pipeline, gen = rag.make_pipeline([rag.make_row(1)])
    result = rag.run(pipeline, query_id="HN_042")
    assert pipeline.source.calls[0]["query_id"] == "HN_042"
    assert result.payload.query_id == "HN_042"
    assert gen.query_ids == ["HN_042"]
    assert result.record.query_id == "HN_042"


def test_source_returning_other_query_id_is_an_error(rag):
    pipeline, _ = rag.make_pipeline([], source=rag.StaticSource([rag.make_row(1)], query_id="HN_999"))
    with pytest.raises(ValueError, match="HN_999"):
        rag.run(pipeline, query_id="HN_001")


def test_empty_retrieval_does_not_call_the_model(rag):
    pipeline, gen = rag.make_pipeline([])
    result = rag.run(pipeline)
    assert gen.prompts == []
    assert result.record.grounding_status == "ABSTAIN"
    assert result.record.retrieval_trace["gate"]["reason"] == "EMPTY_RETRIEVAL"
    assert result.record.done_reason == "not_generated"
    assert result.record.citations == [] and result.payload is None


def test_shared_parent_goes_to_best_ranked_child_only(rag):
    first = rag.make_row(1, parent_id="doc_a_art_1", parent_text="[Điều 1] khoản 1 và khoản 2.")
    second = rag.make_row(2, parent_id="doc_a_art_1", parent_text=None, chunk_text="Khoản 2 Điều 1.")
    payload, trace = build_context_payload([first, second], query_id="Q", query="q", as_of_date="2026-01-01",
                                           as_of_date_source="benchmark", max_context_chars=6000)
    assert payload.evidence_items[0].content == "[Điều 1] khoản 1 và khoản 2."
    assert payload.evidence_items[1].content == "Khoản 2 Điều 1."
    assert [e["content"] for e in trace["evidence"]] == ["parent_text", "chunk_text"]


def test_budget_falls_back_to_chunk_then_stops(rag):
    rows = [rag.make_row(1, parent_text="P" * 50, chunk_text="C" * 10),
            rag.make_row(2, parent_text="Q" * 50, chunk_text="D" * 10),
            rag.make_row(3, parent_text=None, chunk_text="E" * 40)]
    payload, trace = build_context_payload(rows, query_id="Q", query="q", as_of_date="2026-01-01",
                                           as_of_date_source="benchmark", max_context_chars=70)
    assert [e.content for e in payload.evidence_items] == ["P" * 50, "D" * 10]
    assert trace["context_budget_truncated"] is True and trace["rows_left_out"] == 1
    assert payload.total_chars == 60


def test_missing_parent_clause_id_is_not_derived(rag):
    row = rag.make_row(1, parent_clause_id=None)
    with pytest.raises(ValueError, match="parent_clause_id"):
        build_context_payload([row], query_id="Q", query="q", as_of_date="2026-01-01",
                              as_of_date_source="benchmark", max_context_chars=6000)


def test_breadcrumb_fallback_uses_article_and_clause_numbers(rag):
    row = rag.make_row(3)
    row["metadata"].pop("breadcrumb")
    row["metadata"]["chapter"] = "Chương II"
    payload, _ = build_context_payload([row], query_id="Q", query="q", as_of_date="2026-01-01",
                                       as_of_date_source="benchmark", max_context_chars=6000)
    assert payload.evidence_items[0].breadcrumb == "Chương II > Điều 3 > Khoản 1"


def test_rerank_top_k_limits_evidence(rag):
    pipeline, gen = rag.make_pipeline([rag.make_row(i) for i in range(1, 8)], rerank_top_k=3)
    result = rag.run(pipeline)
    assert len(result.payload.evidence_items) == 3
    assert "từ [1] đến [3]" in gen.prompts[0]


def test_unsorted_ranks_are_rejected(rag):
    rows = [rag.make_row(2), rag.make_row(1)]
    pipeline, _ = rag.make_pipeline(rows)
    with pytest.raises(ValueError, match="rank"):
        rag.run(pipeline)


def test_parent_resolver_runs_when_rows_have_no_parent_text(rag):
    rows = [rag.make_row(1), rag.make_row(2)]
    for row in rows:
        row.pop("parent_text")
    resolver = ParentContextResolver([{"parent_id": "doc_a_art_1", "text": "[Điều 1] cha.",
                                       "child_ids": [rows[0]["chunk_id"]]}])
    pipeline, _ = rag.make_pipeline(rows, parent_resolver=resolver)
    result = rag.run(pipeline)
    assert result.payload.evidence_items[0].content == "[Điều 1] cha."
    assert result.payload.evidence_items[1].content == rows[1]["chunk_text"]
    assert result.record.retrieval_trace["parent_context"]["parents_attached"] == 1


def _g3_envelope(rag, **config_overrides):
    config = {"retriever": {"corpus_sha256": "abc"},
              "reranker": {"backend": "cross_encoder", "candidate_text": "document_breadcrumb_chunk_text"},
              "parent_context": {"max_context_chars": 6000}, "as_of_date": "2026-10-15"}
    config.update(config_overrides)
    return {**rag.envelope("HN_001", [rag.make_row(1)], "Câu hỏi?"), "config": config}


def _source(envelopes):
    return PrecomputedRerankedSource(envelopes, expected_corpus_sha256="abc",
                                     expected_candidate_text="document_breadcrumb_chunk_text")


def test_precomputed_g3_envelope_is_accepted(rag):
    source = _source([_g3_envelope(rag)])
    assert source.fetch(query_id="HN_001", query="Câu hỏi?", as_of_date="2026-10-15")["query_id"] == "HN_001"


def test_precomputed_d44_record_is_accepted(rag):
    record = {"query_id": "HN_001", "query": "Câu hỏi?", "as_of_date": "2026-10-15", "precomputed": True,
              "reranker_config": {"backend": "cross_encoder", "candidate_text": "document_breadcrumb_chunk_text"},
              "source_run_config": {"retriever": {"corpus_sha256": "abc"}}, "results": [rag.make_row(1)]}
    assert _source([record]).fetch(query_id="HN_001", query="Câu hỏi?", as_of_date="2026-10-15")


@pytest.mark.parametrize("override, message", [
    ({"retriever": {"corpus_sha256": "old"}}, "corpus"),
    ({"reranker": {"backend": "cross_encoder", "candidate_text": "chunk_text"}}, "candidate_text"),
    ({"reranker": {"backend": "mock", "candidate_text": "document_breadcrumb_chunk_text"}}, "cross_encoder"),
    ({"reranker": None}, "reranker"),
])
def test_precomputed_artifact_mismatch_is_refused(rag, override, message):
    with pytest.raises(ValueError, match=message):
        _source([_g3_envelope(rag, **override)])


def test_precomputed_question_or_date_mismatch_is_refused(rag):
    source = _source([_g3_envelope(rag)])
    with pytest.raises(ValueError, match="as_of_date"):
        source.fetch(query_id="HN_001", query="Câu hỏi?", as_of_date="2020-01-01")
    with pytest.raises(ValueError, match="khác câu hỏi"):
        source.fetch(query_id="HN_001", query="Câu khác?", as_of_date="2026-10-15")
    with pytest.raises(ValueError, match="HN_404"):
        source.fetch(query_id="HN_404", query="Câu hỏi?", as_of_date="2026-10-15")


def test_precomputed_from_jsonl_file(rag, tmp_path):
    path = tmp_path / "dev30.jsonl"
    path.write_text(json.dumps(_g3_envelope(rag), ensure_ascii=False) + "\n", encoding="utf-8")
    source = PrecomputedRerankedSource.from_file(path, expected_corpus_sha256="abc",
                                                 expected_candidate_text="document_breadcrumb_chunk_text")
    assert set(source.envelopes) == {"HN_001"}


def test_run_versions(tmp_path):
    from reranking.confidence import ConfidenceConfig

    corpus = tmp_path / "chunks.jsonl"
    corpus.write_bytes(b'{"a":1}\r\n')
    retrieval = tmp_path / "retrieval.yaml"
    retrieval.write_text("retrieval: {top_k: 50}\n", encoding="utf-8")
    rerank = tmp_path / "rerank.yaml"
    rerank.write_text("reranker: {rerank_top_k: 5}\n", encoding="utf-8")

    def versions(version="confidence_off"):
        return compute_run_versions(corpus_path=corpus, retrieval_config=retrieval, rerank_config=rerank,
                                    confidence=ConfidenceConfig(threshold_config_version=version))

    first = versions("v1")
    assert first.threshold_config_version == "v1"
    assert versions("v2").retrieval_config_version == first.retrieval_config_version
    corpus.write_bytes(b'{"a":1}\n')
    assert versions().corpus_version == first.corpus_version
    rerank.write_text("reranker: {rerank_top_k: 3}\n", encoding="utf-8")
    assert versions().retrieval_config_version != first.retrieval_config_version


def test_versions_must_match_threshold_config(rag):
    from reranking.confidence import ConfidenceConfig

    with pytest.raises(ValueError, match="threshold_config_version"):
        rag_pipeline.RAGPipeline(rag.StaticSource([]), rag.FakeGenerator(),
                                 versions=RunVersions("c", "r", "other"), confidence=ConfidenceConfig(),
                                 rerank_top_k=5, max_context_chars=6000)


def test_run_rag_adapter_uses_benchmark_date(rag, monkeypatch):
    pipeline, _ = rag.make_pipeline([rag.make_row(1)])
    monkeypatch.setattr(rag_pipeline, "_DEFAULT_PIPELINE", pipeline)
    record = rag_pipeline.run_rag({"query_id": "HN_007", "query": "Câu hỏi?", "as_of_date": "2010-06-01"})
    assert record["query_id"] == "HN_007" and record["as_of_date"] == "2010-06-01"
    assert record["as_of_date_source"] == "benchmark"
    assert record["grounding_status"] == "PASS"
    json.dumps(record, ensure_ascii=False)
