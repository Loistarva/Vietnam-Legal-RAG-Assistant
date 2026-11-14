"""
test/test_dev3_sprint9_contracts_prompt_gateway.py
Toàn bộ unit test và contract test cho phân hệ Dev 3 Sprint 9 (Kế hoạch V3).
Đáp ứng các tiêu chí nghiệm thu: DoD-06, DoD-09, DoD-10, DoD-11.
"""
import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from embedding.model_registry import (
    get_embedding_spec,
    get_index_spec,
    prepare_text_for_embedding,
    validate_collection_dimension,
)
from generation.prompt_builder import (
    PROMPT_A_VERSION,
    PROMPT_B_VERSION,
    STANDARD_DISCLAIMER,
    build_controlled_rag_prompt,
    build_zero_shot_prompt,
    get_prompt_hash,
    map_evidence_indices_to_citations,
)
from model_gateway.llm_gateway import (
    GatewayExecutionError,
    QwenGateway,
    summarize_truncation_and_provenance,
)
from schemas.models import (
    CandidateChunk,
    ContextPayload,
    EvidenceItem,
    LLMResponse,
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

        # Chặn ngày sai định dạng ISO YYYY-MM-DD
        bad_date = copy.deepcopy(valid_data)
        bad_date["as_of_date"] = "not-a-date"
        with pytest.raises(ValidationError):
            CandidateChunk(**bad_date)

        bad_eff = copy.deepcopy(valid_data)
        bad_eff["effective_from"] = "01-01-2024"
        with pytest.raises(ValidationError):
            CandidateChunk(**bad_eff)

    def test_candidate_chunk_from_retrieval_item(self):
        item = {
            "chunk_id": "nd_126_2014_art_3_clause_1_chunk_1",
            "document_id": "nd_126_2014_nd_cp",
            "article_id": "art_3",
            "clause_id": "clause_1",
            "parent_clause_id": "nd_126_2014_art_3_clause_1",
            "rank": 1,
            "score": 0.88,
            "rrf_score": 0.032,
            "reranker_score": 0.88,
            "chunk_text": "Áp dụng tập quán trong hôn nhân và gia đình...",
            "retrieval_sources": ["dense", "bm25"],
            "source_ranks": {"dense": 2, "bm25": 1},
            "source_scores": {"dense": 0.75, "bm25": 14.5},
            "metadata": {
                "validity_status": "Còn hiệu lực",
                "effective_from": "2015-02-15",
                "effective_to": None,
                "document_number": "126/2014/NĐ-CP",
                "article_number": "3",
            },
        }
        chunk = CandidateChunk.from_retrieval_item(item, query_id="q_hybrid_01", as_of_date="2024-01-01")
        assert chunk.query_id == "q_hybrid_01"
        assert chunk.chunk_id == "nd_126_2014_art_3_clause_1_chunk_1"
        assert chunk.validity_status == "Còn hiệu lực"
        assert chunk.effective_from == "2015-02-15"
        assert chunk.effective_to is None
        assert "dense" in chunk.retrieval_sources
        assert "bm25" in chunk.retrieval_sources
        assert chunk.rrf_score == 0.032
        assert chunk.reranker_score == 0.88
        # Hit do cả hai nhánh tìm thấy không bị gắn nhãn theo nhánh đầu tiên
        assert chunk.retrieval_source == "hybrid"

    @pytest.mark.parametrize("missing", ["validity_status", "document_id", "rank", "score"])
    def test_candidate_chunk_from_retrieval_item_rejects_missing_fields(self, missing):
        item = {
            "chunk_id": "c1",
            "document_id": "doc",
            "article_id": "art",
            "clause_id": "clause",
            "rank": 1,
            "score": 0.5,
            "chunk_text": "Nội dung",
            "metadata": {"validity_status": "Còn hiệu lực"},
        }
        if missing == "validity_status":
            item["metadata"] = {}
        else:
            item.pop(missing)
        with pytest.raises(ValueError, match=missing):
            CandidateChunk.from_retrieval_item(item, query_id="q", as_of_date="2024-01-01", retriever="bm25")

    @pytest.mark.parametrize(
        "path",
        sorted((Path(__file__).resolve().parent.parent / "retrieval" / "results").rglob("*.json")),
        ids=lambda p: p.name,
    )
    def test_candidate_chunk_from_real_retrieval_results(self, path):
        envelopes = json.loads(path.read_text(encoding="utf-8"))
        if not (isinstance(envelopes, list) and envelopes and "results" in envelopes[0]):
            pytest.skip("không phải dump RetrievalEnvelope")
        for envelope in envelopes:
            for item in envelope["results"]:
                chunk = CandidateChunk.from_retrieval_item(
                    item,
                    query_id=envelope["query_id"],
                    as_of_date="2024-01-01",
                    retriever=envelope["retriever"],
                )
                assert chunk.retrieval_source == envelope["retriever"]

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
            effective_from="2015-01-01",
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
            effective_from="2015-01-01",
        )

        payload = ContextPayload(
            query_id="dev_q02",
            query="Hỏi về ly hôn",
            as_of_date="2024-01-01",
            as_of_date_source="benchmark",
            evidence_items=[item1, item2],
        )

        # Tự động tính total_chars
        assert payload.total_chars == len(item1.content) + len(item2.content)
        # Tự động tạo source_map
        assert 1 in payload.source_map and 2 in payload.source_map
        assert payload.source_map[1]["chunk_id"] == "chunk_a"
        assert payload.source_map[2]["chunk_id"] == "chunk_b"

    def test_context_payload_rejects_non_contiguous_indices(self):
        item1 = EvidenceItem(
            evidence_index=1,
            chunk_id="c1",
            parent_clause_id="p1",
            document_id="d1",
            article_id="a1",
            clause_id="cl1",
            content="Nội dung 1",
            validity_status="Còn hiệu lực",
        )
        item3 = EvidenceItem(
            evidence_index=3,
            chunk_id="c3",
            parent_clause_id="p3",
            document_id="d3",
            article_id="a3",
            clause_id="cl3",
            content="Nội dung 3",
            validity_status="Còn hiệu lực",
        )

        with pytest.raises(ValidationError, match="duy nhất và liên tục"):
            ContextPayload(
                query_id="q_bad_idx",
                query="Query",
                as_of_date="2024-01-01",
                as_of_date_source="benchmark",
                evidence_items=[item1, item3],
            )

    def test_context_payload_rejects_total_chars_exceeding_max(self):
        long_content = "X" * 3500
        item1 = EvidenceItem(
            evidence_index=1,
            chunk_id="c1",
            parent_clause_id="p1",
            document_id="d1",
            article_id="a1",
            clause_id="cl1",
            content=long_content,
            validity_status="Còn hiệu lực",
        )
        item2 = EvidenceItem(
            evidence_index=2,
            chunk_id="c2",
            parent_clause_id="p2",
            document_id="d2",
            article_id="a2",
            clause_id="cl2",
            content=long_content,
            validity_status="Còn hiệu lực",
        )
        # 3500 * 2 = 7000 > max_context_chars (6000)
        with pytest.raises(ValidationError, match="vượt quá giới hạn max_context_chars"):
            ContextPayload(
                query_id="q_overflow",
                query="Query",
                as_of_date="2024-01-01",
                as_of_date_source="benchmark",
                evidence_items=[item1, item2],
            )

    def test_context_payload_rejects_invalid_date(self):
        item1 = EvidenceItem(
            evidence_index=1,
            chunk_id="c1",
            parent_clause_id="p1",
            document_id="d1",
            article_id="a1",
            clause_id="cl1",
            content="Content",
            validity_status="Còn hiệu lực",
        )
        with pytest.raises(ValidationError, match="ISO"):
            ContextPayload(
                query_id="q_date_fail",
                query="Query",
                as_of_date="not-a-date",
                as_of_date_source="benchmark",
                evidence_items=[item1],
            )
        with pytest.raises(ValidationError, match="không phải ngày hợp lệ"):
            ContextPayload(
                query_id="q_date_fail",
                query="Query",
                as_of_date="2024-13-45",
                as_of_date_source="benchmark",
                evidence_items=[item1],
            )

    def test_context_payload_rejects_inconsistent_source_map_and_total_chars(self):
        item1 = EvidenceItem(
            evidence_index=1,
            chunk_id="c1",
            parent_clause_id="p1",
            document_id="d1",
            article_id="a1",
            clause_id="cl1",
            content="X" * 9000,
            validity_status="Còn hiệu lực",
        )
        base = dict(query_id="q", query="Query", as_of_date="2024-01-01", as_of_date_source="benchmark")
        # total_chars truyền tay không được che ngân sách thật
        with pytest.raises(ValidationError, match="total_chars"):
            ContextPayload(**base, evidence_items=[item1], total_chars=100)
        # source_map truyền tay phải giống map dựng từ evidence_items
        short = item1.model_copy(update={"content": "Nội dung"})
        with pytest.raises(ValidationError, match="source_map"):
            ContextPayload(**base, evidence_items=[short], source_map={1: {"chunk_id": "ZZZ"}})

    def test_structured_rag_output_constraints(self):
        out = StructuredRAGOutput(
            answer="Điều kiện ly hôn là...",
            evidence_indices=[1, 3],
            abstained=False,
        )
        assert out.evidence_indices == [1, 3]

        # JSON Schema gửi Ollama giới hạn index trong [1, 5]
        items = StructuredRAGOutput.model_json_schema()["properties"]["evidence_indices"]["items"]
        assert items["minimum"] == 1 and items["maximum"] == 5

        # Chặn nếu đưa string chunk_id vào evidence_indices
        with pytest.raises(ValidationError):
            StructuredRAGOutput(
                answer="Answer",
                evidence_indices=["chunk_123"],  # type: ignore
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
        assert PROMPT_A_VERSION == "v1.1_zero_shot"
        assert PROMPT_B_VERSION == "v1.2_controlled_rag"
        assert STANDARD_DISCLAIMER == "Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."

    def test_prompt_hash(self):
        h1 = get_prompt_hash("Sample prompt text")
        h2 = get_prompt_hash("Sample prompt text")
        h3 = get_prompt_hash("Different text")
        assert len(h1) == 64
        assert h1 == h2
        assert h1 != h3

    def test_build_zero_shot_prompt_formatting(self):
        prompt = build_zero_shot_prompt(
            query="Độ tuổi kết hôn hợp pháp của nam và nữ?",
            as_of_date="2024-01-01",
        )
        assert PROMPT_A_VERSION in prompt
        assert STANDARD_DISCLAIMER in prompt
        assert "Theo quy định có hiệu lực tại ngày 2024-01-01..." in prompt
        assert "Độ tuổi kết hôn hợp pháp của nam và nữ?" in prompt
        assert "Hôn nhân và Gia đình Việt Nam" in prompt
        assert "1. Chỉ trả lời" in prompt
        assert "2. Nếu câu hỏi" in prompt
        assert "3. Thời điểm hiệu lực" in prompt
        assert "4. Cuối câu trả lời" in prompt
        assert "5. NGÔN NGỮ VÀ NGUỒN LUẬT" in prompt

    def test_build_controlled_rag_prompt_formatting(self):
        item1 = EvidenceItem(
            evidence_index=1,
            chunk_id="hn_gd_art_8_clause_1",
            parent_clause_id="hn_gd_art_8_clause_1",
            document_id="law_hn_gd_2014",
            document_title="Luật Hôn nhân và gia đình 2014",
            document_number="52/2014/QH13",
            article_id="art_8",
            clause_id="clause_1",
            breadcrumb="Điều 8 Khoản 1",
            content="Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên.",
            validity_status="Còn hiệu lực",
            effective_from="2015-01-01",
            effective_to=None,
        )
        payload = ContextPayload(
            query_id="dev_q03",
            query="Tuổi kết hôn là bao nhiêu?",
            as_of_date="2024-01-01",
            as_of_date_source="benchmark",
            evidence_items=[item1],
        )

        prompt = build_controlled_rag_prompt(payload)
        assert PROMPT_B_VERSION in prompt
        assert STANDARD_DISCLAIMER in prompt
        assert "Chỉ tư vấn trong phạm vi pháp luật Hôn nhân và Gia đình Việt Nam" in prompt
        assert "[1] Luật Hôn nhân và gia đình 2014 (52/2014/QH13) | Điều 8 Khoản 1 | Hiệu lực: Còn hiệu lực (2015-01-01 -> )" in prompt
        assert "Nội dung: Nam từ đủ 20 tuổi trở lên" in prompt
        assert "tự suy diễn" in prompt
        assert "evidence_indices" in prompt

    def test_build_controlled_rag_prompt_rejects_empty(self):
        with pytest.raises(ValidationError):
            ContextPayload(
                query_id="q_empty",
                query="Query",
                as_of_date="2024-01-01",
                as_of_date_source="benchmark",
                evidence_items=[],
            )

    def test_map_evidence_indices_to_citations_dedupes(self):
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
            as_of_date_source="benchmark",
            evidence_items=[item1, item2],
        )

        # Trùng lặp [1, 1, 2, 6, 99] -> khử trùng [1, 2], invalid [6, 99]
        valid_citations, invalid_indices = map_evidence_indices_to_citations([1, 1, 2, 6, 99], payload)
        assert len(valid_citations) == 2
        assert valid_citations[0].evidence_index == 1
        assert valid_citations[1].evidence_index == 2
        assert invalid_indices == [6, 99]


