"""D1.4: verify a handed-off Dev30 set without generation or tuning."""

from __future__ import annotations
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "evaluation/manifests/dev_gold_30_manifest.json"
QUERIES = "evaluation/datasets/dev_gold_30_queries_v1.json"
IDS = "evaluation/rubrics/dev_gold_30_ids_v1.txt"
CONFIRMATION = "evaluation/review/dev30_confirmation_v1.json"
DEV = "data/benchmark/queries_dev.json"
TEST = "data/benchmark/queries_test.json"
GOLD = "data/benchmark/ground_truth.json"
CHUNKS = "data/chunking_output/chunks.jsonl"
CHUNK_INTEGRITY = "evaluation/manifests/dev30_selected_chunk_hashes_v1.json"
CONTENT_FIELDS = (
    "id",
    "answer",
    "explanation",
    "citations",
    "gold_article_ids",
    "gold_clause_ids",
    "gold_context_ids",
    "outdated_context_ids",
    "outdated_document_ids",
)


class Dev30GuardError(ValueError):
    pass


def require(condition, code, message):
    if not condition:
        raise Dev30GuardError(f"{code}: {message}")


def canonical_hash(value):
    return hashlib.sha256(
        (
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).replace("\r\n", "\n")
            + "\n"
        ).encode()
    ).hexdigest()


def normalized(text):
    require(
        isinstance(text, str) and bool(text.strip()),
        "invalid_question",
        "Question must be nonempty text",
    )
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    value = " ".join(
        "".join(
            c if c.isalnum() else " " for c in text if not unicodedata.combining(c)
        ).split()
    )
    require(bool(value), "invalid_question", "Question contains no text")
    return value


def index(rows, key, role):
    require(
        isinstance(rows, list) and bool(rows),
        "invalid_input",
        f"{role} must be a nonempty array",
    )
    result = {}
    for row in rows:
        require(isinstance(row, dict), "invalid_input", f"Non-object in {role}")
        value = row.get(key)
        require(
            isinstance(value, str) and bool(value),
            "invalid_id",
            f"Missing {key} in {role}",
        )
        if key == "id":
            require(
                bool(re.fullmatch(r"HN_[0-9]{3}", value)),
                "invalid_id",
                f"Invalid {role} ID: {value}",
            )
        require(value not in result, "duplicate_id", f"Duplicate {value} in {role}")
        result[value] = row
    return result


def nonempty_ids(value, role):
    require(
        isinstance(value, list) and bool(value),
        "missing_gold",
        f"{role} must be a nonempty ID array",
    )
    require(
        all(isinstance(v, str) and bool(re.fullmatch(r"[a-z0-9_]+", v)) for v in value),
        "invalid_gold_id",
        role,
    )
    require(len(set(value)) == len(value), "duplicate_gold_id", role)
    return set(value)


def gold_clauses(qid, gold, chunks, split):
    require(qid in gold, "missing_gold", f"Missing Gold for {qid}")
    record = gold[qid]
    require(record.get("split") == split, "gold_split", qid)
    require(record.get("review_status") == "source_checked", "unreviewed_gold", qid)
    require(record.get("gold_context_ids_confirmed") is True, "unconfirmed_gold", qid)
    declared = nonempty_ids(record.get("gold_clause_ids"), qid + " clauses")
    contexts = nonempty_ids(record.get("gold_context_ids"), qid + " contexts")
    actual = set()
    for cid in contexts:
        require(cid in chunks, "missing_chunk", f"{qid}: {cid}")
        chunk = chunks[cid]
        clause = chunk.get("parent_clause_id")
        require(
            isinstance(clause, str) and bool(clause),
            "missing_parent_clause",
            f"{qid}: {cid}",
        )
        require(
            chunk.get("clause_id") == clause,
            "inconsistent_parent_clause",
            f"{qid}: {cid}",
        )
        actual.add(clause)
    require(declared == actual, "gold_clause_mapping", qid)
    return declared, contexts


