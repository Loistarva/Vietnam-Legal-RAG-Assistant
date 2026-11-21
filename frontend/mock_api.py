"""Contract-shaped local responses for developing the Streamlit UI."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from schemas.models import AskResponse, SCHEMA_VERSION


DISCLAIMER = (
    "Dữ liệu giả lập chỉ dùng để kiểm tra giao diện, không phải tư vấn pháp lý."
)

_MOCK_EVIDENCE = {
    "evidence_index": 1,
    "chunk_id": "mock_chunk_001",
    "parent_clause_id": "mock_clause_001",
    "document_id": "mock_document_001",
    "article_id": "mock_article_001",
    "clause_id": "mock_clause_001",
    "content": "[Nội dung căn cứ giả lập để kiểm tra Evidence Panel.]",
    "validity_status": "unknown_mock",
    "effective_from": None,
    "effective_to": None,
    "source_url": None,
    "document_number": None,
    "document_title": "Văn bản giả lập (không phải nguồn pháp luật)",
    "article_number": "Điều giả lập",
    "clause_number": "Khoản giả lập",
    "breadcrumb": "Văn bản giả lập > Điều giả lập > Khoản giả lập",
    "provision_status": "mock",
}


def _response(
    *,
    status: str,
    route: str,
    grounding_status: str,
    as_of_date: str | None,
    request_id: str | None,
    **fields: Any,
) -> dict[str, Any]:
    """Build and validate every fixture against the canonical API response."""
    result = AskResponse(
        schema_version=SCHEMA_VERSION,
        query_id=f"q_mock_{uuid4().hex[:12]}",
        request_id=request_id,
        as_of_date=as_of_date or date.today().isoformat(),
        as_of_date_source="user_input" if as_of_date else "system_today",
        status=status,
        route=route,
        grounding_status=grounding_status,
        disclaimer=DISCLAIMER,
        timings={
            "total_ms": 12.0,
            "retrieval_ms": 4.0,
            "llm_total_ms": 8.0,
            "ttft_model_ms": None,
        },
        **fields,
    )
    return result.model_dump(mode="json")


def ask(
    question: str,
    as_of_date: str | None = None,
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return a contract-shaped mock response for one question.

    Add one marker to the question to preview a specific UI state:
    ``[mock:clarify]``, ``[mock:abstain]``, ``[mock:empty]``,
    ``[mock:low]``, ``[mock:gate_fail]``, ``[mock:bad_json]`` or
    ``[mock:timeout]``. A greeting previews the non-legal fast path.
    """
    normalized = question.casefold()
    common = {
        "as_of_date": as_of_date,
        "request_id": request_id,
    }

    if "[mock:timeout]" in normalized:
        return _response(
            status="ERROR",
            route="LEGAL_IN_SCOPE",
            grounding_status="NOT_RUN",
            error_code="LLM_TIMEOUT",
            error={"message": "Mô phỏng Qwen timeout.", "retryable": True},
            **common,
        )

    if "[mock:clarify]" in normalized:
        return _response(
            status="NEEDS_CLARIFICATION",
            route="LEGAL_IN_SCOPE",
            grounding_status="NEEDS_CLARIFICATION",
            clarification="Bạn vui lòng bổ sung thời điểm và tình tiết liên quan để hệ thống minh họa trạng thái hỏi lại.",
            **common,
        )

    if "[mock:gate_fail]" in normalized or "[mock:bad_json]" in normalized:
        error_code = "CITATION_INVALID" if "[mock:gate_fail]" in normalized else "JSON_INVALID"
        return _response(
            status="ABSTAIN",
            route="LEGAL_IN_SCOPE",
            grounding_status="FAIL",
            abstention_message="Bản nháp giả lập không qua Grounding Gate nên không được hiển thị.",
            abstention_reason=error_code,
            error_code=error_code,
            **common,
        )

    if "[mock:empty]" in normalized or "[mock:low]" in normalized:
        empty = "[mock:empty]" in normalized
        code = "RETRIEVAL_EMPTY" if empty else "LOW_CONFIDENCE"
        return _response(
            status="ABSTAIN",
            route="LEGAL_IN_SCOPE",
            grounding_status="ABSTAIN",
            abstention_message=(
                "Mock không tìm thấy căn cứ phù hợp."
                if empty
                else "Mock có độ tin cậy thấp nên chưa thể trả lời."
            ),
            abstention_reason=code,
            error_code=code,
            **common,
        )

    if "[mock:abstain]" in normalized:
        return _response(
            status="ABSTAIN",
            route="LEGAL_IN_SCOPE",
            grounding_status="ABSTAIN",
            abstention_message="Đây là lời từ chối giả lập để xem trước giao diện.",
            abstention_reason="MODEL_ABSTAINED",
            **common,
        )

    if not question.strip() or any(
        word in normalized for word in ("xin chào", "hello", "chào")
    ):
        answer = "Xin chào! Đây là phản hồi giả lập để xem trước giao diện."
        return _response(
            status="SUCCESS",
            route="NON_LEGAL",
            grounding_status="NOT_RUN",
            answer=answer,
            **common,
        )

    return _response(
        status="SUCCESS",
        route="LEGAL_IN_SCOPE",
        grounding_status="PASS",
        answer="Đây là câu trả lời giả lập để xem bố cục giao diện; không phải kết luận pháp lý. [1]",
        citations=[
            {
                "evidence_index": 1,
                "chunk_id": _MOCK_EVIDENCE["chunk_id"],
                "document_id": _MOCK_EVIDENCE["document_id"],
                "article_id": _MOCK_EVIDENCE["article_id"],
                "clause_id": _MOCK_EVIDENCE["clause_id"],
                "parent_clause_id": _MOCK_EVIDENCE["parent_clause_id"],
            }
        ],
        evidence=[_MOCK_EVIDENCE],
        **common,
    )
