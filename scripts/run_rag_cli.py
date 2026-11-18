"""Ask one question through the shared pipeline (Sprint 10 D5.2).

    python scripts/run_rag_cli.py "Nam phải đủ bao nhiêu tuổi để kết hôn?"
    python scripts/run_rag_cli.py --as-of-date 2026-01-01 "..."
    python scripts/run_rag_cli.py --mock "Điều kiện kết hôn là gì? [mock:gate_fail]"
    python scripts/run_rag_cli.py --json "..."

Same ``AskService`` as the API (router -> RAGPipeline -> Grounding Gate); no retrieval or
model client of its own. Live mode reads ``ELASTICSEARCH_URL``, ``QDRANT_URL``/``QDRANT_PATH``
and Ollama from model_gateway/config/local_qwen.yaml; ``--mock`` needs none of them.

Date: a date stated in the question wins, then ``--as-of-date``, then today.
The model draft is never printed: a Gate FAIL prints the no-conclusion message.

Exit codes: 0 SUCCESS, 3 NEEDS_CLARIFICATION, 4 ABSTAIN, 1 ERROR, 2 invalid input.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from orchestration.events import JsonlEventSink, NullEventSink  # noqa: E402
from orchestration.wiring import ServiceSettings, build_ask_service  # noqa: E402
from schemas.models import AskRequest, AskResponse  # noqa: E402

EXIT_CODES = {"SUCCESS": 0, "NEEDS_CLARIFICATION": 3, "ABSTAIN": 4, "ERROR": 1}
EXIT_INVALID_INPUT = 2


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hỏi một câu qua RAG pipeline dùng chung (CLI = API).")
    parser.add_argument("query", nargs="?", help="Câu hỏi (hoặc dùng --query)")
    parser.add_argument("--query", dest="query_flag", help="Câu hỏi")
    parser.add_argument("--as-of-date", help="Ngày tra cứu YYYY-MM-DD (ngày nêu trong câu hỏi được ưu tiên)")
    parser.add_argument("--query-id", help="query_id cố định (mặc định tự sinh)")
    parser.add_argument("--mock", action="store_true", help="Pipeline giả lập, không cần ES/Qdrant/Ollama")
    parser.add_argument("--precomputed", help="Artifact reranked thay cho retrieval live")
    parser.add_argument("--elasticsearch-url")
    parser.add_argument("--qdrant-url", help="Qdrant server")
    parser.add_argument("--qdrant-path", help="Qdrant embedded (một tiến trình)")
    parser.add_argument("--event-log", help="Ghi stage event (JSONL) vào file này")
    parser.add_argument("--json", action="store_true", help="In AskResponse dạng JSON")
    args = parser.parse_args(argv)
    if args.query and args.query_flag:
        parser.error("chỉ truyền câu hỏi một lần (positional hoặc --query)")
    args.query = args.query or args.query_flag
    if not args.query:
        parser.error("thiếu câu hỏi")
    return args


def settings_from_args(args: argparse.Namespace) -> ServiceSettings:
    env = ServiceSettings.from_env()
    return ServiceSettings(
        mode="mock" if args.mock else env.mode,
        precomputed=args.precomputed or env.precomputed,
        elasticsearch_url=args.elasticsearch_url or env.elasticsearch_url,
        qdrant_url=args.qdrant_url or env.qdrant_url,
        qdrant_path=args.qdrant_path or env.qdrant_path,
        event_log=args.event_log or env.event_log,
    )


def render(response: AskResponse) -> str:
    lines = [f"query_id: {response.query_id}",
             f"route: {response.route} | status: {response.status} | grounding: {response.grounding_status}",
             f"as_of_date: {response.as_of_date} ({response.as_of_date_source})"]
    if response.status == "SUCCESS":
        lines += ["", response.answer or ""]
    elif response.status == "NEEDS_CLARIFICATION":
        lines += ["", f"Cần làm rõ: {response.clarification}"]
    elif response.status == "ABSTAIN":
        lines += ["", response.abstention_message or "", f"(lý do: {response.abstention_reason}, "
                                                          f"error_code: {response.error_code})"]
    else:
        message = response.error.message if response.error else ""
        lines += ["", f"Lỗi {response.error_code}: {message}"]
    by_index = {item.evidence_index: item for item in response.evidence}
    if response.citations:
        lines += ["", "Căn cứ trích dẫn:"]
        for citation in response.citations:
            item = by_index.get(citation.evidence_index)
            title = (item.document_title or item.document_id) if item else citation.document_id
            where = (item.breadcrumb if item and item.breadcrumb else citation.clause_id)
            lines.append(f"  [{citation.evidence_index}] {title} - {where}")
    if response.evidence:
        lines += ["", f"Evidence ({len(response.evidence)}):"]
        for item in response.evidence:
            period = f"{item.effective_from or '?'} -> {item.effective_to or 'nay'}"
            lines.append(f"  [{item.evidence_index}] {item.chunk_id} | {item.validity_status} | {period}")
    timings = {k: v for k, v in response.timings.model_dump().items() if v is not None}
    if timings:
        lines += ["", "Thời gian (ms): " + ", ".join(f"{k}={v}" for k, v in timings.items())]
    lines += ["", response.disclaimer]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    try:
        request = AskRequest(query=args.query, as_of_date=args.as_of_date, query_id=args.query_id)
    except ValidationError as exc:
        print("Input không hợp lệ: " + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                                                for e in exc.errors()), file=sys.stderr)
        return EXIT_INVALID_INPUT
    settings = settings_from_args(args)
    sink = JsonlEventSink(settings.event_log) if settings.event_log else NullEventSink()
    service = build_ask_service(settings, sink=sink)
    response = service.run(request).response
    if args.json:
        print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(render(response))
    return EXIT_CODES[response.status]


if __name__ == "__main__":
    raise SystemExit(main())
