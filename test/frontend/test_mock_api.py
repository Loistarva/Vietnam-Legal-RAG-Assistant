"""Mock responses used by the Streamlit D2.5 UI checks."""

from __future__ import annotations

import pytest
import requests

from frontend.mock_api import ask


@pytest.mark.parametrize(
    ("marker", "status", "required_field"),
    [
        ("[mock:success]", "SUCCESS", "answer"),
        ("[mock:clarify]", "NEEDS_CLARIFICATION", "clarification"),
        ("[mock:abstain]", "ABSTAIN", "abstention_message"),
        ("[mock:error]", "ERROR", "error"),
    ],
)
def test_status_fixtures_follow_ask_response_contract(marker, status, required_field):
    response = ask(marker)

    assert response["status"] == status
    assert response[required_field]
    assert response["disclaimer"]


def test_success_fixture_has_citations_and_evidence_without_point_field():
    response = ask("[mock:success]")

    assert response["citations"][0]["evidence_index"] == 1
    assert response["evidence"][0]["evidence_index"] == 1
    assert response["evidence"][0]["article_number"]
    assert response["evidence"][0]["clause_number"]
    assert "point_ref" not in response["evidence"][0]


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
