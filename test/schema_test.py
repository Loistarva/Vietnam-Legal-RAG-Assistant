import copy
import json
import re
from datetime import date
from pathlib import Path
from typing import Literal

import jsonschema
import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

SAMPLE_PATH = Path(__file__).parent.parent / "data" / "sample_documents.json"


# =============================================================================
# Quy ước chung
# ----------------------------------------------------------------------------─
# 1. Mọi class đều có hậu tố `Schema`.
# 2. Mọi id đều theo dạng `<cấp>_id`; khóa ngoại theo dạng `parent_<cấp cha>_id`.
# 3. Mọi số thứ tự theo dạng `<cấp>_number`; mọi nội dung theo dạng `<cấp>_text`.
# 4. Mọi validator quan hệ cha-con dùng chung một helper và một mẫu thông báo lỗi.
# =============================================================================

DocumentType = Literal["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị", "Nghị quyết", "Thông tư liên tịch"]
ValidityStatus = Literal["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung", "Không xác định"]


def clean_text(value):
    """Chặn null byte và strip TRƯỚC khi kiểm tra min_length."""
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("Văn bản chứa ký tự lỗi (null byte)")
        return value.strip()
    return value


def ensure_parent_match(child_name: str, child_id: str, parent_field: str, actual: str, expected: str) -> None:
    """Một mẫu thông báo lỗi duy nhất cho mọi quan hệ cha-con."""
    if actual != expected:
        raise ValueError(
            f"{child_name} {child_id} có {parent_field} '{actual}' "
            f"không khớp với {parent_field.removeprefix('parent_')} '{expected}'"
        )


class BaseSchema(BaseModel):
    # Bắt field thừa hoặc sai tên thay vì lặng lẽ bỏ qua
    model_config = ConfigDict(extra="forbid")


# --- Schemas -----------------------------------------------------------------

class ChunkSchema(BaseSchema):
    chunk_id: str
    parent_clause_id: str
    clause_number: str | None = None
    point_letter: str | None = None
    chunk_text: str = Field(..., min_length=10)
    char_count: int | None = None

    _clean_chunk_text = field_validator("chunk_text", mode="before")(clean_text)

    @model_validator(mode="after")
    def compute_char_count(self):
        if self.char_count is None:
            self.char_count = len(self.chunk_text)
        return self


class ClauseSchema(BaseSchema):
    clause_id: str
    parent_article_id: str
    clause_number: str
    clause_text: str = Field(..., min_length=1, description="Nội dung thô của toàn bộ Khoản (dành cho Parser)")
    # Optional: Parser không cần quan tâm, bước Chunking sẽ điền sau
    chunks: list[ChunkSchema] | None = None

    _clean_clause_text = field_validator("clause_text", mode="before")(clean_text)

    @model_validator(mode="after")
    def chunks_must_belong_to_clause(self):
        for chunk in self.chunks or []:
            ensure_parent_match("Chunk", chunk.chunk_id, "parent_clause_id", chunk.parent_clause_id, self.clause_id)
        return self


class ArticleSchema(BaseSchema):
    article_id: str
    article_number: str
    article_title: str | None = None
    chapter: str | None = None
    section: str | None = None
    intro: str | None = None
    clauses: list[ClauseSchema] = Field(..., min_length=1)

    @model_validator(mode="after")
    def clauses_must_belong_to_article(self):
        for clause in self.clauses:
            ensure_parent_match("Clause", clause.clause_id, "parent_article_id", clause.parent_article_id, self.article_id)
        return self


class DocumentMetadataSchema(BaseSchema):
    title: str = Field(..., min_length=5)
    document_type: DocumentType
    document_number: str
    issue_date: date
    effective_date: date | None = None
    expiry_date: date | None = None
    issuing_body: str
    validity_status: ValidityStatus
    source_url: str | None = ""
    source_status: str | None = None
    provision_status: str | None = None


class LegalDocumentSchema(BaseSchema):
    document_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    metadata: DocumentMetadataSchema
    articles: list[ArticleSchema] = Field(..., min_length=1)
    footnotes: list[str] = Field(default_factory=list)


# =============================================================================
# Tests
# =============================================================================

