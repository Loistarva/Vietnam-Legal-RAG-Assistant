"""P45-9: Run A goes through the Qwen Gateway with Prompt A and the same generation parameters as Run B."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evaluation import zero_shot
from generation.prompt_builder import LANGUAGE_RULE_A, PROMPT_A_VERSION
from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH, QwenGateway

DURATIONS_NS = {"load_duration": 2_000_000_000, "prompt_eval_duration": 500_000_000,
                "eval_duration": 6_000_000_000, "total_duration": 8_600_000_000}


def _questions(tmp_path: Path, rows=None) -> Path:
    rows = rows if rows is not None else [
        {"id": "HN_001", "question": "Nam bao nhiêu tuổi được kết hôn?", "as_of_date": "2026-10-15"},
        {"id": "HN_002", "question": "Nữ bao nhiêu tuổi được kết hôn?", "as_of_date": "2024-01-01"},
    ]
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


class Recorder:
    def __init__(self, answer="Theo quy định, nam từ đủ 20 tuổi.", fail_on=None):
        self.payloads: list[dict] = []
        self.answer, self.fail_on = answer, fail_on

    def __call__(self, url, payload, timeout):
        if self.fail_on and self.fail_on in payload["prompt"]:
            raise RuntimeError("boom")
        self.payloads.append(payload)
        return {"model": payload["model"], "response": self.answer, "done": True, "done_reason": "stop",
                "prompt_eval_count": 300, "eval_count": 120, **DURATIONS_NS}


def test_load_questions_requires_benchmark_as_of_date(tmp_path):
    with pytest.raises(ValueError, match="as_of_date"):
        zero_shot.load_questions(_questions(tmp_path, [{"id": "HN_001", "question": "Q?"}]))
    with pytest.raises(ValueError, match="as_of_date"):
        zero_shot.load_questions(_questions(tmp_path, [{"id": "HN_001", "question": "Q?", "as_of_date": "15/10/2026"}]))


def test_run_a_uses_prompt_a_gateway_options_and_benchmark_date(tmp_path):
    transport = Recorder()
    output = tmp_path / "out" / "20261113_zero_shot_qwen25_dev30_results.json"
    zero_shot.run_benchmark(_questions(tmp_path), output, gateway=QwenGateway(transport=transport))

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    for payload, as_of_date in zip(transport.payloads, ("2026-10-15", "2024-01-01")):
        assert payload["options"] == {key: config[key] for key in
                                      ("temperature", "repeat_penalty", "num_predict", "num_ctx")}
        assert payload["options"]["repeat_penalty"] == 1.0 and payload["options"]["num_predict"] == 1024
        assert "repeat_last_n" not in payload["options"] and "format" not in payload
        assert f"Phiên bản hướng dẫn: {PROMPT_A_VERSION}" in payload["prompt"]
        assert f"Theo quy định có hiệu lực tại ngày {as_of_date}" in payload["prompt"]
        assert LANGUAGE_RULE_A in payload["prompt"]


def test_run_a_records_and_manifest(tmp_path):
    output = tmp_path / "run_a_results.json"
    zero_shot.run_benchmark(_questions(tmp_path), output, gateway=QwenGateway(transport=Recorder()))
    records = json.loads(output.read_text(encoding="utf-8"))
    assert [r["query_id"] for r in records] == ["HN_001", "HN_002"]
    record = records[0]
    assert record["prompt_version"] == PROMPT_A_VERSION and record["run_mode"] == "A_zero_shot"
    assert record["as_of_date"] == "2026-10-15" and record["as_of_date_source"] == "benchmark"
    assert record["done_reason"] == "stop" and record["truncated"] is False
    assert record["token_usage"] == {"input": 300, "output": 120}
    assert record["llm_calls"] == 1 and record["latency_ms"] >= 0
    assert record["latency_breakdown"] == {
        "retrieval_ms": None, "llm_total_ms": record["latency_ms"], "ttft_model_ms": 2500.0,
        "load_ms": 2000.0, "prompt_eval_ms": 500.0, "eval_ms": 6000.0}
    assert record["repeat_penalty"] == 1.0 and record["num_predict"] == 1024 and record["cjk_chars"] == 0
    assert len(record["prompt_sha256"]) == 64

    manifest = json.loads((tmp_path / "run_a_results_manifest.json").read_text(encoding="utf-8"))
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    runtime = manifest["runtime"]
    assert {k: runtime[k] for k in ("temperature", "repeat_penalty", "num_predict", "num_ctx", "model")} == {
        k: config[k] for k in ("temperature", "repeat_penalty", "num_predict", "num_ctx", "model")}
    assert runtime["prompt_version"] == PROMPT_A_VERSION
    assert manifest["as_of_date_source"] == "benchmark" and manifest["status"] == "SUCCESS"
    assert manifest["total"] == 2 and manifest["failed"] == 0


def test_cjk_answer_is_counted(tmp_path):
    output = tmp_path / "a.json"
    zero_shot.run_benchmark(_questions(tmp_path), output, gateway=QwenGateway(transport=Recorder(answer="hiệu力")))
    assert json.loads(output.read_text(encoding="utf-8"))[0]["cjk_chars"] == 1


def test_error_rows_are_kept_and_manifest_marks_failure(tmp_path):
    output = tmp_path / "a.json"
    transport = Recorder(fail_on="Nữ bao nhiêu")
    gateway = QwenGateway({"max_retries": 0}, transport=transport)
    zero_shot.run_benchmark(_questions(tmp_path), output, gateway=gateway)
    records = json.loads(output.read_text(encoding="utf-8"))
    assert records[1]["answer"] is None and "boom" in records[1]["error"]
    manifest = json.loads((tmp_path / "a_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "FAILED" and manifest["failed"] == 1


def test_existing_output_is_not_overwritten(tmp_path):
    output = tmp_path / "zero_shot_dev30_results.json"
    output.write_text("[]", encoding="utf-8")
    with pytest.raises(FileExistsError):
        zero_shot.run_benchmark(_questions(tmp_path), output, gateway=QwenGateway(transport=Recorder()))
    assert output.read_text(encoding="utf-8") == "[]"


def test_model_flag_must_match_the_shared_config():
    with pytest.raises(ValueError, match="cùng cấu hình"):
        zero_shot.build_gateway("qwen2.5:3b")
