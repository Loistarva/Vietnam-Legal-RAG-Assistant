"""Build AskResponse fields according to the SRS 5.3.4 status/HTTP and 5.3.5 detail-code tables.

The tables define the public error groups; add a row there when adding a detail code.
"""
from __future__ import annotations

from typing import Any

from generation.prompt_builder import STANDARD_DISCLAIMER
from orchestration.rag_pipeline import (
    ABSTAIN_MESSAGE,
    CLARIFY_MESSAGE,
    FAIL_MESSAGE,
    RETRYABLE_ERROR_CODES,
    RAGRunResult,
)
from schemas.models import AskRequest, AskResponse, AskTimings, ErrorCode, ErrorDetail, RouteDecision

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
    "LLM_UNAVAILABLE": "Không kết nối được mô hình ngôn ngữ. Vui lòng thử lại sau.",
    "INTERNAL_ERROR": "Hệ thống gặp lỗi khi xử lý câu hỏi. Vui lòng thử lại sau.",
}
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


def gate_fail_error_code(reason: str) -> ErrorCode:
    """Gate FAIL reason -> ``error_code`` (SRS 5.3.5); codes not in the table -> ``GROUNDING_FAIL``."""
    if reason in JSON_REASONS:
        return "JSON_INVALID"
    if reason in CITATION_REASONS or reason.startswith(CITATION_PREFIXES):
        return "CITATION_INVALID"
    return "GROUNDING_FAIL"


def general_chat_fields() -> dict[str, Any]:
    return {"status": "SUCCESS", "grounding_status": "NOT_RUN", "answer": GENERAL_CHAT_MESSAGE}


def policy_abstention_fields(route: RouteDecision) -> dict[str, Any]:
    message = OUT_OF_SCOPE_MESSAGE if route.route == "LEGAL_OUT_OF_SCOPE" else MIXED_SCOPE_MESSAGE
    return {"status": "ABSTAIN", "grounding_status": "NOT_RUN", "abstention_message": message,
            "abstention_reason": route.reason_code, "error_code": "ROUTE_POLICY"}


def pipeline_error_fields(exc: BaseException) -> tuple[dict[str, Any], ErrorCode]:
    code: ErrorCode = getattr(exc, "error_code", None) or "INTERNAL_ERROR"
    if code not in ERROR_MESSAGES:
        code = "INTERNAL_ERROR"
    error = ErrorDetail(message=ERROR_MESSAGES[code], retryable=code in RETRYABLE_ERROR_CODES)
    return {"status": "ERROR", "grounding_status": "NOT_RUN", "error_code": code, "error": error}, code


def rag_fields(rag: RAGRunResult, as_of_date: str) -> dict[str, Any]:
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


def build_ask_response(*, query_id: str, request: AskRequest, as_of_date: str, as_of_date_source: str,
                       route: RouteDecision, fields: dict[str, Any], rag: RAGRunResult | None,
                       total_ms: float) -> AskResponse:
    breakdown = rag.record.latency_breakdown.model_dump() if rag is not None else {}
    return AskResponse(query_id=query_id, request_id=request.request_id, as_of_date=as_of_date,
                       as_of_date_source=as_of_date_source, route=route.route, disclaimer=STANDARD_DISCLAIMER,
                       timings=AskTimings(**breakdown, total_ms=total_ms), **fields)
