"""SRS 5.5 protocol signatures and dependency injection through AskService."""
import builtins
from inspect import Parameter, signature
from unittest.mock import Mock

import pytest

from generation.prompt_builder import build_controlled_rag_prompt
from model_gateway.llm_gateway import QwenGateway
from monitoring.structured_logger import StructuredLogger
from orchestration import interfaces
from orchestration.ask_service import AskService, RuleRouterAdapter
from orchestration.events import ListEventSink
from orchestration.fakes import FixtureSource, ScriptedGenerator
from orchestration.rag_pipeline import (
    LivePipelineSource,
    PrecomputedRerankedSource,
    RAGPipeline,
    RunVersions,
    apply_grounding_gate,
)
from reranking.confidence import load_confidence_config
from reranking.context_builder import build_context_payload
from schemas.models import AskRequest, GroundingResult, RouteDecision

pytestmark = pytest.mark.req("IR4.1-AC1")


@pytest.mark.parametrize(("protocol", "implementation"), [
    (interfaces.Router.route, RuleRouterAdapter.route),
    (interfaces.RetrievalSource.fetch, LivePipelineSource.fetch),
    (interfaces.RetrievalSource.fetch, PrecomputedRerankedSource.fetch),
    (interfaces.ContextAggregator.__call__, build_context_payload),
    (interfaces.PromptBuilder.__call__, build_controlled_rag_prompt),
    (interfaces.ModelGateway.generate, QwenGateway.generate),
    (interfaces.GroundingGate.__call__, apply_grounding_gate),
    (interfaces.EventSink.emit, StructuredLogger.emit),
    (interfaces.EventSink.emit, ListEventSink.emit),
], ids=lambda fn: fn.__qualname__)
def test_protocol_signature(protocol, implementation):
    expected = dict(signature(protocol).parameters)
    actual = dict(signature(implementation).parameters)
    expected.pop("self")
    actual.pop("self", None)
    # Positional-only Protocol parameters are matched by position, whatever the implementation calls them.
    positional = [p for p in actual.values() if p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)]
    for index, name in enumerate([n for n, p in expected.items() if p.kind is Parameter.POSITIONAL_ONLY]):
        assert index < len(positional), f"Missing positional parameter {name}"
        expected.pop(name)
        actual.pop(positional[index].name)
    assert expected.keys() <= actual.keys(), f"Missing parameters: {expected.keys() - actual.keys()}"
    for name, parameter in expected.items():
        compatible = {parameter.kind}
        if parameter.kind in (Parameter.KEYWORD_ONLY, Parameter.POSITIONAL_ONLY):
            compatible.add(Parameter.POSITIONAL_OR_KEYWORD)
        assert actual[name].kind in compatible, name
        if parameter.default is not Parameter.empty:
            assert actual[name].default is not Parameter.empty, name
    for name in actual.keys() - expected.keys():
        assert actual[name].default is not Parameter.empty, name


class FakeRouter:
    def route(self, *, query, query_id, as_of_date):
        return RouteDecision(route="LEGAL_IN_SCOPE", action="LEGAL_RETRIEVAL", reason_code="TEST_LEGAL",
                             explanation="Fixture route", policy_version="test", query_id=query_id,
                             as_of_date=as_of_date)


@pytest.fixture
def pipeline_options():
    confidence = load_confidence_config()
    versions = RunVersions(corpus_version="test", retrieval_config_version="test",
                           threshold_config_version=confidence.threshold_config_version)
    return dict(versions=versions, confidence=confidence, rerank_top_k=5, max_context_chars=6000,
                run_mode="C_production_rag")


def test_ask_service_with_five_fakes(monkeypatch, pipeline_options):
    live_modules = ("agent.router", "reranking.pipeline", "embedding.vector_store", "model_gateway.llm_gateway",
                    "elasticsearch", "qdrant_client", "ollama")
    original_import = builtins.__import__

    def guard_import(name, *args, **kwargs):
        if any(name == module or name.startswith(module + ".") for module in live_modules):
            pytest.fail(f"Fake service imported {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard_import)
    source, gateway, sink = FixtureSource(), ScriptedGenerator(), ListEventSink()

    def accept_citations(payload, citations, *, evidence_indices, invalid_indices):
        assert [item.evidence_index for item in citations] == evidence_indices
        assert payload.query_id == "q-fakes" and not invalid_indices
        return GroundingResult(status="PASS", citations=citations)

    validator = Mock(side_effect=accept_citations)
    pipeline = RAGPipeline(source, gateway, validator=validator, **pipeline_options)
    service = AskService(FakeRouter(), pipeline, sink=sink)
    response = service.run(AskRequest(query="Điều kiện kết hôn là gì?", query_id="q-fakes")).response
    assert (response.status, response.grounding_status) == ("SUCCESS", "PASS")
    assert source.calls == gateway.calls == 1
    validator.assert_called_once()
    assert {event.query_id for event in sink.events} == {response.query_id}


def test_validator_conflicts_with_custom_gate(pipeline_options):
    with pytest.raises(ValueError, match="validator"):
        RAGPipeline(FixtureSource(), ScriptedGenerator(), validator=Mock(), gate=Mock(), **pipeline_options)
