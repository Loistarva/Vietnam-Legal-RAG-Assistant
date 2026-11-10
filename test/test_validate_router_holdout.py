"""Tests for the owner-authored independent router holdout validator."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_router_holdout import validate_holdout


ROUTE_ACTIONS = (
    ("LEGAL_HNGD", "LEGAL_RETRIEVAL"),
    ("LEGAL_OUT_OF_SCOPE", "POLICY_ABSTENTION"),
    ("MIXED_LEGAL_SCOPE", "POLICY_ABSTENTION"),
    ("NON_LEGAL", "GENERAL_CHAT"),
    ("LEGAL_SCOPE_UNCERTAIN", "LEGAL_RETRIEVAL"),
)


def valid_rows() -> list[dict[str, str]]:
    rows = []
    for index in range(36):
        route, action = ROUTE_ACTIONS[index % len(ROUTE_ACTIONS)]
        rows.append({
            "id": f"R4H_{index + 1:03d}",
            "query": f"Fresh authored query number {index + 1}",
            "expected_route": route,
            "expected_action": action,
            "category": f"category_{index % 5}",
        })
    return rows


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


class ValidateRouterHoldoutTests(unittest.TestCase):
    def test_accepts_36_records_with_all_five_route_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdout.jsonl"
            write_jsonl(path, valid_rows())
            result = validate_holdout(path)
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["rows"]), 36)
        self.assertEqual(len(result["route_counts"]), 5)

    def test_rejects_duplicate_ids_and_normalized_queries(self):
        rows = valid_rows()
        rows[1]["id"] = rows[0]["id"]
        rows[1]["query"] = "  FRESH authored QUERY number 1  "
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdout.jsonl"
            write_jsonl(path, rows)
            result = validate_holdout(path)
        self.assertTrue(any("ID bị trùng" in error for error in result["errors"]))
        self.assertTrue(any("Câu hỏi trùng" in error for error in result["errors"]))

    def test_rejects_inconsistent_route_action_pair(self):
        rows = valid_rows()
        rows[0]["expected_action"] = "GENERAL_CHAT"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdout.jsonl"
            write_jsonl(path, rows)
            result = validate_holdout(path)
        self.assertTrue(any("cặp route/action sai" in error for error in result["errors"]))

    def test_rejects_exact_match_in_comparison_source(self):
        rows = valid_rows()
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            holdout_path = directory_path / "holdout.jsonl"
            comparison_path = directory_path / "existing.jsonl"
            write_jsonl(holdout_path, rows)
            comparison_path.write_text(
                json.dumps({"question": rows[0]["query"]}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            result = validate_holdout(holdout_path, [comparison_path])
        self.assertTrue(any("trùng nguyên văn" in error for error in result["errors"]))

    def test_rejects_missing_route_group_and_out_of_range_count(self):
        rows = [row for row in valid_rows()[:30] if row["expected_route"] != "NON_LEGAL"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdout.jsonl"
            write_jsonl(path, rows)
            result = validate_holdout(path)
        self.assertTrue(any("Số câu phải từ 30 đến 40" in error for error in result["errors"]))
        self.assertTrue(any("chưa có đủ 5 nhóm route" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
