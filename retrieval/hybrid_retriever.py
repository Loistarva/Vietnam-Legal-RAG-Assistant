"""Hybrid BM25 + dense retrieval with Reciprocal Rank Fusion (RRF)."""
from __future__ import annotations

import logging
import inspect
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
from typing import Any, Protocol, Sequence

from retrieval.rrf import reciprocal_rank_fusion
from retrieval.temporal import effective_period, is_effective_at, normalize_as_of_date


logger = logging.getLogger(__name__)

BM25_TOKENIZER_VERSION = "9.5.0"
BM25_TOKENIZER_NAME = "underthesea"


def _segment_bm25_query(query: str) -> str:
    """Tách từ truy vấn bằng đúng phiên bản dùng để tạo corpus BM25."""
    try:
        installed_version = package_version("underthesea")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "BM25 cần underthesea==9.5.0 để tách từ truy vấn; "
            "hãy cài các gói trong requirements.txt."
        ) from exc

    if installed_version != BM25_TOKENIZER_VERSION:
        raise RuntimeError(
            "Phiên bản underthesea không khớp corpus BM25: "
            f"yêu cầu {BM25_TOKENIZER_VERSION}, môi trường đang có {installed_version}."
        )

    try:
        from underthesea import word_tokenize
    except ImportError as exc:
        raise RuntimeError(
            "Không thể nạp underthesea==9.5.0 để tách từ truy vấn BM25."
        ) from exc

    segmented_query = word_tokenize(query, format="text")
    if not isinstance(segmented_query, str) or not segmented_query.strip():
        raise RuntimeError("underthesea không trả về truy vấn BM25 đã tách từ hợp lệ.")
    return segmented_query


class DenseRetriever(Protocol):
    """Interface expected by HybridRetriever; scores are local to dense ranking."""

    def search(self, query: str, top_k: int, *, as_of_date: str) -> list[dict[str, Any]]: ...


class SparseRetriever(Protocol):
    def search(self, query: str, top_k: int, *, as_of_date: str) -> list[dict[str, Any]]: ...


class Reranker(Protocol):
    def rerank(self, query: str, hits: Sequence[dict[str, Any]], top_k: int) -> list[dict[str, Any]]: ...


class ElasticsearchBM25Retriever:
    """Sparse search adapter for an Elasticsearch child-chunk index."""

    def __init__(self, client: Any, index: str, *, text_field: str = "content_segmented"):
        self.client, self.index, self.text_field = client, index, text_field
        self._tokenizer_metadata_verified = False
        self._index_metadata: dict[str, Any] = {}

    def _verify_index_tokenizer(self) -> dict[str, Any]:
        """Verify Elasticsearch declares the same tokenizer used by the BM25 corpus."""
        if self._tokenizer_metadata_verified:
            return dict(self._index_metadata)
        try:
            response = self.client.indices.get_mapping(index=self.index)
            mapping = response[self.index]["mappings"]
            metadata = mapping.get("_meta", {})
        except Exception as exc:
            raise RuntimeError(
                f"Không xác minh được tokenizer metadata của Elasticsearch index {self.index!r}. "
                "Hãy dựng index bằng retrieval/build_bm25_index.py."
            ) from exc
        expected = {
            "bm25_tokenizer": BM25_TOKENIZER_NAME,
            "bm25_tokenizer_version": BM25_TOKENIZER_VERSION,
            "bm25_text_field": self.text_field,
        }
        mismatches = {key: (metadata.get(key), value) for key, value in expected.items()
                      if metadata.get(key) != value}
        if mismatches:
            raise RuntimeError(
                f"Tokenizer metadata của index {self.index!r} không khớp: {mismatches}. "
                "Hãy dựng lại index BM25 từ corpus có chunking_report.json hợp lệ."
            )
        self._tokenizer_metadata_verified = True
        self._index_metadata = dict(metadata)
        return metadata

    @staticmethod
    def build_temporal_filter(as_of_date: str) -> list[dict[str, Any]]:
        as_of = normalize_as_of_date(as_of_date)
        return [
            {"bool": {"should": [
                {"range": {"effective_from": {"lte": as_of}}},
                {"bool": {"must_not": [{"exists": {"field": "effective_from"}}]}},
            ], "minimum_should_match": 1}},
            {"bool": {"should": [
                {"range": {"effective_to": {"gt": as_of}}},
                {"bool": {"must_not": [{"exists": {"field": "effective_to"}}]}},
            ], "minimum_should_match": 1}},
        ]

    def search(self, query: str, top_k: int, *, as_of_date: str | None = None) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k phải là số nguyên lớn hơn 0")
        raw_query = query.strip()
        as_of = normalize_as_of_date(as_of_date)
        self._verify_index_tokenizer()
        segmented_query = _segment_bm25_query(raw_query)
        response = self.client.search(index=self.index, size=top_k, query={
            "bool": {
                "should": [
                    {"multi_match": {
                        "query": raw_query,
                        # Câu hỏi gốc khớp với content và breadcrumb chưa tách từ.
                        "fields": ["content", "breadcrumb^1.5"],
                        "type": "most_fields",
                        "operator": "or",
                    }},
                    {"multi_match": {
                        "query": segmented_query,
                        # Câu hỏi đã tách từ đồng bộ với trường content_segmented của corpus.
                        "fields": [self.text_field],
                        "type": "most_fields",
                        "operator": "or",
                    }},
                ],
                "minimum_should_match": 1,
                "filter": self.build_temporal_filter(as_of),
            }
        })
        rows = []
        for rank, hit in enumerate(response["hits"]["hits"], 1):
            source = hit.get("_source", {})
            chunk_id = source.get("chunk_id", hit.get("_id"))
            meta = source.get("metadata", {})
            chunk_text = source.get("chunk_text") or source.get("content") or source.get("text", "")
            doc_id = source.get("document_id") or source.get("doc_id") or meta.get("document_id") or meta.get("doc_id") or ""
            art_id = source.get("article_id") or meta.get("article_id") or ""
            cl_id = source.get("clause_id") or meta.get("clause_id") or ""
            parent_clause_id = source.get("parent_clause_id") or meta.get("parent_clause_id") or ""
            parent_id = source.get("parent_id") or meta.get("parent_id")
            effective_from, effective_to = effective_period(source)
            rows.append({
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "article_id": art_id,
                "clause_id": cl_id,
                "parent_clause_id": parent_clause_id,
                "rank": rank,
                "score": float(hit.get("_score", 0.0)),
                "chunk_text": chunk_text,
                "parent_id": parent_id,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "metadata": meta,
            })
        return rows


