"""Kiểm bản chia Dev/Test của benchmark (D2).

Bản chia 30/10 và lần chia lại 31/10 được làm tay (docs/sprint6_benchmark.md mục 2, 6), nên
script này không chia lại mà kiểm các nguyên tắc chia trên dữ liệu hiện tại:

1. Test chỉ gồm câu đã duyệt, có gold_clause_ids và gold_context_ids đã xác nhận.
2. Không có Khoản gold chung giữa Dev và Test.
3. Câu gần trùng nằm cùng một phía: cặp Dev/Test có câu hỏi giống nhau từ ``--similarity``
   trở lên và cùng ít nhất một Điều (gold hoặc candidate) là lỗi. Câu hỏi theo cùng mẫu
   nhưng khác Điều không tính là gần trùng.
4. Khoản trong candidate của câu Dev draft trùng Khoản gold Test là cảnh báo: khi duyệt câu
   draft đó với Khoản này, điều kiện 2 sẽ hỏng. ``--strict`` coi cảnh báo là lỗi.

In phân bố theo test_type, question_type, difficulty của Dev đã duyệt và Test để kiểm phân tầng.
Thoát mã 1 khi có lỗi.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "benchmark"
CHUNKS = ROOT / "data" / "chunking_output" / "chunks.jsonl"
STRATA = ("test_type", "question_type", "difficulty")
ARTICLE_RE = re.compile(r"^(.+?_art_\d+[a-z]?)(?:_|$)")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.lower())
    return re.sub(r"[^\w\s]", " ", text).split()


def question_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _tokens(a), _tokens(b)).ratio()


def _articles(ids: Iterable[str]) -> set[str]:
    return {m.group(1) for value in ids if (m := ARTICLE_RE.match(value))}


def _chunk_clauses(chunks_path: Path) -> dict[str, str]:
    clauses = {}
    with chunks_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if row.get("clause_id"):
                    clauses[row["chunk_id"]] = row["clause_id"]
    return clauses


def check_split(
    queries: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    chunk_clauses: dict[str, str],
    similarity: float = 0.85,
) -> dict[str, Any]:
    gold = {row["id"]: row for row in ground_truth}
    errors: list[str] = []
    warnings: list[str] = []
    dev = [q for q in queries if q.get("split") == "dev"]
    test = [q for q in queries if q.get("split") == "test"]
    for query in queries:
        if query.get("split") not in ("dev", "test"):
            errors.append(f"{query.get('id')}: split không phải dev/test.")
        if query["id"] not in gold:
            errors.append(f"{query['id']}: thiếu bản ghi trong ground_truth.json.")
        elif gold[query["id"]].get("split") != query.get("split"):
            errors.append(f"{query['id']}: split của câu hỏi và ground truth khác nhau.")
    if errors:
        return {"errors": errors, "warnings": warnings, "distribution": {}}

    def reviewed(query_id: str) -> bool:
        return gold[query_id].get("gold_context_ids_confirmed") is True

    test_clauses: dict[str, list[str]] = {}
    for query in test:
        label = gold[query["id"]]
        if not reviewed(query["id"]) or label.get("review_status") != "source_checked":
            errors.append(f"{query['id']}: câu Test chưa duyệt.")
        if not label.get("gold_clause_ids") or not label.get("gold_context_ids"):
            errors.append(f"{query['id']}: câu Test thiếu gold_clause_ids hoặc gold_context_ids.")
        for clause in label.get("gold_clause_ids", []):
            test_clauses.setdefault(clause, []).append(query["id"])

    for query in dev:
        label = gold[query["id"]]
        shared = sorted(set(label.get("gold_clause_ids", [])) & test_clauses.keys())
        if shared and reviewed(query["id"]):
            errors.append(f"{query['id']} (Dev) dùng chung Khoản gold với Test: {', '.join(shared)}.")
        if not reviewed(query["id"]):
            candidate = {chunk_clauses.get(c) for c in label.get("candidate_context_ids", [])}
            overlap = sorted((candidate | set(label.get("gold_clause_ids", []))) & test_clauses.keys())
            if overlap:
                owners = sorted({q for c in overlap for q in test_clauses[c]})
                warnings.append(
                    f"{query['id']} (Dev draft): candidate thuộc Khoản gold Test "
                    f"{', '.join(overlap)} ({', '.join(owners)})."
                )

    def articles(query_id: str) -> set[str]:
        label = gold[query_id]
        return _articles([
            *label.get("gold_clause_ids", []),
            *label.get("gold_context_ids", []),
            *label.get("candidate_context_ids", []),
        ])

    for test_query in test:
        test_articles = articles(test_query["id"])
        for dev_query in dev:
            if not test_articles & articles(dev_query["id"]):
                continue
            score = question_similarity(test_query["question"], dev_query["question"])
            if score >= similarity:
                errors.append(
                    f"{test_query['id']} (Test) và {dev_query['id']} (Dev) gần trùng "
                    f"({score:.3f}) và cùng Điều."
                )

    distribution = {
        field: {
            "dev_reviewed": dict(Counter(q.get(field) for q in dev if reviewed(q["id"]))),
            "test": dict(Counter(q.get(field) for q in test)),
        }
        for field in STRATA
    }
    return {"errors": errors, "warnings": warnings, "distribution": distribution}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--queries-dev", type=Path, default=BENCHMARK / "queries_dev.json")
    parser.add_argument("--queries-test", type=Path, default=BENCHMARK / "queries_test.json")
    parser.add_argument("--ground-truth", type=Path, default=BENCHMARK / "ground_truth.json")
    parser.add_argument("--chunks", type=Path, default=CHUNKS)
    parser.add_argument("--similarity", type=float, default=0.85)
    parser.add_argument("--strict", action="store_true", help="Coi cảnh báo candidate là lỗi.")
    args = parser.parse_args()

    queries = [*_read_json(args.queries_dev), *_read_json(args.queries_test)]
    report = check_split(
        queries, _read_json(args.ground_truth), _chunk_clauses(args.chunks), args.similarity
    )
    for field, counts in report["distribution"].items():
        values = sorted(set(counts["dev_reviewed"]) | set(counts["test"]), key=str)
        cells = ", ".join(
            f"{v}: {counts['dev_reviewed'].get(v, 0)}/{counts['test'].get(v, 0)}" for v in values
        )
        print(f"{field} (Dev đã duyệt/Test): {cells}")
    for message in report["warnings"]:
        print(f"CẢNH BÁO {message}")
    for message in report["errors"]:
        print(f"LỖI {message}")
    failed = bool(report["errors"]) or (args.strict and bool(report["warnings"]))
    print(
        f"{'FAIL' if failed else 'PASS'}: {len(report['errors'])} lỗi, "
        f"{len(report['warnings'])} cảnh báo."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
