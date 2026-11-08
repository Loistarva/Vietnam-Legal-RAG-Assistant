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
import re
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_iso_date(value: str | None, field_name: str, required: bool = True) -> str | None:
    """Kiểm tra định dạng ngày chuẩn ISO (YYYY-MM-DD)."""
    if value is None:
        if required:
            raise ValueError(f"Trường '{field_name}' bắt buộc phải có ngày định dạng YYYY-MM-DD")
        return None
    val_str = str(value).strip()
    if not val_str:
        if required:
            raise ValueError(f"Trường '{field_name}' không được để trống")
        return None
    if not ISO_DATE_REGEX.match(val_str):
        raise ValueError(f"Trường '{field_name}' phải theo định dạng ngày ISO (YYYY-MM-DD), nhận được: '{val_str}'")
    try:
        date.fromisoformat(val_str)
    except ValueError as exc:
        raise ValueError(f"Trường '{field_name}' không phải ngày hợp lệ: '{val_str}'") from exc
    return val_str


def _required_text(value: Any, field_name: str) -> str:
    """Lấy chuỗi bắt buộc từ dữ liệu nguồn; thiếu thì báo lỗi thay vì tự điền."""
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"Thiếu trường bắt buộc '{field_name}' trong item retrieval")
    return text


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
    retrieval_sources: list[str] = Field(default_factory=list)
    validity_status: str
    effective_from: str | None = None
    effective_to: str | None = None
    as_of_date: str

    # Provenance fields
    document_id: str
    article_id: str
    clause_id: str
    parent_id: str | None = None
    parent_clause_id: str | None = None
    candidate_text: str | None = None
    parent_text: str | None = None

    # Fusion & rerank metrics matching RetrievalResultItem
    rrf_score: float | None = None
    reranker_score: float | None = None
    source_ranks: dict[str, int] = Field(default_factory=dict)
    source_scores: dict[str, float] = Field(default_factory=dict)

    # Downstream / prompt placement fields
    evidence_index: int | None = None
    vector_ref: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "query_id", "chunk_id", "chunk_text", "retrieval_source", "validity_status",
        "document_id", "article_id", "clause_id",
    )
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Trường '{info.field_name}' không được để trống")
        return v.strip()

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, v: str) -> str:
        res = _check_iso_date(v, "as_of_date", required=True)
        assert res is not None
        return res

    @field_validator("effective_from", "effective_to")
    @classmethod
    def validate_effective_dates(cls, v: str | None, info) -> str | None:
        return _check_iso_date(v, info.field_name, required=False)

    @field_validator("evidence_index")
    @classmethod
    def validate_evidence_index(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            raise ValueError(f"evidence_index phải nằm trong khoảng [1, 5], nhận được: {v}")
        return v

    @classmethod
    def from_retrieval_item(
        cls,
        item: dict[str, Any],
        query_id: str,
        as_of_date: str,
        retriever: str | None = None,
    ) -> CandidateChunk:
        """Chuyển một RetrievalResultItem (schemas/retrieval_schema.json) sang CandidateChunk.

        ``retriever`` là trường ``retriever`` của RetrievalEnvelope (bm25, dense, hybrid,
        hybrid_reranker); file BM25/Dense không có ``retrieval_sources`` theo từng item.
        Thiếu hiệu lực, ID, rank hoặc score thì báo lỗi, không tự điền giá trị.
        """
        meta = item.get("metadata") or {}
        validity_status = _required_text(
            item.get("validity_status") or meta.get("validity_status"), "validity_status"
        )
        effective_from = item.get("effective_from") or meta.get("effective_from")
        effective_to = item.get("effective_to") or meta.get("effective_to")

        # Chuẩn hóa retrieval_sources
        raw_sources = item.get("retrieval_sources")
        if isinstance(raw_sources, list):
            retrieval_sources = [str(s).strip() for s in raw_sources if str(s).strip()]
        elif isinstance(raw_sources, str):
            retrieval_sources = [s.strip() for s in raw_sources.split(",") if s.strip()]
        else:
            retrieval_sources = []

        # Nguồn của candidate: trường của item > retriever của envelope > nguồn duy nhất.
        # Hit hybrid do nhiều nhánh cùng tìm thấy không được gắn nhãn theo nhánh đầu tiên.
        retrieval_source = item.get("retrieval_source") or retriever
        if not retrieval_source:
            if len(retrieval_sources) == 1:
                retrieval_source = retrieval_sources[0]
            elif len(retrieval_sources) > 1:
                retrieval_source = "hybrid"
            else:
                raise ValueError("Thiếu retrieval_source: item không có retrieval_sources và không truyền retriever")

        score_val = item.get("score")
        if score_val is None:
            score_val = item.get("reranker_score")
        if score_val is None:
            score_val = item.get("rrf_score")
        if score_val is None:
            raise ValueError("Thiếu trường bắt buộc 'score' trong item retrieval")
        if item.get("rank") is None:
            raise ValueError("Thiếu trường bắt buộc 'rank' trong item retrieval")
        score = float(score_val)
        rank = int(item["rank"])

        document_id = _required_text(item.get("document_id") or meta.get("document_id"), "document_id")
        article_id = _required_text(item.get("article_id") or meta.get("article_id"), "article_id")
        clause_id = _required_text(item.get("clause_id") or meta.get("clause_id"), "clause_id")
        parent_clause_id = item.get("parent_clause_id") or meta.get("parent_clause_id")
        chunk_text = _required_text(item.get("chunk_text"), "chunk_text")

        return cls(
            query_id=query_id,
            chunk_id=_required_text(item.get("chunk_id"), "chunk_id"),
            chunk_text=chunk_text,
            score=score,
            rank=rank,
            retrieval_source=retrieval_source,
            retrieval_sources=retrieval_sources,
            validity_status=str(validity_status),
            effective_from=effective_from,
            effective_to=effective_to,
            as_of_date=as_of_date,
            document_id=document_id,
            article_id=article_id,
            clause_id=clause_id,
            parent_id=item.get("parent_id"),
            parent_clause_id=parent_clause_id,
            candidate_text=item.get("candidate_text"),
            parent_text=item.get("parent_text"),
            rrf_score=item.get("rrf_score"),
            reranker_score=item.get("reranker_score"),
            source_ranks=item.get("source_ranks") or {},
            source_scores=item.get("source_scores") or {},
            evidence_index=item.get("evidence_index"),
            vector_ref=item.get("vector_ref"),
            metadata=meta,
        )


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
    effective_from: str | None = None
    effective_to: str | None = None
    source_url: str | None = None

    # Nhãn đọc được bổ sung
    document_number: str | None = None
    document_title: str | None = None
    article_number: str | None = None
    clause_number: str | None = None
    breadcrumb: str | None = None
    provision_status: str | None = None

    @field_validator("chunk_id", "parent_clause_id", "document_id", "article_id", "clause_id", "content")
    @classmethod
    def validate_non_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Trường '{info.field_name}' không được để trống")
        return v.strip()

    @field_validator("effective_from", "effective_to")
    @classmethod
    def validate_effective_dates(cls, v: str | None, info) -> str | None:
        return _check_iso_date(v, info.field_name, required=False)


class ContextPayload(StrictBaseModel):
    """Đầu vào cho Prompt Builder & Citation Validator."""
    query_id: str
    query: str
    as_of_date: str
    as_of_date_source: Literal["benchmark", "query_text", "user_input", "system_today"]
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    source_map: dict[int, dict[str, Any]] = Field(default_factory=dict)
    max_context_chars: int = 6000
    total_chars: int = 0

    @field_validator("query_id", "query")
    @classmethod
    def validate_required_text(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Trường '{info.field_name}' không được để trống")
        return v.strip()

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, v: str) -> str:
        res = _check_iso_date(v, "as_of_date", required=True)
        assert res is not None
        return res

    @model_validator(mode="after")
    def populate_and_validate_context(self) -> ContextPayload:
        if not self.evidence_items:
            raise ValueError("Danh sách evidence_items không được để rỗng")
        n = len(self.evidence_items)
        if n > 5:
            raise ValueError(f"Số lượng evidence_items tối đa là 5, nhận được: {n}")

        # Kiểm tra chỉ số duy nhất và liên tục bắt đầu từ 1 đến n
        indices = [item.evidence_index for item in self.evidence_items]
        expected_indices = list(range(1, n + 1))
        if indices != expected_indices:
            raise ValueError(
                f"Các chỉ số evidence_index phải duy nhất và liên tục bắt đầu từ 1 đến {n}, "
                f"nhận được: {indices}"
            )

        # total_chars luôn tính từ nội dung thật; giá trị truyền vào phải khớp
        calc_chars = sum(len(item.content) for item in self.evidence_items)
        if self.total_chars not in (0, calc_chars):
            raise ValueError(
                f"total_chars ({self.total_chars}) không khớp tổng ký tự thật của evidence ({calc_chars})"
            )
        self.total_chars = calc_chars
        if self.total_chars > self.max_context_chars:
            raise ValueError(
                f"Tổng ký tự ngữ cảnh ({self.total_chars}) vượt quá giới hạn max_context_chars ({self.max_context_chars})"
            )

        # Tự động sinh hoặc kiểm tra source_map khớp 1-1 với evidence_items
        built_map: dict[int, dict[str, Any]] = {}
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
                "document_number": item.document_number,
                "document_title": item.document_title,
                "article_number": item.article_number,
                "clause_number": item.clause_number,
                "breadcrumb": item.breadcrumb,
                "provision_status": item.provision_status,
            }

        # source_map luôn dựng từ evidence_items; nếu truyền vào thì phải giống hệt
        if self.source_map and self.source_map != built_map:
            raise ValueError("source_map không khớp evidence_items; hãy bỏ trống để tự dựng")
        self.source_map = built_map

        return self


