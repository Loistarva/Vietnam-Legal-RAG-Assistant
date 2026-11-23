"""Live E2E check: Web UI -> API -> Router -> RAG -> Gate -> log (Sprint 11 D5.4).

Needs a running API (``uvicorn api.main:app``) with Elasticsearch, Qdrant and Ollama behind it,
and ``LEGAL_RAG_EVENT_LOG`` set on the server. The UI cases run the real Streamlit script
(``frontend/streamlit_app.py``, mode "API") through ``streamlit.testing.v1.AppTest``, so the UI's
own ``api_client`` sends the HTTP request; no browser and no screenshot.

Usage (PowerShell)::

    $env:LEGAL_RAG_API_KEY = "<the server key>"
    python scripts/run_live_e2e.py --event-log <server event log> --out reports/week11/live

Writes ``live_e2e_results.json`` (one row per case, no API key, no answer text beyond 300
characters) and prints one line per case. Exit code 1 when a check fails.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
FULL_RAG = ["api", "router", "retrieval", "rerank", "confidence", "context", "llm", "citation", "gate", "response"]
SHORT = ["api", "router", "response"]
CONFIDENCE_ABSTAIN = ["api", "router", "retrieval", "rerank", "confidence", "response"]

# (case, body, expected status, grounding_status, error_code, expected stage order)
API_CASES: list[tuple[str, dict[str, Any], str, str, str | None, list[str]]] = [
    ("legal_marriage_age", {"query": "Nam phải đủ bao nhiêu tuổi thì được kết hôn?", "as_of_date": "2026-11-23"},
     "SUCCESS", "PASS", None, FULL_RAG),
    ("legal_common_property", {"query": "Vợ chồng có quyền và nghĩa vụ gì đối với tài sản chung?",
                               "as_of_date": "2026-11-23"}, "SUCCESS", "PASS", None, FULL_RAG),
    ("legal_date_in_question", {"query": "Tại ngày 01/01/2015, điều kiện kết hôn về độ tuổi là gì?"},
     "SUCCESS", "PASS", None, FULL_RAG),
    ("non_legal", {"query": "Hôm nay thời tiết Hà Nội thế nào?"}, "SUCCESS", "NOT_RUN", None, SHORT),
    ("out_of_scope", {"query": "Thủ tục thành lập doanh nghiệp tư nhân thế nào?"},
     "ABSTAIN", "NOT_RUN", "ROUTE_POLICY", SHORT),
    ("low_confidence_HN_035", {"query": "Theo quy định HNGĐ hiện hành năm 2026, kết hôn cùng giới vẫn là hành vi "
                                        "bị cấm theo Luật 2000 đúng không?", "as_of_date": "2026-10-15"},
     "ABSTAIN", "NOT_RUN", "LOW_CONFIDENCE", CONFIDENCE_ABSTAIN),
]
UI_CASES = [
    ("ui_legal", "Nữ phải đủ bao nhiêu tuổi thì được kết hôn?", "SUCCESS"),
    ("ui_non_legal", "Xin chào, bạn là ai?", "SUCCESS"),
    ("ui_out_of_scope", "Thủ tục thành lập doanh nghiệp tư nhân thế nào?", "ABSTAIN"),
]


def ordered(stages: list[str], expected: list[str]) -> bool:
    """``expected`` equals the first occurrences of the known stages, in order."""
    seen = [s for s in dict.fromkeys(stages) if s in set(FULL_RAG) | {"confidence"}]
    return seen == expected


def short_row(body: dict[str, Any]) -> dict[str, Any]:
    answer = body.get("answer") or ""
    return {"status": body.get("status"), "route": body.get("route"), "grounding": body.get("grounding_status"),
            "error_code": body.get("error_code"), "reason": body.get("abstention_reason"),
            "query_id": body.get("query_id"), "as_of_date": body.get("as_of_date"),
            "as_of_date_source": body.get("as_of_date_source"),
            "citations": [f"{c.get('article_number') or ''}|{c.get('chunk_id')}" for c in body.get("citations", [])],
            "evidence": len(body.get("evidence") or []), "timings": body.get("timings"),
            "answer_head": answer[:300], "disclaimer_once": bool(body.get("disclaimer"))
            and answer.count(body.get("disclaimer") or "\0") == 0}


def run_api_cases(base: str, key: str) -> list[dict[str, Any]]:
    rows = []
    headers = {"X-API-Key": key}
    rejects = [("auth_missing", {}, {"query": "Nam bao nhiêu tuổi được kết hôn?"}, 401, "AUTH_REQUIRED"),
               ("auth_wrong", {"X-API-Key": "wrong-" + "0" * 24}, {"query": "Nam bao nhiêu tuổi được kết hôn?"},
                401, "AUTH_REQUIRED"),
               ("invalid_empty_query", headers, {"query": ""}, 422, "INVALID_REQUEST"),
               ("query_over_2000", headers, {"query": "a" * 2001}, 422, "INVALID_REQUEST")]
    for name, hdrs, body, http, code in rejects:
        started = time.perf_counter()
        response = requests.post(f"{base}/ask", json=body, headers=hdrs, timeout=60)
        data = response.json()
        rows.append({"case": name, "http": response.status_code, "wall_ms": round((time.perf_counter() - started) * 1000),
                     "error_code": data.get("error_code"), "query_id": data.get("query_id"),
                     "no_detail_body": "detail" not in data,
                     "ok": response.status_code == http and data.get("error_code") == code and "detail" not in data,
                     "expected_stages": ["api"]})
    for name, body, status, grounding, code, stages in API_CASES:
        started = time.perf_counter()
        response = requests.post(f"{base}/ask", json=body, headers=headers, timeout=900)
        data = response.json()
        row = {"case": name, "http": response.status_code, "wall_ms": round((time.perf_counter() - started) * 1000),
               **short_row(data), "expected_stages": stages,
               "header_query_id_matches": response.headers.get("X-Query-ID") == data.get("query_id")}
        row["ok"] = (response.status_code == 200 and (data.get("status"), data.get("grounding_status"),
                     data.get("error_code")) == (status, grounding, code) and row["header_query_id_matches"]
                     and (status == "SUCCESS") == bool(data.get("answer")))
        rows.append(row)
    return rows


def run_ui_cases(api_url: str, key: str) -> list[dict[str, Any]]:
    from streamlit.testing.v1 import AppTest

    os.environ["LEGAL_RAG_API_URL"] = api_url
    os.environ["LEGAL_RAG_API_KEY"] = key
    os.environ.setdefault("LEGAL_RAG_REQUEST_TIMEOUT_SECONDS", "900")
    app = AppTest.from_file(str(ROOT / "frontend" / "streamlit_app.py"), default_timeout=900)
    app.run()
    app.radio[0].set_value("API").run()
    rows = []
    for name, question, status in UI_CASES:
        started = time.perf_counter()
        app.chat_input[0].set_value(question).run()
        last = app.session_state["messages"][-1]
        payload = last.get("payload") or {}
        texts = [m.value for m in app.markdown] + [c.value for c in app.caption]
        disclaimer = payload.get("disclaimer") or ""
        row = {"case": name, "wall_ms": round((time.perf_counter() - started) * 1000), **short_row(payload),
               "ui_errors": [e.value for e in app.error], "history_len": len(app.session_state["messages"]),
               "disclaimer_rendered": sum(disclaimer in t for t in texts) if disclaimer else 0,
               "answer_rendered": bool(payload.get("answer")) and any(payload["answer"][:40] in t for t in texts),
               "expected_stages": FULL_RAG if name == "ui_legal" else SHORT}
        row["ok"] = (payload.get("status") == status and not row["ui_errors"] and row["disclaimer_rendered"] >= 1
                     and (status != "SUCCESS" or row["answer_rendered"]))
        rows.append(row)
    return rows


def attach_log(rows: list[dict[str, Any]], log_path: Path, key: str) -> dict[str, Any]:
    raw = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    by_query: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_query.setdefault(event["query_id"], []).append(event)
    for row in rows:
        stream = by_query.get(row.get("query_id") or "", [])
        row["log_stages"] = [e["stage"] for e in stream]
        row["log_order_ok"] = bool(stream) and ordered(row["log_stages"], row["expected_stages"])
        if row["case"].startswith("auth_"):
            row["log_order_ok"] = any(e.get("error_code") == "AUTH_REQUIRED" for e in stream)
        row["ok"] = row["ok"] and row["log_order_ok"]
    return {"events": len(events), "all_lines_json": True, "api_key_in_log": key in raw,
            "wrong_key_in_log": ("wrong-" + "0" * 24) in raw}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--event-log", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--skip-ui", action="store_true")
    args = parser.parse_args(argv)
    key = os.environ.get("LEGAL_RAG_API_KEY", "")
    if not key:
        parser.error("LEGAL_RAG_API_KEY chưa đặt")
    health = requests.get(f"{args.base_url}/health", timeout=10).json()
    rows = run_api_cases(args.base_url, key)
    if not args.skip_ui:
        rows += run_ui_cases(f"{args.base_url}/ask", key)
    time.sleep(2.5)  # the server logger writes from a background queue
    log = attach_log(rows, args.event_log, key)
    ok = all(r["ok"] for r in rows) and not log["api_key_in_log"] and not log["wrong_key_in_log"]
    args.out.mkdir(parents=True, exist_ok=True)
    result = {"health": health, "log": log, "ok": ok, "cases": rows}
    (args.out / "live_e2e_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
    for r in rows:
        print(json.dumps({k: r.get(k) for k in ("case", "http", "wall_ms", "status", "grounding", "error_code",
                                                "log_stages", "ok")}, ensure_ascii=False))
    print(json.dumps({"log": log, "ok": ok}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
