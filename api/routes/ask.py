"""``POST /api/v1/ask`` (Sprint 10 D5.3) and ``GET /api/v1/health``.

The route only validates, authenticates, assigns ``query_id`` and maps the status to HTTP;
routing, retrieval, generation and the Gate run in the shared ``AskService``.

HTTP status: SUCCESS / NEEDS_CLARIFICATION / ABSTAIN -> 200 (the body says which);
ERROR -> 504 for ``LLM_TIMEOUT``, 500 otherwise, still with an ``AskResponse`` body.
401/422 bodies are ``ApiError``.
"""
from __future__ import annotations

import threading
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.dependencies import get_service, get_slots, validated_ask_request
from api.errors import ERROR_HTTP_STATUS, ApiError
from api.security.api_key_guard import require_api_key
from orchestration.ask_service import AskService
from orchestration.events import StageEmitter
from schemas.models import SCHEMA_VERSION, AskRequest, AskResponse, SchemaVersionType

router = APIRouter(prefix="/api/v1")

ASK_RESPONSES = {
    200: {"model": AskResponse, "description": "SUCCESS, NEEDS_CLARIFICATION hoặc ABSTAIN (xem `status`)."},
    401: {"model": ApiError, "description": "Thiếu hoặc sai X-API-Key (`AUTH_REQUIRED`)."},
    422: {"model": ApiError, "description": "Body không đúng AskRequest (`INVALID_REQUEST`)."},
    500: {"model": AskResponse | ApiError, "description": "`status=ERROR`, `error_code=INTERNAL_ERROR`."},
    504: {"model": AskResponse, "description": "`status=ERROR`, `error_code=LLM_TIMEOUT`."},
}


class HealthResponse(BaseModel):
    status: str
    schema_version: SchemaVersionType = SCHEMA_VERSION
    pipeline_ready: bool


@router.get("/health", response_model=HealthResponse, tags=["health"],
            summary="Kiểm tra API còn sống (không gọi Retrieval hay LLM, không cần API key)")
def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", pipeline_ready=getattr(request.app.state, "ask_service", None) is not None)


@router.post("/ask", response_model=AskResponse, responses=ASK_RESPONSES, tags=["ask"],
             dependencies=[Depends(require_api_key)],
             summary="Hỏi đáp pháp luật Hôn nhân và gia đình",
             description="Định tuyến → (Retrieval → Context → Qwen → Grounding Gate) → AskResponse. "
                         "`answer` chỉ có khi `status=SUCCESS`, sau Gate PASS cho câu hỏi pháp lý "
                         "hoặc qua kịch bản tĩnh cho câu xã giao.")
def ask(request: Request, body: AskRequest = Depends(validated_ask_request),
        service: AskService = Depends(get_service),
        slots: threading.BoundedSemaphore = Depends(get_slots)) -> JSONResponse:
    started = time.perf_counter()
    query_id = request.state.query_id
    events = StageEmitter(query_id, service.sink)
    events.emit("api", "request_received", "accepted", request_id=body.request_id, session_id=body.session_id)
    with slots:
        outcome = service.run(body, query_id=query_id)
    response = outcome.response
    status_code = 200 if response.status != "ERROR" else ERROR_HTTP_STATUS.get(response.error_code or "", 500)
    events.emit("api", "request_completed", response.status, duration_ms=(time.perf_counter() - started) * 1000.0,
                http_status=status_code, error_code=response.error_code)
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"),
                        headers={"X-Query-ID": quote(query_id, safe="")})


__all__ = ["ASK_RESPONSES", "HealthResponse", "router"]
