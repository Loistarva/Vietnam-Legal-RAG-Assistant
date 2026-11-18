"""scripts/run_rag_cli.py on the mock pipeline (Sprint 10 D5.2)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("run_rag_cli", ROOT / "scripts" / "run_rag_cli.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

LEGAL = "Nam phải đủ bao nhiêu tuổi để kết hôn?"


@pytest.fixture(autouse=True)
def _no_live_env(monkeypatch):
    for name in ("LEGAL_RAG_PIPELINE_MODE", "RAG_PRECOMPUTED", "LEGAL_RAG_EVENT_LOG"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(("query", "code", "expected"), [
    (LEGAL, 0, "status: SUCCESS"),
    ("Hôm nay thời tiết Hà Nội thế nào?", 0, "route: NON_LEGAL"),
    ("Thủ tục thành lập doanh nghiệp tư nhân thế nào?", 4, "route: LEGAL_OUT_OF_SCOPE"),
    (f"{LEGAL} [mock:empty]", 4, "error_code: RETRIEVAL_EMPTY"),
    (f"{LEGAL} [mock:clarify]", 3, "Cần làm rõ:"),
    (f"{LEGAL} [mock:timeout]", 1, "Lỗi LLM_TIMEOUT"),
])
def test_branches_and_exit_codes(capsys, query, code, expected):
    assert cli.main(["--mock", query]) == code
    out = capsys.readouterr().out
    assert expected in out
    assert "Thông tin chỉ mang tính tham khảo" in out  # disclaimer on every branch


def test_success_prints_answer_citations_and_evidence(capsys):
    assert cli.main(["--mock", "--as-of-date", "2026-01-01", LEGAL]) == 0
    out = capsys.readouterr().out
    assert "Căn cứ trích dẫn:" in out and "[1] [MOCK]" in out and "Evidence (2):" in out


def test_gate_fail_does_not_print_the_draft(capsys):
    assert cli.main(["--mock", f"{LEGAL} [mock:gate_fail]"]) == 4
    out = capsys.readouterr().out
    assert "grounding: FAIL" in out and "Bản nháp" not in out


def test_json_output_is_an_ask_response(capsys):
    from schemas.models import AskResponse

    assert cli.main(["--mock", "--json", "--query-id", "cli-1", LEGAL]) == 0
    body = AskResponse.model_validate(json.loads(capsys.readouterr().out))
    assert body.query_id == "cli-1" and body.status == "SUCCESS"


def test_invalid_date_exits_2(capsys):
    assert cli.main(["--mock", "--as-of-date", "2026-02-30", LEGAL]) == 2
    assert "as_of_date" in capsys.readouterr().err


def test_missing_or_duplicate_query_is_usage_error():
    with pytest.raises(SystemExit) as missing:
        cli.main(["--mock"])
    assert missing.value.code == 2
    with pytest.raises(SystemExit) as twice:
        cli.main(["--mock", "--query", LEGAL, LEGAL])
    assert twice.value.code == 2


def test_event_log_written_with_one_query_id(tmp_path, capsys):
    log = tmp_path / "cli_events.jsonl"
    assert cli.main(["--mock", "--event-log", str(log), "--query-id", "cli-log", LEGAL]) == 0
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert rows and {row["query_id"] for row in rows} == {"cli-log"}
    assert rows[0]["stage"] == "router" and rows[-1]["stage"] == "response"
