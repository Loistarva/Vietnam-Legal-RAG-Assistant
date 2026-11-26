"""Dependency wiring for the CLI and the API (Sprint 10 D5.1). No business logic here.

Settings come from the environment (or CLI flags):

==============================  ======================================================
``LEGAL_RAG_PIPELINE_MODE``     ``live`` (default) or ``mock`` (orchestration/fakes.py)
``RAG_PRECOMPUTED``             reranked artifact instead of live retrieval (optional)
``ELASTICSEARCH_URL``           BM25 index (live)
``QDRANT_URL``                  Qdrant server (live; use it when a batch run also reads)
``QDRANT_PATH``                 embedded Qdrant folder (live, single process only)
``LEGAL_RAG_EVENT_LOG``         JSONL via monitoring.StructuredLogger (PII/secret masked)
==============================  ======================================================
"""
from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from agent.router.adapter import RuleRouterAdapter
from monitoring.pii_masker import PIIMasker
from monitoring.structured_logger import StructuredLogger
from orchestration.ask_service import AskService
from orchestration.events import EventSink, NullEventSink

PRODUCTION_RUN_MODE = "C_production_rag"


@dataclass(frozen=True)
class ServiceSettings:
    mode: Literal["live", "mock"] = "live"
    precomputed: str | None = None
    elasticsearch_url: str | None = None
    qdrant_url: str | None = None
    qdrant_path: str | None = None
    event_log: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ServiceSettings":
        env = os.environ if env is None else env

        def get(name: str) -> str | None:
            value = env.get(name, "").strip()
            return value or None

        mode = (get("LEGAL_RAG_PIPELINE_MODE") or "live").lower()
        if mode not in ("live", "mock"):
            raise ValueError(f"LEGAL_RAG_PIPELINE_MODE={mode!r} không hợp lệ, cần live hoặc mock")
        return cls(mode=mode, precomputed=get("RAG_PRECOMPUTED"), elasticsearch_url=get("ELASTICSEARCH_URL"),
                   qdrant_url=get("QDRANT_URL"), qdrant_path=get("QDRANT_PATH"), event_log=get("LEGAL_RAG_EVENT_LOG"))


def parse_api_keys(value: str) -> tuple[str, ...]:
    return tuple(key for key in map(str.strip, value.split(",")) if key)


def build_event_sink(settings: ServiceSettings, *, secret_values: Iterable[str] = ()) -> EventSink:
    if settings.event_log:
        return StructuredLogger(settings.event_log, masker=PIIMasker(secret_values=secret_values))
    return NullEventSink()


def build_ask_service(settings: ServiceSettings | None = None, *, sink: EventSink | None = None,
                      secret_values: Iterable[str] = ()) -> AskService:
    """Real router + the shared RAGPipeline in production mode (or the mock pipeline)."""
    settings = settings or ServiceSettings.from_env()
    if settings.mode == "mock":
        from orchestration.fakes import build_mock_pipeline

        pipeline = build_mock_pipeline(run_mode=PRODUCTION_RUN_MODE)
    else:
        from orchestration.rag_pipeline import build_pipeline

        pipeline = build_pipeline(precomputed=settings.precomputed, elasticsearch_url=settings.elasticsearch_url,
                                  qdrant_url=settings.qdrant_url, qdrant_path=settings.qdrant_path,
                                  run_mode=PRODUCTION_RUN_MODE)
    router = RuleRouterAdapter()
    if sink is None:
        sink = build_event_sink(settings, secret_values=secret_values)
    return AskService(router, pipeline, sink=sink)


__all__ = ["PRODUCTION_RUN_MODE", "ServiceSettings", "build_ask_service", "build_event_sink", "parse_api_keys"]
