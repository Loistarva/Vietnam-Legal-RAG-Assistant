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
    AskTimings,
    Candidate,
    CandidateChunk,
    ContextPayload,
    ErrorCode,
    ErrorDetail,
    EventStage,
    EvidenceItem,
    GroundingResult,
    GroundingStatus,
    LLMResponse,
    LogEvent,
    MappedCitation,
    MetadataFilters,
    RAGOutputRecord,
    ResponseStatus,
    RetrievalBundle,
    RetrievalLatencyBreakdown,
    RouteAction,
    RouteDecision,
    RouteType,
    SchemaVersionType,
    StructuredRAGOutput,
    TokenUsage,
    export_json_schemas,
    map_router_route_to_canonical,
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


def _sample_evidence(evidence_index: int = 1) -> EvidenceItem:
    return EvidenceItem(
        evidence_index=evidence_index,
        chunk_id=f"c{evidence_index}",
        parent_clause_id="pc1",
        document_id="doc1",
        article_id="art_8",
        clause_id="clause_1",
        content="Nam từ đủ 20 tuổi trở lên.",
        validity_status="Còn hiệu lực",
    )


def _sample_citation(evidence_index: int = 1) -> MappedCitation:
    return MappedCitation(
        evidence_index=evidence_index,
        chunk_id=f"c{evidence_index}",
        document_id="doc1",
        article_id="art_8",
        clause_id="clause_1",
        parent_clause_id="pc1",
    )


def _success_response_kwargs(**overrides) -> dict:
    base = {
        "query_id": "Q1",
        "request_id": "req_1",
        "as_of_date": "2026-11-16",
        "as_of_date_source": "user_input",
        "status": "SUCCESS",
        "route": "LEGAL_IN_SCOPE",
        "answer": "Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên [1].",
        "citations": [_sample_citation(1)],
        "evidence": [_sample_evidence(1)],
        "grounding_status": "PASS",
        "disclaimer": "Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.",
        "timings": AskTimings(retrieval_ms=12.0, llm_total_ms=120.0, total_ms=140.0),
    }
    base.update(overrides)
    return base


@pytest.mark.req("FR1.3")
@pytest.mark.req("FR3.1")
@pytest.mark.req("FR6.4")
@pytest.mark.req("FR9.9")
def test_standard_literals_and_aliases():
    assert SCHEMA_VERSION == "week10_v1.1"
    assert set(get_args(SchemaVersionType)) == {"week10_v1.0", "week10_v1.1"}
    assert Candidate is CandidateChunk
    assert set(get_args(RouteType)) == {"LEGAL_IN_SCOPE", "NON_LEGAL", "LEGAL_OUT_OF_SCOPE", "MIXED_REVIEW"}
    assert set(get_args(RouteAction)) == {"LEGAL_RETRIEVAL", "FAST_PATH", "POLICY_ABSTENTION", "GENERAL_CHAT"}
    assert set(get_args(ResponseStatus)) == {"SUCCESS", "NEEDS_CLARIFICATION", "ABSTAIN", "ERROR"}
    assert set(get_args(GroundingStatus)) == {"PASS", "FAIL", "NOT_RUN", "ABSTAIN", "NEEDS_CLARIFICATION"}
    assert set(get_args(EventStage)) == {
        "api",
        "router",
        "retrieval",
        "rerank",
        "confidence",
        "context",
        "llm",
        "citation",
        "gate",
        "response",
    }
    assert set(get_args(ErrorCode)) == {
        "AUTH_REQUIRED",
        "INVALID_REQUEST",
        "ROUTE_POLICY",
        "RETRIEVAL_EMPTY",
        "LOW_CONFIDENCE",
        "LLM_TIMEOUT",
        "LLM_UNAVAILABLE",
        "JSON_INVALID",
        "CITATION_INVALID",
        "GROUNDING_FAIL",
        "INTERNAL_ERROR",
    }
    assert len(CANONICAL_SCHEMA_MODELS) == 10


