import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from scripts import measure_sse_ttfb as cli

pytestmark = [pytest.mark.req("NFR2.1"), pytest.mark.req("NFR2.1-AC1")]

QUESTION = "Câu hỏi riêng tư?"
ANSWER = "Câu trả lời riêng tư."
KEY = "private-api-key"


def block(event, seq, data):
    return [f"event: {event}".encode(), f"id: {seq}".encode(), b"data: " + json.dumps(data).encode(), b""]


class Response:
    def __init__(self, lines=(), http=200):
        self.lines = lines
        self.status_code = http
        self.drained = False

    def iter_lines(self, *, chunk_size):
        for line in self.lines:
            if isinstance(line, Exception):
                raise line
            yield line
        self.drained = True

    def json(self):
        return {"error_code": "INTERNAL_ERROR", "message": QUESTION}


@pytest.fixture
def run(tmp_path, monkeypatch):
    ids = tmp_path / "ids.txt"
    ids.write_text("Q2\nQ1\n", encoding="utf-8")
    benchmark = tmp_path / "benchmark.json"
    records = [{"id": qid, "question": QUESTION + qid, "as_of_date": "2026-11-01"} for qid in ("Q1", "Q2")]
    benchmark.write_text(json.dumps(records), encoding="utf-8")
    out = tmp_path / "results"
    args = ["--ids", str(ids), "--benchmark", str(benchmark), "--out", str(out), "--api-sha", "abc123"]
    session = Mock(headers={})
    session.get.return_value = nullcontext(Response())
    monkeypatch.setattr(cli.requests, "Session", lambda: nullcontext(session))
    monkeypatch.setattr(cli, "machine_info", lambda: {"cpu": "mock"})
    monkeypatch.setenv("LEGAL_RAG_API_URL", "http://test/")
    monkeypatch.setenv("LEGAL_RAG_API_KEY", KEY)
    return SimpleNamespace(args=args, session=session, ids=ids, benchmark=benchmark,
                           report=out / "sse_ttfb_results.json")


def test_complete_blocks(monkeypatch):
    times = iter([1, 2, 3])
    monkeypatch.setattr(cli, "perf_counter", lambda: next(times))
    response = Response([b"event: status", b"id: 0", b'data: {"elapsed_ms":', b"data: 12}", b"",
                         *block("final", 1, {"status": "SUCCESS"}), b"event: error", b"data: {}"])
    assert list(cli.events(response)) == [
        ("status", 1, {"elapsed_ms": 12}), ("final", 2, {"status": "SUCCESS"}),
    ]
    assert response.drained


def test_nearest_rank():
    rows = [{"first_status_ms": i, "final_ms": 2 * i, "status": "SUCCESS"} for i in range(20, 0, -1)]
    assert cli.summarize(rows) == {"n": 20, "n_ok": 20, "first_status_p50_ms": 10, "first_status_p95_ms": 19,
                                   "final_p50_ms": 20, "final_p95_ms": 38, "threshold_ms": 2000, "pass": True}


@pytest.mark.parametrize(("delay", "exit_code"), [(1.5, 0), (2, 1)])
def test_cli_threshold_and_privacy(run, monkeypatch, capsys, delay, exit_code):
    lines = [*block("status", 0, {"elapsed_ms": 7}), *block("status", 1, {"elapsed_ms": 18}),
             *block("final", 2, {"status": "ABSTAIN", "error_code": "LOW_CONFIDENCE", "answer": ANSWER})]
    replies = [Response(lines), Response(lines)]
    run.session.post.side_effect = [nullcontext(reply) for reply in replies]
    times = iter([0, delay, 3, 6, 10, 10.1, 11, 12])
    monkeypatch.setattr(cli, "perf_counter", lambda: next(times))
    assert cli.main(run.args) == exit_code
    run.session.get.assert_called_once_with("http://test/api/v1/health", timeout=600, allow_redirects=False)
    assert run.session.headers == {"X-API-Key": KEY}
    for call, qid in zip(run.session.post.call_args_list, ["Q2", "Q1"], strict=True):
        assert call.args == ("http://test/api/v1/ask/stream",)
        assert call.kwargs == {"json": {"query": QUESTION + qid, "as_of_date": "2026-11-01"},
                               "stream": True, "timeout": 600, "allow_redirects": False}
    assert all(reply.drained for reply in replies)
    raw = run.report.read_text(encoding="utf-8")
    log = capsys.readouterr()
    for secret in (QUESTION, ANSWER, KEY):
        assert secret not in raw + log.out + log.err
    report = json.loads(raw)
    assert report["schema"] == "sse_ttfb_v1" and report["api_sha"] == "abc123"
    assert report["rows"][0] == {"query_id": "Q2", "http": 200, "first_status_ms": delay * 1000,
                                 "server_first_status_ms": 7, "final_ms": 6000, "final_event": "final",
                                 "status": "ABSTAIN", "error_code": "LOW_CONFIDENCE"}
    assert report["summary"]["n_ok"] == 2
    assert report["summary"]["pass"] == (exit_code == 0)