@pytest.fixture
def make_doc():
    """Factory tạo document hợp lệ; truyền override để tạo dữ liệu sai."""

    def _make(clause_overrides=None, chunk_overrides=None, with_chunks=True):
        chunk = {
            "chunk_id": "nd_100_art_1_clause_1_chunk_1",
            "parent_clause_id": "nd_100_art_1_clause_1",
            "chunk_text": "Nội dung hợp lệ trên 10 ký tự",
        }
        chunk.update(chunk_overrides or {})

        clause = {
            "clause_id": "nd_100_art_1_clause_1",
            "parent_article_id": "nd_100_art_1",
            "clause_number": "1",
            "clause_text": "Phạm vi điều chỉnh của nghị định này...",
        }
        if with_chunks:
            clause["chunks"] = [chunk]
        clause.update(clause_overrides or {})

        return copy.deepcopy({
            "document_id": "nd_100",
            "metadata": {
                "title": "Nghị định 100",
                "document_type": "Nghị định",
                "document_number": "100/2019/NĐ-CP",
                "issue_date": "2019-12-30",
                "effective_date": "2020-01-01",
                "expiry_date": None,
                "issuing_body": "Chính phủ",
                "validity_status": "Còn hiệu lực",
                "source_url": "https://thuvienphapluat.vn",
            },
            "articles": [{
                "article_id": "nd_100_art_1",
                "article_number": "1",
                "clauses": [clause],
            }],
        })

    return _make


# --- Test dương --------------------------------------------------------------

def test_valid_sample_documents():
    if not SAMPLE_PATH.exists():
        pytest.skip(f"Không tìm thấy {SAMPLE_PATH}")
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))

    for doc in data:
        validated = LegalDocumentSchema(**doc)
        assert validated.document_id == doc["document_id"]


def test_valid_parser_output_without_chunks(make_doc):
    doc = LegalDocumentSchema(**make_doc(with_chunks=False))
    assert doc.articles[0].clauses[0].chunks is None


def test_valid_chunked_output(make_doc):
    doc = LegalDocumentSchema(**make_doc())
    assert len(doc.articles[0].clauses[0].chunks) == 1


# --- Test âm: quan hệ cha-con --------------------------------------------------

def test_chunk_wrong_parent_clause_id(make_doc):
    data = make_doc(chunk_overrides={"parent_clause_id": "WRONG"})
    with pytest.raises(ValidationError, match="không khớp với clause_id"):
        LegalDocumentSchema(**data)


def test_clause_wrong_parent_article_id(make_doc):
    data = make_doc(clause_overrides={"parent_article_id": "WRONG"})
    with pytest.raises(ValidationError, match="không khớp với article_id"):
        LegalDocumentSchema(**data)


# --- Test âm: nội dung văn bản -------------------------------------------------

def test_chunk_text_with_null_byte(make_doc):
    data = make_doc(chunk_overrides={"chunk_text": "Nội dung có \x00 ký tự lỗi"})
    with pytest.raises(ValidationError, match="null byte"):
        LegalDocumentSchema(**data)


def test_chunk_text_too_short_after_strip(make_doc):
    data = make_doc(chunk_overrides={"chunk_text": "abc          "})
    with pytest.raises(ValidationError):
        LegalDocumentSchema(**data)


# --- Test âm: cấu trúc ---------------------------------------------------------

def test_extra_field_is_rejected(make_doc):
    data = make_doc()
    data["document_metadata"] = data.pop("metadata")  # tên field cũ
    with pytest.raises(ValidationError):
        LegalDocumentSchema(**data)


def test_empty_clauses_rejected(make_doc):
    data = make_doc()
    data["articles"][0]["clauses"] = []
    with pytest.raises(ValidationError):
        LegalDocumentSchema(**data)


def test_all_parsed_json_files():
    parsed_dir = Path(__file__).parent.parent / "parser" / "parsed_jsons"
    json_files = list(parsed_dir.glob("*.json"))
    assert len(json_files) > 0, "Không tìm thấy file JSON nào trong parser/parsed_jsons"
    for f in json_files:
        data = json.loads(f.read_text(encoding="utf-8"))
        doc = LegalDocumentSchema(**data)
        assert doc.document_id in f.stem


