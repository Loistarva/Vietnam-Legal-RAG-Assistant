import pytest

from monitoring.api_event_adapter import APIEventAdapter
from monitoring.structured_logger import StructuredLogger
from schemas.models import LogEvent


class Collector:
    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(event)


@pytest.mark.parametrize("status,kind", [(401, "auth_rejected"), (403, "auth_rejected"),
                                         (422, "request_validation_error")])
def test_fake_api_rejection_harness(status, kind):
    sink = Collector()
    adapter = APIEventAdapter(sink, "s11-q1")
    if status in (401, 403):
        adapter.auth_rejected(status)
    else:
        adapter.request_validation_error(status)
    e = sink.events[0]
    assert e.event_type == kind and e.query_id == "s11-q1"
    assert e.masked_metadata == {"http_status": status}
    assert e.error_code == ("AUTH_REQUIRED" if status in (401, 403) else "INVALID_REQUEST")


def test_adapter_sanitizes_even_before_an_alternate_sink():
    sink = Collector()
    adapter = APIEventAdapter(sink, "s11-q1")
    adapter.event("probe", "ok", request_id="s11.person@example.test", reason="Call 0900000000",
                  Authorization="Bearer S11_FAKE_TOKEN", headers={"X-API-Key": "secret"}, query="private")
    e = sink.events[0]
    assert e.masked_metadata == {"request_id": "[EMAIL]", "reason": "Call [PHONE]"}


def test_one_query_chain_and_jsonl_roundtrip(tmp_path):
    path = tmp_path / "request.jsonl"
    with StructuredLogger(path) as logger:
        adapter = APIEventAdapter(logger, "s11-q1")
        adapter.request_start(request_id="request-1")
        for stage in ["router", "retrieval", "llm", "citation", "gate"]:
            adapter.event("stage_complete", "ok", stage=stage, duration_ms=1.25)
        adapter.response_complete("SUCCESS", duration_ms=9.5, grounding_status="PASS")
        assert logger.flush()
    events = [LogEvent.model_validate_json(line) for line in path.read_text("utf8").splitlines()]
    assert len(events) == 7 and {e.query_id for e in events} == {"s11-q1"}
    assert len({e.event_id for e in events}) == len(events)
    assert events[-1].event_type == "response_complete"


def test_broken_sink_does_not_change_fake_pipeline_result():
    class Broken:
        def emit(self, _):
            raise OSError("sensitive message")
    adapter = APIEventAdapter(Broken(), "s11-q1")
    adapter.request_start()
    result = {"status": "SUCCESS", "answer": "synthetic verified fixture"}
    adapter.response_complete(result["status"])
    assert result["status"] == "SUCCESS" and adapter.failures == 2
