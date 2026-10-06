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
    parent_id: str
    char_count: Optional[int] = None

    @field_validator('text')
    @classmethod
    def text_must_be_clean(cls, v):
        if '\x00' in v:
            raise ValueError('Văn bản chứa ký tự lỗi (null byte)')
        return v.strip()


class ArticleSchema(BaseModel):
    article_id: str
    article_number: str
    article_title: Optional[str] = None
    chunks: List[ChunkSchema] = Field(..., min_length=1)

    @field_validator('chunks')
    @classmethod
    def chunks_parent_id_must_match_article(cls, v, info):
        if 'article_id' in info.data:
            for chunk in v:
                if chunk.parent_id != info.data['article_id']:
                    raise ValueError(f"Chunk {chunk.chunk_id} có parent_id không khớp với article_id")
        return v


class DocumentMetadataSchema(BaseModel):
    title: str = Field(..., min_length=5)
    document_type: Literal["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị"]
    document_number: str
    issue_date: date
    effective_date: date
    issuing_body: str
    validity_status: Literal["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung"]


class LegalDocumentSchema(BaseModel):
    # document_id: constr(pattern=r'^[a-z0-9_]+$')
    document_id: str = Field(..., pattern=r'^[a-zA-Z0-9_]+$')
    document_metadata: DocumentMetadataSchema
    articles: List[ArticleSchema] = Field(..., min_length=1)


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


def test_invalid_chunk_parent_id_relation():
    invalid_data = {
        "document_id": "nd_100",
        "document_metadata": {
            "title": "Nghị định Test",
            "document_type": "Nghị định",
            "document_number": "100",
            "issue_date": "2020-01-01",
            "effective_date": "2020-01-01",
            "issuing_body": "CP",
            "validity_status": "Còn hiệu lực"
        },
        "articles": [
            {
                "article_id": "nd_100_art_1",
                "article_number": "1",
                "chunks": [
                    {
                        "chunk_id": "chunk_1",
                        "text": "Nội dung hợp lệ độ dài trên 10 ký tự",
                        "parent_id": "WRONG_PARENT_ID"
                    }
                ]
            }
        ]
    }

    with pytest.raises(ValidationError) as excinfo:
        LegalDocumentSchema(**invalid_data)

    assert "parent_id không khớp với article_id" in str(excinfo.value)