def test_corpus_chunks_jsonl():
    base_dir = Path(__file__).resolve().parent.parent
    chunks_file = base_dir / "data" / "chunking_output" / "chunks.jsonl"
    schema_file = base_dir / "schemas" / "chunk_payload_schema.json"
    parsed_files = list(base_dir.glob("parser/parsed_jsons/*.json"))

    assert chunks_file.exists(), f"Không tìm thấy file corpus: {chunks_file}"
    assert schema_file.exists(), f"Không tìm thấy file schema: {schema_file}"

    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    # Thu thập tất cả clause_id tồn tại trong tập dữ liệu parsed JSON của parser
    parsed_clause_ids = set()
    for pf in parsed_files:
        doc_json = json.loads(pf.read_text(encoding="utf-8"))
        for art in doc_json.get("articles", []):
            for cl in art.get("clauses", []):
                cid = cl.get("clause_id")
                if cid:
                    parsed_clause_ids.add(cid)

    assert len(parsed_clause_ids) > 0, "Không tìm thấy clause_id nào trong parser dataset"

    lines = [line.strip() for line in chunks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) > 0, f"File {chunks_file} rỗng"

    for line_idx, line in enumerate(lines, start=1):
        record = json.loads(line)

        # 1. Validate thành công qua cấu trúc của schemas/chunk_payload_schema.json
        errors = list(validator.iter_errors(record))
        assert not errors, f"Dòng {line_idx} ({record.get('chunk_id')}) không khớp schema: {errors}"

        # 2. Kiểm tra len(chunk_text.strip()) >= 10
        chunk_text = record.get("chunk_text", "")
        assert len(chunk_text.strip()) >= 10, (
            f"Dòng {line_idx} ({record.get('chunk_id')}) có chunk_text quá ngắn (< 10 ký tự): '{chunk_text}'"
        )

        # 3. Kiểm tra chunk_id phải khớp định dạng chứa parent_clause_id và hậu tố _chunk_\d+
        chunk_id = record.get("chunk_id", "")
        parent_clause_id = record.get("parent_clause_id", "")
        expected_pattern = rf"^{re.escape(parent_clause_id)}_chunk_\d+$"
        assert re.match(expected_pattern, chunk_id), (
            f"Dòng {line_idx}: chunk_id '{chunk_id}' không khớp định dạng '{parent_clause_id}_chunk_\\d+'"
        )

        # 4. Kiểm tra parent_clause_id tồn tại trong tập dữ liệu parsed JSON của parser
        assert parent_clause_id in parsed_clause_ids, (
            f"Dòng {line_idx}: parent_clause_id '{parent_clause_id}' không tồn tại trong dữ liệu parser"
        )

        # 5. Metadata checks: effective_from và source_url không rỗng; Hết hiệu lực -> effective_to khác null
        meta = record.get("metadata", {})
        eff_from = meta.get("effective_from")
        src_url = meta.get("source_url")
        val_status = meta.get("validity_status")
        eff_to = meta.get("effective_to")

        assert eff_from and isinstance(eff_from, str) and eff_from.strip(), (
            f"Dòng {line_idx} ({record.get('chunk_id')}): effective_from không được rỗng"
        )
        assert src_url and isinstance(src_url, str) and src_url.strip(), (
            f"Dòng {line_idx} ({record.get('chunk_id')}): source_url không được rỗng"
        )
        if val_status == "Hết hiệu lực":
            assert eff_to is not None and isinstance(eff_to, str) and eff_to.strip(), (
                f"Dòng {line_idx} ({record.get('chunk_id')}): văn bản Hết hiệu lực bắt buộc phải có effective_to khác null"
            )


# Bảng ánh xạ status -> validity_status của registry (data_contract.md, mục 3.1).
REGISTRY_STATUS_MAPPING = {
    "Còn hiệu lực": "Còn hiệu lực",
    "Hết hiệu lực toàn bộ": "Hết hiệu lực",
    "Hết hiệu lực một phần": "Sửa đổi bổ sung",
    "Có điều khoản bị sửa đổi / bãi bỏ": "Sửa đổi bổ sung",
    "Cần kiểm tra trạng thái mới nhất": "Không xác định",
}