class StructuredRAGOutput(StrictBaseModel):
    """Schema ép kiểu đầu ra JSON của LLM cho Run B (Controlled RAG).

    minimum/maximum của evidence_indices đi vào JSON Schema gửi Ollama (``format``) để
    grammar chặn index ngoài [1, 5]; index > số evidence thật do mapper/validator chặn.
    """
    answer: str
    evidence_indices: list[Annotated[int, Field(ge=1, le=5)]] = Field(default_factory=list)
    abstained: bool = False
    abstention_reason: str | None = None
    needs_clarification: bool = False

    @field_validator("evidence_indices", mode="before")
    @classmethod
    def validate_evidence_indices(cls, v: Any) -> Any:
        if isinstance(v, list):
            for idx in v:
                if isinstance(idx, bool):
                    raise ValueError("Chỉ số evidence_indices không được là boolean")
                if not isinstance(idx, int):
                    raise ValueError(f"Chỉ số evidence_indices phải là số nguyên, nhận được: {type(idx).__name__}")
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
    evidence_indices: list[int] = Field(default_factory=list)
    abstained: bool = False
    needs_clarification: bool = False

    # Runtime metadata bắt buộc
    model: str = "qwen2.5:7b"
    prompt_version: str
    num_ctx: int = 8192
    num_predict: int = 1024
    temperature: float = 0.0
    repeat_penalty: float = 1.15
    done_reason: str
    truncated: bool = False
    context_truncated: bool = False
    parse_status: Literal["ok", "truncated_json", "invalid_json", "raw_text"] = "ok"
    latency_ms: float = 0.0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    fallback_status: str = "none"
    raw_response: str | None = None
    ollama_version: str | None = None
    model_digest: str | None = None


