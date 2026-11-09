"""Tests for the router holdout candidate loader and evaluation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent.router.rule_router import Action, Route, RouteDecision, RuleRouter
from scripts.smoke_rule_router import (
    DEFAULT_HOLDOUT,
    evaluate_router_holdout,
    read_router_holdout,
)


class RouterHoldoutLoaderTests(unittest.TestCase):
    def test_repository_holdout_candidate_matches_current_labels(self):
        rows, error = read_router_holdout(DEFAULT_HOLDOUT)
        self.assertIsNone(error)
        self.assertEqual(len(rows), 40)
        router = RuleRouter()
        decisions = [router.route(row["query"], query_id=row["id"]) for row in rows]
        result = evaluate_router_holdout(rows, decisions)
        self.assertTrue(result["safety_pass"], result)
        self.assertTrue(result["classification_pass"], result)

    def test_missing_holdout_is_reported_as_a_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            rows, error = read_router_holdout(Path(directory) / "router_holdout.jsonl")
        self.assertEqual(rows, [])
        self.assertIn("Không tìm thấy holdout candidate", error)

    def test_reads_valid_holdout_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "router_holdout.jsonl"
            records = [
                {
                    "id": "HOLDOUT_001",
                    "query": "Chào bạn",
                    "expected_route": "NON_LEGAL",
                    "expected_action": "GENERAL_CHAT",
                    "category": "non_legal",
                }
            ]
            path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in records),
                encoding="utf-8",
            )
            rows, error = read_router_holdout(path)
        self.assertIsNone(error)
        self.assertEqual(rows, records)

    def test_rejects_duplicate_holdout_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "router_holdout.jsonl"
            record = {
                "id": "HOLDOUT_001",
                "query": "Chào bạn",
                "expected_route": "NON_LEGAL",
                "expected_action": "GENERAL_CHAT",
                "category": "non_legal",
            }
            path.write_text(
                json.dumps(record) + "\n" + json.dumps(record), encoding="utf-8"
            )
            rows, error = read_router_holdout(path)
        self.assertEqual(rows, [])
        self.assertEqual(error, "Holdout có ID trùng")

    def test_safety_pass_is_independent_from_exact_classification(self):
        rows = [
            {
                "id": f"HOLDOUT_{index:03d}",
                "query": f"legal query {index}",
                "expected_route": Route.LEGAL_HNGD.value,
                "expected_action": Action.LEGAL_RETRIEVAL.value,
                "category": "hngd",
            }
            for index in range(30)
        ]
        decisions = [
            RouteDecision(
                query_id=row["id"],
                route=Route.LEGAL_SCOPE_UNCERTAIN,
                action=Action.LEGAL_RETRIEVAL,
                route_reason="LEGAL_SCOPE_UNCERTAIN",
            )
            for row in rows
        ]
        result = evaluate_router_holdout(rows, decisions)
        self.assertTrue(result["safety_pass"])
        self.assertFalse(result["classification_pass"])

    def test_safety_fails_when_legal_case_is_sent_to_general_chat(self):
        rows = [
            {
                "id": f"HOLDOUT_{index:03d}",
                "query": f"legal query {index}",
                "expected_route": Route.LEGAL_HNGD.value,
                "expected_action": Action.LEGAL_RETRIEVAL.value,
                "category": "hngd",
            }
            for index in range(30)
        ]
        decisions = [
            RouteDecision(
                query_id=row["id"],
                route=Route.NON_LEGAL,
                action=Action.GENERAL_CHAT,
                route_reason="NON_LEGAL_NO_LEGAL_INTENT",
            )
            for row in rows
        ]
        result = evaluate_router_holdout(rows, decisions)
        self.assertFalse(result["safety_pass"])
        self.assertFalse(result["classification_pass"])
        self.assertEqual(len(result["legal_to_general"]), 30)
