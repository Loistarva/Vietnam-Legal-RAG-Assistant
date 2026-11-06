# -*- coding: utf-8 -*-
"""
model_gateway/llm_gateway.py
Qwen Model Gateway, Structured Output & Runtime Provenance (Tasks D3.3 & D3.4).
Complies with DoD-09 and DoD-10.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Union

import requests
import yaml
from pydantic import BaseModel, Field

from schemas.models import LLMResponse, StructuredRAGOutput, TokenUsage

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "local_qwen.yaml"


class GatewayExecutionError(Exception):
    """Ngoại lệ khi không thể kết nối hoặc thực thi gọi mô hình qua Gateway."""
    pass


class QwenGatewayConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    temperature: float = 0.0
    repeat_penalty: float = 1.15
    num_predict: int = 1024
    num_ctx: int = 8192
    timeout_seconds: float = 120.0
    max_retries: int = 1
    cache_enabled: bool = False
    fallback_locked: bool = True


class QwenGateway:
    """
    Cổng kết nối kiểm soát mô hình Qwen2.5:7b qua Ollama API.
    Đảm bảo tính nhất quán giữa Run A (Zero-Shot) và Run B (Controlled RAG).
    """

    def __init__(
        self,
        config: Optional[Union[QwenGatewayConfig, Dict[str, Any], str, Path]] = None,
        transport: Optional[Callable[[str, Dict[str, Any], float], Dict[str, Any]]] = None,
    ):
        if config is None:
            self.config = self.load_config(DEFAULT_CONFIG_PATH)
        elif isinstance(config, (str, Path)):
            self.config = self.load_config(config)
        elif isinstance(config, dict):
            self.config = QwenGatewayConfig(**config)
        elif isinstance(config, QwenGatewayConfig):
            self.config = config
        else:
            raise ValueError(f"Cấu hình không hợp lệ: {type(config)}")

        # Cho phép inject custom transport phục vụ unit testing
        self._transport = transport
        self._session = requests.Session() if transport is None else None

    @classmethod
    def load_config(cls, config_path: Union[str, Path]) -> QwenGatewayConfig:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file cấu hình gateway: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return QwenGatewayConfig(**data)

    def _execute_http_post(self, url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        """Thực hiện HTTP POST với retry và timeout rõ ràng."""
        attempts = 0
        total_attempts = 1 + max(0, self.config.max_retries)
        last_error: Optional[Exception] = None

        while attempts < total_attempts:
            attempts += 1
            try:
                if self._transport is not None:
                    return self._transport(url, payload, timeout)

                resp = self._session.post(url, json=payload, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_error = e
                if attempts < total_attempts:
                    time.sleep(0.1 * attempts)

        # Fail-fast, tuyệt đối không silently fallback sang model khác
        raise GatewayExecutionError(
            f"Không thể kết nối đến Ollama model gateway ({self.config.base_url}) sau {total_attempts} lần thử: {last_error}"
        ) from last_error

    def generate(
        self,
        prompt: str,
        query_id: str,
        run_mode: Literal["A_zero_shot", "B_controlled_rag", "C_production_rag"],
        prompt_version: str,
        structured_output: bool = False,
        schema: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """
        Gọi mô hình Qwen qua Ollama API (/api/generate).
        Ghi nhận đầy đủ Runtime Provenance vào LLMResponse.
        """
        url = f"{self.config.base_url.rstrip('/')}/api/generate"

        options = {
            "temperature": self.config.temperature,
            "repeat_penalty": self.config.repeat_penalty,
            "num_predict": self.config.num_predict,
            "num_ctx": self.config.num_ctx,
        }

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }

        if structured_output:
            # Dùng schema được truyền vào hoặc schema canonical của StructuredRAGOutput
            payload["format"] = schema if schema is not None else StructuredRAGOutput.model_json_schema()

        t0 = time.perf_counter()
        raw_res = self._execute_http_post(url, payload, self.config.timeout_seconds)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Trích xuất dữ liệu phản hồi
        raw_text = raw_res.get("response", "")
        done_reason = str(raw_res.get("done_reason") or ("stop" if raw_res.get("done") else "unknown"))
        prompt_tokens = int(raw_res.get("prompt_eval_count") or 0)
        output_tokens = int(raw_res.get("eval_count") or 0)
        token_usage = TokenUsage(input=prompt_tokens, output=output_tokens)

        # Xử lý Run A (Zero-Shot) hoặc Non-Structured
        if not structured_output:
            truncated = (done_reason == "length")
            return LLMResponse(
                query_id=query_id,
                run_mode=run_mode,
                answer=raw_text.strip(),
                evidence_indices=[],
                abstained=False,
                needs_clarification=False,
                model=self.config.model,
                prompt_version=prompt_version,
                num_ctx=self.config.num_ctx,
                num_predict=self.config.num_predict,
                temperature=self.config.temperature,
                repeat_penalty=self.config.repeat_penalty,
                done_reason=done_reason,
                truncated=truncated,
                parse_status="raw_text",
                latency_ms=round(latency_ms, 2),
                token_usage=token_usage,
                fallback_status="none",
                raw_response=raw_text,
            )

        # Xử lý Run B (Structured Output)
        parse_status: Literal["ok", "truncated_json", "invalid_json", "raw_text"] = "ok"
        answer = raw_text.strip()
        evidence_indices: List[int] = []
        abstained = False
        needs_clarification = False

        try:
            parsed_json = json.loads(raw_text)
            structured_obj = StructuredRAGOutput(**parsed_json)
            answer = structured_obj.answer
            evidence_indices = structured_obj.evidence_indices
            abstained = structured_obj.abstained
            needs_clarification = structured_obj.needs_clarification
            parse_status = "ok"
        except Exception:
            if done_reason == "length":
                parse_status = "truncated_json"
            else:
                parse_status = "invalid_json"

        truncated = (done_reason == "length") or (parse_status == "truncated_json")

        return LLMResponse(
            query_id=query_id,
            run_mode=run_mode,
            answer=answer,
            evidence_indices=evidence_indices,
            abstained=abstained,
            needs_clarification=needs_clarification,
            model=self.config.model,
            prompt_version=prompt_version,
            num_ctx=self.config.num_ctx,
            num_predict=self.config.num_predict,
            temperature=self.config.temperature,
            repeat_penalty=self.config.repeat_penalty,
            done_reason=done_reason,
            truncated=truncated,
            parse_status=parse_status,
            latency_ms=round(latency_ms, 2),
            token_usage=token_usage,
            fallback_status="none",
            raw_response=raw_text,
        )


def summarize_truncation_and_provenance(responses: List[LLMResponse]) -> Dict[str, Any]:
    """
    Tổng hợp thống kê lô chạy:
    - Truncation rate (done_reason == 'length' hoặc parse_status == 'truncated_json')
    - JSON parse failure rate
    - Latency distribution (p50, p95)
    - Token consumption tổng thể
    """
    total = len(responses)
    if total == 0:
        return {
            "total_queries": 0,
            "truncation_count": 0,
            "truncation_rate": 0.0,
            "json_parse_failure_count": 0,
            "json_parse_failure_rate": 0.0,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }

    truncation_count = sum(1 for r in responses if r.truncated or r.done_reason == "length")
    parse_failures = sum(1 for r in responses if r.parse_status in ("truncated_json", "invalid_json"))

    latencies = sorted(r.latency_ms for r in responses)
    if total == 1:
        p50 = latencies[0]
        p95 = latencies[0]
    else:
        p50 = statistics.median(latencies)
        # 95th percentile
        idx_95 = int(round(0.95 * (total - 1)))
        p95 = latencies[min(idx_95, total - 1)]

    total_in = sum(r.token_usage.input for r in responses)
    total_out = sum(r.token_usage.output for r in responses)

    return {
        "total_queries": total,
        "truncation_count": truncation_count,
        "truncation_rate": round(truncation_count / total, 4),
        "json_parse_failure_count": parse_failures,
        "json_parse_failure_rate": round(parse_failures / total, 4),
        "latency_p50_ms": round(float(p50), 2),
        "latency_p95_ms": round(float(p95), 2),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
    }
