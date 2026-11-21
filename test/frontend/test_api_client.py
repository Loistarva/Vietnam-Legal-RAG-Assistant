"""Contract-focused tests for the frontend HTTP client."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
import requests

from frontend.api_client import APIResponseError, ask


class FakeResponse:
    def __init__(self, payload, *, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self.payload

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.mark.req("IR1.6-AC1")
@pytest.mark.req("IR2.1-AC1")
def test_ask_sends_contract_fields_and_omits_unselected_date(monkeypatch):
    payload = {"status": "SUCCESS", "answer": "Hello", "disclaimer": "Demo"}
    response = FakeResponse(payload)
    post = Mock(return_value=response)
    monkeypatch.setattr("frontend.api_client.requests.post", post)

    result = ask(
        "Xin chào",
        api_url="http://localhost/api/v1/ask",
        timeout_seconds=12,
    )

    assert result == payload
    post.assert_called_once_with(
        "http://localhost/api/v1/ask",
        json={"query": "Xin chào"},
        headers={"Accept": "application/json, text/event-stream"},
        timeout=12,
        stream=True,
    )


@pytest.mark.req("IR2.2-AC1")
def test_ask_sends_api_key_and_optional_context(monkeypatch):
    post = Mock(return_value=FakeResponse({"status": "SUCCESS"}))
    monkeypatch.setattr("frontend.api_client.requests.post", post)

    ask(
        "Câu hỏi",
        api_url="http://localhost/api/v1/ask",
        api_key="secret-value",
        as_of_date="2026-11-21",
        session_id="session-1",
        request_id="request-1",
    )

    post.assert_called_once_with(
        "http://localhost/api/v1/ask",
        json={
            "query": "Câu hỏi",
            "as_of_date": "2026-11-21",
            "session_id": "session-1",
            "request_id": "request-1",
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "X-API-Key": "secret-value",
        },
        timeout=180,
        stream=True,
    )


@pytest.mark.req("IR1.3-AC2")
def test_ask_preserves_contract_error_response_from_server(monkeypatch):
    payload = {
        "status": "ERROR",
        "error_code": "LLM_TIMEOUT",
        "error": {"message": "Timed out", "retryable": True},
    }
    monkeypatch.setattr(
        "frontend.api_client.requests.post",
        Mock(return_value=FakeResponse(payload, status_code=504)),
    )

    assert ask("Question", api_url="http://localhost/api/v1/ask") == payload


@pytest.mark.req("IR2.2-AC1")
def test_ask_raises_for_auth_or_validation_error(monkeypatch):
    monkeypatch.setattr(
        "frontend.api_client.requests.post",
        Mock(return_value=FakeResponse({"error_code": "AUTH_REQUIRED"}, status_code=401)),
    )

    with pytest.raises(requests.HTTPError):
        ask("Question", api_url="http://localhost/api/v1/ask")


@pytest.mark.req("IR2.1-AC1")
def test_ask_rejects_non_object_json_response(monkeypatch):
    monkeypatch.setattr(
        "frontend.api_client.requests.post", Mock(return_value=FakeResponse([]))
    )

    with pytest.raises(APIResponseError, match="JSON object"):
        ask("Question", api_url="http://localhost/api/v1/ask")


@pytest.mark.req("IR2.4-AC1")
@pytest.mark.req("IR2.4-AC2")
def test_ask_reports_sse_status_and_returns_only_final(monkeypatch):
    final = {"status": "SUCCESS", "answer": "Verified", "disclaimer": "Demo"}
    response = FakeResponse(final)
    response.headers = {"Content-Type": "text/event-stream"}
    response.iter_lines = Mock(
        return_value=iter(
            [
                b"event: status",
                b'data: {"stage":"retrieval","message":"Dang truy xuat"}',
                b"",
                b"event: final",
                f"data: {json.dumps(final)}".encode(),
                b"",
            ]
        )
    )
    post = Mock(return_value=response)
    monkeypatch.setattr("frontend.api_client.requests.post", post)
    statuses = []

    result = ask(
        "Question",
        api_url="http://localhost/api/v1/ask",
        on_status=statuses.append,
    )

    assert result == final
    assert statuses == [{"stage": "retrieval", "message": "Dang truy xuat"}]


@pytest.mark.req("IR1.3-AC2")
def test_ask_propagates_transport_timeout_for_ui_to_handle(monkeypatch):
    post = Mock(side_effect=requests.Timeout("connection timed out"))
    monkeypatch.setattr("frontend.api_client.requests.post", post)

    with pytest.raises(requests.Timeout):
        ask("Question", api_url="http://localhost/api/v1/ask", timeout_seconds=1)

    assert post.call_args.kwargs["timeout"] == 1
