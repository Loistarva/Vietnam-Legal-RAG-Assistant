# Logging integration for Dev 5

The Dev 1 sink plugs into the EventSink protocol already implemented on `feature/week10-fastapi-integration`. API routes and dependency wiring remain owned by Dev 5. Keep one shared logger for the app lifecycle.

```python
from monitoring.pii_masker import PIIMasker
from monitoring.structured_logger import StructuredLogger

# configured_keys comes from existing API settings, never a literal production key.
logger = StructuredLogger(
    "logs/api_events.jsonl",
    masker=PIIMasker(secret_values=configured_keys),
    max_queue=256,
)
# In Dev 5 wiring: service = build_ask_service(settings, sink=logger)
# On shutdown: inspect logger.stats and logger.close(timeout=2.0).
```

Existing StageEmitter calls can use this sink directly. Do not replace shared orchestration or produce duplicate events. The current API branch already emits `request_received`, `request_rejected` and completion/stage events, including pre-pipeline auth/validation failures.

For a boundary not already emitting events, the optional adapter offers safe helpers:

```python
from monitoring.api_event_adapter import APIEventAdapter

events = APIEventAdapter(logger, query_id, masker=logger.masker)
events.request_start(request_id=request_id, session_id=session_id)
events.auth_rejected(http_status=401)
events.request_validation_error(http_status=422)
events.event("stage_complete", "ok", stage="citation", violation_codes=[])
events.response_complete("SUCCESS", duration_ms=measured_total_ms)
```

These lines illustrate separate request outcomes, not events to emit unconditionally for every request. The adapter does not validate credentials, decide HTTP status, run the pipeline, authorize answer emission or implement Gate recovery. It also accepts the existing event names through `event(...)`, so no event rename is required.

Logger metadata accepts retrieval_config_hash and stage timings. Dev 5 must align its StageEmitter allow-list with fields approved by Dev 3 before sending newly introduced metadata keys; the current emitter may reject keys before reaching the sink. Dev 4 supplies real hashes/timings; never substitute a version label or estimate a missing measurement.

## Checks

```powershell
python -m pytest -q test/grounding test/monitoring test/orchestration
python -m ruff check grounding monitoring test/grounding test/monitoring
```

`test/monitoring/test_api_integration_optional.py` runs real FastAPI HTTP requests with fake services when Dev 5's API is available, and skips with an explicit reason on the testing baseline where it is absent. On the API branch also run `python -m api.export_openapi --check` and API/E2E tests. Mock-service HTTP tests are not live ES/Qdrant/Qwen or browser E2E evidence.

## Failures and shutdown

Sink errors and queue saturation do not propagate through emit. `flush`/`close` are bounded and return booleans; inspect counters separately for dropped/failed writes. Do not call flush/close per request. The safe diagnostic hook receives only fixed codes; exceptions in it are swallowed, and its invocation stays on the worker. Use one destination per worker process; provision permissions and retention externally.
