"""Test client on the real app with the mock pipeline (no ES/Qdrant/Ollama)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import ApiSettings
from orchestration.ask_service import AskService, RuleRouterAdapter
from orchestration.events import ListEventSink
from orchestration.fakes import FixtureSource, ScriptedGenerator, build_mock_pipeline

API_KEY = "test-key-0123456789abcdef"
AUTH = {"X-API-Key": API_KEY}


@dataclass
class ApiHarness:
    client: TestClient
    sink: ListEventSink
    source: FixtureSource
    generator: ScriptedGenerator
    key: str = API_KEY
    auth: dict | None = None


def make_harness(**settings_kwargs) -> ApiHarness:
    sink, source, generator = ListEventSink(), FixtureSource(), ScriptedGenerator()
    service = AskService(RuleRouterAdapter(), build_mock_pipeline(source=source, generator=generator), sink=sink,
                         today=lambda: date(2026, 11, 16))
    app = create_app(settings=ApiSettings(api_keys=API_KEY, **settings_kwargs), service=service)
    return ApiHarness(TestClient(app), sink, source, generator, auth=dict(AUTH))


@pytest.fixture
def api() -> ApiHarness:
    return make_harness()


@pytest.fixture
def make_api():
    """Factory for a harness with other ApiSettings (``make_api(max_query_chars=50)``)."""
    return make_harness
