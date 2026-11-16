"""Streamlit chat prototype for the Vietnam Legal RAG Assistant.

Run with ``streamlit run frontend/streamlit_app.py``. The default demo mode uses
local mock data, so the UI can be developed before the API is available.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
import streamlit as st

from mock_api import ask as mock_ask


DEFAULT_API_URL = os.getenv("LEGAL_RAG_API_URL", "http://127.0.0.1:8000/api/v1/ask")
REQUEST_TIMEOUT_SECONDS = 60


def api_ask(question: str, api_url: str, api_key: str) -> dict[str, Any]:
    """Call the future FastAPI endpoint; the request body follows the v1 draft."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    response = requests.post(
        api_url,
        json={"query": question},
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("API response phải là một JSON object.")
    return payload


def render_result(payload: dict[str, Any]) -> None:
    status = str(payload.get("status") or payload.get("grounding_status") or "completed")
    status_labels = {
        "answered": "Đã có câu trả lời",
        "PASS": "Đã qua kiểm tra căn cứ",
        "needs_clarification": "Cần bạn làm rõ thêm",
        "NEEDS_CLARIFICATION": "Cần bạn làm rõ thêm",
        "abstained": "Chưa đủ căn cứ để trả lời",
        "ABSTAIN": "Chưa đủ căn cứ để trả lời",
    }
    st.caption(f"Trạng thái: {status_labels.get(status, status)}")

    answer = payload.get("answer") or payload.get("final_answer") or payload.get("message")
    if answer:
        st.markdown(answer)
    elif status.lower() in {"needs_clarification", "abstain", "abstained"}:
        st.info(payload.get("clarification_question") or payload.get("reason") or "Hệ thống chưa thể trả lời.")
    else:
        st.info("API chưa trả trường câu trả lời theo định dạng UI đang hỗ trợ.")

    citations = payload.get("citations") or payload.get("valid_citations") or []
    if citations:
        with st.expander("Trích dẫn", expanded=True):
            for item in citations:
                if isinstance(item, dict):
                    label = item.get("document_name") or item.get("document_id") or "Văn bản pháp luật"
                    article = item.get("article") or item.get("article_id") or item.get("clause_id")
                    st.markdown(f"- **[{item.get('evidence_index', '?')}] {label}**" + (f" — {article}" if article else ""))
                else:
                    st.markdown(f"- {item}")

    evidence = payload.get("evidence") or payload.get("evidence_items") or []
    if evidence:
        with st.expander("Căn cứ pháp lý (Evidence Panel)", expanded=True):
            for item in evidence:
                if not isinstance(item, dict):
                    st.write(item)
                    continue
                title = item.get("title") or item.get("document_name") or f"Evidence [{item.get('evidence_index', '?')}]"
                with st.container(border=True):
                    st.markdown(f"**[{item.get('evidence_index', '?')}] {title}**")
                    excerpt = item.get("excerpt") or item.get("content") or item.get("text")
                    if excerpt:
                        st.write(excerpt)
                    source = item.get("source") or item.get("source_url")
                    if source:
                        st.caption(source)

    disclaimer = payload.get("disclaimer") or "Thông tin chỉ nhằm mục đích tham khảo, không thay thế tư vấn pháp lý."
    st.caption(f"⚖️ {disclaimer}")


def main() -> None:
    st.set_page_config(page_title="Trợ lý pháp lý Việt Nam", page_icon="⚖️", layout="centered")
    st.title("⚖️ Trợ lý pháp lý Việt Nam")
    st.write("Đặt câu hỏi để xem câu trả lời và căn cứ pháp lý được hệ thống sử dụng.")

    with st.sidebar:
        st.subheader("Kết nối")
        mode = st.radio("Nguồn phản hồi", ["Demo (mock)", "API"], index=0)
        api_url = st.text_input("API URL", value=DEFAULT_API_URL, disabled=mode != "API")
        api_key = st.text_input("API key", type="password", disabled=mode != "API", help="Không lưu hoặc ghi API key vào log.")
        if mode == "Demo (mock)":
            st.info("Đang dùng dữ liệu giả lập; nội dung không phải tư vấn pháp lý.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and isinstance(message.get("payload"), dict):
                render_result(message["payload"])
            else:
                st.markdown(message["content"])

    question = st.chat_input("Nhập câu hỏi pháp lý của bạn…")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.status("Đang xử lý câu hỏi…", expanded=False) as status_box:
                try:
                    if mode == "Demo (mock)":
                        time.sleep(0.35)
                        result = mock_ask(question)
                    else:
                        result = api_ask(question, api_url, api_key)
                    status_box.update(label="Đã nhận phản hồi", state="complete")
                    render_result(result)
                    st.session_state.messages.append({"role": "assistant", "payload": result})
                except requests.RequestException as exc:
                    status_box.update(label="Không kết nối được API", state="error")
                    st.error(f"Không gọi được API: {exc}")
                    st.session_state.messages.append({"role": "assistant", "content": "Không gọi được API. Kiểm tra URL và trạng thái backend rồi thử lại."})
                except (ValueError, TypeError) as exc:
                    status_box.update(label="Phản hồi không hợp lệ", state="error")
                    st.error(f"Không đọc được phản hồi: {exc}")
                    st.session_state.messages.append({"role": "assistant", "content": "API trả về dữ liệu không đúng định dạng UI mong đợi."})


if __name__ == "__main__":
    main()
