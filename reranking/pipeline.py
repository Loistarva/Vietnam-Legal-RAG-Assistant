"""Hybrid Retrieval + Reranker packaged as one standalone call (Sprint 6, Dev 5).

``RetrievalPipeline.run`` fetches ``retrieval_top_k`` candidates from any
retriever exposing ``search(query, top_k)`` (HybridRetriever, DenseRetriever, a
stub), maps them to the shared retrieval result (Sprint 6 section 4.3), reranks
them, attaches parent context (``reranking.parent_context``) and returns
``{"query_id", "retriever", "results", ...}``. ``as_of_date`` is passed to the
retriever when its ``search`` accepts that keyword; the envelope config records
whether the results were filtered by date.

Retriever and reranker errors propagate as ``PipelineError``; they are never
turned into empty results, so ``results: []`` always means "nothing found".
"""
from __future__ import annotations

import inspect
import json
import logging
import os
import time
import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, Sequence

from reranking.parent_context import ParentContextResolver
from reranking.reranker import Reranker, deduplicate_candidates
from retrieval.temporal import is_effective_at, normalize_as_of_date

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RETRIEVAL_CONFIG_PATH = ROOT / "retrieval" / "config.yaml"
DEFAULT_RETRIEVAL_TOP_K = 50
UNKNOWN_VALIDITY_STATUS = "Không xác định"

# Optional trace fields kept next to the section 4.3 fields when the upstream provides them.
# Only fields declared in schemas/retrieval_schema.json (RetrievalResultItem) are emitted.
TRACE_FIELDS = ("parent_id", "rrf_score", "reranker_score", "retrieval_sources",
                "source_ranks", "source_scores")
# Key under source_ranks/source_scores holding the pre-rerank rank/score.
RETRIEVAL_SOURCE = "retrieval"


class CandidateRetriever(Protocol):
    def search(self, query: str, top_k: int, *, as_of_date: str) -> list[dict[str, Any]]: ...


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
    # The reranker keeps the pre-rerank values as retrieval_rank/retrieval_score; the schema
    # has no such fields, so they move to source_ranks/source_scores["retrieval"].
    if hit.get("retrieval_rank") is not None:
        row["source_ranks"] = {**row.get("source_ranks", {}), RETRIEVAL_SOURCE: hit["retrieval_rank"]}
        row["reranker_score"] = float(score)
    if hit.get("retrieval_score") is not None:
        row["source_scores"] = {**row.get("source_scores", {}), RETRIEVAL_SOURCE: float(hit["retrieval_score"])}
    return row


def _parse_as_of_date(value: str | None) -> str:
    try:
        return normalize_as_of_date(value)
    except ValueError as exc:
        raise ValueError(f"as_of_date phải có dạng YYYY-MM-DD, nhận được {value!r}") from exc


def _accepts_keyword(function: Any, name: str) -> bool:
    try:
        parameters = inspect.signature(function).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(p.name == name or p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters)