def validate_dev30(
    manifest, query_rows, id_lines, dev_rows, test_rows, gold_rows, chunk_rows
):
    require(
        isinstance(manifest, dict), "invalid_manifest", "Manifest must be an object"
    )
    require(
        manifest.get("version") == "dev_gold_30_v1",
        "manifest_version",
        "Unsupported Dev30 manifest version",
    )
    require(
        type(manifest.get("question_count")) is int
        and manifest["question_count"] == 30,
        "manifest_count",
        "Exactly 30 required",
    )
    manifest_ids = manifest.get("question_ids")
    require(
        isinstance(manifest_ids, list)
        and len(manifest_ids) == 30
        and all(isinstance(v, str) for v in manifest_ids),
        "manifest_ids",
        "Expected 30 string IDs",
    )
    require(
        len(set(manifest_ids)) == 30,
        "duplicate_manifest_id",
        "Manifest IDs must be unique",
    )
    selected = index(query_rows, "id", "selected queries")
    dev = index(dev_rows, "id", "Dev queries")
    test = index(test_rows, "id", "Test queries")
    gold = index(gold_rows, "id", "Gold")
    chunks = index(chunk_rows, "chunk_id", "corpus")
    require(len(selected) == 30, "query_count", "Expected 30 unique queries")
    require(
        isinstance(id_lines, list) and id_lines == manifest_ids == list(selected),
        "id_order",
        "Manifest/query/ID file differ",
    )
    require(
        not set(selected) & set(test), "test_id_leakage", "Selected ID belongs to Test"
    )
    require(
        not set(dev) & set(test), "source_split_overlap", "Dev/Test source IDs overlap"
    )
    require(
        manifest.get("query_canonical_sha256") == canonical_hash(query_rows),
        "query_hash",
        "Query artifact changed",
    )
    require(
        manifest.get("dataset_ids_hash") == canonical_hash(manifest_ids),
        "ids_hash",
        "ID list changed",
    )
    test_clauses, test_chunks, test_questions = set(), set(), set()
    for qid, q in test.items():
        require(
            q.get("split") == "test", "source_split", "Test source contains wrong split"
        )
        test_questions.add(normalized(q.get("question")))
        clauses, contexts = gold_clauses(qid, gold, chunks, "test")
        test_clauses.update(clauses)
        test_chunks.update(contexts)
    selected_clauses, selected_chunks, seen_questions = set(), set(), set()
    for qid, q in selected.items():
        require(
            qid in dev and q.get("split") == "dev" and dev[qid].get("split") == "dev",
            "not_dev",
            qid,
        )
        require(q == dev[qid], "query_not_original", qid)
        require(
            not {
                "answer",
                "explanation",
                "citations",
                "gold_article_ids",
                "gold_clause_ids",
                "gold_context_ids",
            }
            & set(q),
            "answer_in_input",
            qid,
        )
        question = normalized(q.get("question"))
        require(question not in seen_questions, "duplicate_question", qid)
        require(question not in test_questions, "test_question_leakage", qid)
        seen_questions.add(question)
        as_of = q.get("as_of_date")
        try:
            require(
                isinstance(as_of, str)
                and date.fromisoformat(as_of).isoformat() == as_of,
                "query_date",
                qid,
            )
        except ValueError as exc:
            raise Dev30GuardError(f"query_date: {qid}") from exc
        clauses, contexts = gold_clauses(qid, gold, chunks, "dev")
        require(
            gold[qid].get("evidence_level") == "full_text_checked"
            and gold[qid].get("answer_kind") == "reviewed_answer",
            "incomplete_review",
            qid,
        )
        require(
            isinstance(gold[qid].get("answer"), str)
            and bool(gold[qid]["answer"].strip()),
            "missing_answer",
            qid,
        )
        require(not clauses & test_clauses, "test_clause_leakage", qid)
        require(not contexts & test_chunks, "test_chunk_leakage", qid)
        selected_clauses.update(clauses)
        selected_chunks.update(contexts)
    content_hash = canonical_hash(
        [
            {field: gold[qid].get(field) for field in CONTENT_FIELDS}
            for qid in manifest_ids
        ]
    )
    require(
        manifest.get("selected_gold_content_hash") == content_hash,
        "selected_gold_changed",
        "Reference content differs from selected version",
    )
    return dict(
        status="PASS",
        selected_count=30,
        source_checked_count=30,
        selected_unique_clauses=len(selected_clauses),
        selected_unique_chunks=len(selected_chunks),
        test_unique_clauses=len(test_clauses),
        test_id_overlap=0,
        test_clause_overlap=0,
        test_chunk_overlap=0,
        test_question_overlap=0,
        query_canonical_sha256=canonical_hash(query_rows),
        dataset_ids_hash=canonical_hash(manifest_ids),
    )


def read_json(path):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "duplicate_json_key", key)
            value[key] = item
        return value

    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)
    except (OSError, json.JSONDecodeError) as exc:
        raise Dev30GuardError(f"missing_or_invalid_artifact: {path}") from exc


def lf_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def selected_chunk_hash(chunk):
    """Bind legal content/identity/dates, not unrelated corpus or parent packaging."""
    metadata = chunk.get("metadata") or {}
    return canonical_hash(
        {
            **{
                key: chunk.get(key)
                for key in (
                    "chunk_id",
                    "document_id",
                    "article_id",
                    "clause_id",
                    "parent_clause_id",
                    "text",
                    "point_ref",
                )
            },
            **{
                key: metadata.get(key)
                for key in ("effective_from", "effective_to", "quoted_clause_number")
            },
        }
    )


