"""Synthetic-only tests: never read Test questions or run a model/service."""
from __future__ import annotations

import copy
import json
import logging
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import precompute_test30_retrieval as precompute

pytestmark = [pytest.mark.req("FR2.10-AC1"), pytest.mark.req("FR2.10-AC2")]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def synthetic(tmp_path):
    # Only read shared YAML configuration; all questions, corpus and freezes are fake.
    corpus = tmp_path / "chunks.jsonl"
    corpus.write_text('{"chunk_id":"synthetic-1"}\n', encoding="utf-8")
    retrieval = yaml.safe_load((precompute.ROOT / "retrieval/config.yaml").read_text(encoding="utf-8"))
    retrieval["retrieval"]["corpus_path"] = str(corpus)
    retrieval_path = tmp_path / "retrieval.yaml"
    retrieval_path.write_text(yaml.safe_dump(retrieval), encoding="utf-8")
    rerank_path = tmp_path / "rerank.yaml"
    rerank_path.write_bytes((precompute.ROOT / "reranking/config.yaml").read_bytes())
    queries = [{"id": f"SYNTHETIC_{index:03}", "question": f"Synthetic question {index}",
                "split": "test", "as_of_date": "2020-01-01"} for index in range(30)]
    query_path = tmp_path / "queries.json"
    save(query_path, queries)
    questions_freeze = tmp_path / "questions_freeze.json"
    save(questions_freeze, {"question_count": 30, "test_ids": [row["id"] for row in queries],
                            "sha256": precompute._canonical_sha256(queries)})
    config_freeze = tmp_path / "config_freeze.json"
    save(config_freeze, {"top_k": 10, "sha256": {
        "corpus": precompute._file_sha256(corpus),
        "retrieval_config": precompute._file_sha256(retrieval_path),
        "reranking_config": precompute._file_sha256(rerank_path),
    }})
    paths = precompute.Inputs(query_path, questions_freeze, config_freeze, corpus, retrieval_path, rerank_path)
    _, snapshot = precompute.check_inputs(paths)
    raw = []
    for query in queries:
        hits = [{"chunk_id": f"synthetic-{index}", "chunk_text": f"Synthetic evidence {index}",
                 "document_id": "synthetic-law", "article_id": "synthetic-article",
                 "clause_id": f"synthetic-clause-{index}", "parent_clause_id": f"synthetic-clause-{index}",
                 "validity_status": "active", "effective_from": "2010-01-01", "effective_to": None,
                 "rank": index, "score": 1.0 / index, "rrf_score": 1.0 / index,
                 "retrieval_sources": ["bm25", "dense"], "metadata": {}} for index in (1, 2)]
        raw.append({"query_id": query["id"], "query": query["question"], "retriever": "hybrid",
                    "top_k": 50, "results": hits,
                    "config": {"as_of_date": query["as_of_date"], "as_of_date_source": "benchmark",
                               "parent_context": None, "top_k": 50,
                               "retriever": copy.deepcopy(snapshot["retriever"]), "reranker": None}})
    ranked = copy.deepcopy(raw)
    for row in ranked:
        row["retriever"] = "hybrid_reranker"
        row["config"]["reranker"] = copy.deepcopy(snapshot["reranker"])
        for hit in row["results"]:
            hit["reranker_score"] = hit["score"]
    state = {"branch": "synthetic-branch", "sha": "a" * 40, "working_tree_clean_excluding_output": True}
    models = {role: {"name": name, "revision": "b" * 40, "config_sha256": "c" * 64}
              for role, name in (("dense", snapshot["retriever"]["dense_model"]),
                                 ("reranker", snapshot["reranker"]["model"]))}
    approval = {"approved": True, "scope": "test30_retrieval_precompute", "approved_by": "synthetic-reviewer",
                "approved_at": "2026-11-26T10:00:00+07:00", "reference": "synthetic-review-reference",
                "git_sha": state["sha"], "inputs": snapshot, "models": models}
    approval_path = tmp_path / "approval.json"
    save(approval_path, approval)
    reasons = {row["id"]: "Synthetic pool contains only two chunks" for row in queries}
    reasons_path = tmp_path / "reasons.json"
    save(reasons_path, reasons)
    return SimpleNamespace(paths=paths, queries=queries, snapshot=snapshot, raw=raw, ranked=ranked,
                           state=state, models=models, approval=approval, approval_path=approval_path,
                           reasons=reasons, reasons_path=reasons_path, output=tmp_path / "output")


