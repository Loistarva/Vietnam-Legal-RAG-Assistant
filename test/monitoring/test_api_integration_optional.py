"""Real FastAPI transport with fake services, once Dev 5 API is present."""
import json

import pytest

from monitoring.pii_masker import PIIMasker
from monitoring.structured_logger import StructuredLogger

API_MAIN = pytest.importorskip("api.main", reason="Dev 5 API is not merged into this baseline")


def make_client(sink):
    from fastapi.testclient import TestClient

    from api.settings import ApiSettings
    from orchestration.ask_service import AskService, RuleRouterAdapter
    from orchestration.fakes import build_mock_pipeline

    service = AskService(RuleRouterAdapter(), build_mock_pipeline(run_mode="C_production_rag"), sink=sink)
    app = API_MAIN.create_app(settings=ApiSettings(api_keys="S11_FAKE_API_KEY_123456"), service=service)
    return TestClient(app)


def test_real_http_rejections_and_success_with_redacted_logger(tmp_path):
    path = tmp_path / "http.jsonl"
    key = "S11_FAKE_API_KEY_123456"
    with StructuredLogger(path, masker=PIIMasker(secret_values=[key])) as logger:
        with make_client(logger) as client:
            unauthorized = client.post("/api/v1/ask", json={})
            assert unauthorized.status_code == 401
            invalid = client.post("/api/v1/ask", json={}, headers={"X-API-Key": key})
            assert invalid.status_code == 422
            response = client.post("/api/v1/ask", headers={"X-API-Key": key}, json={
                "query": "Nam phải đủ bao nhiêu tuổi thì được kết hôn?", "as_of_date": "2026-11-22",
                "query_id": "S11_HTTP_QUERY", "request_id": "s11.person@example.test"})
            assert response.status_code == 200 and response.json()["status"] == "SUCCESS"
            assert response.json()["grounding_status"] == "PASS"
        assert logger.flush()
    text = path.read_text("utf8")
    assert key not in text and "s11.person@example.test" not in text
    assert "Nam phải đủ" not in text
    events = [json.loads(line) for line in text.splitlines()]
    for rejected in [unauthorized, invalid]:
        assert any(e["query_id"] == rejected.json()["query_id"] and e["event_type"] == "request_rejected" for e in events)
    chain = [e for e in events if e["query_id"] == "S11_HTTP_QUERY"]
    assert {"api", "retrieval", "llm", "citation", "gate"} <= {e["stage"] for e in chain}


def test_actual_http_answer_survives_broken_sink():
    class Broken:
        def emit(self, _):
            raise OSError("S11_SYNTHETIC_FAILURE")
    with make_client(Broken()) as client:
        response = client.post("/api/v1/ask", headers={"X-API-Key": "S11_FAKE_API_KEY_123456"},
                               json={"query": "Nam phải đủ bao nhiêu tuổi thì được kết hôn?", "as_of_date": "2026-11-22"})
        assert response.status_code == 200 and response.json()["status"] == "SUCCESS"
