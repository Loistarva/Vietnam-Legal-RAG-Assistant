"""Public HTTP outcomes (SRS 5.3.4) and detail-code groups (SRS 5.3.5)."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from api.errors import ApiError
from generation.prompt_builder import STANDARD_DISCLAIMER
from orchestration.clarification import load_clarification_catalog
from orchestration.fakes import build_mock_pipeline
from orchestration.response_builder import gate_fail_error_code, rag_fields
from schemas.models import AskResponse

pytestmark = pytest.mark.req("IR2.5-AC1")
LEGAL = "Nam phải đủ bao nhiêu tuổi để kết hôn?"
PATH = "/api/v1/ask"


def assert_ask_row(api, query, status, grounding, code, http=200):
    response = api.client.post(PATH, json={"query": query}, headers=api.auth)
    assert response.status_code == http
    body = AskResponse.model_validate(response.json())
    assert (body.status, body.grounding_status, body.error_code) == (status, grounding, code)
    assert body.disclaimer == STANDARD_DISCLAIMER
    assert response.text.count(STANDARD_DISCLAIMER) == 1
    return body, response.text


@pytest.mark.req("FR5.8-AC1")
@pytest.mark.parametrize(("query", "route", "status", "grounding", "code"), [
    pytest.param(LEGAL, "LEGAL_IN_SCOPE", "SUCCESS", "PASS", None,
                 id="grounded", marks=pytest.mark.req("FR5.4-AC1")),
    pytest.param("Hôm nay thời tiết Hà Nội thế nào?", "NON_LEGAL", "SUCCESS", "NOT_RUN", None,
                 id="non-legal", marks=pytest.mark.req("FR1.2-AC1")),
    pytest.param("Thủ tục thành lập doanh nghiệp tư nhân thế nào?", "LEGAL_OUT_OF_SCOPE", "ABSTAIN",
                 "NOT_RUN", "ROUTE_POLICY", id="out-of-scope", marks=pytest.mark.req("FR1.4-AC1")),
    pytest.param("Tôi muốn ly hôn và thành lập doanh nghiệp tư nhân thì cần thủ tục gì?", "MIXED_REVIEW",
                 "ABSTAIN", "NOT_RUN", "ROUTE_POLICY", id="mixed", marks=pytest.mark.req("FR1.4-AC1")),
    pytest.param(f"{LEGAL} [mock:empty]", "LEGAL_IN_SCOPE", "ABSTAIN", "NOT_RUN", "RETRIEVAL_EMPTY",
                 id="empty", marks=pytest.mark.req("FR3.3-AC2")),
    pytest.param(f"{LEGAL} [mock:low]", "LEGAL_IN_SCOPE", "ABSTAIN", "NOT_RUN", "LOW_CONFIDENCE",
                 id="low-confidence", marks=pytest.mark.req("FR3.1-AC2")),
])
def test_route_and_retrieval_rows(api, query, route, status, grounding, code):
    body, _ = assert_ask_row(api, query, status, grounding, code)
    assert body.route == route
    if status == "ABSTAIN":
        assert body.abstention_reason and body.answer is None


@pytest.mark.req("FR3.4-AC1")
def test_missing_facts_clarification():
    pytest.skip("đo trên tập câu âm v2 (S12-D1.2)")


@pytest.mark.req("FR3.4")
@pytest.mark.req("FR3.4-AC3")
@pytest.mark.req("FR3.4-AC4")
def test_api_clarification_returns_fixed_questions(api):
    path = Path(__file__).parents[1] / "fixtures/sprint12/clarification_catalog_test.yaml"
    api.client.app.state.ask_service.clarification_catalog = load_clarification_catalog(path)
    body, text = assert_ask_row(api, f"{LEGAL} [mock:clarify_facts]", "NEEDS_CLARIFICATION", "NEEDS_CLARIFICATION", None)
    assert body.answer is None and body.citations == []
    assert body.clarification.splitlines()[1:] == ["- Sự kiện xảy ra vào ngày nào?", "- Hai bên đã đăng ký kết hôn chưa?"]
    assert "ma_la" not in text


@pytest.mark.req("FR5.8-AC1")
@pytest.mark.req("FR5.7")
@pytest.mark.parametrize(("marker", "status", "grounding", "code", "reason"), [
    pytest.param("abstain", "ABSTAIN", "ABSTAIN", None, "MODEL_ABSTAINED", marks=pytest.mark.req("FR5.2")),
    pytest.param("clarify", "NEEDS_CLARIFICATION", "NEEDS_CLARIFICATION", None, None,
                 marks=pytest.mark.req("FR3.6-AC1")),
    pytest.param("bad_json", "ABSTAIN", "FAIL", "JSON_INVALID", "LLM_OUTPUT_INVALID_JSON",
                 marks=pytest.mark.req("FR5.2-AC3")),
    pytest.param("gate_fail", "ABSTAIN", "FAIL", "CITATION_INVALID", "EVIDENCE_INDEX_OUTSIDE_CONTEXT",
                 marks=pytest.mark.req("FR5.2-AC1")),
    pytest.param("context_truncated", "ABSTAIN", "FAIL", "GROUNDING_FAIL", "PROMPT_CONTEXT_TRUNCATED",
                 marks=pytest.mark.req("FR5.5-AC1")),
])
def test_gate_rows_hide_model_draft(api, monkeypatch, marker, status, grounding, code, reason):
    generate = api.generator.generate
    draft = "Bản nháp riêng của mô hình."

    def generate_with_draft(*args, **kwargs):
        llm = generate(*args, **kwargs)
        return llm.model_copy(update={"answer": draft, "context_truncated": marker == "context_truncated"})

    monkeypatch.setattr(api.generator, "generate", generate_with_draft)
    body, text = assert_ask_row(api, f"{LEGAL} [mock:{marker}]", status, grounding, code)
    assert body.abstention_reason == reason
    assert body.answer is None
    assert draft not in text


@pytest.mark.req("FR5.8-AC1")
@pytest.mark.parametrize(("marker", "code", "http", "retryable"), [
    pytest.param("timeout", "LLM_TIMEOUT", 504, True, marks=pytest.mark.req("FR6.4-AC1")),
    pytest.param("unavailable", "LLM_UNAVAILABLE", 503, True, marks=pytest.mark.req("FR6.4-AC1")),
    pytest.param("internal", "INTERNAL_ERROR", 500, False, marks=pytest.mark.req("FR5.7")),
])
def test_pipeline_error_rows(api, monkeypatch, marker, code, http, retryable):
    if marker == "internal":
        monkeypatch.setattr(api.source, "fetch", Mock(side_effect=RuntimeError("failed")))
    body, _ = assert_ask_row(api, f"{LEGAL} [mock:{marker}]", "ERROR", "NOT_RUN", code, http)
    assert body.error.retryable is retryable


@pytest.mark.parametrize(("case", "http", "code"), [
    pytest.param("missing-key", 401, "AUTH_REQUIRED", marks=pytest.mark.req("IR2.2-AC1")),
    pytest.param("wrong-key", 401, "AUTH_REQUIRED", marks=pytest.mark.req("IR2.2-AC1")),
    pytest.param("bad-body", 422, "INVALID_REQUEST", marks=pytest.mark.req("IR2.1-AC2")),
    pytest.param("long-query", 422, "INVALID_REQUEST", marks=pytest.mark.req("FR1.7-AC1")),
    pytest.param("router-failure", 500, "INTERNAL_ERROR", marks=pytest.mark.req("FR1.9")),
])
def test_api_error_rows(make_api, monkeypatch, case, http, code):
    api = make_api(max_query_chars=50)
    headers = {"missing-key": {}, "wrong-key": {"X-API-Key": "wrong"}}.get(case, api.auth)
    request = {"bad-body": {}, "long-query": {"query": "x" * 51}}.get(case, {"query": LEGAL})
    if case == "router-failure":
        router = api.client.app.state.ask_service.router
        monkeypatch.setattr(router, "route", Mock(side_effect=RuntimeError("failed")))
    response = api.client.post(PATH, headers=headers, json=request)
    assert response.status_code == http
    body = response.json()
    assert "detail" not in body
    assert set(body) == set(ApiError.model_fields)
    assert ApiError.model_validate(body).error_code == code


@pytest.mark.req("FR5.2")
@pytest.mark.parametrize(("detail", "code"), [
    ("LLM_OUTPUT_INVALID_JSON", "JSON_INVALID"),
    ("LLM_OUTPUT_TRUNCATED_JSON", "JSON_INVALID"),
    ("LLM_OUTPUT_RAW_TEXT", "JSON_INVALID"),
    ("LLM_OUTPUT_TRUNCATED", "JSON_INVALID"),
    ("NON_INTEGER_EVIDENCE_INDEX", "CITATION_INVALID"),
    ("ANSWER_CONTAINS_CHUNK_ID", "CITATION_INVALID"),
    ("ANSWER_MARKER_OUTSIDE_CONTEXT", "CITATION_INVALID"),
    ("ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES", "CITATION_INVALID"),
    ("CITATION_OUTSIDE_CONTEXT", "CITATION_INVALID"),
    ("INVALID_CITATION_INDEX", "CITATION_INVALID"),
    ("INVALID_EVIDENCE_INDEX", "CITATION_INVALID"),
    ("SOURCE_MAP_MISMATCH", "CITATION_INVALID"),
    ("EMPTY_ANSWER", "GROUNDING_FAIL"),
    ("ANSWER_NOT_VIETNAMESE", "GROUNDING_FAIL"),
    ("PROMPT_CONTEXT_TRUNCATED", "GROUNDING_FAIL"),
    ("SOME_UNKNOWN_CODE", "GROUNDING_FAIL"),
])
def test_gate_detail_code(detail, code):
    assert gate_fail_error_code(detail) == code


@pytest.mark.req("FR5.7")
@pytest.mark.parametrize(("marker", "detail", "grounding", "code"), [
    ("empty", "EMPTY_RETRIEVAL", "NOT_RUN", "RETRIEVAL_EMPTY"),
    ("low", "LOW_CONFIDENCE", "NOT_RUN", "LOW_CONFIDENCE"),
    ("abstain", "MODEL_ABSTAINED", "ABSTAIN", None),
])
def test_rag_abstention_detail(marker, detail, grounding, code):
    as_of_date = "2026-01-01"
    rag = build_mock_pipeline().run(query_id="q-row", query=f"{LEGAL} [mock:{marker}]",
                                    as_of_date=as_of_date, as_of_date_source="user_input")
    fields = rag_fields(rag, as_of_date)
    assert fields["abstention_reason"] == detail
    assert (fields["status"], fields["grounding_status"], fields["error_code"]) == ("ABSTAIN", grounding, code)
