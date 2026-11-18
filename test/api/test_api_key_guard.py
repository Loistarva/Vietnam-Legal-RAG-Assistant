"""API Key Guard and request safety (Sprint 10 D5.4)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.main import create_app
from api.security.api_key_guard import ApiKeyGuard, AuthError
from api.settings import ApiSettings

ROOT = Path(__file__).resolve().parents[2]
API_KEY = "test-key-0123456789abcdef"  # same as test/api/conftest.py
BODY = {"query": "Nam phải đủ bao nhiêu tuổi để kết hôn?"}


def test_missing_key_is_401_before_pipeline(api):
    response = api.client.post("/api/v1/ask", json=BODY)
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"
    assert response.headers["WWW-Authenticate"] == "ApiKey"
    assert (api.source.calls, api.generator.calls) == (0, 0)


@pytest.mark.parametrize("key", ["wrong-key-0123456789abc", "", "   ", API_KEY[:-1]])
def test_wrong_or_empty_key_is_rejected_before_pipeline(api, key):
    response = api.client.post("/api/v1/ask", json=BODY, headers={"X-API-Key": key})
    assert response.status_code in (401, 403)
    assert response.json()["error_code"] == "AUTH_REQUIRED"
    assert api.source.calls == 0


def test_stream_route_is_guarded_too(api):
    assert api.client.post("/api/v1/ask/stream", json=BODY).status_code == 401


def test_auth_check_runs_before_body_validation(api):
    """An unauthenticated client learns nothing about the body schema."""
    assert api.client.post("/api/v1/ask", json={"bad": 1}).status_code == 401


def test_key_never_appears_in_response_or_events(api):
    for key in (API_KEY, "wrong-key-0123456789abc"):
        response = api.client.post("/api/v1/ask", json=BODY, headers={"X-API-Key": key})
        assert key not in response.text and key not in json.dumps(dict(response.headers))
    dumped = json.dumps([e.model_dump(mode="json") for e in api.sink.events])
    assert API_KEY not in dumped and "wrong-key" not in dumped


def test_several_keys_and_rotation():
    guard = ApiKeyGuard.from_value(f"{API_KEY}, second-key-0123456789")
    guard.check(API_KEY)
    guard.check("second-key-0123456789")
    with pytest.raises(AuthError) as err:
        guard.check("third-key-0123456789x")
    assert err.value.status_code == 403
    assert API_KEY not in repr(guard)


@pytest.mark.parametrize("value", [None, "", " , ", "short"])
def test_app_refuses_to_start_without_a_usable_key(value):
    with pytest.raises(ValueError):
        create_app(settings=ApiSettings(api_keys=value or ""))


def test_settings_repr_hides_keys():
    assert API_KEY not in repr(ApiSettings(api_keys=API_KEY))


def test_settings_from_env():
    settings = ApiSettings.from_env({"LEGAL_RAG_API_KEYS": API_KEY, "LEGAL_RAG_ENV": "production",
                                     "LEGAL_RAG_CORS_ORIGINS": "http://localhost:8501, https://ui.example",
                                     "LEGAL_RAG_MAX_QUERY_CHARS": "500"})
    assert settings.env == "production" and settings.max_query_chars == 500
    assert settings.cors_origins == ("http://localhost:8501", "https://ui.example")


def test_wildcard_cors_refused_in_production():
    with pytest.raises(ValueError):
        ApiSettings(api_keys=API_KEY, env="production", cors_origins=("*",))


def test_cors_allows_only_configured_origin(make_api):
    api = make_api(cors_origins=("http://localhost:8501",))
    ok = api.client.options("/api/v1/ask", headers={"Origin": "http://localhost:8501",
                                                    "Access-Control-Request-Method": "POST",
                                                    "Access-Control-Request-Headers": "X-API-Key"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:8501"
    bad = api.client.options("/api/v1/ask", headers={"Origin": "http://evil.example",
                                                     "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_no_cors_headers_by_default(api):
    response = api.client.get("/api/v1/health", headers={"Origin": "http://localhost:8501"})
    assert "access-control-allow-origin" not in response.headers


def test_env_example_has_no_real_secret():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "LEGAL_RAG_API_KEYS=" in text
    line = next(line for line in text.splitlines() if line.startswith("LEGAL_RAG_API_KEYS="))
    assert line.split("=", 1)[1].strip().startswith("<")


def test_dotenv_is_gitignored():
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()
