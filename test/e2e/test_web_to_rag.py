"""End-to-end through the HTTP API (Sprint 10 D5.7), the way the Web UI calls it.

Real: FastAPI app + API Key Guard, Dev 4's RuleRouter, the shared RAGPipeline (confidence
filter, context builder, Prompt B, Grounding Gate with Dev 1's validator), Dev 3's
QwenGateway parsing. Replaced: retrieval (fixture candidates) and the Ollama HTTP call
(``transport``). The live run with Elasticsearch/Qdrant/Ollama is in reports/week10/e2e_report.md.
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import ApiSettings
from model_gateway.llm_gateway import QwenGateway
from orchestration.ask_service import AskService, RuleRouterAdapter
from orchestration.events import JsonlEventSink
from orchestration.fakes import FixtureSource, build_mock_pipeline

KEY = "e2e-key-0123456789abcdef"
LEGAL = "Nam phải đủ bao nhiêu tuổi để kết hôn?"
GROUNDED = "Theo căn cứ [1], nam từ đủ 20 tuổi trở lên mới được kết hôn."


class OllamaStub:
    """Stands in for POST /api/generate; ``reply`` is the model's JSON body or an exception."""

    def __init__(self):
        self.reply: dict | Exception = {"answer": GROUNDED, "evidence_indices": [1], "abstained": False,
                                        "abstention_reason": None, "needs_clarification": False}
        self.calls = 0
        self.done_reason = "stop"

    def __call__(self, url, payload, timeout):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return {"model": "qwen2.5:7b", "response": json.dumps(self.reply, ensure_ascii=False), "done": True,
                "done_reason": self.done_reason, "prompt_eval_count": 900, "eval_count": 40,
                "total_duration": 2_000_000_000, "load_duration": 100_000_000,
                "prompt_eval_duration": 900_000_000, "eval_duration": 1_000_000_000}


@pytest.fixture
def e2e(tmp_path):
    stub, source = OllamaStub(), FixtureSource()
    gateway = QwenGateway(config={"max_retries": 0, "timeout_seconds": 5}, transport=stub)
    log_path = tmp_path / "events.jsonl"
    service = AskService(RuleRouterAdapter(), build_mock_pipeline(generator=gateway, source=source),
                         sink=JsonlEventSink(log_path), today=lambda: date(2026, 11, 16))
    client = TestClient(create_app(settings=ApiSettings(api_keys=KEY), service=service))

    class E2E:
        pass

    env = E2E()
    env.stub, env.source, env.client, env.log_path = stub, source, client, log_path

    def ask(query, **extra):
        response = client.post("/api/v1/ask", json={"query": query, **extra}, headers={"X-API-Key": KEY})
        return response.status_code, response.json()

    def events(query_id):
        rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        return [row for row in rows if row["query_id"] == query_id]

    env.ask, env.events = ask, events
    return env


def test_legal_question_goes_through_every_stage_and_returns_verified_answer(e2e):
    status, body = e2e.ask(LEGAL)
    assert status == 200
    assert (body["status"], body["route"], body["grounding_status"]) == ("SUCCESS", "LEGAL_IN_SCOPE", "PASS")
    assert body["answer"] == GROUNDED
    assert [c["evidence_index"] for c in body["citations"]] == [1]
    assert body["evidence"][0]["chunk_id"] == body["citations"][0]["chunk_id"]
    assert body["timings"]["llm_total_ms"] is not None and body["timings"]["ttft_model_ms"] == 1000.0
    stages = [row["stage"] for row in e2e.events(body["query_id"])]
    assert stages == ["api", "router", "retrieval", "retrieval", "rerank", "context", "llm", "llm", "citation", "gate",
                      "response", "api"]
    assert (e2e.source.calls, e2e.stub.calls) == (1, 1)


def test_non_legal_fast_path_calls_neither_retrieval_nor_llm(e2e):
    status, body = e2e.ask("Hôm nay thời tiết Hà Nội thế nào?")
    assert status == 200 and (body["status"], body["route"], body["grounding_status"]) == ("SUCCESS", "NON_LEGAL",
                                                                                           "NOT_RUN")
    assert (e2e.source.calls, e2e.stub.calls) == (0, 0)
    assert [row["stage"] for row in e2e.events(body["query_id"])] == ["api", "router", "response", "api"]


