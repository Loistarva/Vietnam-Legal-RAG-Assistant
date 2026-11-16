"""Local mock responses for the Streamlit UI before the backend is available.

The payload shape is intentionally simple and is only a UI fixture. Replace
this module with the real API client once the backend contract is finalized.
"""

from __future__ import annotations

from typing import Any


DISCLAIMER = (
    "Đây là nội dung minh họa, không phải tư vấn pháp lý và chưa được hệ thống kiểm chứng."
)


def ask(question: str) -> dict[str, Any]:
    """Return a deterministic mock answer for a submitted question."""
    if not question.strip():
        return {
            "status": "needs_clarification",
            "clarification_question": "Bạn hãy nhập câu hỏi để bắt đầu.",
            "disclaimer": DISCLAIMER,
            "citations": [],
            "evidence": [],
        }

    if any(word in question.casefold() for word in ("xin chào", "hello", "chào")):
        return {
            "status": "answered",
            "answer": "Xin chào! Đây là phản hồi giả lập để xem trước giao diện.",
            "disclaimer": DISCLAIMER,
            "citations": [],
            "evidence": [],
        }

    return {
        "status": "answered",
        "answer": (
            "Theo dữ liệu minh họa, câu trả lời pháp lý cần dựa trên tình tiết cụ thể "
            "và quy định đang có hiệu lực. Nội dung này chỉ dùng để xem trước cách "
            "giao diện trình bày câu trả lời. [1]"
        ),
        "disclaimer": DISCLAIMER,
        "citations": [
            {
                "evidence_index": 1,
                "document_name": "Luật Hôn nhân và Gia đình (minh họa)",
                "article": "Điều 1 (ví dụ giao diện)",
            }
        ],
        "evidence": [
            {
                "evidence_index": 1,
                "title": "Điều 1 — căn cứ giả lập",
                "excerpt": (
                    "Đoạn văn này là dữ liệu giả để kiểm tra bố cục Evidence Panel; "
                    "không trích từ văn bản pháp luật."
                ),
                "source": "Mock data — không phải văn bản pháp luật",
            }
        ],
    }
