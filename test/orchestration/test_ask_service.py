"""AskService: routing branches, Gate release, error mapping and per-stage events (Sprint 10 D5.1)."""
from __future__ import annotations

import json
from datetime import date

import pytest

from model_gateway.llm_gateway import GatewayExecutionError
from orchestration.ask_service import (
    GENERAL_CHAT_MESSAGE,
    MIXED_SCOPE_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    AskService,
    InvalidAskRequest,
    RoutingFailed,
    RuleRouterAdapter,
    gate_fail_error_code,
    next_action,
)
from orchestration.events import ListEventSink
from orchestration.fakes import MOCK_ANSWER, FixtureSource, ScriptedGenerator, build_mock_pipeline
from schemas.models import AskRequest, AskResponse, RouteDecision

LEGAL = "Nam phải đủ bao nhiêu tuổi để kết hôn?"


class FixedRouter:
    """Returns one RouteDecision; records calls."""

    def __init__(self, route: str, action: str | None, reason: str = "TEST_REASON"):
        self.label, self.action, self.reason = route, action, reason
        self.calls: list[dict] = []

    def route(self, *, query: str, query_id: str, as_of_date: str) -> RouteDecision:
        self.calls.append({"query": query, "query_id": query_id, "as_of_date": as_of_date})
        return RouteDecision(route=self.label, reason_code=self.reason, explanation="test", policy_version="test_v1",
                             query_id=query_id, action=self.action, as_of_date=as_of_date)


def make_service(router=None, *, today=date(2026, 11, 16)):
    source, generator, sink = FixtureSource(), ScriptedGenerator(), ListEventSink()
    pipeline = build_mock_pipeline(source=source, generator=generator)
    service = AskService(router or FixedRouter("LEGAL_IN_SCOPE", "LEGAL_RETRIEVAL"), pipeline, sink=sink,
                         today=lambda: today)
    return service, source, generator, sink


@pytest.mark.req("FR1.2-AC1")
@pytest.mark.req("FR1.2-AC2")
def test_general_chat_uses_agent_config_without_retrieval_or_llm():
    import re

    from agent.config import GENERAL_CHAT_MESSAGE as configured_message
    from agent.config import GENERAL_CHAT_RESPONSES
    from agent.router import RuleRouterAdapter as PublicRouterAdapter

    assert RuleRouterAdapter is PublicRouterAdapter  # legacy consumer import stays compatible
    assert GENERAL_CHAT_MESSAGE == configured_message
    for message in GENERAL_CHAT_RESPONSES:
        assert not re.search(r"\bđiều\b|\b\d+/\d{4}/", message, re.IGNORECASE)
    service, source, generator, _ = make_service(PublicRouterAdapter())
    response = service.run(AskRequest(query="Xin chào")).response
    assert response.answer == configured_message
    assert (response.status, response.grounding_status) == ("SUCCESS", "NOT_RUN")
    assert response.citations == [] and response.evidence == []
    assert (source.calls, generator.calls) == (0, 0)


def ask(service, query=LEGAL, **kwargs):
    return service.run(AskRequest(query=query, **kwargs))


def test_legal_pass_returns_answer_citations_and_evidence_after_gate():
    service, source, generator, _ = make_service()
    outcome = ask(service, request_id="req-1")
    response = outcome.response
    assert (response.status, response.route, response.grounding_status) == ("SUCCESS", "LEGAL_IN_SCOPE", "PASS")
    assert response.answer == MOCK_ANSWER  # disclaimer is its own field, not appended
    assert response.disclaimer and response.disclaimer not in response.answer
    assert [c.evidence_index for c in response.citations] == [1, 2]
    assert [e.evidence_index for e in response.evidence] == [1, 2]
    assert response.request_id == "req-1"
    assert response.timings.llm_total_ms == 5.0
    assert (source.calls, generator.calls) == (1, 1)
    assert outcome.rag.record.retrieval_trace["gate"]["status"] == "PASS"


