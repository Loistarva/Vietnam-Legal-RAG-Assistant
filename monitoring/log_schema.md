# Dev 1 JSONL interface (provisional, Week 10)

`StructuredLogger(path=..., enabled=True).emit(event) -> bool` accepts dicts or
public Pydantic `model_dump(mode="json")` values. `log` is an alias for `emit`.
It imports no API, model, database or retrieval implementation.

Each input requires an opaque `query_id`, `stage`, `event_type`, `status`.
Optional fields: nonnegative finite `duration_ms` and `masked_metadata` dict.
The sink generates a new UUID `event_id` and UTC `timestamp`. Caller timestamps,
headers, environment and top-level extra fields are never forwarded.

Stages: `api`, `router`, `retrieval`, `rerank`, `context`, `llm`, `citation`,
`gate`, `response`. Labels contain only ASCII letters/digits/`_.:-`; IDs contain
letters/digits/`_-`, at most 128 characters, and must not contain detected PII.
Supply the same query ID at every callback in one request. No raw query/prompt
logging mode is exposed. Unknown metadata fields are discarded.

The metadata allowlist in `structured_logger.METADATA` covers model/prompt/config
versions, corpus hash, route, latency, citation identity, grounding outcome,
done_reason/truncation/token usage and nullable hallucination provenance.
Citation bodies are excluded; only citation identity/date fields survive.
Known secrets can be supplied explicitly as `secrets=(...)`; environment values
are never scanned or serialized. Recursive masking runs before serialization.
Non-finite JSON values and malformed events are rejected without partial writes.

`emit` returns false on disabled logging, invalid events or sink failure. For
failure it writes only `structured_log_write_failed` to its safe error channel,
never exception details. It does not retry, raise into business code or include
a failed event in diagnostics. A lock serializes threads sharing one logger.
Separate processes/instances must use separate files or a managed shared sink;
this implementation does not claim cross-process safety or durable delivery.

`RequestTrace(query_id, logger.emit, metadata)` provides `record(...)` and
`with trace.stage(stage): ...`. Stage timing uses a monotonic clock; callback
failure does not change the returned business result or suppress its exception.
Dev 5 calls these interfaces from its existing orchestration. Dev 1 does not
modify the API, add a second Gate, or control generation/recovery.

`summarize(events)` returns counts by stage, structural violation and semantic
assessment separately; an unassessed event is not a false hallucination.

**Contract dependency:** `schemas/models.py` is absent in the supplied branch.
This is a documented dict/model-dump boundary, not a competing canonical schema.
Dev 3/TL must freeze their models and approve field mapping before contract and
live integration sign-off. No canonical schema files were created or changed.
