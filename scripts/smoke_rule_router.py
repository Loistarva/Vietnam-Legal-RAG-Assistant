"""Evaluate RuleRouter on official Dev30, Dev benchmark, and negative set v2."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOLDOUT = ROOT / "test/agent/data/router_holdout.jsonl"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.router.rule_router import CLASSIFIER_VERSION, Action, Route, RuleRouter
from embedding.vector_store import chunk_file_sha256
from scripts.validate_router_holdout import DEFAULT_COMPARISON_PATHS, validate_holdout


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_router_holdout(path: Path) -> tuple[list[dict], str | None]:
    if not path.is_file():
        return [], f"Không tìm thấy holdout candidate: {path.name}"
    rows: list[dict] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                return [], f"Holdout dòng {line_number} không phải JSON object"
            if not all(isinstance(row.get(key), str) and row[key].strip()
                       for key in ("id", "query", "expected_route", "expected_action", "category")):
                return [], f"Holdout dòng {line_number} thiếu id/query/expected_route/expected_action/category"
            try:
                Route(row["expected_route"])
                Action(row["expected_action"])
            except ValueError:
                return [], f"Holdout dòng {line_number} có route/action không hợp lệ"
            rows.append(row)
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"Không đọc được holdout {path.name}: {type(exc).__name__}"
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        return [], "Holdout có ID trùng"
    return rows, None


def evaluate_router_holdout(
    rows: list[dict], decisions: list[object], validation_error: str | None = None
) -> dict[str, object]:
    """Separate the safety invariant from exact classification quality."""
    valid_set = validation_error is None and 30 <= len(rows) <= 40 and len(rows) == len(decisions)
    legal_to_general = [
        row["id"] for row, decision in zip(rows, decisions)
        if row["expected_route"] != Route.NON_LEGAL.value
        and decision.action == Action.GENERAL_CHAT
    ]
    mismatches = [
        row["id"] for row, decision in zip(rows, decisions)
        if decision.route.value != row["expected_route"]
        or decision.action.value != row["expected_action"]
    ]
    return {
        "valid_set": valid_set,
        "legal_to_general": legal_to_general,
        "mismatches": mismatches,
        "safety_pass": valid_set and not legal_to_general,
        "classification_pass": valid_set and not mismatches,
    }


def run() -> tuple[str, bool]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=None,
                        help="Markdown report path; if omitted, print to stdout")
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT,
                        help="30–40 case JSONL evaluation dataset (review status documented in metadata)")
    parser.add_argument("--skip-holdout", action="store_true",
                        help="Chỉ chạy freeze gates trên Dev/Negative Set; không đọc bất kỳ holdout nào")
    args = parser.parse_args()

    official_ids = [line.strip() for line in (ROOT / "evaluation/rubrics/dev_gold_30_ids_v1.txt")
                    .read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
    benchmark = read_json(ROOT / "data/benchmark/queries_dev.json")
    benchmark_by_id = {row["id"]: row for row in benchmark}
    missing = sorted(set(official_ids) - set(benchmark_by_id))
    if len(official_ids) != 30 or len(set(official_ids)) != 30 or missing:
        raise ValueError(f"Official ID contract failed: count={len(official_ids)}, missing={missing}")

    router = RuleRouter()
    official = [(query_id, router.route(benchmark_by_id[query_id]["question"], query_id=query_id))
                for query_id in official_ids]
    dev = [(row["id"], router.route(row["question"], query_id=row["id"])) for row in benchmark]
    negative_path = ROOT / "evaluation/negative_set/dev_negative_queries_v2.jsonl"
    negatives = [json.loads(line) for line in negative_path.read_text(encoding="utf-8-sig").splitlines()
                 if line.strip()]
    negative_rows = [(row, router.route(row["question"], query_id=row.get("id"))) for row in negatives]
    holdout_path = None
    holdout: list[dict] = []
    holdout_error = "skipped for pre-freeze evaluation" if args.skip_holdout else None
    holdout_validation = {"errors": [], "route_counts": {}, "category_counts": {}}
    holdout_results: list[tuple[dict, object]] = []
    if not args.skip_holdout:
        holdout_path = args.holdout if args.holdout.is_absolute() else ROOT / args.holdout
        holdout, holdout_error = read_router_holdout(holdout_path)
        comparison_paths = tuple(
            source
            for source in DEFAULT_COMPARISON_PATHS
            if source.resolve() != holdout_path.resolve()
        )
        holdout_validation = validate_holdout(holdout_path, comparison_paths)
        if holdout_validation["errors"]:
            validation_message = "; ".join(holdout_validation["errors"])
            holdout_error = f"{holdout_error}; {validation_message}" if holdout_error else validation_message
        holdout_results = [
            (row, router.route(row["query"], query_id=row["id"])) for row in holdout
        ]
    reviewer_statuses = sorted({
        str(row.get("reviewer_status", "UNSPECIFIED")) for row in holdout
    })
    reviewer_summary = ", ".join(reviewer_statuses) if reviewer_statuses else "unavailable"

    confusion: collections.Counter[tuple[str, str]] = collections.Counter()
    for row, decision in negative_rows:
        expected = str(row.get("expected_route", "unknown")).upper()
        confusion[(expected, decision.route.value)] += 1

    official_pass = len(official) == 30 and all(
        d.route == Route.LEGAL_HNGD and d.action == Action.LEGAL_RETRIEVAL
        for _, d in official
    )
    dev_retrieval = sum(d.action == Action.LEGAL_RETRIEVAL for _, d in dev)
    dev_pass = bool(dev) and dev_retrieval / len(dev) >= 0.95
    nonlegal = [(row, decision) for row, decision in negative_rows
                if row.get("expected_route") == "non_legal"]
    nonlegal_pass = len(nonlegal) == 6 and all(
        d.route == Route.NON_LEGAL and d.action == Action.GENERAL_CHAT
        for _, d in nonlegal
    )
    legal_negative = [(row, decision) for row, decision in negative_rows
                      if str(row.get("expected_route", "")).startswith("legal_")]
    legal_safety_violations = [
        query_id for query_id, decision in (
            official + dev + [(row["id"], decision) for row, decision in legal_negative]
        )
        if decision.route == Route.NON_LEGAL or decision.action == Action.GENERAL_CHAT
    ]
    negative_route_action_mismatches = []
    for row, decision in negative_rows:
        expected_route = str(row.get("expected_route", "")).upper()
        if expected_route == "LEGAL_IN_SCOPE":
            expected_route = Route.LEGAL_HNGD.value
        # The Router owns route/action dispatch. Evidence abstention and
        # clarification are later pipeline actions owned by the Orchestrator.
        expected_action = {
            Route.NON_LEGAL.value: Action.GENERAL_CHAT.value,
            Route.LEGAL_OUT_OF_SCOPE.value: Action.POLICY_ABSTENTION.value,
        }.get(expected_route, Action.LEGAL_RETRIEVAL.value)
        if decision.route.value != expected_route or decision.action.value != expected_action:
            negative_route_action_mismatches.append(row["id"])
    negative_route_action_pass = len(negative_rows) == 26 and not negative_route_action_mismatches
    holdout_evaluation = evaluate_router_holdout(
        holdout, [decision for _, decision in holdout_results], holdout_error
    ) if not args.skip_holdout else None
    holdout_legal_to_general = (
        holdout_evaluation["legal_to_general"] if holdout_evaluation is not None else []
    )
    holdout_mismatches = holdout_evaluation["mismatches"] if holdout_evaluation is not None else []
    gates = {
        "official30_route_and_action_match": official_pass,
        "dev_legal_retrieval_at_least_95_percent": dev_pass,
        "negative_26_route_and_router_action_match": negative_route_action_pass,
        "negative_non_legal_6_route_action_and_no_RAG": nonlegal_pass,
        "no_legal_query_to_NON_LEGAL_or_GENERAL_CHAT": not legal_safety_violations,
    }
    if holdout_evaluation is not None:
        gates["holdout_candidate_safety_no_legal_to_GENERAL_CHAT"] = holdout_evaluation["safety_pass"]
        gates["holdout_candidate_route_action_match"] = holdout_evaluation["classification_pass"]

    try:
        git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout.strip()
        working_tree_dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        git_sha = "unknown"
        working_tree_dirty = None
    corpus_path = ROOT / "data/chunking_output/chunks.jsonl"
    corpus_sha = chunk_file_sha256(corpus_path) if corpus_path.is_file() else "unavailable"
    router_sha = hashlib.sha256((ROOT / "agent/router/rule_router.py").read_bytes()).hexdigest()
    holdout_sha = (
        hashlib.sha256(holdout_path.read_bytes()).hexdigest()
        if holdout_path is not None and holdout_path.is_file() else "not evaluated"
    )
    if holdout_path is None:
        holdout_summary = "skipped (pre-freeze mode)"
    else:
        holdout_source = (
            holdout_path.resolve().relative_to(ROOT).as_posix()
            if holdout_path.resolve().is_relative_to(ROOT.resolve()) else "<external-path>"
        )
        holdout_summary = (
            f"{len(holdout)} cases; recorded reviewer_status: `{reviewer_summary}` "
            f"(metadata only; not an independent-review certification); source: `{holdout_source}`"
        )
    lines = [
        "# R4.7 Rule Router Evaluation",
        "",
        f"- Thời điểm UTC: {datetime.now(timezone.utc).isoformat()}",
        f"- Git commit: `{git_sha}`",
        f"- Working tree: `{'dirty' if working_tree_dirty else 'clean' if working_tree_dirty is not None else 'unknown'}`",
        f"- Classifier version: `{CLASSIFIER_VERSION}`",
        f"- Router source SHA-256: `{router_sha}`; holdout file SHA-256: `{holdout_sha}`",
        f"- Corpus SHA chuẩn hóa: `{corpus_sha}`",
        f"- Official IDs: {len(official)}; Dev queries: {len(dev)}; negative v2: {len(negatives)}",
        f"- Router holdout candidate: {holdout_summary}",
        *( [] if holdout_evaluation is None else [
            f"- Holdout validation error: `{holdout_error or 'none'}`",
            f"- Holdout expected route distribution: `{json.dumps(holdout_validation['route_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Holdout category distribution: `{json.dumps(holdout_validation['category_counts'], ensure_ascii=False, sort_keys=True)}`",
        ]),
        f"- Negative route/action mismatches (Router-owned mapping): {len(negative_route_action_mismatches)}; IDs: `{negative_route_action_mismatches}`",
        f"- Legal negative-to-NON_LEGAL/GENERAL_CHAT: {len(legal_safety_violations)}; IDs: `{legal_safety_violations}`",
        *( [] if holdout_evaluation is None else [
            f"- Holdout legal-to-GENERAL_CHAT: {len(holdout_legal_to_general)}; exact route/action mismatches: {len(holdout_mismatches)}"
        ]),
        "",
        "## Gate results",
        "",
        "| Gate | Kết quả |",
        "|---|---|",
    ]
    lines.extend(f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in gates.items())
    lines += ["", f"- Dev queries routed to LEGAL_RETRIEVAL: {dev_retrieval}/{len(dev)} "
              f"({dev_retrieval / len(dev):.1%})" if dev else "- Dev queries: 0",
              "", "## Negative-set confusion matrix", "",
              "| Expected route | Predicted route | Count |", "|---|---|---:|"]
    lines.extend(f"| {expected} | {actual} | {count} |"
                 for (expected, actual), count in sorted(confusion.items()))
    if holdout_evaluation is not None:
        lines += ["", "## Holdout candidate detail (reviewer status as recorded in each dataset row)", "",
                  "| ID | Expected route/action | Actual route/action | Result |",
                  "|---|---|---|---|"]
        lines.extend(
            f"| {row['id']} | {row['expected_route']} / {row['expected_action']} | "
            f"{decision.route.value} / {decision.action.value} | "
            f"{'PASS' if row['id'] not in holdout_mismatches else 'FAIL'} |"
            for row, decision in holdout_results
        )
    report = "\n".join(lines) + "\n"
    if args.report:
        target = args.report if args.report.is_absolute() else ROOT / args.report
        if target.exists():
            raise FileExistsError(f"Từ chối ghi đè smoke report: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report, encoding="utf-8")
    return report, all(gates.values())


if __name__ == "__main__":
    result, success = run()
    print(result)
    raise SystemExit(0 if success else 1)
