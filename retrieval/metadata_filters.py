"""Shared exact-match metadata filter semantics for BM25 and Dense retrieval."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


FILTER_FIELDS = (
    "document_type", "document_number", "document_id", "article_id", "clause_id", "validity_status",
)


def normalize_metadata_filters(filters: Mapping[str, Any] | Any | None) -> dict[str, str]:
    if filters is None:
        return {}
    if hasattr(filters, "model_dump"):
        filters = filters.model_dump(exclude_none=True)
    if not isinstance(filters, Mapping):
        raise TypeError("metadata_filters phải là object MetadataFilters hoặc mapping")
    unknown = set(filters) - set(FILTER_FIELDS)
    if unknown:
        raise ValueError(f"Metadata filters không hỗ trợ các trường: {sorted(unknown)}")
    normalized: dict[str, str] = {}
    for key, value in filters.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"metadata_filters.{key} phải là chuỗi không rỗng")
        normalized[key] = value.strip()
    return normalized


def metadata_matches(record: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
    metadata = record.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    for key, expected in filters.items():
        actual = record.get(key)
        if actual is None:
            actual = metadata.get(key)
        if actual != expected:
            return False
    return True
