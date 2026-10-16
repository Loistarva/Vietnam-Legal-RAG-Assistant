"""Dense retrieval adapter backed by the existing BGE-M3/Qdrant components."""
from retrieval.hybrid_retriever import EmbeddingQdrantAdapter


class DenseRetriever(EmbeddingQdrantAdapter):
    """Expose the architecture's dense retriever name for application wiring."""


__all__ = ["DenseRetriever", "EmbeddingQdrantAdapter"]
