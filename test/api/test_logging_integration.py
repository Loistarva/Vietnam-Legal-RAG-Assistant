"""Stage events through the API and CLI with the mock pipeline and production logger."""
import json

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import ApiSettings
from monitoring.structured_logger import StructuredLogger
from orchestration.events import NullEventSink
from orchestration.wiring import ServiceSettings, build_ask_service, build_event_sink
from schemas.models import LogEvent
from scripts.run_rag_cli import main as run_cli

API_KEY = "first-configured-test-key"
SECOND_KEY = "second-configured-test-key"
WRONG_KEY = "unconfigured-test-key"
AUTH = {"X-API-Key": API_KEY}
ASK = "/api/v1/ask"
LEGAL = {"query": "Nam phải đủ bao nhiêu tuổi để kết hôn?", "as_of_date": "2026-01-01"}
STAGES = ["api", "router", "retrieval", "rerank", "context", "llm", "citation", "gate", "response"]


def logging_app(path):
    return create_app(settings=ApiSettings(api_keys=f" {API_KEY} , , {SECOND_KEY} "),
                      service_settings=ServiceSettings(mode="mock", event_log=str(path)))


@pytest.fixture
def logged_api(tmp_path):
    path = tmp_path / "api.jsonl"
    app = logging_app(path)
    with TestClient(app) as client:
        yield client, app.state.ask_service.sink, path


def read_log(logger, path):
    assert logger.flush()
    return path.read_text(encoding="utf-8")


@pytest.mark.req("FR9.9-AC1")
def test_gate_pass_logs_correlated_stages_in_order(logged_api):
    client, logger, path = logged_api
    response = client.post(ASK, headers=AUTH, json=LEGAL)
    assert response.status_code == 200
    assert response.json()["grounding_status"] == "PASS"
    required = {"schema_version", "event_id", "query_id", "stage", "event_type", "timestamp", "status", "masked_metadata"}
    stages = []
    for line in read_log(logger, path).splitlines():
        row = json.loads(line)
        assert required <= row.keys()
        event = LogEvent.model_validate(row)
        assert event.query_id == response.headers["X-Query-ID"]
        stages.append(event.stage)
    assert [stage for stage in dict.fromkeys(stages) if stage in STAGES] == STAGES


@pytest.mark.req("FR9.9-AC2")
def test_greeting_logs_only_short_route(logged_api):
    client, logger, path = logged_api
    response = client.post(ASK, headers=AUTH, json={"query": "Xin chào!"})
    assert response.status_code == 200
    assert response.json()["route"] == "NON_LEGAL"
    assert {json.loads(line)["stage"] for line in read_log(logger, path).splitlines()} == {"api", "router", "response"}


@pytest.mark.req("IR2.5-AC2")
@pytest.mark.parametrize("headers", [{}, {"X-API-Key": WRONG_KEY}], ids=["missing", "wrong"])
def test_auth_rejection_logs_status_without_keys(logged_api, headers):
    client, logger, path = logged_api
    response = client.post(ASK, headers=headers, json=LEGAL)
    assert response.status_code == 401
    raw = read_log(logger, path)
    for key in (API_KEY, SECOND_KEY, WRONG_KEY):
        assert key not in raw
        assert key not in response.text
    events = [LogEvent.model_validate_json(line) for line in raw.splitlines()]
    assert any(e.stage == "api" and e.query_id == response.headers["X-Query-ID"]
               and e.error_code == "AUTH_REQUIRED" and e.masked_metadata.get("http_status") == 401 for e in events)


@pytest.mark.req("NFR3.4")
def test_query_contact_details_do_not_reach_log(logged_api):
    client, logger, path = logged_api
    email, phone = "a.b@example.com", "0912345678"
    response = client.post(ASK, headers=AUTH, json={"query": f"{LEGAL['query']} Liên hệ {email}, {phone}."})
    assert response.status_code == 200
    raw = read_log(logger, path)
    assert response.headers["X-Query-ID"] in raw
    assert email not in raw and phone not in raw


@pytest.mark.req("FR9.10-AC1")
def test_sink_failures_preserve_http_response(logged_api):
    client, working, path = logged_api
    baseline = client.post(ASK, headers=AUTH, json=LEGAL)
    assert read_log(working, path)

    class BrokenSink:
        def emit(self, event):
            raise OSError("simulated sink failure")

    with StructuredLogger(sink=BrokenSink()) as broken:
        service = build_ask_service(ServiceSettings(mode="mock"), sink=broken)
        with TestClient(create_app(settings=ApiSettings(api_keys=API_KEY), service=service)) as other:
            response = other.post(ASK, headers=AUTH, json=LEGAL)
        assert broken.flush()
        assert broken.stats["SINK_WRITE_FAILED"] == broken.stats["enqueued"] > 0
        # The caller still owns the injected logger after the app shuts down.
        event = LogEvent.model_validate_json(read_log(working, path).splitlines()[0])
        broken.emit(event)
        assert broken.flush()
        assert "LOGGER_CLOSED" not in broken.stats

    assert baseline.status_code == response.status_code == 200
    expected, actual = baseline.json(), response.json()
    for field in ("query_id", "timings"):
        expected.pop(field)
        actual.pop(field)
    assert actual == expected


@pytest.mark.req("FR9.9-AC1")
def test_lifespan_masks_configured_keys_and_closes_logger(tmp_path):
    path = tmp_path / "lifespan.jsonl"
    app = logging_app(path)
    with TestClient(app) as client:
        logger = app.state.ask_service.sink
        assert isinstance(logger, StructuredLogger)
        response = client.post(ASK, headers=AUTH, json={**LEGAL, "request_id": f"{API_KEY}/{SECOND_KEY}"})
        assert response.status_code == 200
    raw = read_log(logger, path)
    assert API_KEY not in raw and SECOND_KEY not in raw
    events = [LogEvent.model_validate_json(line) for line in raw.splitlines()]
    assert events[0].masked_metadata["request_id"] == "[SECRET]/[SECRET]"
    assert events[-1].masked_metadata["http_status"] == 200
    logger.emit(events[0])
    assert logger.stats["LOGGER_CLOSED"] == 1


@pytest.mark.req("NFR3.4")
def test_wiring_selects_sink_and_configures_masker(tmp_path):
    assert isinstance(build_event_sink(ServiceSettings()), NullEventSink)
    logger = build_event_sink(ServiceSettings(event_log=str(tmp_path / "wired.jsonl")), secret_values=[API_KEY])
    assert isinstance(logger, StructuredLogger)
    with logger:
        assert logger.masker.mask_text(API_KEY) == "[SECRET]"


@pytest.mark.req("NFR3.4")
def test_cli_drains_masked_events_before_return(tmp_path, monkeypatch):
    path = tmp_path / "cli.jsonl"
    monkeypatch.setenv("LEGAL_RAG_API_KEYS", API_KEY)
    monkeypatch.setenv("LEGAL_RAG_EVENT_LOG", str(path))
    assert run_cli(["--mock", "--query-id", API_KEY, LEGAL["query"]]) == 0
    raw = path.read_text(encoding="utf-8")
    assert API_KEY not in raw
    events = [LogEvent.model_validate_json(line) for line in raw.splitlines()]
    assert events[-1].stage == "response"
    assert len({event.query_id for event in events}) == 1
