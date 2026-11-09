"""Evaluate RuleRouter on official Dev30, Dev benchmark, and negative set v2."""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.router.rule_router import Action, Route, RuleRouter
from embedding.vector_store import chunk_file_sha256


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run() -> tuple[str, bool]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=None,
                        help="Markdown report path; if omitted, print to stdout")
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

    confusion: collections.Counter[tuple[str, str]] = collections.Counter()
    for row, decision in negative_rows:
        expected = str(row.get("expected_route", "unknown")).upper()
        confusion[(expected, decision.route.value)] += 1

    official_pass = len(official) == 30 and all(d.route == Route.LEGAL_HNGD for _, d in official)
    dev_retrieval = sum(d.action == Action.LEGAL_RETRIEVAL for _, d in dev)
    dev_pass = bool(dev) and dev_retrieval / len(dev) >= 0.95
    nonlegal = [(row, decision) for row, decision in negative_rows
                if row.get("expected_route") == "non_legal"]
    nonlegal_pass = len(nonlegal) == 6 and all(d.route == Route.NON_LEGAL for _, d in nonlegal)
    legal_negative = [(row, decision) for row, decision in negative_rows
                      if str(row.get("expected_route", "")).startswith("legal_")]
    legal_not_general = all(d.action != Action.GENERAL_CHAT for _, d in legal_negative)
    gates = {
        "official30_all_LEGAL_HNGD": official_pass,
        "dev_legal_retrieval_at_least_95_percent": dev_pass,
        "negative_non_legal_6_of_6": nonlegal_pass,
        "no_legal_negative_to_GENERAL_CHAT": legal_not_general,
    }

    try:
        git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git_sha = "unknown"
    corpus_path = ROOT / "data/chunking_output/chunks.jsonl"
    corpus_sha = chunk_file_sha256(corpus_path) if corpus_path.is_file() else "unavailable"
    lines = [
        "# D4.5 Rule Router smoke",
        "",
        f"- Thời điểm UTC: {datetime.now(timezone.utc).isoformat()}",
        f"- Git commit: `{git_sha}`",
        f"- Corpus SHA chuẩn hóa: `{corpus_sha}`",
        f"- Official IDs: {len(official)}; Dev queries: {len(dev)}; negative v2: {len(negatives)}",
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
