"""Dependency wiring for the CLI and the API (Sprint 10 D5.1). No business logic here.

Settings come from the environment (or CLI flags):

==============================  ======================================================
``LEGAL_RAG_PIPELINE_MODE``     ``live`` (default) or ``mock`` (orchestration/fakes.py)
``RAG_PRECOMPUTED``             reranked artifact instead of live retrieval (optional)
``ELASTICSEARCH_URL``           BM25 index (live)
``QDRANT_URL``                  Qdrant server (live; use it when a batch run also reads)
``QDRANT_PATH``                 embedded Qdrant folder (live, single process only)
``LEGAL_RAG_EVENT_LOG``         JSONL file for stage events (optional, local only)
==============================  ======================================================
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from orchestration.ask_service import AskService, RuleRouterAdapter
from orchestration.events import EventSink, JsonlEventSink, NullEventSink

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


def build_event_sink(settings: ServiceSettings) -> EventSink:
    return JsonlEventSink(settings.event_log) if settings.event_log else NullEventSink()


def build_ask_service(settings: ServiceSettings | None = None, *, sink: EventSink | None = None) -> AskService:
    """Real router + the shared RAGPipeline in production mode (or the mock pipeline)."""
    settings = settings or ServiceSettings.from_env()
    sink = sink or build_event_sink(settings)
    if settings.mode == "mock":
        from orchestration.fakes import build_mock_pipeline

        pipeline = build_mock_pipeline(run_mode=PRODUCTION_RUN_MODE)
    else:
        from orchestration.rag_pipeline import build_pipeline

        pipeline = build_pipeline(precomputed=settings.precomputed, elasticsearch_url=settings.elasticsearch_url,
                                  qdrant_url=settings.qdrant_url, qdrant_path=settings.qdrant_path,
                                  run_mode=PRODUCTION_RUN_MODE)
    return AskService(RuleRouterAdapter(), pipeline, sink=sink)


__all__ = ["PRODUCTION_RUN_MODE", "ServiceSettings", "build_ask_service", "build_event_sink"]
