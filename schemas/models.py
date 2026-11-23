"""
schemas/models.py
Canonical Pydantic models & JSON Schema generation for Sprint 9 (Kế hoạch V3).
Single Source of Truth for:
  - CandidateChunk (D3.1)
  - EvidenceItem & ContextPayload (D3.1)
  - StructuredRAGOutput (D3.1 / D3.3)
  - TokenUsage & LLMResponse (D3.1 / D3.4)
  - MappedCitation, GroundingResult & RAGOutputRecord (D3.1)
  - LatencyBreakdown + abstention fields of RAGOutputRecord (P45-4, P45-6)
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SchemaVersionType = Literal["week10_v1.0", "week10_v1.1"]
SCHEMA_VERSION: SchemaVersionType = "week10_v1.1"
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"

AsOfDateSource = Literal["benchmark", "query_text", "user_input", "system_today"]
RouteType = Literal["LEGAL_IN_SCOPE", "NON_LEGAL", "LEGAL_OUT_OF_SCOPE", "MIXED_REVIEW"]
ResponseStatus = Literal["SUCCESS", "NEEDS_CLARIFICATION", "ABSTAIN", "ERROR"]
GroundingStatus = Literal["PASS", "FAIL", "NOT_RUN", "ABSTAIN", "NEEDS_CLARIFICATION"]
EventStage = Literal["api", "router", "retrieval", "rerank", "context", "llm", "citation", "gate", "response"]
ErrorCode = Literal[
    "AUTH_REQUIRED",
    "INVALID_REQUEST",
    "ROUTE_POLICY",
    "RETRIEVAL_EMPTY",
    "LOW_CONFIDENCE",
    "LLM_TIMEOUT",
    "JSON_INVALID",
    "CITATION_INVALID",
    "GROUNDING_FAIL",
    "INTERNAL_ERROR",
]
_ABSTAIN_ERROR_CODES = {"ROUTE_POLICY", "RETRIEVAL_EMPTY", "LOW_CONFIDENCE", "GROUNDING_FAIL"}
# Gate FAIL vì JSON hỏng / citation sai vẫn abstain, nhưng giữ mã lỗi cụ thể.
_GATE_FAIL_ERROR_CODES = {"JSON_INVALID", "CITATION_INVALID"}

_ROUTER_ROUTE_MAP: dict[str, RouteType] = {
    "LEGAL_HNGD": "LEGAL_IN_SCOPE",
    "LEGAL_IN_SCOPE": "LEGAL_IN_SCOPE",
    "NON_LEGAL": "NON_LEGAL",
    "LEGAL_OUT_OF_SCOPE": "LEGAL_OUT_OF_SCOPE",
    "MIXED_LEGAL_SCOPE": "MIXED_REVIEW",
    "LEGAL_SCOPE_UNCERTAIN": "MIXED_REVIEW",
    "MIXED_REVIEW": "MIXED_REVIEW",
}


def map_router_route_to_canonical(router_route: str) -> RouteType:
    """Ánh xạ nhãn Route nội bộ từ RuleRouter (Dev 4) sang RouteType chuẩn Week 10."""
    raw = str(router_route).strip()
    mapped = _ROUTER_ROUTE_MAP.get(raw)
    if mapped is None:
        raise ValueError(f"Nhãn route không hợp lệ để ánh xạ sang canonical RouteType: {router_route!r}")
    return mapped

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


def _non_empty_field(value: str, field_name: str) -> str:
    """Kiểm tra chuỗi trường bắt buộc không rỗng sau khi strip."""
    if not value or not value.strip():
        raise ValueError(f"Trường '{field_name}' không được để trống")
    return value.strip()


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


Candidate = CandidateChunk


class AskRequest(StrictBaseModel):
    """Đầu vào chuẩn cho endpoint hỏi đáp / pipeline Week 10 (D3.1).

    Khóa các tham số nội bộ phía server (không cho phép client truyền ``run_mode``,
    ``top_k`` hoặc ``metadata`` tự do). Quy ước: ``request_id`` do client cấp, còn
    ``query_id`` là ID truy vết xuyên suốt pipeline do server gán hoặc tiếp nhận.
    """
    schema_version: SchemaVersionType = SCHEMA_VERSION
    query: str = Field(..., min_length=1)
    as_of_date: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    query_id: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        return _non_empty_field(v, "query")

    @field_validator("query_id", "session_id", "request_id")
    @classmethod
    def validate_optional_id(cls, v: str | None, info) -> str | None:
        if v is None:
            return None
        return _non_empty_field(v, info.field_name)

    @field_validator("as_of_date")
    @classmethod
    def validate_optional_as_of_date(cls, v: str | None) -> str | None:
        return _check_iso_date(v, "as_of_date", required=False)


class RouteDecision(StrictBaseModel):
    """Kết quả phân luồng câu hỏi trước retrieval/generation (D3.1)."""
    schema_version: SchemaVersionType = SCHEMA_VERSION
    route: RouteType
    reason_code: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    policy_version: str = Field(..., min_length=1)
    query_id: str | None = None
    action: str | None = None
    matched_rule_id: str | None = None
    fast_path: bool = False
    as_of_date: str | None = None

    @field_validator("reason_code", "explanation", "policy_version")
    @classmethod
    def validate_required_fields(cls, v: str, info) -> str:
        return _non_empty_field(v, info.field_name)

    @field_validator("query_id", "action", "matched_rule_id")
    @classmethod
    def validate_optional_fields(cls, v: str | None, info) -> str | None:
        if v is None:
            return None
        return _non_empty_field(v, info.field_name)

    @field_validator("as_of_date")
    @classmethod
    def validate_optional_as_of_date(cls, v: str | None) -> str | None:
        return _check_iso_date(v, "as_of_date", required=False)


class MetadataFilters(StrictBaseModel):
    """Serializable exact-match filters shared by BM25 and Dense retrieval."""
    document_type: str | None = None
    document_number: str | None = None
    document_id: str | None = None
    article_id: str | None = None
    clause_id: str | None = None
    validity_status: str | None = None

    @field_validator(
        "document_type", "document_number", "document_id", "article_id", "clause_id", "validity_status",
    )
    @classmethod
    def validate_filter_values(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _non_empty_field(value, info.field_name)

class RetrievalLatencyBreakdown(StrictBaseModel):
    """Stage timings measured by retrieval; null means that a stage was not measured."""
    bm25_ms: float | None = Field(default=None, ge=0.0)
    dense_ms: float | None = Field(default=None, ge=0.0)
    rrf_ms: float | None = Field(default=None, ge=0.0)
    reranking_ms: float | None = Field(default=None, ge=0.0)
    parent_context_ms: float | None = Field(default=None, ge=0.0)
    total_retrieval_ms: float | None = Field(default=None, ge=0.0)


class RetrievalBundle(StrictBaseModel):
    """Gói kết quả truy xuất ứng viên trước khi xây ContextPayload (D3.1)."""
    schema_version: SchemaVersionType = SCHEMA_VERSION
    query_id: str = Field(..., min_length=1)
    as_of_date: str
    candidates: list[CandidateChunk] = Field(default_factory=list)
    retrieval_config_version: str = Field(..., min_length=1)
    corpus_hash: str = Field(..., min_length=1)
    precomputed: bool = False
    latency_ms: float = Field(..., ge=0.0)
    query: str | None = None
    retriever: str | None = None
    top_k: int | None = Field(default=None, ge=1)
    metadata_filters: MetadataFilters | None = None
    latency_breakdown: RetrievalLatencyBreakdown | None = None

    @field_validator("query_id", "retrieval_config_version", "corpus_hash")
    @classmethod
    def validate_required_fields(cls, v: str, info) -> str:
        return _non_empty_field(v, info.field_name)

    @field_validator("query", "retriever")
    @classmethod
    def validate_optional_text(cls, v: str | None, info) -> str | None:
        if v is None:
            return None
        return _non_empty_field(v, info.field_name)

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, v: str) -> str:
        res = _check_iso_date(v, "as_of_date", required=True)
        assert res is not None
        return res


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
    """Số lượng token sử dụng (input prompt eval, output generation eval). null = không có số liệu."""
    input: int | None = Field(default=None, ge=0)
    output: int | None = Field(default=None, ge=0)


class LLMResponse(StrictBaseModel):
    """Runtime Provenance và kết quả gọi Model Gateway (Task D3.4)."""
    query_id: str
    run_mode: Literal["A_zero_shot", "B_controlled_rag", "C_production_rag"]
    answer: str
    evidence_indices: list[int] = Field(default_factory=list)
    # Giá trị không phải số nguyên mà model trả trong evidence_indices (JSON-encoded); Gate coi là FAIL
    rejected_evidence_values: list[str] = Field(default_factory=list)
    abstained: bool = False
    abstention_reason: str | None = None
    needs_clarification: bool = False

    # Runtime metadata bắt buộc
    model: str = "qwen2.5:7b"
    prompt_version: str
    num_ctx: int = 8192
    num_predict: int = 1024
    temperature: float = 0.0
    repeat_penalty: float = 1.0
    done_reason: str
    truncated: bool = False
    context_truncated: bool = False
    parse_status: Literal["ok", "truncated_json", "invalid_json", "raw_text"] = "ok"
    latency_ms: float = 0.0
    # Thời gian Ollama trả về (nano giây -> ms), có cả khi stream=false (P45-3). null = Ollama
    # không trả trường đó, không đặt 0. ttft_model_ms = load + prompt_eval: từ lúc gửi đến token
    # đầu tiên của model (xấp xỉ vì gateway gọi không stream). load_duration_ms lớn = khởi động nguội.
    load_duration_ms: float | None = Field(default=None, ge=0)
    prompt_eval_duration_ms: float | None = Field(default=None, ge=0)
    eval_duration_ms: float | None = Field(default=None, ge=0)
    total_duration_ms: float | None = Field(default=None, ge=0)
    ttft_model_ms: float | None = Field(default=None, ge=0)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    fallback_status: str = "none"
    raw_response: str | None = None
    raw_response_reference: str | None = None
    error_code: ErrorCode | None = None
    ollama_version: str | None = None
    model_digest: str | None = None
    schema_version: SchemaVersionType = SCHEMA_VERSION


class MappedCitation(StrictBaseModel):
    """Căn cứ pháp lý đã được ánh xạ ngược từ evidence_index [1]..[5]."""
    evidence_index: int = Field(ge=1, le=5)
    chunk_id: str
    document_id: str
    article_id: str
    clause_id: str
    parent_clause_id: str | None = None


class GroundingResult(StrictBaseModel):
    """Kết quả kiểm định căn cứ từ Dev 1 / Dev 5 (D3.1 + tương thích Sprint 9)."""
    schema_version: SchemaVersionType = SCHEMA_VERSION
    status: GroundingStatus
    grounding_status: GroundingStatus | None = Field(default=None, json_schema_extra={"deprecated": True})
    is_grounded: bool = False
    validated_answer: str | None = None
    citations: list[MappedCitation] = Field(default_factory=list)
    valid_citations: list[MappedCitation] = Field(default_factory=list, json_schema_extra={"deprecated": True})
    violation_codes: list[str] = Field(default_factory=list)
    invalid_indices: list[int] = Field(default_factory=list, json_schema_extra={"deprecated": True})
    unsupported_claims: list[str] = Field(default_factory=list, json_schema_extra={"deprecated": True})
    retryable: bool = False
    abstention_reason: str | None = None
    reason: str | None = Field(default=None, json_schema_extra={"deprecated": True})

    @model_validator(mode="before")
    @classmethod
    def sync_canonical_and_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        merged = dict(data)
        has_status = "status" in merged and merged["status"] is not None
        has_gs = "grounding_status" in merged and merged["grounding_status"] is not None
        if not has_status and not has_gs:
            raise ValueError("GroundingResult bắt buộc phải có 'status' hoặc 'grounding_status'")
        if has_status and has_gs and merged["status"] != merged["grounding_status"]:
            raise ValueError("Trường 'status' và 'grounding_status' không được mâu thuẫn")
        resolved_status = merged["status"] if has_status else merged["grounding_status"]
        merged["status"] = resolved_status
        merged["grounding_status"] = resolved_status

        if "is_grounded" not in merged:
            merged["is_grounded"] = resolved_status == "PASS"

        if "citations" in merged and "valid_citations" not in merged:
            merged["valid_citations"] = merged["citations"]
        elif "valid_citations" in merged and "citations" not in merged:
            merged["citations"] = merged["valid_citations"]

        if resolved_status == "ABSTAIN":
            if "abstention_reason" in merged and "reason" not in merged:
                merged["reason"] = merged["abstention_reason"]
            elif "reason" in merged and "abstention_reason" not in merged:
                merged["abstention_reason"] = merged["reason"]

        if resolved_status == "FAIL" and merged.get("reason") and "violation_codes" not in merged:
            merged["violation_codes"] = [str(merged["reason"])]

        return merged

    @model_validator(mode="after")
    def validate_grounding_invariants(self) -> "GroundingResult":
        if self.is_grounded != (self.status == "PASS"):
            raise ValueError("Trường 'is_grounded' chỉ được là True khi status == 'PASS'")
        if self.status != "ABSTAIN" and self.abstention_reason is not None:
            raise ValueError("Trường 'abstention_reason' chỉ được đặt khi status == 'ABSTAIN'")
        return self


AbstentionSource = Literal["confidence_filter", "model", "grounding_gate", "router"]
# Nguồn không gọi LLM (llm_calls = 0) và nguồn chỉ có sau khi gọi LLM (llm_calls >= 1)
_PRE_LLM_SOURCES = {"confidence_filter", "router"}


class LatencyBreakdown(StrictBaseModel):
    """Thời gian từng bước (ms). null = không đo được (không đặt 0), ví dụ retrieval_ms khi
    dùng artifact precomputed, hoặc các trường thời gian Ollama khi không gọi LLM."""
    retrieval_ms: float | None = Field(default=None, ge=0)
    llm_total_ms: float | None = Field(default=None, ge=0)
    ttft_model_ms: float | None = Field(default=None, ge=0)
    load_ms: float | None = Field(default=None, ge=0)
    prompt_eval_ms: float | None = Field(default=None, ge=0)
    eval_ms: float | None = Field(default=None, ge=0)


class RAGOutputRecord(StrictBaseModel):
    """Bản ghi JSONL hoàn chỉnh cho benchmark và production (Phụ lục B).

    ``abstained``/``abstention_reason``/``abstention_source``/``needs_clarification`` có ở mọi
    record (P45-4), kể cả khi không gọi LLM; ``abstention_reason`` là mã cố định để evaluator
    đếm. Gate FAIL tính là từ chối (người dùng chỉ nhận thông báo không kết luận), phân biệt
    với model tự từ chối qua ``abstention_source``.
    """
    query_id: str
    query: str
    as_of_date: str
    as_of_date_source: Literal["benchmark", "query_text", "user_input", "system_today"]
    route: RouteType | None = None
    answer: str
    evidence_indices: list[int] = Field(default_factory=list)
    citations: list[MappedCitation] = Field(default_factory=list)
    grounding_status: Literal["PASS", "FAIL", "ABSTAIN", "NEEDS_CLARIFICATION"]
    abstained: bool
    abstention_reason: str | None
    abstention_source: AbstentionSource | None
    needs_clarification: bool
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
    llm_calls: int = Field(ge=0)
    latency_breakdown: LatencyBreakdown = Field(default_factory=LatencyBreakdown)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    fallback_status: str = "none"

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, v: str) -> str:
        res = _check_iso_date(v, "as_of_date", required=True)
        assert res is not None
        return res

    @model_validator(mode="after")
    def check_abstention_fields(self) -> "RAGOutputRecord":
        """Các trường từ chối phải khớp grounding_status và số lần gọi model."""
        status, source = self.grounding_status, self.abstention_source
        if status in ("PASS", "NEEDS_CLARIFICATION"):
            if self.abstained or self.abstention_reason is not None:
                raise ValueError(f"{status}: abstained phải false và abstention_reason null")
            if self.needs_clarification != (status == "NEEDS_CLARIFICATION"):
                raise ValueError(f"{status}: needs_clarification không khớp grounding_status")
            if status == "PASS" and source is not None:
                raise ValueError("PASS: abstention_source phải null")
            if status == "NEEDS_CLARIFICATION" and source not in ("model", "router"):
                raise ValueError("NEEDS_CLARIFICATION: abstention_source phải là model hoặc router")
        else:
            if not self.abstained or not self.abstention_reason or self.needs_clarification:
                raise ValueError(f"{status}: cần abstained=true, abstention_reason (mã) và "
                                 "needs_clarification=false")
            allowed = {"grounding_gate"} if status == "FAIL" else {"confidence_filter", "model", "router"}
            if source not in allowed:
                raise ValueError(f"{status}: abstention_source {source!r} không hợp lệ, cần một trong "
                                 f"{sorted(allowed)}")
        if source in _PRE_LLM_SOURCES and self.llm_calls != 0:
            raise ValueError(f"abstention_source={source}: dừng trước LLM nên llm_calls phải bằng 0")
        if source not in _PRE_LLM_SOURCES and self.llm_calls < 1:
            raise ValueError(f"{status} (abstention_source={source}) chỉ có sau khi gọi model: llm_calls >= 1")
        return self


class AskTimings(LatencyBreakdown):
    """Thời gian từng bước và tổng thời gian cho API AskResponse (D3.1)."""
    total_ms: float | None = Field(default=None, ge=0)


class ErrorDetail(StrictBaseModel):
    """Chi tiết lỗi an toàn trả về API (chặn extra fields để không lộ traceback/prompt)."""
    message: str = Field(..., min_length=1)
    retryable: bool = False

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        return _non_empty_field(v, "message")


class AskResponse(StrictBaseModel):
    """Đầu ra API chuẩn hóa tách bạch rạch ròi SUCCESS / ABSTAIN / NEEDS_CLARIFICATION / ERROR."""
    schema_version: SchemaVersionType = SCHEMA_VERSION
    query_id: str = Field(..., min_length=1)
    request_id: str | None = None
    as_of_date: str
    as_of_date_source: AsOfDateSource
    status: ResponseStatus
    route: RouteType
    answer: str | None = None
    clarification: str | None = None
    abstention_message: str | None = None
    abstention_reason: str | None = None
    citations: list[MappedCitation] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    grounding_status: GroundingStatus
    disclaimer: str = Field(..., min_length=1)
    timings: AskTimings = Field(default_factory=AskTimings)
    error_code: ErrorCode | None = None
    error: ErrorDetail | None = None

    @field_validator("query_id", "disclaimer")
    @classmethod
    def validate_required_fields(cls, v: str, info) -> str:
        return _non_empty_field(v, info.field_name)

    @field_validator("request_id")
    @classmethod
    def validate_optional_request_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _non_empty_field(v, "request_id")

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, v: str) -> str:
        res = _check_iso_date(v, "as_of_date", required=True)
        assert res is not None
        return res

    @model_validator(mode="after")
    def validate_status_separation(self) -> "AskResponse":
        """Ngăn trộn lẫn SUCCESS / ABSTAIN / NEEDS_CLARIFICATION / ERROR, chặn rò answer và ràng buộc route-citation."""
        if self.status == "SUCCESS":
            if not self.answer or not self.answer.strip():
                raise ValueError("status='SUCCESS' bắt buộc phải có câu trả lời (answer) không rỗng")
            if self.route == "LEGAL_OUT_OF_SCOPE":
                raise ValueError("status='SUCCESS' không hợp lệ với route='LEGAL_OUT_OF_SCOPE'")
            if self.route == "NON_LEGAL":
                if self.grounding_status != "NOT_RUN":
                    raise ValueError("status='SUCCESS' với route='NON_LEGAL' bắt buộc phải có grounding_status='NOT_RUN'")
                if self.evidence or self.citations:
                    raise ValueError("status='SUCCESS' với route='NON_LEGAL' phải có evidence=[] và citations=[]")
            else:
                if self.grounding_status != "PASS":
                    raise ValueError("status='SUCCESS' cho luồng legal bắt buộc phải có grounding_status='PASS'")
                if not self.citations:
                    raise ValueError("status='SUCCESS' cho luồng legal bắt buộc phải có ít nhất một citation")
                available_indices = {item.evidence_index for item in self.evidence}
                missing_indices = sorted({c.evidence_index for c in self.citations} - available_indices)
                if missing_indices:
                    raise ValueError(
                        f"citations chứa evidence_index {missing_indices} không tồn tại trong evidence"
                    )
            if (
                self.clarification is not None
                or self.abstention_message is not None
                or self.abstention_reason is not None
                or self.error_code is not None
                or self.error is not None
            ):
                raise ValueError(
                    "status='SUCCESS' không được đặt clarification, abstention_message, abstention_reason, error_code hoặc error"
                )
        elif self.status == "ABSTAIN":
            if self.answer is not None:
                raise ValueError("status='ABSTAIN' bắt buộc phải có answer=None")
            if self.grounding_status not in ("ABSTAIN", "FAIL", "NOT_RUN"):
                raise ValueError("status='ABSTAIN' chỉ nhận grounding_status trong ('ABSTAIN', 'FAIL', 'NOT_RUN')")
            if not (
                (self.abstention_message and self.abstention_message.strip())
                or (self.abstention_reason and self.abstention_reason.strip())
            ):
                raise ValueError("status='ABSTAIN' bắt buộc phải có abstention_message hoặc abstention_reason")
            if self.clarification is not None or self.error is not None:
                raise ValueError("status='ABSTAIN' không được đặt clarification hoặc error")
            if self.error_code in _GATE_FAIL_ERROR_CODES:
                if self.grounding_status != "FAIL":
                    raise ValueError(
                        f"status='ABSTAIN' với error_code='{self.error_code}' bắt buộc grounding_status='FAIL'"
                    )
            elif self.error_code is not None and self.error_code not in _ABSTAIN_ERROR_CODES:
                raise ValueError(
                    f"status='ABSTAIN' chỉ nhận error_code thuộc {sorted(_ABSTAIN_ERROR_CODES)}, "
                    f"{sorted(_GATE_FAIL_ERROR_CODES)} (khi grounding_status='FAIL') hoặc None"
                )
        elif self.status == "NEEDS_CLARIFICATION":
            if self.answer is not None:
                raise ValueError("status='NEEDS_CLARIFICATION' bắt buộc phải có answer=None")
            if not self.clarification or not self.clarification.strip():
                raise ValueError("status='NEEDS_CLARIFICATION' bắt buộc phải có clarification không rỗng")
            if self.grounding_status not in ("NEEDS_CLARIFICATION", "NOT_RUN"):
                raise ValueError(
                    "status='NEEDS_CLARIFICATION' chỉ nhận grounding_status='NEEDS_CLARIFICATION' hoặc 'NOT_RUN'"
                )
            if (
                self.abstention_message is not None
                or self.abstention_reason is not None
                or self.error_code is not None
                or self.error is not None
            ):
                raise ValueError(
                    "status='NEEDS_CLARIFICATION' không được đặt abstention_message, abstention_reason, error_code hoặc error"
                )
        elif self.status == "ERROR":
            if self.answer is not None:
                raise ValueError("status='ERROR' bắt buộc phải có answer=None")
            if self.error_code is None:
                raise ValueError("status='ERROR' bắt buộc phải có error_code")
            if self.grounding_status == "PASS":
                raise ValueError("status='ERROR' không thể có grounding_status='PASS'")
            if (
                self.clarification is not None
                or self.abstention_message is not None
                or self.abstention_reason is not None
            ):
                raise ValueError(
                    "status='ERROR' không được đặt clarification, abstention_message hoặc abstention_reason"
                )
        return self


class LogEvent(StrictBaseModel):
    """Sự kiện log có cấu trúc qua 9 chặng của pipeline RAG (D3.1)."""
    schema_version: SchemaVersionType = SCHEMA_VERSION
    event_id: str = Field(..., min_length=1)
    query_id: str = Field(..., min_length=1)
    stage: EventStage
    event_type: str = Field(..., min_length=1)
    timestamp: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    duration_ms: float | None = Field(default=None, ge=0.0)
    error_code: ErrorCode | None = None
    masked_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "query_id", "event_type", "status")
    @classmethod
    def validate_required_fields(cls, v: str, info) -> str:
        return _non_empty_field(v, info.field_name)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        text = _non_empty_field(v, "timestamp")
        try:
            datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Trường 'timestamp' phải chuẩn ISO-8601, nhận được: '{text}'") from exc
        return text


CANONICAL_SCHEMA_MODELS: dict[str, type[StrictBaseModel]] = {
    "ask_request.schema.json": AskRequest,
    "ask_response.schema.json": AskResponse,
    "route_decision.schema.json": RouteDecision,
    "candidate.schema.json": CandidateChunk,
    "retrieval_bundle.schema.json": RetrievalBundle,
    "evidence_item.schema.json": EvidenceItem,
    "context_payload.schema.json": ContextPayload,
    "llm_response.schema.json": LLMResponse,
    "grounding_result.schema.json": GroundingResult,
    "log_event.schema.json": LogEvent,
}


def export_json_schemas(output_dir: str | Path | None = None) -> dict[str, Path]:
    """
    Xuất tự động 4 JSON Schemas ở thư mục gốc (3 tệp legacy Sprint 9 và tệp tường minh
    ``structured_rag_output.schema.json``) cùng 10 JSON Schemas chuẩn hóa trong ``generated/``
    với ``$schema`` (Draft 2020-12) và ``schema_version``.
    """
    if output_dir is None:
        target_dir = Path(__file__).resolve().parent
    else:
        target_dir = Path(output_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    generated_dir = target_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    root_mapping = {
        "candidate.schema.json": CandidateChunk.model_json_schema(),
        "context_payload.schema.json": ContextPayload.model_json_schema(),
        "llm_response.schema.json": StructuredRAGOutput.model_json_schema(),
        "structured_rag_output.schema.json": StructuredRAGOutput.model_json_schema(),
    }

    written_paths: dict[str, Path] = {}
    for filename, schema_dict in root_mapping.items():
        file_path = target_dir / filename
        file_path.write_text(json.dumps(schema_dict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written_paths[filename] = file_path

    for filename, model_cls in CANONICAL_SCHEMA_MODELS.items():
        schema_dict = {
            "$schema": JSON_SCHEMA_DRAFT,
            "schema_version": SCHEMA_VERSION,
            **model_cls.model_json_schema(),
        }
        file_path = generated_dir / filename
        file_path.write_text(json.dumps(schema_dict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written_paths[f"generated/{filename}"] = file_path

    return written_paths


if __name__ == "__main__":
    exported = export_json_schemas()
    for name, p in exported.items():
        print(f"Exported: {p}")
