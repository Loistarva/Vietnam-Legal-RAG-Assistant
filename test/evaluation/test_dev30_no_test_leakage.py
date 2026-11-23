"""D1.4 canonical guard against Dev30/Test leakage; absent handoff is a failure."""

from copy import deepcopy
import json
import shutil

import pytest

from evaluation import dev30_guard as guard
from evaluation.dev30_guard import check_handoff


def test_dev30_manifest_handoff_and_holdout_separation():
    result = check_handoff()
    assert result["selected_count"] == result["source_checked_count"] == 30
    assert (
        result["test_id_overlap"]
        == result["test_clause_overlap"]
        == result["test_question_overlap"]
        == 0
    )
    assert result["test_freeze_verified"] is True


@pytest.fixture(scope="module")
def source_bundle():
    root = guard.ROOT
    return dict(
        manifest=guard.read_json(root / guard.MANIFEST),
        query_rows=guard.read_json(root / guard.QUERIES),
        id_lines=(root / guard.IDS).read_text(encoding="utf-8-sig").splitlines(),
        dev_rows=guard.read_json(root / guard.DEV),
        test_rows=guard.read_json(root / guard.TEST),
        gold_rows=guard.read_json(root / guard.GOLD),
        chunk_rows=[
            json.loads(line)
            for line in (root / guard.CHUNKS)
            .read_text(encoding="utf-8-sig")
            .splitlines()
        ],
    )


def record(bundle, qid):
    return next(g for g in bundle["gold_rows"] if g["id"] == qid)