def filter_legal_metadata(hits: Sequence[dict[str, Any]], *, as_of: date | None = None,
                          filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Apply the shared metadata/temporal gate after retrieval where backend filters are absent."""
    as_of_str = normalize_as_of_date(as_of)
    accepted = []
    for hit in hits:
        metadata = hit.get("metadata", {})
        if not is_effective_at(hit, as_of_str):
            continue
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

    def search(self, query: str, top_k: int, *, as_of_date: str | None = None) -> list[dict[str, Any]]:
        try:
            query_vector = self.embedding_service.embed_query(query)
            as_of = normalize_as_of_date(as_of_date)
            search = self.vector_store.search
            try:
                parameters = inspect.signature(search).parameters
            except (TypeError, ValueError):
                parameters = {}
            if "as_of_date" in parameters or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
            ):
                return search(query_vector, top_k=top_k, as_of_date=as_of)
            raise TypeError("Vector store search() phải nhận as_of_date để lọc Qdrant trước Top-K")
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

    def retrieve(self, query: str, top_k: int | None = None, *,
                 as_of_date: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """Return the top-K branch results and fusion from one execution."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        requested_top_k = self.config.top_k if top_k is None else top_k
        if not isinstance(requested_top_k, int) or isinstance(requested_top_k, bool) or requested_top_k < 1:
            raise ValueError("top_k phải là số nguyên lớn hơn 0")
        if requested_top_k > self.config.candidate_k:
            raise ValueError("top_k không được lớn hơn candidate_k")
        as_of = normalize_as_of_date(as_of_date)

        cache_key = None
        if self.cache is not None:
            import hashlib
            normalized = " ".join(query.casefold().split())
            # Kết quả phụ thuộc cả cấu hình fusion, bộ lọc metadata và reranker, nên khóa cache gồm
            # cả ba; bộ lọc/reranker nên khai báo cache_key ổn định, nếu không thì dùng tên lớp.
            def component_key(component: Any) -> str:
                if component is None:
                    return "none"
                return str(getattr(component, "cache_key", None) or getattr(component, "__qualname__", None)
                           or type(component).__qualname__)

            key_text = "|".join([
                normalized, f"as_of_date={as_of}", f"top_k={requested_top_k}",
                f"candidate_k={self.config.candidate_k}",
                f"rrf_k={self.config.rrf_k}", f"filter={component_key(self.metadata_filter)}",
                f"reranker={component_key(self.reranker)}",
            ])
            cache_key = hashlib.sha256(key_text.encode("utf-8")).hexdigest()
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Sparse and dense branches are independent in the system architecture.
        def search_branch(retriever: Any) -> list[dict[str, Any]]:
            search = retriever.search
            try:
                parameters = inspect.signature(search).parameters
            except (TypeError, ValueError):
                parameters = {}
            supports_date = "as_of_date" in parameters or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
            )
            if supports_date:
                return search(query, self.config.candidate_k, as_of_date=as_of)
            raise TypeError(
                f"Retriever {type(retriever).__name__}.search() phải nhận as_of_date "
                "để lọc theo thời điểm trước Top-K"
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            sparse_future = executor.submit(search_branch, self.bm25_index)
            dense_future = executor.submit(search_branch, self.dense_retriever)
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
        fused = filter_legal_metadata(fused, as_of=date.fromisoformat(as_of))
        if self.metadata_filter is not None:
            try:
                parameters = inspect.signature(self.metadata_filter).parameters
            except (TypeError, ValueError):
                parameters = {}
            if "as_of" in parameters:
                fused = self.metadata_filter(fused, as_of=date.fromisoformat(as_of))
            elif "as_of_date" in parameters:
                fused = self.metadata_filter(fused, as_of_date=as_of)
            else:
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

    def search(self, query: str, top_k: int | None = None, *,
               as_of_date: str | None = None) -> list[dict[str, Any]]:
        """Return top-K RRF results; defaults to ``config.top_k``."""
        return self.retrieve(query, top_k=top_k, as_of_date=as_of_date)["hybrid"]


def hybrid_search(
    query: str,
    bm25_index: SparseRetriever,
    embedding_service: Any,
    vector_store: Any,
    *,
    top_k: int = 10,
    candidate_k: int = 50,
    rrf_k: int = 60,
    as_of_date: str | None = None,
) -> list[dict[str, Any]]:
    """Compatibility helper around HybridRetriever and the Qdrant adapter."""
    config = HybridSearchConfig(top_k=top_k, candidate_k=candidate_k, rrf_k=rrf_k)
    dense = EmbeddingQdrantAdapter(embedding_service, vector_store)
    return HybridRetriever(bm25_index, dense, config).search(query, as_of_date=as_of_date)
