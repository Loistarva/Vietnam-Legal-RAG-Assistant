"""Dev 1 event adapter. Dev 5 owns routes, status mapping and DI wiring."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from schemas.models import LogEvent
from monitoring.pii_masker import PIIMasker
from monitoring.structured_logger import sanitize_event


class APIEventAdapter:
    def __init__(self, sink, query_id: str, *, masker: PIIMasker | None = None):
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError("query_id is required")
        self.sink = sink
        self.query_id = query_id
        self.failures = 0
        self.masker = masker or PIIMasker()

    def event(self, event_type: str, status: str, *, stage: str = "api", duration_ms: float | None = None,
              error_code: str | None = None, **metadata: Any) -> None:
        try:
            event = LogEvent(event_id=uuid.uuid4().hex, query_id=self.query_id, stage=stage,
                             event_type=event_type, timestamp=datetime.now(timezone.utc).isoformat(),
                             status=status, duration_ms=duration_ms, error_code=error_code,
                             masked_metadata=metadata)
            self.sink.emit(sanitize_event(event, self.masker))
        except Exception:
            # No exception text and no sensitive payload in the fallback channel.
            self.failures += 1

    def request_start(self, *, request_id: str | None = None, session_id: str | None = None) -> None:
        self.event("request_start", "accepted", request_id=request_id, session_id=session_id)

    def request_validation_error(self, http_status: int = 422) -> None:
        self.event("request_validation_error", "rejected", error_code="INVALID_REQUEST", http_status=http_status)

    def auth_rejected(self, http_status: int = 401) -> None:
        self.event("auth_rejected", "rejected", error_code="AUTH_REQUIRED", http_status=http_status)

    def response_complete(self, status: str, *, duration_ms: float | None = None, **metadata: Any) -> None:
        self.event("response_complete", status, duration_ms=duration_ms, **metadata)
