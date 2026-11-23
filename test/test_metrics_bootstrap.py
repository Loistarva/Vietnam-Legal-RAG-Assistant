import json
import tempfile
import unittest
from pathlib import Path

from evaluation.metrics import evaluate


class RetrievalMetricBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.ground_truth_path = self.root / "ground_truth.json"
        self.results_path = self.root / "results.json"
        self.ground_truth_path.write_text(
            json.dumps([
                {
                    "id": "Q1",
                    "gold_context_ids": ["c1"],
                    "gold_context_ids_confirmed": True,
                },
                {
                    "id": "Q2",
                    "gold_context_ids": ["c2"],
                    "gold_context_ids_confirmed": True,
                },
            ]),
            encoding="utf-8",
        )
        self.results_path.write_text(
            json.dumps([
                {
                    "query_id": "Q1",
                    "category": "civil",
                    "retrieved_chunk_ids": ["c1"],
                    "retrieved_parent_clause_ids": ["p1"],
                },
                {
                    "query_id": "Q2",
                    "category": "civil",
                    "retrieved_chunk_ids": ["other"],
                    "retrieved_parent_clause_ids": [None],
                },
            ]),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _evaluate(self):
        return evaluate(
            self.results_path,
            self.ground_truth_path,
            ks=(1,),
            parent_by_chunk={"c1": "p1", "c2": "p2"},
        )

    def test_reports_reproducible_bootstrap_intervals_for_each_metric(self):
        report = self._evaluate()
        intervals = report["confidence_intervals"]

        self.assertEqual(intervals["method"], "percentile_bootstrap")
        self.assertEqual(intervals["confidence_level"], 0.95)
        self.assertEqual(intervals["resamples"], 10_000)
        self.assertEqual(set(intervals["average"]), set(report["average"]))
        strict_recall = intervals["average"]["strict_match_recall@1"]
        self.assertEqual(strict_recall["num_questions"], 2)
        self.assertLess(strict_recall["lower"], 0.5)
        self.assertGreater(strict_recall["upper"], 0.5)

        parent_recall = intervals["average"]["parent_match_recall@1"]
        self.assertEqual(parent_recall, {
            "lower": 1.0,
            "upper": 1.0,
            "num_questions": 1,
        })
        self.assertIn("civil", intervals["by_category"])

        repeated_intervals = self._evaluate()["confidence_intervals"]
        self.assertEqual(intervals, repeated_intervals)


if __name__ == "__main__":
    unittest.main()
