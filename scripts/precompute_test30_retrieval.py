"""Prepare, run and verify the frozen Test30 retrieval handoff (no Qwen calls).

check-inputs is read-only and does not contact services or load models.
retrieve/rerank require a recorded approval, committed code and cached models.
Each phase runs in a separate process and never overwrites an existing artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import math
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.test_run_freeze import _canonical_sha256, _file_sha256  # noqa: E402
from orchestration.rag_pipeline import PrecomputedRerankedSource  # noqa: E402
from reranking.reranker import build_reranker, load_reranker_config  # noqa: E402
from retrieval.settings import load_settings  # noqa: E402
from retrieval.temporal import normalize_as_of_date, is_effective_at  # noqa: E402
from schemas.models import CandidateChunk  # noqa: E402

VERSION = "sprint12.test30.precompute.v1"
POOL_K = 50


class PrecomputeError(ValueError):
    """Fail closed before an unverified artifact can be handed off."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PrecomputeError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def byte_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: Any) -> None:
    # Exclusive create is also the phase lock; partial/failed outputs are retained.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


@dataclass(frozen=True)
class Inputs:
    queries: Path = ROOT / "data/benchmark/queries_test.json"
    questions_freeze: Path = ROOT / "docs/test_questions_freeze.json"
    config_freeze: Path = ROOT / "docs/test_run_config_freeze.json"
    corpus: Path = ROOT / "data/chunking_output/chunks.jsonl"
    retrieval: Path = ROOT / "retrieval/config.yaml"
    rerank: Path = ROOT / "reranking/config.yaml"


def check_inputs(paths: Inputs) -> tuple[list[dict], dict]:
    queries = read_json(paths.queries)
    freeze = read_json(paths.questions_freeze)
    require(isinstance(queries, list) and len(queries) == 30, "Expected exactly 30 Test queries")
    require(all(isinstance(row, dict) for row in queries), "Invalid query record")
    ids = [row.get("id") for row in queries]
    require(all(isinstance(qid, str) and qid and qid == qid.strip() for qid in ids), "Invalid Test ID")
    require(len(set(ids)) == 30, "Duplicate Test IDs")
    require(freeze.get("question_count") == 30 and freeze.get("test_ids") == ids, "Frozen Test IDs mismatch")
    require(freeze.get("sha256") == _canonical_sha256(queries), "Frozen query hash mismatch")
    for row in queries:
        qid = row["id"]
        require(row.get("split") == "test", f"{qid}: expected Test split")
        require(isinstance(row.get("question"), str) and bool(row["question"].strip()), f"{qid}: missing question")
        require(isinstance(row.get("as_of_date"), str) and bool(row["as_of_date"]), f"{qid}: missing as_of_date")
        require(normalize_as_of_date(row["as_of_date"]) == row["as_of_date"], f"{qid}: invalid as_of_date")

    frozen_config = read_json(paths.config_freeze)
    hashes = {"corpus": _file_sha256(paths.corpus), "retrieval_config": _file_sha256(paths.retrieval),
              "reranking_config": _file_sha256(paths.rerank)}
    for key, value in hashes.items():
        require((frozen_config.get("sha256") or {}).get(key) == value, f"Frozen {key} hash mismatch")
    cfg = load_settings(paths.retrieval)
    rerank = load_reranker_config(paths.rerank)
    require(cfg["retrieval"]["retrieval_top_k"] == POOL_K, "Expected retrieval_top_k=50")
    require(rerank.enabled and rerank.backend == "cross_encoder", "Mock/disabled reranker is forbidden")
    require(rerank.max_candidates == POOL_K and rerank.rerank_top_k == 5, "Expected pool=50 and runtime evidence=5")
    require(rerank.candidate_text == "document_breadcrumb_chunk_text", "Unexpected candidate_text")
    require(cfg["bm25"]["backend"] == "elasticsearch" and cfg["dense"]["backend"] == "qdrant",
            "Expected Elasticsearch and Qdrant")
    # The CLI resolves corpus paths relative to the repository, independently of this wrapper.
    corpus_path = Path(cfg["retrieval"]["corpus_path"])
    if not corpus_path.is_absolute():
        corpus_path = ROOT / corpus_path
    require(corpus_path.resolve() == paths.corpus.resolve(), "Configured corpus path mismatch")
    spec = cfg["dense"]["supported_models"][cfg["dense"]["model"]]
    snapshot = {
        "hashes": {**hashes, "queries": _file_sha256(paths.queries),
                   "questions_freeze": _file_sha256(paths.questions_freeze),
                   "config_freeze": _file_sha256(paths.config_freeze)},
        "query_ids": ids,
        "dates": {row["id"]: row["as_of_date"] for row in queries},
        "query_payload_sha256": _canonical_sha256(queries),
        "top_k": {"retrieval_pool": POOL_K, "reranked_pool": POOL_K,
                  "runtime_evidence": rerank.rerank_top_k,
                  "retrieval_result_default": cfg["retrieval"]["result_top_k"],
                  "legacy_evaluation": frozen_config.get("top_k")},
        "retriever": {"backend": "hybrid", "retrieval_top_k": POOL_K,
                      "rrf_k": cfg["hybrid"]["rrf_k"], "fusion": cfg["hybrid"]["fusion"],
                      "dense_model": cfg["dense"]["model"], "dimension": spec["dimension"],
                      "collection": cfg["dense"]["collection"], "bm25_index": cfg["bm25"]["index"],
                      "corpus_sha256": hashes["corpus"]},
        "reranker": build_reranker(rerank).describe(),
    }
    return queries, snapshot


