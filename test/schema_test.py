import copy
import json
import re
from datetime import date
from pathlib import Path
from typing import List, Literal, Optional

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
    clause_number: Optional[str] = None
    point_letter: Optional[str] = None
    chunk_text: str = Field(..., min_length=10)
    char_count: Optional[int] = None

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
    chunks: Optional[List[ChunkSchema]] = None

    _clean_clause_text = field_validator("clause_text", mode="before")(clean_text)

    @model_validator(mode="after")
    def chunks_must_belong_to_clause(self):
        for chunk in self.chunks or []:
            ensure_parent_match("Chunk", chunk.chunk_id, "parent_clause_id", chunk.parent_clause_id, self.clause_id)
        return self


class ArticleSchema(BaseSchema):
    article_id: str
    article_number: str
    article_title: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    intro: Optional[str] = None
    clauses: List[ClauseSchema] = Field(..., min_length=1)

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
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_body: str
    validity_status: ValidityStatus
    source_url: Optional[str] = ""
    source_status: Optional[str] = None
    provision_status: Optional[str] = None


class LegalDocumentSchema(BaseSchema):
    document_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    metadata: DocumentMetadataSchema
    articles: List[ArticleSchema] = Field(..., min_length=1)
    footnotes: List[str] = Field(default_factory=list)


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