def test_registry_validity_status_mapping():
    registry_file = Path(__file__).resolve().parent.parent / "data" / "reference" / "document_versions.json"
    records = json.loads(registry_file.read_text(encoding="utf-8"))
    assert len(records) > 0, f"Registry rỗng: {registry_file}"

    for record in records:
        number = record.get("document_number")
        status = record.get("source_status") or record.get("status")
        validity_status = record.get("validity_status")
        assert status in REGISTRY_STATUS_MAPPING, (
            f"{number}: status '{status}' chưa có trong bảng ánh xạ của data_contract.md"
        )
        assert validity_status == REGISTRY_STATUS_MAPPING[status], (
            f"{number}: status '{status}' phải ánh xạ thành '{REGISTRY_STATUS_MAPPING[status]}', "
            f"registry ghi '{validity_status}'"
        )
        if validity_status == "Hết hiệu lực":
            assert record.get("expiry_date"), f"{number}: văn bản Hết hiệu lực bắt buộc có expiry_date"


def test_registry_titles_are_trich_yeu_only():
    """A16: title chỉ ghi trích yếu, không chép lại loại văn bản, số hiệu, ngày ở dòng đầu văn bản."""
    registry_file = Path(__file__).resolve().parent.parent / "data" / "reference" / "document_versions.json"
    for record in json.loads(registry_file.read_text(encoding="utf-8")):
        title = record["title"]
        assert title == title.strip(), f"{record['document_number']}: title có khoảng trắng thừa ở đầu/cuối"
        assert not re.match(r"(Nghị định|Thông tư|Nghị quyết|Quyết định) của ", title), (
            f"{record['document_number']}: title chép cả dòng đầu văn bản: {title[:60]!r}"
        )
        assert record["document_number"] not in title, (
            f"{record['document_number']}: title lặp lại số hiệu của chính văn bản"
        )


# =============================================================================
# Dev 3 Sprint 9 Pydantic & Canonical Schema Tests (DoD-06)
# =============================================================================

def test_candidate_chunk_validation():
    from schemas.models import CandidateChunk

    valid_payload = {
        "query_id": "q_001",
        "chunk_id": "nd_126_art_1_clause_1_chunk_1",
        "chunk_text": "Nội dung quy định chi tiết về...",
        "score": 0.89,
        "rank": 1,
        "retrieval_source": "RRF",
        "validity_status": "Còn hiệu lực",
        "effective_from": "2015-01-01",
        "effective_to": None,
        "as_of_date": "2024-01-01",
        "document_id": "nd_126",
        "article_id": "nd_126_art_1",
        "clause_id": "nd_126_art_1_clause_1",
        "evidence_index": 1,
    }
    candidate = CandidateChunk(**valid_payload)
    assert candidate.query_id == "q_001"
    assert candidate.evidence_index == 1

    # Từ chối query_id rỗng
    invalid_query = copy.deepcopy(valid_payload)
    invalid_query["query_id"] = "   "
    with pytest.raises(ValidationError):
        CandidateChunk(**invalid_query)

    # Từ chối evidence_index ngoài [1, 5]
    invalid_index = copy.deepcopy(valid_payload)
    invalid_index["evidence_index"] = 6
    with pytest.raises(ValidationError):
        CandidateChunk(**invalid_index)

    # Từ chối trường lạ không nằm trong contract
    extra_field = copy.deepcopy(valid_payload)
    extra_field["unexpected_field"] = "malicious_payload"
    with pytest.raises(ValidationError):
        CandidateChunk(**extra_field)


def test_evidence_item_and_context_payload_validation():
    from schemas.models import ContextPayload, EvidenceItem

    item1 = EvidenceItem(
        evidence_index=1,
        chunk_id="chunk_1",
        parent_clause_id="parent_clause_1",
        document_id="doc_1",
        article_id="art_1",
        clause_id="clause_1",
        content="Quy định kết hôn giữa nam và nữ...",
        validity_status="Còn hiệu lực",
        effective_from="2015-01-01",
    )

    payload = ContextPayload(
        query_id="q_001",
        query="Điều kiện kết hôn năm 2024?",
        as_of_date="2024-01-01",
        as_of_date_source="benchmark",
        evidence_items=[item1],
    )
    assert payload.total_chars == len(item1.content)
    assert 1 in payload.source_map
    assert payload.source_map[1]["chunk_id"] == "chunk_1"

    # Kiểm tra chặn rỗng
    with pytest.raises(ValidationError):
        ContextPayload(query_id="", query="abc", as_of_date="2024-01-01", as_of_date_source="benchmark", evidence_items=[item1])


