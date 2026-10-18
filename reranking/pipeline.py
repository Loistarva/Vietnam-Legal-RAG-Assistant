"""Hybrid Retrieval + Reranker packaged as one standalone call (Sprint 6, Dev 5).

``RetrievalPipeline.run`` fetches ``retrieval_top_k`` candidates from any
retriever exposing ``search(query, top_k)`` (HybridRetriever, DenseRetriever, a
stub), maps them to the shared retrieval result (Sprint 6 section 4.3), reranks
them and returns ``{"query_id", "retriever", "results", ...}``.

Retriever and reranker errors propagate as ``PipelineError``; they are never
turned into empty results, so ``results: []`` always means "nothing found".
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, Sequence

from reranking.reranker import Reranker, deduplicate_candidates

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RETRIEVAL_CONFIG_PATH = ROOT / "retrieval" / "config.yaml"
DEFAULT_RETRIEVAL_TOP_K = 50
DEFAULT_RRF_K = 60
UNKNOWN_VALIDITY_STATUS = "Không xác định"

# Optional trace fields kept next to the section 4.3 fields when the upstream provides them.
TRACE_FIELDS = ("parent_id", "rrf_score", "retrieval_sources", "source_ranks",
                "retrieval_rank", "retrieval_score")


class CandidateRetriever(Protocol):
    def search(self, query: str, top_k: int) -> list[dict[str, Any]]: ...


class PipelineError(RuntimeError):
    """A retriever/reranker adapter failed; ``stage`` is ``retrieval`` or ``rerank``."""

    def __init__(self, stage: str, cause: BaseException):
        super().__init__(f"{stage} thất bại: {type(cause).__name__}: {cause}")
        self.stage = stage
        self.cause = cause


def _require_positive_int(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} phải là số nguyên lớn hơn 0")
    return value


def to_contract_result(hit: Mapping[str, Any]) -> dict[str, Any]:
    """Map one retriever/reranker hit to the shared retrieval result.

    Only the aliases documented in docs/data_contract.md section 5 are resolved
    (``doc_id`` -> ``document_id``, ``text`` -> ``chunk_text``). ``article_id``,
    ``clause_id`` and ``parent_clause_id`` are copied when the upstream provides
    them and are ``null`` otherwise: they are never derived from other IDs, so
    evaluation can report missing parent metadata instead of a guessed match.
    """
    if not isinstance(hit, Mapping):
        raise ValueError("Mỗi kết quả retrieval phải là object")
    chunk_id = hit.get("chunk_id")
    if not isinstance(chunk_id, str) or not chunk_id:
        raise ValueError("Kết quả retrieval thiếu chunk_id hợp lệ")
    raw_metadata = hit.get("metadata") or {}
    if not isinstance(raw_metadata, Mapping):
        raise ValueError(f"metadata của {chunk_id} phải là object")
    metadata = dict(raw_metadata)

    def pick(field: str) -> Any:
        value = hit.get(field)
        return value if value not in (None, "") else (metadata.get(field) or None)

    score = hit.get("score")
    if score is None:
        score = hit.get("rrf_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError(f"Kết quả {chunk_id} thiếu score dạng số")
    chunk_text = hit.get("chunk_text") or hit.get("text") or ""
    if not chunk_text:
        logger.warning("Chunk %s không có chunk_text", chunk_id)

    metadata["validity_status"] = (metadata.get("validity_status") or hit.get("validity_status")
                                   or UNKNOWN_VALIDITY_STATUS)
    if not metadata.get("article_number") and hit.get("article_number"):
        metadata["article_number"] = hit["article_number"]

    row = {
        "chunk_id": chunk_id,
        "document_id": pick("document_id") or pick("doc_id"),
        "article_id": pick("article_id"),
        "clause_id": pick("clause_id"),
        "parent_clause_id": pick("parent_clause_id"),
        "rank": hit.get("rank"),
        "score": float(score),
        "chunk_text": chunk_text,
        "metadata": metadata,
    }
    for field in TRACE_FIELDS:
        if hit.get(field) is not None:
            row[field] = hit[field]
    return row


class RetrievalPipeline:
    """Retriever -> contract mapping -> optional Reranker -> ranked top-k envelope."""

    def __init__(self, retriever: CandidateRetriever, reranker: Reranker | None = None, *,
                 retrieval_top_k: int = DEFAULT_RETRIEVAL_TOP_K, retriever_name: str = "hybrid",
                 retriever_settings: Mapping[str, Any] | None = None):
        self.retriever = retriever
        self.reranker = reranker
        self.retrieval_top_k = _require_positive_int("retrieval_top_k", retrieval_top_k)
        self.retriever_name = retriever_name
        self.retriever_settings = dict(retriever_settings or {})

    @property
    def name(self) -> str:
        return f"{self.retriever_name}_reranker" if self.reranker else self.retriever_name

    @property
    def default_top_k(self) -> int:
        return self.reranker.rerank_top_k if self.reranker else min(5, self.retrieval_top_k)

    def run(self, query: str, top_k: int | None = None, *, query_id: str = "Q_CLI_001") -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        top_k = self.default_top_k if top_k is None else _require_positive_int("top_k", top_k)
        limit = min(self.retrieval_top_k, self.reranker.max_candidates) if self.reranker else self.retrieval_top_k
        if top_k > limit:
            raise ValueError(f"top_k ({top_k}) không được lớn hơn số candidate được xếp hạng ({limit})")
        query = query.strip()

        started = time.perf_counter()
        try:
            hits = self.retriever.search(query, self.retrieval_top_k)
            if not isinstance(hits, list):
                raise TypeError(f"retriever phải trả list, nhận được {type(hits).__name__}")
            candidates = [to_contract_result(hit) for hit in hits]
        except Exception as exc:
            logger.error("Retrieval stage failed: %s", exc)
            raise PipelineError("retrieval", exc) from exc
        retrieved_at = time.perf_counter()

        rerank_stats: dict[str, Any] = {}
        if self.reranker is not None:
            try:
                final = [to_contract_result(hit) for hit in self.reranker.rerank(query, candidates, top_k)]
            except Exception as exc:
                logger.error("Rerank stage failed: %s", exc)
                raise PipelineError("rerank", exc) from exc
            rerank_stats = dict(self.reranker.last_stats)
        else:
            unique, duplicates = deduplicate_candidates(candidates)
            final = unique[:top_k]
            rerank_stats = {"duplicates_removed": duplicates}
        for rank, row in enumerate(final, 1):
            row["rank"] = rank
        finished = time.perf_counter()

        stats = {
            "retrieved_candidates": len(candidates),
            **rerank_stats,
            "returned": len(final),
            "retrieval_latency_ms": round((retrieved_at - started) * 1000.0, 3),
            "total_latency_ms": round((finished - started) * 1000.0, 3),
        }
        logger.info("Pipeline[%s] query_id=%s retrieved=%d returned=%d total=%.1fms",
                    self.name, query_id, len(candidates), len(final), stats["total_latency_ms"])
        return {
            "query_id": query_id,
            "query": query,
            "retriever": self.name,
            "results": final,
            "config": {
                "retriever": {"backend": self.retriever_name, "retrieval_top_k": self.retrieval_top_k,
                              **self.retriever_settings},
                "reranker": self.reranker.describe() if self.reranker else None,
                "top_k": top_k,
            },
            "stats": stats,
        }


# ---------------------------------------------------------------------------
# Retriever factories used by scripts/run_retrieval.py
# ---------------------------------------------------------------------------
class FixtureRetriever:
    """Stub retriever returning a fixed candidate list, independent of the query."""

    def __init__(self, candidates: Sequence[Mapping[str, Any]]):
        self.candidates = [dict(candidate) for candidate in candidates]

    @classmethod
    def from_file(cls, path: str | Path) -> "FixtureRetriever":
        """Read a JSON list, or an object with ``candidates`` or ``results``."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Không đọc được candidate fixture {path}: {exc}") from exc
        if isinstance(data, dict):
            data = data.get("candidates", data.get("results"))
        if not isinstance(data, list):
            raise ValueError("Candidate fixture phải là list hoặc object có 'candidates'/'results'")
        return cls(data)

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        _require_positive_int("top_k", top_k)
        return [dict(candidate) for candidate in self.candidates[:top_k]]


