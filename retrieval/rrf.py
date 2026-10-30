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
            hit_text = hit.get("chunk_text") or hit.get("text", "")
            hit_metadata = hit.get("metadata")
            hit_metadata = dict(hit_metadata) if isinstance(hit_metadata, dict) else {}
            row = fused.setdefault(chunk_id, {
                "chunk_id": chunk_id, "chunk_text": hit_text,
                "metadata": hit_metadata, "rrf_score": 0.0,
                "score": 0.0,
                "source_ranks": {}, "source_scores": {}, "retrieval_sources": [],
            })
            if not row["chunk_text"] and hit_text:
                row["chunk_text"] = hit_text
            for key, value in hit_metadata.items():
                if row["metadata"].get(key) in (None, "") and value not in (None, ""):
                    row["metadata"][key] = value
            for field in (
                "document_id", "article_id", "clause_id", "parent_clause_id", "parent_id",
                "effective_from", "effective_to",
            ):
                value = hit.get(field)
                if field in ("effective_from", "effective_to") and value in (None, ""):
                    value = hit_metadata.get(field)
                if value not in (None, "") and row.get(field) in (None, ""):
                    row[field] = value
            row["rrf_score"] += 1.0 / (rrf_k + position)
            row["source_ranks"][source_name] = position
            if "score" in hit:
                row["source_scores"][source_name] = hit["score"]
            row["retrieval_sources"].append(source_name)
    ranked = sorted(fused.values(), key=lambda row: (-row["rrf_score"], row["chunk_id"]))
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
        row["score"] = row["rrf_score"]
    return ranked[:top_k]