def validate_records(records: Any, queries: list[dict], snapshot: dict, *, reranked: bool,
                     short_reasons: dict | None = None) -> dict:
    require(isinstance(records, list) and len(records) == 30, "Artifact must contain exactly 30 records")
    require(all(isinstance(row, dict) for row in records), "Invalid artifact record")
    ids = [row.get("query_id") for row in records]
    require(ids == snapshot["query_ids"], "Artifact IDs missing, duplicated or reordered")
    summaries = {}
    for record, query in zip(records, queries):
        qid = query["id"]
        require(record.get("query") == query["question"].strip(), f"{qid}: query mismatch")
        cfg = record.get("config") or {}
        require(isinstance(cfg, dict), f"{qid}: invalid config snapshot")
        require(cfg.get("as_of_date") == query["as_of_date"], f"{qid}: as_of_date mismatch")
        require(cfg.get("as_of_date_source") == "benchmark", f"{qid}: date source mismatch")
        require(cfg.get("parent_context") is None, f"{qid}: parent context must be disabled")
        require(record.get("top_k") == POOL_K and cfg.get("top_k") == POOL_K, f"{qid}: output Top-k mismatch")
        require(record.get("retriever") == ("hybrid_reranker" if reranked else "hybrid"), f"{qid}: mock/invalid source")
        for key, expected in snapshot["retriever"].items():
            require((cfg.get("retriever") or {}).get(key) == expected, f"{qid}: retriever.{key} mismatch")
        require(cfg.get("reranker") == (snapshot["reranker"] if reranked else None), f"{qid}: reranker mismatch")
        rows = record.get("results")
        require(isinstance(rows, list) and len(rows) <= POOL_K, f"{qid}: candidate pool exceeds 50 or invalid")
        chunk_ids = [row.get("chunk_id") for row in rows if isinstance(row, dict)]
        require(len(chunk_ids) == len(rows) and len(set(chunk_ids)) == len(rows), f"{qid}: duplicate/invalid chunks")
        previous_score = math.inf
        for rank, row in enumerate(rows, 1):
            require(type(row.get("rank")) is int and row["rank"] == rank, f"{qid}: non-contiguous ranks")
            require(not row.get("parent_text"), f"{qid}: parent text must not be attached to precompute pool")
            try:
                CandidateChunk.from_retrieval_item(row, qid, query["as_of_date"], retriever=record["retriever"])
            except ValueError as exc:
                raise PrecomputeError(f"{qid}: invalid candidate fields") from exc
            require(is_effective_at(row, query["as_of_date"]), f"{qid}: ineffective candidate")
            score = row.get("reranker_score") if reranked else row.get("score")
            require(type(score) in (int, float) and math.isfinite(score), f"{qid}: invalid score")
            require(score <= previous_score, f"{qid}: scores not sorted")
            previous_score = score
        reason = (short_reasons or {}).get(qid)
        if len(rows) < POOL_K:
            require(isinstance(reason, str) and bool(reason.strip()), f"{qid}: short pool needs explicit reason")
        summaries[qid] = {"candidate_count": len(rows), "short_pool_reason": reason if len(rows) < POOL_K else None}
    if reranked:
        source = PrecomputedRerankedSource(records, expected_corpus_sha256=snapshot["hashes"]["corpus"],
                                         expected_candidate_text=snapshot["reranker"]["candidate_text"],
                                         expected_settings={"retriever": snapshot["retriever"],
                                                            "reranker": snapshot["reranker"]})
        for query in queries:
            source.fetch(query_id=query["id"], query=query["question"], as_of_date=query["as_of_date"])
    return summaries


