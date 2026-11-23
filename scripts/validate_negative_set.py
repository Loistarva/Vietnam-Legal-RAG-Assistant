"""Validate the Dev calibration artifact without calling retrievers or models."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evaluation/negative_set"
POLICIES = {
    "non_legal": ("non_legal", "general_chat"),
    "legal_out_of_scope": ("legal_out_of_scope", "policy_abstention"),
    "missing_corpus_evidence": ("legal_in_scope", "insufficient_evidence_abstention"),
    "insufficient_facts": ("legal_in_scope", "clarification"),
}
SHA256 = re.compile(r"[a-f0-9]{64}")
GIT_SHA = re.compile(r"[a-f0-9]{40}")


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Non-finite JSON number: {value}")
        return number

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)


def read_jsonl(text):
    lines = text.splitlines()
    if not lines or any(not line.strip() for line in lines):
        raise ValueError("JSONL must be nonempty with one object per line; blank lines are not allowed")
    return [strict_json(line) for line in lines]


def valid_date(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be an object")
    if manifest.get("dataset_version") not in {"dev_negative_v1", "dev_negative_v2"}:
        raise ValueError("Unsupported dataset version")
    if not valid_date(manifest.get("as_of_date")) or not valid_date(manifest.get("created_on")):
        raise ValueError("Invalid manifest date")
    if not isinstance(manifest.get("baseline_git_sha"), str) or not GIT_SHA.fullmatch(manifest["baseline_git_sha"]):
        raise ValueError("Baseline must be a full Git SHA")
    if not isinstance(manifest.get("dataset_canonical_sha256"), str) or not SHA256.fullmatch(manifest["dataset_canonical_sha256"]):
        raise ValueError("Invalid dataset hash")
    if manifest.get("review_status") != "pending_peer_review" or manifest.get("reviewers_required") != ["Dev 2", "Tech Lead"]:
        raise ValueError("This pre-review v1 artifact must not claim completed review")
    count, labels = manifest.get("question_count"), manifest.get("label_counts")
    if type(count) is not int or not 20 <= count <= 30 or not isinstance(labels, dict) or set(labels) != set(POLICIES):
        raise ValueError("Invalid manifest counts/groups")
    if any(type(n) is not int or n < 1 for n in labels.values()) or sum(labels.values()) != count:
        raise ValueError("Invalid manifest label counts")
    hashes = manifest.get("baseline_files_git_sha256")
    files = {"data/reference/document_versions.json", "data/chunking_output/chunks.jsonl"}
    if not isinstance(hashes, dict) or set(hashes) != files or any(not isinstance(v, str) or not SHA256.fullmatch(v) for v in hashes.values()):
        raise ValueError("Missing or invalid baseline hashes")
    sources = manifest.get("benchmark_query_sources")
    if not isinstance(sources, list) or len(sources) < 3:
        raise ValueError("Required baseline Dev/Test and additional Test snapshots missing")
    identities = set()
    allowed = {"data/benchmark/queries_dev.json", "data/benchmark/queries_test.json"}
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get("path"), str) or source["path"] not in allowed or
                not isinstance(source.get("git_sha"), str) or not GIT_SHA.fullmatch(source["git_sha"]) or
                not isinstance(source.get("canonical_sha256"), str) or not SHA256.fullmatch(source["canonical_sha256"])):
            raise ValueError("Invalid benchmark snapshot descriptor")
        identity = (source["git_sha"], source["path"])
        if identity in identities:
            raise ValueError("Duplicate benchmark snapshot")
        identities.add(identity)
    baseline = manifest["baseline_git_sha"]
    if not all((baseline, name) in identities for name in allowed) or not any(
            sha != baseline and filename.endswith("queries_test.json") for sha, filename in identities):
        raise ValueError("Required benchmark collision checks must not be removed")


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def number_key(text: str) -> str:
    return normalized(text).replace(" ", "")


def canonical_hash(value) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def git_bytes(ref: str, relative: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{relative}"], cwd=ROOT)


def fetch_sources(manifest, root=ROOT):
    """Explicit opt-in network step for shallow clones; never switch HEAD."""
    shas = [manifest["baseline_git_sha"], *[s["git_sha"] for s in manifest["benchmark_query_sources"]]]
    if any(not isinstance(sha, str) or not GIT_SHA.fullmatch(sha) for sha in shas):
        raise ValueError("Pinned full Git SHAs required before fetching")
    fetched = []
    for sha in dict.fromkeys(shas):
        exists = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=root,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if exists.returncode:
            subprocess.run(["git", "fetch", "--no-tags", "origin", sha], cwd=root, check=True)
            subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=root, check=True)
            fetched.append(sha)
    return fetched


def validate_rows(rows, registry, chunks, queries):
    errors = []
    if not isinstance(rows, list):
        return ["Dataset must be a list of objects"]
    if not 20 <= len(rows) <= 30:
        errors.append("Expected 20–30 queries")
    if any(not isinstance(row, dict) for row in rows):
        return errors + ["Every JSONL row must be an object"]
    ids, questions = set(), set()
    if (not isinstance(queries, list) or any(not isinstance(q, dict) or not isinstance(q.get("id"), str)
            or not isinstance(q.get("question"), str) or not q["question"].strip() for q in queries)):
        return errors + ["Invalid benchmark query source"]
    if not isinstance(registry, list) or not isinstance(chunks, list):
        return errors + ["Registry and chunks must be arrays"]
    available_numbers = set()
    for doc in registry:
        if not isinstance(doc, dict) or not isinstance(doc.get("document_number"), str) or not doc["document_number"].strip():
            errors.append("Malformed document registry entry")
            continue
        available_numbers.add(number_key(doc["document_number"]))
    for chunk in chunks:
        if not isinstance(chunk, dict) or not isinstance(chunk.get("metadata", {}), dict):
            errors.append("Malformed chunk metadata")
            continue
        for number in (chunk.get("document_number"), chunk.get("metadata", {}).get("document_number")):
            if number is not None and not isinstance(number, str):
                errors.append("Malformed chunk document number")
            elif number:
                available_numbers.add(number_key(number))
    forbidden_ids = {q["id"] for q in queries}
    forbidden_questions = {normalized(q["question"]) for q in queries}
    allowed = {"id", "question", "split", "as_of_date", "label", "reason", "expected_route",
               "expected_action", "required_document_number", "require_primary_source", "clarification_fields"}
    for pos, row in enumerate(rows, 1):
        prefix = f"row {pos} ({row.get('id', '?')})"
        for key in ("id", "question", "label", "reason", "expected_route", "expected_action"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                errors.append(f"{prefix}: missing/non-string {key}")
        if not all(isinstance(row.get(k), str) for k in ("id", "question", "label")):
            continue
        qid, question, label = row["id"], normalized(row["question"]), row["label"]
        if not re.fullmatch(r"NEG_DEV_[0-9]{3}", qid) or qid in ids or qid in forbidden_ids:
            errors.append(f"{prefix}: invalid/duplicate/benchmark ID")
        if not question or question in questions or question in forbidden_questions:
            errors.append(f"{prefix}: empty/duplicate/benchmark question")
        ids.add(qid)
        questions.add(question)
        if row.get("split") != "dev":
            errors.append(f"{prefix}: split must be dev")
        if not valid_date(row.get("as_of_date")):
            errors.append(f"{prefix}: invalid as_of_date")
        if label not in POLICIES or (row.get("expected_route"), row.get("expected_action")) != POLICIES.get(label):
            errors.append(f"{prefix}: label/route/action mismatch")
        if set(row) - allowed:
            errors.append(f"{prefix}: unexpected fields {sorted(set(row) - allowed)}")
        if label == "missing_corpus_evidence":
            number = row.get("required_document_number")
            if not isinstance(number, str) or not number_key(number) or row.get("require_primary_source") is not True:
                errors.append(f"{prefix}: missing primary-source requirement")
            elif number_key(number) in available_numbers:
                errors.append(f"{prefix}: requested source now present; relabel/review this negative")
            elif number_key(number) not in number_key(row["question"]):
                errors.append(f"{prefix}: required document does not match question")
            if "clarification_fields" in row:
                errors.append(f"{prefix}: source-missing case mislabeled as missing facts")
        elif "required_document_number" in row or "require_primary_source" in row:
            errors.append(f"{prefix}: primary-source fields only for missing_corpus_evidence")
        if label == "insufficient_facts":
            fields = row.get("clarification_fields")
            if (not isinstance(fields, list) or not fields or
                    any(not isinstance(v, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", v) for v in fields) or len(set(fields)) != len(fields)):
                errors.append(f"{prefix}: clarification fields required and unique")
        elif "clarification_fields" in row:
            errors.append(f"{prefix}: unexpected clarification fields")
    counts = Counter(row.get("label") for row in rows if isinstance(row.get("label"), str))
    if set(counts) != set(POLICIES):
        errors.append("All four negative groups must be represented")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATA / "dev_negative_queries_v2.jsonl")
    parser.add_argument("--manifest", type=Path, default=DATA / "dev_negative_manifest_v2.json")
    parser.add_argument("--fetch-sources", action="store_true", help="Explicitly fetch missing pinned Git sources before offline validation")
    args = parser.parse_args()
    try:
        rows = read_jsonl(args.dataset.read_text(encoding="utf-8-sig"))
        manifest = strict_json(args.manifest.read_text(encoding="utf-8-sig"))
        validate_manifest(manifest)
        if args.fetch_sources:
            fetch_sources(manifest)
        registry = strict_json((ROOT / "data/reference/document_versions.json").read_text(encoding="utf-8-sig"))
        chunks = read_jsonl((ROOT / "data/chunking_output/chunks.jsonl").read_text(encoding="utf-8-sig"))
        queries = []
        errors = []
        warnings = []
        # Pinned snapshots preserve provenance; also check current checkout so a
        # subsequently merged/edited benchmark cannot introduce a collision unnoticed.
        for filename in ("queries_dev.json", "queries_test.json"):
            current = strict_json((ROOT / "data/benchmark" / filename).read_text(encoding="utf-8-sig"))
            if not isinstance(current, list) or not current:
                raise ValueError(f"Current benchmark source must be a nonempty query array: {filename}")
            queries.extend(current)
        for source in manifest["benchmark_query_sources"]:
            blob = git_bytes(source["git_sha"], source["path"])
            parsed = strict_json(blob.decode("utf-8-sig"))
            if not isinstance(parsed, list) or not parsed:
                raise ValueError("Benchmark snapshot must be a nonempty query array")
            queries.extend(parsed)
            if canonical_hash(parsed) != source["canonical_sha256"]:
                errors.append(f"Changed benchmark source: {source['path']}")
        for filename, values in [("data/reference/document_versions.json", registry), ("data/chunking_output/chunks.jsonl", chunks)]:
            blob = git_bytes(manifest["baseline_git_sha"], filename)
            baseline = ([json.loads(line) for line in blob.decode("utf-8-sig").splitlines() if line.strip()]
                        if filename.endswith(".jsonl") else json.loads(blob.decode("utf-8-sig")))
            # A changed corpus/registry alone is not a failure: validate_rows below
            # re-checks coverage on the current checkout and fails if a "missing"
            # source is now present. Keep the difference visible as a warning.
            if canonical_hash(baseline) != canonical_hash(values):
                warnings.append(f"Working dataset differs from pinned baseline: {filename}; coverage re-checked on current checkout")
            if hashlib.sha256(blob).hexdigest() != manifest["baseline_files_git_sha256"][filename]:
                errors.append(f"Baseline hash mismatch: {filename}")
        errors += validate_rows(rows, registry, chunks, queries)
        if any(isinstance(row, dict) and row.get("as_of_date") != manifest["as_of_date"] for row in rows):
            errors.append("Query as_of_date differs from manifest")
        if canonical_hash(rows) != manifest["dataset_canonical_sha256"]:
            errors.append("Dataset canonical hash mismatch; version/review changes explicitly")
        counts = dict(Counter(row.get("label") for row in rows if isinstance(row, dict) and isinstance(row.get("label"), str)))
        if counts != manifest["label_counts"] or len(rows) != manifest["question_count"]:
            errors.append("Manifest count mismatch")
        print(json.dumps({"count": len(rows), "labels": counts, "issues": errors, "warnings": warnings,
                          "review_status": manifest["review_status"]}, ensure_ascii=True, indent=2))
        return bool(errors)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
