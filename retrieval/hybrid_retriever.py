"""Hybrid BM25 + dense retrieval with Reciprocal Rank Fusion (RRF)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from retrieval.bm25_retriever import BM25Index

logger = logging.getLogger(__name__)


class DenseRetriever(Protocol):
    """Interface expected by HybridRetriever; scores are local to dense ranking."""

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]: ...


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


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[dict[str, Any]]],
    *,
    top_k: int = 10,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse ranked result lists by chunk_id, using 1 / (rrf_k + 1-based rank)."""
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k phải là số nguyên lớn hơn 0")
    if not isinstance(rrf_k, int) or isinstance(rrf_k, bool) or rrf_k < 0:
        raise ValueError("rrf_k phải là số nguyên không âm")

    fused: dict[str, dict[str, Any]] = {}
    for source_index, results in enumerate(result_lists):
        seen_in_source: set[str] = set()
        source_name = "bm25" if source_index == 0 else "dense" if source_index == 1 else f"source_{source_index + 1}"
        for position, hit in enumerate(results, start=1):
            chunk_id = hit.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id:
                raise ValueError(f"Kết quả {source_name} thiếu chunk_id hợp lệ")
            if chunk_id in seen_in_source:
                continue
            seen_in_source.add(chunk_id)
            row = fused.setdefault(chunk_id, {
                "chunk_id": chunk_id,
                "text": hit.get("text", ""),
                "metadata": hit.get("metadata", {}),
                "rrf_score": 0.0,
                "source_ranks": {},
                "source_scores": {},
                "retrieval_sources": [],
            })
            # Fill payload if the first branch only returned ranking metadata.
            if not row["text"] and hit.get("text"):
                row["text"] = hit["text"]
            if not row["metadata"] and hit.get("metadata"):
                row["metadata"] = hit["metadata"]
            row["rrf_score"] += 1.0 / (rrf_k + position)
            row["source_ranks"][source_name] = position
            if "score" in hit:
                row["source_scores"][source_name] = hit["score"]
            row["retrieval_sources"].append(source_name)

    ranked = sorted(fused.values(), key=lambda item: (-item["rrf_score"], item["chunk_id"]))
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked[:top_k]


class HybridRetriever:
    """Search BM25 and a DenseRetriever, then combine their rankings with RRF."""

    def __init__(self, bm25_index: BM25Index, dense_retriever: DenseRetriever,
                 config: HybridSearchConfig | None = None):
        self.bm25_index = bm25_index
        self.dense_retriever = dense_retriever
        self.config = config or HybridSearchConfig()

    def retrieve(self, query: str, top_k: int | None = None) -> dict[str, list[dict[str, Any]]]:
        """Return the top-K branch results and fusion from one execution."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        requested_top_k = self.config.top_k if top_k is None else top_k
        if not isinstance(requested_top_k, int) or isinstance(requested_top_k, bool) or requested_top_k < 1:
            raise ValueError("top_k phải là số nguyên lớn hơn 0")
        if requested_top_k > self.config.candidate_k:
            raise ValueError("top_k không được lớn hơn candidate_k")

        lexical_hits = self.bm25_index.search(query, top_k=self.config.candidate_k)
        dense_hits = self.dense_retriever.search(query, top_k=self.config.candidate_k)
        return {
            "bm25": lexical_hits[:requested_top_k],
            "dense": dense_hits[:requested_top_k],
            "hybrid": reciprocal_rank_fusion(
                [lexical_hits, dense_hits], top_k=requested_top_k, rrf_k=self.config.rrf_k
            ),
        }

    def search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Return top-K RRF results; defaults to ``config.top_k``."""
        return self.retrieve(query, top_k=top_k)["hybrid"]


def hybrid_search(
    query: str,
    bm25_index: BM25Index,
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

