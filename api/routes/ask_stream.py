"""``POST /api/v1/ask/stream``: SSE status events, then the verified response (Sprint 10 D5.5, P1).

Same body, API key and pipeline as ``POST /api/v1/ask``. Event order (``sse_v1``)::

    status (accepted) -> status (routing, retrieving, reranking, generating, validating, ...)
      -> one of verified_answer | clarification | abstention | error -> done

* Status events come from the stage ``LogEvent``s, which never carry query, prompt or
  answer text, so nothing of the draft can reach the client before the Gate.
* The answer is only in the final event, i.e. after the Gate decided (buffer -> Gate -> emit).
* Every event has ``elapsed_ms`` since the request was accepted; the server logs the first
  status byte and the final event time separately (``stream_first_status``, ``stream_final``).
* If the client disconnects, the stream stops and ``client_disconnected`` is logged. The
  pipeline call already running (a local Qwen request) cannot be interrupted; it finishes in
  its worker thread and releases its slot.

Format and examples: docs/api/sse_events.md.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.dependencies import get_service, get_settings, get_slots
from api.errors import ValidationDetail, error_response
from api.routes.ask import ASK_RESPONSES
from api.security.api_key_guard import require_api_key
from api.settings import ApiSettings
from orchestration.ask_service import AskService, new_query_id
from orchestration.events import StageEmitter
from schemas.models import SCHEMA_VERSION, AskRequest, LogEvent

router = APIRouter(prefix="/api/v1")

SSE_VERSION = "sse_v1"
PHASES = {"router": "routing", "retrieval": "retrieving", "rerank": "reranking", "context": "generating",
          "llm": "generating", "citation": "validating", "gate": "validating"}
FINAL_EVENTS = {"SUCCESS": "verified_answer", "NEEDS_CLARIFICATION": "clarification", "ABSTAIN": "abstention",
                "ERROR": "error"}


def format_sse(event: str, seq: int, data: dict[str, Any]) -> str:
    return f"event: {event}\nid: {seq}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class _QueueSink:
    """Hands stage events from the worker thread to the event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
        self.loop, self.queue = loop, queue

    def emit(self, event: LogEvent) -> None:
        try:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, ("stage", event))
        except RuntimeError:  # loop closed after a disconnect at shutdown
            pass


@router.post("/ask/stream", tags=["ask"], dependencies=[Depends(require_api_key)], response_model=None,
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "Chuỗi SSE `sse_v1` (docs/api/sse_events.md)."},
                        **{k: v for k, v in ASK_RESPONSES.items() if k in (401, 403, 422)}},
             summary="Hỏi đáp qua SSE: trạng thái trước, câu trả lời sau Grounding Gate")
async def ask_stream(body: AskRequest, request: Request, service: AskService = Depends(get_service),
                     settings: ApiSettings = Depends(get_settings),
                     slots: threading.BoundedSemaphore = Depends(get_slots)) -> StreamingResponse | JSONResponse:
    if len(body.query) > settings.max_query_chars:
        detail = ValidationDetail(loc=["body", "query"], msg=f"query dài hơn {settings.max_query_chars} ký tự",
                                  type="string_too_long")
        return error_response(422, "INVALID_REQUEST", "Request không hợp lệ", details=[detail])

    query_id = body.query_id or new_query_id()
    request.state.query_id = query_id
    log = StageEmitter(query_id, service.sink)
    started = time.perf_counter()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def work() -> None:
        outcome = None
        try:
            with slots:
                outcome = service.run(body, query_id=query_id, sink=_QueueSink(loop, queue))
        except Exception as exc:  # noqa: BLE001 - reported as an error event without details
            log.emit("api", "stream_failed", "error", error_code="INTERNAL_ERROR", error_type=type(exc).__name__)
        try:
            loop.call_soon_threadsafe(queue.put_nowait, ("final", outcome))
        except RuntimeError:
            pass

    def elapsed() -> float:
        return round((time.perf_counter() - started) * 1000.0, 2)

    async def events() -> AsyncIterator[str]:
        seq = 0
        seen: set[str] = set()
        finished = False
        log.emit("api", "request_received", "accepted", request_id=body.request_id, session_id=body.session_id,
                 transport="sse")
        try:
            yield format_sse("status", seq, {"schema_version": SCHEMA_VERSION, "sse_version": SSE_VERSION,
                                             "query_id": query_id, "phase": "accepted", "elapsed_ms": elapsed()})
            log.emit("api", "stream_first_status", "sent", duration_ms=elapsed(), transport="sse")
            loop.run_in_executor(None, work)
            while True:
                kind, item = await queue.get()
                if kind == "stage":
                    phase = PHASES.get(item.stage)
                    if phase is None or phase in seen:
                        continue
                    seen.add(phase)
                    seq += 1
                    yield format_sse("status", seq, {"sse_version": SSE_VERSION, "query_id": query_id,
                                                     "phase": phase, "elapsed_ms": elapsed()})
                    continue
                seq += 1
                if item is None:
                    data = {"sse_version": SSE_VERSION, "query_id": query_id, "status": "ERROR",
                            "error_code": "INTERNAL_ERROR", "message": "Hệ thống gặp lỗi khi xử lý request",
                            "elapsed_ms": elapsed()}
                    yield format_sse("error", seq, data)
                    final_status = "ERROR"
                else:
                    response = item.response
                    yield format_sse(FINAL_EVENTS[response.status], seq,
                                     {"sse_version": SSE_VERSION, "elapsed_ms": elapsed(),
                                      "response": response.model_dump(mode="json")})
                    final_status = response.status
                log.emit("api", "stream_final", final_status, duration_ms=elapsed(), transport="sse")
                seq += 1
                yield format_sse("done", seq, {"sse_version": SSE_VERSION, "query_id": query_id,
                                               "status": final_status, "elapsed_ms": elapsed()})
                finished = True
                return
        finally:
            if not finished:
                log.emit("api", "client_disconnected", "cancelled", duration_ms=elapsed(), transport="sse")

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Query-ID": query_id,
                                      "X-Accel-Buffering": "no"})


__all__ = ["FINAL_EVENTS", "PHASES", "SSE_VERSION", "format_sse", "router"]
