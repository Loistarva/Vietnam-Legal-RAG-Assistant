"""Tests for QwenGateway structured output hardening, fence stripping, range checks, and error codes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import requests
import yaml
from pydantic import ValidationError

from generation.prompt_builder import PROMPT_B_VERSION
from model_gateway.llm_gateway import (
    DEFAULT_CONFIG_PATH,
    REQUIRED_CONFIG_KEYS,
    GatewayExecutionError,
    QwenGateway,
    QwenGatewayConfig,
    summarize_truncation_and_provenance,
)
from schemas.models import SCHEMA_VERSION, LLMResponse

ROOT = Path(__file__).resolve().parents[2]


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


@pytest.mark.req("FR6.1")
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


@pytest.mark.req("FR5.2-AC3")
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


@pytest.mark.req("FR5.2-AC3")
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


@pytest.mark.req("FR5.2")
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


@pytest.mark.req("FR5.2")
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


@pytest.mark.req("FR6.4")
def test_gateway_error_codes_for_timeout_unavailable_and_internal_error():
    def timeout_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        raise requests.ReadTimeout("Read timed out after 120s")

    gw_timeout = QwenGateway({"max_retries": 0}, transport=timeout_transport)
    with pytest.raises(GatewayExecutionError) as exc_timeout:
        gw_timeout.generate("P", "q_t", "C_production_rag", PROMPT_B_VERSION, structured_output=True)
    assert exc_timeout.value.error_code == "LLM_TIMEOUT"
    assert exc_timeout.value.retryable is True

    def conn_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        raise ConnectionError("Connection refused")

    gw_conn = QwenGateway({"max_retries": 0}, transport=conn_transport)
    with pytest.raises(GatewayExecutionError) as exc_conn:
        gw_conn.generate("P", "q_c", "C_production_rag", PROMPT_B_VERSION, structured_output=True)
    assert exc_conn.value.error_code == "LLM_UNAVAILABLE"
    assert exc_conn.value.retryable is True

    def http_503_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        resp = requests.Response()
        resp.status_code = 503
        raise requests.HTTPError("Service Unavailable", response=resp)

    gw_503 = QwenGateway({"max_retries": 0}, transport=http_503_transport)
    with pytest.raises(GatewayExecutionError) as exc_503:
        gw_503.generate("P", "q_503", "C_production_rag", PROMPT_B_VERSION, structured_output=True)
    assert exc_503.value.error_code == "LLM_UNAVAILABLE"
    assert exc_503.value.retryable is True

    gw_mismatch = _make_gateway("OK", model="qwen2.5:14b")
    with pytest.raises(GatewayExecutionError) as exc_mismatch:
        gw_mismatch.generate("P", "q_m", "A_zero_shot", "v1.1_zero_shot")
    assert exc_mismatch.value.error_code == "INTERNAL_ERROR"
    assert exc_mismatch.value.retryable is False


@pytest.mark.req("FR6.6")
@pytest.mark.req("FR6.6-AC2")
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


@pytest.mark.req("FR6.4")
def test_llm_response_enforces_canonical_error_code_and_schema_version():
    from pydantic import ValidationError

    valid = LLMResponse(
        query_id="q_ok",
        run_mode="C_production_rag",
        answer="",
        prompt_version=PROMPT_B_VERSION,
        done_reason="stop",
        error_code="GROUNDING_FAIL",
    )
    assert valid.error_code == "GROUNDING_FAIL" and valid.schema_version == SCHEMA_VERSION

    with pytest.raises(ValidationError):
        LLMResponse(
            query_id="q_old_code",
            run_mode="C_production_rag",
            answer="",
            prompt_version=PROMPT_B_VERSION,
            done_reason="stop",
            error_code="GATE_FAIL",  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError):
        LLMResponse(
            query_id="q_bad_ver",
            run_mode="C_production_rag",
            answer="",
            prompt_version=PROMPT_B_VERSION,
            done_reason="stop",
            schema_version="week10_v99",  # type: ignore[arg-type]
        )


@pytest.mark.req("FR6.2")
@pytest.mark.req("FR6.2-AC1")
@pytest.mark.parametrize("missing_key", list(REQUIRED_CONFIG_KEYS))
def test_gateway_yaml_missing_required_key_raises_error(tmp_path: Path, missing_key: str):
    cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    assert REQUIRED_CONFIG_KEYS <= tuple(cfg.keys()) or set(REQUIRED_CONFIG_KEYS) <= set(cfg.keys())
    cfg.pop(missing_key)
    bad_path = tmp_path / "incomplete_qwen.yaml"
    bad_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    with pytest.raises(GatewayExecutionError, match=missing_key):
        QwenGateway(bad_path)


@pytest.mark.req("FR6.2")
@pytest.mark.parametrize(
    "bad_override",
    [
        {"fallback_locked": False},
        {"cache_enabled": True},
        {"provider": "openai"},
        {"base_url": "not-a-url"},
        {"model": "   "},
        {"num_ctx": True},
        {"num_ctx": 0},
        {"timeout_seconds": -1},
        {"unknown_extra_key": "nope"},
    ],
)
def test_gateway_rejects_invalid_config_values_and_types(bad_override: dict[str, Any]):
    with pytest.raises((GatewayExecutionError, ValidationError, ValueError)):
        QwenGateway(bad_override, transport=lambda url, payload, timeout: {})


@pytest.mark.req("FR6.1")
@pytest.mark.req("FR6.8")
def test_gateway_propagates_missing_facts_and_core_modules_never_call_ollama_directly():
    payload = {
        "answer": "Cần thêm thông tin ngày kết hôn.",
        "evidence_indices": [1],
        "abstained": False,
        "needs_clarification": True,
        "missing_facts": ["ngay_su_kien"],
    }
    gateway = _make_gateway(json.dumps(payload))
    resp = gateway.generate(
        prompt="Prompt v1.3",
        query_id="q_v13",
        run_mode="C_production_rag",
        prompt_version="v1.3_controlled_rag",
        structured_output=True,
        max_evidence_index=1,
    )
    assert resp.parse_status == "ok" and resp.error_code is None
    assert resp.missing_facts == ["ngay_su_kien"]
    assert resp.ollama_version is None and resp.model_digest is None

    for pkg in ("orchestration", "evaluation", "agent", "retrieval", "reranking", "grounding", "generation"):
        for py_file in (ROOT / pkg).rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            assert "/api/generate" not in text and "11434" not in text, str(py_file)


@pytest.mark.req("FR6.2")
def test_qwen_gateway_config_defaults_load_config_version():
    cfg = QwenGateway.load_config(DEFAULT_CONFIG_PATH)
    assert cfg.config_version == "local_qwen_v1.1"
    assert QwenGatewayConfig().config_version == "local_qwen_v1.1"


@pytest.mark.req("FR6.2")
@pytest.mark.req("NFR4.1")
@pytest.mark.parametrize("field", ["temperature", "repeat_penalty", "timeout_seconds"])
@pytest.mark.parametrize("bad_num", [float("nan"), float("inf"), float("-inf")])
def test_gateway_config_rejects_non_finite_floats(field: str, bad_num: float):
    with pytest.raises((ValidationError, ValueError)):
        QwenGatewayConfig(**{field: bad_num})
    with pytest.raises((GatewayExecutionError, ValidationError, ValueError)):
        QwenGateway({field: bad_num}, transport=lambda url, payload, timeout: {})


@pytest.mark.req("FR4.4")
def test_gateway_enforces_missing_facts_closed_taxonomy_for_v1_3_only():
    from generation.prompt_builder import MISSING_FACTS_TAXONOMY, PROMPT_A_VERSION, PROMPT_B_V1_3_VERSION

    valid_code = MISSING_FACTS_TAXONOMY[0]
    ok_payload = json.dumps(
        {
            "answer": "Cần thêm mốc thời gian [1].",
            "evidence_indices": [1],
            "abstained": False,
            "needs_clarification": True,
            "missing_facts": [valid_code],
        }
    )
    resp_ok = _make_gateway(ok_payload).generate(
        prompt="Prompt v1.3",
        query_id="q_v13_ok",
        run_mode="C_production_rag",
        prompt_version=PROMPT_B_V1_3_VERSION,
        structured_output=True,
        max_evidence_index=1,
    )
    assert resp_ok.parse_status == "ok"
    assert resp_ok.error_code is None
    assert resp_ok.missing_facts == [valid_code]

    bad_payload = json.dumps(
        {
            "answer": "Thiếu thông tin.",
            "evidence_indices": [1],
            "abstained": False,
            "needs_clarification": True,
            "missing_facts": ["MA_KHONG_HOP_LE"],
        }
    )
    resp_bad = _make_gateway(bad_payload).generate(
        prompt="Prompt v1.3",
        query_id="q_v13_bad",
        run_mode="C_production_rag",
        prompt_version=PROMPT_B_V1_3_VERSION,
        structured_output=True,
        max_evidence_index=1,
    )
    assert resp_bad.parse_status == "invalid_json"
    assert resp_bad.error_code == "JSON_INVALID"
    assert resp_bad.answer == ""
    assert resp_bad.missing_facts == []

    # Tương thích ngược với v1.2 (v1.2_controlled_rag & v1.2_zero_shot)
    resp_v12_rag = _make_gateway(bad_payload).generate(
        prompt="Prompt v1.2",
        query_id="q_v12_rag",
        run_mode="B_controlled_rag",
        prompt_version=PROMPT_B_VERSION,
        structured_output=True,
        max_evidence_index=1,
    )
    assert resp_v12_rag.parse_status == "ok"
    assert resp_v12_rag.error_code is None

    resp_v12_zs = _make_gateway("Nam đủ 20 tuổi.").generate(
        prompt="Prompt v1.2 zero-shot",
        query_id="q_v12_zs",
        run_mode="A_zero_shot",
        prompt_version=PROMPT_A_VERSION,
        structured_output=False,
    )
    assert resp_v12_zs.parse_status == "raw_text"
    assert resp_v12_zs.error_code is None
