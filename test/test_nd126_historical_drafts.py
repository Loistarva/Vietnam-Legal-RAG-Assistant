"""Prevent repealed ND126 provisions from being used as current-law candidates."""
import json
import re
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


@pytest.mark.parametrize("query_id", ["HN_225", "HN_226", "HN_232", "HN_234", "HN_236"])
def test_historical_draft_answer_has_no_title_tail_or_next_heading(query_id):
    label = LABELS[query_id]
    head = label["answer"].split("(126/2014/NĐ-CP): ", 1)[1]
    assert re.match(r"(\d+\. |Việc )", head)
    words = [w.strip(",.;:") for w in label["answer"].split()]
    caps = [len(w) > 1 and w.isupper() for w in words]
    assert not any(all(caps[i:i + 3]) for i in range(len(caps) - 2))
    assert all(CHUNKS[cid]["text"] in label["answer"] for cid in label["candidate_context_ids"])
    assert label["review_status"] == "draft"


def test_hn063_question_and_candidates_cover_only_three_named_concepts():
    query, label = QUERIES["HN_063"], LABELS["HN_063"]
    expected = [f"l_52_2014_qh13_art_3_clause_{n}_chunk_1" for n in (1, 5, 7)]
    assert label["candidate_context_ids"] == expected
    assert label["gold_clause_ids"] == [CHUNKS[cid]["clause_id"] for cid in expected]
    assert all(is_effective_at(CHUNKS[cid], query["as_of_date"]) for cid in expected)
    for concept in ("hôn nhân", "kết hôn", "chung sống như vợ chồng"):
        assert concept in query["question"].lower()
        assert concept in label["answer"].lower()
    assert label["review_status"] == "draft"
    assert label["gold_context_ids"] == []
    assert label["gold_context_ids_confirmed"] is False
