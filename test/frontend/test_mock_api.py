"""Mock responses used by the Streamlit D2.5 UI checks."""

from __future__ import annotations

import pytest
import requests

from frontend.mock_api import ask


@pytest.mark.req("IR1.3-AC1")
def test_out_of_scope_mock_returns_abstention_without_answer():
    response = ask("[mock:out_of_scope]")

    assert response["status"] == "ABSTAIN"
    assert response["route"] == "LEGAL_OUT_OF_SCOPE"
    assert response["grounding_status"] == "NOT_RUN"
    assert response["answer"] is None
    assert response["citations"] == []


@pytest.mark.req("IR1.3-AC2")
def test_network_timeout_marker_raises_requests_timeout():
    with pytest.raises(requests.Timeout):
        ask("[mock:network_timeout]")
