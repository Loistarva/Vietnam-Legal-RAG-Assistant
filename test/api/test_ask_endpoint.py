"""POST /api/v1/ask and GET /api/v1/health (Sprint 10 D5.3)."""
from __future__ import annotations

import json

import pytest

from orchestration.fakes import MOCK_ANSWER
from schemas.models import SCHEMA_VERSION, AskResponse

LEGAL = "Nam phải đủ bao nhiêu tuổi để kết hôn?"


def post(api, body, **kwargs):
    return api.client.post("/api/v1/ask", json=body, headers=kwargs.pop("headers", api.auth), **kwargs)


def test_health_needs_no_key_and_no_pipeline_call(api):
    response = api.client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "schema_version": SCHEMA_VERSION, "pipeline_ready": True}
    assert (api.source.calls, api.generator.calls) == (0, 0)


def test_legal_question_returns_contract_response(api):
    response = post(api, {"query": LEGAL, "as_of_date": "2026-01-01", "request_id": "r-1"})
    assert response.status_code == 200
    body = AskResponse.model_validate(response.json())
    assert (body.status, body.route, body.grounding_status) == ("SUCCESS", "LEGAL_IN_SCOPE", "PASS")
    assert body.answer == MOCK_ANSWER and body.request_id == "r-1"
    assert body.citations and body.evidence and body.disclaimer
    assert response.headers["X-Query-ID"] == body.query_id


@pytest.mark.parametrize(("body", "expected"), [
    ({"query": LEGAL}, ("2026-11-16", "system_today")),
    ({"query": LEGAL, "as_of_date": "2020-05-01"}, ("2020-05-01", "user_input")),
    ({"query": "Tại ngày 01/01/2015 nam bao nhiêu tuổi được kết hôn?", "as_of_date": "2020-05-01"},
     ("2015-01-01", "query_text")),
    ({"query": "Hôm nay thời tiết Hà Nội thế nào?"}, ("2026-11-16", "system_today")),
])
def test_response_tells_which_date_was_applied(api, body, expected):
    data = post(api, body).json()
    assert (data["as_of_date"], data["as_of_date_source"]) == expected


def test_timings_have_total_ms_on_every_branch(api):
    for query in (LEGAL, "Hôm nay thời tiết Hà Nội thế nào?", f"{LEGAL} [mock:low]", f"{LEGAL} [mock:timeout]"):
        timings = post(api, {"query": query}).json()["timings"]
        assert isinstance(timings["total_ms"], float) and timings["total_ms"] >= 0


def test_error_body_is_typed_error_detail(api):
    body = post(api, {"query": f"{LEGAL} [mock:timeout]"}).json()
    assert set(body["error"]) == {"message", "retryable"} and body["error"]["retryable"] is True


def test_client_query_id_is_kept(api):
    response = post(api, {"query": LEGAL, "query_id": "client-qid-1"})
    assert response.json()["query_id"] == "client-qid-1" == response.headers["X-Query-ID"]


@pytest.mark.parametrize(("query", "status", "route", "grounding"), [
    ("Hôm nay thời tiết Hà Nội thế nào?", "SUCCESS", "NON_LEGAL", "NOT_RUN"),
    ("Thủ tục thành lập doanh nghiệp tư nhân thế nào?", "ABSTAIN", "LEGAL_OUT_OF_SCOPE", "NOT_RUN"),
    (f"{LEGAL} [mock:low]", "ABSTAIN", "LEGAL_IN_SCOPE", "NOT_RUN"),
    (f"{LEGAL} [mock:clarify]", "NEEDS_CLARIFICATION", "LEGAL_IN_SCOPE", "NEEDS_CLARIFICATION"),
    (f"{LEGAL} [mock:gate_fail]", "ABSTAIN", "LEGAL_IN_SCOPE", "FAIL"),
])
def test_non_success_statuses_are_http_200_with_status_in_body(api, query, status, route, grounding):
    response = post(api, {"query": query})
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["route"], body["grounding_status"]) == (status, route, grounding)
    if status != "SUCCESS":
        assert body["answer"] is None


@pytest.mark.parametrize(("marker", "http_status", "code"), [("[mock:timeout]", 504, "LLM_TIMEOUT")])
def test_error_status_maps_to_http(api, marker, http_status, code):
    response = post(api, {"query": f"{LEGAL} {marker}"})
    assert response.status_code == http_status
    body = AskResponse.model_validate(response.json())
    assert (body.status, body.error_code, body.answer) == ("ERROR", code, None)


def test_internal_error_maps_to_500(make_api):
    api = make_api()

    def broken(**_):
        raise RuntimeError("boom with secret text")

    api.source.fetch = broken
    response = post(api, {"query": LEGAL})
    assert response.status_code == 500
    assert response.json()["error_code"] == "INTERNAL_ERROR"
    assert "secret text" not in response.text


@pytest.mark.parametrize("body", [
    {},
    {"query": ""},
    {"query": "   "},
    {"query": LEGAL, "as_of_date": "15/10/2026"},
    {"query": LEGAL, "run_mode": "A_zero_shot"},
    {"query": LEGAL, "top_k": 20},
    {"query": LEGAL, "schema_version": "week9"},
])
def test_invalid_body_is_422_invalid_request_without_echo(api, body):
    response = post(api, body)
    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "INVALID_REQUEST" and payload["details"]
    assert all(set(detail) == {"loc", "msg", "type"} for detail in payload["details"])
    assert (api.source.calls, api.generator.calls) == (0, 0)