@pytest.mark.parametrize(
    "case,code",
    [
        ("duplicate_manifest", "duplicate_manifest_id"),
        ("wrong_count", "manifest_count"),
        ("bad_version", "manifest_version"),
        ("ids_order", "id_order"),
        ("missing_query", "query_count"),
        ("query_hash", "query_hash"),
        ("ids_hash", "ids_hash"),
        ("test_id", "test_id_leakage"),
        ("test_clause", "test_clause_leakage"),
        ("missing_test_gold", "missing_gold"),
        ("empty_test_clauses", "missing_gold"),
        ("test_label_mismatch", "gold_clause_mapping"),
        ("missing_test_set", "invalid_input"),
        ("draft", "unreviewed_gold"),
        ("not_dev", "not_dev"),
        ("gold_test_split", "gold_split"),
        ("unconfirmed", "unconfirmed_gold"),
        ("incomplete_review", "incomplete_review"),
        ("missing_chunk", "missing_chunk"),
        ("missing_parent", "missing_parent_clause"),
        ("wrong_parent", "inconsistent_parent_clause"),
        ("missing_answer", "missing_answer"),
        ("changed_answer", "selected_gold_changed"),
        ("invalid_date", "query_date"),
        ("duplicate_question", "duplicate_question"),
        ("test_question", "test_question_leakage"),
        ("answer_in_input", "answer_in_input"),
    ],
)
def test_corrupt_or_leaking_sets_fail_closed(source_bundle, case, code):
    bundle = deepcopy(source_bundle)
    qid = bundle["query_rows"][0]["id"]
    g = record(bundle, qid)
    cid = g["gold_context_ids"][0]
    chunk = next(c for c in bundle["chunk_rows"] if c["chunk_id"] == cid)
    test_id = bundle["test_rows"][0]["id"]
    if case == "duplicate_manifest":
        bundle["manifest"]["question_ids"][1] = qid
    elif case == "bad_version":
        bundle["manifest"]["version"] = "unknown"
    elif case == "wrong_count":
        bundle["manifest"]["question_count"] = True
    elif case == "ids_order":
        bundle["id_lines"].reverse()
    elif case == "missing_query":
        bundle["query_rows"].pop()
    elif case == "query_hash":
        bundle["manifest"]["query_canonical_sha256"] = "0" * 64
    elif case == "ids_hash":
        bundle["manifest"]["dataset_ids_hash"] = "0" * 64
    elif case == "test_id":
        bundle["test_rows"][0]["id"] = qid
    elif case == "test_clause":
        # Different chunks can still leak the same parent clause.
        other = deepcopy(chunk)
        other["chunk_id"] = cid + "_fixture"
        bundle["chunk_rows"].append(other)
        record(bundle, test_id)["gold_context_ids"] = [other["chunk_id"]]
        record(bundle, test_id)["gold_clause_ids"] = list(g["gold_clause_ids"])
    elif case == "missing_test_gold":
        bundle["gold_rows"] = [r for r in bundle["gold_rows"] if r["id"] != test_id]
    elif case == "empty_test_clauses":
        record(bundle, test_id)["gold_clause_ids"] = []
    elif case == "test_label_mismatch":
        record(bundle, test_id)["gold_clause_ids"] = list(g["gold_clause_ids"])
    elif case == "missing_test_set":
        bundle["test_rows"] = []
    elif case == "draft":
        g["review_status"] = "draft"
    elif case == "not_dev":
        bundle["dev_rows"] = [r for r in bundle["dev_rows"] if r["id"] != qid]
    elif case == "gold_test_split":
        g["split"] = "test"
    elif case == "unconfirmed":
        g["gold_context_ids_confirmed"] = False
    elif case == "incomplete_review":
        g["evidence_level"] = "unverified"
    elif case == "missing_chunk":
        bundle["chunk_rows"] = [c for c in bundle["chunk_rows"] if c["chunk_id"] != cid]
    elif case == "missing_parent":
        chunk.pop("parent_clause_id")
    elif case == "wrong_parent":
        chunk["parent_clause_id"] = "wrong_parent"
    elif case == "missing_answer":
        g["answer"] = ""
    elif case == "changed_answer":
        g["answer"] += " changed"
    elif case in ("invalid_date", "duplicate_question", "answer_in_input"):
        q = bundle["query_rows"][1]
        dev = next(r for r in bundle["dev_rows"] if r["id"] == q["id"])
        change = (
            {"as_of_date": "2026-02-30"}
            if case == "invalid_date"
            else {"question": bundle["query_rows"][0]["question"].upper()}
            if case == "duplicate_question"
            else {"answer": "reference answer"}
        )
        q.update(change)
        dev.update(change)
        bundle["manifest"]["query_canonical_sha256"] = guard.canonical_hash(
            bundle["query_rows"]
        )
    else:
        bundle["test_rows"][0]["question"] = bundle["query_rows"][0]["question"].upper()
    with pytest.raises(guard.Dev30GuardError, match=code):
        guard.validate_dev30(**bundle)


