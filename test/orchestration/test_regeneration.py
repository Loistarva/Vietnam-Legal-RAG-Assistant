"""Production Gate regeneration and official-run isolation (FR5.6)."""
from unittest.mock import Mock

import pytest

from generation.prompt_builder import get_prompt_hash
from orchestration.events import ListEventSink, StageEmitter
from orchestration.fakes import MOCK_ANSWER, build_mock_pipeline
from orchestration.regeneration import REPAIR_NOTES, RegenerationPolicy
from orchestration.wiring import ServiceSettings, build_ask_service
from schemas.models import AskRequest

LEGAL = "Nam phải đủ bao nhiêu tuổi để kết hôn?"


@pytest.mark.req("FR5.6")
@pytest.mark.req("FR5.6-AC1")
def test_policy_allows_only_the_versioned_reasons():
    policy = RegenerationPolicy()
    assert policy.version == "repair_notes_v1"
    assert policy.repairable == {
        "LLM_OUTPUT_TRUNCATED": "truncated",
        "LLM_OUTPUT_TRUNCATED_JSON": "truncated",
        "ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES": "undeclared_marker",
    }
    for reason, key in policy.repairable.items():
        assert policy.note_for(reason) == REPAIR_NOTES[key]
    for reason in ("ANSWER_MARKER_OUTSIDE_CONTEXT", "EVIDENCE_INDEX_OUTSIDE_CONTEXT", "CITATION_INVALID",
                   "INVALID_CITATION_INDEX", "SOURCE_MAP_MISSING", "LLM_OUTPUT_INVALID_JSON", "ANSWER_NOT_VIETNAMESE"):
        assert policy.note_for(reason) is None
    with pytest.raises(ValueError, match="Missing repair notes"):
        RegenerationPolicy(notes={})


@pytest.mark.req("FR5.6")
@pytest.mark.req("FR5.6-AC3")
def test_official_mode_rejects_regeneration():
    with pytest.raises(ValueError, match="C_production_rag"):
        build_mock_pipeline(run_mode="B_controlled_rag", regeneration=RegenerationPolicy())


@pytest.mark.req("FR5.6")
@pytest.mark.req("FR5.6-AC1")
@pytest.mark.req("FR5.6-AC2")
@pytest.mark.parametrize(("marker", "reason", "note"), [
    ("truncated_once", "LLM_OUTPUT_TRUNCATED", "truncated"),
    ("undeclared_once", "ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES", "undeclared_marker"),
])
def test_retry_uses_original_payload_and_bounds(monkeypatch, marker, reason, note):
    pipeline = build_mock_pipeline(regeneration=RegenerationPolicy())
    gate = Mock(wraps=pipeline.gate)
    monkeypatch.setattr(pipeline, "gate", gate)
    scripted = pipeline.generator.generate

    def measured(*args, **kwargs):
        response = scripted(*args, **kwargs)
        duration = pipeline.generator.calls
        return response.model_copy(update={"load_duration_ms": duration, "ttft_model_ms": 2 * duration,
                                           "eval_duration_ms": 3 * duration, "prompt_eval_duration_ms": 4 * duration})

    generate = Mock(side_effect=measured)
    monkeypatch.setattr(pipeline.generator, "generate", generate)
    sink = ListEventSink()
    result = pipeline.run(query_id="retry", query=f"{LEGAL} [mock:{marker}]", as_of_date="2025-01-01",
                          as_of_date_source="user_input", events=StageEmitter("retry", sink))
    first, second = generate.call_args_list
    assert second.args[0] == first.args[0] + "\n\n" + REPAIR_NOTES[note]
    assert first.args[1:] == second.args[1:]
    assert first.kwargs == second.kwargs == {"structured_output": True, "max_evidence_index": 2}
    first_gate, second_gate = gate.call_args_list
    assert first_gate.args[0] is second_gate.args[0] is result.payload
    assert result.payload.as_of_date == "2025-01-01"
    assert pipeline.source.calls == 1
    assert result.trace["regeneration"] == {
        "attempted": True, "first_reason": reason, "repair_notes_version": "repair_notes_v1",
        "first_prompt_sha256": get_prompt_hash(first.args[0]), "prompt_sha256": get_prompt_hash(second.args[0]),
        "first_answer_before_gate": MOCK_ANSWER,
    }
    starts = [e for e in sink.events if e.event_type == "generation_started"]
    assert len(starts) == 2
    assert starts[1].masked_metadata == {**starts[0].masked_metadata, "attempt": 2, "regeneration_reason": reason,
                                        "repair_notes_version": "repair_notes_v1"}
    assert sink.events[-1].masked_metadata["llm_calls"] == result.record.llm_calls == 2
    assert result.record.grounding_status == "PASS"
    assert result.record.done_reason == "stop" and not result.record.truncated
    assert result.record.token_usage.model_dump() == {"input": 1600, "output": 120}
    timing = result.record.latency_breakdown
    assert (timing.llm_total_ms, timing.ttft_model_ms, timing.load_ms, timing.eval_ms, timing.prompt_eval_ms) == (
        10, 2, 1, 9, 12)


