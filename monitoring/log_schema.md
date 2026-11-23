# Structured logging contract

Sprint 11 uses `schemas.models.LogEvent` and its generated schema. This file documents usage; it does not define a second schema. Dev 3 owns canonical fields and enums.

`StructuredLogger.emit(LogEvent)` implements the existing Dev 5 EventSink protocol. Events retain event_id, query_id, stage, event_type, timestamp, status, optional duration_ms/error_code and masked_metadata. No API or orchestration imports are required.

## Metadata and privacy

`SAFE_METADATA_KEYS` in `structured_logger.py` is the executable allow-list. It includes route/reason codes, counts, stage latency, prompt/model/config/corpus versions and hashes, citation/Gate outcome and transport status. Unknown keys are dropped. Missing measurements remain absent or null; the logger does not fabricate hashes, durations or legal validity.

All retained string values and nested structures pass through `PIIMasker`. Secret-bearing keys are dropped at every nesting level. Production drops raw query, prompt, answer, content, request/response bodies and headers. Debug is explicit and still redacts known patterns and supplied secret values. The policy and limits are in `docs/privacy/logging_policy.md`.

Opaque query IDs remain unchanged. A query ID containing detected PII/secret is replaced with a process-scoped HMAC identifier. Adapter and logger share the same process key so events stay correlated without collapsing different detected-sensitive IDs. This identifier is intentionally not stable across process restarts.

## Lifecycle and failure behavior

One logger instance owns one daemon worker and a bounded queue. Redaction and model validation happen before enqueue. `emit` never waits for disk or the destination sink. A full queue drops the new event and increments `QUEUE_FULL`; invalid events increment `INVALID_EVENT`. Diagnostic messages are also deferred, bounded and contain only fixed codes.

`flush(timeout)` waits for accepted events to finish; it does not assert that every write succeeded. Inspect `stats` for `written`, `SINK_WRITE_FAILED`, `QUEUE_FULL`, `INVALID_EVENT`, `LOGGER_CLOSED` and `SHUTDOWN_TIMEOUT`. `close(timeout)` closes admission, drains accepted work and joins within its deadline. A hung destination may outlive shutdown as a daemon worker; the API must not wait indefinitely.

The JSONL destination is for one process/logger instance per path. Multi-process rotation, retention scheduling and durable delivery are deployment responsibilities, not provided here.
