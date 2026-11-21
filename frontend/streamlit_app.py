"""Streamlit prototype for the Vietnam Legal RAG Assistant."""

from __future__ import annotations

import time
from datetime import date
import sys
from pathlib import Path
from uuid import uuid4

import requests
import streamlit as st

# Streamlit may put ``frontend/`` rather than the repository root on sys.path
# when launched as ``streamlit run frontend/streamlit_app.py``.
REPOSITORY_ROOT = str(Path(__file__).resolve().parents[1])
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

from frontend.api_client import ask as api_ask
from frontend.components.evidence_panel import (
    render_answer_with_citations,
    render_evidence_panel,
)
from frontend.config import MAX_AS_OF_DATE, MIN_AS_OF_DATE, load_config
from frontend.mock_api import ask as mock_ask


STATUS_LABELS = {
    "SUCCESS": "Đã có câu trả lời",
    "NEEDS_CLARIFICATION": "Cần bạn làm rõ thêm",
    "ABSTAIN": "Chưa đủ căn cứ để trả lời",
    "ERROR": "API gặp lỗi",
}
AS_OF_SOURCES = {
    "benchmark": "ngày của bộ câu hỏi",
    "query_text": "ngày trong câu hỏi",
    "user_input": "ngày bạn chọn",
    "system_today": "ngày hiện tại của hệ thống",
}
FALLBACK_DISCLAIMER = (
    "Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."
)


def render_result(payload: dict) -> None:
    """Render API response using its explicit status and canonical fields."""
    status = payload.get("status")
    st.caption(f"Trạng thái: {STATUS_LABELS.get(status, status or 'Không rõ')}")

    timings = payload.get("timings") or {}
    if not isinstance(timings, dict):
        timings = {}

    def format_ms(value: object) -> str:
        return f"{value:.0f} ms" if isinstance(value, (int, float)) else "—"

    st.caption(
        f"Route: {payload.get('route', '—')} · "
        f"Grounding: {payload.get('grounding_status', '—')} · "
        f"Latency tổng: {format_ms(timings.get('total_ms'))}"
    )
    st.caption(
        " · ".join(
            (
                f"Retrieval: {format_ms(timings.get('retrieval_ms'))}",
                f"LLM: {format_ms(timings.get('llm_total_ms'))}",
                f"TTFT: {format_ms(timings.get('ttft_model_ms'))}",
            )
        )
    )
    if payload.get("as_of_date"):
        source = AS_OF_SOURCES.get(
            payload.get("as_of_date_source"), payload.get("as_of_date_source", "không rõ nguồn")
        )
        st.caption(f"Thời điểm áp dụng: {payload['as_of_date']} ({source})")

    if status == "SUCCESS":
        answer = payload.get("answer")
        if answer:
            render_answer_with_citations(answer, payload)
        else:
            st.info("API chưa trả nội dung câu trả lời.")
        render_evidence_panel(payload)
    elif status == "NEEDS_CLARIFICATION":
        st.info(payload.get("clarification") or "Hệ thống cần thêm thông tin.")
    elif status == "ABSTAIN":
        st.info(payload.get("abstention_message") or "Hệ thống chưa đủ căn cứ để trả lời.")
        render_evidence_panel(payload)
    elif status == "ERROR":
        error = payload.get("error")
        message = error.get("message") if isinstance(error, dict) else None
        st.error(message or "API gặp lỗi khi xử lý câu hỏi.")
    else:
        st.error("API trả về status không được hỗ trợ.")

    # The API contract requires disclaimer in every user-visible response.
    disclaimer = payload.get("disclaimer")
    if disclaimer:
        st.caption(f"⚖️ {disclaimer}")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def main() -> None:
    config = load_config()
    st.set_page_config(page_title="Trợ lý pháp lý Việt Nam", page_icon="⚖️")
    st.title("⚖️ Trợ lý pháp lý Việt Nam")
    st.write("Đặt câu hỏi để xem câu trả lời và căn cứ pháp lý được hệ thống sử dụng.")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = _new_id("session")

    with st.sidebar:
        st.subheader("Kết nối")
        mode = st.radio("Nguồn phản hồi", ["Demo (mock)", "API"], index=0)
        st.markdown("**Thời điểm áp dụng pháp luật**")
        use_selected_date = st.checkbox("Tự chọn ngày tra cứu", value=False)
        selected_date = None
        if use_selected_date:
            selected_date = st.date_input(
                "Chọn ngày áp dụng pháp luật",
                value=date.today(),
                min_value=MIN_AS_OF_DATE,
                max_value=MAX_AS_OF_DATE,
            )
        else:
            st.caption("API sẽ xác định ngày áp dụng và trả về nguồn ngày.")
        if mode == "Demo (mock)":
            st.info("Dữ liệu giả lập chỉ để xem giao diện, không phải tư vấn pháp lý.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and isinstance(
                message.get("payload"), dict
            ):
                render_result(message["payload"])
            else:
                st.markdown(message["content"])
                if message.get("disclaimer"):
                    st.caption(f"⚖️ {message['disclaimer']}")

    question = st.chat_input("Nhập câu hỏi pháp lý của bạn…")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    request_id = _new_id("req")
    selected_date_text = selected_date.isoformat() if selected_date else None
    with st.chat_message("assistant"):
        with st.status("Đang xử lý câu hỏi…", expanded=False) as status_box:
            try:
                if mode == "Demo (mock)":
                    time.sleep(0.2)
                    result = mock_ask(
                        question,
                        as_of_date=selected_date_text,
                        request_id=request_id,
                    )
                else:
                    def update_progress(event: dict) -> None:
                        label = event.get("message") or event.get("stage")
                        if label:
                            status_box.update(label=str(label), state="running")

                    result = api_ask(
                        question,
                        api_url=config.api_url,
                        api_key=config.api_key,
                        as_of_date=selected_date_text,
                        session_id=st.session_state.session_id,
                        request_id=request_id,
                        timeout_seconds=config.request_timeout_seconds,
                        on_status=update_progress,
                    )
                status_box.update(label="Đã nhận phản hồi", state="complete")
                render_result(result)
                st.session_state.messages.append(
                    {"role": "assistant", "payload": result}
                )
            except requests.Timeout:
                status_box.update(label="API quá thời gian chờ", state="error")
                message = "API phản hồi quá chậm. Vui lòng thử lại sau."
                st.error(message)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": message,
                        "disclaimer": FALLBACK_DISCLAIMER,
                    }
                )
            except requests.RequestException:
                status_box.update(label="Không kết nối được API", state="error")
                message = "Không gọi được API. Hãy kiểm tra URL và trạng thái backend."
                st.error(message)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": message,
                        "disclaimer": FALLBACK_DISCLAIMER,
                    }
                )
            except (ValueError, TypeError) as exc:
                status_box.update(label="Phản hồi không hợp lệ", state="error")
                st.error(f"Không đọc được phản hồi từ API: {exc}")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": "API trả về dữ liệu không đúng định dạng.",
                        "disclaimer": FALLBACK_DISCLAIMER,
                    }
                )


if __name__ == "__main__":
    main()
