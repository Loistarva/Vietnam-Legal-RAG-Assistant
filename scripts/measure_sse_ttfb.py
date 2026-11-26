"""Measure client latency to complete SSE status and terminal events on Dev30.

Percentiles use nearest rank: sort the times and take the ceil(p * n)th item
(one-based). Both distributions include completed streams with a first status,
including terminal error events. Transport failures have no timings. HTTP 0
means the client received no response headers.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import get_args

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemas.models import AskRequest, ErrorCode, ResponseStatus
from scripts.precompute_dev30_retrieval import DEFAULT_BENCHMARK, DEFAULT_IDS, PrecomputeError, read_benchmark


def machine_info():
    try:
        import psutil
        ram = round(psutil.virtual_memory().total / 1024**3, 2)
    except (ImportError, OSError):
        ram = None
    try:
        probe = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, errors="replace", timeout=5, check=True,
        )
        gpu = next(iter(probe.stdout.strip().splitlines()), None)
    except (OSError, subprocess.SubprocessError):
        gpu = None
    return {"platform": platform.platform(), "python": platform.python_version(),
            "cpu": platform.processor() or os.getenv("PROCESSOR_IDENTIFIER"),
            "logical_cpus": os.cpu_count(), "ram_gb": ram, "gpu": gpu}


def events(response):
    name, data = "", []
    # The API streams HTTP chunks. Consume each chunk as it arrives.
    for line in response.iter_lines(chunk_size=None):
        if not line:
            if name and data:
                yield name, perf_counter(), json.loads(b"\n".join(data))
            name, data = "", []
            continue
        field, _, value = line.partition(b":")
        if field == b"event":
            name = value.strip().decode("utf-8")
        elif field == b"data":
            data.append(value)
        # Event ids are server sequence numbers, unrelated to benchmark ids.


def error_code(data):
    code = data.get("error_code") if isinstance(data, dict) else None
    return code if code in get_args(ErrorCode) else None


def measure(session, url, query_id, body, timeout):
    failure = {"query_id": query_id, "http": 0, "first_status_ms": None, "server_first_status_ms": None,
               "final_ms": None, "final_event": None, "status": "ERROR", "error_code": None}
    first = server_first = final = terminal = None
    started = perf_counter()
    try:
        with session.post(url, json=body, stream=True, timeout=timeout, allow_redirects=False) as response:
            failure["http"] = response.status_code
            if response.status_code != 200:
                failure["error_code"] = error_code(response.json())
                return failure
            for event, arrived, data in events(response):
                if not isinstance(data, dict) or terminal is not None:
                    return failure
                elapsed = (arrived - started) * 1000
                if event == "status" and first is None:
                    server_first = data.get("elapsed_ms")
                    if type(server_first) not in (float, int) or not math.isfinite(server_first):
                        return failure
                    first = elapsed
                elif event in ("final", "error"):
                    status = "ERROR" if event == "error" else data.get("status")
                    if status not in get_args(ResponseStatus):
                        return failure
                    final, terminal, code = elapsed, event, error_code(data)
    except (requests.RequestException, ValueError):
        return failure
    if first is None or terminal is None:
        return failure
    return {**failure, "first_status_ms": first, "server_first_status_ms": server_first,
            "final_ms": final, "final_event": terminal, "status": status, "error_code": code}


def summarize(rows):
    measured = [row for row in rows if row["first_status_ms"] is not None]
    n_ok = sum(row["status"] != "ERROR" for row in measured)
    result = {"n": len(rows), "n_ok": n_ok, "threshold_ms": 2000}
    for field in ("first_status", "final"):
        times = sorted(row[field + "_ms"] for row in measured)
        for p in (50, 95):
            rank = math.ceil(p * len(times) / 100)
            result[f"{field}_p{p}_ms"] = times[rank - 1] if times else None
    result["pass"] = bool(rows) and n_ok == len(rows) and result["first_status_p95_ms"] < result["threshold_ms"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Đo thời gian nhận sự kiện SSE trên Dev30.")
    parser.add_argument("--api-url", default=os.getenv("LEGAL_RAG_API_URL") or "http://127.0.0.1:8000")
    parser.add_argument("--ids", type=Path, default=DEFAULT_IDS)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--api-sha", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    args = parser.parse_args(argv)
    key = os.getenv("LEGAL_RAG_API_KEY", "").strip()
    if not key:
        print("Chưa đặt biến môi trường LEGAL_RAG_API_KEY.", file=sys.stderr)
        return 2
    if not args.api_sha.strip() or not (0 < args.timeout_seconds < math.inf):
        print("Cần mã SHA của máy chủ và thời gian chờ dương hữu hạn.", file=sys.stderr)
        return 2
    base = args.api_url.rstrip("/")
    try:
        ids = [line.strip() for line in args.ids.read_text(encoding="utf-8-sig").splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError
        queries = read_benchmark(args.benchmark, ids)
        bodies = {qid: AskRequest(query=q["query"], as_of_date=q["as_of_date"]).model_dump(exclude_unset=True)
                  for qid, q in queries.items()}
        args.out.mkdir(parents=True, exist_ok=True)
    except (PrecomputeError, ValueError, OSError):
        print("Không thể chuẩn bị dữ liệu đo. Hãy kiểm tra ID, câu hỏi, ngày và thư mục đầu ra.", file=sys.stderr)
        return 2

    rows = []
    with requests.Session() as session:
        session.headers.update({"X-API-Key": key})
        try:
            with session.get(f"{base}/api/v1/health", timeout=args.timeout_seconds, allow_redirects=False) as health:
                if health.status_code != 200:
                    raise requests.HTTPError
        except requests.RequestException:
            print("Không thể kết nối với API hoặc API chưa sẵn sàng.", file=sys.stderr)
            return 2
        machine = machine_info()
        started = datetime.now(UTC).isoformat()
        for qid, body in bodies.items():
            row = measure(session, f"{base}/api/v1/ask/stream", qid, body, args.timeout_seconds)
            rows.append(row)
            print(json.dumps(row), flush=True)
    summary = summarize(rows)
    result = {"schema": "sse_ttfb_v1", "api_url": base, "api_sha": args.api_sha, "started_at_utc": started,
              "finished_at_utc": datetime.now(UTC).isoformat(), "machine": machine, "rows": rows, "summary": summary}
    try:
        (args.out / "sse_ttfb_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    except OSError:
        print("Không thể ghi tệp kết quả.", file=sys.stderr)
        return 2
    print(json.dumps(summary))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
