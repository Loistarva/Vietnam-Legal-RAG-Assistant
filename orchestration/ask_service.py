"""Single entrypoint ``run(AskRequest) -> AskResponse`` for the CLI and the API (Sprint 10 D5.1).

One request goes through::

    AskRequest -> query_id + as_of_date (question > user date > today)
      -> Router (Dev 4, via ``RouteDecision``)
           NON_LEGAL           -> static General Chat reply, no retrieval, no LLM
           POLICY_ABSTENTION   -> Policy Abstention (out of scope / mixed), no retrieval, no LLM
           LEGAL_RETRIEVAL     -> RAGPipeline.run (retrieval -> confidence -> context -> Qwen -> Gate)
      -> AskResponse (answer only after Gate PASS; evidence, citations, disclaimer, timings)

Every stage emits a ``LogEvent`` with the same ``query_id`` (orchestration/events.py).
``RAGPipeline`` stays the only RAG pipeline: this module adds routing and the response
mapping around it, the batch runner keeps calling ``run_rag``.

Router input errors (``INVALID_*``) raise ``InvalidAskRequest`` (API: 422 ``INVALID_REQUEST``);
a router failure or a missing/unknown ``action`` raises ``RoutingFailed`` (API: 500
``INTERNAL_ERROR``). Errors after routing become ``status=ERROR`` with a stable ``error_code``.
No message carries the exception text, prompt or query.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol

from agent.config import GENERAL_CHAT_MESSAGE
from agent.router.adapter import RuleRouterAdapter
from generation.prompt_builder import STANDARD_DISCLAIMER
from orchestration.events import EventSink, FanOutSink, ListEventSink, NullEventSink, StageEmitter
from orchestration.rag_pipeline import (
    ABSTAIN_MESSAGE,
    CLARIFY_MESSAGE,
    FAIL_MESSAGE,
    RAGPipeline,
    RAGRunResult,
)
from retrieval.temporal import resolve_interactive_as_of_date
from schemas.models import (
    AskRequest,
    AskResponse,
    AskTimings,
    ErrorCode,
    ErrorDetail,
    LogEvent,
    RouteDecision,
)

OUT_OF_SCOPE_MESSAGE = (
    "Hệ thống hiện chỉ hỗ trợ câu hỏi về pháp luật Hôn nhân và gia đình. Câu hỏi này thuộc lĩnh vực pháp "
    "luật khác nên hệ thống không đưa ra kết luận; vui lòng tham khảo văn bản hoặc chuyên gia của lĩnh vực đó."
)
MIXED_SCOPE_MESSAGE = (
    "Câu hỏi có phần nằm ngoài phạm vi Hôn nhân và gia đình. Hệ thống không trả lời phần đó; vui lòng tách "
    "riêng phần câu hỏi về hôn nhân và gia đình để được tra cứu."
)
ERROR_MESSAGES: dict[str, str] = {
    "LLM_TIMEOUT": "Mô hình ngôn ngữ không phản hồi kịp. Vui lòng thử lại sau.",
    "INTERNAL_ERROR": "Hệ thống gặp lỗi khi xử lý câu hỏi. Vui lòng thử lại sau.",
}
# ``as_of_date`` provenance of retrieval.temporal -> contract literal
DATE_SOURCES = {"question": "query_text", "ui": "user_input", "today": "system_today"}
# Gate reasons that are citation problems (CITATION_INVALID); other FAIL reasons -> GROUNDING_FAIL
# (Gate checks in rag_pipeline + grounding/citation_validator.py reason codes).
CITATION_REASONS = frozenset({
    "EVIDENCE_INDEX_OUTSIDE_CONTEXT", "NON_INTEGER_EVIDENCE_INDEX", "ANSWER_MARKER_OUTSIDE_CONTEXT",
    "ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES", "ANSWER_CONTAINS_CHUNK_ID",
    "INVALID_CITATION_TYPE", "INVALID_EVIDENCE_INDEX", "MAPPER_INVALID_INDICES", "DUPLICATE_EVIDENCE_INDEX",
    "MISSING_CITATIONS", "INVALID_CITATION_INDEX", "DUPLICATE_CITATION_INDEX", "CITATION_INDEX_SET_MISMATCH",
    "CITATION_OUTSIDE_CONTEXT", "CITATION_PROVENANCE_MISMATCH",
})
# SRS 5.3.5: CITATION_*, INVALID_CITATION_*, SOURCE_MAP_* of grounding/citation_validator.py
CITATION_PREFIXES = ("CITATION_", "INVALID_CITATION_", "SOURCE_MAP_")
JSON_REASONS = frozenset({"LLM_OUTPUT_INVALID_JSON", "LLM_OUTPUT_TRUNCATED_JSON", "LLM_OUTPUT_RAW_TEXT",
                          "LLM_OUTPUT_TRUNCATED"})
SKIP_ACTIONS = {"GENERAL_CHAT": "general_chat", "POLICY_ABSTENTION": "policy_abstention"}
# Router input reason codes -> ApiError INVALID_REQUEST (HTTP 422), SRS 5.3.5
INVALID_INPUT_REASONS = frozenset({"INVALID_EMPTY_QUERY", "INVALID_QUERY_TYPE", "INVALID_AS_OF_DATE"})


class InvalidAskRequest(ValueError):
    """The router rejected the input (``INVALID_*``); the API answers 422 ``INVALID_REQUEST``."""

    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


class RoutingFailed(RuntimeError):
    """The router failed or returned an unsupported ``action``; the API answers 500 ``INTERNAL_ERROR``."""


def gate_fail_error_code(reason: str) -> ErrorCode:
    """Gate FAIL reason -> ``error_code`` (SRS 5.3.5); codes not in the table -> ``GROUNDING_FAIL``."""
    if reason in JSON_REASONS:
        return "JSON_INVALID"
    if reason in CITATION_REASONS or reason.startswith(CITATION_PREFIXES):
        return "CITATION_INVALID"
    return "GROUNDING_FAIL"


class Router(Protocol):
    """Dev 4's router behind the shared contract."""

    def route(self, *, query: str, query_id: str, as_of_date: str) -> RouteDecision: ...


