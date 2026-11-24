"""Typed interfaces between modules (SRS 2.1.2, 5.5 "Interface giữa phân hệ"; Sprint 11 D5.1, đợt 0).

One ``typing.Protocol`` per row of the SRS 5.5 table. The signatures are the approved ones;
the existing modules satisfy them without a rewrite:

=========================  ==========================================================  ===============
Protocol                   Implementation on ``testing``                               Owner
=========================  ==========================================================  ===============
``Router``                 ``orchestration.ask_service.RuleRouterAdapter``             Dev 4 (adapter: Dev 5)
                           (wraps ``agent.router.rule_router.RuleRouter``, SRS 5.3.3)
``RetrievalSource``        ``rag_pipeline.LivePipelineSource``,                        Dev 4 / Dev 5
                           ``rag_pipeline.PrecomputedRerankedSource``
``ContextAggregator``      ``reranking.context_builder.build_context_payload``         Dev 5
``PromptBuilder``          ``generation.prompt_builder.build_controlled_rag_prompt``   Dev 3
``ModelGateway``           ``model_gateway.llm_gateway.QwenGateway``                   Dev 3
``GroundingGate``          ``orchestration.rag_pipeline.apply_grounding_gate``         Dev 5 (validator: Dev 1)
``EventSink``              ``monitoring.structured_logger.StructuredLogger``,          Dev 1 / Dev 5
                           ``orchestration.events.*Sink``
=========================  ==========================================================  ===============

``rag_pipeline`` narrows two of them for its own needs: ``CandidateSource`` adds the ``name``
label written to the trace, and ``Generator`` adds ``config`` (model metadata) and the optional
``max_evidence_index`` bound that ``QwenGateway.generate`` takes in production mode. Both stay
compatible with the Protocols here.

Only contract types from ``schemas.models`` cross these interfaces. Nothing here imports a
module implementation, so tests can pass fakes for every row (IR4.1-AC1).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from schemas.models import ContextPayload, GroundingResult, LLMResponse, LogEvent, RouteDecision


@runtime_checkable
class Router(Protocol):
    """Router -> Orchestrator. Returns the contract ``RouteDecision`` (never the router's inner class)."""

    def route(self, *, query: str, query_id: str, as_of_date: str) -> RouteDecision: ...


@runtime_checkable
class RetrievalSource(Protocol):
    """Retrieval -> Orchestrator. The reranked envelope ``{query_id, results: [...]}``, sorted by rank.

    Becomes ``RetrievalBundle`` once its ``week10_v1.1`` fields are in the contract (SRS 5.6)."""

    def fetch(self, *, query_id: str, query: str, as_of_date: str) -> Mapping[str, Any]: ...


class ContextAggregator(Protocol):
    """Context Aggregator -> Orchestrator. Evidence ``[1..n]`` plus a trace of what each item carries."""

    def __call__(self, rows: Sequence[Mapping[str, Any]], *, query_id: str, query: str, as_of_date: str,
                 as_of_date_source: str, max_context_chars: int,
                 max_items: int) -> tuple[ContextPayload, dict[str, Any]]: ...


class PromptBuilder(Protocol):
    """Prompt Builder -> Orchestrator. The exact prompt text the Gate later checks against.

    Positional-only, as the pipeline calls it: fakes may name the parameter differently."""

    def __call__(self, context_payload: ContextPayload, /) -> str: ...


@runtime_checkable
class ModelGateway(Protocol):
    """Orchestrator -> Model Gateway. Typed errors (``LLM_TIMEOUT``, ...) are raised, not returned."""

    def generate(self, prompt: str, query_id: str, run_mode: str, prompt_version: str,
                 structured_output: bool = False, schema: dict[str, Any] | None = None) -> LLMResponse: ...


class GroundingGate(Protocol):
    """Gate -> Orchestrator. Uses ``grounding/citation_validator.py``; only PASS lets the answer out."""

    def __call__(self, payload: ContextPayload, llm: LLMResponse, /) -> GroundingResult: ...


@runtime_checkable
class EventSink(Protocol):
    """Every module -> Logger. Must not raise to the caller (FR9.10)."""

    def emit(self, event: LogEvent) -> None: ...


__all__ = [
    "ContextAggregator", "EventSink", "GroundingGate", "ModelGateway", "PromptBuilder", "RetrievalSource", "Router",
]