def test_readonly_preflight_keeps_four_top_k_meanings_separate(synthetic):
    _, snapshot = precompute.check_inputs(synthetic.paths)
    assert snapshot["top_k"] == {"retrieval_pool": 50, "reranked_pool": 50, "runtime_evidence": 5,
                                 "retrieval_result_default": 10, "legacy_evaluation": 10}
    assert not synthetic.output.exists()


@pytest.mark.parametrize("name", ["corpus", "retrieval", "rerank"])
def test_rejects_modified_frozen_bytes(synthetic, name):
    path = getattr(synthetic.paths, name)
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(precompute.PrecomputeError, match="hash mismatch"):
        precompute.check_inputs(synthetic.paths)


@pytest.mark.parametrize("damage", ["duplicate", "missing", "date", "split", "query_hash"])
def test_rejects_bad_query_inputs_without_changing_real_test_data(synthetic, damage):
    rows = copy.deepcopy(synthetic.queries)
    if damage == "duplicate":
        rows[1]["id"] = rows[0]["id"]
    elif damage == "missing":
        rows.pop()
    elif damage == "date":
        rows[0].pop("as_of_date")
    elif damage == "split":
        rows[0]["split"] = "dev"
    else:
        rows[0]["question"] = "Changed synthetic wording"
    save(synthetic.paths.queries, rows)
    # For schema cases, re-freeze this synthetic fixture to get past the hash gate.
    if damage in {"date", "split"}:
        frozen = precompute.read_json(synthetic.paths.questions_freeze)
        frozen["sha256"] = precompute._canonical_sha256(rows)
        save(synthetic.paths.questions_freeze, frozen)
    with pytest.raises(precompute.PrecomputeError):
        precompute.check_inputs(synthetic.paths)


def test_input_hashing_accepts_windows_newlines(synthetic):
    for path in (synthetic.paths.corpus, synthetic.paths.retrieval, synthetic.paths.rerank):
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert precompute.check_inputs(synthetic.paths)[1] == synthetic.snapshot


def test_pool_and_source_compatible_with_dev5_consumer(synthetic):
    summary = precompute.validate_records(synthetic.ranked, synthetic.queries, synthetic.snapshot,
                                         reranked=True, short_reasons=synthetic.reasons)
    assert len(summary) == 30
    assert all(item["candidate_count"] == 2 for item in summary.values())
    precompute.validate_same_pool(synthetic.raw, synthetic.ranked)


@pytest.mark.parametrize("damage", ["date", "query", "corpus", "model", "candidate_text", "rrf",
                                   "mock", "parent", "rank", "duplicate_chunk", "missing_id", "duplicate_id",
                                   "too_many", "score", "sort", "future", "top_k"])
def test_checker_rejects_corrupted_synthetic_artifacts(synthetic, damage):
    records = copy.deepcopy(synthetic.ranked)
    row = records[0]
    if damage == "date":
        row["config"]["as_of_date"] = "2020-01-02"
    elif damage == "query":
        row["query"] = "Another synthetic question"
    elif damage == "corpus":
        row["config"]["retriever"]["corpus_sha256"] = "0" * 64
    elif damage == "model":
        row["config"]["reranker"]["model"] = "wrong-model"
    elif damage == "candidate_text":
        row["config"]["reranker"]["candidate_text"] = "chunk_text"
    elif damage == "rrf":
        row["config"]["retriever"]["rrf_k"] = 10
    elif damage == "mock":
        row["retriever"] = "hybrid_mock_reranker"
    elif damage == "parent":
        row["config"]["parent_context"] = {"enabled": True}
    elif damage == "rank":
        row["results"][0]["rank"] = 2
    elif damage == "duplicate_chunk":
        row["results"][1]["chunk_id"] = row["results"][0]["chunk_id"]
    elif damage == "missing_id":
        records.pop()
    elif damage == "duplicate_id":
        records[1]["query_id"] = row["query_id"]
    elif damage == "too_many":
        row["results"] *= 26
    elif damage == "score":
        row["results"][0]["reranker_score"] = float("nan")
    elif damage == "sort":
        row["results"][1]["reranker_score"] = 2.0
    elif damage == "future":
        row["results"][0]["effective_from"] = "2030-01-01"
    else:
        row["top_k"] = 5
    with pytest.raises(precompute.PrecomputeError):
        precompute.validate_records(records, synthetic.queries, synthetic.snapshot, reranked=True,
                                    short_reasons=synthetic.reasons)


