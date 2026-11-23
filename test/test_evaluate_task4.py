import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_task4 import evaluate


class EvaluateTask4Test(unittest.TestCase):
    def test_chunk_and_article_metrics_use_shared_evaluator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_path = root / "dev.json"
            truth_path = root / "ground_truth.json"
            chunks_path = root / "chunks.jsonl"
            article_index_path = root / "article_index.json"
            results_dir = root / "results"
            results_dir.mkdir()
            output_path = root / "metrics.csv"
            article_output_path = root / "article_metrics.csv"

            dev_path.write_text(
                json.dumps([{"id": "Q1", "question": "Question"}]),
                encoding="utf-8",
            )
            truth_path.write_text(
                json.dumps([{
                    "id": "Q1",
                    "gold_context_ids": ["chunk-2"],
                    "gold_context_ids_confirmed": True,
                    "candidate_context_ids": [],
                    "gold_article_ids": ["article-2"],
                }]),
                encoding="utf-8",
            )
            chunks = [
                {
                    "chunk_id": f"chunk-{index}",
                    "document_number": f"document-{index}",
                    "article_number": "1",
                }
                for index in range(1, 11)
            ]
            chunks_path.write_text(
                "\n".join(json.dumps(chunk) for chunk in chunks) + "\n",
                encoding="utf-8",
            )
            article_index_path.write_text(
                json.dumps([
                    {
                        "document_number": f"document-{index}",
                        "article_number": "1",
                        "article_id": f"article-{index}",
                    }
                    for index in range(1, 11)
                ]),
                encoding="utf-8",
            )
            for method in ("bm25", "dense", "hybrid"):
                envelope = [{
                    "query_id": "Q1",
                    "query": "Question",
                    "results": [
                        {
                            "chunk_id": f"chunk-{index}",
                            "rank": index,
                            "score": 1 / index,
                        }
                        for index in range(1, 11)
                    ],
                }]
                (results_dir / f"dev_{method}.json").write_text(
                    json.dumps(envelope), encoding="utf-8"
                )

            rows = evaluate(
                dev_path,
                truth_path,
                chunks_path,
                results_dir,
                output_path,
                article_index_path,
                article_output_path,
            )

            self.assertEqual(rows[0]["recall_at_10"], 1.0)
            self.assertEqual(rows[0]["mrr_at_10"], 0.5)
            self.assertEqual(rows[0]["precision_at_10"], 0.1)
            with article_output_path.open(encoding="utf-8-sig", newline="") as file:
                article_rows = list(csv.DictReader(file))
            self.assertEqual(float(article_rows[0]["recall_at_10"]), 1.0)
            self.assertEqual(float(article_rows[0]["mrr_at_10"]), 0.5)
            self.assertEqual(float(article_rows[0]["precision_at_10"]), 0.1)


if __name__ == "__main__":
    unittest.main()
