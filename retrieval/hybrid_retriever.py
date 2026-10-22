"""Hybrid BM25 + dense retrieval with Reciprocal Rank Fusion (RRF)."""
from __future__ import annotations

import logging
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from retrieval.rrf import reciprocal_rank_fusion


logger = logging.getLogger(__name__)


class DenseRetriever(Protocol):
    """Interface expected by HybridRetriever; scores are local to dense ranking."""

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]: ...


class SparseRetriever(Protocol):
    def search(self, query: str, top_k: int) -> list[dict[str, Any]]: ...


class Reranker(Protocol):
    def rerank(self, query: str, hits: Sequence[dict[str, Any]], top_k: int) -> list[dict[str, Any]]: ...


class ElasticsearchBM25Retriever:
    """Sparse search adapter for an Elasticsearch child-chunk index."""

    def __init__(self, client: Any, index: str, *, text_field: str = "content_segmented"):
        self.client, self.index, self.text_field = client, index, text_field

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k phải là số nguyên lớn hơn 0")
        response = self.client.search(index=self.index, size=top_k, query={
            "bool": {
                "must": [{"multi_match": {
                    "query": query,
                    "fields": [self.text_field, "breadcrumb^1.5", "article_ref^4",
                               "metadata.article_number^4", "metadata.clause_ref^2"],
                    "type": "most_fields",
                    "operator": "or",
                }}],
                "must_not": [{"term": {"metadata.validity_status": "Hết hiệu lực"}}],
            }
        })
        rows = []
        for rank, hit in enumerate(response["hits"]["hits"], 1):
            source = hit.get("_source", {})
            chunk_id = source.get("chunk_id", hit.get("_id"))
            meta = source.get("metadata", {})
            chunk_text = source.get("chunk_text") or source.get("content") or source.get("text", "")
            parent_clause_id = (
                source.get("parent_clause_id")
                or source.get("parent_id")
                or meta.get("parent_clause_id")
                or ""
            )
            doc_id = (
                source.get("document_id")
                or source.get("doc_id")
                or meta.get("document_id")
                or (chunk_id.split("_art_")[0] if "_art_" in str(chunk_id) else "")
            )
            art_id = (
                source.get("article_id")
                or meta.get("article_id")
                or (parent_clause_id.split("_clause_")[0] if "_clause_" in str(parent_clause_id) else "")
            )
            cl_id = source.get("clause_id") or meta.get("clause_id") or parent_clause_id
            rows.append({
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "article_id": art_id,
                "clause_id": cl_id,
                "parent_clause_id": parent_clause_id,
                "rank": rank,
                "score": float(hit.get("_score", 0.0)),
                "chunk_text": chunk_text,
                "text": chunk_text,
                "parent_id": source.get("parent_id"),
                "metadata": meta,
            })
        return rows


class CrossEncoderReranker:
    """Lazy bge-reranker-v2-m3 adapter; scores the RRF candidate pool."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", model: Any = None):
        self.model_name, self._model = model_name, model

    @property
    def model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError("Cần cài sentence-transformers để dùng cross-encoder reranker") from exc
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, hits: Sequence[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if not hits:
            return []
        scores = self.model.predict([(query, hit.get("chunk_text") or hit.get("text", "")) for hit in hits])
        ranked = []
        for hit, score in zip(hits, scores):
            row = dict(hit)
            row["reranker_score"] = float(score)
            ranked.append(row)
        return sorted(ranked, key=lambda row: (-row["reranker_score"], row["chunk_id"]))[:top_k]


def filter_legal_metadata(hits: Sequence[dict[str, Any]], *, as_of: date | None = None,
                          filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Apply the shared metadata/temporal gate after retrieval where backend filters are absent."""
    as_of = as_of or date.today()
    as_of_str = as_of.isoformat()
    accepted = []
    for hit in hits:
        metadata = hit.get("metadata", {})
        if metadata.get("validity_status") == "Hết hiệu lực" or hit.get("validity_status") == "Hết hiệu lực":
            continue
        effective_from = (
            metadata.get("effective_from")
            or metadata.get("effective_date")
            or hit.get("effective_from")
        )
        effective_to = (
            metadata.get("effective_to")
            if "effective_to" in metadata
            else hit.get("effective_to")
        )
        if effective_from:
            try:
                eff_from_str = str(effective_from)[:10]
                if as_of_str < eff_from_str:
                    continue
            except (ValueError, TypeError):
                logger.warning("Ignoring invalid effective_from on chunk %s", hit.get("chunk_id"))
        if effective_to:
            try:
                eff_to_str = str(effective_to)[:10]
                if as_of_str >= eff_to_str:
                    continue
            except (ValueError, TypeError):
                logger.warning("Ignoring invalid effective_to on chunk %s", hit.get("chunk_id"))
        if filters and any(metadata.get(key) != value for key, value in filters.items()):
            continue
        accepted.append(dict(hit))
    return accepted


class RedisJSONCache:
    """Small JSON cache adapter usable for query and reranker cache namespaces."""

    def __init__(self, client: Any, *, prefix: str, ttl_seconds: int = 3600):
        self.client, self.prefix, self.ttl_seconds = client, prefix.rstrip(":"), ttl_seconds

    def get(self, key: str) -> Any:
        import json
        value = self.client.get(f"{self.prefix}:{key}")
        return json.loads(value) if value is not None else None

    def set(self, key: str, value: Any) -> None:
        import json
        self.client.setex(f"{self.prefix}:{key}", self.ttl_seconds,
                          json.dumps(value, ensure_ascii=False))


