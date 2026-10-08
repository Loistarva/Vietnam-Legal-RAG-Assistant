import json
import pytest
from datetime import date
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, constr, field_validator, ValidationError


# --- Pydantic Models for Validation ---

class ChunkSchema(BaseModel):
    chunk_id: str
    clause_number: Optional[str] = None
    point_letter: Optional[str] = None
    text: str = Field(..., min_length=10)
    parent_clause_id: str
    char_count: Optional[int] = None

    @field_validator('text')
    @classmethod
    def text_must_be_clean(cls, v):
        if '\x00' in v:
            raise ValueError('Văn bản chứa ký tự lỗi (null byte)')
        return v.strip()

class ClauseSchema(BaseModel):
    clause_id: str
    clause_number: str
    clause_text: str = Field(..., description="Nội dung thô của toàn bộ Khoản (Dành cho Parser)")
    # Để Optional: Parser không cần quan tâm, Chunking sẽ điền sau
    chunks: Optional[List[ChunkSchema]] = None
    parent_article_id: str

    @field_validator('chunks')
    @classmethod
    def chunks_parent_id_must_match_clause(cls, v, info):
        if v and 'clause_id' in info.data:
            for chunk in v:
                if chunk.parent_clause_id != info.data['clause_id']:
                    raise ValueError(f"Chunk {chunk.chunk_id} sai parent_id")
        return v

class ArticleSchema(BaseModel):
    article_id: str
    article_number: str
    article_title: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    intro: Optional[str] = None
    clauses: List[ClauseSchema] = Field(..., min_length=1)

class LegalMetadata(BaseModel):
    title: str = Field(..., min_length=5)
    document_type: Literal["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị"]
    document_number: str
    issue_date: date
    effective_date: date
    issuing_body: str
    validity_status: Literal["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung"]

class LegalDocumentSchema(BaseModel):
    document_id: str = Field(..., pattern=r'^[a-zA-Z0-9_]+$')
    metadata: LegalMetadata
    articles: List[ArticleSchema] = Field(..., min_length=1)
    footnotes: List[str] = Field(default_factory=list)


# --- Pytest Test Cases ---

def test_valid_sample_document():
    with open("data/sample_documents.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for doc in data:
        try:
            validated_doc = LegalDocumentSchema(**doc)
            assert validated_doc.document_id == doc["document_id"]
        except ValidationError as e:
            pytest.fail(f"Lỗi schema trên document {doc.get('document_id', 'unknown')}: {e}")


def test_schema_with_raw_parser_data():
    raw_data = {
        "document_id": "nd_100",
        "metadata": {
            "title": "Nghị định 100",
            "document_type": "Nghị định",
            "document_number": "100/2019/NĐ-CP",
            "issue_date": "2019-12-30",
            "effective_date": "2020-01-01",
            "issuing_body": "Chính phủ",
            "validity_status": "Còn hiệu lực"
        },
        "articles": [
            {
                "article_id": "nd_100_art_1",
                "article_number": "1",
                "clauses": [
                    {
                        "clause_id": "nd_100_art_1_clause_1",
                        "clause_number": "1",
                        "clause_text": "Phạm vi điều chỉnh của nghị định này...",
                        "parent_article_id": "nd_100_art_1"
                    }
                ]
            }
        ]
    }

    try:
        validated_doc = LegalDocumentSchema(**raw_data)
        assert validated_doc.document_id == "nd_100"
    except ValidationError as e:
        pytest.fail(f"Lỗi schema: {e}")