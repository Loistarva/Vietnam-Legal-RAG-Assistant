"""scripts/calibrate_confidence_threshold.py on a tiny synthetic Dev + negative set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import calibrate_confidence_threshold as calibrate  # noqa: E402


def rows(*pairs):
    return [{"chunk_id": cid, "rank": i, "reranker_score": s} for i, (cid, s) in enumerate(pairs, 1)]


@pytest.fixture
def files(tmp_path):
    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    paths = {
        "benchmark": write("queries.json", [{"id": "Q1"}, {"id": "Q2"}, {"id": "Q3"}]),
        "ground_truth": write("gt.json", [
            {"id": "Q1", "review_status": "source_checked", "gold_context_ids": ["g1"]},
            {"id": "Q2", "review_status": "source_checked", "gold_context_ids": ["g2"]},
            {"id": "Q3", "review_status": "source_checked", "gold_context_ids": ["g3"]},
        ]),
        "id_manifest": write("ids.json", {"question_ids": ["Q3"]}),
        "dev_artifact": write("dev.json", [
            {"query_id": "Q1", "results": rows(("g1", 0.9), ("x", 0.05))},
            {"query_id": "Q2", "results": rows(("x", 0.3), ("y", 0.2))},
            {"query_id": "Q3", "results": rows(("g3", 0.01))},
        ]),
        "negatives_artifact": write("neg.json", [
            {"query_id": "N1", "query": "Nấu ăn?", "config": {"as_of_date": "2026-10-15"},
             "results": rows(("z", 0.002))},
        ]),
    }
    neg = tmp_path / "neg.jsonl"
    neg.write_text(json.dumps({"id": "N1", "question": "Nấu ăn?", "as_of_date": "2026-10-15",
                               "label": "non_legal"}, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["negative_set"] = neg
    return paths


def run(files, tmp_path):
    out = tmp_path / "sweep.json"
    argv = [arg for key, path in files.items() for arg in (f"--{key.replace('_', '-')}", str(path))]
    assert calibrate.main([*argv, "--output", str(out)]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_sweep_excludes_official_ids_and_counts_outcomes(files, tmp_path):
    result = run(files, tmp_path)
    assert result["inputs"]["dev_remaining_ids"] == ["Q1", "Q2"]
    row = next(s for s in result["sweep"] if (s["min_top1_score"], s["min_evidence_score"]) == (0.5, 0.1))
    assert row["false_rejection_gold_in_top5"] == []
    assert row["rejected_without_gold_in_top5"] == ["Q2"]
    assert row["negatives_accepted"] == {"non_legal": []}
    off = next(s for s in result["sweep"] if (s["min_top1_score"], s["min_evidence_score"]) == (0.0, 0.0))
    assert off["negatives_accepted"] == {"non_legal": ["N1"]}


def test_negative_artifact_must_match_the_set(files, tmp_path):
    files["negatives_artifact"].write_text(json.dumps([
        {"query_id": "N1", "query": "Câu khác?", "config": {"as_of_date": "2026-10-15"}, "results": []}]),
        encoding="utf-8")
    with pytest.raises(SystemExit, match="khác tập câu âm"):
        run(files, tmp_path)
