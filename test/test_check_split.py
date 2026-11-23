import unittest
from pathlib import Path

from scripts.check_split import _chunk_clauses, _read_json, check_split

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "benchmark"


def _query(qid, split, question):
    return {"id": qid, "split": split, "question": question, "test_type": "current_law",
            "question_type": "fact", "difficulty": "easy"}


def _gold(qid, split, clauses, reviewed=True, candidates=()):
    return {"id": qid, "split": split, "gold_clause_ids": list(clauses),
            "gold_context_ids": [f"{c}_chunk_1" for c in clauses] if reviewed else [],
            "gold_context_ids_confirmed": reviewed,
            "review_status": "source_checked" if reviewed else "draft",
            "candidate_context_ids": list(candidates)}


class CheckSplitTest(unittest.TestCase):
    def test_current_split_has_no_errors(self):
        queries = [*_read_json(BENCHMARK / "queries_dev.json"),
                   *_read_json(BENCHMARK / "queries_test.json")]
        report = check_split(queries, _read_json(BENCHMARK / "ground_truth.json"),
                             _chunk_clauses(ROOT / "data" / "chunking_output" / "chunks.jsonl"))
        self.assertEqual(report["errors"], [])
        self.assertEqual(sum(report["distribution"]["test_type"]["test"].values()), 30)

    def test_shared_reviewed_clause_is_an_error(self):
        report = check_split(
            [_query("D1", "dev", "Câu một"), _query("T1", "test", "Câu hai khác hẳn")],
            [_gold("D1", "dev", ["x_art_1_clause_1"]), _gold("T1", "test", ["x_art_1_clause_1"])],
            {},
        )
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("dùng chung Khoản gold", report["errors"][0])

    def test_draft_candidate_on_test_clause_is_a_warning(self):
        report = check_split(
            [_query("D1", "dev", "Câu một"), _query("T1", "test", "Câu hai khác hẳn")],
            [_gold("D1", "dev", [], reviewed=False, candidates=["x_art_1_clause_1_chunk_1"]),
             _gold("T1", "test", ["x_art_1_clause_1"])],
            {"x_art_1_clause_1_chunk_1": "x_art_1_clause_1"},
        )
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["warnings"]), 1)

    def test_near_duplicate_on_same_article_is_an_error(self):
        question = "Theo Luật Hôn nhân và gia đình 2014, nam phải đủ bao nhiêu tuổi để kết hôn?"
        queries = [_query("D1", "dev", question), _query("T1", "test", question.replace("nam", "nữ"))]
        same_article = check_split(
            queries,
            [_gold("D1", "dev", ["x_art_8_clause_2"]), _gold("T1", "test", ["x_art_8_clause_1"])],
            {},
        )
        self.assertEqual(len(same_article["errors"]), 1)
        self.assertIn("gần trùng", same_article["errors"][0])
        other_article = check_split(
            queries,
            [_gold("D1", "dev", ["x_art_9_clause_1"]), _gold("T1", "test", ["x_art_8_clause_1"])],
            {},
        )
        self.assertEqual(other_article["errors"], [])

    def test_unreviewed_test_question_is_an_error(self):
        report = check_split(
            [_query("T1", "test", "Câu hỏi")],
            [_gold("T1", "test", [], reviewed=False)],
            {},
        )
        self.assertTrue(any("chưa duyệt" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
