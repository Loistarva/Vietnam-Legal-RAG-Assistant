# -*- coding: utf-8 -*-
"""
schemas/models.py
Canonical Pydantic models & JSON Schema generation for Sprint 9 (Kế hoạch V3).
Single Source of Truth for:
  - CandidateChunk (D3.1)
  - EvidenceItem & ContextPayload (D3.1)
  - StructuredRAGOutput (D3.1 / D3.3)
  - TokenUsage & LLMResponse (D3.1 / D3.4)
  - MappedCitation, GroundingResult & RAGOutputRecord (D3.1)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class StrictBaseModel(BaseModel):
    """Base model forbidding unknown fields and stripping string inputs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CandidateChunk(StrictBaseModel):
    """Đại diện cho một chunk ứng viên từ pipeline retrieval/rerank."""

    query_id: str
    chunk_id: str
    chunk_text: str
    score: float
    rank: int = Field(ge=1)
    retrieval_source: str
    validity_status: str
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    as_of_date: str

    # Provenance fields
    document_id: str
    article_id: str
    clause_id: str
    parent_id: Optional[str] = None
    parent_clause_id: Optional[str] = None
    candidate_text: Optional[str] = None

    # Downstream / prompt placement fields
    evidence_index: Optional[int] = None
    vector_ref: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("query_id", "chunk_id", "chunk_text", "as_of_date")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Trường '{info.field_name}' không được để trống")
        return v.strip()

    @field_validator("evidence_index")
    @classmethod
    def validate_evidence_index(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 5):
            raise ValueError(
                f"evidence_index phải nằm trong khoảng [1, 5], nhận được: {v}"
            )
        return v


class EvidenceItem(StrictBaseModel):
    """Đại diện cho từng mảnh bằng chứng đưa vào prompt sau Parent Resolver (Top 1..5)."""

    evidence_index: int = Field(ge=1, le=5)
    chunk_id: str
    parent_clause_id: str
    document_id: str
    article_id: str
    clause_id: str
    content: str
    validity_status: str
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    source_url: Optional[str] = None

    @field_validator(
        "chunk_id",
        "parent_clause_id",
        "document_id",
        "article_id",
        "clause_id",
        "content",
    )
    @classmethod
    def validate_non_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Trường '{info.field_name}' không được để trống")
        return v.strip()


