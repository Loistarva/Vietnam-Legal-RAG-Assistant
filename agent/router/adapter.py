"""Public Router boundary for API/CLI consumers (SRS FR1.3)."""
from __future__ import annotations

from agent.router.rule_router import RuleRouter
from schemas.models import RouteDecision


class RuleRouterAdapter:
    """Expose the canonical decision without duplicating internal route mapping."""

    def __init__(self, router: RuleRouter | None = None):
        self.router = router if router is not None else RuleRouter()

    def route(self, *, query: str, query_id: str, as_of_date: str) -> RouteDecision:
        decision = self.router.route(
            query, query_id=query_id, as_of_date=as_of_date, source="ask_service",
        )
        return decision.to_canonical()
