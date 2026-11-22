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

Errors after routing become ``status=ERROR`` with a stable ``error_code`` and a message
that never carries the exception text, prompt or query.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol

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
    map_router_route_to_canonical,
)

GENERAL_CHAT_MESSAGE = (
    "Tôi là trợ lý tra cứu pháp luật Hôn nhân và gia đình Việt Nam nên không trả lời các câu hỏi ngoài pháp "
    "luật. Bạn có thể hỏi về kết hôn, ly hôn, tài sản vợ chồng, nuôi con, cấp dưỡng hoặc quan hệ giữa cha mẹ và con."
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
JSON_REASONS = frozenset({"LLM_OUTPUT_INVALID_JSON", "LLM_OUTPUT_TRUNCATED_JSON", "LLM_OUTPUT_TRUNCATED"})
SKIP_ACTIONS = {"GENERAL_CHAT": "general_chat", "POLICY_ABSTENTION": "policy_abstention"}


class Router(Protocol):
    """Dev 4's router behind the shared contract."""

    def route(self, *, query: str, query_id: str, as_of_date: str) -> RouteDecision: ...


class RuleRouterAdapter:
    """``agent.router.rule_router.RuleRouter`` -> contract ``RouteDecision``.

    Only the public ``route()`` result is read; route labels go through
    ``schemas.models.map_router_route_to_canonical`` (Dev 3's mapping table)."""

    def __init__(self, router: Any | None = None):
        if router is None:
            from agent.router.rule_router import RuleRouter

            router = RuleRouter()
        self.router = router

    def route(self, *, query: str, query_id: str, as_of_date: str) -> RouteDecision:
        decision = self.router.route(query, query_id=query_id, as_of_date=as_of_date, source="ask_service")
        reason = decision.route_reason.value
        return RouteDecision(
            route=map_router_route_to_canonical(decision.route.value),
            reason_code=reason,
            explanation=f"{decision.route.value} -> {decision.action.value} ({reason})",
            policy_version=decision.classifier_version,
            query_id=query_id,
            action=decision.action.value,
            matched_rule_id=decision.matched_rule_id,
            fast_path=bool(decision.fast_path),
            as_of_date=as_of_date,
        )


def next_action(decision: RouteDecision) -> str:
    """``rag``, ``general_chat`` or ``policy_abstention``.

    The router's ``action`` decides. ``FAST_PATH`` has no approved responder yet, so it goes
    through RAG instead of answering from a template. A router without ``action`` is read by
    route, and ``MIXED_REVIEW`` / ``LEGAL_OUT_OF_SCOPE`` abstain (plan Sprint 10, section 3.2)."""
    if decision.action in ("LEGAL_RETRIEVAL", "FAST_PATH"):
        return "rag"
    if decision.action in SKIP_ACTIONS:
        return SKIP_ACTIONS[decision.action]
    if decision.action is not None:
        raise ValueError(f"Router trả action không hỗ trợ: {decision.action!r}")
    return {"LEGAL_IN_SCOPE": "rag", "NON_LEGAL": "general_chat"}.get(decision.route, "policy_abstention")


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

        route = self.router.route(query=request.query, query_id=query_id, as_of_date=as_of_date)
        action = next_action(route)
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
        events.emit("response", "response_built", response.status, duration_ms=total_ms, route=response.route,
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
        if reason in JSON_REASONS:
            fail_code: ErrorCode = "JSON_INVALID"
        elif reason in CITATION_REASONS:
            fail_code = "CITATION_INVALID"
        else:
            fail_code = "GROUNDING_FAIL"
        return {"status": "ABSTAIN", "grounding_status": "FAIL", "abstention_message": FAIL_MESSAGE,
                "abstention_reason": reason, "error_code": fail_code}


__all__ = [
    "AskOutcome", "AskService", "GENERAL_CHAT_MESSAGE", "MIXED_SCOPE_MESSAGE", "OUT_OF_SCOPE_MESSAGE", "Router",
    "RuleRouterAdapter", "new_query_id", "next_action",
]
