"""Shared fixtures for the RAG orchestrator tests: synthetic reranked rows, a fake Qwen."""
from __future__ import annotations

import json
from typing import Any

import pytest

from orchestration.rag_pipeline import RAGPipeline, RunVersions
from reranking.confidence import ConfidenceConfig
from schemas.models import LLMResponse, TokenUsage


def make_row(i: int, *, score: float | None = None, parent_id: str | None = None, parent_text: Any = "",
             chunk_text: str | None = None, **overrides: Any) -> dict[str, Any]:
    """Row as reranking.pipeline.to_contract_result + ParentContextResolver emit it."""
    row = {
        "chunk_id": f"doc_a_art_{i}_clause_1_chunk_1",
        "document_id": "doc_a",
        "article_id": f"doc_a_art_{i}",
        "clause_id": f"doc_a_art_{i}_clause_1",
        "parent_clause_id": f"doc_a_art_{i}_clause_1",
        "rank": i,
        "score": score if score is not None else round(1.0 - i * 0.1, 3),
        "reranker_score": score if score is not None else round(1.0 - i * 0.1, 3),
        "chunk_text": chunk_text or f"Khoản 1 Điều {i}: nội dung {i}.",
        "metadata": {
            "validity_status": "Còn hiệu lực",
            "effective_from": "2015-01-01",
            "effective_to": None,
            "document_title": "Luật Hôn nhân và gia đình 2014",
            "document_number": "52/2014/QH13",
            "breadcrumb": f"Điều {i} > Khoản 1",
            "source_url": "https://vbpl.vn/x",
            "provision_status": "document_level_only",
            "article_number": str(i),
            "clause_number": "1",
        },
        "parent_id": parent_id or f"doc_a_art_{i}",
        "parent_text": (f"[Điều {i}] toàn văn điều {i}." if parent_text == "" else parent_text),
    }
    row.update(overrides)
    return row


def envelope(query_id: str, rows: list[dict[str, Any]], query: str = "Câu hỏi?") -> dict[str, Any]:
    return {"query_id": query_id, "query": query, "retriever": "hybrid_reranker", "results": rows}


class StaticSource:
    name = "fixture"

    def __init__(self, rows: list[dict[str, Any]], *, query_id: str | None = None):
        self.rows = rows
        self.query_id = query_id
        self.calls: list[dict[str, Any]] = []

    def fetch(self, *, query_id: str, query: str, as_of_date: str) -> dict[str, Any]:
        self.calls.append({"query_id": query_id, "query": query, "as_of_date": as_of_date})
        return envelope(self.query_id or query_id, [dict(r) for r in self.rows], query)


class FakeConfig:
    model = "qwen2.5:7b"
    num_ctx = 8192
    num_predict = 1024


class FakeGenerator:
    """Returns one canned LLMResponse; records the prompts it was given."""

    config = FakeConfig()

    def __init__(self, **response: Any):
        self.response = response
        self.prompts: list[str] = []
        self.query_ids: list[str] = []

    def generate(self, prompt: str, query_id: str, run_mode: str, prompt_version: str,
                 structured_output: bool = False, schema: dict[str, Any] | None = None) -> LLMResponse:
        assert structured_output is True and run_mode == "B_controlled_rag"
        self.prompts.append(prompt)
        self.query_ids.append(query_id)
        values = {
            "query_id": query_id, "run_mode": run_mode, "answer": "Theo [1], nam từ đủ 20 tuổi.",
            "evidence_indices": [1], "prompt_version": prompt_version, "done_reason": "stop",
            "token_usage": TokenUsage(input=900, output=80), "latency_ms": 12.0,
            "raw_response": json.dumps({"answer": "x"}),
        }
        values.update(self.response)
        return LLMResponse(**values)


def make_pipeline(rows: list[dict[str, Any]], generator: FakeGenerator | None = None, *,
                  confidence: ConfidenceConfig | None = None, rerank_top_k: int = 5,
                  max_context_chars: int = 6000, source: Any = None, parent_resolver: Any = None):
    confidence = confidence or ConfidenceConfig()
    generator = generator or FakeGenerator()
    versions = RunVersions(corpus_version="sha256:c0", retrieval_config_version="sha256:r0",
                           threshold_config_version=confidence.threshold_config_version)
    pipeline = RAGPipeline(source or StaticSource(rows), generator, versions=versions, confidence=confidence,
                           rerank_top_k=rerank_top_k, max_context_chars=max_context_chars,
                           parent_resolver=parent_resolver)
    return pipeline, generator


def run(pipeline: RAGPipeline, query_id: str = "HN_001", query: str = "Câu hỏi?", as_of_date: str = "2026-10-15"):
    return pipeline.run(query_id=query_id, query=query, as_of_date=as_of_date, as_of_date_source="benchmark")


@pytest.fixture
def rag():
    """Namespace of helpers so tests do not import conftest directly."""
    class Helpers:
        pass

    helpers = Helpers()
    helpers.make_row = make_row
    helpers.make_pipeline = make_pipeline
    helpers.run = run
    helpers.FakeGenerator = FakeGenerator
    helpers.StaticSource = StaticSource
    helpers.envelope = envelope
    return helpers
