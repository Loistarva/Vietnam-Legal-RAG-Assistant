"""Tests for QwenGateway structured output hardening, fence stripping, range checks, and error codes."""
from __future__ import annotations

import json
from typing import Any

import pytest
import requests

from generation.prompt_builder import PROMPT_B_VERSION
from model_gateway.llm_gateway import (
    GatewayExecutionError,
    QwenGateway,
    summarize_truncation_and_provenance,
)
from schemas.models import SCHEMA_VERSION


def _make_gateway(response_text: str, **payload_overrides: Any) -> QwenGateway:
    def transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        body = {
            "model": "qwen2.5:7b",
            "response": response_text,
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 210,
            "eval_count": 45,
        }
        body.update(payload_overrides)
        return body

    return QwenGateway(transport=transport)


@pytest.mark.parametrize(
    "raw_response",
    [
        '```json\n{"answer": "Theo [1], nam đủ 20 tuổi.", "evidence_indices": [1], "abstained": false}\n```',
        '```\n{"answer": "Theo [1], nam đủ 20 tuổi.", "evidence_indices": [1], "abstained": false}\n```',
        '   ```json  {"answer": "Theo [1], nam đủ 20 tuổi.", "evidence_indices": [1], "abstained": false}```   ',
    ],
)
def test_gateway_strips_markdown_fences_from_structured_output(raw_response: str):
    gateway = _make_gateway(raw_response)
    resp = gateway.generate(
        prompt="Prompt",
        query_id="q_fence",
        run_mode="B_controlled_rag",
        prompt_version=PROMPT_B_VERSION,
        structured_output=True,
        max_evidence_index=3,
    )
    assert resp.parse_status == "ok"
    assert resp.error_code is None
    assert resp.answer == "Theo [1], nam đủ 20 tuổi."
    assert resp.evidence_indices == [1]
    assert resp.schema_version == SCHEMA_VERSION
    assert resp.raw_response_reference is not None
    assert resp.raw_response_reference.startswith("ollama://B_controlled_rag/q_fence#sha256:")


@pytest.mark.parametrize(
    "bad_raw",
    [
        "Đây là câu trả lời văn bản thuần, không phải JSON.",
        "{}",
        json.dumps({"abstained": False, "evidence_indices": [1]}),
        json.dumps({"answer": 12345, "evidence_indices": [1]}),
        json.dumps({"answer": "Hợp lệ", "evidence_indices": [1], "unexpected_extra": "blocked"}),
        json.dumps(["not", "a", "dict"]),
    ],
)
def test_gateway_rejects_invalid_or_unexpected_json_structure(bad_raw: str):
    gateway = _make_gateway(bad_raw)
    resp = gateway.generate(
        prompt="Prompt",
        query_id="q_bad_json",
        run_mode="C_production_rag",
        prompt_version=PROMPT_B_VERSION,
        structured_output=True,
    )
    assert resp.parse_status == "invalid_json"
    assert resp.error_code == "JSON_INVALID"
    assert resp.answer == ""
    assert resp.evidence_indices == []
    assert resp.raw_response == bad_raw
    assert resp.raw_response_reference is not None


def test_gateway_marks_truncated_json_with_json_invalid_error_code():
    truncated_raw = '```json\n{"answer": "Nội dung bị cắt giữa chừng'
    gateway = _make_gateway(truncated_raw, done_reason="length", eval_count=1024)
    resp = gateway.generate(
        prompt="Prompt",
        query_id="q_trunc",
        run_mode="B_controlled_rag",
        prompt_version=PROMPT_B_VERSION,
        structured_output=True,
    )
    assert resp.parse_status == "truncated_json"
    assert resp.truncated is True
    assert resp.error_code == "JSON_INVALID"
    assert resp.answer == ""


def test_gateway_enforces_max_evidence_index_when_provided():
    payload_text = json.dumps(
        {
            "answer": "Theo [1] và [3], không dùng [5].",
            "evidence_indices": [0, 1, 3, 5, "2"],
            "abstained": False,
        }
    )
    gateway = _make_gateway(payload_text)
    resp = gateway.generate(
        prompt="Prompt",
        query_id="q_range",
        run_mode="C_production_rag",
        prompt_version=PROMPT_B_VERSION,
        structured_output=True,
        max_evidence_index=3,
    )
    assert resp.parse_status == "ok"
    assert resp.error_code == "CITATION_INVALID"
    assert resp.evidence_indices == [1, 3]
    assert resp.rejected_evidence_values == ["0", "5", '"2"']


def test_gateway_rejects_all_indices_when_max_evidence_index_is_zero():
    gateway = _make_gateway(json.dumps({"answer": "Không có nguồn.", "evidence_indices": [1], "abstained": False}))
    resp = gateway.generate(
        prompt="Prompt",
        query_id="q_zero_ev",
        run_mode="C_production_rag",
        prompt_version=PROMPT_B_VERSION,
        structured_output=True,
        max_evidence_index=0,
    )
    assert resp.evidence_indices == []
    assert resp.rejected_evidence_values == ["1"]
    assert resp.error_code == "CITATION_INVALID"


def test_gateway_error_codes_for_timeout_and_internal_error():
    def timeout_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        raise requests.ReadTimeout("Read timed out after 120s")

    gw_timeout = QwenGateway({"max_retries": 0}, transport=timeout_transport)
    with pytest.raises(GatewayExecutionError) as exc_timeout:
        gw_timeout.generate("P", "q_t", "C_production_rag", PROMPT_B_VERSION, structured_output=True)
    assert exc_timeout.value.error_code == "LLM_TIMEOUT"

    def conn_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        raise ConnectionError("Connection refused")

    gw_conn = QwenGateway({"max_retries": 0}, transport=conn_transport)
    with pytest.raises(GatewayExecutionError) as exc_conn:
        gw_conn.generate("P", "q_c", "C_production_rag", PROMPT_B_VERSION, structured_output=True)
    assert exc_conn.value.error_code == "INTERNAL_ERROR"

    gw_mismatch = _make_gateway("OK", model="qwen2.5:14b")
    with pytest.raises(GatewayExecutionError) as exc_mismatch:
        gw_mismatch.generate("P", "q_m", "A_zero_shot", "v1.1_zero_shot")
    assert exc_mismatch.value.error_code == "INTERNAL_ERROR"


def test_gateway_preserves_none_tokens_and_summarizes_safely():
    def no_tokens_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return {
            "model": "qwen2.5:7b",
            "response": json.dumps({"answer": "Đủ căn cứ.", "evidence_indices": [1], "abstained": False}),
            "done": True,
            "done_reason": "stop",
        }

    resp_none = QwenGateway(transport=no_tokens_transport).generate(
        "P", "q_none", "B_controlled_rag", PROMPT_B_VERSION, structured_output=True
    )
    assert resp_none.token_usage.input is None
    assert resp_none.token_usage.output is None
    assert resp_none.context_truncated is False

    resp_zero = _make_gateway(
        json.dumps({"answer": "OK", "evidence_indices": [], "abstained": False}),
        prompt_eval_count=0,
        eval_count=0,
    ).generate("P", "q_zero", "B_controlled_rag", PROMPT_B_VERSION, structured_output=True)
    assert resp_zero.token_usage.input == 0
    assert resp_zero.token_usage.output == 0

    summary = summarize_truncation_and_provenance([resp_none, resp_zero])
    assert summary["total_queries"] == 2
    assert summary["total_input_tokens"] == 0
    assert summary["total_output_tokens"] == 0
