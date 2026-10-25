"""Evaluation outputs use query_id only and read categories from the given question files."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import evaluate_zero_shot
from evaluation.metrics import evaluate


def write(path: Path, data) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class EvaluationIdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.gt = write(self.dir / "gt.json", [
            {"id": "HN_001", "gold_context_ids": ["c1"], "answer": "Nam từ đủ 20 tuổi trở lên."},
        ])
        self.queries = write(self.dir / "queries.json", [{"id": "HN_001", "category": "ket_hon"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_metrics_write_query_id_only_and_category_from_given_file(self):
        results = write(self.dir / "results.json", [{"query_id": "HN_001", "retrieved_chunk_ids": ["c1"]}])
        report = evaluate(results, self.gt, ks=(1,), queries_paths=[self.queries])
        self.assertEqual(report["per_question"][0]["query_id"], "HN_001")
        self.assertNotIn("question_id", report["per_question"][0])
        self.assertEqual(report["by_category"]["ket_hon"]["recall@1"], 1.0)

    def test_metrics_reject_question_id_and_unreadable_question_file(self):
        legacy = write(self.dir / "legacy.json", [{"question_id": "HN_001", "retrieved_chunk_ids": ["c1"]}])
        with self.assertRaisesRegex(ValueError, "query_id"):
            evaluate(legacy, self.gt, ks=(1,))
        results = write(self.dir / "results.json", [{"query_id": "HN_001", "retrieved_chunk_ids": ["c1"]}])
        broken = self.dir / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            evaluate(results, self.gt, ks=(1,), queries_paths=[broken])

    def test_zero_shot_output_is_accepted_by_the_evaluator(self):
        # Same record shape as evaluation/zero_shot.py writes.
        predictions = write(self.dir / "pred.json", [
            {"query_id": "HN_001", "question": "?", "answer": "Nam từ đủ 20 tuổi trở lên.", "method": "zero_shot"},
        ])
        summary = evaluate_zero_shot.evaluate(predictions, self.gt, self.dir / "m.json", self.dir / "s.json",
                                              queries_paths=[self.queries])
        self.assertEqual(summary["evaluated_questions"], 1)
        self.assertEqual(summary["by_category"]["ket_hon"]["count"], 1)
        scored = json.loads((self.dir / "s.json").read_text(encoding="utf-8"))
        self.assertNotIn("question_id", scored[0])


if __name__ == "__main__":
    unittest.main()
