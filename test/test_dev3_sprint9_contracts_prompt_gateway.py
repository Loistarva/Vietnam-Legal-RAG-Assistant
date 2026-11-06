# -*- coding: utf-8 -*-
"""
test/test_dev3_sprint9_contracts_prompt_gateway.py
Toàn bộ unit test và contract test cho phân hệ Dev 3 Sprint 9 (Kế hoạch V3).
Đáp ứng các tiêu chí nghiệm thu: DoD-06, DoD-09, DoD-10, DoD-11.
"""
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from embedding.model_registry import (
    DEFAULT_DIMENSION,
    DEFAULT_PRODUCTION_MODEL,
    get_embedding_spec,
    prepare_text_for_embedding,
    validate_collection_dimension,
)
from generation.prompt_builder import (
    PROMPT_A_VERSION,
    PROMPT_B_VERSION,
    STANDARD_DISCLAIMER,
    build_controlled_rag_prompt,
    build_zero_shot_prompt,
    format_evidence_item,
    map_evidence_indices_to_citations,
)
from model_gateway.llm_gateway import (
    GatewayExecutionError,
    QwenGateway,
    QwenGatewayConfig,
    summarize_truncation_and_provenance,
)
from schemas.models import (
    CandidateChunk,
    ContextPayload,
    EvidenceItem,
    GroundingResult,
    LLMResponse,
    MappedCitation,
    RAGOutputRecord,
    StructuredRAGOutput,
    TokenUsage,
)


# =============================================================================
# 1. Tests for Pydantic Models & Contracts (DoD-06)
# =============================================================================

class TestContractsAndSchemas:
    def test_candidate_chunk_strict_validation(self):
        valid_data = {
            "query_id": "dev_q01",
            "chunk_id": "law_hn_gd_2014_art_56_clause_1_chunk_1",
            "chunk_text": "Vợ, chồng hoặc cả hai người có quyền yêu cầu Tòa án giải quyết ly hôn.",
            "score": 0.95,
            "rank": 1,
            "retrieval_source": "RRF",
            "validity_status": "Còn hiệu lực",
            "effective_from": "2015-01-01",
            "effective_to": None,
            "as_of_date": "2024-01-01",
            "document_id": "law_hn_gd_2014",
            "article_id": "art_56",
            "clause_id": "clause_1",
            "evidence_index": 1,
        }
        chunk = CandidateChunk(**valid_data)
        assert chunk.query_id == "dev_q01"
        assert chunk.rank == 1
        assert chunk.effective_to is None

        # Chặn chuỗi rỗng
        for field in ["query_id", "chunk_id", "chunk_text", "as_of_date"]:
            bad_data = copy.deepcopy(valid_data)
            bad_data[field] = "   "
            with pytest.raises(ValidationError):
                CandidateChunk(**bad_data)

        # Chặn evidence_index ngoài [1, 5]
        bad_idx = copy.deepcopy(valid_data)
        bad_idx["evidence_index"] = 0
        with pytest.raises(ValidationError):
            CandidateChunk(**bad_idx)

        bad_idx["evidence_index"] = 6
        with pytest.raises(ValidationError):
            CandidateChunk(**bad_idx)

    def test_context_payload_auto_computations(self):
        item1 = EvidenceItem(
            evidence_index=1,
            chunk_id="chunk_a",
            parent_clause_id="parent_a",
            document_id="doc_a",
            article_id="art_a",
            clause_id="clause_a",
            content="Nội dung điều 1",
            validity_status="Còn hiệu lực",
        )
        item2 = EvidenceItem(
            evidence_index=2,
            chunk_id="chunk_b",
            parent_clause_id="parent_b",
            document_id="doc_b",
            article_id="art_b",
            clause_id="clause_b",
            content="Nội dung điều 2 dài hơn",
            validity_status="Còn hiệu lực",
        )

        payload = ContextPayload(
            query_id="dev_q02",
            query="Hỏi về ly hôn",
            as_of_date="2024-01-01",
            evidence_items=[item1, item2],
        )

        # Tự động tính total_chars
        assert payload.total_chars == len(item1.content) + len(item2.content)
        # Tự động tạo source_map
        assert 1 in payload.source_map and 2 in payload.source_map
        assert payload.source_map[1]["chunk_id"] == "chunk_a"
        assert payload.source_map[2]["chunk_id"] == "chunk_b"

    def test_structured_rag_output_constraints(self):
        # Hợp lệ
        out = StructuredRAGOutput(
            answer="Điều kiện ly hôn là...",
            evidence_indices=[1, 3],
            abstained=False,
        )
        assert out.evidence_indices == [1, 3]

        # Chặn nếu đưa string chunk_id vào evidence_indices
        with pytest.raises(ValidationError):
            StructuredRAGOutput(
                answer="Answer",
                evidence_indices=["chunk_123"],  # type: ignore
            )

        # Chặn số nguyên ngoài [1, 5]
        with pytest.raises(ValidationError):
            StructuredRAGOutput(
                answer="Answer",
                evidence_indices=[1, 7],
            )

    def test_json_schemas_on_disk_match_models(self):
        schemas_dir = Path(__file__).resolve().parent.parent / "schemas"
        files = {
            "candidate.schema.json": CandidateChunk.model_json_schema(),
            "context_payload.schema.json": ContextPayload.model_json_schema(),
            "llm_response.schema.json": StructuredRAGOutput.model_json_schema(),
        }
        for filename, expected_schema in files.items():
            schema_file = schemas_dir / filename
            assert schema_file.exists(), f"Thiếu file schema: {schema_file}"
            actual = json.loads(schema_file.read_text(encoding="utf-8"))
            assert actual == expected_schema, f"Schema {filename} không khớp với Pydantic model!"


