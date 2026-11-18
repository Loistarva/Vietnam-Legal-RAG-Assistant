"""Tests for the router holdout candidate loader and evaluation."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from agent.router.rule_router import Action, Route, RouteDecision, RuleRouter
from scripts.smoke_rule_router import (
    DEFAULT_HOLDOUT,
    evaluate_router_holdout,
    read_router_holdout,
    run,
)


class RouterHoldoutLoaderTests(unittest.TestCase):
    def test_freeze_mode_skips_holdout_and_passes_dev_and_negative_gates(self):
        with patch.object(sys, "argv", ["smoke_rule_router.py", "--skip-holdout"]):
            report, success = run()
        self.assertTrue(success)
        self.assertIn("skipped (pre-freeze mode)", report)
        self.assertIn("negative_26_route_and_router_action_match | PASS", report)
        self.assertIn("no_legal_query_to_NON_LEGAL_or_GENERAL_CHAT | PASS", report)
        self.assertNotIn("holdout_candidate_route_action_match", report)

    def test_repository_holdout_candidate_matches_current_labels(self):
        rows, error = read_router_holdout(DEFAULT_HOLDOUT)
        self.assertIsNone(error)
        self.assertEqual(len(rows), 40)
        router = RuleRouter()
        decisions = [router.route(row["query"], query_id=row["id"]) for row in rows]
        result = evaluate_router_holdout(rows, decisions, min_accuracy=1.0)
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

    def test_independent_holdout_passes_at_ninety_percent_with_zero_safety_violations(self):
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
                route=Route.LEGAL_HNGD if idx < 27 else Route.LEGAL_SCOPE_UNCERTAIN,
                action=Action.LEGAL_RETRIEVAL,
                route_reason="HNGD_DOMAIN_MATCH" if idx < 27 else "LEGAL_SCOPE_UNCERTAIN",
            )
            for idx, row in enumerate(rows)
        ]
        result = evaluate_router_holdout(rows, decisions)
        self.assertTrue(result["safety_pass"])
        self.assertTrue(result["classification_pass"])
        self.assertAlmostEqual(result["accuracy"], 0.90)
        self.assertEqual(result["matched"], 27)
        self.assertEqual(result["total"], 30)

        strict_regression = evaluate_router_holdout(rows, decisions, min_accuracy=1.0)
        self.assertFalse(strict_regression["classification_pass"])

    def test_independent_holdout_fails_below_ninety_percent(self):
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
                route=Route.LEGAL_HNGD if idx < 26 else Route.LEGAL_SCOPE_UNCERTAIN,
                action=Action.LEGAL_RETRIEVAL,
                route_reason="HNGD_DOMAIN_MATCH" if idx < 26 else "LEGAL_SCOPE_UNCERTAIN",
            )
            for idx, row in enumerate(rows)
        ]
        result = evaluate_router_holdout(rows, decisions)
        self.assertTrue(result["safety_pass"])
        self.assertFalse(result["classification_pass"])
        self.assertAlmostEqual(result["accuracy"], 26 / 30)

    def test_independent_holdout_fails_with_high_accuracy_if_safety_violation_exists(self):
        rows = [
            {
                "id": f"HOLDOUT_{index:03d}",
                "query": f"legal query {index}",
                "expected_route": Route.LEGAL_HNGD.value,
                "expected_action": Action.LEGAL_RETRIEVAL.value,
                "category": "hngd",
            }
            for index in range(36)
        ]
        decisions = [
            RouteDecision(
                query_id=row["id"],
                route=Route.LEGAL_HNGD if idx < 35 else Route.NON_LEGAL,
                action=Action.LEGAL_RETRIEVAL if idx < 35 else Action.GENERAL_CHAT,
                route_reason="HNGD_DOMAIN_MATCH" if idx < 35 else "NON_LEGAL_NO_LEGAL_INTENT",
            )
            for idx, row in enumerate(rows)
        ]
        result = evaluate_router_holdout(rows, decisions)
        self.assertAlmostEqual(result["accuracy"], 35 / 36)
        self.assertFalse(result["safety_pass"])
        self.assertFalse(result["classification_pass"])
        self.assertEqual(result["legal_to_general"], ["HOLDOUT_035"])

    def test_run_uses_strict_threshold_for_regression_and_ninety_percent_for_independent(self):
        with patch.object(
            sys,
            "argv",
            ["smoke_rule_router.py", "--holdout", "evaluation/router_holdout/router_holdout_week10_v6.jsonl"],
        ):
            report_v6, success_v6 = run()
        self.assertTrue(success_v6, report_v6)
        self.assertIn("34/36 (94.4%, min gate 90%)", report_v6)
        self.assertIn("holdout_candidate_route_action_match | PASS", report_v6)

        with patch.object(
            sys,
            "argv",
            ["smoke_rule_router.py", "--holdout", "evaluation/router_holdout/router_holdout_week10_v5.jsonl"],
        ):
            report_v5, success_v5 = run()
        self.assertTrue(success_v5, report_v5)
        self.assertIn("36/36 (100.0%, min gate 100%)", report_v5)
