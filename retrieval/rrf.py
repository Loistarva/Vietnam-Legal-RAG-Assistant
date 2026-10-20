"""Reciprocal Rank Fusion helper used by hybrid retrieval."""
from __future__ import annotations

from typing import Any, Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[dict[str, Any]]], *, top_k: int = 10, rrf_k: int = 60
) -> list[dict[str, Any]]:
    """Fuse ranked result lists by chunk_id, summing 1 / (rrf_k + rank)."""
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k phải là số nguyên lớn hơn 0")
    if not isinstance(rrf_k, int) or isinstance(rrf_k, bool) or rrf_k < 0:
        raise ValueError("rrf_k phải là số nguyên không âm")
    fused: dict[str, dict[str, Any]] = {}
    for source_index, hits in enumerate(rankings):
        source_name = ("bm25", "dense")[source_index] if source_index < 2 else f"source_{source_index + 1}"
        seen: set[str] = set()
        for position, hit in enumerate(hits, 1):
            chunk_id = hit.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id:
                raise ValueError(f"Kết quả {source_name} thiếu chunk_id hợp lệ")
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            hit_text = hit.get("text") or hit.get("chunk_text", "")
            row = fused.setdefault(chunk_id, {
                "chunk_id": chunk_id, "text": hit_text, "chunk_text": hit_text,
                "metadata": hit.get("metadata", {}), "rrf_score": 0.0,
                "source_ranks": {}, "source_scores": {}, "retrieval_sources": [],
            })
            if not row["text"] and hit_text:
                row["text"] = hit_text
                row["chunk_text"] = hit_text
            if not row["metadata"] and hit.get("metadata"):
                row["metadata"] = hit["metadata"]
            for field in ("document_id", "article_id", "clause_id", "parent_clause_id", "parent_id"):
                if field in hit and field not in row:
                    row[field] = hit[field]
            row["rrf_score"] += 1.0 / (rrf_k + position)
            row["source_ranks"][source_name] = position
            if "score" in hit:
                row["source_scores"][source_name] = hit["score"]
            row["retrieval_sources"].append(source_name)
    ranked = sorted(fused.values(), key=lambda row: (-row["rrf_score"], row["chunk_id"]))
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    return ranked[:top_k]
