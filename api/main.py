"""FastAPI app (Sprint 10 D5.3–D5.6).

Run::

    set LEGAL_RAG_API_KEYS=<key>                 (PowerShell: $env:LEGAL_RAG_API_KEYS="<key>")
    uvicorn api.main:app --host 127.0.0.1 --port 8000

``LEGAL_RAG_PIPELINE_MODE=mock`` serves the mock pipeline (no Elasticsearch/Qdrant/Ollama)
for UI work. Swagger UI is at ``/docs``, the schema at ``/openapi.json``.

``app`` is created on first access, so importing this module (tests, OpenAPI export) needs
no API key; ``create_app`` refuses to build an app without one.
"""
from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.errors import install_error_handlers
from api.routes import ask, ask_stream
from api.security.api_key_guard import API_KEY_HEADER, ApiKeyGuard
from api.settings import ApiSettings
from orchestration.ask_service import AskService
from orchestration.wiring import ServiceSettings, build_ask_service
from schemas.models import SCHEMA_VERSION

API_TITLE = "Vietnam Legal RAG Assistant API"
API_VERSION = "1.0.0"
API_DESCRIPTION = (
    "API hỏi đáp pháp luật Hôn nhân và gia đình. Contract `schemas/models.py` "
    f"(`schema_version={SCHEMA_VERSION}`). Mọi request hỏi đáp cần header `{API_KEY_HEADER}`."
)


def create_app(*, settings: ApiSettings | None = None, service: AskService | None = None,
               service_settings: ServiceSettings | None = None) -> FastAPI:
    """``service`` is injected in tests; otherwise it is built at startup from the environment."""
    settings = settings or ApiSettings.from_env()
    guard = ApiKeyGuard.from_value(settings.api_keys)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.ask_service is None:
            app.state.ask_service = build_ask_service(service_settings or ServiceSettings.from_env())
        yield

    app = FastAPI(title=API_TITLE, version=API_VERSION, description=API_DESCRIPTION, lifespan=lifespan)
    app.state.api_settings = settings
    app.state.api_key_guard = guard
    app.state.ask_service = service
    app.state.pipeline_slots = threading.BoundedSemaphore(settings.max_concurrency)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                           allow_methods=["GET", "POST"], allow_headers=["Content-Type", API_KEY_HEADER])
    install_error_handlers(app)
    app.include_router(ask.router)
    app.include_router(ask_stream.router)
    return app


_APP: FastAPI | None = None


def __getattr__(name: str) -> Any:
    """``api.main.app`` for ``uvicorn api.main:app``, built from the environment on first access."""
    global _APP
    if name == "app":
        if _APP is None:
            _APP = create_app()
        return _APP
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["API_TITLE", "API_VERSION", "create_app"]
