"""Contract tests for Week 10 canonical Pydantic models, JSON Schemas, and examples (D3.1)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import jsonschema
import pytest
from pydantic import ValidationError

from schemas.models import (
    CANONICAL_SCHEMA_MODELS,
    JSON_SCHEMA_DRAFT,
    SCHEMA_VERSION,
    AskRequest,
    AskResponse,
    Candidate,
    CandidateChunk,
    ContextPayload,
    ErrorCode,
    EventStage,
    EvidenceItem,
    GroundingResult,
    GroundingStatus,
    LLMResponse,
    LogEvent,
    ResponseStatus,
    RetrievalBundle,
    RouteDecision,
    RouteType,
    StructuredRAGOutput,
    TokenUsage,
    export_json_schemas,
)

ROOT = Path(__file__).resolve().parents[2]
GENERATED_DIR = ROOT / "schemas" / "generated"
EXAMPLES_DIR = ROOT / "schemas" / "examples"

EXAMPLE_MODEL_MAP: dict[str, tuple[type, str]] = {
    "ask_request_valid.json": (AskRequest, "ask_request.schema.json"),
    "ask_response_ok.json": (AskResponse, "ask_response.schema.json"),
    "ask_response_abstain.json": (AskResponse, "ask_response.schema.json"),
    "ask_response_needs_clarification.json": (AskResponse, "ask_response.schema.json"),
    "ask_response_error_timeout.json": (AskResponse, "ask_response.schema.json"),
    "route_decision_out_of_scope.json": (RouteDecision, "route_decision.schema.json"),
    "retrieval_bundle_valid.json": (RetrievalBundle, "retrieval_bundle.schema.json"),
    "log_event_generate.json": (LogEvent, "log_event.schema.json"),
}


def _ok_response_kwargs(**overrides) -> dict:
    base = {
        "query_id": "Q1",
        "query": "Điều kiện kết hôn là gì?",
        "as_of_date": "2026-11-15",
        "as_of_date_source": "user_input",
        "route": "FACTUAL_LEGAL",
        "status": "OK",
        "grounding_status": "PASS",
        "answer": "Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên [1].",
        "abstained": False,
        "needs_clarification": False,
        "error_code": None,
    }
    base.update(overrides)
    return base


def test_standard_literals_and_aliases():
    assert SCHEMA_VERSION == "week10_v1.0"
    assert Candidate is CandidateChunk
    assert set(get_args(RouteType)) == {"FACTUAL_LEGAL", "OUT_OF_SCOPE", "AMBIGUOUS", "SYSTEM_META"}
    assert set(get_args(ResponseStatus)) == {"OK", "ABSTAIN", "NEEDS_CLARIFICATION", "ERROR"}
    assert set(get_args(GroundingStatus)) == {"PASS", "FAIL", "ABSTAIN", "NEEDS_CLARIFICATION"}
    assert set(get_args(EventStage)) == {
        "request",
        "route",
        "retrieve",
        "context",
        "generate",
        "grounding",
        "response",
        "error",
    }
    assert set(get_args(ErrorCode)) == {
        "LLM_TIMEOUT",
        "JSON_INVALID",
        "CITATION_INVALID",
        "GATE_FAIL",
        "INTERNAL_ERROR",
    }
    assert len(CANONICAL_SCHEMA_MODELS) == 10


def test_generated_json_schemas_match_models_and_draft_2020_12():
    for filename, model_cls in CANONICAL_SCHEMA_MODELS.items():
        schema_path = GENERATED_DIR / filename
        assert schema_path.exists(), f"Thiếu schema chuẩn: {schema_path}"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["$schema"] == JSON_SCHEMA_DRAFT
        assert schema["schema_version"] == SCHEMA_VERSION
        jsonschema.Draft202012Validator.check_schema(schema)
        stripped = {k: v for k, v in schema.items() if k not in ("$schema", "schema_version")}
        assert stripped == model_cls.model_json_schema()


@pytest.mark.parametrize("example_name,spec", list(EXAMPLE_MODEL_MAP.items()))
def test_example_payloads_validate_with_pydantic_and_json_schema(example_name: str, spec: tuple[type, str]):
    model_cls, schema_file = spec
    payload = json.loads((EXAMPLES_DIR / example_name).read_text(encoding="utf-8"))
    validated = model_cls.model_validate(payload)
    assert validated is not None

    schema = json.loads((GENERATED_DIR / schema_file).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_remaining_canonical_models_roundtrip_against_generated_schemas():
    evidence = EvidenceItem(
        evidence_index=1,
        chunk_id="c1",
        parent_clause_id="pc1",
        document_id="doc1",
        article_id="art_8",
        clause_id="clause_1",
        content="Nội dung điều luật",
        validity_status="Còn hiệu lực",
    )
    ctx = ContextPayload(
        query_id="Q1",
        query="Tuổi kết hôn?",
        as_of_date="2026-10-15",
        as_of_date_source="benchmark",
        evidence_items=[evidence],
    )
    llm_resp = LLMResponse(
        query_id="Q1",
        run_mode="B_controlled_rag",
        answer="Theo [1]...",
        evidence_indices=[1],
        prompt_version="v1.2_controlled_rag",
        done_reason="stop",
    )
    grounding = GroundingResult(grounding_status="PASS", is_grounded=True)

    pairs = [
        (evidence, "evidence_item.schema.json"),
        (ctx, "context_payload.schema.json"),
        (llm_resp, "llm_response.schema.json"),
        (grounding, "grounding_result.schema.json"),
    ]
    for model_obj, schema_filename in pairs:
        schema = json.loads((GENERATED_DIR / schema_filename).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(model_obj.model_dump(mode="json"))


def test_export_json_schemas_writes_legacy_and_generated(tmp_path: Path):
    exported = export_json_schemas(tmp_path)
    assert len(exported) == 13
    assert set(exported.keys()) >= {
        "candidate.schema.json",
        "context_payload.schema.json",
        "llm_response.schema.json",
    }
    assert json.loads((tmp_path / "llm_response.schema.json").read_text(encoding="utf-8")) == (
        StructuredRAGOutput.model_json_schema()
    )
    gen_llm = json.loads((tmp_path / "generated" / "llm_response.schema.json").read_text(encoding="utf-8"))
    assert gen_llm["schema_version"] == SCHEMA_VERSION
    assert "error_code" in gen_llm["properties"]


@pytest.mark.parametrize(
    "bad_overrides",
    [
        {"grounding_status": "FAIL"},
        {"abstained": True},
        {"needs_clarification": True},
        {"error_code": "INTERNAL_ERROR"},
        {"answer": "   "},
        {"status": "ABSTAIN", "grounding_status": "ABSTAIN", "abstained": False, "abstention_reason": "LOW_CONFIDENCE"},
        {"status": "ABSTAIN", "grounding_status": "ABSTAIN", "abstained": True, "abstention_reason": None},
        {"status": "ABSTAIN", "grounding_status": "PASS", "abstained": True, "abstention_reason": "LOW_CONFIDENCE"},
        {"status": "ABSTAIN", "grounding_status": "ABSTAIN", "abstained": True, "abstention_reason": "X", "error_code": "INTERNAL_ERROR"},
        {"status": "NEEDS_CLARIFICATION", "grounding_status": "NEEDS_CLARIFICATION", "needs_clarification": False},
        {"status": "NEEDS_CLARIFICATION", "grounding_status": "PASS", "needs_clarification": True},
        {"status": "NEEDS_CLARIFICATION", "grounding_status": "NEEDS_CLARIFICATION", "needs_clarification": True, "abstained": True},
        {"status": "ERROR", "grounding_status": "FAIL", "error_code": None},
        {"status": "ERROR", "grounding_status": "PASS", "error_code": "LLM_TIMEOUT"},
        {"status": "ERROR", "grounding_status": "FAIL", "error_code": "LLM_TIMEOUT", "abstained": True},
    ],
)
def test_ask_response_status_separation_rejects_mixed_states(bad_overrides: dict):
    with pytest.raises(ValidationError):
        AskResponse(**_ok_response_kwargs(**bad_overrides))


def test_extra_forbid_and_field_validation():
    with pytest.raises(ValidationError):
        AskRequest(query="   ")

    with pytest.raises(ValidationError):
        AskRequest(query="Hỏi?", as_of_date="15-11-2026")

    with pytest.raises(ValidationError):
        AskRequest(query="Hỏi?", unknown_extra="nope")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        RouteDecision(query_id="q1", route="FACTUAL_LEGAL", unexpected=True)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        LogEvent(timestamp="not-a-timestamp", trace_id="t1", query_id="q1", stage="route", status="OK")

    usage = TokenUsage()
    assert usage.input is None and usage.output is None
    with pytest.raises(ValidationError):
        TokenUsage(input=-1, output=10)