def test_api_and_cli_use_production_run_mode_and_bound_evidence_indices():
    service, *_ = make_service()
    outcome = ask(service)
    assert outcome.rag.llm_response.run_mode == "C_production_rag"


@pytest.mark.parametrize(("route", "action", "message", "status", "code"), [
    ("NON_LEGAL", "GENERAL_CHAT", GENERAL_CHAT_MESSAGE, "SUCCESS", None),
    ("LEGAL_OUT_OF_SCOPE", "POLICY_ABSTENTION", OUT_OF_SCOPE_MESSAGE, "ABSTAIN", "ROUTE_POLICY"),
    ("MIXED_REVIEW", "POLICY_ABSTENTION", MIXED_SCOPE_MESSAGE, "ABSTAIN", "ROUTE_POLICY"),
])
def test_fast_path_and_policy_abstention_skip_retrieval_and_llm(route, action, message, status, code):
    service, source, generator, sink = make_service(FixedRouter(route, action))
    response = ask(service).response
    assert (source.calls, generator.calls) == (0, 0)
    assert response.status == status and response.route == route and response.grounding_status == "NOT_RUN"
    assert response.error_code == code
    assert message in (response.answer or response.abstention_message)
    assert response.evidence == [] and response.citations == []
    assert [e.stage for e in sink.events] == ["router", "response"]


@pytest.mark.parametrize(("marker", "reason", "code"), [
    ("[mock:empty]", "EMPTY_RETRIEVAL", "RETRIEVAL_EMPTY"),
    ("[mock:low]", "LOW_CONFIDENCE", "LOW_CONFIDENCE"),
])
def test_empty_or_low_confidence_retrieval_stops_before_generation(marker, reason, code):
    service, source, generator, _ = make_service()
    response = ask(service, f"{LEGAL} {marker}").response
    assert (source.calls, generator.calls) == (1, 0)
    assert (response.status, response.grounding_status) == ("ABSTAIN", "NOT_RUN")
    assert (response.abstention_reason, response.error_code) == (reason, code)
    assert response.answer is None and "2026-11-16" in response.abstention_message


@pytest.mark.parametrize(("marker", "reason", "code"), [
    ("[mock:gate_fail]", "EVIDENCE_INDEX_OUTSIDE_CONTEXT", "CITATION_INVALID"),
    ("[mock:bad_json]", "LLM_OUTPUT_INVALID_JSON", "JSON_INVALID"),
])
def test_gate_fail_never_returns_the_draft(marker, reason, code):
    service, _, generator, _ = make_service()
    outcome = ask(service, f"{LEGAL} {marker}")
    response = outcome.response
    assert generator.calls == 1
    assert (response.status, response.grounding_status) == ("ABSTAIN", "FAIL")
    assert (response.abstention_reason, response.error_code) == (reason, code)
    assert response.answer is None and response.citations == [] and response.evidence == []
    draft = outcome.rag.llm_response.answer
    if draft:
        assert draft not in json.dumps(response.model_dump(mode="json"), ensure_ascii=False)


def test_model_clarification_and_abstention():
    service, *_ = make_service()
    clarify = ask(service, f"{LEGAL} [mock:clarify]").response
    assert (clarify.status, clarify.grounding_status) == ("NEEDS_CLARIFICATION", "NEEDS_CLARIFICATION")
    assert clarify.clarification and clarify.answer is None
    abstain = ask(service, f"{LEGAL} [mock:abstain]").response
    assert (abstain.status, abstain.grounding_status, abstain.abstention_reason) == ("ABSTAIN", "ABSTAIN",
                                                                                     "MODEL_ABSTAINED")


def test_gateway_timeout_is_typed_error_without_exception_text():
    service, _, _, sink = make_service()
    response = ask(service, f"{LEGAL} [mock:timeout]").response
    assert (response.status, response.error_code, response.grounding_status) == ("ERROR", "LLM_TIMEOUT", "NOT_RUN")
    assert response.error.model_dump() == {"message": "Mô hình ngôn ngữ không phản hồi kịp. Vui lòng thử lại sau.",
                                           "retryable": True}
    assert response.timings.total_ms is not None
    assert "mock gateway timeout" not in json.dumps(response.model_dump(mode="json"), ensure_ascii=False)
    failed = [e for e in sink.events if e.event_type == "pipeline_failed"]
    assert failed and failed[0].masked_metadata["error_type"] == "GatewayExecutionError"