def test_structured_rag_output_and_indices_validation():
    from schemas.models import StructuredRAGOutput

    valid = StructuredRAGOutput(
        answer="Theo quy định, điều kiện kết hôn là...",
        evidence_indices=[1, 2],
        abstained=False,
    )
    assert valid.evidence_indices == [1, 2]

    # Chặn chuỗi chunk_id thay vì số nguyên
    with pytest.raises(ValidationError):
        StructuredRAGOutput(
            answer="Answer",
            evidence_indices=["chunk_123"],  # type: ignore
        )

    # Chặn boolean lẩn vào integer
    with pytest.raises(ValidationError):
        StructuredRAGOutput(
            answer="Answer",
            evidence_indices=[True],  # type: ignore
        )


def test_llm_response_provenance_validation():
    from schemas.models import LLMResponse, TokenUsage

    resp = LLMResponse(
        query_id="q_001",
        run_mode="B_controlled_rag",
        answer="Trả lời câu hỏi dựa trên bằng chứng...",
        evidence_indices=[1],
        prompt_version="v1.0_controlled_rag_m1",
        num_ctx=8192,
        num_predict=1024,
        temperature=0.0,
        repeat_penalty=1.15,
        done_reason="stop",
        truncated=False,
        parse_status="ok",
        latency_ms=125.5,
        token_usage=TokenUsage(input=450, output=120),
    )
    assert resp.model == "qwen2.5:7b"
    assert resp.parse_status == "ok"
    assert not resp.truncated


def test_rag_output_record_appendix_b_schema():
    from schemas.models import MappedCitation, RAGOutputRecord, TokenUsage

    record = RAGOutputRecord(
        query_id="q_001",
        query="Điều kiện kết hôn?",
        as_of_date="2024-01-01",
        as_of_date_source="benchmark",
        answer="Theo Điều 8 Luật Hôn nhân...",
        evidence_indices=[1],
        citations=[
            MappedCitation(
                evidence_index=1,
                chunk_id="hn_gd_art_8_clause_1_chunk_1",
                document_id="hn_gd",
                article_id="hn_gd_art_8",
                clause_id="hn_gd_art_8_clause_1",
            )
        ],
        grounding_status="PASS",
        abstained=False,
        abstention_reason=None,
        abstention_source=None,
        needs_clarification=False,
        retrieval_trace={"top_k": 5, "rerank_used": True},
        model="qwen2.5:7b",
        prompt_version="v1.0_controlled_rag_m1",
        num_ctx=8192,
        num_predict=1024,
        done_reason="stop",
        truncated=False,
        corpus_version="v1.0",
        retrieval_config_version="v1.0",
        threshold_config_version="v1.0",
        latency_ms=150.0,
        llm_calls=1,
        token_usage=TokenUsage(input=500, output=100),
        fallback_status="none",
    )
    assert record.grounding_status == "PASS"
    assert len(record.citations) == 1


def test_exported_json_schemas_match_models():
    base_dir = Path(__file__).resolve().parent.parent
    schemas_dir = base_dir / "schemas"

    candidate_file = schemas_dir / "candidate.schema.json"
    context_file = schemas_dir / "context_payload.schema.json"
    llm_resp_file = schemas_dir / "llm_response.schema.json"

    assert candidate_file.exists()
    assert context_file.exists()
    assert llm_resp_file.exists()

    from schemas.models import CandidateChunk, ContextPayload, StructuredRAGOutput

    assert json.loads(candidate_file.read_text(encoding="utf-8")) == CandidateChunk.model_json_schema()
    assert json.loads(context_file.read_text(encoding="utf-8")) == ContextPayload.model_json_schema()
    assert json.loads(llm_resp_file.read_text(encoding="utf-8")) == StructuredRAGOutput.model_json_schema()
