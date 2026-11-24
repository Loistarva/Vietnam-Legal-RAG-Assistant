"""Rendering checks for citation links and the Evidence Panel."""

from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import Mock

import frontend.components.evidence_panel as evidence_panel


def _evidence(index: int, *, content: str = "Nội dung căn cứ tiếng Việt.") -> dict:
    return {
        "evidence_index": index,
        "chunk_id": f"chunk-{index}",
        "document_id": f"document-{index}",
        "article_id": f"article-{index}",
        "clause_id": f"clause-{index}",
        "parent_clause_id": f"parent-{index}",
        "document_title": f"Luật giả lập {index}",
        "document_number": f"{index}/2026/QH15",
        "article_number": "Điều 8",
        "clause_number": "Khoản 1",
        "breadcrumb": "Luật giả lập > Điều 8 > Khoản 1",
        "content": content,
        "validity_status": "in_force",
        "effective_from": "2026-01-01",
        "effective_to": None,
    }


def _patch_streamlit(monkeypatch):
    markdown = Mock()
    button = Mock(return_value=False)
    writes = []
    captions = []
    containers = []
    monkeypatch.setattr(evidence_panel.st, "markdown", markdown)
    monkeypatch.setattr(evidence_panel.st, "button", button)
    monkeypatch.setattr(evidence_panel.st, "write", writes.append)
    monkeypatch.setattr(evidence_panel.st, "caption", captions.append)
    monkeypatch.setattr(evidence_panel.st, "expander", lambda *a, **k: nullcontext())

    def container(*args, **kwargs):
        containers.append(kwargs)
        return nullcontext()

    monkeypatch.setattr(evidence_panel.st, "container", container)
    monkeypatch.setattr(evidence_panel.st, "link_button", Mock())
    monkeypatch.setattr(evidence_panel.st, "success", Mock())
    return markdown, button, writes, captions, containers


def test_citation_markers_link_to_matching_evidence(monkeypatch):
    _, button, _, _, _ = _patch_streamlit(monkeypatch)
    payload = {
        "query_id": "q-vietnamese",
        "citations": [{"evidence_index": 1}, {"evidence_index": 2}],
        "evidence": [_evidence(1), _evidence(2)],
    }

    evidence_panel.render_answer_with_citations(
        "Câu trả lời tiếng Việt [1], đồng thời căn cứ [2].", payload
    )

    assert [call.args[0] for call in button.call_args_list] == [
        "[1] Luật giả lập 1",
        "[2] Luật giả lập 2",
    ]
    assert [call.kwargs["args"] for call in button.call_args_list] == [
        ("q-vietnamese", 1),
        ("q-vietnamese", 2),
    ]


def test_evidence_panel_shows_metadata_date_and_scrolls_long_content(monkeypatch):
    markdown, _, writes, captions, containers = _patch_streamlit(monkeypatch)
    payload = {
        "query_id": "q-long",
        "as_of_date": "2026-11-23",
        "citations": [{"evidence_index": 1}],
        "evidence": [_evidence(1, content="Nội dung dài. " * 100)],
    }

    evidence_panel.render_evidence_panel(payload)

    rendered = " ".join(str(item) for item in writes)
    headings = " ".join(call.args[0] for call in markdown.call_args_list)
    assert "Luật giả lập 1" in headings
    assert "1/2026/QH15" in headings
    assert "Nội dung dài." in rendered
    assert any("Hiệu lực tại 2026-11-23" in caption for caption in captions)
    assert any(container.get("height") == 260 for container in containers)


def test_evidence_panel_explains_when_response_has_no_citations(monkeypatch):
    _, _, writes, _, _ = _patch_streamlit(monkeypatch)

    evidence_panel.render_evidence_panel(
        {"query_id": "q-empty", "citations": [], "evidence": []}
    )

    assert writes == ["Phản hồi này không có citation hoặc căn cứ evidence để hiển thị."]