def test_short_pool_requires_documented_reason(synthetic):
    with pytest.raises(precompute.PrecomputeError, match="short pool needs"):
        precompute.validate_records(synthetic.raw, synthetic.queries, synthetic.snapshot, reranked=False)


def test_reranking_must_preserve_evidence_and_candidate_set(synthetic):
    ranked = copy.deepcopy(synthetic.ranked)
    ranked[0]["results"][0]["chunk_text"] = "Changed evidence"
    with pytest.raises(precompute.PrecomputeError, match="changed evidence"):
        precompute.validate_same_pool(synthetic.raw, ranked)
    ranked = copy.deepcopy(synthetic.ranked)
    ranked[0]["results"].pop()
    with pytest.raises(precompute.PrecomputeError, match="changed candidate pool"):
        precompute.validate_same_pool(synthetic.raw, ranked)


def test_same_pool_accepts_actual_production_serializer_provenance(synthetic):
    from reranking.pipeline import to_contract_result

    raw = copy.deepcopy(synthetic.raw)
    for record in raw:
        record["results"] = [to_contract_result({**row, "source_ranks": {"bm25": row["rank"]},
                                                "source_scores": {"bm25": row["score"]}})
                             for row in record["results"]]
    ranked = copy.deepcopy(raw)
    for record in ranked:
        record["results"] = [to_contract_result({**row, "retrieval_rank": row["rank"],
                                                "retrieval_score": row["score"], "score": 0.9 / row["rank"]})
                             for row in record["results"]]
    assert ranked[0]["results"][0]["source_ranks"] == {"bm25": 1, "retrieval": 1}
    precompute.validate_same_pool(raw, ranked)


@pytest.mark.parametrize("field", ["source_ranks", "source_scores"])
@pytest.mark.parametrize("damage", ["original_branch", "wrong_retrieval", "unknown_source"])
def test_provenance_extension_cannot_rewrite_existing_branch_or_invent_values(synthetic, field, damage):
    raw = copy.deepcopy(synthetic.raw)
    raw[0]["results"][0][field] = {"bm25": 1}
    ranked = copy.deepcopy(raw)
    result = ranked[0]["results"][0]
    if damage == "original_branch":
        result[field]["bm25"] = 2
    elif damage == "wrong_retrieval":
        result[field]["retrieval"] = 999
    else:
        result[field]["invented"] = 1
    with pytest.raises(precompute.PrecomputeError):
        precompute.validate_same_pool(raw, ranked)


@pytest.mark.parametrize("damage", ["pending", "scope", "sha", "inputs", "reviewer", "timezone", "dirty"])
def test_run_requires_recorded_approval_for_exact_inputs(synthetic, damage):
    approval = copy.deepcopy(synthetic.approval)
    state = dict(synthetic.state)
    if damage == "pending":
        approval["approved"] = False
    elif damage == "scope":
        approval["scope"] = "other"
    elif damage == "sha":
        approval["git_sha"] = "d" * 40
    elif damage == "inputs":
        approval["inputs"]["top_k"]["runtime_evidence"] = 10
    elif damage == "reviewer":
        approval["approved_by"] = ""
    elif damage == "timezone":
        approval["approved_at"] = "2026-11-26T10:00:00"
    else:
        state["working_tree_clean_excluding_output"] = False
    with pytest.raises(precompute.PrecomputeError):
        precompute.validate_approval(approval, synthetic.snapshot, state)


