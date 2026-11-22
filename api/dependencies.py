"""FastAPI dependencies: the shared ``AskService`` and the concurrency slots. No business logic."""
from __future__ import annotations

import threading

from fastapi import Request
from fastapi.exceptions import RequestValidationError

from api.settings import ApiSettings
from orchestration.ask_service import AskService, new_query_id
from schemas.models import AskRequest


def get_settings(request: Request) -> ApiSettings:
    return request.app.state.api_settings


def validated_ask_request(body: AskRequest, request: Request) -> AskRequest:
    request.state.query_id = body.query_id or new_query_id()
    limit = get_settings(request).max_query_chars
    if len(body.query) > limit:
        raise RequestValidationError([{"loc": ("body", "query"), "msg": f"query dài hơn {limit} ký tự",
                                       "type": "string_too_long"}])
    return body


def get_service(request: Request) -> AskService:
    service = getattr(request.app.state, "ask_service", None)
    if service is None:
        raise RuntimeError("AskService chưa được khởi tạo (lifespan chưa chạy)")
    return service


def get_slots(request: Request) -> threading.BoundedSemaphore:
    return request.app.state.pipeline_slots


__all__ = ["get_service", "get_settings", "get_slots", "validated_ask_request"]
