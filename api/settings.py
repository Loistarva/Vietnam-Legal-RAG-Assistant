"""API settings from the environment (Sprint 10 D5.3/D5.4). Secrets are read, never stored in Git.

==============================  =========================================================
``LEGAL_RAG_API_KEYS``          required; comma-separated keys, each >= 16 characters
``LEGAL_RAG_ENV``               ``development`` (default) or ``production``
``LEGAL_RAG_CORS_ORIGINS``      comma-separated origins; empty = no CORS; ``*`` refused in
                                production
``LEGAL_RAG_MAX_QUERY_CHARS``   longest accepted question (default 2000)
``LEGAL_RAG_MAX_CONCURRENCY``   questions processed at the same time (default 1: one local
                                Qwen, embedded Qdrant)
==============================  =========================================================

Pipeline settings (mode, Elasticsearch, Qdrant, event log) are in ``orchestration.wiring``.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ApiSettings:
    api_keys: str = field(default="", repr=False)
    env: Literal["development", "production"] = "development"
    cors_origins: tuple[str, ...] = ()
    max_query_chars: int = 2000
    max_concurrency: int = 1

    def __post_init__(self) -> None:
        if self.env not in ("development", "production"):
            raise ValueError(f"LEGAL_RAG_ENV={self.env!r} không hợp lệ")
        if self.env == "production" and "*" in self.cors_origins:
            raise ValueError("Không cho phép LEGAL_RAG_CORS_ORIGINS='*' khi LEGAL_RAG_ENV=production")
        if self.max_query_chars < 1 or self.max_concurrency < 1:
            raise ValueError("LEGAL_RAG_MAX_QUERY_CHARS và LEGAL_RAG_MAX_CONCURRENCY phải >= 1")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ApiSettings":
        env = os.environ if env is None else env
        origins = tuple(o.strip() for o in env.get("LEGAL_RAG_CORS_ORIGINS", "").split(",") if o.strip())
        return cls(
            api_keys=env.get("LEGAL_RAG_API_KEYS", ""),
            env=(env.get("LEGAL_RAG_ENV", "").strip().lower() or "development"),  # type: ignore[arg-type]
            cors_origins=origins,
            max_query_chars=int(env.get("LEGAL_RAG_MAX_QUERY_CHARS", "").strip() or 2000),
            max_concurrency=int(env.get("LEGAL_RAG_MAX_CONCURRENCY", "").strip() or 1),
        )


__all__ = ["ApiSettings"]