def test_out_of_scope_legal_question_gets_policy_abstention(e2e):
    status, body = e2e.ask("Thủ tục thành lập doanh nghiệp tư nhân thế nào?")
    assert status == 200
    assert (body["status"], body["route"], body["error_code"]) == ("ABSTAIN", "LEGAL_OUT_OF_SCOPE", "ROUTE_POLICY")
    assert body["answer"] is None and "Hôn nhân và gia đình" in body["abstention_message"]
    assert (e2e.source.calls, e2e.stub.calls) == (0, 0)


@pytest.mark.parametrize(("marker", "code"), [("[mock:empty]", "RETRIEVAL_EMPTY"), ("[mock:low]", "LOW_CONFIDENCE")])
def test_empty_or_low_confidence_evidence_does_not_call_generation(e2e, marker, code):
    status, body = e2e.ask(f"{LEGAL} {marker}")
    assert status == 200 and (body["status"], body["error_code"]) == ("ABSTAIN", code)
    assert e2e.stub.calls == 0
    stages = [row["stage"] for row in e2e.events(body["query_id"])]
    assert "llm" not in stages and "gate" not in stages


@pytest.mark.parametrize("indices", [[1, 7], [3]])
def test_citation_outside_context_fails_gate_and_hides_draft(e2e, indices):
    draft = "Bản nháp có căn cứ [7] không nằm trong ngữ cảnh."
    e2e.stub.reply = {"answer": draft, "evidence_indices": indices, "abstained": False, "abstention_reason": None,
                      "needs_clarification": False}
    status, body = e2e.ask(LEGAL)
    assert status == 200
    assert (body["status"], body["grounding_status"], body["error_code"]) == ("ABSTAIN", "FAIL", "CITATION_INVALID")
    assert body["answer"] is None and body["citations"] == []
    assert draft not in json.dumps(body, ensure_ascii=False)
    gate = next(row for row in e2e.events(body["query_id"]) if row["stage"] == "gate")
    assert gate["status"] == "FAIL"


def test_inline_marker_outside_context_fails_gate(e2e):
    e2e.stub.reply = {"answer": "Theo [1] và [4].", "evidence_indices": [1], "abstained": False,
                      "abstention_reason": None, "needs_clarification": False}
    _, body = e2e.ask(LEGAL)
    assert (body["grounding_status"], body["abstention_reason"]) == ("FAIL", "ANSWER_MARKER_OUTSIDE_CONTEXT")


def test_truncated_generation_with_parseable_json_is_withheld(e2e):
    e2e.stub.done_reason = "length"
    status, body = e2e.ask(LEGAL)
    assert status == 200
    assert (body["status"], body["grounding_status"], body["error_code"]) == ("ABSTAIN", "FAIL", "JSON_INVALID")
    assert body["answer"] is None


def test_llm_timeout_returns_typed_error(e2e):
    e2e.stub.reply = TimeoutError("read timed out")
    status, body = e2e.ask(LEGAL)
    assert status == 504 and (body["status"], body["error_code"]) == ("ERROR", "LLM_TIMEOUT")
    assert "timed out" not in json.dumps(body)
    rows = e2e.events(body["query_id"])
    failed = next(row for row in rows if row["event_type"] == "generation_failed")
    assert (failed["stage"], failed["error_code"]) == ("llm", "LLM_TIMEOUT")
    response = next(row for row in rows if row["event_type"] == "response_built")
    assert response["masked_metadata"]["llm_calls"] == 1


def test_logs_follow_one_query_id_and_contain_no_question_or_key(e2e):
    _, body = e2e.ask(LEGAL, request_id="ui-req-7", session_id="sess-1")
    rows = e2e.events(body["query_id"])
    assert rows and {row["query_id"] for row in rows} == {body["query_id"]}
    assert len({row["event_id"] for row in rows}) == len(rows)
    text = e2e.log_path.read_text(encoding="utf-8")
    assert LEGAL not in text and GROUNDED not in text and KEY not in text
    assert rows[0]["masked_metadata"] == {"request_id": "ui-req-7", "session_id": "sess-1"}
