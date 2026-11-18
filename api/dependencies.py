"""FastAPI dependencies: the shared ``AskService`` and the concurrency slots. No business logic."""
from __future__ import annotations

import threading

from fastapi import Request

from api.settings import ApiSettings
from orchestration.ask_service import AskService


def get_settings(request: Request) -> ApiSettings:
    return request.app.state.api_settings


def get_service(request: Request) -> AskService:
    service = getattr(request.app.state, "ask_service", None)
    if service is None:
        raise RuntimeError("AskService chưa được khởi tạo (lifespan chưa chạy)")
    return service


def get_slots(request: Request) -> threading.BoundedSemaphore:
    return request.app.state.pipeline_slots


__all__ = ["get_service", "get_settings", "get_slots"]
