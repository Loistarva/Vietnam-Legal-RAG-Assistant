"""Package Dev4 retrieval results using the active canonical D3 contract."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, get_args

from retrieval.temporal import normalize_as_of_date
from retrieval.metadata_filters import normalize_metadata_filters
from schemas.models import (
    AsOfDateSource,
    CandidateChunk,
    MetadataFilters,
    RetrievalBundle,
    RetrievalLatencyBreakdown,
)


class RetrievalAdapter:
    """Expose the existing pipeline through the active ``RetrievalBundle``."""

    def __init__(self, pipeline: Any, *, corpus_hash: str,
                 retrieval_config_version: str):
        if not callable(getattr(pipeline, "run", None)):
            raise TypeError("pipeline phải cung cấp run(query=..., as_of_date=...)")
        if not isinstance(corpus_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", corpus_hash.strip()):
            raise ValueError("corpus_hash phải là SHA-256 64 ký tự hex thường đã xác minh")
        if not isinstance(retrieval_config_version, str) or not retrieval_config_version.strip():
            raise ValueError("retrieval_config_version phải được cung cấp rõ ràng")
        self.pipeline = pipeline
        self.corpus_hash = corpus_hash.strip()
        self.retrieval_config_version = retrieval_config_version.strip()

    @classmethod
    def from_corpus_artifact(cls, pipeline: Any, *, corpus_path: str | Path,
                             retrieval_config_version: str) -> "RetrievalAdapter":
        """Build provenance from the exact corpus using the project's CRLF-safe SHA helper."""
        from embedding.vector_store import chunk_file_sha256

        path = Path(corpus_path)
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy corpus để tính SHA-256: {path}")
        return cls(
            pipeline,
            corpus_hash=chunk_file_sha256(path),
            retrieval_config_version=retrieval_config_version,
        )

    @staticmethod
    def _query_id(query: str, as_of_date: str) -> str:
        digest = hashlib.sha256(f"{as_of_date}\n{query}".encode("utf-8")).hexdigest()[:16]
        return f"retrieval-{digest}"

    def retrieve(self, query: str, as_of_date: str,
                 options: dict[str, Any] | None = None, *,
                 filters: dict[str, Any] | MetadataFilters | None = None) -> RetrievalBundle:
        """Run retrieval and validate its candidates against the active D3 schema.

        ``ContextPayload`` is created by Dev5's Context Builder. The merged
        ``filters`` are exact-match metadata filters shared by BM25 and Dense.
        Stage timings are included when supplied by the pipeline.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        if as_of_date is None or not str(as_of_date).strip():
            raise ValueError("as_of_date bắt buộc; không tự thay bằng ngày hiện tại")
        normalized_date = normalize_as_of_date(as_of_date)
        controls = dict(options or {})
        unsupported = set(controls) - {"query_id", "top_k"}
        if unsupported:
            raise ValueError(f"options không được hỗ trợ bởi canonical contract: {sorted(unsupported)}")
        query_id = controls.get("query_id") or self._query_id(query.strip(), normalized_date)
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError("query_id phải là chuỗi không rỗng")
        top_k = controls.get("top_k")
        if top_k is not None and (not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1):
            raise ValueError("top_k phải là số nguyên dương")

        normalized_filters = normalize_metadata_filters(filters)
        result = self.pipeline.run(
            query=query.strip(), query_id=query_id.strip(), as_of_date=normalized_date, top_k=top_k,
            metadata_filters=normalized_filters or None,
        )
        rows = result.get("results")
        if not isinstance(rows, list):
            raise TypeError("retrieval pipeline phải trả results dạng list")
        candidates = [
            CandidateChunk.from_retrieval_item(
                row, query_id=query_id.strip(), as_of_date=normalized_date,
                retriever=result.get("retriever", "hybrid_reranker"),
            )
            for row in rows
        ]
        stats = result.get("stats") or {}
        latency_ms = stats.get("total_latency_ms")
        if latency_ms is None:
            latency_ms = result.get("latency_ms")
        if latency_ms is None:
            # The canonical bundle requires a measured total. Stage timings may
            # remain null, but an unknown total must never masquerade as zero.
            raise ValueError("Thiếu latency_ms đã đo; RetrievalBundle yêu cầu tổng thời gian, không tự gán 0")
        raw_breakdown = stats.get("latency_breakdown")
        latency_breakdown = (
            RetrievalLatencyBreakdown.model_validate(raw_breakdown) if raw_breakdown is not None else None
        )
        return RetrievalBundle(
            query_id=query_id.strip(),
            as_of_date=normalized_date,
            candidates=candidates,
            retrieval_config_version=self.retrieval_config_version,
            corpus_hash=self.corpus_hash,
            precomputed=bool(result.get("precomputed", False) or
                             ((result.get("config") or {}).get("retriever") or {}).get("backend") == "precomputed"),
            latency_ms=latency_ms,
            query=query.strip(),
            retriever=result.get("retriever"),
            top_k=top_k or result.get("top_k"),
            metadata_filters=MetadataFilters(**normalized_filters) if normalized_filters else None,
            latency_breakdown=latency_breakdown,
        )

    def retrieve_with_trace(
        self, query: str, as_of_date: str, options: dict[str, Any] | None = None, *,
        corpus_version: str, as_of_date_source: AsOfDateSource,
        filters: dict[str, Any] | MetadataFilters | None = None,
    ) -> tuple[RetrievalBundle, dict[str, Any]]:
        """Return the canonical bundle and a request-local handoff trace.

        The trace is a Dev4 sidecar, not an extension of the canonical schema.
        It contains identifiers and measured timings, never query/chunk text.
        Empty retrieval is not classified as low confidence: that is Dev5's gate.
        """
        if not isinstance(corpus_version, str) or not corpus_version.strip():
            raise ValueError("corpus_version phải được cung cấp rõ ràng cho trace")
        if as_of_date_source not in get_args(AsOfDateSource):
            raise ValueError("as_of_date_source không thuộc canonical contract")
        bundle = self.retrieve(query, as_of_date, options, filters=filters)
        candidate_fields = {
            "chunk_id", "document_id", "article_id", "clause_id", "parent_id",
            "parent_clause_id", "rank", "score", "retrieval_source", "retrieval_sources",
            "validity_status", "effective_from", "effective_to",
            "source_ranks", "source_scores", "rrf_score", "reranker_score",
        }
        trace = {
            "trace_version": "dev4_retrieval_trace_v1",
            "query_id": bundle.query_id,
            "as_of_date": bundle.as_of_date,
            "as_of_date_source": as_of_date_source,
            "schema_version": bundle.schema_version,
            "retrieval_config_version": bundle.retrieval_config_version,
            "corpus_hash": bundle.corpus_hash,
            "corpus_version": corpus_version.strip(),
            "retriever": bundle.retriever,
            "precomputed": bundle.precomputed,
            "metadata_filters": (
                bundle.metadata_filters.model_dump(mode="json", exclude_none=True)
                if bundle.metadata_filters is not None else {}
            ),
            "result_top_k": bundle.top_k,
            "returned_candidate_count": len(bundle.candidates),
            "outcome": "RETRIEVED" if bundle.candidates else "EMPTY",
            "latency_ms": bundle.latency_ms,
            "latency_breakdown": (
                bundle.latency_breakdown.model_dump(mode="json")
                if bundle.latency_breakdown is not None else None
            ),
            "candidates": [
                candidate.model_dump(mode="json", include=candidate_fields)
                for candidate in bundle.candidates
            ],
        }
        return bundle, trace


__all__ = ["RetrievalAdapter"]