# =============================================================================
# 2. Tests for Prompt Builder & Evidence Numbering (DoD-09, DoD-11)
# =============================================================================

class TestPromptBuilder:
    def test_prompt_version_and_disclaimer_frozen(self):
        assert PROMPT_A_VERSION == "v1.0_zero_shot_m1"
        assert PROMPT_B_VERSION == "v1.0_controlled_rag_m1"
        assert STANDARD_DISCLAIMER == "Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."

    def test_build_zero_shot_prompt_formatting(self):
        prompt = build_zero_shot_prompt(
            query="Độ tuổi kết hôn hợp pháp của nam và nữ?",
            as_of_date="2024-01-01",
            include_as_of_date=True,
        )
        assert PROMPT_A_VERSION in prompt
        assert STANDARD_DISCLAIMER in prompt
        assert "Theo quy định có hiệu lực tại ngày 2024-01-01..." in prompt
        assert "Độ tuổi kết hôn hợp pháp của nam và nữ?" in prompt
        assert "Hôn nhân và Gia đình Việt Nam" in prompt

    def test_build_controlled_rag_prompt_formatting(self):
        item1 = EvidenceItem(
            evidence_index=1,
            chunk_id="hn_gd_art_8_clause_1",
            parent_clause_id="hn_gd_art_8_clause_1",
            document_id="Luật Hôn nhân và gia đình 2014",
            article_id="Điều 8",
            clause_id="Khoản 1",
            content="Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên.",
            validity_status="Còn hiệu lực",
            effective_from="2015-01-01",
            effective_to=None,
        )
        payload = ContextPayload(
            query_id="dev_q03",
            query="Tuổi kết hôn là bao nhiêu?",
            as_of_date="2024-01-01",
            evidence_items=[item1],
        )

        prompt = build_controlled_rag_prompt(payload)
        assert PROMPT_B_VERSION in prompt
        assert STANDARD_DISCLAIMER in prompt
        assert "[1] Văn bản: Luật Hôn nhân và gia đình 2014" in prompt
        assert "Điều/Khoản: hn_gd_art_8_clause_1" in prompt
        assert "Hiệu lực: 2015-01-01 -> hiện tại" in prompt
        assert "Nội dung: Nam từ đủ 20 tuổi trở lên" in prompt
        assert "tự suy diễn" in prompt
        assert "evidence_indices" in prompt

    def test_map_evidence_indices_to_citations(self):
        item1 = EvidenceItem(
            evidence_index=1,
            chunk_id="chunk_01",
            parent_clause_id="parent_01",
            document_id="doc_01",
            article_id="art_01",
            clause_id="cl_01",
            content="Content 1",
            validity_status="Còn hiệu lực",
        )
        item2 = EvidenceItem(
            evidence_index=2,
            chunk_id="chunk_02",
            parent_clause_id="parent_02",
            document_id="doc_02",
            article_id="art_02",
            clause_id="cl_02",
            content="Content 2",
            validity_status="Còn hiệu lực",
        )
        payload = ContextPayload(
            query_id="dev_q04",
            query="Câu hỏi test",
            as_of_date="2024-01-01",
            evidence_items=[item1, item2],
        )

        # Mô hình trả về: 1 (hợp lệ), 2 (hợp lệ), 6 (ngoài 1..5), 99 (ngoài source_map)
        valid_citations, invalid_indices = map_evidence_indices_to_citations([1, 2, 6, 99], payload)
        assert len(valid_citations) == 2
        assert valid_citations[0].evidence_index == 1
        assert valid_citations[0].chunk_id == "chunk_01"
        assert valid_citations[1].evidence_index == 2
        assert valid_citations[1].chunk_id == "chunk_02"

        assert invalid_indices == [6, 99]


