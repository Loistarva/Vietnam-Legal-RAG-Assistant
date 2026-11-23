#!/usr/bin/env python3
"""Prepare and execute resumable sequential RAG batches with provenance."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_BENCHMARK = ROOT / "data" / "benchmark" / "queries_dev.json"
DEFAULT_RUNNER = "orchestration.rag_pipeline:run_rag"


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
            if value and not value.startswith("#"):
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
            errors.append(InputError("input", f"query_id bị trùng: {query_id!r}.", line=position))
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
        self.results_path.touch(exist_ok=True)
        self.errors_path.touch(exist_ok=True)

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
    input_path: str | Path, benchmark_path: str | Path, *, allow_test_split: bool = False
) -> tuple[list[dict[str, Any]], list[InputError], dict[str, int]]:
    benchmark_source = Path(benchmark_path)
    benchmark_data = load_benchmark(benchmark_path)
    is_test = "test" in benchmark_source.stem.casefold() or any(
        isinstance(row, dict) and str(row.get("split", "")).casefold() == "test"
        for row in benchmark_data
    )
    if is_test and not allow_test_split:
        raise BatchInputError("Test split đang đóng băng; chỉ dùng với --allow-test-split cho đánh giá chính thức.")
    ids, errors, initial_count = _load_input(Path(input_path))
    benchmark = build_benchmark_index(benchmark_data)
    queries, resolution_errors = resolve_queries(ids, benchmark)
    errors.extend(resolution_errors)
    stats = {
        "input_ids": initial_count,
        "unique_valid_ids": len(ids),
        "valid_queries": len(queries),
        "invalid_records": len(errors),
    }
    return queries, errors, stats


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_json_url(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
        raise BatchInputError(f"Ollama preflight thất bại tại {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BatchInputError(f"Ollama trả dữ liệu không hợp lệ tại {url}.")
    return payload


def preflight_ollama() -> dict[str, Any]:
    """Fail before the batch if the configured local model gateway is unavailable."""
    import yaml

    from generation.prompt_builder import PROMPT_B_VERSION

    gateway_path = ROOT / "model_gateway/config/local_qwen.yaml"
    confidence_path = ROOT / "reranking/confidence.yaml"
    try:
        gateway = yaml.safe_load(gateway_path.read_text(encoding="utf-8")) or {}
        confidence = yaml.safe_load(confidence_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise BatchInputError(f"Không đọc được cấu hình model/threshold: {exc}") from exc

    provider = gateway.get("provider", "ollama")
    if provider != "ollama":
        raise BatchInputError(f"Batch adapter hiện chỉ preflight provider ollama, nhận {provider!r}.")
    base_url = str(gateway.get("base_url", "http://localhost:11434")).rstrip("/")
    model_name = str(gateway.get("model", "qwen2.5:7b"))
    version_payload = _read_json_url(f"{base_url}/api/version")
    tags_payload = _read_json_url(f"{base_url}/api/tags")
    models = tags_payload.get("models") or []

    def normalized(name: Any) -> str:
        clean = str(name or "").strip().casefold()
        return clean if ":" in clean else f"{clean}:latest"

    model_entry = next((entry for entry in models if isinstance(entry, dict) and any(
        normalized(entry.get(key)) == normalized(model_name) for key in ("name", "model")
    )), None)
    if model_entry is None:
        raise BatchInputError(
            f"Ollama đang chạy tại {base_url}, nhưng chưa có model {model_name!r}; "
            "hãy pull model trước khi chạy batch."
        )

    warmup_payload = {
        "model": model_name,
        "prompt": "Trả lời bằng một từ: sẵn sàng",
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": gateway.get("temperature", 0.0),
            "repeat_penalty": gateway.get("repeat_penalty", 1.0),
            "num_predict": 1,
            "num_ctx": gateway.get("num_ctx", 8192),
        },
    }
    try:
        request = Request(
            f"{base_url}/api/generate",
            data=json.dumps(warmup_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=float(gateway.get("timeout_seconds", 120))) as response:
            warmup = json.loads(response.read().decode("utf-8"))
    except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
        raise BatchInputError(f"Ollama model warm-up thất bại trước batch: {exc}") from exc
    if not isinstance(warmup, dict) or not isinstance(warmup.get("response"), str):
        raise BatchInputError("Ollama model warm-up trả response không hợp lệ; batch chưa được bắt đầu.")

    confidence_values = confidence.get("confidence") if isinstance(confidence, dict) else {}
    confidence_values = confidence_values if isinstance(confidence_values, dict) else {}
    return {
        "provider": provider,
        "base_url": base_url,
        "model": model_name,
        "model_config_path": _repo_path(gateway_path),
        "model_config_sha256": _sha256_file(gateway_path),
        "model_digest": model_entry.get("digest"),
        "ollama_version": version_payload.get("version"),
        "model_preflight": "PASS",
        "temperature": gateway.get("temperature", 0.0),
        "repeat_penalty": gateway.get("repeat_penalty", 1.0),
        "num_predict": gateway.get("num_predict", 1024),
        "num_ctx": gateway.get("num_ctx", 8192),
        "timeout_seconds": gateway.get("timeout_seconds", 120),
        "max_retries": gateway.get("max_retries", 1),
        "cache_enabled": gateway.get("cache_enabled", False),
        "fallback_locked": gateway.get("fallback_locked", True),
        "prompt_version": PROMPT_B_VERSION,
        "confidence_thresholds": confidence_values,
        "threshold_config_version": confidence_values.get("threshold_config_version"),
        "threshold_config_path": _repo_path(confidence_path),
        "threshold_config_sha256": _sha256_file(confidence_path),
        "hyde_enabled": False,
        "judge_enabled": False,
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
    }


def build_run_manifest(input_path: Path, benchmark_path: Path, runner: str,
                       results_path: Path,
                       runtime_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    retrieval_config = ROOT / "retrieval/config.yaml"
    rerank_config = ROOT / "reranking/config.yaml"
    corpus = ROOT / "data/chunking_output/chunks.jsonl"
    try:
        git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, check=True,
                                capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                                    capture_output=True, text=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        git_sha, branch, dirty = "unknown", "unknown", True

    precomputed_value = os.getenv("RAG_PRECOMPUTED")
    precomputed = None
    if precomputed_value:
        precomputed_path = Path(precomputed_value)
        if not precomputed_path.is_absolute():
            precomputed_path = ROOT / precomputed_path
        if not precomputed_path.is_file():
            raise BatchInputError(f"RAG_PRECOMPUTED không trỏ tới file tồn tại: {precomputed_path}")
        precomputed = {"path": _repo_path(precomputed_path),
                       "sha256": _sha256_file(precomputed_path)}

    try:
        from embedding.vector_store import chunk_file_sha256
        corpus_sha = chunk_file_sha256(corpus)
    except (OSError, FileNotFoundError):
        corpus_sha = None
    required_files = (input_path, benchmark_path, retrieval_config, rerank_config)
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise BatchInputError(f"Thiếu file cần đưa vào run manifest: {missing}")
    stable = {
        "runner": runner,
        "git_branch": branch,
        "git_sha": git_sha,
        "working_tree_dirty": dirty,
        "benchmark_path": _repo_path(benchmark_path),
        "benchmark_sha256": _sha256_file(benchmark_path),
        "input_ids_path": _repo_path(input_path),
        "input_ids_sha256": _sha256_file(input_path),
        "retrieval_config_sha256": _sha256_file(retrieval_config),
        "rerank_config_sha256": _sha256_file(rerank_config),
        "corpus_sha256": corpus_sha,
        "precomputed_artifact": precomputed,
        "as_of_date_source": "benchmark",
        "results_path": _repo_path(results_path),
        "runtime": runtime_snapshot,
    }
    signature = hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":"))
                               .encode("utf-8")).hexdigest()
    return {"manifest_version": "d4.6.run_manifest.v2", **stable,
            "run_signature_sha256": signature}


def prepare_run_manifest(manifest_path: Path, expected: dict[str, Any], results_path: Path) -> dict[str, Any]:
    """Reject resume if its manifest differs from the current inputs/configuration."""
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("run_signature_sha256") != expected["run_signature_sha256"]:
            raise BatchInputError("Run manifest không khớp input/config hiện tại; dùng thư mục output mới.")
        if not results_path.exists():
            raise BatchInputError("Có run_manifest.json nhưng thiếu results JSONL; không thể resume an toàn.")
        return existing
    if results_path.exists():
        raise BatchInputError("Có results JSONL nhưng thiếu run_manifest.json; từ chối resume không provenance.")
    manifest = {**expected, "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "finished_at_utc": None, "status": "RUNNING"}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy batch RAG tuần tự, có resume và ghi JSONL.")
    parser.add_argument("--input", required=True, help="File ID .txt hoặc .jsonl")
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--output-dir", help="Thư mục chứa results.jsonl và errors.jsonl.")
    parser.add_argument("--output", help="Đường dẫn đầy đủ/tương đối của JSONL success output.")
    parser.add_argument(
        "--runner",
        default=DEFAULT_RUNNER,
        help=f"Callable adapter python.module:callable (mặc định {DEFAULT_RUNNER}).",
    )
    parser.add_argument("--allow-test-split", action="store_true",
                        help="Cho phép chạy Test chỉ trong lần đánh giá chính thức đã được duyệt.")
    parser.add_argument("--require-clean-checkout", action="store_true",
                        help="Chỉ chạy nếu HEAD đã có trên upstream và working tree sạch, kể cả untracked files.")
    parser.add_argument(
        "--prepare-only", action="store_true",
        help="Chỉ nạp, resolve và kiểm tra query; không gọi runner hoặc ghi output batch.",
    )
    args = parser.parse_args(argv)
    if not args.prepare_only and not args.output_dir and not args.output:
        print(
            "Để chạy batch cần --output-dir hoặc --output.",
            file=sys.stderr,
        )
        return 2
    try:
        input_path = Path(args.input).resolve()
        benchmark_path = Path(args.benchmark).resolve()
        queries, errors, stats = prepare_batch(
            input_path, benchmark_path, allow_test_split=args.allow_test_split
        )
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
        if args.require_clean_checkout:
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            upstream = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                cwd=ROOT, check=True, capture_output=True, text=True,
            ).stdout.strip()
            pushed = subprocess.run(
                ["git", "merge-base", "--is-ancestor", "HEAD", upstream],
                cwd=ROOT, check=False, capture_output=True, text=True,
            ).returncode == 0
            if status or not branch or not pushed:
                raise BatchInputError(
                    "Run chính thức yêu cầu branch có upstream, HEAD đã được push lên upstream "
                    "và working tree sạch (bao gồm untracked files)."
                )
        results_path = Path(args.output).resolve() if args.output else Path(args.output_dir).resolve() / "results.jsonl"
        output_dir = Path(args.output_dir).resolve() if args.output_dir else results_path.parent
        errors_path = output_dir / "errors.jsonl" if not args.output else results_path.with_name(results_path.stem + "_errors.jsonl")
        manifest_path = output_dir / "run_manifest.json"
        runtime_snapshot = preflight_ollama() if args.runner == DEFAULT_RUNNER else None
        expected_manifest = build_run_manifest(
            input_path, benchmark_path, args.runner, results_path, runtime_snapshot
        )
        manifest = prepare_run_manifest(manifest_path, expected_manifest, results_path)
        writer = JsonlWriter(results_path, errors_path)
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
    except (OSError, BatchInputError, subprocess.CalledProcessError) as exc:
        print(f"Batch execution setup failed: {exc}", file=sys.stderr)
        return 1
    summary = {**counts, "invalid_records": len(errors), "valid_queries": len(queries)}
    manifest.update(summary)
    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["status"] = "FAILED" if errors or counts["failed"] else "SUCCESS"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors or counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
