"""POST /api/v1/ask/stream: status first, answer only after the Gate (Sprint 10 D5.5)."""
from __future__ import annotations

import json

import pytest

from orchestration.fakes import MOCK_ANSWER
from schemas.models import SCHEMA_VERSION

LEGAL = "Nam phải đủ bao nhiêu tuổi để kết hôn?"


def read_stream(api, query, **fields):
    events = []
    with api.client.stream("POST", "/api/v1/ask/stream", json={"query": query, **fields}, headers=api.auth) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        query_id = response.headers["X-Query-ID"]
        name = None
        for line in response.iter_lines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                events.append((name, json.loads(line[len("data: "):])))
    return query_id, events


def test_status_events_then_final_response(api):
    query_id, events = read_stream(api, LEGAL)
    names = [name for name, _ in events]
    assert names[:-1] == ["status"] * 6 and names[-1] == "final"
    phases = [data["phase"] for name, data in events if name == "status"]
    assert phases == ["accepted", "routing", "retrieving", "reranking", "generating", "validating"]
    assert all(data["sse_version"] == "sse_v2" for _, data in events[:-1])
    assert events[0][1]["schema_version"] == SCHEMA_VERSION
    final = events[-1][1]
    assert final["status"] == "SUCCESS" and final["answer"] == MOCK_ANSWER and final["query_id"] == query_id
    elapsed = [data["elapsed_ms"] for _, data in events[:-1]]
    assert elapsed == sorted(elapsed)


def test_no_answer_text_before_the_final_event(api):
    _, events = read_stream(api, LEGAL)
    before_final = json.dumps([data for name, data in events if name == "status"], ensure_ascii=False)
    assert MOCK_ANSWER not in before_final and "answer" not in before_final


@pytest.mark.parametrize("query", [
    LEGAL, "Hôm nay thời tiết Hà Nội thế nào?", "Thủ tục thành lập doanh nghiệp tư nhân thế nào?",
    f"{LEGAL} [mock:clarify]", f"{LEGAL} [mock:low]", f"{LEGAL} [mock:gate_fail]", f"{LEGAL} [mock:timeout]",
])
def test_terminal_event_matches_json_endpoint(api, query):
    query_id, events = read_stream(api, query, query_id="stream-1")
    response = api.client.post("/api/v1/ask", json={"query": query, "query_id": query_id}, headers=api.auth).json()
    names = [name for name, _ in events]
    assert set(names[:-1]) == {"status"}
    assert names[-1] == ("error" if response["status"] == "ERROR" else "final")
    terminal = events[-1][1]
    if response["status"] == "ERROR":
        assert terminal["message"] == response["error"]["message"]
        assert terminal["error_code"] == response["error_code"]
        terminal = terminal["response"]
    assert terminal.keys() == response.keys()
    assert {k: v for k, v in terminal.items() if k != "timings"} == {
        k: v for k, v in response.items() if k != "timings"}
    if "[mock:low]" in query:
        assert [data["phase"] for _, data in events[:-1]] == ["accepted", "routing", "retrieving", "reranking"]


def test_gate_fail_stream_never_contains_the_draft(api):
    _, events = read_stream(api, f"{LEGAL} [mock:gate_fail]")
    text = json.dumps(events, ensure_ascii=False)
    assert "Bản nháp" not in text
    assert events[-1][1]["grounding_status"] == "FAIL"


def test_stream_logs_first_status_and_final_separately(api):
    query_id, _ = read_stream(api, LEGAL)
    api_events = [e for e in api.sink.events if e.stage == "api"]
    assert [e.event_type for e in api_events] == ["request_received", "stream_first_status", "stream_final"]
    assert all(e.query_id == query_id for e in api.sink.events)
    first, final = api_events[1], api_events[2]
    assert first.duration_ms is not None and final.duration_ms >= first.duration_ms


def test_router_input_error_ends_stream_with_invalid_request(api):
    from agent.router.rule_router import RouteReason, RouterInputError

    class Rejecting:
        def route(self, *, query, query_id, as_of_date):
            raise RouterInputError("bad", reason_code=RouteReason.INVALID_EMPTY_QUERY)

    api.client.app.state.ask_service.router = Rejecting()
    _, events = read_stream(api, LEGAL)
    name, data = events[-1]
    assert name == "error" and data["error_code"] == "INVALID_REQUEST"
    assert data["details"][0]["type"] == "INVALID_EMPTY_QUERY"
    assert api.source.calls == 0
