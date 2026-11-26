import json
import threading
from copy import deepcopy

from monitoring.pii_masker import PIIMasker
from monitoring.structured_logger import StructuredLogger
from schemas.models import LogEvent


def event(query_id="s11-q1", **metadata):
    return LogEvent(event_id="s11-event", query_id=query_id, stage="api", event_type="request_start",
                    timestamp="2026-11-22T00:00:00Z", status="ok", masked_metadata=metadata)


def test_jsonl_schema_privacy_and_input_immutability(tmp_path):
    path = tmp_path / "events.jsonl"
    raw = event(request_id="s11.person@example.test", reason="Call 0900000000; S11_OPAQUE_TEST_KEY",
                Authorization="secret", query="raw query", prompt="raw prompt", token_input=10)
    before = deepcopy(raw.model_dump())
    with StructuredLogger(path, masker=PIIMasker(secret_values=["S11_OPAQUE_TEST_KEY"])) as logger:
        logger.emit(raw)
        assert logger.flush()
    text = path.read_text("utf8")
    for value in ["s11.person@example.test", "0900000000", "S11_OPAQUE_TEST_KEY", "raw query", "raw prompt", "Authorization"]:
        assert value not in text
    parsed = LogEvent.model_validate_json(text)
    assert parsed.query_id == "s11-q1" and parsed.masked_metadata["token_input"] == 10
    assert raw.model_dump() == before


def test_sensitive_correlation_ids_stable_without_collapsing_distinct_requests(tmp_path):
    path = tmp_path / "events.jsonl"
    with StructuredLogger(path) as logger:
        for query_id in ["first@example.test", "first@example.test", "other@example.test"]:
            logger.emit(event(query_id))
        assert logger.flush()
    ids = [json.loads(line)["query_id"] for line in path.read_text("utf8").splitlines()]
    assert ids[0] == ids[1] and ids[0] != ids[2]
    assert all(v.startswith("redacted-") for v in ids)


def test_sink_and_diagnostic_failures_do_not_escape_or_log_exception_text():
    codes = []
    class Broken:
        def emit(self, _):
            raise OSError("S11_OPAQUE_TEST_KEY should never be echoed")
    def diagnostic(code):
        codes.append(code)
        raise RuntimeError("also broken")
    with StructuredLogger(sink=Broken(), diagnostic=diagnostic) as logger:
        logger.emit(event())
        assert logger.flush()
        assert logger.stats["SINK_WRITE_FAILED"] == 1
    assert codes == ["SINK_WRITE_FAILED"]


def test_bounded_queue_slow_sink_and_explicit_shutdown_timeout():
    entered, release = threading.Event(), threading.Event()
    class Slow:
        def emit(self, _):
            entered.set()
            assert release.wait(3)
    logger = StructuredLogger(sink=Slow(), max_queue=1)
    try:
        logger.emit(event())
        assert entered.wait(1)
        logger.emit(event())
        logger.emit(event())
        assert logger.stats["QUEUE_FULL"] == 1
        assert logger.flush(timeout=0) is False
        assert logger.close(timeout=0) is False
        assert logger.stats["SHUTDOWN_TIMEOUT"] == 1
    finally:
        release.set()
        assert logger.close(timeout=2)
    logger.emit(event())
    assert logger.stats["LOGGER_CLOSED"] == 1


def test_invalid_events_are_nonfatal(tmp_path):
    with StructuredLogger(tmp_path / "events.jsonl") as logger:
        logger.emit({"not": "a LogEvent"})
        assert logger.stats["INVALID_EVENT"] == 1


def test_debug_is_explicit_and_still_redacted(tmp_path):
    path = tmp_path / "events.jsonl"
    with StructuredLogger(path, masker=PIIMasker(debug=True)) as logger:
        logger.emit(event(query="Contact s11.person@example.test", api_key="secret"))
        assert logger.flush()
    data = json.loads(path.read_text("utf8"))
    assert data["masked_metadata"] == {"query": "Contact [EMAIL]"}