def observed_short_reasons(records: list[dict]) -> dict[str, str]:
    """Describe observed pool exhaustion; do not invent a legal/semantic cause."""
    reasons = {}
    for record in records:
        count = len(record.get("results", []))
        stats = record.get("stats") or {}
        retrieved = stats.get("retrieved_candidates")
        duplicates = stats.get("duplicates_removed", 0)
        if (count < POOL_K and type(retrieved) is int and type(duplicates) is int
                and 0 <= retrieved <= POOL_K and duplicates >= 0 and retrieved - duplicates == count):
            reason = "UPSTREAM_RETURNED_FEWER_THAN_LIMIT" if retrieved < POOL_K else "DUPLICATES_REMOVED"
            reasons[record["query_id"]] = f"{reason}: retrieved={retrieved}, duplicates={duplicates}, returned={count}, limit={POOL_K}"
    return reasons


def validate_same_pool(raw: list[dict], ranked: list[dict]) -> None:
    for original, reranked in zip(raw, ranked):
        qid = original["query_id"]
        before = {row["chunk_id"]: row for row in original["results"]}
        after = {row["chunk_id"]: row for row in reranked["results"]}
        require(set(before) == set(after), f"{qid}: reranker changed candidate pool")
        for chunk_id, row in before.items():
            # Reranking may change only placement/scoring fields, never evidence.
            for key, value in row.items():
                if key not in {"rank", "score", "reranker_score", "retrieval_rank", "retrieval_score"}:
                    require(after[chunk_id].get(key) == value, f"{qid}: reranker changed evidence field {key}")


def git_state(output: Path | None = None) -> dict:
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").strip()
    dirty = git("status", "--porcelain", "--untracked-files=all", "--", ".",
                *([f":(exclude){output.resolve().relative_to(ROOT).as_posix()}/**"]
                  if output and output.resolve().is_relative_to(ROOT) else []))
    return {"branch": git("branch", "--show-current"), "sha": git("rev-parse", "HEAD"),
            "working_tree_clean_excluding_output": not bool(dirty)}


def validate_approval(approval: Any, snapshot: dict, state: dict) -> None:
    require(isinstance(approval, dict) and approval.get("approved") is True, "Recorded configuration approval is required")
    for key in ("approved_by", "approved_at", "reference"):
        require(isinstance(approval.get(key), str) and bool(approval[key].strip()), f"Approval missing {key}")
    require(approval.get("scope") == "test30_retrieval_precompute", "Wrong approval scope")
    require(approval.get("git_sha") == state["sha"], "Approval Git SHA mismatch")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", state["sha"] or "")), "Invalid source Git SHA")
    require(approval.get("inputs") == snapshot, "Approval inputs/config mismatch")
    approved_at = datetime.fromisoformat(approval["approved_at"])
    require(approved_at.tzinfo is not None, "Approval timestamp must include timezone")
    require(state["working_tree_clean_excluding_output"], "Commit code and input changes before running Test precompute")


def cached_model_versions(snapshot: dict) -> dict:
    # The subprocess is offline, so the cached main revision cannot change through
    # a download between this check and model load. Check again after the phase.
    from huggingface_hub import try_to_load_from_cache
    versions = {}
    for role, name in (("dense", snapshot["retriever"]["dense_model"]),
                       ("reranker", snapshot["reranker"]["model"])):
        cached = try_to_load_from_cache(name, "config.json", revision="main")
        require(isinstance(cached, str) and Path(cached).is_file(), f"Cached {role} model config missing; prepare cache first")
        revision = Path(cached).parent.name
        require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)), f"Cannot identify immutable {role} model revision")
        versions[role] = {"name": name, "revision": revision, "config_sha256": byte_hash(Path(cached))}
    return versions


