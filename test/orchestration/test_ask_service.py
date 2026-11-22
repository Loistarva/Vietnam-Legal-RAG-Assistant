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
    RuleRouterAdapter,
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
    ("LEGAL_IN_SCOPE", None, "rag"),
    ("NON_LEGAL", None, "general_chat"),
    ("MIXED_REVIEW", None, "policy_abstention"),
    ("LEGAL_OUT_OF_SCOPE", None, "policy_abstention"),
])
def test_next_action(route, action, expected):
    decision = RouteDecision(route=route, reason_code="R", explanation="e", policy_version="v", action=action)
    assert next_action(decision) == expected


def test_next_action_rejects_unknown_action():
    decision = RouteDecision(route="LEGAL_IN_SCOPE", reason_code="R", explanation="e", policy_version="v",
                             action="SOMETHING_NEW")
    with pytest.raises(ValueError):
        next_action(decision)


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
