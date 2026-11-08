"""D5.5: only a PASS returns the model answer; every other path returns a policy message."""
from __future__ import annotations

import json

import pytest

from generation.prompt_builder import STANDARD_DISCLAIMER
from model_gateway.llm_gateway import QwenGateway
from orchestration.rag_pipeline import CLARIFY_MESSAGE, FAIL_MESSAGE
from reranking.confidence import ConfidenceConfig

MODEL_TEXT = "Theo [1], nam từ đủ 20 tuổi."


def _three(rag):
    return [rag.make_row(i) for i in (1, 2, 3)]


def test_pass_returns_answer_with_disclaimer_and_citations(rag):
    pipeline, _ = rag.make_pipeline(_three(rag))
    record = rag.run(pipeline).record
    assert record.grounding_status == "PASS"
    assert record.answer == f"{MODEL_TEXT}\n\n{STANDARD_DISCLAIMER}"
    assert [c.evidence_index for c in record.citations] == [1]
    assert record.retrieval_trace["gate"]["reason"] == "CITATIONS_MATCH_SELECTED_CONTEXT"


def test_disclaimer_is_not_duplicated(rag):
    gen = rag.FakeGenerator(answer=f"Theo [1], có. {STANDARD_DISCLAIMER}")
    pipeline, _ = rag.make_pipeline(_three(rag), gen)
    assert rag.run(pipeline).record.answer.count(STANDARD_DISCLAIMER) == 1


@pytest.mark.parametrize("response, reason", [
    ({"evidence_indices": [4]}, "MAPPER_INVALID_INDICES"),
    ({"evidence_indices": [6]}, "MAPPER_INVALID_INDICES"),
    ({"evidence_indices": [1, 1]}, "DUPLICATE_EVIDENCE_INDEX"),
    ({"evidence_indices": [], "answer": "Có."}, "MISSING_CITATIONS"),
    ({"rejected_evidence_values": ['"1"']}, "NON_INTEGER_EVIDENCE_INDEX"),
    ({"parse_status": "invalid_json", "answer": ""}, "LLM_OUTPUT_INVALID_JSON"),
    ({"parse_status": "truncated_json", "truncated": True, "done_reason": "length"}, "LLM_OUTPUT_TRUNCATED_JSON"),
    ({"truncated": True, "done_reason": "length"}, "LLM_OUTPUT_TRUNCATED"),
    ({"context_truncated": True}, "PROMPT_CONTEXT_TRUNCATED"),
    ({"answer": "   "}, "EMPTY_ANSWER"),
    ({"answer": "Theo [1] và [4]."}, "ANSWER_MARKER_OUTSIDE_CONTEXT"),
    ({"answer": "Theo [1] và [2].", "evidence_indices": [1]}, "ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES"),
    ({"query_id": "HN_OTHER"}, "QUERY_ID_MISMATCH"),
])
def test_fail_returns_policy_message_not_model_text(rag, response, reason):
    gen = rag.FakeGenerator(**response)
    pipeline, _ = rag.make_pipeline(_three(rag), gen)
    record = rag.run(pipeline).record
    assert record.grounding_status == "FAIL"
    assert record.retrieval_trace["gate"]["reason"] == reason
    assert record.answer == f"{FAIL_MESSAGE}\n\n{STANDARD_DISCLAIMER}"
    assert record.citations == []


def test_model_abstention_is_policy_abstention(rag):
    gen = rag.FakeGenerator(abstained=True, abstention_reason="Không đủ căn cứ", answer="Tôi nghĩ là có.",
                            evidence_indices=[])
    pipeline, _ = rag.make_pipeline(_three(rag), gen)
    record = rag.run(pipeline, as_of_date="2026-10-15").record
    assert record.grounding_status == "ABSTAIN"
    assert "2026-10-15" in record.answer and "Tôi nghĩ là có" not in record.answer
    assert record.retrieval_trace["llm"]["answer_before_gate"] == "Tôi nghĩ là có."
    assert record.retrieval_trace["llm"]["abstention_reason"] == "Không đủ căn cứ"


def test_needs_clarification(rag):
    gen = rag.FakeGenerator(needs_clarification=True, answer="Bạn kết hôn năm nào?", evidence_indices=[])
    pipeline, _ = rag.make_pipeline(_three(rag), gen)
    record = rag.run(pipeline).record
    assert record.grounding_status == "NEEDS_CLARIFICATION"
    assert record.answer == f"{CLARIFY_MESSAGE}\n\n{STANDARD_DISCLAIMER}"


def test_low_confidence_abstains_without_calling_the_model(rag):
    rows = [rag.make_row(1, score=0.2), rag.make_row(2, score=0.1)]
    confidence = ConfidenceConfig(enabled=True, min_top1_score=0.5, threshold_config_version="t1")
    pipeline, gen = rag.make_pipeline(rows, confidence=confidence)
    record = rag.run(pipeline).record
    assert gen.prompts == []
    assert record.grounding_status == "ABSTAIN"
    assert record.retrieval_trace["gate"]["reason"] == "LOW_CONFIDENCE"
    assert record.threshold_config_version == "t1"


def test_low_scored_tail_is_left_out_of_the_prompt(rag):
    rows = [rag.make_row(1, score=0.9), rag.make_row(2, score=0.6), rag.make_row(3, score=0.05)]
    confidence = ConfidenceConfig(enabled=True, min_top1_score=0.5, min_evidence_score=0.1,
                                  threshold_config_version="t1")
    pipeline, gen = rag.make_pipeline(rows, confidence=confidence)
    result = rag.run(pipeline)
    assert [e.chunk_id for e in result.payload.evidence_items] == [rows[0]["chunk_id"], rows[1]["chunk_id"]]
    assert "từ [1] đến [2]" in gen.prompts[0]
    assert result.record.retrieval_trace["confidence"]["dropped_chunk_ids"] == [rows[2]["chunk_id"]]


def test_gate_with_real_gateway_parsing(rag):
    """Index 6 from a raw Ollama reply survives parsing and is failed by the Gate."""
    def transport(url, payload, timeout):
        body = {"answer": "Theo [1].", "evidence_indices": [1, 6], "abstained": False,
                "abstention_reason": None, "needs_clarification": False}
        return {"model": "qwen2.5:7b", "response": json.dumps(body), "done": True, "done_reason": "stop",
                "prompt_eval_count": 1200, "eval_count": 40}

    pipeline, _ = rag.make_pipeline(_three(rag), QwenGateway(transport=transport))
    record = rag.run(pipeline).record
    assert record.grounding_status == "FAIL"
    assert record.retrieval_trace["gate"]["invalid_indices"] == [6]
    assert record.evidence_indices == [1, 6]
