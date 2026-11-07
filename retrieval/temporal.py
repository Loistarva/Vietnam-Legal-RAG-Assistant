"""Shared date normalization and effective-period checks for legal retrieval."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping


def normalize_date(value: Any, *, field_name: str, chunk_id: str | None = None) -> str | None:
    """Return an ISO date, preserve empty values as unbounded, and reject malformed dates."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        label = f" cho chunk {chunk_id!r}" if chunk_id else ""
        raise ValueError(f"{field_name}{label} phải là ngày ISO hoặc rỗng, nhận được {value!r}")

    raw = value.strip()
    if not raw:
        return None
    try:
        if len(raw) == 10:
            return date.fromisoformat(raw).isoformat()
        # Accept an ISO datetime in source data, but store/compare its calendar date.
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError as exc:
        label = f" cho chunk {chunk_id!r}" if chunk_id else ""
        raise ValueError(f"{field_name}{label} không phải ngày hợp lệ: {value!r}") from exc


def normalize_as_of_date(value: Any = None) -> str:
    """Normalize a query date; queries without one use today's local legal date."""
    if value is None:
        return date.today().isoformat()
    normalized = normalize_date(value, field_name="as_of_date")
    if normalized is None:
        raise ValueError("as_of_date không được rỗng")
    return normalized


def effective_period(record: Mapping[str, Any]) -> tuple[str | None, str | None]:
    metadata = record.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    effective_from = (
        record.get("effective_from") or metadata.get("effective_from")
        or record.get("effective_date") or metadata.get("effective_date")
    )
    effective_to = record.get("effective_to") or metadata.get("effective_to")
    if effective_to is None or effective_to == "":
        effective_to = record.get("expiry_date") or metadata.get("expiry_date")
    chunk_id = str(record.get("chunk_id") or "") or None
    return (
        normalize_date(effective_from, field_name="effective_from", chunk_id=chunk_id),
        normalize_date(effective_to, field_name="effective_to", chunk_id=chunk_id),
    )


def is_effective_at(record: Mapping[str, Any], as_of_date: Any) -> bool:
    as_of = normalize_as_of_date(as_of_date)
    effective_from, effective_to = effective_period(record)
    return (effective_from is None or effective_from <= as_of) and (
        effective_to is None or as_of < effective_to
    )