def check_handoff(root=ROOT):
    root = Path(root)
    manifest = read_json(root / MANIFEST)
    require(
        isinstance(manifest, dict), "invalid_manifest", "Manifest must be an object"
    )
    confirmation = read_json(root / CONFIRMATION)
    require(
        isinstance(confirmation, dict)
        and confirmation.get("scope") == "DEV30_ZERO_SHOT_SET_CONFIRMATION"
        and confirmation.get("status") == "confirmed_for_zero_shot_baseline"
        and confirmation.get("question_count") == 30,
        "unconfirmed_handoff",
        "Separate Dev30 baseline confirmation required",
    )
    require(
        type(confirmation.get("version")) is int
        and confirmation["version"] == 1
        and isinstance(confirmation.get("confirmed_by"), str)
        and bool(confirmation["confirmed_by"].strip()),
        "confirmation_metadata",
        "Confirmation version/owner missing",
    )
    try:
        confirmed_on = confirmation.get("confirmed_on")
        require(
            isinstance(confirmed_on, str)
            and date.fromisoformat(confirmed_on).isoformat() == confirmed_on,
            "confirmation_metadata",
            "Confirmation date required",
        )
    except ValueError as exc:
        raise Dev30GuardError(
            "confirmation_metadata: Invalid confirmation date"
        ) from exc
    require(
        manifest.get("query_file") == QUERIES
        and manifest.get("ids_file") == IDS
        and confirmation.get("query_file") == QUERIES
        and confirmation.get("ids_file") == IDS
        and confirmation.get("manifest") == MANIFEST,
        "artifact_path",
        "Use the canonical handoff paths",
    )
    hashes = confirmation.get("input_sha256_lf_normalized")
    require(
        isinstance(hashes, dict) and set(hashes) == {QUERIES, DEV, GOLD, CHUNKS},
        "confirmation_inputs",
        "Incomplete confirmed inputs",
    )
    input_warnings = []
    for relative, expected in hashes.items():
        require(
            isinstance(expected, str) and bool(re.fullmatch(r"[a-f0-9]{64}", expected)),
            "invalid_hash",
            relative,
        )
        if relative == QUERIES:
            require(lf_hash(root / relative) == expected, "confirmation_hash", relative)
        elif lf_hash(root / relative) != expected:
            input_warnings.append(f"unselected_input_hash_changed: {relative}")
    query_rows, dev_rows, test_rows, gold_rows = (
        read_json(root / p) for p in (QUERIES, DEV, TEST, GOLD)
    )
    try:
        ids = (root / IDS).read_text(encoding="utf-8-sig").splitlines()
        chunk_rows = [
            json.loads(line)
            for line in (root / CHUNKS).read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise Dev30GuardError("missing_or_invalid_ids_or_corpus") from exc
    result = validate_dev30(
        manifest, query_rows, ids, dev_rows, test_rows, gold_rows, chunk_rows
    )
    integrity = read_json(root / CHUNK_INTEGRITY)
    selected_ids = set(manifest["question_ids"])
    selected_chunks = {
        cid
        for row in gold_rows
        if row["id"] in selected_ids
        for cid in row["gold_context_ids"]
    }
    expected_chunks = (
        integrity.get("chunk_hashes") if isinstance(integrity, dict) else None
    )
    require(
        isinstance(expected_chunks, dict) and set(expected_chunks) == selected_chunks,
        "selected_chunk_integrity",
        "Selected Gold chunk set differs",
    )
    by_chunk = {row["chunk_id"]: row for row in chunk_rows}
    require(
        all(
            selected_chunk_hash(by_chunk[cid]) == expected_chunks[cid]
            for cid in selected_chunks
        ),
        "selected_chunk_changed",
        "Selected Gold chunk content/identity/dates changed",
    )
    question_freeze = read_json(root / "docs/test_questions_freeze.json")
    gold_freeze = read_json(root / "docs/test_gold_freeze.json")
    require(
        isinstance(question_freeze, dict) and isinstance(gold_freeze, dict),
        "invalid_test_freeze",
        "Freeze manifests must be objects",
    )
    require(
        question_freeze.get("question_count") == len(test_rows)
        and gold_freeze.get("test_question_count") == len(test_rows),
        "test_freeze_count",
        "Test freeze counts differ",
    )
    require(
        question_freeze.get("sha256") == canonical_hash(test_rows),
        "test_question_freeze",
        "Current Test questions differ from freeze",
    )
    by_id = {g["id"]: g for g in gold_rows}
    payload = {
        "questions": test_rows,
        "test_ground_truth": [by_id[q["id"]] for q in test_rows],
    }
    require(
        gold_freeze.get("sha256") == canonical_hash(payload),
        "test_gold_freeze",
        "Current Test Gold differs from freeze",
    )
    require(
        question_freeze.get("test_ids")
        == gold_freeze.get("test_ids")
        == [q["id"] for q in test_rows],
        "test_freeze_ids",
        "Test freeze IDs differ",
    )
    result.update(
        manifest_status=manifest.get("status"),
        confirmation_status=confirmation["status"],
        handoff_scope="zero_shot_baseline; does not authorize official A/B or retuning",
        test_freeze_verified=True,
        input_warnings=input_warnings,
    )
    return result
