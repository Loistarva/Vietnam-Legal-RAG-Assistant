import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from retrieval.hybrid_retriever import HybridRetriever, HybridSearchConfig
from retrieval.run_dev_retrieval import read_queries, to_envelope

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "retrieval_schema.json").read_text(encoding="utf-8"))


def chunk(chunk_id, score):
    return {
        "chunk_id": chunk_id, "document_id": "l_52_2014_qh13", "article_id": "l_52_2014_qh13_art_8",
        "clause_id": "l_52_2014_qh13_art_8_clause_1", "parent_clause_id": "l_52_2014_qh13_art_8_clause_1",
        "chunk_text": f"Nội dung {chunk_id}", "score": score,
        "metadata": {"validity_status": "Còn hiệu lực", "article_number": "8"},
    }


class StaticRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query, top_k, *, as_of_date):
        return [dict(hit) for hit in self.hits[:top_k]]


class RunDevRetrievalOutputTest(unittest.TestCase):
    def test_read_queries_keeps_benchmark_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queries.json"
            path.write_text(json.dumps([{"id": "HN_001", "question": " Tuổi kết hôn? ",
                                         "as_of_date": "1995-06-01"}]), encoding="utf-8")
            self.assertEqual(read_queries(path), [("HN_001", "Tuổi kết hôn?", "1995-06-01")])
            path.write_text(json.dumps(["Tuổi kết hôn?"]), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_queries(path)

    def test_every_method_writes_schema_valid_envelopes(self):
        a, b = chunk("l_52_2014_qh13_art_8_clause_1_chunk_1", 3.0), chunk("l_52_2014_qh13_art_8_clause_2_chunk_1", 1.0)
        retriever = HybridRetriever(StaticRetriever([a, b]), StaticRetriever([b, a]),
                                    HybridSearchConfig(top_k=2, candidate_k=2, rrf_k=60))
        ranked = retriever.retrieve("Tuổi kết hôn?")
        validator = Draft202012Validator(SCHEMA)
        for method in ("bm25", "dense", "hybrid"):
            envelope = to_envelope(method, "HN_001", "Tuổi kết hôn?", ranked[method], {"top_k": 2}, 1.5)
            self.assertEqual(list(validator.iter_errors(envelope)), [], method)
            self.assertEqual(envelope["query_id"], "HN_001")
            self.assertEqual([row["rank"] for row in envelope["results"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