class MappedCitation(StrictBaseModel):
    """Căn cứ pháp lý đã được ánh xạ ngược từ evidence_index [1]..[5]."""
    evidence_index: int = Field(ge=1, le=5)
    chunk_id: str
    document_id: str
    article_id: str
    clause_id: str
    parent_clause_id: str | None = None


class GroundingResult(StrictBaseModel):
    """Kết quả kiểm định căn cứ từ Dev 1 / Dev 5."""
    grounding_status: Literal["PASS", "FAIL", "ABSTAIN", "NEEDS_CLARIFICATION"]
    is_grounded: bool
    valid_citations: list[MappedCitation] = Field(default_factory=list)
    invalid_indices: list[int] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    reason: str | None = None


class RAGOutputRecord(StrictBaseModel):
    """Bản ghi JSONL hoàn chỉnh cho benchmark và production (Phụ lục B)."""
    query_id: str
    query: str
    as_of_date: str
    as_of_date_source: Literal["benchmark", "query_text", "user_input", "system_today"]
    answer: str
    evidence_indices: list[int] = Field(default_factory=list)
    citations: list[MappedCitation] = Field(default_factory=list)
    grounding_status: Literal["PASS", "FAIL", "ABSTAIN", "NEEDS_CLARIFICATION"]
    retrieval_trace: dict[str, Any] = Field(default_factory=dict)
    model: str = "qwen2.5:7b"
    prompt_version: str
    num_ctx: int = 8192
    num_predict: int = 1024
    done_reason: str
    truncated: bool
    corpus_version: str
    retrieval_config_version: str
    threshold_config_version: str
    latency_ms: float
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    fallback_status: str = "none"

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, v: str) -> str:
        res = _check_iso_date(v, "as_of_date", required=True)
        assert res is not None
        return res


def export_json_schemas(output_dir: str | Path | None = None) -> dict[str, Path]:
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

    written_paths: dict[str, Path] = {}
    for filename, schema_dict in mapping.items():
        file_path = target_dir / filename
        file_path.write_text(json.dumps(schema_dict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written_paths[filename] = file_path

    return written_paths


if __name__ == "__main__":
    exported = export_json_schemas()
    for name, p in exported.items():
        print(f"Exported: {p}")