@pytest.fixture
def handed_off_root(tmp_path):
    for name in (
        guard.MANIFEST,
        guard.CONFIRMATION,
        guard.QUERIES,
        guard.IDS,
        guard.DEV,
        guard.TEST,
        guard.GOLD,
        guard.CHUNKS,
        guard.CHUNK_INTEGRITY,
        "docs/test_questions_freeze.json",
        "docs/test_gold_freeze.json",
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(guard.ROOT / name, target)
    return tmp_path


@pytest.mark.parametrize(
    "case,code",
    [
        ("missing_manifest", "missing_or_invalid_artifact"),
        ("malformed_manifest", "invalid_manifest"),
        ("missing_confirmation", "missing_or_invalid_artifact"),
        ("unconfirmed", "unconfirmed_handoff"),
        ("unsafe_path", "artifact_path"),
        ("missing_hash", "confirmation_inputs"),
        ("changed_gt", "selected_gold_changed"),
        ("changed_test_question", "test_question_freeze"),
        ("changed_freeze", "test_gold_freeze"),
        ("duplicate_key", "duplicate_json_key"),
        ("bad_confirmation_date", "confirmation_metadata"),
        ("bad_freeze_count", "test_freeze_count"),
    ],
)
def test_real_files_require_complete_bound_handoff(handed_off_root, case, code):
    root = handed_off_root

    def change(name, fn):
        path = root / name
        x = guard.read_json(path)
        fn(x)
        path.write_text(json.dumps(x), encoding="utf-8")

    if case == "missing_manifest":
        (root / guard.MANIFEST).unlink()
    elif case == "malformed_manifest":
        (root / guard.MANIFEST).write_text("[]", encoding="utf-8")
    elif case == "missing_confirmation":
        (root / guard.CONFIRMATION).unlink()
    elif case == "unconfirmed":
        change(guard.CONFIRMATION, lambda x: x.update(status="proposed"))
    elif case == "unsafe_path":
        change(guard.MANIFEST, lambda x: x.update(query_file="../outside.json"))
    elif case == "missing_hash":
        change(
            guard.CONFIRMATION,
            lambda x: x["input_sha256_lf_normalized"].pop(guard.CHUNKS),
        )
    elif case == "changed_gt":
        selected_id = guard.read_json(root / guard.MANIFEST)["question_ids"][0]
        change(
            guard.GOLD,
            lambda rows: next(r for r in rows if r["id"] == selected_id).update(
                answer="changed selected answer"
            ),
        )
    elif case == "changed_test_question":
        change(
            guard.TEST,
            lambda x: x[0].update(question=x[0]["question"] + " additional text"),
        )
    elif case == "changed_freeze":
        change("docs/test_gold_freeze.json", lambda x: x.update(sha256="0" * 64))
    elif case == "bad_confirmation_date":
        change(guard.CONFIRMATION, lambda x: x.update(confirmed_on="2026-02-30"))
    elif case == "bad_freeze_count":
        change("docs/test_gold_freeze.json", lambda x: x.update(test_question_count=31))
    else:
        (root / guard.MANIFEST).write_text(
            '{"question_count":30,"question_count":29}', encoding="utf-8"
        )
    with pytest.raises(guard.Dev30GuardError, match=code):
        guard.check_handoff(root)


def test_guard_does_not_write_handoff_or_benchmark(handed_off_root):
    root = handed_off_root
    before = {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    result = guard.check_handoff(root)
    assert result["confirmation_status"] == "confirmed_for_zero_shot_baseline"
    assert result["manifest_status"] == "proposed_pending_user_and_dev2_review"
    assert before == {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }


def test_no_manifest_is_failure_not_skip(tmp_path):
    with pytest.raises(guard.Dev30GuardError, match="missing_or_invalid_artifact"):
        guard.check_handoff(tmp_path)


def test_unselected_draft_or_format_change_does_not_break_handoff(handed_off_root):
    root = handed_off_root
    gold = guard.read_json(root / guard.GOLD)
    selected = set(guard.read_json(root / guard.MANIFEST)["question_ids"])
    row = next(
        r for r in gold if r["id"] not in selected and r.get("review_status") == "draft"
    )
    row["answer"] += " draft edit outside Dev30"
    (root / guard.GOLD).write_text(json.dumps(gold), encoding="utf-8")
    assert guard.check_handoff(root)["status"] == "PASS"


def test_selected_chunk_content_change_fails_even_with_same_identity(handed_off_root):
    root = handed_off_root
    expected = guard.read_json(root / guard.CHUNK_INTEGRITY)["chunk_hashes"]
    chunks = [
        json.loads(line)
        for line in (root / guard.CHUNKS).read_text(encoding="utf-8").splitlines()
    ]
    next(c for c in chunks if c["chunk_id"] in expected)["text"] += " corrupted content"
    (root / guard.CHUNKS).write_text(
        "".join(json.dumps(c) + "\n" for c in chunks), encoding="utf-8"
    )
    with pytest.raises(guard.Dev30GuardError, match="selected_chunk_changed"):
        guard.check_handoff(root)
