"""Reciprocal Rank Fusion helper used by hybrid retrieval."""
from __future__ import annotations

import math
from typing import Any, Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[dict[str, Any]]], *, top_k: int = 10, rrf_k: int = 60,
    weights: Sequence[float] | None = None,
) -> list[dict[str, Any]]:
    """Fuse rankings by chunk ID using weighted reciprocal rank contributions.

    Omitting ``weights`` preserves ordinary RRF: every source contributes
    ``1 / (rrf_k + rank)``. A zero-weight source contributes no candidates.
    """
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k phải là số nguyên lớn hơn 0")
    if not isinstance(rrf_k, int) or isinstance(rrf_k, bool) or rrf_k < 0:
        raise ValueError("rrf_k phải là số nguyên không âm")
    if weights is None:
        source_weights = [1.0] * len(rankings)
    else:
        if len(weights) != len(rankings):
            raise ValueError("Số trọng số phải bằng số danh sách ranking")
        source_weights = list(weights)
        if any(not isinstance(weight, (int, float)) or isinstance(weight, bool)
               or not math.isfinite(weight) or weight < 0 for weight in source_weights):
            raise ValueError("Trọng số RRF phải là số hữu hạn không âm")
        if rankings and not any(weight > 0 for weight in source_weights):
            raise ValueError("Ít nhất một trọng số RRF phải lớn hơn 0")
    fused: dict[str, dict[str, Any]] = {}
    for source_index, hits in enumerate(rankings):
        weight = source_weights[source_index]
        if weight == 0:
            continue
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
            row = fused.setdefault(chunk_id, {
                "chunk_id": chunk_id, "chunk_text": hit_text,
                "metadata": hit.get("metadata", {}), "rrf_score": 0.0,
                "score": 0.0,
                "source_ranks": {}, "source_scores": {}, "retrieval_sources": [],
            })
            if not row["chunk_text"] and hit_text:
                row["chunk_text"] = hit_text
            if not row["metadata"] and hit.get("metadata"):
                row["metadata"] = hit["metadata"]
            for field in ("document_id", "article_id", "clause_id", "parent_clause_id", "parent_id"):
                if field in hit and field not in row:
                    row[field] = hit[field]
            row["rrf_score"] += weight / (rrf_k + position)
            row["source_ranks"][source_name] = position
            if "score" in hit:
                row["source_scores"][source_name] = hit["score"]
            row["retrieval_sources"].append(source_name)
    ranked = sorted(fused.values(), key=lambda row: (-row["rrf_score"], row["chunk_id"]))
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
        row["score"] = row["rrf_score"]
    return ranked[:top_k]