# =============================================================================
# 3. Tests for Qwen Model Gateway & Provenance (DoD-10)
# =============================================================================

class TestQwenModelGateway:
    def test_gateway_config_and_hyperparameters(self):
        gateway = QwenGateway()
        assert gateway.config.model == "qwen2.5:7b"
        assert gateway.config.temperature == 0.0
        assert gateway.config.repeat_penalty == 1.15
        assert gateway.config.num_predict == 1024
        assert gateway.config.num_ctx == 8192
        assert gateway.config.fallback_locked is True

    def test_gateway_run_a_zero_shot(self):
        recorded_calls = []

        def mock_transport(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
            recorded_calls.append({"url": url, "payload": payload, "timeout": timeout})
            return {
                "response": "Nam từ đủ 20 tuổi, nữ từ đủ 18 tuổi.",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 80,
                "eval_count": 25,
            }

        gateway = QwenGateway(transport=mock_transport)
        resp = gateway.generate(
            prompt="Tuổi kết hôn?",
            query_id="q_zero",
            run_mode="A_zero_shot",
            prompt_version=PROMPT_A_VERSION,
            structured_output=False,
        )

        assert len(recorded_calls) == 1
        sent_payload = recorded_calls[0]["payload"]
        assert sent_payload["options"]["num_ctx"] == 8192
        assert sent_payload["options"]["num_predict"] == 1024
        assert sent_payload["options"]["temperature"] == 0.0
        assert sent_payload["options"]["repeat_penalty"] == 1.15
        assert "format" not in sent_payload

        assert resp.query_id == "q_zero"
        assert resp.run_mode == "A_zero_shot"
        assert resp.parse_status == "raw_text"
        assert resp.done_reason == "stop"
        assert resp.truncated is False
        assert resp.token_usage.input == 80
        assert resp.token_usage.output == 25

    def test_gateway_run_b_structured_output_ok(self):
        recorded_calls = []

        def mock_transport(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
            recorded_calls.append({"url": url, "payload": payload, "timeout": timeout})
            return {
                "response": json.dumps({
                    "answer": "Theo quy định, nam từ đủ 20 tuổi, nữ từ đủ 18 tuổi.",
                    "evidence_indices": [1],
                    "abstained": False,
                    "abstention_reason": None,
                    "needs_clarification": False,
                }),
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 350,
                "eval_count": 65,
            }

        gateway = QwenGateway(transport=mock_transport)
        resp = gateway.generate(
            prompt="Prompt RAG B",
            query_id="q_rag_ok",
            run_mode="B_controlled_rag",
            prompt_version=PROMPT_B_VERSION,
            structured_output=True,
        )

        assert len(recorded_calls) == 1
        assert "format" in recorded_calls[0]["payload"]
        assert resp.parse_status == "ok"
        assert resp.evidence_indices == [1]
        assert resp.abstained is False
        assert resp.truncated is False

    def test_gateway_run_b_truncation_detection(self):
        def mock_transport(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
            # Giả lập phản hồi bị cắt đứt giữa chừng vì chạm trần num_predict
            return {
                "response": '{"answer": "Theo quy định tại Điều 8 Luật Hôn nhân và gia đình n',
                "done": True,
                "done_reason": "length",
                "prompt_eval_count": 400,
                "eval_count": 1024,
            }

        gateway = QwenGateway(transport=mock_transport)
        resp = gateway.generate(
            prompt="Prompt RAG B",
            query_id="q_truncated",
            run_mode="B_controlled_rag",
            prompt_version=PROMPT_B_VERSION,
            structured_output=True,
        )

        # Phải phân loại rõ parse_status = truncated_json và truncated = True
        assert resp.parse_status == "truncated_json"
        assert resp.truncated is True
        assert resp.done_reason == "length"

    def test_gateway_retry_and_fail_fast(self):
        call_count = 0

        def failing_transport(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Connection timed out")

        gateway = QwenGateway(transport=failing_transport)

        # Khi timeout, retry đúng 1 lần (tổng 2 lần thử) rồi ném GatewayExecutionError
        with pytest.raises(GatewayExecutionError, match="sau 2 lần thử"):
            gateway.generate(
                prompt="Prompt test",
                query_id="q_fail",
                run_mode="A_zero_shot",
                prompt_version=PROMPT_A_VERSION,
            )
        assert call_count == 2

    def test_summarize_truncation_and_provenance(self):
        r1 = LLMResponse(
            query_id="q1",
            run_mode="B_controlled_rag",
            answer="Ans 1",
            evidence_indices=[1],
            prompt_version=PROMPT_B_VERSION,
            done_reason="stop",
            truncated=False,
            parse_status="ok",
            latency_ms=100.0,
            token_usage=TokenUsage(input=200, output=50),
        )
        r2 = LLMResponse(
            query_id="q2",
            run_mode="B_controlled_rag",
            answer="Ans 2 truncated...",
            evidence_indices=[],
            prompt_version=PROMPT_B_VERSION,
            done_reason="length",
            truncated=True,
            parse_status="truncated_json",
            latency_ms=300.0,
            token_usage=TokenUsage(input=200, output=1024),
        )

        summary = summarize_truncation_and_provenance([r1, r2])
        assert summary["total_queries"] == 2
        assert summary["truncation_count"] == 1
        assert summary["truncation_rate"] == 0.5
        assert summary["json_parse_failure_count"] == 1
        assert summary["json_parse_failure_rate"] == 0.5
        assert summary["total_input_tokens"] == 400
        assert summary["total_output_tokens"] == 1074


# =============================================================================
# 4. Tests for Embedding Ownership Handoff (Task D3.5)
# =============================================================================

class TestEmbeddingOwnershipHandoff:
    def test_default_production_model_spec(self):
        spec = get_embedding_spec(DEFAULT_PRODUCTION_MODEL)
        assert spec["name"] == "BAAI/bge-m3"
        assert spec["dimension"] == DEFAULT_DIMENSION  # 1024
        assert spec["use_word_segmentation"] is False
        assert spec["text_field"] == "embed_text_raw"

    def test_validate_collection_dimension_success_and_fail_fast(self):
        # Chiều đúng: 1024
        assert validate_collection_dimension("BAAI/bge-m3", 1024) is True

        # Chiều lệch: ném ValueError
        with pytest.raises(ValueError, match="Lệch chiều vector"):
            validate_collection_dimension("BAAI/bge-m3", 768)

    def test_prepare_text_for_embedding(self):
        raw = "  Điều 56.   Ly hôn   theo yêu cầu  của một bên   "
        prepared = prepare_text_for_embedding(raw, "BAAI/bge-m3")
        assert prepared == "Điều 56. Ly hôn theo yêu cầu của một bên"
