"""Schema & JSON Schema validation tests for Sprint 12 handoff fixtures (S12-D3.1)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from api.errors import ApiError
from generation.prompt_builder import build_clarification_message
from schemas.models import SCHEMA_VERSION, AskResponse

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "test" / "fixtures" / "sprint12"
ASK_RESPONSE_SCHEMA = ROOT / "schemas" / "generated" / "ask_response.schema.json"


def _load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    assert path.exists(), f"Thiếu fixture Sprint 12: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.req("FR3.4")
@pytest.mark.req("FR3.6")
@pytest.mark.req("FR6.4")
@pytest.mark.req("IR1.3")
@pytest.mark.req("IR2.1")
@pytest.mark.parametrize(
    "fixture_name,expected_status,expected_grounding_status",
    [
        ("ask_response_success_v1.1.json", "SUCCESS", "PASS"),
        ("ask_response_needs_clarification_v1.1.json", "NEEDS_CLARIFICATION", "NEEDS_CLARIFICATION"),
        ("ask_response_abstain_v1.1.json", "ABSTAIN", "NOT_RUN"),
        ("ask_response_error_llm_unavailable_v1.1.json", "ERROR", "NOT_RUN"),
    ],
)
def test_sprint12_ask_response_fixtures_validate_against_pydantic_and_json_schema(
    fixture_name: str,
    expected_status: str,
    expected_grounding_status: str,
):
    payload = _load_fixture(fixture_name)
    schema = json.loads(ASK_RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)

    parsed = AskResponse.model_validate(payload)
    assert parsed.schema_version == SCHEMA_VERSION == "week10_v1.1"
    assert parsed.status == expected_status
    assert parsed.grounding_status == expected_grounding_status


@pytest.mark.req("FR3.4")
@pytest.mark.req("FR3.6")
def test_sprint12_needs_clarification_fixture_matches_srs_4_2_and_config_template():
    payload = _load_fixture("ask_response_needs_clarification_v1.1.json")
    parsed = AskResponse.model_validate(payload)
    assert parsed.answer is None
    assert parsed.citations == []
    assert parsed.abstention_reason is None
    assert parsed.disclaimer
    assert parsed.clarification == build_clarification_message(
        ["ngay_su_kien", "tinh_trang_dang_ky_ket_hon"]
    )


@pytest.mark.req("FR6.4")
@pytest.mark.req("IR2.1")
def test_sprint12_api_error_llm_unavailable_fixture_validates():
    payload = _load_fixture("api_error_llm_unavailable_v1.1.json")
    parsed = ApiError.model_validate(payload)
    assert parsed.schema_version == SCHEMA_VERSION == "week10_v1.1"
    assert parsed.error_code == "LLM_UNAVAILABLE"
    assert parsed.message
