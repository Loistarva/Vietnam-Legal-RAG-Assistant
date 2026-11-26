"""Stage events of one request (Sprint 10 D5.1), emitted as the shared ``LogEvent`` contract.

The orchestrator, CLI and API only call ``StageEmitter.emit``. Where the event goes is a
sink: ``NullEventSink`` (default), ``ListEventSink`` (tests, SSE), ``JsonlEventSink`` (local
file). Dev 1's structured logger (D1.2) plugs in as one more sink with the same
``emit(LogEvent)`` method; nothing here formats or stores logs for production.

``masked_metadata`` only takes keys from ``SAFE_METADATA_KEYS``: ids, versions, counts,
scores, statuses and reason codes. Query text, prompt, model answer, headers and API keys
are never passed in, so a sink cannot leak them.
"""
from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestration.interfaces import EventSink
from schemas.models import ErrorCode, EventStage, LogEvent

SAFE_METADATA_KEYS = frozenset({
    "attempt", "regeneration_reason", "repair_notes_version",
    "action", "as_of_date", "as_of_date_source", "candidate_count", "candidate_source", "citation_count",
    "corpus_hash", "corpus_version", "done_reason", "error_type", "evidence_count", "fast_path", "grounding_status",
    "http_status", "invalid_indices", "kept_count", "llm_calls", "matched_rule_id", "min_evidence_score",
    "min_top1_score", "model", "model_digest", "missing_facts", "catalog_version", "generic_clarification", "dropped_count",
    "parse_status", "policy_version", "prompt_version", "reason", "reason_code", "request_id", "rerank_top_k",
    "retrieval_config_version", "retryable", "route", "run_mode", "session_id", "status", "threshold_config_version",
    "token_input", "token_output", "top1_score", "total_chars", "total_ms", "transport", "truncated",
    "ttft_model_ms", "violation_codes",
})


class NullEventSink:
    def emit(self, event: LogEvent) -> None:
        return None


class ListEventSink:
    """Keeps events in memory (tests, SSE)."""

    def __init__(self) -> None:
        self.events: list[LogEvent] = []

    def emit(self, event: LogEvent) -> None:
        self.events.append(event)


class JsonlEventSink:
    """Appends one JSON line per event. Local development only; Dev 1's logger replaces it."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, event: LogEvent) -> None:
        line = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


class FanOutSink:
    def __init__(self, sinks: Iterable[EventSink]):
        self.sinks = [sink for sink in sinks if sink is not None]

    def emit(self, event: LogEvent) -> None:
        first_error = None
        for sink in self.sinks:
            try:
                sink.emit(event)
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error


def _now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def mask_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Drop every key outside the allow-list and every ``None`` value."""
    unknown = sorted(set(metadata) - SAFE_METADATA_KEYS)
    if unknown:
        raise ValueError(f"Metadata key không nằm trong danh sách được phép ghi log: {unknown}")
    return {key: value for key, value in metadata.items() if value is not None}


class StageEmitter:
    """Builds ``LogEvent`` for one ``query_id`` and sends it to the sink.

    A sink that raises does not break the request: logging is off the answer path (plan
    Sprint 10, section 3)."""

    def __init__(self, query_id: str, sink: EventSink | None = None):
        if not query_id or not query_id.strip():
            raise ValueError("query_id không được rỗng")
        self.query_id = query_id
        self.sink = sink or NullEventSink()
        self.sink_errors = 0

    def emit(self, stage: EventStage, event_type: str, status: str, *, duration_ms: float | None = None,
             error_code: ErrorCode | None = None, **metadata: Any) -> LogEvent:
        event = LogEvent(
            event_id=uuid.uuid4().hex,
            query_id=self.query_id,
            stage=stage,
            event_type=event_type,
            timestamp=_now_utc(),
            status=status,
            duration_ms=None if duration_ms is None else round(max(float(duration_ms), 0.0), 2),
            error_code=error_code,
            masked_metadata=mask_metadata(metadata),
        )
        try:
            self.sink.emit(event)
        except Exception:  # noqa: BLE001 - a broken sink must not fail the answer
            self.sink_errors += 1
        return event


__all__ = [
    "EventSink", "FanOutSink", "JsonlEventSink", "ListEventSink", "NullEventSink", "SAFE_METADATA_KEYS",
    "StageEmitter", "mask_metadata",
]
