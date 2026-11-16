"""OpenAPI snapshot = app (Sprint 10 D5.6). A failing test means the API contract changed:
run ``python -m api.export_openapi``, review the diff and tell Dev 2."""
from __future__ import annotations

import json

from api.export_openapi import SNAPSHOT, build_spec, render


def test_snapshot_matches_app():
    assert SNAPSHOT.exists(), "Thiếu api/openapi.json: chạy python -m api.export_openapi"
    assert SNAPSHOT.read_text(encoding="utf-8") == render(build_spec()), (
        "api/openapi.json đã cũ: chạy python -m api.export_openapi rồi review thay đổi contract")


def test_paths_methods_and_security():
    spec = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert set(spec["paths"]) == {"/api/v1/ask", "/api/v1/ask/stream", "/api/v1/health"}
    assert spec["components"]["securitySchemes"]["APIKeyHeader"] == {
        "type": "apiKey", "in": "header", "name": "X-API-Key",
        "description": "API key cấp cho client (biến môi trường LEGAL_RAG_API_KEYS ở server)."}
    ask = spec["paths"]["/api/v1/ask"]["post"]
    assert ask["security"] == [{"APIKeyHeader": []}]
    assert "security" not in spec["paths"]["/api/v1/health"]["get"]
    assert {"200", "401", "403", "422", "500", "504"} <= set(ask["responses"])


def test_request_and_response_use_shared_contract_models():
    spec = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    ask = spec["paths"]["/api/v1/ask"]["post"]
    assert ask["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/AskRequest")
    assert ask["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/AskResponse")
    schemas = spec["components"]["schemas"]
    response = schemas["AskResponse"]["properties"]
    for field in ("query_id", "as_of_date", "as_of_date_source", "status", "route", "answer", "clarification",
                  "abstention_message", "citations", "evidence", "grounding_status", "disclaimer", "timings",
                  "error_code", "error"):
        assert field in response
    assert {"as_of_date", "as_of_date_source"} <= set(schemas["AskResponse"]["required"])
    assert "total_ms" in schemas["AskTimings"]["properties"]
    assert set(schemas["ErrorDetail"]["properties"]) == {"message", "retryable"}
    request = schemas["AskRequest"]["properties"]
    assert set(request) == {"schema_version", "query", "as_of_date", "session_id", "request_id", "query_id"}
    assert schemas["ApiError"]["properties"]["error_code"]
