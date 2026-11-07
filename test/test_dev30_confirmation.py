"""Tập Dev30 dùng cho Zero-shot khớp bản xác nhận, và bảng chấm tay phủ đúng 30 câu."""
import csv
import json
import unittest
from pathlib import Path

from evaluation.test_run_freeze import _file_sha256

ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION = ROOT / "evaluation" / "review" / "dev30_confirmation_v1.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Dev30ConfirmationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.confirmation = read_json(CONFIRMATION)
        cls.queries = read_json(ROOT / cls.confirmation["query_file"])
        cls.ids = [row["id"] for row in cls.queries]
        cls.ground_truth = {row["id"]: row for row in read_json(ROOT / "data/benchmark/ground_truth.json")}

    def test_query_file_matches_confirmed_hash(self):
        key = self.confirmation["query_file"]
        self.assertEqual(_file_sha256(ROOT / key), self.confirmation["input_sha256_lf_normalized"][key])

    def test_ids_file_and_dev_records_match(self):
        ids_file = (ROOT / self.confirmation["ids_file"]).read_text(encoding="utf-8").split()
        self.assertEqual(ids_file, self.ids)
        self.assertEqual(len(set(self.ids)), self.confirmation["question_count"])
        dev = {row["id"]: row for row in read_json(ROOT / "data/benchmark/queries_dev.json")}
        test_ids = {row["id"] for row in read_json(ROOT / "data/benchmark/queries_test.json")}
        for row in self.queries:
            self.assertEqual(dev.get(row["id"]), row, row["id"])
            self.assertNotIn(row["id"], test_ids)

    def test_gold_is_confirmed_and_does_not_share_a_clause_with_test(self):
        chunks = {}
        with (ROOT / "data/chunking_output/chunks.jsonl").open(encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                chunks[chunk["chunk_id"]] = chunk
        test_ids = {row["id"] for row in read_json(ROOT / "data/benchmark/queries_test.json")}
        test_clauses = {
            chunks[cid].get("parent_clause_id") or cid
            for qid in test_ids for cid in self.ground_truth[qid]["gold_context_ids"]
        }
        for row in self.queries:
            gold = self.ground_truth[row["id"]]
            self.assertTrue(gold.get("gold_context_ids_confirmed"), row["id"])
            self.assertTrue((gold.get("answer") or "").strip(), row["id"])
            for cid in gold["gold_context_ids"]:
                self.assertIn(cid, chunks)
                self.assertNotIn(chunks[cid].get("parent_clause_id") or cid, test_clauses, row["id"])

    def test_manual_scores_cover_exactly_the_30_questions(self):
        path = ROOT / self.confirmation["manual_rubric"]["scores"]
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([row["query_id"] for row in rows], self.ids)
        for row in rows:
            self.assertIn(row["answer_relevance_score"], {"1", "2", "3", "4", "5"})
            self.assertIn(row["faithfulness_score"], {"1", "2", "3", "4", "5"})
            self.assertTrue(row["rubric_rationale"].strip())
            self.assertTrue(row["grader"].strip())
            self.assertRegex(row["prediction_sha256"], r"^[0-9a-f]{64}$")

    def test_committed_zero_shot_metrics_use_all_manual_scores(self):
        metrics = read_json(ROOT / "evaluation/results/zero_shot_dev30_metrics.json")
        self.assertEqual(metrics["rubric_scored_questions"], 30)
        self.assertEqual(metrics["evaluated_questions"], 30)


if __name__ == "__main__":
    unittest.main()
