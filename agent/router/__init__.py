"""Lightweight request routing for the legal assistant."""

from .rule_router import (
    Action,
    FastPathRule,
    Route,
    RouteDecision,
    RouteReason,
    RouterInputError,
    RuleRouter,
)

__all__ = [
    "Action",
    "FastPathRule",
    "Route",
    "RouteDecision",
    "RouteReason",
    "RouterInputError",
    "RuleRouter",
]