class ContextPayload(StrictBaseModel):
    """Đầu vào cho Prompt Builder & Citation Validator."""

    query_id: str
    query: str
    as_of_date: str
    as_of_date_source: Literal[
        "benchmark", "query_text", "user_input", "system_today"
    ] = "benchmark"
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    source_map: Dict[int, Dict[str, Any]] = Field(default_factory=dict)
    max_context_chars: int = 6000
    total_chars: int = 0

    @field_validator("query_id", "query", "as_of_date")
    @classmethod
    def validate_required_text(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Trường '{info.field_name}' không được để trống")
        return v.strip()

    @model_validator(mode="after")
    def populate_and_validate_context(self) -> ContextPayload:
        # Tự động tính total_chars nếu chưa được cung cấp
        calc_chars = sum(len(item.content) for item in self.evidence_items)
        if self.total_chars == 0 and calc_chars > 0:
            self.total_chars = calc_chars

        # Tự động đồng bộ source_map nếu chưa truyền
        if not self.source_map and self.evidence_items:
            built_map: Dict[int, Dict[str, Any]] = {}
            for item in self.evidence_items:
                built_map[item.evidence_index] = {
                    "chunk_id": item.chunk_id,
                    "parent_clause_id": item.parent_clause_id,
                    "document_id": item.document_id,
                    "article_id": item.article_id,
                    "clause_id": item.clause_id,
                    "validity_status": item.validity_status,
                    "effective_from": item.effective_from,
                    "effective_to": item.effective_to,
                    "source_url": item.source_url,
                }
            self.source_map = built_map
        return self


class StructuredRAGOutput(StrictBaseModel):
    """Schema ép kiểu đầu ra JSON của LLM cho Run B (Controlled RAG)."""

    answer: str
    evidence_indices: List[int] = Field(default_factory=list)
    abstained: bool = False
    abstention_reason: Optional[str] = None
    needs_clarification: bool = False

    @field_validator("evidence_indices")
    @classmethod
    def validate_evidence_indices(cls, v: List[int]) -> List[int]:
        for idx in v:
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise ValueError(
                    f"Chỉ số evidence_indices phải là số nguyên, nhận được: {type(idx).__name__}"
                )
            if idx < 1 or idx > 5:
                raise ValueError(
                    f"Chỉ số bằng chứng phải nằm trong tập [1, 2, 3, 4, 5], nhận được: {idx}"
                )
        return v


class TokenUsage(StrictBaseModel):
    """Số lượng token sử dụng (input prompt eval, output generation eval)."""

    input: int = 0
    output: int = 0


class LLMResponse(StrictBaseModel):
    """Runtime Provenance và kết quả gọi Model Gateway (Task D3.4)."""

    query_id: str
    run_mode: Literal["A_zero_shot", "B_controlled_rag", "C_production_rag"]
    answer: str
    evidence_indices: List[int] = Field(default_factory=list)
    abstained: bool = False
    needs_clarification: bool = False

    # Runtime metadata bắt buộc
    model: str = "Qwen2.5:7b"
    prompt_version: str
    num_ctx: int = 8192
    num_predict: int = 1024
    temperature: float = 0.0
    repeat_penalty: float = 1.15
    done_reason: str = "stop"
    truncated: bool = False
    parse_status: Literal["ok", "truncated_json", "invalid_json", "raw_text"] = "ok"
    latency_ms: float = 0.0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    fallback_status: str = "none"
    raw_response: Optional[str] = None


class MappedCitation(StrictBaseModel):
    """Căn cứ pháp lý đã được ánh xạ ngược từ evidence_index [1]..[5]."""

    evidence_index: int = Field(ge=1, le=5)
    chunk_id: str
    document_id: str
    article_id: str
    clause_id: str
    parent_clause_id: Optional[str] = None


class GroundingResult(StrictBaseModel):
    """Kết quả kiểm định căn cứ từ Dev 1 / Dev 5."""

    grounding_status: Literal["PASS", "FAIL", "ABSTAIN", "NEEDS_CLARIFICATION"]
    is_grounded: bool
    valid_citations: List[MappedCitation] = Field(default_factory=list)
    invalid_indices: List[int] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


class RAGOutputRecord(StrictBaseModel):
    """Bản ghi JSONL hoàn chỉnh cho benchmark và production (Phụ lục B)."""

    query_id: str
    query: str
    as_of_date: str
    as_of_date_source: Literal[
        "benchmark", "query_text", "user_input", "system_today"
    ] = "benchmark"
    answer: str
    evidence_indices: List[int] = Field(default_factory=list)
    citations: List[MappedCitation] = Field(default_factory=list)
    grounding_status: Literal["PASS", "FAIL", "ABSTAIN", "NEEDS_CLARIFICATION"]
    retrieval_trace: Dict[str, Any] = Field(default_factory=dict)
    model: str = "Qwen2.5:7b"
    prompt_version: str
    num_ctx: int = 8192
    num_predict: int = 1024
    done_reason: str
    truncated: bool
    corpus_version: str = "v1.0"
    retrieval_config_version: str = "v1.0"
    threshold_config_version: str = "v1.0"
    latency_ms: float
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    fallback_status: str = "none"


def export_json_schemas(output_dir: str | Path | None = None) -> Dict[str, Path]:
    """
    Xuất tự động 3 JSON Schemas từ các Pydantic model nguồn:
      - schemas/candidate.schema.json (từ CandidateChunk)
      - schemas/context_payload.schema.json (từ ContextPayload)
      - schemas/llm_response.schema.json (từ StructuredRAGOutput - dùng ép kiểu Ollama format)
    """
    if output_dir is None:
        target_dir = Path(__file__).resolve().parent
    else:
        target_dir = Path(output_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    mapping = {
        "candidate.schema.json": CandidateChunk.model_json_schema(),
        "context_payload.schema.json": ContextPayload.model_json_schema(),
        "llm_response.schema.json": StructuredRAGOutput.model_json_schema(),
    }

    written_paths: Dict[str, Path] = {}
    for filename, schema_dict in mapping.items():
        file_path = target_dir / filename
        file_path.write_text(
            json.dumps(schema_dict, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written_paths[filename] = file_path

    return written_paths


if __name__ == "__main__":
    exported = export_json_schemas()
    for name, p in exported.items():
        print(f"Exported: {p}")
