from unittest.mock import MagicMock

import pytest

pytest.importorskip("streamlit")

from frontend.components import evidence_panel  # noqa: E402


@pytest.mark.req("FR4.3-AC2")
@pytest.mark.parametrize(
    ("as_of_date", "expected"),
    [
        ("1987-01-02", "Chưa có hiệu lực"),
        ("1987-01-03", "Còn hiệu lực"),
        ("1995-06-01", "Còn hiệu lực"),
        ("2001-01-01", "Hết hiệu lực"),
    ],
)
def test_evidence_panel_labels_historical_effectivity(monkeypatch, as_of_date, expected):
    streamlit = MagicMock()
    monkeypatch.setattr(evidence_panel, "st", streamlit)

    evidence_panel.render_evidence_panel({
        "as_of_date": as_of_date,
        "citations": [{"evidence_index": 1}],
        "evidence": [{
            "evidence_index": 1,
            "document_title": "Luật Hôn nhân và Gia đình 1986",
            "effective_from": "1987-01-03",
            "effective_to": "2001-01-01",
            "validity_status": "Hết hiệu lực",
        }],
    })

    streamlit.caption.assert_any_call(f"Hiệu lực tại {as_of_date}: {expected}")
    streamlit.caption.assert_any_call("Tình trạng hiện nay: Hết hiệu lực")