@pytest.fixture
def fake_runtime(synthetic, monkeypatch):
    calls = []
    monkeypatch.setattr(precompute, "git_state", lambda output=None: dict(synthetic.state))
    monkeypatch.setattr(precompute, "cached_model_versions", lambda snapshot: copy.deepcopy(synthetic.models))
    monkeypatch.setattr(precompute, "runtime_metadata", lambda: {
        "python": "synthetic", "os": "synthetic", "cpu": "synthetic", "packages": {}, "model_downloads": "disabled"})
    monkeypatch.setattr(precompute, "check_services", lambda paths, snapshot, args: {
        "verified": True, "queries_executed": 0,
        "elasticsearch": {"corpus_sha256": snapshot["hashes"]["corpus"]},
        "qdrant": {"model": snapshot["retriever"]["dense_model"], "dimension": snapshot["retriever"]["dimension"],
                   "corpus_sha256": snapshot["hashes"]["corpus"], "chunk_count": 2}})

    def run(command, **kwargs):
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"
        assert "run_retrieval.py" in command[1]
        assert "--no-parent-context" in command
        assert command[command.index("--top-k") + 1] == "50"
        assert command[command.index("--retrieval-top-k") + 1] == "50"
        output = Path(command[command.index("--output") + 1])
        records = synthetic.raw if output.name == "candidates.json" else synthetic.ranked
        save(output, records)
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(precompute.subprocess, "run", run)
    args = Namespace(elasticsearch_url="http://synthetic.invalid:9200", qdrant_url=None, qdrant_path=None,
                     short_pool_reasons=synthetic.reasons_path)
    return args, calls


@pytest.mark.req("FR9.8-AC1")
def test_two_phase_wrapper_and_manifest_chain_without_inference(synthetic, fake_runtime):
    args, calls = fake_runtime
    precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=False)
    precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=True)
    manifest = precompute.verify_phase(synthetic.output, synthetic.paths, True)
    assert manifest["status"] == "COMPLETE"
    assert manifest["models"] == synthetic.models
    assert len(calls) == 2
    assert calls[0][calls[0].index("--reranker") + 1] == "none"
    assert calls[1][calls[1].index("--retriever") + 1] == "precomputed"
    before = (synthetic.output / "reranked.json").read_bytes()
    with pytest.raises(precompute.PrecomputeError, match="overwrite"):
        precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=True)
    assert len(calls) == 2 and (synthetic.output / "reranked.json").read_bytes() == before
    with pytest.raises(precompute.PrecomputeError, match="overwrite"):
        precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=False)


@pytest.mark.parametrize("damage", ["artifact_hash", "manifest_config", "model_revision", "runtime", "timestamps"])
def test_manifest_checker_rejects_hash_config_and_provenance_damage(synthetic, fake_runtime, damage):
    args, _ = fake_runtime
    precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=False)
    precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=True)
    path = synthetic.output / "reranked_manifest.json"
    manifest = precompute.read_json(path)
    if damage == "artifact_hash":
        artifact = synthetic.output / "reranked.json"
        artifact.write_bytes(artifact.read_bytes() + b" ")
    elif damage == "manifest_config":
        manifest["inputs"]["hashes"]["corpus"] = "0" * 64
    elif damage == "model_revision":
        manifest["models"]["dense"]["revision"] = "0" * 40
    elif damage == "runtime":
        manifest.pop("runtime")
    else:
        manifest["finished_at"] = "2000-01-01T00:00:00Z"
    save(path, manifest)
    with pytest.raises(precompute.PrecomputeError):
        precompute.verify_phase(synthetic.output, synthetic.paths, True)


def test_revision_drift_stops_before_second_subprocess(synthetic, fake_runtime, monkeypatch):
    args, calls = fake_runtime
    precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=False)
    changed = copy.deepcopy(synthetic.models)
    changed["reranker"]["revision"] = "d" * 40
    monkeypatch.setattr(precompute, "cached_model_versions", lambda snapshot: changed)
    with pytest.raises(precompute.PrecomputeError, match="approved revisions"):
        precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=True)
    assert len(calls) == 1 and not (synthetic.output / "reranked.json").exists()


