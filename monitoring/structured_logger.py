"""Bounded best-effort LogEvent sink compatible with Dev 5 EventSink.emit."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import queue
import secrets
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Callable

from monitoring.pii_masker import PIIMasker
from schemas.models import LogEvent

SAFE_METADATA_KEYS = frozenset({
    "action", "as_of_date", "as_of_date_source", "candidate_count", "candidate_source", "citation_count",
    "corpus_hash", "corpus_version", "done_reason", "error_type", "evidence_count", "fast_path",
    "grounding_status", "http_status", "invalid_indices", "kept_count", "llm_calls", "matched_rule_id",
    "min_evidence_score", "min_top1_score", "model", "model_digest", "model_version", "parse_status",
    "policy_version", "prompt_version", "reason", "reason_code", "request_id", "session_id",
    "retrieval_config_version", "retrieval_config_hash", "retryable", "route", "run_mode", "status",
    "threshold_config_version", "token_input", "token_output", "top1_score", "total_chars", "total_ms",
    "transport", "truncated", "ttft_model_ms", "violation_codes", "bm25_ms", "dense_ms", "rrf_ms",
    "rerank_ms", "context_ms",
})
_DEBUG_KEYS = frozenset({"query", "prompt", "answer_draft"})
_IDENTITY_KEY = secrets.token_bytes(32)


def sanitize_event(event: LogEvent, masker: PIIMasker) -> LogEvent:
    """Shared by adapter and sink so even a test/alternate sink sees safe data."""
    if not isinstance(event, LogEvent):
        raise ValueError("LogEvent required")
    data = event.model_dump(mode="python")
    allowed = SAFE_METADATA_KEYS | (_DEBUG_KEYS if masker.debug else frozenset())
    data["masked_metadata"] = {k: v for k, v in data["masked_metadata"].items() if k in allowed}
    original_id = data["query_id"]
    data = masker.sanitize(data)
    if data["query_id"] != original_id:
        data["query_id"] = "redacted-" + hmac.new(
            _IDENTITY_KEY, original_id.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return LogEvent.model_validate(data)


class JSONLSink:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def emit(self, event: LogEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False, allow_nan=False) + "\n")


class StructuredLogger:
    """emit never waits for disk/sink and never propagates data/sink errors.

    flush/close are explicit bounded lifecycle operations for owner wiring/tests;
    call close from application shutdown, not once per request.
    """
    def __init__(self, path: str | Path | None = None, *, sink=None, max_queue: int = 256,
                 masker: PIIMasker | None = None, diagnostic: Callable[[str], None] | None = None):
        if (path is None) == (sink is None):
            raise ValueError("Provide exactly one path or sink")
        if type(max_queue) is not int or max_queue < 1:
            raise ValueError("max_queue must be a positive integer")
        self.masker = masker or PIIMasker()
        self._sink = JSONLSink(path) if path is not None else sink
        self._diagnostic = diagnostic or safe_diagnostic
        self._queue: queue.Queue[LogEvent] = queue.Queue(maxsize=max_queue)
        self._diagnostics: queue.Queue[str] = queue.Queue(maxsize=32)
        self._condition = threading.Condition()
        self._closed = False
        self._pending = 0
        self._counts: Counter[str] = Counter()
        self._worker = threading.Thread(target=self._run, name="legal-rag-log", daemon=True)
        self._worker.start()

    def _note(self, code: str) -> None:
        with self._condition:
            self._counts[code] += 1
        # Health notifications also stay off the request thread.
        try:
            self._diagnostics.put_nowait(code)
        except queue.Full:
            pass

    def _drain_diagnostics(self) -> None:
        while True:
            try:
                code = self._diagnostics.get_nowait()
            except queue.Empty:
                return
            try:
                self._diagnostic(code)
            except Exception:
                pass

    @property
    def stats(self) -> dict[str, int]:
        with self._condition:
            return dict(self._counts)

    def _prepare(self, event: LogEvent) -> LogEvent:
        return sanitize_event(event, self.masker)

    def emit(self, event: LogEvent) -> None:
        try:
            safe = self._prepare(event)
            with self._condition:
                if self._closed:
                    self._note("LOGGER_CLOSED")
                    return
                try:
                    self._queue.put_nowait(safe)
                except queue.Full:
                    self._note("QUEUE_FULL")
                    return
                self._pending += 1
                self._counts["enqueued"] += 1
        except Exception:
            self._note("INVALID_EVENT")

    def _run(self) -> None:
        while True:
            try:
                event = self._queue.get(timeout=0.05)
            except queue.Empty:
                self._drain_diagnostics()
                with self._condition:
                    if self._closed and self._pending == 0:
                        return
                continue
            try:
                self._sink.emit(event)
                with self._condition:
                    self._counts["written"] += 1
            except Exception:
                self._note("SINK_WRITE_FAILED")
            finally:
                self._drain_diagnostics()
                self._queue.task_done()
                with self._condition:
                    self._pending -= 1
                    self._condition.notify_all()

    def flush(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            while self._pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def close(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            self._closed = True
        flushed = self.flush(max(0.0, deadline - time.monotonic()))
        self._worker.join(max(0.0, deadline - time.monotonic()))
        done = flushed and not self._worker.is_alive()
        if not done:
            self._note("SHUTDOWN_TIMEOUT")
        return done

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def safe_diagnostic(code: str) -> None:
    """Optional fallback channel; emits only the fixed diagnostic code."""
    logging.getLogger("legal_rag.logging_health").warning("Logging health: %s", code)
