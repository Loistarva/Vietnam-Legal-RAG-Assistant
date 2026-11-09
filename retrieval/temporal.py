"""Shared date normalization and effective-period checks for legal retrieval."""
from __future__ import annotations

import re
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


_DATE_VALUE = r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})"
_DATE_CONTEXTS = (
    re.compile(rf"^\s*(?:ngày\s+)?(?P<value>{_DATE_VALUE})(?!\d)", re.IGNORECASE),
    re.compile(
        rf"\b(?:tại(?:\s+thời\s+điểm)?|vào\s+ngày|tính\s+đến|đến\s+ngày)\s+"
        rf"(?:ngày\s+)?(?P<value>{_DATE_VALUE})(?!\d)", re.IGNORECASE
    ),
    re.compile(
        r"^\s*(?:vào|trong|tại(?:\s+thời\s+điểm)?|tính\s+đến)\s+"
        r"(?:ngày\s+)?(?P<day>\d{1,2})\s+tháng\s+(?P<month>\d{1,2})\s+năm\s+(?P<year>\d{4})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:vào\s+ngày|tại(?:\s+thời\s+điểm)?|tính\s+đến)\s+"
        r"(?:ngày\s+)?(?P<day>\d{1,2})\s+tháng\s+(?P<month>\d{1,2})\s+năm\s+(?P<year>\d{4})\b",
        re.IGNORECASE,
    ),
)
_YEAR_CONTEXTS = (
    re.compile(r"^\s*năm\s+(?P<year>\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(?:vào|trong|tại\s+thời\s+điểm)\s+năm\s+(?P<year>\d{4})\b", re.IGNORECASE),
)


def extract_question_as_of_date(question: str, *, today: date | None = None) -> str | None:
    """Extract only dates stated as query-time context, not dates in legal titles.

    Invalid date mentions are ignored so interactive input can fall back to the
    UI date or today. A bare year means year-end for a past year, today for the
    current year, and January 1 for a future year.
    """
    if not isinstance(question, str) or not question.strip():
        return None
    today = today or date.today()
    for pattern in _DATE_CONTEXTS:
        match = pattern.search(question)
        if not match:
            continue
        if "value" in match.groupdict() and match.group("value"):
            raw = match.group("value")
            try:
                if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", raw):
                    year, month, day = re.split("-", raw)
                    return date(int(year), int(month), int(day)).isoformat()
                day, month, year = re.split(r"[/-]", raw)
                return date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                return None
        try:
            return date(int(match.group("year")), int(match.group("month")),
                        int(match.group("day"))).isoformat()
        except ValueError:
            return None

    for pattern in _YEAR_CONTEXTS:
        match = pattern.search(question)
        if match:
            year = int(match.group("year"))
            if year == today.year:
                return today.isoformat()
            return date(year, 12, 31).isoformat() if year < today.year else date(year, 1, 1).isoformat()
    return None


def resolve_interactive_as_of_date(
    question: str, ui_as_of_date: Any = None, *, today: date | None = None
) -> tuple[str, str]:
    """Return the resolved date and provenance: question, ui, or today."""
    question_date = extract_question_as_of_date(question, today=today)
    if question_date is not None:
        return question_date, "question"
    if ui_as_of_date is not None and str(ui_as_of_date).strip():
        return normalize_as_of_date(ui_as_of_date), "ui"
    effective_today = today or date.today()
    return effective_today.isoformat(), "today"


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
