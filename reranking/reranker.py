"""Reranking interfaces and cross-encoder implementation."""
from retrieval.hybrid_retriever import CrossEncoderReranker

Reranker = CrossEncoderReranker

__all__ = ["CrossEncoderReranker", "Reranker"]
