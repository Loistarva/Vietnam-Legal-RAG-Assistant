from copy import deepcopy
import json

import pytest

from scripts import prepare_dev30 as selection


@pytest.fixture(scope="module")
def original():
    policy = json.loads(selection.POLICY.read_text(encoding="utf-8"))
    ctx = selection.context(policy)
    rows = [deepcopy(ctx["dev"][qid]) for qid in policy["selected_ids"]]
    return policy, ctx, rows


def test_all_30_pass_and_exact_user_exclusion_count(original):
    policy, ctx, rows = original
    blocked = selection.expand_ids(policy["user_excluded_id_spec"])
    assert len(blocked) == 195
    assert not blocked & set(policy["selected_ids"])
    assert len(ctx["added_chunks"]) == 9
    assert selection.check_selection(rows, ctx, policy) == []


@pytest.mark.parametrize("spec", ["HN_050–HN_037", "HN_000", "HN_301", "HN_037, HN_037", "HN_037–050", "HN_037 junk"])
def test_invalid_exclusion_range_rejected(spec):
    with pytest.raises(ValueError):
        selection.expand_ids(spec)


@pytest.mark.parametrize("change,expected", [
    ({"split":"test"}, "not_dev_or_test_id"),
    ({"as_of_date":None}, "invalid_or_missing_as_of_date"),
    ({"as_of_date":"2026-02-30"}, "invalid_or_missing_as_of_date"),
    ({"question":""}, "empty_question"),
    ({"answer":"accidentally included reference answer"}, "answer_or_gold_leaked_into_model_input"),
])
def test_bad_model_input_rejected(original, change, expected):
    policy,ctx,rows = original
    q = deepcopy(rows[0]); q.update(change)
    assert expected in selection.rejection_reasons(q,ctx,policy)


def test_user_blocked_and_known_typo_never_selected(original):
    policy,ctx,_ = original
    assert "user_requested_exclusion" in selection.rejection_reasons(ctx["dev"]["HN_037"],ctx,policy)
    assert "known_query_issue" in selection.rejection_reasons(ctx["dev"]["HN_078"],ctx,policy)


@pytest.mark.parametrize("field", ["review_status", "evidence_level", "mapping_status", "answer_kind"])
def test_unverified_gold_rejected(original,field):
    policy,ctx,rows = original; ctx=deepcopy(ctx)
    ctx["gold"][rows[0]["id"]][field] = "draft"
    assert f"unverified_{field}" in selection.rejection_reasons(rows[0],ctx,policy)


@pytest.mark.parametrize("mode,expected", [("id","not_dev_or_test_id"),("clause","test_clause_leakage"),("question","test_question_collision")])
def test_test_leakage_rejected(original, mode, expected):
    policy,ctx,rows=original;ctx=deepcopy(ctx);q=rows[0]
    if mode=="id": ctx["test_ids"].add(q["id"])
    elif mode=="clause": ctx["test_clauses"].add(ctx["gold"][q["id"]]["gold_clause_ids"][0])
    else: ctx["test_questions"].add(selection.normalized(q["question"]))
    assert expected in selection.rejection_reasons(q,ctx,policy)


@pytest.mark.parametrize("mode,expected", [("chunk","uses_added_chunk"),("document","uses_added_document"),("missing","missing_corpus_chunk"),("hierarchy","inconsistent_corpus_hierarchy")])
def test_corpus_failures_rejected(original, mode, expected):
    policy,ctx,rows=original;ctx=deepcopy(ctx);q=rows[0]
    cid=ctx["gold"][q["id"]]["gold_context_ids"][0]
    if mode=="chunk": ctx["added_chunks"].add(cid)
    elif mode=="document": ctx["added_documents"].add(ctx["chunks"][cid]["document_id"])
    elif mode=="missing": del ctx["chunks"][cid]
    else: ctx["chunks"][cid]["article_id"] = "wrong_article"
    assert expected in selection.rejection_reasons(q,ctx,policy)


def test_pending_answer_fix_rejected(original):
    policy,ctx,rows=original;ctx=deepcopy(ctx);q=rows[0]
    ctx["peer_gold"][q["id"]]["answer"] = "A newly revised answer"
    assert "substantive_gold_changed_in_pending_d1" in selection.rejection_reasons(q,ctx,policy)


def test_pending_question_edit_rejected(original):
    policy,ctx,rows=original;ctx=deepcopy(ctx);q=rows[0]
    ctx["peer_dev"][q["id"]]["question"] += " revised"
    assert "query_changed_in_pending_d1" in selection.rejection_reasons(q,ctx,policy)


def test_test_split_in_gold_rejected(original):
    policy,ctx,rows=original;ctx=deepcopy(ctx);q=rows[0]
    ctx["gold"][q["id"]]["split"]="test"
    assert "gold_split_is_not_dev" in selection.rejection_reasons(q,ctx,policy)


def test_end_date_is_exclusive(original):
    policy,ctx,rows=original;ctx=deepcopy(ctx);q=rows[0]
    cid=ctx["gold"][q["id"]]["gold_context_ids"][0]
    ctx["chunks"][cid]["metadata"]["effective_to"] = q["as_of_date"]
    assert "gold_not_in_force_at_query_date_or_unknown_start" in selection.rejection_reasons(q,ctx,policy)


def test_missing_clause_continuation_rejected(original):
    policy,ctx,_=original;ctx=deepcopy(ctx);q=ctx["dev"]["HN_007"]
    assert len(ctx["gold"][q["id"]]["gold_context_ids"]) > 1
    ctx["gold"][q["id"]]["gold_context_ids"].pop()
    assert "incomplete_clause_chunk_coverage" in selection.rejection_reasons(q,ctx,policy)


def test_citation_wrong_document_or_article_rejected(original):
    policy,ctx,rows=original;ctx=deepcopy(ctx);q=rows[0]
    ctx["gold"][q["id"]]["citations"][0]["article"]="999"
    assert "citation_article_mapping_mismatch" in selection.rejection_reasons(q,ctx,policy)


def test_count_duplicate_and_tampered_export_rejected(original):
    policy,ctx,rows=original
    assert selection.check_selection(rows[:-1],ctx,policy)
    bad=deepcopy(rows);bad[1]=deepcopy(bad[0])
    assert selection.check_selection(bad,ctx,policy)
    bad=deepcopy(rows);bad[0]["question"] += " edited"
    assert selection.check_selection(bad,ctx,policy)


def test_generated_artifact_contains_only_original_queries(original):
    policy,ctx,rows=original
    exported=json.loads((selection.ROOT/selection.QUERY_PATH).read_text(encoding="utf-8"))
    manifest=json.loads((selection.ROOT/selection.MANIFEST_PATH).read_text(encoding="utf-8"))
    assert exported==rows
    assert all(not selection.ANSWER_FIELDS & set(q) for q in exported)
    assert manifest["query_canonical_sha256"]==selection.canonical_hash(exported)
