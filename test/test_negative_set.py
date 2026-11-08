"""Dataset safety checks; these do not claim a working router or tuned threshold."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import shutil

import pytest

from scripts.validate_negative_set import canonical_hash, normalized, read_jsonl, strict_json, validate_manifest, validate_rows

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evaluation/negative_set"


def rows():
    return [json.loads(line) for line in (DATA / "dev_negative_queries_v2.jsonl").read_text(encoding="utf-8").splitlines()]


def test_versioned_artifact_counts_and_hash():
    dataset = rows()
    manifest = json.loads((DATA / "dev_negative_manifest_v2.json").read_text(encoding="utf-8"))
    assert len(dataset) == 26
    assert manifest["dataset_canonical_sha256"] == canonical_hash(dataset)
    assert manifest["review_status"] == "pending_peer_review"
    assert validate_rows(dataset, [], [], []) == []


def test_duplicate_question_detected_after_accent_case_and_punctuation_folding():
    dataset = rows()
    dataset[1]["question"] = "CHAO BAN HOM NAY BAN CO THE TRO CHUYEN VOI TOI MOT CHUT KHONG!!!"
    assert any("duplicate/benchmark question" in e for e in validate_rows(dataset, [], [], []))


def test_benchmark_question_collision_rejected():
    dataset = rows()
    benchmark = [{"id": "HN_SYNTHETIC_FIXTURE", "question": dataset[0]["question"], "split": "test"}]
    assert any("benchmark question" in e for e in validate_rows(dataset, [], [], benchmark))


def test_benchmark_id_collision_rejected():
    dataset = rows()
    benchmark = [{"id": dataset[0]["id"], "question": "An unrelated fixture", "split": "test"}]
    assert any("benchmark ID" in e for e in validate_rows(dataset, [], [], benchmark))


@pytest.mark.parametrize("change", [
    {"split": "test"}, {"reason": ""}, {"as_of_date": "2026-02-30"},
    {"expected_action": "policy_abstention"}, {"label": []}, {"expected_route": "legal_in_scope"},
])
def test_invalid_case_metadata_rejected(change):
    dataset = rows()
    dataset[0].update(deepcopy(change))
    assert validate_rows(dataset, [], [], [])


@pytest.mark.parametrize("where", ["registry", "chunk_root", "chunk_metadata"])
def test_missing_source_case_invalidated_when_document_is_loaded(where):
    dataset = rows()
    source = {"document_number": "52/2010/QH12"}
    registry = [source] if where == "registry" else []
    chunks = [source] if where == "chunk_root" else [{"metadata": source}] if where == "chunk_metadata" else []
    assert any("requested source now present" in e for e in validate_rows(dataset, registry, chunks, []))


def test_missing_source_requires_explicit_primary_source_request():
    dataset = rows()
    del dataset[12]["require_primary_source"]
    assert any("primary-source requirement" in e for e in validate_rows(dataset, [], [], []))


def test_clarification_requires_information_to_ask_for():
    dataset = rows()
    dataset[18]["clarification_fields"] = []
    assert any("clarification fields required" in e for e in validate_rows(dataset, [], [], []))


def test_missing_group_or_out_of_range_dataset_rejected():
    assert validate_rows(rows()[:18], [], [], [])
    assert validate_rows(rows() + rows(), [], [], [])


def test_normalization_keeps_document_numbers_distinct():
    assert normalized("52/2010/QH12") != normalized("52/2014/QH13")
    assert normalized("ĐĂNG KÝ") == "dang ky"


@pytest.mark.parametrize("change", ["dataset_hash", "baseline_hash"])
def test_cli_rejects_tampered_manifest(tmp_path, change):
    manifest = json.loads((DATA / "dev_negative_manifest_v2.json").read_text(encoding="utf-8"))
    if change == "dataset_hash":
        manifest["dataset_canonical_sha256"] = "0" * 64
    else:
        manifest["baseline_files_git_sha256"]["data/chunking_output/chunks.jsonl"] = "0" * 64
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_negative_set.py"),
                             "--manifest", str(manifest_path)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 1
    assert "hash mismatch" in result.stdout.lower()


@pytest.mark.parametrize("text", [
    '{"label":"non_legal","label":"legal_out_of_scope"}',
    '{"outer":{"id":1,"id":2}}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1e999}',
])
def test_ambiguous_or_nonstandard_json_rejected(text):
    with pytest.raises(ValueError):
        strict_json(text)


@pytest.mark.parametrize("text", ["", "  ", '{}\n\n{}', '{not json}'])
def test_invalid_jsonl_rejected(text):
    with pytest.raises(ValueError):
        read_jsonl(text)


def test_jsonl_crlf_and_terminal_newline_supported():
    assert read_jsonl('{"question":"Đăng ký"}\r\n') == [{"question": "Đăng ký"}]


@pytest.mark.parametrize("case", [
    "empty_sources", "missing_baseline_dev", "no_additional_test", "duplicate_source", "wrong_path_type",
    "bad_sha", "bad_count_type", "missing_group", "bad_date", "false_review_claim", "missing_corpus_hash",
])
def test_manifest_must_not_disable_safety_checks(case):
    manifest = json.loads((DATA / "dev_negative_manifest_v2.json").read_text(encoding="utf-8"))
    if case == "empty_sources":
        manifest["benchmark_query_sources"] = []
    elif case == "missing_baseline_dev":
        manifest["benchmark_query_sources"][0]["git_sha"] = "0" * 40
    elif case == "no_additional_test":
        manifest["benchmark_query_sources"][2]["path"] = "data/benchmark/queries_dev.json"
    elif case == "duplicate_source":
        manifest["benchmark_query_sources"][2] = deepcopy(manifest["benchmark_query_sources"][1])
    elif case == "wrong_path_type":
        manifest["benchmark_query_sources"][0]["path"] = []
    elif case == "bad_sha":
        manifest["baseline_git_sha"] = "--help"
    elif case == "bad_count_type":
        manifest["question_count"] = True
    elif case == "missing_group":
        del manifest["label_counts"]["non_legal"]
    elif case == "bad_date":
        manifest["as_of_date"] = "2026-99-99"
    elif case == "false_review_claim":
        manifest["review_status"] = "approved"
    else:
        del manifest["baseline_files_git_sha256"]["data/chunking_output/chunks.jsonl"]
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_document_present_in_metadata_not_hidden_by_different_root_number():
    chunk = {"document_number": "52/2014/QH13", "metadata": {"document_number": "52/2010/QH12"}}
    assert any("requested source now present" in e for e in validate_rows(rows(), [], [chunk], []))


def test_declared_missing_document_matches_the_question():
    dataset = rows()
    dataset[12]["required_document_number"] = "60/2014/QH13"
    assert any("does not match question" in e for e in validate_rows(dataset, [], [], []))


@pytest.mark.parametrize("registry,chunks,queries", [
    ([None], [], []), ([{"document_number": None}], [], []),
    ([], [{"metadata": None}], []), ([], [{"document_number": []}], []),
    ([], [], [{"id": [], "question": "fixture"}]),
])
def test_malformed_dependencies_report_errors_without_crashing(registry, chunks, queries):
    assert validate_rows(rows(), registry, chunks, queries)


@pytest.mark.parametrize("change", [
    {"id": "NEG_DEV_٠٠١"}, {"clarification_fields": ["x", "x"]},
    {"clarification_fields": [" x "]}, {"clarification_fields": [{}]},
])
def test_invalid_clarification_or_non_ascii_id_rejected(change):
    dataset = rows()
    dataset[18].update(change)
    assert validate_rows(dataset, [], [], [])


@pytest.mark.parametrize("case", ["date_mismatch", "nonobject_row", "malformed_json", "missing_file", "empty_sources"])
def test_cli_bad_inputs_fail_cleanly(tmp_path, case):
    dataset, manifest = rows(), json.loads((DATA / "dev_negative_manifest_v2.json").read_text(encoding="utf-8"))
    if case == "date_mismatch":
        dataset[0]["as_of_date"] = "2026-10-16"
        manifest["dataset_canonical_sha256"] = canonical_hash(dataset)
    elif case == "nonobject_row":
        dataset[0] = []
    elif case == "empty_sources":
        manifest["benchmark_query_sources"] = []
    dataset_path, manifest_path = tmp_path / "data.jsonl", tmp_path / "manifest.json"
    dataset_path.write_text("\n".join(json.dumps(r) for r in dataset) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    if case == "malformed_json":
        dataset_path.write_text('{"broken":', encoding="utf-8")
    if case == "missing_file":
        dataset_path.unlink()
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_negative_set.py"),
                             "--dataset", str(dataset_path), "--manifest", str(manifest_path)],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr


def test_cli_supports_utf8_bom_and_crlf_without_mutating_files(tmp_path):
    raw = (DATA / "dev_negative_queries_v2.jsonl").read_text(encoding="utf-8")
    dataset_path = tmp_path / "bom.jsonl"
    dataset_path.write_bytes(b"\xef\xbb\xbf" + raw.replace("\n", "\r\n").encode("utf-8"))
    before = dataset_path.read_bytes()
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_negative_set.py"),
                             "--dataset", str(dataset_path)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0
    assert dataset_path.read_bytes() == before


def test_current_checkout_collision_detected_even_when_pinned_snapshots_are_clean(tmp_path, monkeypatch, capsys):
    from scripts import validate_negative_set as validator
    for relative in ("data/reference/document_versions.json", "data/chunking_output/chunks.jsonl"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    benchmark = tmp_path / "data/benchmark"
    benchmark.mkdir()
    for split, question in [("dev", "An unrelated synthetic fixture"), ("test", rows()[0]["question"])]:
        (benchmark / f"queries_{split}.json").write_text(json.dumps([
            {"id": f"SYNTHETIC_{split}", "question": question, "split": split}
        ]), encoding="utf-8")
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "git_bytes", lambda ref, name: subprocess.check_output(
        ["git", "show", f"{ref}:{name}"], cwd=ROOT))
    monkeypatch.setattr(sys, "argv", ["validate_negative_set.py", "--dataset",
                                     str(DATA / "dev_negative_queries_v2.jsonl"), "--manifest",
                                     str(DATA / "dev_negative_manifest_v2.json")])
    assert validator.main() == 1
    assert "duplicate/benchmark question" in capsys.readouterr().out


def test_fetch_pinned_sources_restores_shallow_clone_and_preserves_head(tmp_path):
    from scripts.validate_negative_set import fetch_sources
    source = tmp_path / "source"
    source.mkdir()
    def git(root, *args):
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    git(source, "init", "-b", "fixture")
    git(source, "config", "user.name", "CI fixture")
    git(source, "config", "user.email", "ci-fixture@example.invalid")
    shas = []
    for i in range(2):
        (source / "source.txt").write_text(str(i), encoding="utf-8")
        git(source, "add", "source.txt")
        git(source, "commit", "-m", f"fixture {i}")
        shas.append(git(source, "rev-parse", "HEAD"))
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "clone", "--no-local", "--depth", "1", str(source), str(checkout)], check=True)
    manifest = {"baseline_git_sha":shas[0], "benchmark_query_sources":[{"git_sha":sha} for sha in shas]}
    before = git(checkout, "rev-parse", "HEAD")
    assert fetch_sources(manifest, checkout) == [shas[0]]
    assert fetch_sources(manifest, checkout) == []
    assert git(checkout, "rev-parse", "HEAD") == before
    assert git(checkout, "status", "--porcelain") == ""


def test_fetch_rejects_unpinned_refs_without_subprocess(tmp_path, monkeypatch):
    from scripts import validate_negative_set as validator
    def forbidden(*args, **kwargs):
        raise AssertionError("Must validate SHA before subprocess")
    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(ValueError):
        validator.fetch_sources({"baseline_git_sha":"--all", "benchmark_query_sources":[]}, tmp_path)