def runtime_metadata() -> dict:
    packages = {}
    for name in ("sentence-transformers", "transformers", "torch", "qdrant-client", "elasticsearch", "underthesea"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "os": platform.platform(),
            "cpu": platform.processor(), "packages": packages, "model_downloads": "disabled"}


def check_services(paths: Inputs, snapshot: dict, args: argparse.Namespace) -> dict:
    """Read index metadata/counts without embedding or searching any question."""
    from reranking.pipeline import build_hybrid_retriever, load_retrieval_settings

    require(bool(args.elasticsearch_url), "--elasticsearch-url or ELASTICSEARCH_URL is required")
    hybrid = None
    previous_logging_threshold = logging.root.manager.disable
    # Retry logs may contain endpoint credentials or raw provider exceptions.
    logging.disable(logging.CRITICAL)
    try:
        settings = load_retrieval_settings(paths.retrieval)
        hybrid = build_hybrid_retriever(settings, elasticsearch_url=args.elasticsearch_url,
                                        qdrant_url=args.qdrant_url, qdrant_path=args.qdrant_path)
        sparse, dense = hybrid.bm25_index, hybrid.dense_retriever
        store = dense.vector_store
        require(store.use_qdrant and store.persistent and not dense.use_mock, "Real persistent Qdrant is required")
        sparse_meta = sparse._verify_index_tokenizer()
        dense_meta = dense.verify_index(snapshot["hashes"]["corpus"])
        require(sparse_meta.get("corpus_sha256") == snapshot["hashes"]["corpus"], "Elasticsearch corpus mismatch")
        require(dense_meta.get("corpus_sha256") == snapshot["hashes"]["corpus"], "Qdrant corpus mismatch")
        require(dense_meta.get("model_name") == snapshot["retriever"]["dense_model"]
                and dense_meta.get("dimension") == snapshot["retriever"]["dimension"], "Qdrant model/dimension mismatch")
        count = store.count()
        require(type(count) is int and count > 0, "Qdrant collection is empty")
        return {"verified": True, "queries_executed": 0,
                "elasticsearch": {key: sparse_meta.get(key) for key in
                                  ("corpus_sha256", "bm25_tokenizer", "bm25_tokenizer_version", "bm25_text_field")},
                "qdrant": {"model": dense_meta["model_name"], "dimension": dense_meta["dimension"],
                            "corpus_sha256": dense_meta["corpus_sha256"], "chunk_count": count}}
    except PrecomputeError:
        raise
    except Exception as exc:
        raise PrecomputeError(f"Index metadata preflight failed: {type(exc).__name__}; check services/dependencies") from exc
    finally:
        try:
            if hybrid is not None:
                for client in (hybrid.bm25_index.client, hybrid.dense_retriever.vector_store.client):
                    close = getattr(client, "close", None)
                    if callable(close):
                        close()
        finally:
            logging.disable(previous_logging_threshold)


def stage_command(paths: Inputs, output: Path, reranked: bool, args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(ROOT / "scripts/run_retrieval.py"), "--queries", str(paths.queries),
               "--allow-test-split", "--retrieval-config", str(paths.retrieval), "--config", str(paths.rerank),
               "--no-parent-context", "--top-k", "50", "--retrieval-top-k", "50"]
    if reranked:
        command += ["--retriever", "precomputed", "--candidates", str(output / "candidates.json"),
                    "--reranker", "cross_encoder", "--output", str(output / "reranked.json")]
    else:
        require(bool(args.elasticsearch_url), "--elasticsearch-url or ELASTICSEARCH_URL is required")
        command += ["--retriever", "hybrid", "--reranker", "none", "--output", str(output / "candidates.json"),
                    "--elasticsearch-url", args.elasticsearch_url]
        if args.qdrant_url:
            command += ["--qdrant-url", args.qdrant_url]
        if args.qdrant_path:
            command += ["--qdrant-path", args.qdrant_path]
    return command


