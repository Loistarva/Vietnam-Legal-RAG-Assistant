import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("baseline_report_extras", ROOT / "scripts" / "baseline_report_extras.py")
extras = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extras)


class BaselineReportExtrasTest(unittest.TestCase):
    def test_paired_bootstrap_counts_and_mean_difference(self):
        a = [{"query_id": f"q{i}", "m": 0.5} for i in range(4)]
        b = [{"query_id": "q0", "m": 1.0}, {"query_id": "q1", "m": 0.0},
             {"query_id": "q2", "m": 0.5}, {"query_id": "q3", "m": 1.0}]
        result = extras.paired_bootstrap(a, b, "m", resamples=200)
        self.assertAlmostEqual(result["mean_difference"], 0.125)
        self.assertEqual((result["better"], result["worse"], result["num_questions"]), (2, 1, 4))
        self.assertLessEqual(result["lower"], result["mean_difference"])
        self.assertGreaterEqual(result["upper"], result["mean_difference"])

    def test_paired_bootstrap_requires_same_questions(self):
        with self.assertRaises(ValueError):
            extras.paired_bootstrap([{"query_id": "q0", "m": 1}], [{"query_id": "q1", "m": 1}], "m")

    def test_temporal_check_counts_only_scored_queries_and_top_k(self):
        chunks = {
            "in_force": {"chunk_id": "in_force", "metadata": {"effective_from": "2015-01-01"}},
            "expired": {"chunk_id": "expired", "metadata": {"effective_from": "2001-01-01", "effective_to": "2015-01-01"}},
            "no_date": {"chunk_id": "no_date", "metadata": {}},
        }
        results = [
            {"query_id": "q0", "results": [{"chunk_id": "in_force"}, {"chunk_id": "expired"}, {"chunk_id": "no_date"}]},
            {"query_id": "q1", "results": [{"chunk_id": "expired"}]},
        ]
        row = extras.temporal_check(results, {"q0": "2026-10-15", "q1": "2026-10-15"}, {"q0"}, chunks)
        self.assertEqual((row["violations"], row["checked"], row["missing_date_metadata"]), (1, 2, 1))
        row = extras.temporal_check(results, {"q0": "2026-10-15"}, {"q0"}, chunks, top_k=1)
        self.assertEqual((row["violations"], row["checked"]), (0, 1))


if __name__ == "__main__":
    unittest.main()