@pytest.mark.parametrize("failure", ["http", "timeout", "drop", "incomplete", "error"])
def test_failed_row(run, failure):
    status = block("status", 0, {"elapsed_ms": 5})
    complete = Response([*status, *block("final", 1, {"status": "SUCCESS"})])
    first = {
        "http": nullcontext(Response(http=500)),
        "timeout": requests.Timeout(),
        "drop": nullcontext(Response([*status, requests.ConnectionError()])),
        "incomplete": nullcontext(Response(status)),
        "error": nullcontext(Response([*status, *block("error", 1, {"error_code": "INTERNAL_ERROR"})])),
    }[failure]
    run.session.post.side_effect = [first, nullcontext(complete)]
    assert cli.main(run.args) == 1
    result = json.loads(run.report.read_text(encoding="utf-8"))
    failed, ok = result["rows"]
    assert result["summary"]["n"] == 2 and result["summary"]["n_ok"] == 1
    assert failed["http"] == {"http": 500, "timeout": 0}.get(failure, 200)
    assert failed["status"] == "ERROR" and ok["status"] == "SUCCESS"
    if failure in ("http", "error"):
        assert failed["error_code"] == "INTERNAL_ERROR"
    if failure == "error":
        assert failed["final_event"] == "error" and failed["final_ms"] >= failed["first_status_ms"]
    else:
        assert all(failed[k] is None for k in ("first_status_ms", "server_first_status_ms", "final_ms", "final_event"))
        assert result["summary"]["first_status_p95_ms"] == ok["first_status_ms"]


@pytest.mark.parametrize("reason", ["missing_key", "unknown_id", "bad_date", "api_down"])
def test_setup_errors(run, monkeypatch, reason):
    if reason == "missing_key":
        monkeypatch.delenv("LEGAL_RAG_API_KEY")
    elif reason == "unknown_id":
        run.ids.write_text("Q2\nunknown\n", encoding="utf-8")
    elif reason == "bad_date":
        run.benchmark.write_text(run.benchmark.read_text().replace("2026-11-01", "2026-02-30"))
    else:
        run.session.get.side_effect = requests.ConnectionError()
    assert cli.main(run.args) == 2
    run.session.post.assert_not_called()
    assert not run.report.exists()


def test_machine_record(monkeypatch):
    monkeypatch.setattr(cli.platform, "processor", lambda: "")
    monkeypatch.setenv("PROCESSOR_IDENTIFIER", "cpu")
    monkeypatch.setitem(cli.sys.modules, "psutil", None)
    probe = Mock(return_value=SimpleNamespace(stdout="gpu A, 4096 MiB\ngpu B, 8192 MiB\n"))
    monkeypatch.setattr(cli.subprocess, "run", probe)
    monkeypatch.setattr(cli.platform, "platform", lambda: "platform")
    record = cli.machine_info()
    assert record == {"platform": "platform", "cpu": "cpu", "python": cli.platform.python_version(),
                      "logical_cpus": cli.os.cpu_count(), "ram_gb": None, "gpu": "gpu A, 4096 MiB"}
    probe.side_effect = FileNotFoundError
    assert cli.machine_info()["gpu"] is None