def verify_phase(output: Path, paths: Inputs, reranked: bool) -> dict:
    queries, snapshot = check_inputs(paths)
    name = "reranked" if reranked else "candidates"
    manifest = read_json(output / f"{name}_manifest.json")
    require(isinstance(manifest, dict), "Manifest must be a JSON object")
    require(manifest.get("manifest_version") == VERSION and manifest.get("status") == "COMPLETE", "Incomplete/invalid manifest")
    require(manifest.get("phase") == name and manifest.get("inputs") == snapshot, "Manifest config/input mismatch")
    require(manifest.get("artifact_sha256") == byte_hash(output / f"{name}.json"), "Artifact hash mismatch")
    validate_approval(manifest.get("approval"), snapshot,
                      {"sha": manifest.get("git", {}).get("sha"), "working_tree_clean_excluding_output": True})
    require(manifest.get("git", {}).get("working_tree_clean_excluding_output") is True, "Run was not clean")
    require(isinstance(manifest.get("git", {}).get("branch"), str) and bool(manifest["git"]["branch"]), "Missing source branch")
    runtime = manifest.get("runtime")
    require(isinstance(runtime, dict) and all(key in runtime for key in ("python", "os", "cpu", "packages")), "Missing runtime metadata")
    require(runtime.get("model_downloads") == "disabled", "Model downloads must be disabled")
    started = datetime.fromisoformat(manifest.get("started_at", ""))
    finished = datetime.fromisoformat(manifest.get("finished_at", ""))
    require(started.tzinfo is not None and finished.tzinfo is not None and finished >= started, "Invalid phase timestamps")
    require(manifest.get("models") == manifest["approval"].get("models"), "Approved model revisions mismatch")
    services = manifest.get("services", {})
    require(services.get("verified") is True and services.get("queries_executed") == 0, "Missing index verification")
    require(services.get("elasticsearch", {}).get("corpus_sha256") == snapshot["hashes"]["corpus"], "ES provenance mismatch")
    dense = services.get("qdrant", {})
    require(dense.get("corpus_sha256") == snapshot["hashes"]["corpus"]
            and dense.get("model") == snapshot["retriever"]["dense_model"]
            and dense.get("dimension") == snapshot["retriever"]["dimension"], "Qdrant provenance mismatch")
    for role in ("dense", "reranker"):
        model = (manifest.get("models") or {}).get(role, {})
        expected = snapshot["retriever"]["dense_model"] if role == "dense" else snapshot["reranker"]["model"]
        require(model.get("name") == expected and bool(re.fullmatch(r"[0-9a-f]{40}", model.get("revision", "")))
                and bool(re.fullmatch(r"[0-9a-f]{64}", model.get("config_sha256", ""))), f"Invalid {role} model provenance")
    records = read_json(output / f"{name}.json")
    reasons = {qid: item.get("short_pool_reason") for qid, item in manifest.get("pools", {}).items()}
    summaries = validate_records(records, queries, snapshot, reranked=reranked, short_reasons=reasons)
    require(summaries == manifest.get("pools"), "Pool summary mismatch")
    if reranked:
        raw_manifest = verify_phase(output, paths, False)
        require(manifest.get("candidates_manifest_sha256") == byte_hash(output / "candidates_manifest.json"), "Candidate manifest hash mismatch")
        require(manifest.get("models") == raw_manifest.get("models") and manifest.get("git") == raw_manifest.get("git"),
                "Two-stage model/code provenance mismatch")
        validate_same_pool(read_json(output / "candidates.json"), records)
    return manifest


