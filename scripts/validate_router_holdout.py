"""Validate a newly authored Rule Router holdout before running the router."""
from __future__ import annotations

import argparse
import ast
import collections
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.router.rule_router import Action, Route  # noqa: E402

DEFAULT_HOLDOUT = ROOT / "test/agent/data/router_holdout_independent_v1.jsonl"
DEFAULT_COMPARISON_PATHS = (
    ROOT / "test/agent/data/router_holdout.jsonl",
    ROOT / "data/benchmark/queries_dev.json",
    ROOT / "evaluation/negative_set/dev_negative_queries_v2.jsonl",
    ROOT / "test/agent/test_rule_router.py",
)
EXPECTED_ACTION_BY_ROUTE = {
    Route.LEGAL_HNGD.value: Action.LEGAL_RETRIEVAL.value,
    Route.LEGAL_OUT_OF_SCOPE.value: Action.POLICY_ABSTENTION.value,
    Route.MIXED_LEGAL_SCOPE.value: Action.POLICY_ABSTENTION.value,
    Route.NON_LEGAL.value: Action.GENERAL_CHAT.value,
    Route.LEGAL_SCOPE_UNCERTAIN.value: Action.LEGAL_RETRIEVAL.value,
}


def normalize_query(value: str) -> str:
    """Normalize only Unicode, case, and whitespace for exact-text comparison."""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _comparison_queries(path: Path) -> tuple[set[str], str | None]:
    if not path.is_file():
        return set(), f"Không tìm thấy nguồn đối chiếu: {path}"
    try:
        if path.suffix.casefold() == ".py":
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            values = [
                node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            ]
        elif path.suffix.casefold() == ".jsonl":
            values = []
            for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    return set(), f"Nguồn {path.name}, dòng {line_number} không phải JSON object"
                query = row.get("query", row.get("question"))
                if isinstance(query, str):
                    values.append(query)
        else:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, list):
                return set(), f"Nguồn đối chiếu {path.name} phải là JSON array"
            values = [
                row.get("query", row.get("question"))
                for row in data
                if isinstance(row, dict)
                and isinstance(row.get("query", row.get("question")), str)
            ]
    except (OSError, UnicodeError, json.JSONDecodeError, SyntaxError) as exc:
        return set(), f"Không đọc được nguồn {path.name}: {type(exc).__name__}"
    return {normalize_query(value) for value in values if value.strip()}, None


def validate_holdout(
    path: Path,
    comparison_paths: tuple[Path, ...] | list[Path] = (),
) -> dict[str, object]:
    errors: list[str] = []
    rows: list[dict[str, str]] = []
    if not path.is_file():
        return {"rows": rows, "errors": [f"Không tìm thấy holdout: {path}"],
                "route_counts": {}, "category_counts": {}, "comparison_matches": []}

    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        return {"rows": rows, "errors": [f"Không đọc được holdout: {type(exc).__name__}"],
                "route_counts": {}, "category_counts": {}, "comparison_matches": []}

    required = ("id", "query", "expected_route", "expected_action", "category")
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"Dòng {line_number}: JSON không hợp lệ (cột {exc.colno})")
            continue
        if not isinstance(row, dict):
            errors.append(f"Dòng {line_number}: mỗi dòng phải là JSON object")
            continue
        missing = [key for key in required if not isinstance(row.get(key), str) or not row[key].strip()]
        if missing:
            errors.append(f"Dòng {line_number}: thiếu trường string hợp lệ: {', '.join(missing)}")
            continue
        if any(row[key] != row[key].strip() for key in ("id", "query")):
            errors.append(f"Dòng {line_number}: id/query không được có khoảng trắng đầu hoặc cuối")
        try:
            Route(row["expected_route"])
            Action(row["expected_action"])
        except ValueError:
            errors.append(f"Dòng {line_number}: expected_route hoặc expected_action không thuộc enum")
            continue
        required_action = EXPECTED_ACTION_BY_ROUTE.get(row["expected_route"])
        if row["expected_action"] != required_action:
            errors.append(
                f"Dòng {line_number}: cặp route/action sai; "
                f"{row['expected_route']} phải dùng {required_action}"
            )
        rows.append({key: row[key] for key in required})

    if not 30 <= len(rows) <= 40:
        errors.append(f"Số câu phải từ 30 đến 40; hiện có {len(rows)}")

    ids = [row["id"] for row in rows]
    duplicate_ids = sorted(value for value, count in collections.Counter(ids).items() if count > 1)
    if duplicate_ids:
        errors.append(f"ID bị trùng: {', '.join(duplicate_ids)}")

    normalized_queries = [normalize_query(row["query"]) for row in rows]
    duplicate_queries = sorted(
        value for value, count in collections.Counter(normalized_queries).items() if count > 1
    )
    if duplicate_queries:
        errors.append(f"Câu hỏi trùng trong holdout: {len(duplicate_queries)} nội dung")

    route_counts = collections.Counter(row["expected_route"] for row in rows)
    missing_routes = sorted(set(EXPECTED_ACTION_BY_ROUTE) - set(route_counts))
    if missing_routes:
        errors.append(f"Holdout chưa có đủ 5 nhóm route; thiếu: {', '.join(missing_routes)}")

    comparison_queries: set[str] = set()
    for source in comparison_paths:
        found, error = _comparison_queries(source)
        if error:
            errors.append(error)
        comparison_queries.update(found)
    comparison_matches = sorted(set(normalized_queries) & comparison_queries)
    if comparison_matches:
        errors.append(
            f"Có {len(comparison_matches)} câu trùng nguyên văn với holdout/Dev/negative/regression hiện có"
        )

    return {
        "rows": rows,
        "errors": errors,
        "route_counts": dict(sorted(route_counts.items())),
        "category_counts": dict(sorted(collections.Counter(row["category"] for row in rows).items())),
        "comparison_matches": comparison_matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument(
        "--skip-repository-comparisons",
        action="store_true",
        help="Chỉ dùng khi cần kiểm tra fixture riêng; không dùng cho holdout nghiệm thu",
    )
    args = parser.parse_args()
    holdout_path = args.holdout if args.holdout.is_absolute() else ROOT / args.holdout
    comparisons = () if args.skip_repository_comparisons else DEFAULT_COMPARISON_PATHS
    result = validate_holdout(holdout_path, comparisons)

    if result["errors"]:
        print("VALIDATION FAILED")
        for error in result["errors"]:
            print(f"- {error}")
        return 1

    print("VALIDATION PASSED")
    print(f"Records: {len(result['rows'])}")
    print("Counts by expected route:")
    for route, count in result["route_counts"].items():
        print(f"  {route}: {count}")
    print("Counts by category:")
    for category, count in result["category_counts"].items():
        print(f"  {category}: {count}")
    print(f"Compared exact text against {len(comparisons)} repository sources.")
    print("Semantic duplication and label correctness still require human review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
