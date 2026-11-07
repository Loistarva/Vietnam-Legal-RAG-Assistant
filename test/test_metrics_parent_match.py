import json
import tempfile
import unittest
from pathlib import Path

from evaluation.metrics import evaluate


class RetrievalMetricContractTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _evaluate(
        self,
        gold_chunk_ids,
        retrieved_chunk_ids,
        retrieved_parent_clause_ids,
        parent_by_chunk,
        k,
    ):
        ground_truth_path = self.root / "ground_truth.json"
        ground_truth_path.write_text(
            json.dumps([{
                "id": "Q1",
                "gold_context_ids": gold_chunk_ids,
                "gold_context_ids_confirmed": True,
            }]),
            encoding="utf-8",
        )
        results_path = self.root / "results.json"
        results_path.write_text(
            json.dumps([{
                "query_id": "Q1",
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "retrieved_parent_clause_ids": retrieved_parent_clause_ids,
            }]),
            encoding="utf-8",
        )
        return evaluate(
            results_path,
            ground_truth_path,
            ks=(k,),
            parent_by_chunk=parent_by_chunk,
        )["per_question"][0]

    def test_strict_match_scores_retrieved_gold_chunk(self):
        row = self._evaluate(
            gold_chunk_ids=["gold-1"],
            retrieved_chunk_ids=["gold-1", "other"],
            retrieved_parent_clause_ids=["clause-1", "clause-2"],
            parent_by_chunk={"gold-1": "clause-1"},
            k=1,
        )

        self.assertEqual(row["strict_match_recall@1"], 1.0)

    def test_parent_match_scores_unique_gold_parent_clauses(self):
        row = self._evaluate(
            gold_chunk_ids=["gold-1", "gold-2"],
            retrieved_chunk_ids=["retrieved-1", "retrieved-2"],
            retrieved_parent_clause_ids=["clause-2", "clause-1"],
            parent_by_chunk={"gold-1": "clause-1", "gold-2": "clause-2"},
            k=2,
        )

        self.assertEqual(row["parent_match_recall@2"], 1.0)
        self.assertFalse(row["parent_match_metadata_missing@2"])

    def test_multiple_gold_chunks_use_all_gold_chunks_as_recall_denominator(self):
        row = self._evaluate(
            gold_chunk_ids=["gold-1", "gold-2"],
            retrieved_chunk_ids=["gold-1"],
            retrieved_parent_clause_ids=["clause-1"],
            parent_by_chunk={"gold-1": "clause-1", "gold-2": "clause-2"},
            k=1,
        )

        self.assertEqual(row["strict_match_recall@1"], 0.5)

    def test_missing_retrieved_parent_metadata_is_not_inferred_or_scored(self):
        row = self._evaluate(
            gold_chunk_ids=["gold-1"],
            retrieved_chunk_ids=["gold-1"],
            retrieved_parent_clause_ids=[None],
            parent_by_chunk={"gold-1": "clause-1"},
            k=1,
        )

        self.assertEqual(row["strict_match_recall@1"], 1.0)
        self.assertIsNone(row["parent_match_recall@1"])
        self.assertTrue(row["parent_match_metadata_missing@1"])


if __name__ == "__main__":
    unittest.main()
