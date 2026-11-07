"""Reference tables must be regenerated in the same change as the corpus (D3).

When data/chunking_output/chunks.jsonl is regenerated, run
    python scripts/import_chunk_index.py --input data/chunking_output/chunks.jsonl --force
so production_chunk_index.json carries exactly the corpus chunk_ids.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def corpus_ids():
    lines = (ROOT / "data" / "chunking_output" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    return {json.loads(line)["chunk_id"] for line in lines if line.strip()}


class ReferenceSyncTest(unittest.TestCase):
    def test_production_chunk_index_matches_corpus(self):
        index = json.loads((ROOT / "data" / "reference" / "production_chunk_index.json").read_text(encoding="utf-8"))
        index_ids = {row["chunk_id"] for row in index}
        corpus = corpus_ids()
        self.assertEqual(sorted(index_ids - corpus)[:5], [], "production_chunk_index có chunk_id không còn trong corpus")
        self.assertEqual(sorted(corpus - index_ids)[:5], [], "corpus có chunk_id chưa vào production_chunk_index")

    def test_benchmark_chunk_ids_exist_in_corpus(self):
        corpus = corpus_ids()
        for name in ("ground_truth.json",):
            rows = json.loads((ROOT / "data" / "benchmark" / name).read_text(encoding="utf-8"))
            missing = sorted({cid for row in rows
                              for field in ("gold_context_ids", "candidate_context_ids")
                              for cid in row.get(field) or []
                              if not cid.startswith("version_") and cid not in corpus})
            self.assertEqual(missing[:5], [], f"{name}: chunk_id không có trong corpus")


if __name__ == "__main__":
    unittest.main()