def test_non_json_body_is_422(api):
    response = api.client.post("/api/v1/ask", content=b"not json", headers={**api.auth,
                                                                         "Content-Type": "application/json"})
    assert response.status_code == 422 and response.json()["error_code"] == "INVALID_REQUEST"


def test_too_long_query_is_rejected_before_pipeline(make_api):
    api = make_api(max_query_chars=50)
    response = post(api, {"query": "kết hôn " * 20})
    assert response.status_code == 422 and response.json()["details"][0]["type"] == "string_too_long"
    assert api.source.calls == 0


@pytest.mark.parametrize("path", ["/api/v1/ask", "/api/v1/ask/stream"])
@pytest.mark.parametrize(("query", "status"), [("x" * 2000, 200), ("x" * 2001, 422), (123, 422)])
def test_query_validation_at_default_limit(api, path, query, status):
    response = api.client.post(path, json={"query": query}, headers=api.auth)
    assert response.status_code == status
    if status == 422:
        body = response.json()
        assert body["error_code"] == "INVALID_REQUEST" and body["details"]
        assert body["query_id"] == response.headers["X-Query-ID"]
        assert [(e.stage, e.event_type, e.query_id) for e in api.sink.events] == [
            ("api", "request_rejected", body["query_id"])]
        assert (api.source.calls, api.generator.calls) == (0, 0)
    else:
        assert any(e.stage == "router" for e in api.sink.events)


@pytest.mark.parametrize("path", ["/api/v1/ask", "/api/v1/ask/stream"])
def test_unicode_query_id_is_transportable_in_response_headers(api, path):
    from urllib.parse import unquote

    query_id = "yêu-cầu%01"
    response = api.client.post(path, json={"query": LEGAL, "query_id": query_id}, headers=api.auth)
    assert response.status_code == 200
    assert unquote(response.headers["X-Query-ID"]) == query_id
    assert all(e.query_id == query_id for e in api.sink.events)


def test_response_has_no_prompt_or_trace(api):
    body = post(api, {"query": LEGAL}).json()
    assert set(body) == set(AskResponse.model_fields)
    text = json.dumps(body, ensure_ascii=False)
    for marker in ("retrieval_trace", "answer_before_gate", "raw_response", "prompt_sha256", "NGUYÊN TẮC ĐÓNG NGỮ CẢNH"):
        assert marker not in text


def test_api_events_wrap_pipeline_events_with_one_query_id(api):
    response = post(api, {"query": LEGAL})
    query_id = response.json()["query_id"]
    stages = [e.stage for e in api.sink.events]
    assert stages[0] == "api" and stages[-1] == "api"
    assert {"router", "retrieval", "rerank", "context", "llm", "citation", "gate", "response"} <= set(stages)
    assert {e.query_id for e in api.sink.events} == {query_id}
    assert api.sink.events[-1].masked_metadata["http_status"] == 200


class _BrokenRouter:
    """Router stand-in: raises ``exc`` or returns a decision without ``action``."""

    def __init__(self, exc=None):
        self.exc = exc

    def route(self, *, query, query_id, as_of_date):
        from schemas.models import RouteDecision

        if self.exc is not None:
            raise self.exc
        return RouteDecision(route="LEGAL_IN_SCOPE", reason_code="R", explanation="e", policy_version="v",
                             query_id=query_id, action=None, as_of_date=as_of_date)


def _invalid_input(reason):
    from agent.router.rule_router import RouteReason, RouterInputError

    return RouterInputError("bad input", reason_code=RouteReason(reason))


@pytest.mark.parametrize(("reason", "field"), [("INVALID_EMPTY_QUERY", "query"), ("INVALID_QUERY_TYPE", "query"),
                                               ("INVALID_AS_OF_DATE", "as_of_date")])
def test_router_input_error_is_422_api_error(api, reason, field):
    api.client.app.state.ask_service.router = _BrokenRouter(_invalid_input(reason))
    response = api.client.post("/api/v1/ask", json={"query": LEGAL}, headers=api.auth)
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"schema_version", "error_code", "message", "query_id", "details"}
    assert body["error_code"] == "INVALID_REQUEST"
    assert body["details"] == [{"loc": ["body", field], "msg": "Router từ chối đầu vào", "type": reason}]
    assert (api.source.calls, api.generator.calls) == (0, 0)


@pytest.mark.parametrize("router", [_BrokenRouter(), _BrokenRouter(RuntimeError("secret detail"))])
def test_router_failure_or_missing_action_is_500_api_error(api, router):
    api.client.app.state.ask_service.router = router
    response = api.client.post("/api/v1/ask", json={"query": LEGAL}, headers=api.auth)
    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "INTERNAL_ERROR" and "secret detail" not in response.text
    assert body["query_id"] == response.headers["X-Query-ID"]
    assert api.source.calls == 0
    assert [e.event_type for e in api.sink.events if e.error_code] == ["route_failed", "request_rejected"]
