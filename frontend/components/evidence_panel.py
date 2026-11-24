"""Citation and evidence rendering for AskResponse payloads."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import streamlit as st


_CITATION_MARKER = re.compile(r"\[(\d+)\]")
_EVIDENCE_SCROLL_THRESHOLD_CHARS = 900
_EVIDENCE_SCROLL_HEIGHT_PX = 260


def _evidence_by_index(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        return {}
    return {
        item["evidence_index"]: item
        for item in evidence
        if isinstance(item, dict)
        and isinstance(item.get("evidence_index"), int)
    }


def render_answer_with_citations(answer: str, payload: dict[str, Any]) -> None:
    """Render answer text and actionable citation markers tied to evidence."""
    evidence_by_index = _evidence_by_index(payload)
    citations = payload.get("citations")
    cited_indices = {
        item.get("evidence_index")
        for item in citations or []
        if isinstance(item, dict) and isinstance(item.get("evidence_index"), int)
    }
    cited_indices.intersection_update(evidence_by_index)

    pieces = _CITATION_MARKER.split(answer)
    for index, piece in enumerate(pieces):
        if index % 2 == 0:
            if piece:
                st.markdown(piece)
            continue
        evidence_index = int(piece)
        if evidence_index in cited_indices:
            evidence = evidence_by_index[evidence_index]
            title = evidence.get("document_title") or f"Căn cứ [{evidence_index}]"
            st.button(
                f"[{evidence_index}] {title}",
                key=f"citation_{payload.get('query_id', 'response')}_{evidence_index}",
                on_click=_select_evidence,
                args=(payload.get("query_id", "response"), evidence_index),
                help="Mở căn cứ tương ứng trong Evidence Panel.",
            )
        else:
            st.markdown(f"[{evidence_index}]")


def _select_evidence(query_id: str, evidence_index: int) -> None:
    st.session_state[f"selected_evidence_{query_id}"] = evidence_index


def render_evidence_panel(payload: dict[str, Any]) -> None:
    """Show citation metadata and the exact evidence item for each citation."""
    evidence_by_index = _evidence_by_index(payload)
    citations = payload.get("citations")
    citations = citations if isinstance(citations, list) else []
    cited_indices = [
        item.get("evidence_index")
        for item in citations
        if isinstance(item, dict) and isinstance(item.get("evidence_index"), int)
    ]
    query_id = str(payload.get("query_id") or "response")
    selected_index = st.session_state.get(f"selected_evidence_{query_id}")

    with st.expander("Căn cứ pháp lý (Evidence Panel)", expanded=True):
        if not cited_indices:
            st.write("Không có căn cứ trích dẫn.")
            return

        for evidence_index in cited_indices:
            item = evidence_by_index.get(evidence_index)
            if item is None:
                continue
            title = item.get("document_title") or "Văn bản pháp luật"
            number = item.get("document_number")
            provision = " · ".join(
                str(item[key])
                for key in ("article_number", "clause_number", "point_ref")
                if item.get(key)
            )
            heading = f"[{evidence_index}] {title}"
            if number:
                heading += f" ({number})"
            if provision:
                heading += f" · {provision}"

            with st.container(border=True):
                st.markdown(f"**{heading}**")
                breadcrumb = item.get("breadcrumb")
                if breadcrumb:
                    st.caption(breadcrumb)
                content = item.get("content")
                if content:
                    if len(content) > _EVIDENCE_SCROLL_THRESHOLD_CHARS:
                        with st.container(
                            height=_EVIDENCE_SCROLL_HEIGHT_PX, border=False
                        ):
                            st.write(content)
                    else:
                        st.write(content)
                as_of_date = payload.get("as_of_date")
                if as_of_date:
                    st.caption(f"Hiệu lực tại {as_of_date}: {_effectivity_at(item, as_of_date)}")
                validity = item.get("validity_status") or item.get("provision_status")
                if validity:
                    st.caption(f"Tình trạng hiện nay: {validity}")
                source_url = item.get("source_url")
                if source_url:
                    st.link_button("Mở nguồn văn bản", source_url)
                if selected_index == evidence_index:
                    st.success("Căn cứ được chọn từ ký hiệu citation trong câu trả lời.")


def _effectivity_at(item: dict[str, Any], as_of_date: str) -> str:
    try:
        target = date.fromisoformat(as_of_date)
        start = date.fromisoformat(item["effective_from"]) if item.get("effective_from") else None
        end = date.fromisoformat(item["effective_to"]) if item.get("effective_to") else None
    except (TypeError, ValueError):
        return "Chưa đủ dữ liệu"
    if end is not None and target >= end:
        return "Hết hiệu lực"
    if start is None:
        return "Chưa đủ dữ liệu"
    if target < start:
        return "Chưa có hiệu lực"
    return "Còn hiệu lực"
