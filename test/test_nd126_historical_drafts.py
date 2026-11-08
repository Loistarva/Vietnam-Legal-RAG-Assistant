"""Prevent repealed ND126 provisions from being used as current-law candidates."""
import json
from pathlib import Path

import pytest

from retrieval.temporal import is_effective_at

ROOT = Path(__file__).resolve().parents[1]
QUERIES = {q["id"]: q for q in json.loads((ROOT / "data/benchmark/queries_dev.json").read_text(encoding="utf-8"))}
LABELS = {q["id"]: q for q in json.loads((ROOT / "data/benchmark/ground_truth.json").read_text(encoding="utf-8"))}
CHUNKS = {c["chunk_id"]: c for c in (
    json.loads(line) for line in (ROOT / "data/chunking_output/chunks.jsonl").read_text(encoding="utf-8").splitlines()
)}
IDS = [f"HN_{n:03}" for n in (
    209, 211, 212, 213, 214, 216, 217, 218, 222, 223, 224, 225, 226,
    227, 228, 229, 232, 233, 234, 235, 236, 237, 238, 239, 276, 277,
)]


@pytest.mark.parametrize("query_id", IDS)
def test_historical_draft_has_explicit_date_and_effective_candidates(query_id):
    query, label = QUERIES[query_id], LABELS[query_id]
    assert query["as_of_date"] == "2015-12-31"
    assert "31/12/2015" in query["question"]
    assert query["test_type"] == "historical_law"
    assert label["review_status"] == "draft"
    assert label["gold_context_ids"] == []
    assert label["gold_context_ids_confirmed"] is False
    assert label["candidate_context_ids"]
    assert all(is_effective_at(CHUNKS[cid], query["as_of_date"]) for cid in label["candidate_context_ids"])
    old_provisions = [CHUNKS[cid] for cid in label["candidate_context_ids"] if cid.startswith("nd_126_2014_nd_cp_art_")]
    assert old_provisions
    assert all(not is_effective_at(c, "2016-01-01") for c in old_provisions)


def test_hn207_draft_answer_has_only_its_mapped_provisions():
    label = LABELS["HN_207"]
    assert "QUAN HỆ HÔN NHÂN" not in label["answer"]
    assert all(CHUNKS[cid]["text"] in label["answer"] for cid in label["candidate_context_ids"])
    assert label["review_status"] == "draft"
