"""
scripts/verify_qwen_live.py
Kiểm chứng QwenGateway với Ollama + qwen2.5:7b thật (Tasks D3.3, D3.4 - DoD-10).

Script chỉ chạy với Ollama thật. Không có Ollama hoặc chưa pull model thì dừng với mã lỗi 1
và không ghi report: kiểm tra cấu trúc bằng transport giả đã nằm trong
test/test_dev3_sprint9_contracts_prompt_gateway.py, không được dùng làm bằng chứng DoD-10.

Dữ liệu chạy:
- Câu hỏi và as_of_date lấy từ data/benchmark/queries_dev.json theo --query-id
  (as_of_date_source=benchmark). Không nhận câu thuộc Test hoặc thuộc 30 ID official
  (evaluation/rubrics/dev_gold_30_ids_v1.txt), vì 30 câu này chỉ chạy sau Freeze.
- Evidence của Run B lấy từ kết quả Hybrid + Reranker đã chạy
  (retrieval/results/dev_hybrid_reranker.json): Top rerank_top_k theo reranking/config.yaml,
  parent_text nếu có (do Parent-Context Resolver gắn), dừng trước khi vượt max_context_chars.
  Đây là smoke test của gateway; ContextPayload chính thức do orchestration (D5.3) dựng.

Kết quả: report JSON (mặc định reports/dev3_live_qwen_verification.json) gồm Ollama version,
model digest, tham số gateway, prompt hash, metadata runtime của Run A/B và các kiểm tra
tính từ response thật. Mã thoát 1 nếu có kiểm tra FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from generation.prompt_builder import (
    PROMPT_A_VERSION,
    PROMPT_B_VERSION,
    build_controlled_rag_prompt,
    build_zero_shot_prompt,
    get_prompt_hash,
)
from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH, QwenGateway
from schemas.models import CandidateChunk, ContextPayload, EvidenceItem, LLMResponse

DEFAULT_QUERY_ID = "HN_003"  # Dev, source_checked, không thuộc 30 ID official
QUERIES_DEV = ROOT_DIR / "data" / "benchmark" / "queries_dev.json"
OFFICIAL_IDS = ROOT_DIR / "evaluation" / "rubrics" / "dev_gold_30_ids_v1.txt"
RERANK_RESULTS = ROOT_DIR / "retrieval" / "results" / "dev_hybrid_reranker.json"
RERANK_CONFIG = ROOT_DIR / "reranking" / "config.yaml"


def load_dev_query(query_id: str) -> dict[str, Any]:
    official = set(OFFICIAL_IDS.read_text(encoding="utf-8").split())
    if query_id in official:
        raise SystemExit(f"{query_id} thuộc 30 ID official; chỉ được chạy sau Freeze, chọn câu Dev khác")
    queries = json.loads(QUERIES_DEV.read_text(encoding="utf-8-sig"))
    for query in queries:
        if query.get("id") == query_id:
            if query.get("split") != "dev":
                raise SystemExit(f"{query_id} không thuộc Dev split")
            if not query.get("as_of_date"):
                raise SystemExit(f"{query_id} thiếu as_of_date trong {QUERIES_DEV.name}")
            return query
    raise SystemExit(f"Không tìm thấy {query_id} trong {QUERIES_DEV.name} (câu Test không được dùng)")


def build_context_payload(query: dict[str, Any]) -> ContextPayload:
    config = yaml.safe_load(RERANK_CONFIG.read_text(encoding="utf-8"))
    top_k = int(config["reranker"]["rerank_top_k"])
    max_chars = int(config["parent_context"]["max_context_chars"])

    envelopes = json.loads(RERANK_RESULTS.read_text(encoding="utf-8"))
    envelope = next((e for e in envelopes if e["query_id"] == query["id"]), None)
    if envelope is None or not envelope["results"]:
        raise SystemExit(f"{RERANK_RESULTS.name} không có kết quả cho {query['id']}")

    items: list[EvidenceItem] = []
    used_chars = 0
    for raw in sorted(envelope["results"], key=lambda r: r["rank"])[:top_k]:
        candidate = CandidateChunk.from_retrieval_item(
            raw, query_id=query["id"], as_of_date=query["as_of_date"], retriever=envelope["retriever"]
        )
        content = candidate.parent_text or candidate.chunk_text
        if used_chars + len(content) > max_chars:
            break
        used_chars += len(content)
        meta = candidate.metadata
        items.append(EvidenceItem(
            evidence_index=len(items) + 1,
            chunk_id=candidate.chunk_id,
            parent_clause_id=candidate.parent_clause_id or candidate.clause_id,
            document_id=candidate.document_id,
            article_id=candidate.article_id,
            clause_id=candidate.clause_id,
            content=content,
            validity_status=candidate.validity_status,
            effective_from=candidate.effective_from,
            effective_to=candidate.effective_to,
            source_url=meta.get("source_url"),
            document_number=meta.get("document_number"),
            document_title=meta.get("document_title"),
            article_number=meta.get("article_number"),
            clause_number=meta.get("clause_number"),
            breadcrumb=meta.get("breadcrumb"),
            provision_status=meta.get("provision_status"),
        ))
    if not items:
        raise SystemExit(f"Evidence đầu tiên của {query['id']} đã vượt max_context_chars={max_chars}")

    return ContextPayload(
        query_id=query["id"],
        query=query["question"],
        as_of_date=query["as_of_date"],
        as_of_date_source="benchmark",
        evidence_items=items,
        max_context_chars=max_chars,
    )


def run_record(resp: LLMResponse, prompt: str) -> dict[str, Any]:
    return {
        "prompt_version": resp.prompt_version,
        "prompt_hash": get_prompt_hash(prompt),
        "response": resp.model_dump(mode="json"),
    }


def evaluate_checks(gateway: QwenGateway, resp_a: LLMResponse, resp_b: LLMResponse,
                    evidence_count: int) -> dict[str, str]:
    def status(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    b_indices_ok = all(1 <= idx <= evidence_count for idx in resp_b.evidence_indices)
    return {
        "ollama_version_recorded": status(bool(gateway.ollama_version)),
        "model_digest_recorded": status(bool(gateway.model_digest)),
        "a_done_reason_stop": status(resp_a.done_reason == "stop"),
        "b_done_reason_stop": status(resp_b.done_reason == "stop"),
        "no_output_truncation": status(not resp_a.truncated and not resp_b.truncated),
        "no_context_truncation": status(not resp_a.context_truncated and not resp_b.context_truncated),
        "b_structured_output_parsed": status(resp_b.parse_status == "ok"),
        "b_evidence_indices_in_context": status(b_indices_ok and not resp_b.rejected_evidence_values),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiểm chứng QwenGateway với Ollama thật (DoD-10).")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="File cấu hình gateway")
    parser.add_argument("--query-id", default=DEFAULT_QUERY_ID, help="ID câu Dev ngoài 30 ID official")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "reports" / "dev3_live_qwen_verification.json",
        help="File report JSON",
    )
    args = parser.parse_args()

    gateway = QwenGateway(args.config)
    cfg = gateway.config
    print(f"[*] Gateway: base_url={cfg.base_url}, model={cfg.model}, num_ctx={cfg.num_ctx}, num_predict={cfg.num_predict}")
    if not gateway.ollama_version or not gateway.model_digest:
        print(f"[X] Không đọc được Ollama version hoặc digest của {cfg.model} tại {cfg.base_url}.")
        print("    Bật Ollama ('ollama serve'), pull model ('ollama pull " + cfg.model + "') rồi chạy lại.")
        print("    Không ghi report: script này chỉ ghi kết quả chạy thật.")
        sys.exit(1)
    print(f"[✓] Ollama {gateway.ollama_version}, digest {gateway.model_digest}")

    query = load_dev_query(args.query_id)
    context_payload = build_context_payload(query)
    print(f"[*] {query['id']} (as_of_date {query['as_of_date']}, benchmark), {len(context_payload.evidence_items)} evidence, "
          f"{context_payload.total_chars} ký tự")

    prompt_a = build_zero_shot_prompt(query=query["question"], as_of_date=query["as_of_date"])
    resp_a = gateway.generate(prompt=prompt_a, query_id=query["id"], run_mode="A_zero_shot",
                              prompt_version=PROMPT_A_VERSION)
    print(f"[A] done_reason={resp_a.done_reason}, tokens={resp_a.token_usage}, latency={resp_a.latency_ms} ms")

    prompt_b = build_controlled_rag_prompt(context_payload)
    resp_b = gateway.generate(prompt=prompt_b, query_id=query["id"], run_mode="B_controlled_rag",
                              prompt_version=PROMPT_B_VERSION, structured_output=True)
    print(f"[B] done_reason={resp_b.done_reason}, parse={resp_b.parse_status}, indices={resp_b.evidence_indices}, "
          f"tokens={resp_b.token_usage}, latency={resp_b.latency_ms} ms")

    checks = evaluate_checks(gateway, resp_a, resp_b, len(context_payload.evidence_items))
    report = {
        "report_id": "dev3_live_qwen_verification",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_reference": "Sprint 9 Dev 3 (Tasks D3.3, D3.4 - DoD-10)",
        "execution_mode": "live_ollama",
        "ollama": {
            "base_url": cfg.base_url,
            "version": gateway.ollama_version,
            "model": cfg.model,
            "model_digest": gateway.model_digest,
        },
        "gateway_config": cfg.model_dump(mode="json"),
        "query": {
            "query_id": query["id"],
            "question": query["question"],
            "as_of_date": query["as_of_date"],
            "as_of_date_source": "benchmark",
        },
        "evidence": {
            "source_file": RERANK_RESULTS.relative_to(ROOT_DIR).as_posix(),
            "chunk_ids": [item.chunk_id for item in context_payload.evidence_items],
            "total_chars": context_payload.total_chars,
            "max_context_chars": context_payload.max_context_chars,
        },
        "runs": {
            "run_a_zero_shot": run_record(resp_a, prompt_a),
            "run_b_controlled_rag": run_record(resp_b, prompt_b),
        },
        "checks": checks,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[✓] Report: {args.output}")
    for name, value in checks.items():
        print(f"    {value}  {name}")
    if any(value != "PASS" for value in checks.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
