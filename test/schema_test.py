import copy
import json
from datetime import date
from pathlib import Path
from typing import List, Literal, Optional

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
# -----------------------------------------------------------------------------
# 1. Mọi class đều có hậu tố `Schema`.
# 2. Mọi id đều theo dạng `<cấp>_id`; khóa ngoại theo dạng `parent_<cấp cha>_id`.
# 3. Mọi số thứ tự theo dạng `<cấp>_number`; mọi nội dung theo dạng `<cấp>_text`.
# 4. Mọi validator quan hệ cha-con dùng chung một helper và một mẫu thông báo lỗi.
# =============================================================================

DocumentType = Literal["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị"]
ValidityStatus = Literal["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung"]


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
    effective_date: date
    issuing_body: str
    validity_status: ValidityStatus


class LegalDocumentSchema(BaseSchema):
    document_id: str = Field(..., pattern=r"^[a-zA-Z0-9_]+$")
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
                "issuing_body": "Chính phủ",
                "validity_status": "Còn hiệu lực",
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