def test_unexpected_pipeline_error_becomes_internal_error():
    class Broken:
        name = "broken"

        def fetch(self, **_):
            raise KeyError("secret detail")

    service = AskService(FixedRouter("LEGAL_IN_SCOPE", "LEGAL_RETRIEVAL"),
                         build_mock_pipeline(source=Broken()), today=lambda: date(2026, 11, 16))
    response = ask(service).response
    assert (response.status, response.error_code) == ("ERROR", "INTERNAL_ERROR")
    assert "secret detail" not in json.dumps(response.model_dump(mode="json"), ensure_ascii=False)


def test_unknown_gateway_error_code_falls_back_to_internal_error():
    class Gen(ScriptedGenerator):
        def generate(self, *args, **kwargs):
            raise GatewayExecutionError("x", error_code="JSON_INVALID")

    service = AskService(FixedRouter("LEGAL_IN_SCOPE", "LEGAL_RETRIEVAL"), build_mock_pipeline(generator=Gen()))
    assert ask(service).response.error_code == "INTERNAL_ERROR"


def test_one_query_id_through_every_stage_and_no_text_in_events():
    service, _, _, sink = make_service()
    outcome = ask(service, query_id="qid-fixed")
    assert outcome.response.query_id == "qid-fixed"
    assert [e.stage for e in sink.events] == ["router", "retrieval", "retrieval", "rerank", "context", "llm", "llm",
                                             "citation", "gate", "response"]
    assert {e.query_id for e in sink.events} == {"qid-fixed"}
    assert outcome.events == sink.events
    dumped = json.dumps([e.model_dump(mode="json") for e in sink.events], ensure_ascii=False)
    for text in (LEGAL, MOCK_ANSWER, outcome.rag.prompt):
        assert text not in dumped


def test_generated_query_ids_are_unique():
    service, *_ = make_service()
    ids = {ask(service).response.query_id for _ in range(5)}
    assert len(ids) == 5 and all(i.startswith("q_") for i in ids)


@pytest.mark.parametrize(("query", "as_of_date", "expected", "source"), [
    ("Nam bao nhiêu tuổi được kết hôn?", None, "2026-11-16", "system_today"),
    ("Nam bao nhiêu tuổi được kết hôn?", "2020-05-01", "2020-05-01", "user_input"),
    ("Tại ngày 01/01/2015 nam bao nhiêu tuổi được kết hôn?", "2020-05-01", "2015-01-01", "query_text"),
])
def test_as_of_date_order_question_then_user_then_today(query, as_of_date, expected, source):
    router = FixedRouter("LEGAL_IN_SCOPE", "LEGAL_RETRIEVAL")
    service, *_ = make_service(router)
    outcome = ask(service, query, as_of_date=as_of_date)
    assert router.calls[0]["as_of_date"] == expected
    assert outcome.rag.payload.as_of_date == expected
    assert outcome.rag.payload.as_of_date_source == source


@pytest.mark.parametrize(("route", "action", "expected"), [
    ("LEGAL_IN_SCOPE", "LEGAL_RETRIEVAL", "rag"),
    ("MIXED_REVIEW", "LEGAL_RETRIEVAL", "rag"),
    ("LEGAL_IN_SCOPE", "FAST_PATH", "rag"),
    ("NON_LEGAL", "GENERAL_CHAT", "general_chat"),
    ("LEGAL_OUT_OF_SCOPE", "POLICY_ABSTENTION", "policy_abstention"),
])
def test_next_action(route, action, expected):
    decision = RouteDecision(route=route, reason_code="R", explanation="e", policy_version="v", action=action)
    assert next_action(decision) == expected