class RetrievalPipeline:
    """Retriever -> contract mapping -> optional Reranker -> optional Parent-Context Resolver -> envelope."""

    def __init__(self, retriever: CandidateRetriever, reranker: Reranker | None = None, *,
                 retrieval_top_k: int = DEFAULT_RETRIEVAL_TOP_K, retriever_name: str = "hybrid",
                 retriever_settings: Mapping[str, Any] | None = None,
                 parent_resolver: ParentContextResolver | None = None):
        self.retriever = retriever
        self.reranker = reranker
        self.retrieval_top_k = _require_positive_int("retrieval_top_k", retrieval_top_k)
        self.retriever_name = retriever_name
        self.retriever_settings = dict(retriever_settings or {})
        self.parent_resolver = parent_resolver
        # The temporal pre-filter belongs to the retriever (E1); it receives as_of_date only
        # when its search() declares that keyword. query_id goes only to retrievers that ask
        # for it (PrecomputedRetriever looks its candidates up by query_id).
        self.retriever_takes_as_of_date = _accepts_keyword(retriever.search, "as_of_date")
        self.retriever_takes_query_id = _accepts_keyword(retriever.search, "query_id")

    @property
    def name(self) -> str:
        # The mock scorer is token overlap, not the architecture's cross-encoder; keep its runs
        # apart from real "<retriever>_reranker" results.
        if self.reranker is None:
            return self.retriever_name
        suffix = "mock_reranker" if self.reranker.backend == "mock" else "reranker"
        return f"{self.retriever_name}_{suffix}"

    @property
    def default_top_k(self) -> int:
        return self.reranker.rerank_top_k if self.reranker else min(5, self.retrieval_top_k)

    def run(self, query: str, top_k: int | None = None, *, query_id: str = "Q_CLI_001",
            as_of_date: str | None = None) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        as_of_date = _parse_as_of_date(as_of_date)
        top_k = self.default_top_k if top_k is None else _require_positive_int("top_k", top_k)
        limit = min(self.retrieval_top_k, self.reranker.max_candidates) if self.reranker else self.retrieval_top_k
        if top_k > limit:
            raise ValueError(f"top_k ({top_k}) không được lớn hơn số candidate được xếp hạng ({limit})")
        query = query.strip()

        if not self.retriever_takes_as_of_date:
            raise ValueError(
                f"Retriever {self.retriever_name} không hỗ trợ lọc theo as_of_date; "
                "từ chối trả kết quả chưa lọc theo thời điểm."
            )
        temporal_filter = "retriever"

        search_kwargs: dict[str, Any] = {}
        search_kwargs["as_of_date"] = as_of_date
        if self.retriever_takes_query_id:
            search_kwargs["query_id"] = query_id
        started = time.perf_counter()
        try:
            hits = self.retriever.search(query, self.retrieval_top_k, **search_kwargs)
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
        parent_stats: dict[str, Any] = {}
        if self.parent_resolver is not None:
            final = self.parent_resolver.resolve(final)
            parent_stats = {"parent_context": dict(self.parent_resolver.last_stats)}
        finished = time.perf_counter()

        stats = {
            "retrieved_candidates": len(candidates),
            **rerank_stats,
            **parent_stats,
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
            "latency_ms": stats.get("total_latency_ms", 0.0),
            "top_k": top_k,
            "config": {
                "retriever": {"backend": self.retriever_name, "retrieval_top_k": self.retrieval_top_k,
                              **self.retriever_settings},
                "reranker": self.reranker.describe() if self.reranker else None,
                "parent_context": self.parent_resolver.describe() if self.parent_resolver else None,
                "as_of_date": as_of_date,
                "temporal_filter": temporal_filter,
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

    def search(self, query: str, top_k: int, *, as_of_date: str) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        _require_positive_int("top_k", top_k)
        return [dict(candidate) for candidate in self.candidates if is_effective_at(candidate, as_of_date)][:top_k]


class PrecomputedRetriever:
    """Candidates saved by an earlier run without reranking, looked up by query_id.

    Lets Hybrid retrieval and the cross-encoder run in separate processes, so the
    dense model and the reranker never share one GPU: run 1 with ``--reranker none
    --no-parent-context --top-k <retrieval_top_k>`` writes the envelopes, run 2 with
    ``--retriever precomputed --candidates <file>`` reranks them. Run 1 already
    applied the temporal filter; its date must match the second-stage run.
    """

    def __init__(self, envelopes: Sequence[Mapping[str, Any]]):
        if not envelopes:
            raise ValueError("File candidate không có câu hỏi nào")
        self.envelopes: dict[str, Mapping[str, Any]] = {}
        for envelope in envelopes:
            if not isinstance(envelope, Mapping) or not isinstance(envelope.get("results"), list):
                raise ValueError("Mỗi phần tử của file candidate phải là envelope có 'results'")
            query_id = envelope.get("query_id")
            if not isinstance(query_id, str) or not query_id:
                raise ValueError("Envelope trong file candidate thiếu query_id")
            if query_id in self.envelopes:
                raise ValueError(f"query_id bị trùng trong file candidate: {query_id}")
            config = envelope.get("config") or {}
            if config.get("reranker") is not None:
                raise ValueError(f"{query_id} đã được rerank; lần chạy 1 phải dùng --reranker none")
            if config.get("parent_context") is not None:
                raise ValueError(f"{query_id} đã gắn parent_text; lần chạy 1 phải dùng --no-parent-context")
            self.envelopes[query_id] = envelope
        first = next(iter(self.envelopes.values()))
        # Settings of the run that produced the candidates, recorded with every reranked output.
        self.source_settings = dict((first.get("config") or {}).get("retriever") or {})

    @classmethod
    def from_file(cls, path: str | Path) -> "PrecomputedRetriever":
        """Read the ``--output`` of run 1: one envelope (``--query``) or a list (``--queries``)."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Không đọc được file candidate {path}: {exc}") from exc
        return cls([data] if isinstance(data, dict) else data if isinstance(data, list) else [])

    def search(self, query: str, top_k: int, *, query_id: str, as_of_date: str) -> list[dict[str, Any]]:
        _require_positive_int("top_k", top_k)
        envelope = self.envelopes.get(query_id)
        if envelope is None:
            raise ValueError(f"File candidate không có query_id {query_id}")
        if str(envelope.get("query", "")).strip() != query.strip():
            raise ValueError(f"Câu hỏi của {query_id} khác câu hỏi trong file candidate")
        saved_as_of_date = (envelope.get("config") or {}).get("as_of_date")
        if saved_as_of_date != as_of_date:
            raise ValueError(
                f"Ngày as_of_date của candidate {query_id} ({saved_as_of_date!r}) "
                f"không khớp lần chạy hiện tại ({as_of_date!r}); hãy tạo lại candidate cùng ngày."
            )
        saved = envelope.get("top_k")
        if isinstance(saved, int) and saved < top_k:
            raise ValueError(f"File candidate chỉ lưu top {saved} của {query_id}, cần {top_k} "
                             f"(chạy lần 1 với --top-k {top_k})")
        return [dict(hit) for hit in envelope["results"][:top_k]]


def load_retrieval_settings(path: str | Path = DEFAULT_RETRIEVAL_CONFIG_PATH) -> dict[str, Any]:
    """Load the shared validated config and expose legacy flat keys to this CLI."""
    from retrieval.settings import ROOT as REPOSITORY_ROOT, load_settings

    shared = load_settings(path)
    corpus_path = Path(shared["retrieval"]["corpus_path"])
    if not corpus_path.is_absolute():
        corpus_path = REPOSITORY_ROOT / corpus_path
    index_dir = Path(shared["dense"]["index_dir"])
    if not index_dir.is_absolute():
        index_dir = REPOSITORY_ROOT / index_dir
    return {
        "shared_config": shared,
        "retrieval_top_k": shared["retrieval"]["retrieval_top_k"],
        "result_top_k": shared["retrieval"]["result_top_k"],
        "rrf_k": shared["hybrid"]["rrf_k"],
        "fusion": shared["hybrid"]["fusion"],
        "bm25_index": shared["bm25"]["index"],
        "bm25_text_field": shared["bm25"]["text_field"],
        "bm25_tokenizer": shared["bm25"]["tokenizer"],
        "bm25_tokenizer_version": str(shared["bm25"]["tokenizer_version"]),
        "dense_model": shared["dense"]["model"],
        "dimension": shared["dense"]["dimension"],
        "collection": shared["dense"]["collection"],
        "index_dir": index_dir,
        "qdrant_storage_path": index_dir / "qdrant_storage",
        "corpus_path": corpus_path,
    }


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
                           collection: str | None = None,
                           dense_model: str | None = None, cache: Any = None,
                           cache_context: Mapping[str, Any] | None = None) -> CandidateRetriever:
    """Real Hybrid retriever (Dev 4): Elasticsearch BM25 + Qdrant dense + RRF, no internal reranker.

    The pipeline owns reranking, so HybridRetriever returns its fused top
    ``retrieval_top_k`` candidates unchanged.
    """
    from embedding.dense_retriever import DenseRetriever
    from embedding.model_registry import ModelRegistry
    from embedding.vector_store import LegalVectorStore, chunk_file_sha256
    from retrieval.hybrid_retriever import ElasticsearchBM25Retriever, HybridRetriever, HybridSearchConfig

    if not elasticsearch_url:
        raise ValueError("Cần --elasticsearch-url hoặc biến ELASTICSEARCH_URL cho retriever hybrid")
    shared = settings.get("shared_config")
    if not isinstance(shared, dict):
        raise ValueError("Thiếu shared_config đã validate; hãy dùng load_retrieval_settings()")
    model = dense_model or settings["dense_model"]
    registry = ModelRegistry(shared)
    model_spec = registry.get_model(model)
    dense_settings = copy.deepcopy(shared)
    dense_settings["dense"]["model"] = model
    dense_settings["dense"]["dimension"] = model_spec["dimension"]
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
    corpus_path = Path(settings["corpus_path"])
    if not corpus_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy corpus cấu hình: {corpus_path}")
    sparse = ElasticsearchBM25Retriever(
        client, index, text_field=settings["bm25_text_field"], settings=shared,
        expected_corpus_sha256=chunk_file_sha256(corpus_path),
    )

    actual_collection = collection or settings["collection"]
    storage = Path(qdrant_path or os.getenv("QDRANT_PATH") or settings["qdrant_storage_path"])
    if not storage.is_absolute():
        storage = ROOT / storage
    store = LegalVectorStore(collection_name=actual_collection, dimension=model_spec["dimension"], storage_path=storage)
    if store.count() == 0:
        raise ValueError(f"Qdrant collection {actual_collection} tại {storage} rỗng; chạy scripts/build_index.py trước")
    dense = DenseRetriever(vector_store=store, model_name=model, settings=dense_settings,
                           corpus_path=settings["corpus_path"])

    top_k = settings["retrieval_top_k"]
    config = HybridSearchConfig(top_k=top_k, candidate_k=top_k, rrf_k=settings["rrf_k"])
    effective_cache_context = {
        "dense_model": model,
        "dense_dimension": model_spec["dimension"],
        "dense_use_word_segmentation": model_spec["use_word_segmentation"],
        "dense_text_field": model_spec["text_field"],
        "qdrant_collection": actual_collection,
        "elasticsearch_index": index,
        "bm25_text_field": settings["bm25_text_field"],
        "bm25_tokenizer": settings["bm25_tokenizer"],
        "bm25_tokenizer_version": settings["bm25_tokenizer_version"],
        "corpus_sha256": chunk_file_sha256(corpus_path),
        "fusion": settings["fusion"],
        "candidate_k": top_k,
        "rrf_k": settings["rrf_k"],
    }
    effective_cache_context.update(dict(cache_context or {}))
    return HybridRetriever(sparse, dense, config, cache=cache, cache_context=effective_cache_context)


__all__ = [
    "CandidateRetriever", "FixtureRetriever", "PipelineError", "PrecomputedRetriever", "RetrievalPipeline",
    "TRACE_FIELDS",
    "build_hybrid_retriever", "build_mock_dense_retriever", "load_retrieval_settings", "to_contract_result",
]
