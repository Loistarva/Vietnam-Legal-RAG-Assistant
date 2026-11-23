"""Contract-shaped local responses for developing the Streamlit UI."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any
from uuid import uuid4

import requests

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


def _mock_evidence(
    evidence_index: int,
    *,
    content: str | None = None,
) -> dict[str, Any]:
    """Create clearly synthetic evidence for exercising the UI layout."""
    evidence = deepcopy(_MOCK_EVIDENCE)
    evidence.update(
        {
            "evidence_index": evidence_index,
            "chunk_id": f"mock_chunk_{evidence_index:03d}",
            "parent_clause_id": f"mock_clause_{evidence_index:03d}",
            "document_id": f"mock_document_{evidence_index:03d}",
            "article_id": f"mock_article_{evidence_index:03d}",
            "clause_id": f"mock_clause_{evidence_index:03d}",
            "document_number": f"MOCK-{evidence_index:03d}",
            "document_title": f"Tài liệu giả lập {evidence_index} (không phải văn bản pháp luật)",
            "article_number": str(evidence_index),
            "clause_number": "1",
            "breadcrumb": f"Tài liệu giả lập > Điều {evidence_index} > Khoản 1",
            "content": content or f"[Nội dung căn cứ giả lập số {evidence_index}.]",
        }
    )
    return evidence


def _mock_citation(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        key: evidence[key]
        for key in (
            "evidence_index",
            "chunk_id",
            "document_id",
            "article_id",
            "clause_id",
            "parent_clause_id",
        )
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
    ``[mock:low]``, ``[mock:gate_fail]``, ``[mock:bad_json]``,
    ``[mock:timeout]``, ``[mock:network_timeout]``, ``[mock:out_of_scope]``,
    ``[mock:many_evidence]`` or ``[mock:long_evidence]``.
    The latter two contain synthetic display text only. A greeting previews the
    non-legal fast path.
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

    if "[mock:network_timeout]" in normalized:
        raise requests.Timeout("Mock network timeout for frontend QA.")

    if "[mock:out_of_scope]" in normalized:
        return _response(
            status="ABSTAIN",
            route="LEGAL_OUT_OF_SCOPE",
            grounding_status="NOT_RUN",
            abstention_message=(
                "Câu hỏi giả lập nằm ngoài phạm vi pháp luật Hôn nhân và gia đình."
            ),
            abstention_reason="OUT_OF_SCOPE",
            error_code="ROUTE_POLICY",
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

    if "[mock:many_evidence]" in normalized:
        evidence = [_mock_evidence(index) for index in range(1, 4)]
        return _response(
            status="SUCCESS",
            route="LEGAL_IN_SCOPE",
            grounding_status="PASS",
            answer=(
                "Phản hồi giả lập có ba căn cứ để kiểm tra liên kết citation: "
                "[1] [2] [3]. Nội dung này không phải thông tin pháp lý."
            ),
            citations=[_mock_citation(item) for item in evidence],
            evidence=evidence,
            **common,
        )

    if "[mock:long_evidence]" in normalized:
        long_content = (
            "[NỘI DUNG GIẢ LẬP DÀI — KHÔNG PHẢI VĂN BẢN PHÁP LUẬT]\n\n"
            + ("Đoạn văn mẫu để kiểm tra cuộn và hiển thị nội dung dài. " * 180)
        )
        evidence = [_mock_evidence(1, content=long_content)]
        return _response(
            status="SUCCESS",
            route="LEGAL_IN_SCOPE",
            grounding_status="PASS",
            answer=(
                "Phản hồi giả lập có một căn cứ dài để kiểm tra Evidence Panel. "
                "Nội dung này không phải thông tin pháp lý. [1]"
            ),
            citations=[_mock_citation(evidence[0])],
            evidence=evidence,
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