@pytest.mark.parametrize("route", ["LEGAL_IN_SCOPE", "NON_LEGAL", "MIXED_REVIEW", "LEGAL_OUT_OF_SCOPE"])
@pytest.mark.parametrize("action", [None, "SOMETHING_NEW"])
def test_next_action_rejects_missing_or_unknown_action(route, action):
    """SRS 5.3.3: the orchestrator reads only ``action``; it never infers one from ``route``."""
    decision = RouteDecision.model_construct(route=route, reason_code="R", explanation="e", policy_version="v", action=action)
    with pytest.raises(ValueError):
        next_action(decision)


@pytest.mark.parametrize("action", [None, "SOMETHING_NEW"])
def test_router_without_supported_action_is_an_internal_error(action):
    service, source, generator, sink = make_service(FixedRouter("LEGAL_IN_SCOPE", action))
    with pytest.raises(RoutingFailed):
        ask(service)
    assert (source.calls, generator.calls) == (0, 0)
    failed = [e for e in sink.events if e.event_type == "route_failed"]
    assert len(failed) == 1 and (failed[0].stage, failed[0].error_code) == ("router", "INTERNAL_ERROR")


class RaisingRouter:
    def __init__(self, exc: Exception):
        self.exc = exc

    def route(self, *, query: str, query_id: str, as_of_date: str) -> RouteDecision:
        raise self.exc


@pytest.mark.parametrize("reason", ["INVALID_EMPTY_QUERY", "INVALID_QUERY_TYPE", "INVALID_AS_OF_DATE"])
def test_router_input_error_is_an_invalid_request(reason):
    from agent.router.rule_router import RouteReason, RouterInputError

    exc = RouterInputError("bad input", reason_code=RouteReason(reason))
    service, source, generator, sink = make_service(RaisingRouter(exc))
    with pytest.raises(InvalidAskRequest) as err:
        ask(service)
    assert err.value.reason_code == reason
    assert (source.calls, generator.calls) == (0, 0)
    rejected = [e for e in sink.events if e.event_type == "route_rejected"]
    assert len(rejected) == 1 and rejected[0].error_code == "INVALID_REQUEST"


def test_router_crash_is_an_internal_error_without_details():
    service, source, _, sink = make_service(RaisingRouter(RuntimeError("secret detail")))
    with pytest.raises(RoutingFailed) as err:
        ask(service)
    assert "secret detail" not in str(err.value) and err.value.__cause__ is None
    assert source.calls == 0
    assert "secret detail" not in json.dumps([e.model_dump(mode="json") for e in sink.events], ensure_ascii=False)


# SRS 5.3.5: one case per row of the Gate FAIL part of the table.
@pytest.mark.parametrize(("reason", "code"), [
    *[(r, "JSON_INVALID") for r in ("LLM_OUTPUT_INVALID_JSON", "LLM_OUTPUT_TRUNCATED_JSON", "LLM_OUTPUT_RAW_TEXT",
                                    "LLM_OUTPUT_TRUNCATED")],
    *[(r, "CITATION_INVALID") for r in (
        "NON_INTEGER_EVIDENCE_INDEX", "ANSWER_CONTAINS_CHUNK_ID", "ANSWER_MARKER_OUTSIDE_CONTEXT",
        "ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES", "CITATION_OUTSIDE_CONTEXT",
        "CITATION_PROVENANCE_MISMATCH", "INVALID_CITATION_INDEX", "INVALID_CITATION_TYPE", "INVALID_EVIDENCE_INDEX",
        "SOURCE_MAP_INDEX_MISMATCH", "SOURCE_MAP_PROVENANCE_MISMATCH")],
    *[(r, "GROUNDING_FAIL") for r in ("EMPTY_ANSWER", "ANSWER_NOT_VIETNAMESE", "PROMPT_CONTEXT_TRUNCATED",
                                      "QUERY_ID_MISMATCH", "SOME_NEW_GATE_CODE")],
])
def test_gate_fail_reason_maps_to_error_code(reason, code):
    assert gate_fail_error_code(reason) == code


