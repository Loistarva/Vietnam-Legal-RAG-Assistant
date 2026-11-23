"""Tests for scripts/verify_qwen_live.py: chỉ ghi report khi chạy Ollama thật, dữ liệu lấy từ benchmark."""
import json
import sys

import pytest

from model_gateway.llm_gateway import QwenGateway
from scripts import verify_qwen_live as verify


def test_refuses_official_and_test_questions():
    with pytest.raises(SystemExit, match="30 ID official"):
        verify.load_dev_query("HN_001")
    test_ids = [q["id"] for q in json.loads(
        (verify.ROOT_DIR / "data" / "benchmark" / "queries_test.json").read_text(encoding="utf-8-sig")
    )]
    with pytest.raises(SystemExit, match="Không tìm thấy"):
        verify.load_dev_query(test_ids[0])


def test_context_payload_comes_from_benchmark_and_rerank_results():
    query = verify.load_dev_query(verify.DEFAULT_QUERY_ID)
    payload = verify.build_context_payload(query)
    assert payload.as_of_date == query["as_of_date"]
    assert payload.as_of_date_source == "benchmark"
    indices = [item.evidence_index for item in payload.evidence_items]
    assert indices == list(range(1, len(indices) + 1)) and len(indices) <= 5
    assert payload.total_chars <= payload.max_context_chars
    envelope = next(
        e for e in json.loads(verify.RERANK_RESULTS.read_text(encoding="utf-8")) if e["query_id"] == query["id"]
    )
    ranked = [r["chunk_id"] for r in sorted(envelope["results"], key=lambda r: r["rank"])]
    assert [item.chunk_id for item in payload.evidence_items] == ranked[: len(indices)]


def _run_main(monkeypatch, tmp_path, gateway_factory):
    output = tmp_path / "report.json"
    monkeypatch.setattr(verify, "QwenGateway", gateway_factory)
    monkeypatch.setattr(sys, "argv", ["verify_qwen_live.py", "--output", str(output)])
    return output


def test_exits_without_report_when_ollama_is_offline(monkeypatch, tmp_path):
    def offline_gateway(config):
        return QwenGateway(config, transport=lambda url, payload, timeout: {})

    output = _run_main(monkeypatch, tmp_path, offline_gateway)
    with pytest.raises(SystemExit) as exc:
        verify.main()
    assert exc.value.code == 1
    assert not output.exists()


def test_writes_report_with_checks_from_real_responses(monkeypatch, tmp_path):
    def transport(url, payload, timeout):
        body = (
            json.dumps({"answer": "Có.", "evidence_indices": [1], "abstained": False})
            if "format" in payload else "Có."
        )
        return {"model": "qwen2.5:7b", "response": body, "done": True, "done_reason": "stop",
                "prompt_eval_count": 900, "eval_count": 40}

    def live_gateway(config):
        gateway = QwenGateway(config, transport=transport)
        gateway.ollama_version = "0.6.2"
        gateway.model_digest = "sha256:abc"
        return gateway

    output = _run_main(monkeypatch, tmp_path, live_gateway)
    verify.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["execution_mode"] == "live_ollama"
    assert report["query"]["as_of_date_source"] == "benchmark"
    assert set(report["checks"].values()) == {"PASS"}
    assert report["runs"]["run_b_controlled_rag"]["response"]["evidence_indices"] == [1]
