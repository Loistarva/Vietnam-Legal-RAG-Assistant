"""P45-4/P45-5/P45-6 (review PR #45, Run B 10/11): abstention fields on every record,
Gate block on CJK answers, llm_calls and latency_breakdown."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from orchestration.rag_pipeline import FAIL_MESSAGE, LivePipelineSource, apply_grounding_gate, count_cjk_chars
from reranking.confidence import ConfidenceConfig
from schemas.models import LLMResponse, RAGOutputRecord

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RUN_B_CJK = json.loads((FIXTURES / "run_b_20261110_cjk_answers.json").read_text(encoding="utf-8"))
ABSTENTION_KEYS = ("abstained", "abstention_reason", "abstention_source", "needs_clarification")
BREAKDOWN_KEYS = ("retrieval_ms", "llm_total_ms", "ttft_model_ms", "load_ms", "prompt_eval_ms", "eval_ms")
VIETNAMESE_ANSWER = ("Theo [1], nhà nước bảo hộ hôn nhân giữa công dân Việt Nam với người nước ngoài; "
                     "việc kết hôn phải tuân thủ nguyên tắc tự nguyện, tiến bộ, một vợ một chồng.")


def _five(rag):
    return [rag.make_row(i) for i in (1, 2, 3, 4, 5)]


def _fields(record: RAGOutputRecord) -> tuple:
    dumped = record.model_dump(mode="json")
    assert all(key in dumped for key in ABSTENTION_KEYS + ("llm_calls", "latency_breakdown"))
    assert set(dumped["latency_breakdown"]) == set(BREAKDOWN_KEYS)
    return tuple(dumped[key] for key in ABSTENTION_KEYS) + (dumped["llm_calls"],)


# ---------------------------------------------------------------------------
# P45-4: one test per row of the table in the task doc
# ---------------------------------------------------------------------------
def test_normal_answer(rag):
    pipeline, _ = rag.make_pipeline(_five(rag))
    record = rag.run(pipeline).record
    assert record.grounding_status == "PASS"
    assert _fields(record) == (False, None, None, False, 1)


@pytest.mark.parametrize("rows_scores, reason", [((0.087, 0.05), "LOW_CONFIDENCE"), ((), "EMPTY_RETRIEVAL")])
def test_confidence_filter_abstains_before_llm(rag, rows_scores, reason):
    rows = [rag.make_row(i + 1, score=s) for i, s in enumerate(rows_scores)]
    confidence = ConfidenceConfig(enabled=True, min_top1_score=0.5, threshold_config_version="t1")
    pipeline, gen = rag.make_pipeline(rows, confidence=confidence)
    record = rag.run(pipeline, query_id="HN_035").record
    assert gen.prompts == [] and "llm" not in record.retrieval_trace
    assert record.grounding_status == "ABSTAIN"
    assert _fields(record) == (True, reason, "confidence_filter", False, 0)


def test_model_abstains(rag):
    gen = rag.FakeGenerator(abstained=True, abstention_reason="Bằng chứng không nói về việc này",
                            answer="", evidence_indices=[])
    pipeline, _ = rag.make_pipeline(_five(rag), gen)
    record = rag.run(pipeline).record
    assert record.grounding_status == "ABSTAIN"
    assert _fields(record) == (True, "MODEL_ABSTAINED", "model", False, 1)
    assert record.retrieval_trace["llm"]["abstention_reason"] == "Bằng chứng không nói về việc này"


def test_model_needs_clarification(rag):
    gen = rag.FakeGenerator(needs_clarification=True, answer="Hai bên kết hôn năm nào?", evidence_indices=[])
    pipeline, _ = rag.make_pipeline(_five(rag), gen)
    record = rag.run(pipeline).record
    assert record.grounding_status == "NEEDS_CLARIFICATION"
    assert _fields(record) == (False, None, "model", True, 1)


def test_gate_fail_counts_as_abstention(rag):
    """HN_300 in Run B 10/11: markers [3], [5] in the answer, evidence_indices [1, 2]."""
    gen = rag.FakeGenerator(answer="Theo [1], [2], [3] và [5].", evidence_indices=[1, 2])
    pipeline, _ = rag.make_pipeline(_five(rag), gen)
    record = rag.run(pipeline, query_id="HN_300").record
    assert record.grounding_status == "FAIL"
    assert _fields(record) == (True, "ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES", "grounding_gate", False, 1)


def _record_kwargs(**overrides):
    values = dict(query_id="q", query="Câu hỏi?", as_of_date="2026-10-15", as_of_date_source="benchmark",
                  answer="x", grounding_status="PASS", abstained=False, abstention_reason=None,
                  abstention_source=None, needs_clarification=False, prompt_version="v", done_reason="stop",
                  truncated=False, corpus_version="c", retrieval_config_version="r",
                  threshold_config_version="t", latency_ms=1.0, llm_calls=1)
    values.update(overrides)
    return values


@pytest.mark.parametrize("overrides", [
    {"grounding_status": "ABSTAIN"},                                                    # all four left at PASS values
    {"grounding_status": "ABSTAIN", "abstained": True, "abstention_source": "confidence_filter"},  # no reason
    {"grounding_status": "FAIL", "abstained": True, "abstention_reason": "X", "abstention_source": "model"},
    {"grounding_status": "PASS", "abstention_source": "model"},
    {"grounding_status": "NEEDS_CLARIFICATION", "abstention_source": "model"},          # needs_clarification false
    {"grounding_status": "ABSTAIN", "abstained": True, "abstention_reason": "LOW_CONFIDENCE",
     "abstention_source": "confidence_filter", "llm_calls": 1},
    {"llm_calls": 0},
])
def test_record_rejects_inconsistent_abstention_fields(overrides):
    with pytest.raises(ValidationError):
        RAGOutputRecord(**_record_kwargs(**overrides))


def test_record_requires_the_abstention_fields():
    values = _record_kwargs()
    for key in ABSTENTION_KEYS + ("llm_calls",):
        missing = {k: v for k, v in values.items() if k != key}
        with pytest.raises(ValidationError):
            RAGOutputRecord(**missing)


def test_router_source_is_allowed_before_llm():
    record = RAGOutputRecord(**_record_kwargs(grounding_status="ABSTAIN", abstained=True,
                                              abstention_reason="OUT_OF_SCOPE", abstention_source="router",
                                              llm_calls=0))
    assert record.abstention_source == "router"


# ---------------------------------------------------------------------------
# P45-5: Gate blocks CJK answers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case", RUN_B_CJK, ids=[c["query_id"] for c in RUN_B_CJK])
def test_run_b_chinese_answers_now_fail(rag, case):
    """Verbatim answer_before_gate of HN_025/HN_062 (Gate PASS on 10/11)."""
    assert case["gate_status_then"] == "PASS" and count_cjk_chars(case["answer"]) > 0
    gen = rag.FakeGenerator(answer=case["answer"], evidence_indices=case["evidence_indices"])
    pipeline, _ = rag.make_pipeline(_five(rag), gen)
    record = rag.run(pipeline, query_id=case["query_id"]).record
    assert record.grounding_status == "FAIL"
    assert record.retrieval_trace["gate"]["reason"] == "ANSWER_NOT_VIETNAMESE"
    assert record.answer.startswith(FAIL_MESSAGE) and count_cjk_chars(record.answer) == 0
    assert record.retrieval_trace["llm"]["cjk_chars_before_gate"] == count_cjk_chars(case["answer"])
    assert _fields(record) == (True, "ANSWER_NOT_VIETNAMESE", "grounding_gate", False, 1)


def test_vietnamese_answer_mentioning_foreigners_passes(rag):
    gen = rag.FakeGenerator(answer=VIETNAMESE_ANSWER, evidence_indices=[1])
    pipeline, _ = rag.make_pipeline(_five(rag), gen)
    record = rag.run(pipeline).record
    assert record.grounding_status == "PASS"
    assert record.retrieval_trace["llm"]["cjk_chars_before_gate"] == 0


@pytest.mark.parametrize("text", [
    "Theo [1], hiệu力 của bản án.",     # one Han character mid-word (HN_025 start)
    "Theo [1], 《婚姻法》 quy định.",      # CJK brackets
    "Theo [1], すべて có hiệu lực.",      # kana
    "Theo [1], 혼인 có hiệu lực.",         # Hangul
    "Theo [1], 𠀀 có hiệu lực.",           # CJK extension B
])
def test_gate_blocks_any_cjk_script(rag, text):
    pipeline, _ = rag.make_pipeline(_five(rag))
    payload = rag.run(pipeline).payload
    llm = LLMResponse(query_id="HN_001", run_mode="B_controlled_rag", answer=text, evidence_indices=[1],
                      prompt_version="v", done_reason="stop")
    assert apply_grounding_gate(payload, llm).reason == "ANSWER_NOT_VIETNAMESE"


def test_full_vietnamese_diacritics_are_not_cjk():
    text = ("ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệ"
            "ỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ “” … – §")
    assert count_cjk_chars(text) == 0


# ---------------------------------------------------------------------------
# P45-6: llm_calls and latency_breakdown
# ---------------------------------------------------------------------------
class TimedLLMResponse(LLMResponse):
    """LLMResponse with the Ollama duration fields planned in P45-3 (Dev 3)."""
    load_duration_ms: float | None = None
    prompt_eval_duration_ms: float | None = None
    eval_duration_ms: float | None = None
    total_duration_ms: float | None = None
    ttft_model_ms: float | None = None


class TimedGenerator:
    def __init__(self, base, **durations):
        self.base, self.durations, self.config = base, durations, base.config

    def generate(self, *args, **kwargs):
        response = self.base.generate(*args, **kwargs)
        return TimedLLMResponse(**response.model_dump(), **self.durations)


def test_breakdown_is_null_without_measurements(rag):
    """Precomputed/fixture source and a gateway without Ollama durations: null, never 0."""
    pipeline, _ = rag.make_pipeline(_five(rag))
    record = rag.run(pipeline).record
    assert record.latency_breakdown.model_dump() == {
        "retrieval_ms": None, "llm_total_ms": 12.0, "ttft_model_ms": None, "load_ms": None,
        "prompt_eval_ms": None, "eval_ms": None}


def test_breakdown_takes_ollama_durations_when_the_gateway_returns_them(rag):
    gen = TimedGenerator(rag.FakeGenerator(), load_duration_ms=12000.5, prompt_eval_duration_ms=800.25,
                         eval_duration_ms=9000.0, total_duration_ms=21900.0, ttft_model_ms=12800.75)
    pipeline, _ = rag.make_pipeline(_five(rag), gen)
    breakdown = rag.run(pipeline).record.latency_breakdown
    assert (breakdown.ttft_model_ms, breakdown.load_ms, breakdown.prompt_eval_ms, breakdown.eval_ms) == (
        12800.75, 12000.5, 800.25, 9000.0)


def test_breakdown_without_llm_call(rag):
    confidence = ConfidenceConfig(enabled=True, min_top1_score=0.5, threshold_config_version="t1")
    pipeline, _ = rag.make_pipeline([rag.make_row(1, score=0.1)], confidence=confidence)
    record = rag.run(pipeline).record
    assert record.llm_calls == 0
    assert all(v is None for v in record.latency_breakdown.model_dump().values())


def test_live_source_measures_retrieval(rag):
    class FakeLive:
        reranker = object()

        def run(self, query, *, query_id, as_of_date):
            return rag.envelope(query_id, _five(rag), query)

    pipeline, _ = rag.make_pipeline([], source=LivePipelineSource(FakeLive()))
    record = rag.run(pipeline).record
    assert record.latency_breakdown.retrieval_ms is not None
    assert 0 <= record.latency_breakdown.retrieval_ms <= record.latency_ms
