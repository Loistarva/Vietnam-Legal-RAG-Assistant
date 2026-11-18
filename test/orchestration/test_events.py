"""Stage events: allow-listed metadata, broken sinks, JSONL sink, RAGPipeline stages."""
from __future__ import annotations

import json

import pytest

from orchestration.events import JsonlEventSink, ListEventSink, StageEmitter, mask_metadata
from schemas.models import LogEvent


def test_emit_builds_contract_log_event():
    sink = ListEventSink()
    event = StageEmitter("q1", sink).emit("retrieval", "retrieval_finished", "ok", duration_ms=12.345,
                                          candidate_count=3, model=None)
    assert isinstance(event, LogEvent) and sink.events == [event]
    assert event.query_id == "q1" and event.duration_ms == 12.35 and event.timestamp.endswith("Z")
    assert event.masked_metadata == {"candidate_count": 3}  # None dropped


@pytest.mark.parametrize("key", ["query", "prompt", "answer", "x_api_key", "authorization", "chunk_text"])
def test_text_and_secret_keys_are_refused(key):
    with pytest.raises(ValueError):
        mask_metadata({key: "x"})


def test_broken_sink_does_not_break_the_request():
    class Broken:
        def emit(self, event):
            raise OSError("disk full")

    emitter = StageEmitter("q1", Broken())
    emitter.emit("api", "request_received", "accepted")
    assert emitter.sink_errors == 1


def test_jsonl_sink_writes_one_parsable_line_per_event(tmp_path):
    path = tmp_path / "logs" / "events.jsonl"
    emitter = StageEmitter("q1", JsonlEventSink(path))
    emitter.emit("api", "request_received", "accepted")
    emitter.emit("response", "response_built", "SUCCESS", route="LEGAL_IN_SCOPE")
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line["stage"] for line in lines] == ["api", "response"]
    assert len({line["event_id"] for line in lines}) == 2
    LogEvent.model_validate(lines[1])


def test_rag_pipeline_emits_its_stages_with_run_query_id(rag):
    pipeline, _ = rag.make_pipeline([rag.make_row(1), rag.make_row(2)])
    sink = ListEventSink()
    pipeline.run(query_id="HN_001", query="Câu hỏi?", as_of_date="2026-10-15", as_of_date_source="benchmark",
                 events=StageEmitter("HN_001", sink))
    assert [e.stage for e in sink.events] == ["retrieval", "retrieval", "rerank", "context", "llm", "llm",
                                             "citation", "gate"]
    assert {e.query_id for e in sink.events} == {"HN_001"}


def test_rag_pipeline_refuses_emitter_of_another_query(rag):
    pipeline, _ = rag.make_pipeline([rag.make_row(1)])
    with pytest.raises(ValueError):
        pipeline.run(query_id="HN_001", query="Câu hỏi?", as_of_date="2026-10-15", as_of_date_source="benchmark",
                     events=StageEmitter("HN_002"))


def test_run_b_default_keeps_unbounded_evidence_indices(rag):
    """Run B (default) does not pass max_evidence_index; Dev 2's Citation Validity needs the raw list."""
    pipeline, gen = rag.make_pipeline([rag.make_row(1)])
    rag.run(pipeline)
    assert gen.run_modes == ["B_controlled_rag"] and gen.max_evidence_indices == [None]


def test_production_mode_bounds_evidence_indices(rag):
    from orchestration.rag_pipeline import RAGPipeline

    base, gen = rag.make_pipeline([rag.make_row(1), rag.make_row(2)])
    pipeline = RAGPipeline(base.source, gen, versions=base.versions, confidence=base.confidence, rerank_top_k=5,
                           max_context_chars=6000, run_mode="C_production_rag")
    rag.run(pipeline)
    assert gen.run_modes == ["C_production_rag"] and gen.max_evidence_indices == [2]


def test_unknown_run_mode_is_refused(rag):
    from orchestration.rag_pipeline import RAGPipeline

    base, gen = rag.make_pipeline([rag.make_row(1)])
    with pytest.raises(ValueError):
        RAGPipeline(base.source, gen, versions=base.versions, confidence=base.confidence, rerank_top_k=5,
                    max_context_chars=6000, run_mode="A_zero_shot")


def test_gate_names_out_of_range_rejected_indices(rag):
    gen = rag.FakeGenerator(evidence_indices=[1], rejected_evidence_values=["6"], error_code="CITATION_INVALID")
    pipeline, _ = rag.make_pipeline([rag.make_row(1)], gen)
    record = rag.run(pipeline).record
    assert record.grounding_status == "FAIL"
    assert record.retrieval_trace["gate"]["reason"] == "EVIDENCE_INDEX_OUTSIDE_CONTEXT"
    assert record.retrieval_trace["gate"]["invalid_indices"] == [6]


def test_gate_keeps_non_integer_reason(rag):
    gen = rag.FakeGenerator(evidence_indices=[1], rejected_evidence_values=['"1"'])
    pipeline, _ = rag.make_pipeline([rag.make_row(1)], gen)
    assert rag.run(pipeline).record.retrieval_trace["gate"]["reason"] == "NON_INTEGER_EVIDENCE_INDEX"