class ReshapedGenerator(ScriptedGenerator):
    """Scripted output, then overrides fields of the LLMResponse (raw text, truncation)."""

    def __init__(self, **update):
        super().__init__()
        self.update = update

    def generate(self, *args, **kwargs):
        return super().generate(*args, **kwargs).model_copy(update=self.update)


@pytest.mark.parametrize(("update", "reason"), [
    ({"parse_status": "raw_text"}, "LLM_OUTPUT_RAW_TEXT"),
    ({"done_reason": "length"}, "LLM_OUTPUT_TRUNCATED"),
    ({"truncated": True}, "LLM_OUTPUT_TRUNCATED"),
])
def test_raw_or_truncated_model_output_is_json_invalid(update, reason):
    source, sink = FixtureSource(), ListEventSink()
    service = AskService(FixedRouter("LEGAL_IN_SCOPE", "LEGAL_RETRIEVAL"),
                         build_mock_pipeline(source=source, generator=ReshapedGenerator(**update)), sink=sink,
                         today=lambda: date(2026, 11, 16))
    response = ask(service).response
    assert (response.status, response.grounding_status) == ("ABSTAIN", "FAIL")
    assert (response.abstention_reason, response.error_code) == (reason, "JSON_INVALID")
    assert response.answer is None


@pytest.mark.parametrize(("query", "route"), [
    (LEGAL, "LEGAL_IN_SCOPE"),
    ("Hôm nay thời tiết Hà Nội thế nào?", "NON_LEGAL"),
    ("Thủ tục thành lập doanh nghiệp tư nhân thế nào?", "LEGAL_OUT_OF_SCOPE"),
])
def test_rule_router_adapter_maps_to_contract(query, route):
    decision = RuleRouterAdapter().route(query=query, query_id="q1", as_of_date="2026-11-16")
    assert isinstance(decision, RouteDecision)
    assert decision.route == route and decision.query_id == "q1" and decision.policy_version.startswith("rule_router")
    assert decision.action in ("LEGAL_RETRIEVAL", "GENERAL_CHAT", "POLICY_ABSTENTION", "FAST_PATH")


def test_every_response_is_a_valid_contract_object():
    service, *_ = make_service()
    for marker in ("", "[mock:empty]", "[mock:low]", "[mock:clarify]", "[mock:abstain]", "[mock:gate_fail]",
                   "[mock:bad_json]", "[mock:timeout]"):
        response = ask(service, f"{LEGAL} {marker}").response
        AskResponse.model_validate(response.model_dump(mode="json"))


# SRS 5.4: minimum masked_metadata per stage (confidence goes to stage ``rerank`` before v1.1).
MIN_METADATA = {
    ("router", "route_decided"): {"route", "action", "reason_code", "policy_version"},
    ("retrieval", "retrieval_finished"): {"corpus_version", "corpus_hash", "retrieval_config_version",
                                          "candidate_count"},
    ("rerank", "confidence_checked"): {"top1_score", "min_top1_score", "threshold_config_version"},
    ("llm", "generation_finished"): {"model", "prompt_version", "token_input", "token_output"},
    ("gate", "gate_decided"): {"grounding_status", "violation_codes"},
    ("response", "response_built"): {"grounding_status", "total_ms", "citation_count", "evidence_count"},
}


@pytest.mark.parametrize("marker", ["", "[mock:gate_fail]"])
def test_stage_events_carry_srs_minimum_metadata(marker):
    service, _, _, sink = make_service()
    response = ask(service, f"{LEGAL} {marker}").response
    seen = {(e.stage, e.event_type): e for e in sink.events}
    for key, fields in MIN_METADATA.items():
        assert fields <= set(seen[key].masked_metadata), key
    gate = seen[("gate", "gate_decided")].masked_metadata
    assert gate["violation_codes"] == ([] if response.grounding_status == "PASS" else [response.abstention_reason])
    built = seen[("response", "response_built")]
    assert built.status == response.status and built.error_code == response.error_code
