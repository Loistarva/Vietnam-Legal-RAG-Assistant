"""Mock components with the real interfaces (Sprint 10 plan, section 4.4: mock-first).

``build_mock_pipeline()`` is the real ``RAGPipeline`` (confidence filter, context builder,
prompt, Gate) with a fixture candidate source and a scripted model, so tests, the CLI
``--mock`` flag and the API mock mode (``LEGAL_RAG_PIPELINE_MODE=mock``, for Dev 2's UI)
need no Elasticsearch, Qdrant or Ollama.

Markers in the question pick a branch (the router still runs on the real text):

* ``[mock:empty]``      no candidate            -> ABSTAIN, RETRIEVAL_EMPTY, no LLM call
* ``[mock:low]``        top-1 score 0.2         -> ABSTAIN, LOW_CONFIDENCE, no LLM call
* ``[mock:clarify]``    model asks for details  -> NEEDS_CLARIFICATION
* ``[mock:abstain]``    model abstains          -> ABSTAIN (model)
* ``[mock:gate_fail]``  model cites [6] of 2    -> Gate FAIL, CITATION_INVALID, no draft returned
* ``[mock:bad_json]``   unparsable model output -> Gate FAIL, JSON_INVALID
* ``[mock:timeout]``    gateway timeout         -> ERROR, LLM_TIMEOUT
* ``[mock:unavailable]`` model not reachable   -> ERROR, LLM_UNAVAILABLE

Every evidence text and title says it is mock data; nothing here is a real legal source.
"""
from __future__ import annotations

import json
import re
from typing import Any

from model_gateway.llm_gateway import GatewayExecutionError
from orchestration.rag_pipeline import RAGPipeline, RunVersions
from reranking.confidence import load_confidence_config
from schemas.models import LLMResponse, TokenUsage

MOCK_MARKER = re.compile(r"\[mock:([a-z_]+)\]")
MOCK_TITLE = "[MOCK] Luật Hôn nhân và gia đình (dữ liệu giả lập)"
MOCK_ANSWER = ("[Dữ liệu giả lập] Theo căn cứ [1], nam từ đủ 20 tuổi và nữ từ đủ 18 tuổi trở lên mới được "
               "kết hôn; việc kết hôn phải do hai bên tự nguyện quyết định [2].")


def mock_markers(text: str) -> set[str]:
    return set(MOCK_MARKER.findall(text or ""))


def mock_row(i: int, *, score: float) -> dict[str, Any]:
    chunk = f"mock_hngd_art_{i}_clause_1_chunk_1"
    return {
        "chunk_id": chunk,
        "document_id": "mock_hngd",
        "article_id": f"mock_hngd_art_{i}",
        "clause_id": f"mock_hngd_art_{i}_clause_1",
        "parent_clause_id": f"mock_hngd_art_{i}_clause_1",
        "parent_id": f"mock_hngd_art_{i}",
        "rank": i,
        "score": score,
        "reranker_score": score,
        "chunk_text": f"[Dữ liệu giả lập] Khoản 1 Điều {i}: nội dung minh họa số {i}, không phải văn bản luật.",
        "parent_text": f"[Dữ liệu giả lập] Điều {i}: toàn văn minh họa số {i}, không phải văn bản luật.",
        "metadata": {
            "validity_status": "Còn hiệu lực",
            "effective_from": "2015-01-01",
            "effective_to": None,
            "document_title": MOCK_TITLE,
            "document_number": "MOCK/2014",
            "breadcrumb": f"Điều {i} > Khoản 1",
            "source_url": None,
            "provision_status": "mock",
            "article_number": str(i),
            "clause_number": "1",
        },
    }


class FixtureSource:
    """Two reranked candidates (scores 0.95, 0.8); markers empty the list or lower the scores."""

    name = "mock_fixture"
    measures_retrieval = True

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, *, query_id: str, query: str, as_of_date: str) -> dict[str, Any]:
        self.calls += 1
        markers = mock_markers(query)
        if "empty" in markers:
            rows: list[dict[str, Any]] = []
        elif "low" in markers:
            rows = [mock_row(1, score=0.2), mock_row(2, score=0.1)]
        else:
            rows = [mock_row(1, score=0.95), mock_row(2, score=0.8)]
        return {"query_id": query_id, "query": query, "retriever": "mock_fixture", "as_of_date": as_of_date,
                "results": rows}


class _Config:
    model = "qwen2.5:7b"
    num_ctx = 8192
    num_predict = 1024


class ScriptedGenerator:
    """Behaves like ``QwenGateway.generate`` for structured output, driven by markers in the prompt."""

    config = _Config()

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, query_id: str, run_mode: str, prompt_version: str,
                 structured_output: bool = False, schema: dict[str, Any] | None = None,
                 max_evidence_index: int | None = None) -> LLMResponse:
        self.calls += 1
        markers = mock_markers(prompt)
        if "timeout" in markers:
            raise GatewayExecutionError("mock gateway timeout", error_code="LLM_TIMEOUT")
        if "unavailable" in markers:
            raise GatewayExecutionError("mock gateway unavailable", error_code="LLM_UNAVAILABLE")
        body: dict[str, Any] = {"answer": MOCK_ANSWER, "evidence_indices": [1, 2], "abstained": False,
                                "abstention_reason": None, "needs_clarification": False}
        parse_status, error_code = "ok", None
        if "clarify" in markers:
            body.update(answer="", evidence_indices=[], needs_clarification=True)
        elif "abstain" in markers:
            body.update(answer="", evidence_indices=[], abstained=True, abstention_reason="mock")
        elif "gate_fail" in markers:
            body.update(answer="[Dữ liệu giả lập] Bản nháp trích căn cứ [6] không có trong ngữ cảnh.",
                        evidence_indices=[6])
        indices, rejected = [], []
        for idx in body["evidence_indices"]:
            if max_evidence_index is not None and not 1 <= idx <= max_evidence_index:
                rejected.append(json.dumps(idx))
            else:
                indices.append(idx)
        if rejected:
            error_code = "CITATION_INVALID"
        if "bad_json" in markers:
            body.update(answer="", evidence_indices=[])
            indices, rejected, parse_status, error_code = [], [], "invalid_json", "JSON_INVALID"
        return LLMResponse(
            query_id=query_id, run_mode=run_mode, answer=body["answer"], evidence_indices=indices,
            rejected_evidence_values=rejected, abstained=body["abstained"],
            abstention_reason=body["abstention_reason"], needs_clarification=body["needs_clarification"],
            prompt_version=prompt_version, done_reason="stop", parse_status=parse_status, latency_ms=5.0,
            token_usage=TokenUsage(input=800, output=60), raw_response=json.dumps(body, ensure_ascii=False),
            error_code=error_code, model_digest="mock",
        )


def build_mock_pipeline(*, run_mode: str = "C_production_rag", generator: ScriptedGenerator | None = None,
                        source: FixtureSource | None = None) -> RAGPipeline:
    """Real orchestrator and Gate with fixture retrieval and a scripted model; the real
    confidence thresholds (reranking/confidence.yaml) apply."""
    confidence = load_confidence_config()
    versions = RunVersions(corpus_version="mock:corpus", retrieval_config_version="mock:retrieval",
                           threshold_config_version=confidence.threshold_config_version)
    return RAGPipeline(source or FixtureSource(), generator or ScriptedGenerator(), versions=versions,
                       confidence=confidence, rerank_top_k=5, max_context_chars=6000, run_mode=run_mode)


__all__ = ["FixtureSource", "MOCK_TITLE", "ScriptedGenerator", "build_mock_pipeline", "mock_markers", "mock_row"]