def test_failed_subprocess_does_not_get_complete_manifest_or_retry(synthetic, fake_runtime, monkeypatch):
    args, calls = fake_runtime
    monkeypatch.setattr(precompute.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    with pytest.raises(precompute.PrecomputeError, match="subprocess failed"):
        precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=False)
    assert (synthetic.output / "candidates.lock.json").exists()
    assert not (synthetic.output / "candidates_manifest.json").exists()
    with pytest.raises(precompute.PrecomputeError, match="overwrite"):
        precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=False)
    assert calls == []


def test_observed_short_pool_reasons_are_recorded_and_inherited(synthetic, fake_runtime):
    args, _ = fake_runtime
    args.short_pool_reasons = None
    for row in synthetic.raw:
        row["stats"] = {"retrieved_candidates": 2, "duplicates_removed": 0}
    precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=False)
    precompute.run_phase(synthetic.paths, synthetic.output, synthetic.approval_path, args, reranked=True)
    manifest = precompute.verify_phase(synthetic.output, synthetic.paths, True)
    assert all("UPSTREAM_RETURNED_FEWER_THAN_LIMIT" in item["short_pool_reason"] for item in manifest["pools"].values())


def test_prepare_approval_creates_pending_draft_without_inference(synthetic, fake_runtime, monkeypatch):
    _, calls = fake_runtime
    monkeypatch.setattr(precompute, "Inputs", lambda: synthetic.paths)
    draft = synthetic.approval_path.with_name("pending.json")
    assert precompute.main(["prepare-approval", "--approval-file", str(draft)]) == 0
    approval = precompute.read_json(draft)
    assert approval["approved"] is False and approval["approved_by"] is None
    assert approval["models"] == synthetic.models and approval["inputs"] == synthetic.snapshot
    with pytest.raises(precompute.PrecomputeError, match="approval"):
        precompute.validate_approval(approval, synthetic.snapshot, synthetic.state)
    assert precompute.main(["prepare-approval", "--approval-file", str(draft)]) == 1
    assert calls == [] and not synthetic.output.exists()


@pytest.mark.parametrize("mismatch", [None, "corpus", "model", "dimension"])
def test_service_preflight_checks_metadata_without_query_or_embedding(synthetic, monkeypatch, mismatch):
    from reranking import pipeline

    closes = []
    corpus_hash = synthetic.snapshot["hashes"]["corpus"]
    metadata = {"corpus_sha256": corpus_hash,
                "model_name": synthetic.snapshot["retriever"]["dense_model"], "dimension": 1024}
    if mismatch:
        metadata[{"corpus": "corpus_sha256", "model": "model_name", "dimension": "dimension"}[mismatch]] = "wrong"
    client = SimpleNamespace(close=lambda: closes.append(True))
    hybrid = SimpleNamespace(
        bm25_index=SimpleNamespace(client=client, _verify_index_tokenizer=lambda: {"corpus_sha256": corpus_hash}),
        dense_retriever=SimpleNamespace(use_mock=False, verify_index=lambda expected: metadata,
                                       vector_store=SimpleNamespace(use_qdrant=True, persistent=True,
                                                                    count=lambda: 2, client=client)),
    )
    monkeypatch.setattr(pipeline, "build_hybrid_retriever", lambda *a, **kw: hybrid)
    args = Namespace(elasticsearch_url="http://synthetic.invalid", qdrant_path=None, qdrant_url=None)
    logging_threshold = logging.root.manager.disable
    if mismatch:
        with pytest.raises(precompute.PrecomputeError, match="Qdrant"):
            precompute.check_services(synthetic.paths, synthetic.snapshot, args)
    else:
        assert precompute.check_services(synthetic.paths, synthetic.snapshot, args)["queries_executed"] == 0
    assert len(closes) == 2
    assert logging.root.manager.disable == logging_threshold