# =============================================================================
# 3. Tests for Qwen Model Gateway & Provenance (DoD-10)
# =============================================================================

class TestQwenModelGateway:
    def test_gateway_config_and_hyperparameters(self):
        gateway = QwenGateway()
        assert gateway.config.model == "qwen2.5:7b"
        assert gateway.config.temperature == 0.0
        assert gateway.config.repeat_penalty == 1.0
        assert gateway.config.num_predict == 1024
        assert gateway.config.num_ctx == 8192
        assert gateway.config.fallback_locked is True

    def test_gateway_run_a_zero_shot(self):
        recorded_calls = []

        def mock_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            recorded_calls.append({"url": url, "payload": payload, "timeout": timeout})
            return {
                "model": "qwen2.5:7b",
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

        assert len(recorded_calls) >= 1
        sent_payload = recorded_calls[-1]["payload"]
        assert sent_payload["options"]["num_ctx"] == 8192
        assert sent_payload["options"]["num_predict"] == 1024
        assert sent_payload["options"]["temperature"] == 0.0
        assert sent_payload["options"]["repeat_penalty"] == 1.0
        assert "format" not in sent_payload

        assert resp.query_id == "q_zero"
        assert resp.run_mode == "A_zero_shot"
        assert resp.parse_status == "raw_text"
        assert resp.done_reason == "stop"
        assert resp.truncated is False
        assert resp.context_truncated is False
        assert resp.token_usage.input == 80
        assert resp.token_usage.output == 25

    def test_gateway_run_b_structured_output_ok(self):
        def mock_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            return {
                "model": "qwen2.5:7b",
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

        assert resp.parse_status == "ok"
        assert resp.evidence_indices == [1]
        assert resp.abstained is False
        assert resp.truncated is False

    def test_gateway_run_b_parses_out_of_bound_indices_as_ok(self):
        def mock_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            return {
                "model": "qwen2.5:7b",
                "response": json.dumps({
                    "answer": "Trả lời câu hỏi.",
                    "evidence_indices": [1, 6],
                    "abstained": False,
                }),
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 200,
                "eval_count": 40,
            }

        gateway = QwenGateway(transport=mock_transport)
        resp = gateway.generate(
            prompt="Prompt RAG B",
            query_id="q_oob",
            run_mode="B_controlled_rag",
            prompt_version=PROMPT_B_VERSION,
            structured_output=True,
        )

        assert resp.parse_status == "ok"
        assert resp.evidence_indices == [1, 6]

    def test_gateway_context_truncated_detection(self):
        def mock_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            return {
                "model": "qwen2.5:7b",
                "response": "Answer",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 8192,  # Bằng trần num_ctx
                "eval_count": 100,
            }

        gateway = QwenGateway(transport=mock_transport)
        resp = gateway.generate(
            prompt="Prompt Long",
            query_id="q_ctx_trunc",
            run_mode="A_zero_shot",
            prompt_version=PROMPT_A_VERSION,
        )
        assert resp.context_truncated is True

    @pytest.mark.parametrize("served", ["qwen2.5:3b", "qwen2.5:14b", "qwen2.5"])
    def test_gateway_rejects_other_tag_of_same_family(self, served):
        gateway = QwenGateway(transport=lambda url, payload, timeout: {
            "model": served, "response": "Answer", "done": True, "done_reason": "stop",
        })
        with pytest.raises(GatewayExecutionError, match="không khớp"):
            gateway.generate(prompt="P", query_id="q", run_mode="A_zero_shot", prompt_version=PROMPT_A_VERSION)

    def test_gateway_accepts_same_model_ignoring_case_and_latest_tag(self):
        gateway = QwenGateway(
            {"model": "llama3"},
            transport=lambda url, payload, timeout: {
                "model": "Llama3:latest", "response": "Answer", "done": True, "done_reason": "stop",
            },
        )
        resp = gateway.generate(prompt="P", query_id="q", run_mode="A_zero_shot", prompt_version=PROMPT_A_VERSION)
        assert resp.answer == "Answer"

    def test_gateway_keeps_non_integer_indices_and_abstention_reason(self):
        gateway = QwenGateway(transport=lambda url, payload, timeout: {
            "model": "qwen2.5:7b",
            "response": json.dumps({
                "answer": "Không đủ căn cứ.",
                "evidence_indices": ["1", 2.0, True, 3],
                "abstained": True,
                "abstention_reason": "Evidence không nói về độ tuổi",
            }),
            "done": True,
            "done_reason": "stop",
        })
        resp = gateway.generate(
            prompt="P", query_id="q", run_mode="B_controlled_rag",
            prompt_version=PROMPT_B_VERSION, structured_output=True,
        )
        assert resp.parse_status == "ok"
        assert resp.evidence_indices == [3]
        assert resp.rejected_evidence_values == ['"1"', "2.0", "true"]
        assert resp.abstention_reason == "Evidence không nói về độ tuổi"

    def test_probe_reads_digest_from_api_tags(self):
        class FakeResponse:
            def __init__(self, data):
                self.status_code = 200
                self._data = data

            def json(self):
                return self._data

        class FakeSession:
            def get(self, url, timeout):
                if url.endswith("/api/version"):
                    return FakeResponse({"version": "0.6.2"})
                return FakeResponse({"models": [
                    {"name": "qwen2.5:3b", "model": "qwen2.5:3b", "digest": "sha256:other"},
                    {"name": "qwen2.5:7b", "model": "qwen2.5:7b", "digest": "sha256:abc123"},
                ]})

        gateway = QwenGateway(transport=lambda url, payload, timeout: {})
        gateway._session = FakeSession()
        gateway._probe_ollama_metadata()
        assert gateway.ollama_version == "0.6.2"
        assert gateway.model_digest == "sha256:abc123"

    def test_gateway_rejects_mismatched_model(self):
        def mock_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            return {
                "model": "llama3.1:8b",  # Khác model qwen2.5:7b
                "response": "Answer",
                "done": True,
            }

        gateway = QwenGateway(transport=mock_transport)
        with pytest.raises(GatewayExecutionError, match="không khớp"):
            gateway.generate(
                prompt="Prompt",
                query_id="q_mismatch",
                run_mode="A_zero_shot",
                prompt_version=PROMPT_A_VERSION,
            )

    def test_gateway_run_b_truncation_detection(self):
        def mock_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            return {
                "model": "qwen2.5:7b",
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

        assert resp.parse_status == "truncated_json"
        assert resp.truncated is True
        assert resp.done_reason == "length"
        assert resp.answer == ""

    def test_gateway_retry_and_fail_fast(self):
        call_count = 0

        def failing_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Connection timed out")

        gateway = QwenGateway(transport=failing_transport)

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
            context_truncated=False,
            parse_status="ok",
            latency_ms=100.0,
            token_usage=TokenUsage(input=200, output=50),
        )
        r2 = LLMResponse(
            query_id="q2",
            run_mode="B_controlled_rag",
            answer="",
            evidence_indices=[],
            prompt_version=PROMPT_B_VERSION,
            done_reason="length",
            truncated=True,
            context_truncated=True,
            parse_status="truncated_json",
            latency_ms=300.0,
            token_usage=TokenUsage(input=8192, output=1024),
        )

        summary = summarize_truncation_and_provenance([r1, r2])
        assert summary["total_queries"] == 2
        assert summary["truncation_count"] == 1
        assert summary["truncation_rate"] == 0.5
        assert summary["context_truncated_count"] == 1
        assert summary["context_truncated_rate"] == 0.5
        assert summary["json_parse_failure_count"] == 1
        assert summary["json_parse_failure_rate"] == 0.5
        assert summary["total_input_tokens"] == 8392
        assert summary["total_output_tokens"] == 1074


# =============================================================================
# 4. Tests for Embedding Ownership Handoff (Task D3.5)
# =============================================================================

class TestEmbeddingOwnershipHandoff:
    def test_production_model_spec_from_config(self):
        spec = get_embedding_spec("BAAI/bge-m3")
        assert spec["name"] == "BAAI/bge-m3"
        assert spec["dimension"] == 1024
        assert spec["use_word_segmentation"] is False
        assert spec["text_field"] == "embed_text_raw"
        assert spec["collection_name"] == "vietnam_legal_chunks"

    def test_get_index_spec(self):
        meta = get_index_spec()
        assert meta["collection_name"] == "vietnam_legal_chunks"
        assert meta["vector_size"] == 1024
        assert meta["dimension"] == 1024
        assert meta["model_name"] == "BAAI/bge-m3"
        assert meta["text_field"] == "embed_text_raw"

    def test_registry_does_not_shadow_built_index_metadata_reader(self):
        # read_index_metadata của vector_store đọc metadata index thật; registry không có hàm cùng tên
        import embedding.model_registry as registry_module

        assert not hasattr(registry_module, "read_index_metadata")

    def test_validate_collection_dimension_success_and_fail_fast(self):
        assert validate_collection_dimension("BAAI/bge-m3", 1024) is True
        with pytest.raises(ValueError, match="Lệch chiều vector"):
            validate_collection_dimension("BAAI/bge-m3", 768)

    def test_prepare_text_for_embedding_calls_preprocess_text(self):
        raw = "  Điều 56.   Ly hôn   theo yêu cầu  của một bên   "
        prepared = prepare_text_for_embedding(raw, "BAAI/bge-m3")
        assert prepared == "Điều 56. Ly hôn theo yêu cầu của một bên"
