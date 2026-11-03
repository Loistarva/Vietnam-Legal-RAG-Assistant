"""Preflight checks for frozen, committed final Test evaluations."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_MANIFEST = ROOT / "docs" / "test_questions_freeze.json"
GOLD_MANIFEST = ROOT / "docs" / "test_gold_freeze.json"
RUN_CONFIG_MANIFEST = ROOT / "docs" / "test_run_config_freeze.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được {path}: {exc}") from exc


def _canonical_sha256(value: Any) -> str:
    serialized = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .replace("\r\n", "\n")
        + "\n"
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        content = path.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(content).hexdigest()
    except OSError as exc:
        raise ValueError(f"Không đọc được đầu vào Test {path}: {exc}") from exc


def _require_committed(paths: Sequence[Path]) -> str:
    relative_paths = [path.resolve().relative_to(ROOT).as_posix() for path in paths]
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", *relative_paths],
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode:
        raise ValueError(
            "Các manifest và cấu hình Test phải được git add/commit trước khi chạy: "
            + ", ".join(relative_paths)
        )

    changed = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", *relative_paths],
        capture_output=True,
        text=True,
        check=False,
    )
    if changed.returncode == 1:
        raise ValueError(
            "Manifest hoặc cấu hình Test có thay đổi chưa commit: "
            + ", ".join(relative_paths)
        )
    if changed.returncode:
        raise RuntimeError(
            f"Không xác minh được trạng thái commit của cấu hình Test: {changed.stderr}"
        )

    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if head.returncode:
        raise RuntimeError(f"Không đọc được commit hiện tại: {head.stderr}")
    return head.stdout.strip()


def verify_test_run(
    queries_path: Path,
    ground_truth_path: Path,
    chunks_path: Path,
    retrieval_config_path: Path,
    reranking_config_path: Path,
    top_k: int,
    methods: Sequence[str],
) -> str:
    """Verify frozen Test data/config and return the commit that locks them."""
    manifest_paths = (QUESTIONS_MANIFEST, GOLD_MANIFEST, RUN_CONFIG_MANIFEST)
    queries = _read_json(queries_path)
    ground_truth = _read_json(ground_truth_path)
    if not isinstance(queries, list) or not queries:
        raise ValueError("Tập Test phải là JSON array không rỗng.")
    if not isinstance(ground_truth, list):
        raise ValueError("Ground truth phải là JSON array.")

    question_manifest = _read_json(QUESTIONS_MANIFEST)
    question_hash = _canonical_sha256(queries)
    query_ids = [row.get("id") for row in queries if isinstance(row, dict)]
    if (
        question_manifest.get("sha256") != question_hash
        or question_manifest.get("test_ids") != query_ids
        or question_manifest.get("question_count") != len(queries)
    ):
        raise ValueError("Test questions không khớp manifest SHA-256 đã khóa.")

    gold_by_id = {
        row.get("id"): row for row in ground_truth if isinstance(row, dict)
    }
    if len(gold_by_id) != len(ground_truth):
        raise ValueError("Ground truth có ID thiếu hoặc trùng.")
    test_gold = []
    for query in queries:
        query_id = query.get("id") if isinstance(query, dict) else None
        if not isinstance(query_id, str) or query.get("split") != "test":
            raise ValueError(f"Query Test không hợp lệ: {query_id!r}")
        label = gold_by_id.get(query_id)
        if label is None:
            raise ValueError(f"{query_id}: thiếu bản ghi trong ground truth.")
        if label.get("split") != "test":
            raise ValueError(f"{query_id}: ground truth không thuộc Test split.")
        if (
            label.get("gold_context_ids_confirmed") is not True
            or not isinstance(label.get("gold_context_ids"), list)
            or not label["gold_context_ids"]
        ):
            raise ValueError(
                f"{query_id}: Test gold_context_ids thiếu hoặc chưa xác nhận; dừng chấm."
            )
        test_gold.append(label)

    gold_manifest = _read_json(GOLD_MANIFEST)
    gold_payload = {"questions": queries, "test_ground_truth": test_gold}
    if (
        gold_manifest.get("sha256") != _canonical_sha256(gold_payload)
        or gold_manifest.get("test_ids") != query_ids
        or gold_manifest.get("test_question_count") != len(queries)
    ):
        raise ValueError("Test questions/gold không khớp manifest SHA-256 đã khóa.")

    run_manifest = _read_json(RUN_CONFIG_MANIFEST)
    expected_hashes = run_manifest.get("sha256", {})
    actual_hashes = {
        "corpus": _file_sha256(chunks_path),
        "retrieval_config": _file_sha256(retrieval_config_path),
        "reranking_config": _file_sha256(reranking_config_path),
    }
    for name, actual in actual_hashes.items():
        if expected_hashes.get(name) != actual:
            raise ValueError(f"{name} không khớp cấu hình/hash Test đã khóa.")
    if run_manifest.get("top_k") != top_k or run_manifest.get("methods") != list(methods):
        raise ValueError("top_k hoặc danh sách phương pháp khác cấu hình Test đã khóa.")

    return _require_committed((
        *manifest_paths,
        queries_path,
        ground_truth_path,
        chunks_path,
        retrieval_config_path,
        reranking_config_path,
    ))


def validate_test_gold(
    queries: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
) -> None:
    """Reject missing or unconfirmed labels instead of silently skipping Test rows."""
    gold_by_id = {row.get("id"): row for row in ground_truth}
    for query in queries:
        query_id = query.get("id")
        label = gold_by_id.get(query_id)
        if label is None:
            raise ValueError(f"{query_id}: thiếu bản ghi trong ground truth.")
        if (
            label.get("gold_context_ids_confirmed") is not True
            or not isinstance(label.get("gold_context_ids"), list)
            or not label["gold_context_ids"]
        ):
            raise ValueError(
                f"{query_id}: Test gold_context_ids thiếu hoặc chưa xác nhận; dừng chấm."
            )