@pytest.mark.req("FR5.6")
@pytest.mark.req("FR5.6-AC1")
@pytest.mark.parametrize(("setting", "marker", "calls", "status", "grounding"), [
    (None, "truncated_once", 2, "SUCCESS", "PASS"),
    ("on", "undeclared_once", 2, "SUCCESS", "PASS"),
    ("on", "truncated", 2, "ABSTAIN", "FAIL"),
    ("on", "gate_fail", 1, "ABSTAIN", "FAIL"),
    ("off", "truncated_once", 1, "ABSTAIN", "FAIL"),
])
def test_service_reports_final_gate_and_call_count(setting, marker, calls, status, grounding):
    env = {"LEGAL_RAG_PIPELINE_MODE": "mock"}
    if setting is not None:
        env["LEGAL_RAG_REGENERATION"] = setting
    service = build_ask_service(ServiceSettings.from_env(env))
    outcome = service.run(AskRequest(query=f"{LEGAL} [mock:{marker}]"))
    assert (outcome.response.status, outcome.response.grounding_status) == (status, grounding)
    assert service.pipeline.generator.calls == outcome.rag.record.llm_calls == calls
    assert outcome.events[-1].masked_metadata["llm_calls"] == calls
    if marker == "gate_fail":
        assert outcome.response.error_code == "CITATION_INVALID"
        assert outcome.rag.trace["regeneration"] == {"attempted": False}
    if setting == "off":
        assert "regeneration" not in outcome.rag.trace


@pytest.mark.req("FR5.6")
@pytest.mark.req("FR5.6-AC1")
@pytest.mark.parametrize("value", ["true", "1", "enabled"])
def test_regeneration_setting_rejects_unknown_values(value):
    with pytest.raises(ValueError, match="LEGAL_RAG_REGENERATION"):
        ServiceSettings.from_env({"LEGAL_RAG_REGENERATION": value})


@pytest.mark.req("FR5.6")
@pytest.mark.req("FR5.6-AC1")
@pytest.mark.parametrize(("second_marker", "expected"), [
    ("abstain", ("ABSTAIN", "ABSTAIN")), ("clarify", ("NEEDS_CLARIFICATION", "NEEDS_CLARIFICATION")),
])
def test_second_gate_decides_without_grounded_answer(monkeypatch, second_marker, expected):
    service = build_ask_service(ServiceSettings(mode="mock"))
    generate = service.pipeline.generator.generate

    def scripted(prompt, *args, **kwargs):
        if "LƯU Ý SỬA LỖI" in prompt:
            prompt = prompt.replace("[mock:truncated_once]", f"[mock:{second_marker}]")
        return generate(prompt, *args, **kwargs)

    monkeypatch.setattr(service.pipeline.generator, "generate", scripted)
    outcome = service.run(AskRequest(query=f"{LEGAL} [mock:truncated_once]"))
    assert (outcome.response.status, outcome.response.grounding_status) == expected
    assert outcome.response.answer is None and outcome.response.citations == []
    assert outcome.rag.record.llm_calls == 2
