#!/usr/bin/env python3
"""Prepare and execute resumable sequential RAG batches.

This module owns batch input, benchmark resolution, validation, resume state,
execution bookkeeping, and JSONL output. The shared Dev5 ``run_rag`` adapter is
intentionally not implemented here; the CLI currently supports preparation
only until that handoff is available.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = ROOT / "data" / "benchmark" / "queries_dev.json"


class BatchInputError(ValueError):
    """Invalid batch input or benchmark structure."""


@dataclass(frozen=True)
class InputError:
    stage: str
    message: str
    query_id: str | None = None
    line: int | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "status": "ERROR",
            "stage": self.stage,
            "query_id": self.query_id,
            "line": self.line,
            "error_type": "BatchInputError",
            "error": self.message,
        }


def load_ids_from_txt(path: str | Path) -> tuple[list[Any], list[InputError]]:
    """Load one ID per non-empty line; report rather than hide malformed data."""
    source = Path(path)
    ids: list[Any] = []
    errors: list[InputError] = []
    with source.open("r", encoding="utf-8-sig") as stream:
        for line_no, line in enumerate(stream, 1):
            value = line.strip()
            if value:
                ids.append(value)
    return ids, errors


def load_ids_from_jsonl(path: str | Path) -> tuple[list[Any], list[InputError]]:
    """Load ``query_id`` values from JSONL, retaining line-level parse errors."""
    source = Path(path)
    ids: list[Any] = []
    errors: list[InputError] = []
    with source.open("r", encoding="utf-8-sig") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(InputError("input", f"JSONL không hợp lệ: {exc.msg}", line=line_no))
                continue
            if not isinstance(record, dict):
                errors.append(InputError("input", "Mỗi dòng JSONL phải là một object.", line=line_no))
                continue
            ids.append(record.get("query_id"))
    return ids, errors


def normalize_input_ids(ids: Iterable[Any]) -> tuple[list[str], list[InputError], int]:
    """Trim IDs, reject missing/invalid values, and deduplicate stably."""
    normalized: list[str] = []
    errors: list[InputError] = []
    seen: set[str] = set()
    initial_count = 0
    for position, raw_id in enumerate(ids, 1):
        initial_count += 1
        if not isinstance(raw_id, str):
            errors.append(InputError("input", "query_id phải là chuỗi không rỗng.", line=position))
            continue
        query_id = raw_id.strip()
        if not query_id:
            errors.append(InputError("input", "query_id không được rỗng.", line=position))
            continue
        if query_id in seen:
            continue
        seen.add(query_id)
        normalized.append(query_id)
    return normalized, errors, initial_count


def load_benchmark(path: str | Path) -> list[Any]:
    """Read queries_dev.json as a JSON array."""
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise BatchInputError(f"Benchmark JSON không hợp lệ tại dòng {exc.lineno}: {exc.msg}") from exc
    if not isinstance(value, list):
        raise BatchInputError("Benchmark phải là một JSON array.")
    return value


def build_benchmark_index(benchmark_data: Sequence[Any]) -> dict[str, Any]:
    """Index benchmark records by unique non-empty ID; reject ambiguity."""
    index: dict[str, Any] = {}
    for position, record in enumerate(benchmark_data, 1):
        if not isinstance(record, dict):
            continue
        query_id = record.get("id")
        if not isinstance(query_id, str) or not query_id.strip():
            continue
        query_id = query_id.strip()
        if query_id in index:
            raise BatchInputError(f"ID {query_id!r} xuất hiện nhiều lần trong benchmark.")
        index[query_id] = record
    return index


def resolve_query(query_id: str, benchmark_index: dict[str, Any]) -> dict[str, Any]:
    """Resolve query text and date exclusively from the benchmark record."""
    record = benchmark_index.get(query_id)
    if record is None:
        raise BatchInputError(f"Không tìm thấy query_id {query_id!r} trong benchmark.")
    return {
        "query_id": query_id,
        "query": record.get("question"),
        "as_of_date": record.get("as_of_date"),
    }


def validate_query(query: Any) -> None:
    if not isinstance(query, dict):
        raise BatchInputError("Resolved query phải là object.")
    query_id = query.get("query_id")
    if not isinstance(query_id, str) or not query_id.strip():
        raise BatchInputError("query_id bị thiếu hoặc không hợp lệ.")
    text = query.get("query")
    if not isinstance(text, str) or not text.strip():
        raise BatchInputError(f"Query {query_id!r}: question phải là chuỗi không rỗng.")
    as_of_date = query.get("as_of_date")
    if not isinstance(as_of_date, str):
        raise BatchInputError(f"Query {query_id!r}: thiếu as_of_date dạng YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(as_of_date)
    except ValueError as exc:
        raise BatchInputError(f"Query {query_id!r}: as_of_date không hợp lệ: {as_of_date!r}.") from exc
    if parsed.isoformat() != as_of_date:
        raise BatchInputError(f"Query {query_id!r}: as_of_date phải có dạng YYYY-MM-DD.")


def resolve_queries(
    query_ids: Sequence[str], benchmark_index: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[InputError]]:
    valid: list[dict[str, Any]] = []
    errors: list[InputError] = []
    for query_id in query_ids:
        try:
            query = resolve_query(query_id, benchmark_index)
            validate_query(query)
            valid.append(query)
        except BatchInputError as exc:
            errors.append(InputError("resolve_validate", str(exc), query_id=query_id))
    return valid, errors


def load_completed_query_ids(results_path: str | Path) -> set[str]:
    """Read only structurally valid SUCCESS records as completed work."""
    source = Path(results_path)
    if not source.exists():
        return set()
    completed: set[str] = set()
    with source.open("r", encoding="utf-8-sig") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BatchInputError(f"Results JSONL lỗi dòng {line_no}: {exc.msg}") from exc
            if (
                isinstance(record, dict)
                and record.get("status") == "SUCCESS"
                and isinstance(record.get("query_id"), str)
                and isinstance(record.get("result"), dict)
            ):
                completed.add(record["query_id"])
    return completed


def is_query_completed(query_id: str, completed_ids: set[str]) -> bool:
    return query_id in completed_ids


def filter_pending_queries(
    queries: Sequence[dict[str, Any]], completed_ids: set[str]
) -> tuple[list[dict[str, Any]], int]:
    pending = [query for query in queries if not is_query_completed(query["query_id"], completed_ids)]
    return pending, len(queries) - len(pending)


class JsonlWriter:
    """Append UTF-8 JSONL records and flush after every record."""

    def __init__(self, results_path: str | Path, errors_path: str | Path):
        self.results_path = Path(results_path)
        self.errors_path = Path(errors_path)
        self.results_path.parent.mkdir(parents=True, exist_ok=True)
        self.errors_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _append(path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()

    def write_success(self, query: dict[str, Any], result: dict[str, Any]) -> None:
        if not isinstance(result, dict):
            raise BatchInputError("Runner phải trả về object để ghi kết quả thành công.")
        self._append(
            self.results_path,
            {
                "status": "SUCCESS",
                "query_id": query["query_id"],
                "as_of_date": query["as_of_date"],
                "result": result,
            },
        )

    def write_error(
        self,
        query_id: str | None,
        error: Exception | str,
        *,
        stage: str = "execute",
        line: int | None = None,
    ) -> None:
        error_type = type(error).__name__ if isinstance(error, Exception) else "InputError"
        message = str(error)
        self._append(
            self.errors_path,
            {
                "status": "ERROR",
                "query_id": query_id,
                "stage": stage,
                "line": line,
                "error_type": error_type,
                "error": message,
                "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )

    def write_input_error(self, error: InputError) -> None:
        record = error.to_record()
        record["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
        self._append(self.errors_path, record)


Runner = Callable[[dict[str, Any]], dict[str, Any]]


def load_runner(spec: str) -> Runner:
    """Load a Dev5-owned adapter specified as ``python.module:callable``.

    The callable contract is ``runner(query_dict) -> result_dict``. This loader
    does not guess how to initialize or call the shared RAG pipeline.
    """
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name.strip() or not attribute.strip():
        raise BatchInputError("--runner phải có dạng python.module:callable.")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise BatchInputError(f"Không import được runner module {module_name!r}: {exc}") from exc
    runner = getattr(module, attribute, None)
    if not callable(runner):
        raise BatchInputError(f"Runner {spec!r} không trỏ tới callable.")
    return runner


def execute_batch(
    queries: Sequence[dict[str, Any]],
    runner: Runner,
    writer: JsonlWriter,
    *,
    completed_ids: set[str] | None = None,
    on_progress: Callable[[int, int, str, str], None] | None = None,
) -> dict[str, int]:
    """Run sequentially, append each result immediately, and isolate failures."""
    completed = (
        completed_ids
        if completed_ids is not None
        else load_completed_query_ids(writer.results_path)
    )
    counts = {"succeeded": 0, "failed": 0, "skipped": 0}
    total = len(queries)
    for position, query in enumerate(queries, 1):
        query_id = query["query_id"]
        if query_id in completed:
            counts["skipped"] += 1
            if on_progress:
                on_progress(position, total, query_id, "SKIP")
            continue
        try:
            result = runner(query)
            writer.write_success(query, result)
            completed.add(query_id)
            counts["succeeded"] += 1
            if on_progress:
                on_progress(position, total, query_id, "SUCCESS")
        except Exception as exc:  # isolate a single query and continue the batch
            writer.write_error(query_id, exc)
            counts["failed"] += 1
            if on_progress:
                on_progress(position, total, query_id, "ERROR")
    return counts


def _load_input(path: Path) -> tuple[list[str], list[InputError], int]:
    suffix = path.suffix.casefold()
    if suffix == ".txt":
        raw_ids, errors = load_ids_from_txt(path)
    elif suffix == ".jsonl":
        raw_ids, errors = load_ids_from_jsonl(path)
    else:
        raise BatchInputError("File ID phải có phần mở rộng .txt hoặc .jsonl.")
    ids, id_errors, initial_count = normalize_input_ids(raw_ids)
    return ids, errors + id_errors, initial_count


def prepare_batch(
    input_path: str | Path, benchmark_path: str | Path
) -> tuple[list[dict[str, Any]], list[InputError], dict[str, int]]:
    ids, errors, initial_count = _load_input(Path(input_path))
    benchmark = build_benchmark_index(load_benchmark(benchmark_path))
    queries, resolution_errors = resolve_queries(ids, benchmark)
    errors.extend(resolution_errors)
    stats = {
        "input_ids": initial_count,
        "unique_valid_ids": len(ids),
        "valid_queries": len(queries),
        "invalid_records": len(errors),
    }
    return queries, errors, stats


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy batch RAG tuần tự, có resume và ghi JSONL.")
    parser.add_argument("--input", required=True, help="File ID .txt hoặc .jsonl")
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--output-dir", help="Thư mục chứa results.jsonl và errors.jsonl.")
    parser.add_argument(
        "--runner",
        help="Callable adapter theo dạng python.module:callable; contract: nhận query dict, trả result dict.",
    )
    parser.add_argument(
        "--prepare-only", action="store_true",
        help="Chỉ nạp, resolve và kiểm tra query; không gọi runner hoặc ghi output batch.",
    )
    args = parser.parse_args(argv)
    if not args.prepare_only and (not args.output_dir or not args.runner):
        print(
            "Để chạy batch cần --output-dir và --runner. Adapter phải gọi shared RAG pipeline; "
            "chưa có adapter Dev5 trong repo. Dùng --prepare-only để kiểm tra input.",
            file=sys.stderr,
        )
        return 2
    try:
        queries, errors, stats = prepare_batch(args.input, args.benchmark)
    except (OSError, BatchInputError) as exc:
        print(f"Batch preparation thất bại: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    for query in queries:
        print(f"READY {query['query_id']} as_of_date={query['as_of_date']}")
    for error in errors:
        print(f"ERROR {error.stage} line={error.line} id={error.query_id}: {error.message}")
    if args.prepare_only:
        return 1 if errors else 0

    try:
        writer = JsonlWriter(
            Path(args.output_dir) / "results.jsonl",
            Path(args.output_dir) / "errors.jsonl",
        )
        for error in errors:
            writer.write_input_error(error)
        runner = load_runner(args.runner) if queries else None
        counts = (
            execute_batch(
                queries,
                runner,
                writer,
                on_progress=lambda position, total, query_id, status: print(
                    f"[{position}/{total}] {status} {query_id}"
                ),
            )
            if runner is not None
            else {"succeeded": 0, "failed": 0, "skipped": 0}
        )
    except (OSError, BatchInputError) as exc:
        print(f"Batch execution setup failed: {exc}", file=sys.stderr)
        return 1
    summary = {**counts, "invalid_records": len(errors), "valid_queries": len(queries)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors or counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
