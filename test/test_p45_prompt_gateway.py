"""P45-1/P45-2/P45-3 (review PR #45, Run B 10/11): language rule in Prompt A/B, repeat_penalty 1.0,
Ollama durations kept by the gateway."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from generation.prompt_builder import (
    LANGUAGE_RULE_A,
    LANGUAGE_RULE_B,
    PROMPT_A_VERSION,
    PROMPT_B_VERSION,
    build_controlled_rag_prompt,
    build_zero_shot_prompt,
)
from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH, QwenGateway, QwenGatewayConfig, ollama_durations_ms
from schemas.models import ContextPayload, EvidenceItem, LLMResponse

ROOT = Path(__file__).resolve().parents[1]
DURATIONS_NS = {"load_duration": 12_345_678_901, "prompt_eval_duration": 1_500_000_000,
                "eval_duration": 8_250_000_000, "total_duration": 22_100_000_000}
DURATION_KEYS = ("load_duration_ms", "prompt_eval_duration_ms", "eval_duration_ms", "total_duration_ms",
                 "ttft_model_ms")


def _payload() -> ContextPayload:
    item = EvidenceItem(evidence_index=1, chunk_id="l_52_art_8_clause_1_chunk_1", parent_clause_id="c",
                        document_id="l_52", document_title="Luật Hôn nhân và gia đình 2014",
                        document_number="52/2014/QH13", article_id="art_8", clause_id="clause_1",
                        breadcrumb="Điều 8 Khoản 1", content="Nam từ đủ 20 tuổi trở lên.",
                        validity_status="Còn hiệu lực", effective_from="2015-01-01", effective_to=None)
    return ContextPayload(query_id="HN_001", query="Tuổi kết hôn?", as_of_date="2026-10-15",
                          as_of_date_source="benchmark", evidence_items=[item])


# ---------------------------------------------------------------------------
# P45-1
# ---------------------------------------------------------------------------
def test_versions_moved_off_the_m1_names():
    assert PROMPT_B_VERSION == "v1.1_controlled_rag" and PROMPT_A_VERSION == "v1.1_zero_shot"


def test_prompt_b_has_rule_6_before_output_section():
    prompt = build_controlled_rag_prompt(_payload())
    rule = f"6. {LANGUAGE_RULE_B}"
    assert rule in prompt
    assert prompt.index("5. Luôn đính kèm") < prompt.index(rule) < prompt.index("YÊU CẦU ĐẦU RA:")
    assert 'Trường "answer" phải viết hoàn toàn bằng tiếng Việt' in prompt
    assert "không viện dẫn pháp luật nước ngoài" in prompt
    assert f"Phiên bản hướng dẫn: {PROMPT_B_VERSION}" in prompt


def test_prompt_a_has_rule_5_before_question():
    prompt = build_zero_shot_prompt("Tuổi kết hôn?", "2026-10-15")
    assert f"5. {LANGUAGE_RULE_A}" in prompt
    assert prompt.index("4. Cuối câu trả lời") < prompt.index("5. NGÔN NGỮ") < prompt.index("CÂU HỎI:")
    assert f"Phiên bản hướng dẫn: {PROMPT_A_VERSION}" in prompt


def test_prompt_spec_documents_the_new_versions_and_change_log():
    spec = (ROOT / "generation" / "prompts" / "legal_rag_prompt_v1_0.md").read_text(encoding="utf-8")
    assert f"`{PROMPT_A_VERSION}`" in spec and f"`{PROMPT_B_VERSION}`" in spec
    assert "NGÔN NGỮ VÀ NGUỒN LUẬT" in spec
    assert "HN_025" in spec and "HN_062" in spec


# ---------------------------------------------------------------------------
# P45-2
# ---------------------------------------------------------------------------
def test_repeat_penalty_is_one_in_config_code_and_schema():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["repeat_penalty"] == 1.0
    assert QwenGatewayConfig().repeat_penalty == 1.0
    assert LLMResponse.model_fields["repeat_penalty"].default == 1.0


def test_gateway_sends_repeat_penalty_one():
    sent = []

    def transport(url, payload, timeout):
        sent.append(payload)
        return {"model": "qwen2.5:7b", "response": "Có.", "done": True, "done_reason": "stop"}

    QwenGateway(transport=transport).generate("P", "q", "A_zero_shot", PROMPT_A_VERSION)
    assert sent[0]["options"]["repeat_penalty"] == 1.0


# ---------------------------------------------------------------------------
# P45-3
# ---------------------------------------------------------------------------
def test_durations_are_converted_to_ms():
    assert ollama_durations_ms(DURATIONS_NS) == {
        "load_duration_ms": 12345.68, "prompt_eval_duration_ms": 1500.0, "eval_duration_ms": 8250.0,
        "total_duration_ms": 22100.0, "ttft_model_ms": 13845.68}


@pytest.mark.parametrize("raw", [{}, {"load_duration": None, "prompt_eval_duration": "12"},
                                 {"load_duration": -1, "prompt_eval_duration": True}])
def test_missing_or_bad_durations_are_null_not_zero(raw):
    assert all(v is None for v in ollama_durations_ms(raw).values())


def test_ttft_needs_both_load_and_prompt_eval():
    out = ollama_durations_ms({"prompt_eval_duration": 1_000_000, "eval_duration": 2_000_000})
    assert out["prompt_eval_duration_ms"] == 1.0 and out["eval_duration_ms"] == 2.0
    assert out["load_duration_ms"] is None and out["ttft_model_ms"] is None


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("with_durations", [True, False])
def test_gateway_keeps_durations_for_run_a_and_run_b(structured, with_durations):
    body = {"answer": "Theo [1], có.", "evidence_indices": [1], "abstained": False,
            "abstention_reason": None, "needs_clarification": False}

    def transport(url, payload, timeout):
        reply = {"model": "qwen2.5:7b", "response": json.dumps(body) if structured else "Có.", "done": True,
                 "done_reason": "stop", "prompt_eval_count": 100, "eval_count": 10}
        return {**reply, **(DURATIONS_NS if with_durations else {})}

    resp = QwenGateway(transport=transport).generate(
        "P", "q", "B_controlled_rag" if structured else "A_zero_shot",
        PROMPT_B_VERSION if structured else PROMPT_A_VERSION, structured_output=structured)
    values = [getattr(resp, key) for key in DURATION_KEYS]
    if with_durations:
        assert values == [12345.68, 1500.0, 8250.0, 22100.0, 13845.68]
    else:
        assert values == [None] * 5