def run_phase(paths: Inputs, output: Path, approval_path: Path, args: argparse.Namespace, *, reranked: bool) -> None:
    queries, snapshot = check_inputs(paths)
    state = git_state(output)
    approval = read_json(approval_path)
    validate_approval(approval, snapshot, state)
    if not reranked:
        require(not output.exists(), "Refuse to overwrite existing output directory")
    models = cached_model_versions(snapshot)
    require(approval.get("models") == models, "Cached models differ from approved revisions")
    name = "reranked" if reranked else "candidates"
    command = stage_command(paths, output, reranked, args)
    if reranked:
        raw_manifest = verify_phase(output, paths, False)
        require(raw_manifest["git"] == state and raw_manifest["models"] == models, "Phase inputs/model/code changed")
        require(not (output / "reranked.json").exists() and not (output / "reranked_manifest.json").exists(), "Refuse to overwrite reranked output")
    else:
        services = check_services(paths, snapshot, args)
        output.mkdir(parents=True, exist_ok=False)
    write_new(output / f"{name}.lock.json", {"phase": name, "started_at": datetime.now(timezone.utc).isoformat()})
    started = datetime.now(timezone.utc).isoformat()
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
    require(result.returncode == 0, f"{name}: retrieval subprocess failed, exit={result.returncode}; output retained, do not overwrite")
    require(check_inputs(paths)[1] == snapshot and git_state(output) == state, "Inputs/code changed during phase")
    require(cached_model_versions(snapshot) == models, "Cached model revision changed during phase")
    records = read_json(output / f"{name}.json")
    reasons = ({qid: item["short_pool_reason"] for qid, item in raw_manifest["pools"].items()}
               if reranked else observed_short_reasons(records))
    if args.short_pool_reasons:
        provided = read_json(args.short_pool_reasons)
        require(isinstance(provided, dict), "Short pool reasons must be an ID-to-reason JSON object")
        require(set(provided) <= set(snapshot["query_ids"]), "Unknown IDs in short-pool reasons")
        reasons.update(provided)
    summaries = validate_records(records, queries, snapshot, reranked=reranked, short_reasons=reasons)
    if reranked:
        validate_same_pool(read_json(output / "candidates.json"), records)
    manifest = {"manifest_version": VERSION, "phase": name, "status": "COMPLETE", "git": state,
                "inputs": snapshot, "models": models, "approval": approval, "runtime": runtime_metadata(),
                "services": raw_manifest["services"] if reranked else services,
                "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
                "artifact_sha256": byte_hash(output / f"{name}.json"), "pools": summaries,
                "note": "Retrieval-only manifest; not the A/B generation manifest required by NFR4.2."}
    if reranked:
        manifest["candidates_manifest_sha256"] = byte_hash(output / "candidates_manifest.json")
    write_new(output / f"{name}_manifest.json", manifest)
    verify_phase(output, paths, reranked)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("check-inputs", "check-models", "check-services", "prepare-approval",
                                         "retrieve", "rerank", "verify"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--short-pool-reasons", type=Path)
    parser.add_argument("--elasticsearch-url", default=os.getenv("ELASTICSEARCH_URL"))
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL"))
    parser.add_argument("--qdrant-path", default=os.getenv("QDRANT_PATH"))
    args = parser.parse_args(argv)
    try:
        paths = Inputs()
        if args.phase in ("check-inputs", "check-models", "check-services", "prepare-approval"):
            _, snapshot = check_inputs(paths)
            payload = {"status": "INPUTS_VALID", "inputs": snapshot, "git": git_state(),
                       "services_verified": False, "approval_verified": False}
            if args.phase in ("check-models", "prepare-approval"):
                payload["models"] = cached_model_versions(snapshot)
            if args.phase == "check-services":
                payload["services"] = check_services(paths, snapshot, args)
                payload["services_verified"] = True
            if args.phase == "prepare-approval":
                require(args.approval_file is not None, "--approval-file is required for the draft")
                write_new(args.approval_file, {"approved": False, "scope": "test30_retrieval_precompute",
                          "approved_by": None, "approved_at": None, "reference": None,
                          "git_sha": payload["git"]["sha"], "inputs": snapshot, "models": payload["models"]})
                print("PENDING approval draft created; no retrieval executed")
            else:
                print(json.dumps(payload, indent=2))
        else:
            require(args.output_dir is not None, "--output-dir is required")
            output = args.output_dir.resolve()
            if args.phase == "verify":
                verify_phase(output, paths, True)
            else:
                require(args.approval_file is not None, "--approval-file is required")
                run_phase(paths, output, args.approval_file, args, reranked=args.phase == "rerank")
            print(f"{args.phase.upper()} PASSED")
        return 0
    except (ValueError, OSError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        # Never expose provider exception bodies, credentials or raw query text.
        print(f"PRECOMPUTE FAILED: {exc}" if isinstance(exc, PrecomputeError)
              else f"PRECOMPUTE FAILED: {type(exc).__name__}; check input files/dependencies", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