def next_action(decision: RouteDecision) -> str:
    """``rag``, ``general_chat`` or ``policy_abstention``.

    Only the router's ``action`` decides (SRS 5.3.3). ``FAST_PATH`` has no approved responder
    yet, so it goes through RAG instead of answering from a template. A missing or unknown
    ``action`` is not read from ``route``: it raises ``ValueError`` (-> ``INTERNAL_ERROR``)."""
    if decision.action in ("LEGAL_RETRIEVAL", "FAST_PATH"):
        return "rag"
    if decision.action in SKIP_ACTIONS:
        return SKIP_ACTIONS[decision.action]
    raise ValueError(f"Router trả action không hỗ trợ: {decision.action!r}")


def new_query_id(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"q_{now:%Y%m%dT%H%M%S}_{uuid.uuid4().hex}"


@dataclass
class AskOutcome:
    response: AskResponse
    route: RouteDecision | None = None
    rag: RAGRunResult | None = None
    total_ms: float = 0.0
    events: list[LogEvent] = field(default_factory=list)


class AskService:
    """CLI and API call ``run``; dependencies are injected (fakes in tests, real modules in
    ``orchestration.wiring``)."""

    def __init__(self, router: Router, pipeline: RAGPipeline, *, sink: EventSink | None = None,
                 today: Any = None):
        self.router = router
        self.pipeline = pipeline
        self.sink = sink or NullEventSink()
        self._today = today  # callable returning a date, for tests

    def _resolve_date(self, request: AskRequest) -> tuple[str, str]:
        today = self._today() if callable(self._today) else None
        if today is not None and not isinstance(today, date):
            raise TypeError("today() phải trả datetime.date")
        resolved, source = resolve_interactive_as_of_date(request.query, request.as_of_date, today=today)
        return resolved, DATE_SOURCES[source]

    def run(self, request: AskRequest, *, query_id: str | None = None, sink: EventSink | None = None) -> AskOutcome:
        """``query_id`` from the caller (API) wins, then ``request.query_id``, then a new one."""
        started = time.perf_counter()
        query_id = query_id or request.query_id or new_query_id()
        collector = ListEventSink()
        events = StageEmitter(query_id, FanOutSink([self.sink, sink, collector]))
        as_of_date, as_of_date_source = self._resolve_date(request)

        try:
            route = self.router.route(query=request.query, query_id=query_id, as_of_date=as_of_date)
            action = next_action(route)
        except Exception as exc:  # noqa: BLE001 - typed for the caller, details only in the log
            reason = getattr(getattr(exc, "reason_code", None), "value", getattr(exc, "reason_code", None))
            if reason in INVALID_INPUT_REASONS:
                events.emit("router", "route_rejected", "error", error_code="INVALID_REQUEST", reason_code=reason)
                raise InvalidAskRequest(reason) from None
            events.emit("router", "route_failed", "error", error_code="INTERNAL_ERROR",
                        error_type=type(exc).__name__)
            raise RoutingFailed("router failed") from None
        events.emit("router", "route_decided", "ok", route=route.route, reason_code=route.reason_code,
                    action=route.action, fast_path=route.fast_path, matched_rule_id=route.matched_rule_id,
                    policy_version=route.policy_version, as_of_date=as_of_date,
                    as_of_date_source=as_of_date_source)

        rag: RAGRunResult | None = None
        if action == "general_chat":
            fields: dict[str, Any] = {"status": "SUCCESS", "grounding_status": "NOT_RUN",
                                      "answer": GENERAL_CHAT_MESSAGE}
        elif action == "policy_abstention":
            message = OUT_OF_SCOPE_MESSAGE if route.route == "LEGAL_OUT_OF_SCOPE" else MIXED_SCOPE_MESSAGE
            fields = {"status": "ABSTAIN", "grounding_status": "NOT_RUN", "abstention_message": message,
                      "abstention_reason": route.reason_code, "error_code": "ROUTE_POLICY"}
        else:
            try:
                rag = self.pipeline.run(query_id=query_id, query=request.query, as_of_date=as_of_date,
                                        as_of_date_source=as_of_date_source, events=events)
                fields = self._rag_fields(rag, as_of_date)
            except Exception as exc:  # noqa: BLE001 - mapped to a typed error, details only in the log
                code: ErrorCode = getattr(exc, "error_code", None) or "INTERNAL_ERROR"
                if code not in ERROR_MESSAGES:
                    code = "INTERNAL_ERROR"
                events.emit("response", "pipeline_failed", "error", error_code=code, error_type=type(exc).__name__,
                            retryable=code == "LLM_TIMEOUT")
                fields = {"status": "ERROR", "grounding_status": "NOT_RUN", "error_code": code,
                          "error": ErrorDetail(message=ERROR_MESSAGES[code], retryable=code == "LLM_TIMEOUT")}

        total_ms = round((time.perf_counter() - started) * 1000.0, 2)
        breakdown = rag.record.latency_breakdown.model_dump() if rag is not None else {}
        response = AskResponse(query_id=query_id, request_id=request.request_id, as_of_date=as_of_date,
                               as_of_date_source=as_of_date_source, route=route.route,
                               disclaimer=STANDARD_DISCLAIMER, timings=AskTimings(**breakdown, total_ms=total_ms),
                               **fields)
        events.emit("response", "response_built", response.status, duration_ms=total_ms,
                    error_code=response.error_code, total_ms=total_ms, route=response.route,
                    grounding_status=response.grounding_status, citation_count=len(response.citations),
                    evidence_count=len(response.evidence), llm_calls=sum(e.event_type == "generation_started" for e in collector.events))
        return AskOutcome(response=response, route=route, rag=rag, total_ms=total_ms, events=collector.events)

    @staticmethod
    def _rag_fields(rag: RAGRunResult, as_of_date: str) -> dict[str, Any]:
        """AskResponse fields for a RAG run; the model text is only used after Gate PASS."""
        record, grounding = rag.record, rag.grounding
        status = record.grounding_status
        if status == "PASS":
            if rag.llm_response is None or rag.payload is None:
                raise RuntimeError("Gate PASS cần LLMResponse và ContextPayload")
            return {"status": "SUCCESS", "grounding_status": "PASS", "answer": rag.llm_response.answer.strip(),
                    "citations": list(record.citations), "evidence": list(rag.payload.evidence_items)}
        if status == "NEEDS_CLARIFICATION":
            return {"status": "NEEDS_CLARIFICATION", "grounding_status": "NEEDS_CLARIFICATION",
                    "clarification": CLARIFY_MESSAGE}
        reason = record.abstention_reason or (grounding.reason if grounding else None) or status
        if status == "ABSTAIN":
            code: ErrorCode | None = {"EMPTY_RETRIEVAL": "RETRIEVAL_EMPTY",
                                      "LOW_CONFIDENCE": "LOW_CONFIDENCE"}.get(reason)
            return {"status": "ABSTAIN", "grounding_status": "NOT_RUN" if code else "ABSTAIN",
                    "abstention_message": ABSTAIN_MESSAGE.format(as_of_date=as_of_date),
                    "abstention_reason": reason, "error_code": code}
        # Gate FAIL: the draft stays in the record trace, the user gets the no-conclusion message.
        return {"status": "ABSTAIN", "grounding_status": "FAIL", "abstention_message": FAIL_MESSAGE,
                "abstention_reason": reason, "error_code": gate_fail_error_code(reason)}


__all__ = [
    "AskOutcome", "AskService", "GENERAL_CHAT_MESSAGE", "InvalidAskRequest", "MIXED_SCOPE_MESSAGE",
    "OUT_OF_SCOPE_MESSAGE", "Router", "RoutingFailed", "RuleRouterAdapter", "gate_fail_error_code", "new_query_id",
    "next_action",
]