def load_retrieval_settings(path: str | Path = DEFAULT_RETRIEVAL_CONFIG_PATH) -> dict[str, Any]:
    """Read Dev 4's retrieval/config.yaml.

    ``retrieval_top_k`` comes from ``retrieval.retrieval_top_k`` (section 14.3)
    and falls back to the older ``hybrid.candidate_k`` key.
    """
    import yaml

    config_path = Path(path)
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Không đọc được cấu hình retrieval {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{config_path} phải là YAML mapping")
    retrieval = data.get("retrieval") or {}
    hybrid = data.get("hybrid") or {}
    bm25 = data.get("bm25") or {}
    dense = data.get("dense") or {}
    settings = {
        "retrieval_top_k": retrieval.get("retrieval_top_k", hybrid.get("candidate_k", DEFAULT_RETRIEVAL_TOP_K)),
        "rrf_k": hybrid.get("rrf_k", DEFAULT_RRF_K),
        "bm25_index": bm25.get("index", "legal-child-chunks-dev"),
        "bm25_text_field": bm25.get("text_field", "content_segmented"),
        "dense_model": dense.get("model"),
    }
    _require_positive_int("retrieval_top_k", settings["retrieval_top_k"])
    if not isinstance(settings["rrf_k"], int) or isinstance(settings["rrf_k"], bool) or settings["rrf_k"] < 0:
        raise ValueError("rrf_k phải là số nguyên không âm")
    return settings


def build_mock_dense_retriever(chunks_path: str | Path) -> CandidateRetriever:
    """Offline retriever: Dev 3's DenseRetriever with deterministic mock vectors over a chunk file.

    Chunks are adapted by Dev 3's ``scripts/build_index.py`` loader so the mock
    index matches what ``build_index.py --mock`` produces. Rankings are not
    semantic; use this only to exercise the pipeline without services.
    """
    from embedding.dense_retriever import DenseRetriever
    from embedding.vector_store import LegalVectorStore
    from scripts.build_index import load_chunks_from_repo

    path = Path(chunks_path)
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy chunk file: {path}")
    chunks = load_chunks_from_repo(path)
    store = LegalVectorStore(collection_name="mock_pipeline", dimension=768, use_qdrant=False)
    retriever = DenseRetriever(vector_store=store, use_mock=True, use_word_segmentation=False)
    indexed = retriever.index_chunks(chunks)
    logger.info("Mock dense index: %d chunks from %s", indexed, path)
    return retriever


def build_hybrid_retriever(settings: Mapping[str, Any], *, elasticsearch_url: str | None,
                           elasticsearch_index: str | None = None, qdrant_path: str | None = None,
                           collection: str = "vietnam_legal_chunks",
                           dense_model: str | None = None) -> CandidateRetriever:
    """Real Hybrid retriever (Dev 4): Elasticsearch BM25 + Qdrant dense + RRF, no internal reranker.

    The pipeline owns reranking, so HybridRetriever returns its fused top
    ``retrieval_top_k`` candidates unchanged.
    """
    from embedding.dense_retriever import MODEL_DIMENSIONS, DenseRetriever
    from embedding.vector_store import LegalVectorStore
    from retrieval.hybrid_retriever import ElasticsearchBM25Retriever, HybridRetriever, HybridSearchConfig

    if not elasticsearch_url:
        raise ValueError("Cần --elasticsearch-url hoặc biến ELASTICSEARCH_URL cho retriever hybrid")
    model = dense_model or settings.get("dense_model")
    if model not in MODEL_DIMENSIONS:
        raise ValueError(f"Dense model không được hỗ trợ: {model!r}; chọn một trong {sorted(MODEL_DIMENSIONS)}")
    try:
        from elasticsearch import Elasticsearch
    except ImportError as exc:
        raise RuntimeError("Cần cài elasticsearch client (pip install -r requirements.txt)") from exc

    index = elasticsearch_index or settings["bm25_index"]
    client = Elasticsearch(elasticsearch_url)
    if not client.ping():
        raise ConnectionError(f"Không kết nối được Elasticsearch tại {elasticsearch_url}")
    if not client.indices.exists(index=index):
        raise ValueError(f"Elasticsearch index không tồn tại: {index}")
    sparse = ElasticsearchBM25Retriever(client, index, text_field=settings["bm25_text_field"])

    storage = qdrant_path or os.getenv("QDRANT_PATH") or str(ROOT / "data" / "indexes" / "qdrant_storage")
    store = LegalVectorStore(collection_name=collection, dimension=MODEL_DIMENSIONS[model], storage_path=storage)
    if store.count() == 0:
        raise ValueError(f"Qdrant collection {collection} tại {storage} rỗng; chạy scripts/build_index.py trước")
    dense = DenseRetriever(vector_store=store, model_name=model)

    top_k = settings["retrieval_top_k"]
    config = HybridSearchConfig(top_k=top_k, candidate_k=top_k, rrf_k=settings["rrf_k"])
    return HybridRetriever(sparse, dense, config)


__all__ = [
    "CandidateRetriever", "FixtureRetriever", "PipelineError", "RetrievalPipeline", "TRACE_FIELDS",
    "build_hybrid_retriever", "build_mock_dense_retriever", "load_retrieval_settings", "to_contract_result",
]