@pytest.mark.req("FR1.3")
@pytest.mark.parametrize(
    "raw_route,expected",
    [
        ("LEGAL_HNGD", "LEGAL_IN_SCOPE"),
        ("LEGAL_IN_SCOPE", "LEGAL_IN_SCOPE"),
        ("NON_LEGAL", "NON_LEGAL"),
        ("LEGAL_OUT_OF_SCOPE", "LEGAL_OUT_OF_SCOPE"),
        ("MIXED_LEGAL_SCOPE", "MIXED_REVIEW"),
        ("LEGAL_SCOPE_UNCERTAIN", "MIXED_REVIEW"),
        ("MIXED_REVIEW", "MIXED_REVIEW"),
    ],
)
def test_map_router_route_to_canonical(raw_route: str, expected: RouteType):
    assert map_router_route_to_canonical(raw_route) == expected


@pytest.mark.req("FR1.3")
def test_map_router_route_to_canonical_rejects_unknown():
    with pytest.raises(ValueError):
        map_router_route_to_canonical("UNKNOWN_ROUTE")


@pytest.mark.req("IR2.1")
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


@pytest.mark.req("IR2.1")
@pytest.mark.parametrize("example_name,spec", list(EXAMPLE_MODEL_MAP.items()))
def test_example_payloads_validate_with_pydantic_and_json_schema(example_name: str, spec: tuple[type, str]):
    model_cls, schema_file = spec
    payload = json.loads((EXAMPLES_DIR / example_name).read_text(encoding="utf-8"))
    validated = model_cls.model_validate(payload)
    assert validated is not None

    schema = json.loads((GENERATED_DIR / schema_file).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(payload)


@pytest.mark.req("FR4.4")
@pytest.mark.req("FR4.7")
@pytest.mark.req("IR1.4")
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
    grounding = GroundingResult(
        status="FAIL",
        violation_codes=["ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES"],
        retryable=False,
        reason="ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES",
    )
    assert grounding.grounding_status == "FAIL" and grounding.is_grounded is False
    assert grounding.abstention_reason is None

    pairs = [
        (evidence, "evidence_item.schema.json"),
        (ctx, "context_payload.schema.json"),
        (llm_resp, "llm_response.schema.json"),
        (grounding, "grounding_result.schema.json"),
    ]
    for model_obj, schema_filename in pairs:
        schema = json.loads((GENERATED_DIR / schema_filename).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(model_obj.model_dump(mode="json"))


@pytest.mark.req("IR2.1")
def test_export_json_schemas_writes_root_and_generated(tmp_path: Path):
    exported = export_json_schemas(tmp_path)
    assert len(exported) == 14
    assert {
        "candidate.schema.json",
        "context_payload.schema.json",
        "llm_response.schema.json",
        "structured_rag_output.schema.json",
    } <= set(exported.keys())
    assert json.loads((tmp_path / "structured_rag_output.schema.json").read_text(encoding="utf-8")) == (
        StructuredRAGOutput.model_json_schema()
    )
    assert json.loads((tmp_path / "llm_response.schema.json").read_text(encoding="utf-8")) == (
        StructuredRAGOutput.model_json_schema()
    )
    gen_llm = json.loads((tmp_path / "generated" / "llm_response.schema.json").read_text(encoding="utf-8"))
    assert gen_llm["schema_version"] == SCHEMA_VERSION
    assert "error_code" in gen_llm["properties"]


@pytest.mark.req("IR2.1")
@pytest.mark.req("IR2.5")
@pytest.mark.req("FR5.8")
def test_ask_response_valid_paths_and_strict_schema_consistency():
    non_legal = AskResponse(
        query_id="Q_CHAT",
        as_of_date="2026-11-16",
        as_of_date_source="system_today",
        status="SUCCESS",
        route="NON_LEGAL",
        answer="Xin chào, tôi là trợ lý hỏi đáp pháp luật Hôn nhân và gia đình.",
        grounding_status="NOT_RUN",
        disclaimer="Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.",
        timings=AskTimings(total_ms=3.5),
    )
    assert non_legal.grounding_status == "NOT_RUN"
    assert non_legal.evidence == [] and non_legal.citations == []
    assert non_legal.timings.total_ms == 3.5

    abstain_allowed_code = AskResponse(
        **_success_response_kwargs(
            status="ABSTAIN",
            route="LEGAL_IN_SCOPE",
            answer=None,
            citations=[],
            evidence=[],
            grounding_status="NOT_RUN",
            abstention_reason="LOW_CONFIDENCE",
            error_code="LOW_CONFIDENCE",
        )
    )
    assert abstain_allowed_code.error_code == "LOW_CONFIDENCE"

    # Gate FAIL (JSON hỏng / citation sai) abstain kèm mã cụ thể
    for gate_code in ("JSON_INVALID", "CITATION_INVALID"):
        gate_fail = AskResponse(
            **_success_response_kwargs(
                status="ABSTAIN",
                answer=None,
                citations=[],
                evidence=[],
                grounding_status="FAIL",
                abstention_reason="LLM_OUTPUT_INVALID_JSON",
                error_code=gate_code,
            )
        )
        assert (gate_fail.status, gate_fail.grounding_status, gate_fail.error_code) == ("ABSTAIN", "FAIL", gate_code)

    # as_of_date_source không có mặc định: thiếu là lỗi
    missing_source = _success_response_kwargs()
    missing_source.pop("as_of_date_source")
    with pytest.raises(ValidationError):
        AskResponse(**missing_source)

    # Legacy Pydantic-only aliases removed so Pydantic matches JSON Schema
    with pytest.raises(ValidationError):
        AskResponse(**_success_response_kwargs(status="OK"))

    with pytest.raises(ValidationError):
        AskResponse(
            query_id="Q_AMB",
            as_of_date="2026-11-16",
            as_of_date_source="system_today",
            status="NEEDS_CLARIFICATION",
            route="MIXED_REVIEW",
            answer=None,
            clarification_question="Vui lòng nêu rõ thời điểm kết hôn?",
            grounding_status="NOT_RUN",
            disclaimer="Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.",
        )


@pytest.mark.req("IR2.1")
@pytest.mark.req("FR5.2")
@pytest.mark.parametrize(
    "bad_overrides",
    [
        {"grounding_status": "FAIL"},
        {"grounding_status": "NOT_RUN"},  # LEGAL_IN_SCOPE cannot use NOT_RUN when SUCCESS
        {"route": "LEGAL_OUT_OF_SCOPE"},
        {"citations": []},
        {"citations": [_sample_citation(2)]},  # evidence_index=2 missing from evidence
        {"route": "NON_LEGAL", "grounding_status": "PASS", "citations": [], "evidence": []},
        {"route": "NON_LEGAL", "grounding_status": "NOT_RUN", "citations": []},  # evidence still present
        {"route": "NON_LEGAL", "grounding_status": "NOT_RUN", "evidence": []},  # citations still present
        {"as_of_date": "16-11-2026"},
        {"answer": None},
        {"answer": "   "},
        {"disclaimer": "   "},
        {"clarification": "Hỏi lại?"},
        {"abstention_reason": "OUT_OF_SCOPE"},
        {"error_code": "INTERNAL_ERROR"},
        {"status": "ABSTAIN", "grounding_status": "ABSTAIN", "answer": "", "citations": [], "evidence": [], "abstention_reason": "LOW_CONFIDENCE"},
        {"status": "ABSTAIN", "grounding_status": "ABSTAIN", "answer": "Draft leak", "citations": [], "evidence": [], "abstention_reason": "LOW_CONFIDENCE"},
        {"status": "ABSTAIN", "grounding_status": "NOT_RUN", "answer": None, "citations": [], "evidence": [], "abstention_message": None, "abstention_reason": None},
        {"status": "ABSTAIN", "grounding_status": "PASS", "answer": None, "citations": [], "evidence": [], "abstention_reason": "LOW_CONFIDENCE"},
        {"status": "ABSTAIN", "grounding_status": "NOT_RUN", "answer": None, "citations": [], "evidence": [], "abstention_reason": "X", "error_code": "LLM_TIMEOUT"},
        {"status": "ABSTAIN", "grounding_status": "NOT_RUN", "answer": None, "citations": [], "evidence": [], "abstention_reason": "X", "error_code": "JSON_INVALID"},
        {"status": "ABSTAIN", "grounding_status": "ABSTAIN", "answer": None, "citations": [], "evidence": [], "abstention_reason": "X", "error_code": "CITATION_INVALID"},
        {"status": "ABSTAIN", "grounding_status": "NOT_RUN", "answer": None, "citations": [], "evidence": [], "abstention_reason": "X", "error": {"message": "fail"}},
        {"status": "NEEDS_CLARIFICATION", "grounding_status": "NOT_RUN", "answer": "Hỏi lại?", "citations": [], "evidence": [], "clarification": "Hỏi lại?"},
        {"status": "NEEDS_CLARIFICATION", "grounding_status": "NOT_RUN", "answer": None, "citations": [], "evidence": [], "clarification": None},
        {"status": "NEEDS_CLARIFICATION", "grounding_status": "PASS", "answer": None, "citations": [], "evidence": [], "clarification": "Cần thêm thông tin"},
        {"status": "ERROR", "grounding_status": "NOT_RUN", "answer": "Có lỗi", "citations": [], "evidence": [], "error_code": "LLM_TIMEOUT"},
        {"status": "ERROR", "grounding_status": "NOT_RUN", "answer": None, "citations": [], "evidence": [], "error_code": None, "error": ErrorDetail(message="Timeout")},
        {"status": "ERROR", "grounding_status": "PASS", "answer": None, "citations": [], "evidence": [], "error_code": "LLM_TIMEOUT"},
    ],
)
def test_ask_response_status_separation_rejects_mixed_states(bad_overrides: dict):
    with pytest.raises(ValidationError):
        AskResponse(**_success_response_kwargs(**bad_overrides))


@pytest.mark.req("IR2.5")
def test_error_detail_rejects_arbitrary_traceback_or_prompt_fields():
    with pytest.raises(ValidationError):
        ErrorDetail(message="Failed", traceback="Traceback (most recent call last)...")  # type: ignore[call-arg]


@pytest.mark.req("FR1.7")
@pytest.mark.req("IR2.1")
def test_ask_request_locks_server_params_and_schema_version_literal():
    with pytest.raises(ValidationError):
        AskRequest(query="   ")

    with pytest.raises(ValidationError):
        AskRequest(query="Hỏi?", as_of_date="16-11-2026")

    for forbidden_kw in (
        {"run_mode": "A_zero_shot"},
        {"top_k": 10},
        {"metadata": {"user": "pii"}},
    ):
        with pytest.raises(ValidationError):
            AskRequest(query="Hỏi?", **forbidden_kw)  # type: ignore[arg-type]

    for bad_version in ("week10_v2.0", "arbitrary", ""):
        with pytest.raises(ValidationError):
            AskRequest(query="Hỏi?", schema_version=bad_version)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            AskResponse(**_success_response_kwargs(schema_version=bad_version))


@pytest.mark.req("FR1.3")
@pytest.mark.req("FR5.2")
@pytest.mark.req("FR9.9")
def test_other_canonical_models_validation_and_grounding_compatibility():
    with pytest.raises(ValidationError):
        RouteDecision(route="LEGAL_IN_SCOPE", reason_code="", explanation="OK", policy_version="v1")

    with pytest.raises(ValidationError):
        RetrievalBundle(
            query_id="q1",
            as_of_date="2026-11-16",
            retrieval_config_version="v1",
            corpus_hash="abc",
            latency_ms=-1.0,
        )

    with pytest.raises(ValidationError):
        LogEvent(
            event_id="e1",
            query_id="q1",
            stage="invalid_stage",  # type: ignore[arg-type]
            event_type="x",
            timestamp="2026-11-16T10:00:00Z",
            status="SUCCESS",
        )

    with pytest.raises(ValidationError):
        LogEvent(
            event_id="e1",
            query_id="q1",
            stage="router",
            event_type="routed",
            timestamp="not-iso",
            status="SUCCESS",
        )

    # Backward compatibility with Sprint 9 citation_validator / rag_pipeline calling pattern
    legacy_gr = GroundingResult(grounding_status="PASS", is_grounded=True)
    assert legacy_gr.status == "PASS" and legacy_gr.grounding_status == "PASS"
    abstain_gr = GroundingResult(grounding_status="ABSTAIN", is_grounded=False, reason="LOW_CONFIDENCE")
    assert abstain_gr.abstention_reason == "LOW_CONFIDENCE"
    fail_gr = GroundingResult(grounding_status="FAIL", is_grounded=False, reason="OUT_OF_RANGE")
    assert fail_gr.abstention_reason is None and fail_gr.violation_codes == ["OUT_OF_RANGE"]

    with pytest.raises(ValidationError):
        GroundingResult(status="PASS", grounding_status="FAIL", is_grounded=True)
    with pytest.raises(ValidationError):
        GroundingResult(status="PASS", is_grounded=False)
    with pytest.raises(ValidationError):
        GroundingResult(status="FAIL", is_grounded=True)

    # Empty object rejected by both Pydantic and generated JSON Schema
    with pytest.raises(ValidationError):
        GroundingResult()  # type: ignore[call-arg]
    grounding_schema = json.loads((GENERATED_DIR / "grounding_result.schema.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(grounding_schema).validate({})

    usage = TokenUsage()
    assert usage.input is None and usage.output is None
    with pytest.raises(ValidationError):
        TokenUsage(input=-1, output=10)


@pytest.mark.req("FR1.3")
@pytest.mark.req("FR3.1")
@pytest.mark.req("FR3.4")
@pytest.mark.req("FR4.4")
@pytest.mark.req("FR4.7")
@pytest.mark.req("FR6.4")
@pytest.mark.req("FR9.9")
@pytest.mark.req("IR1.4")
def test_week10_v1_1_additions_and_constraints():
    # EvidenceItem.point_ref (FR4.7-AC2, IR1.4) + propagation to ContextPayload.source_map
    ev = EvidenceItem(
        evidence_index=1,
        chunk_id="c_pt",
        parent_clause_id="pc_pt",
        document_id="doc1",
        article_id="art_8",
        clause_id="clause_1",
        point_ref="Điểm a",
        content="Nam từ đủ 20 tuổi trở lên.",
        validity_status="Còn hiệu lực",
    )
    ctx = ContextPayload(
        query_id="Q_PT",
        query="Tuổi kết hôn của nam?",
        as_of_date="2026-11-23",
        as_of_date_source="user_input",
        evidence_items=[ev],
    )
    assert ctx.source_map[1]["point_ref"] == "Điểm a"
    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_index=1,
            chunk_id="c_pt",
            parent_clause_id="pc_pt",
            document_id="doc1",
            article_id="art_8",
            clause_id="clause_1",
            point_ref="   ",
            content="Nam từ đủ 20 tuổi trở lên.",
            validity_status="Còn hiệu lực",
        )

    # StructuredRAGOutput / LLMResponse missing_facts (FR4.4, FR3.4)
    out = StructuredRAGOutput(
        answer="Cần thêm dữ kiện về thời điểm kết hôn.",
        evidence_indices=[1],
        needs_clarification=True,
        missing_facts=["ngay_su_kien"],
    )
    assert out.missing_facts == ["ngay_su_kien"]
    with pytest.raises(ValidationError):
        StructuredRAGOutput(answer="Test", missing_facts=["   "])

    llm_resp = LLMResponse(
        query_id="Q_MF",
        run_mode="B_controlled_rag",
        answer="Cần làm rõ.",
        evidence_indices=[1],
        needs_clarification=True,
        missing_facts=["ngay_su_kien"],
        prompt_version="v1.3_controlled_rag",
        done_reason="stop",
    )
    assert llm_resp.missing_facts == ["ngay_su_kien"] and llm_resp.schema_version == "week10_v1.1"

    # ErrorCode.LLM_UNAVAILABLE (FR6.4) & EventStage.confidence (FR9.9, FR3.1)
    err_resp = AskResponse(
        **_success_response_kwargs(
            status="ERROR",
            answer=None,
            citations=[],
            evidence=[],
            grounding_status="NOT_RUN",
            error_code="LLM_UNAVAILABLE",
            error=ErrorDetail(message="Không kết nối được tới Ollama.", retryable=True),
        )
    )
    assert err_resp.error_code == "LLM_UNAVAILABLE" and err_resp.error is not None and err_resp.error.retryable

    conf_evt = LogEvent(
        event_id="evt_conf_1",
        query_id="Q_CONF",
        stage="confidence",
        event_type="confidence_evaluated",
        timestamp="2026-11-23T10:00:00Z",
        status="ok",
        masked_metadata={"top1_score": 0.91, "threshold_config_version": "conf_v1"},
    )
    assert conf_evt.stage == "confidence" and conf_evt.schema_version == "week10_v1.1"

    # RouteDecision.router_route & strict RouteAction (FR1.3, SRS 5.3.3)
    for valid_action in ("LEGAL_RETRIEVAL", "FAST_PATH", "POLICY_ABSTENTION", "GENERAL_CHAT"):
        rd = RouteDecision(
            route="MIXED_REVIEW",
            router_route="LEGAL_SCOPE_UNCERTAIN",
            reason_code="SCOPE_UNCERTAIN",
            explanation="Chuyển retrieval kiểm tra ngưỡng.",
            policy_version="router_v1",
            action=valid_action,  # type: ignore[arg-type]
        )
        assert rd.action == valid_action and rd.router_route == "LEGAL_SCOPE_UNCERTAIN"

    with pytest.raises(ValidationError):
        RouteDecision(
            route="LEGAL_OUT_OF_SCOPE",
            reason_code="OOS",
            explanation="Ngoài phạm vi",
            policy_version="router_v1",
            action="ABSTAIN_OUT_OF_SCOPE",  # type: ignore[arg-type]
        )


@pytest.mark.req("FR1.8")
@pytest.mark.req("FR4.7")
@pytest.mark.req("FR9.9")
def test_week10_v1_0_backward_compatibility():
    legacy_request = AskRequest.model_validate({"schema_version": "week10_v1.0", "query": "Tuổi kết hôn?"})
    legacy_route = RouteDecision.model_validate(
        {
            "schema_version": "week10_v1.0",
            "route": "LEGAL_IN_SCOPE",
            "reason_code": "HNGD_DOMAIN_MATCH",
            "explanation": "Khớp từ khóa HNGĐ",
            "policy_version": "router_v1",
            "action": "LEGAL_RETRIEVAL",
        }
    )
    legacy_bundle = RetrievalBundle.model_validate(
        {
            "schema_version": "week10_v1.0",
            "query_id": "Q_OLD",
            "as_of_date": "2026-11-16",
            "retrieval_config_version": "v1",
            "corpus_hash": "a" * 64,
            "latency_ms": 15.0,
        }
    )
    legacy_response = AskResponse.model_validate(
        {
            **_success_response_kwargs(schema_version="week10_v1.0"),
            "evidence": [_sample_evidence(1).model_dump(exclude={"point_ref"})],
        }
    )
    legacy_llm = LLMResponse.model_validate(
        {
            "schema_version": "week10_v1.0",
            "query_id": "Q_OLD",
            "run_mode": "B_controlled_rag",
            "answer": "Nam từ đủ 20 tuổi [1].",
            "evidence_indices": [1],
            "prompt_version": "v1.2_controlled_rag",
            "done_reason": "stop",
        }
    )
    legacy_log = LogEvent.model_validate(
        {
            "schema_version": "week10_v1.0",
            "event_id": "evt_1",
            "query_id": "Q_OLD",
            "stage": "rerank",
            "event_type": "rerank_completed",
            "timestamp": "2026-11-16T10:00:00Z",
            "status": "ok",
        }
    )
    assert legacy_request.schema_version == "week10_v1.0"
    assert legacy_route.router_route is None and legacy_route.action == "LEGAL_RETRIEVAL"
    assert legacy_bundle.schema_version == "week10_v1.0"
    assert legacy_response.evidence[0].point_ref is None
    assert legacy_llm.missing_facts == []
    assert legacy_log.stage == "rerank"


@pytest.mark.req("FR2.11")
@pytest.mark.req("FR9.4")
@pytest.mark.req("FR1.9")
@pytest.mark.req("FR9.8")
def test_retrieval_bundle_filters_latency_and_rag_record_route():
    # 1. RetrievalBundle v1.1 example với metadata_filters & latency_breakdown
    source = json.loads((EXAMPLES_DIR / "retrieval_bundle_valid.json").read_text(encoding="utf-8"))
    bundle = RetrievalBundle.model_validate(source)
    dumped = bundle.model_dump(mode="json")
    assert dumped["schema_version"] == "week10_v1.1"
    assert dumped["metadata_filters"] == {
        "document_type": None,
        "document_number": None,
        "document_id": "l_52_2014_qh13",
        "article_id": "art_8",
        "clause_id": None,
        "validity_status": None,
    }
    assert dumped["latency_breakdown"] == {
        "bm25_ms": 11.4,
        "dense_ms": 24.7,
        "rrf_ms": 0.4,
        "reranking_ms": 6.2,
        "parent_context_ms": None,
        "total_retrieval_ms": 45.2,
    }

    # Tương thích ngược week10_v1.0 thiếu metadata_filters và latency_breakdown
    legacy_source = {
        k: v for k, v in source.items() if k not in {"metadata_filters", "latency_breakdown"}
    }
    legacy_source["schema_version"] = "week10_v1.0"
    legacy_bundle = RetrievalBundle.model_validate(legacy_source)
    assert legacy_bundle.metadata_filters is None
    assert legacy_bundle.latency_breakdown is None

    # MetadataFilters và RetrievalLatencyBreakdown ràng buộc nghiêm ngặt
    with pytest.raises(ValidationError):
        MetadataFilters(document_id="   ")
    with pytest.raises(ValidationError):
        MetadataFilters(unknown_field="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        RetrievalLatencyBreakdown(bm25_ms=-0.1)

    # 2. RAGOutputRecord.route (optional để bản ghi cũ thiếu route vẫn hợp lệ)
    base_record = {
        "query_id": "Q_ROUTE_01",
        "query": "Điều kiện kết hôn?",
        "as_of_date": "2026-10-15",
        "as_of_date_source": "benchmark",
        "answer": "",
        "grounding_status": "ABSTAIN",
        "abstained": True,
        "abstention_reason": "LOW_CONFIDENCE",
        "abstention_source": "confidence_filter",
        "needs_clarification": False,
        "prompt_version": "v1.2_controlled_rag",
        "done_reason": "not_generated",
        "truncated": False,
        "corpus_version": "sha256:" + "a" * 64,
        "retrieval_config_version": "v1",
        "threshold_config_version": "conf_v1",
        "latency_ms": 1.5,
        "llm_calls": 0,
    }
    legacy_rec = RAGOutputRecord.model_validate(base_record)
    assert legacy_rec.route is None

    enriched_rec = RAGOutputRecord.model_validate({**base_record, "route": "LEGAL_IN_SCOPE"})
    assert enriched_rec.route == "LEGAL_IN_SCOPE"

    with pytest.raises(ValidationError):
        RAGOutputRecord.model_validate({**base_record, "route": "LEGAL_HNGD"})


@pytest.mark.req("FR4.7")
@pytest.mark.req("IR1.4")
def test_context_payload_source_map_backward_compatible_without_point_ref():
    ev_without_point = _sample_evidence(1).model_copy(update={"point_ref": None})
    built_ctx = ContextPayload(
        query_id="Q_CTX_LEGACY",
        query="Tuổi kết hôn?",
        as_of_date="2026-10-15",
        as_of_date_source="benchmark",
        evidence_items=[ev_without_point],
    )
    legacy_source_entry = dict(built_ctx.source_map[1])
    legacy_source_entry.pop("point_ref")

    # 1. Payload week10_v1.0 thiếu khóa point_ref trong source_map -> hợp lệ và chuẩn hóa point_ref=None
    legacy_payload = {
        "query_id": "Q_CTX_LEGACY",
        "query": "Tuổi kết hôn?",
        "as_of_date": "2026-10-15",
        "as_of_date_source": "benchmark",
        "evidence_items": [ev_without_point.model_dump(exclude={"point_ref"})],
        "source_map": {"1": legacy_source_entry},
        "total_chars": len(ev_without_point.content),
    }
    parsed = ContextPayload.model_validate(legacy_payload)
    assert parsed.source_map[1]["point_ref"] is None

    # 2. Sai point_ref, có khóa lạ, hoặc sai chunk_id/article_id -> vẫn phải từ chối
    with pytest.raises(ValidationError):
        ContextPayload.model_validate(
            {**legacy_payload, "source_map": {"1": {**legacy_source_entry, "point_ref": "Điểm a"}}}
        )
    with pytest.raises(ValidationError):
        ContextPayload.model_validate(
            {**legacy_payload, "source_map": {"1": {**legacy_source_entry, "unexpected_key": "x"}}}
        )
    with pytest.raises(ValidationError):
        ContextPayload.model_validate(
            {**legacy_payload, "source_map": {"1": {**legacy_source_entry, "chunk_id": "wrong_chunk"}}}
        )
    with pytest.raises(ValidationError):
        ContextPayload.model_validate(
            {**legacy_payload, "source_map": {"1": {**legacy_source_entry, "article_id": "art_999"}}}
        )