@dataclass(frozen=True)
class HybridSearchConfig:
    """Candidate depth, final result count, and RRF smoothing constant."""

    top_k: int = 10
    candidate_k: int = 50
    rrf_k: int = 60

    def __post_init__(self) -> None:
        if not isinstance(self.top_k, int) or isinstance(self.top_k, bool) or self.top_k < 1:
            raise ValueError("top_k phải là số nguyên lớn hơn 0")
        if not isinstance(self.candidate_k, int) or isinstance(self.candidate_k, bool) or self.candidate_k < 1:
            raise ValueError("candidate_k phải là số nguyên lớn hơn 0")
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k phải >= top_k")
        if not isinstance(self.rrf_k, int) or isinstance(self.rrf_k, bool) or self.rrf_k < 0:
            raise ValueError("rrf_k phải là số nguyên không âm")


class EmbeddingQdrantAdapter:
    """Adapt the project's query embedder + VectorStore to DenseRetriever."""

    def __init__(self, embedding_service: Any, vector_store: Any):
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        try:
            query_vector = self.embedding_service.embed_query(query)
            return self.vector_store.search(query_vector, top_k=top_k)
        except Exception:
            logger.exception("Dense retrieval failed; propagating error (no implicit BM25 fallback)")
            raise


class HybridRetriever:
    """Parallel sparse/dense retrieval, RRF candidate fusion, then optional reranking.

    ``retrieve`` keeps the architecture's Top-50 fused candidates available as
    ``fused`` and returns reranked Top-K as ``hybrid`` when a reranker is wired.
    """

    def __init__(self, bm25_index: SparseRetriever, dense_retriever: DenseRetriever,
                 config: HybridSearchConfig | None = None, *, reranker: Reranker | None = None,
                 parent_resolver: Any = None, confidence_filter: Any = None,
                 metadata_filter: Any = None, cache: Any = None):
        self.bm25_index = bm25_index
        self.dense_retriever = dense_retriever
        self.config = config or HybridSearchConfig()
        self.reranker = reranker
        self.parent_resolver = parent_resolver
        self.confidence_filter = confidence_filter
        self.metadata_filter = metadata_filter
        self.cache = cache

    def retrieve(self, query: str, top_k: int | None = None) -> dict[str, list[dict[str, Any]]]:
        """Return the top-K branch results and fusion from one execution."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        requested_top_k = self.config.top_k if top_k is None else top_k
        if not isinstance(requested_top_k, int) or isinstance(requested_top_k, bool) or requested_top_k < 1:
            raise ValueError("top_k phải là số nguyên lớn hơn 0")
        if requested_top_k > self.config.candidate_k:
            raise ValueError("top_k không được lớn hơn candidate_k")

        cache_key = None
        if self.cache is not None:
            import hashlib
            normalized = " ".join(query.casefold().split())
            cache_key = hashlib.sha256(f"{normalized}|top_k={requested_top_k}".encode("utf-8")).hexdigest()
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Sparse and dense branches are independent in the system architecture.
        with ThreadPoolExecutor(max_workers=2) as executor:
            sparse_future = executor.submit(self.bm25_index.search, query, self.config.candidate_k)
            dense_future = executor.submit(self.dense_retriever.search, query, self.config.candidate_k)
            try:
                lexical_hits = sparse_future.result()
            except Exception:
                logger.exception("Sparse retrieval failed; propagating error (no implicit dense fallback)")
                raise
            try:
                dense_hits = dense_future.result()
            except Exception:
                logger.exception("Dense retrieval failed; propagating error (no implicit sparse fallback)")
                raise
        fused = reciprocal_rank_fusion(
            [lexical_hits, dense_hits], top_k=self.config.candidate_k, rrf_k=self.config.rrf_k
        )
        if self.metadata_filter is not None:
            fused = self.metadata_filter(fused)
        final = self.reranker.rerank(query, fused, requested_top_k) if self.reranker else fused[:requested_top_k]
        if self.confidence_filter is not None:
            final = self.confidence_filter(query, final)
        if self.parent_resolver is not None:
            final = self.parent_resolver.resolve(final)
        result = {
            "bm25": lexical_hits[:requested_top_k],
            "dense": dense_hits[:requested_top_k],
            "fused": fused,
            "hybrid": final[:requested_top_k],
        }
        if self.cache is not None and cache_key is not None:
            self.cache.set(cache_key, result)
        return result

    def search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Return top-K RRF results; defaults to ``config.top_k``."""
        return self.retrieve(query, top_k=top_k)["hybrid"]


def hybrid_search(
    query: str,
    bm25_index: SparseRetriever,
    embedding_service: Any,
    vector_store: Any,
    *,
    top_k: int = 10,
    candidate_k: int = 50,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Compatibility helper around HybridRetriever and the Qdrant adapter."""
    config = HybridSearchConfig(top_k=top_k, candidate_k=candidate_k, rrf_k=rrf_k)
    dense = EmbeddingQdrantAdapter(embedding_service, vector_store)
    return HybridRetriever(bm25_index, dense, config).search(query)
