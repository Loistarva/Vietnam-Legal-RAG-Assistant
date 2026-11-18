"""POST /api/v1/ask/stream: status first, answer only after the Gate (Sprint 10 D5.5)."""
from __future__ import annotations

import json

import pytest

from orchestration.fakes import MOCK_ANSWER

LEGAL = "Nam phải đủ bao nhiêu tuổi để kết hôn?"


def read_stream(api, query):
    events = []
    with api.client.stream("POST", "/api/v1/ask/stream", json={"query": query}, headers=api.auth) as response:
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


def test_status_events_then_verified_answer_then_done(api):
    query_id, events = read_stream(api, LEGAL)
    names = [name for name, _ in events]
    assert names[0] == "status" and names[-2:] == ["verified_answer", "done"]
    phases = [data["phase"] for name, data in events if name == "status"]
    assert phases == ["accepted", "routing", "retrieving", "reranking", "generating", "validating"]
    assert all(data["sse_version"] == "sse_v1" for _, data in events)
    assert events[0][1]["schema_version"] == "week10_v1.0"
    final = events[-2][1]["response"]
    assert final["status"] == "SUCCESS" and final["answer"] == MOCK_ANSWER and final["query_id"] == query_id
    assert events[-1][1]["status"] == "SUCCESS"
    elapsed = [data["elapsed_ms"] for _, data in events]
    assert elapsed == sorted(elapsed)


def test_no_answer_text_before_the_final_event(api):
    _, events = read_stream(api, LEGAL)
    before_final = json.dumps([data for name, data in events if name == "status"], ensure_ascii=False)
    assert MOCK_ANSWER not in before_final and "answer" not in before_final


@pytest.mark.parametrize(("query", "final"), [
    ("Hôm nay thời tiết Hà Nội thế nào?", "verified_answer"),
    ("Thủ tục thành lập doanh nghiệp tư nhân thế nào?", "abstention"),
    (f"{LEGAL} [mock:clarify]", "clarification"),
    (f"{LEGAL} [mock:gate_fail]", "abstention"),
    (f"{LEGAL} [mock:timeout]", "error"),
])
def test_each_branch_ends_with_one_final_event(api, query, final):
    _, events = read_stream(api, query)
    names = [name for name, _ in events]
    assert names[-1] == "done" and names[-2] == final
    assert sum(name in ("verified_answer", "clarification", "abstention", "error") for name in names) == 1


def test_gate_fail_stream_never_contains_the_draft(api):
    _, events = read_stream(api, f"{LEGAL} [mock:gate_fail]")
    text = json.dumps(events, ensure_ascii=False)
    assert "Bản nháp" not in text
    assert events[-2][1]["response"]["grounding_status"] == "FAIL"


def test_stream_logs_first_status_and_final_separately(api):
    query_id, _ = read_stream(api, LEGAL)
    api_events = [e for e in api.sink.events if e.stage == "api"]
    assert [e.event_type for e in api_events] == ["request_received", "stream_first_status", "stream_final"]
    assert all(e.query_id == query_id for e in api.sink.events)
    first, final = api_events[1], api_events[2]
    assert first.duration_ms is not None and final.duration_ms >= first.duration_ms
