"""
model_gateway/llm_gateway.py
Qwen Model Gateway, Structured Output & Runtime Provenance (Tasks D3.3 & D3.4).
Complies with DoD-09 and DoD-10.
"""
from __future__ import annotations

import json
import statistics
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import requests
import yaml
from pydantic import BaseModel

from schemas.models import LLMResponse, StructuredRAGOutput, TokenUsage

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "local_qwen.yaml"


class GatewayExecutionError(Exception):
    """Ngoại lệ khi không thể kết nối hoặc thực thi gọi mô hình qua Gateway."""


def normalize_model_name(name: str) -> str:
    """Chuẩn hóa tên model Ollama: chữ thường, không ghi tag nghĩa là ``:latest``."""
    clean = str(name).strip().lower()
    return clean if ":" in clean else f"{clean}:latest"


class QwenGatewayConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    temperature: float = 0.0
    repeat_penalty: float = 1.0
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
        config: QwenGatewayConfig | dict[str, Any] | str | Path | None = None,
        transport: Callable[[str, dict[str, Any], float], dict[str, Any]] | None = None,
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

        if self.config.fallback_locked is not True:
            raise GatewayExecutionError("fallback_locked bắt buộc phải là True để ngăn chặn silent fallback")
        if self.config.cache_enabled is not False:
            raise GatewayExecutionError("cache_enabled bắt buộc phải là False trong môi trường chuẩn")

        # Cho phép inject custom transport phục vụ unit testing
        self._transport = transport
        self._session = requests.Session() if transport is None else None
        self.ollama_version: str | None = None
        self.model_digest: str | None = None

        self._probe_ollama_metadata()

    @classmethod
    def load_config(cls, config_path: str | Path) -> QwenGatewayConfig:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file cấu hình gateway: {path}")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return QwenGatewayConfig(**data)

    def _probe_ollama_metadata(self) -> None:
        """Lấy ollama_version (/api/version) và model_digest (/api/tags, models[].digest).

        /api/show không trả digest, nên digest lấy từ danh sách model đã pull.
        Offline thì giữ None; không điền giá trị thay thế.
        """
        if self._session is None:
            return
        base = self.config.base_url.rstrip("/")
        try:
            v_resp = self._session.get(f"{base}/api/version", timeout=2.0)
            if v_resp.status_code == 200:
                self.ollama_version = v_resp.json().get("version")
            t_resp = self._session.get(f"{base}/api/tags", timeout=2.0)
            if t_resp.status_code == 200:
                self.model_digest = find_model_digest(t_resp.json(), self.config.model)
        except Exception:
            # Không làm crash khi offline init
            pass

    def _execute_http_post(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        """Thực hiện HTTP POST với retry và timeout rõ ràng."""
        attempts = 0
        total_attempts = 1 + max(0, self.config.max_retries)
        last_error: Exception | None = None

        while attempts < total_attempts:
            attempts += 1
            try:
                if self._transport is not None:
                    return self._transport(url, payload, timeout)

                assert self._session is not None
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
        schema: dict[str, Any] | None = None,
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

        payload: dict[str, Any] = {
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

        # Kiểm tra model thực tế từ response: so đủ tên và tag (qwen2.5:3b khác qwen2.5:7b)
        resp_model = raw_res.get("model")
        if resp_model and normalize_model_name(resp_model) != normalize_model_name(self.config.model):
            raise GatewayExecutionError(
                f"Model phản hồi ({resp_model}) không khớp với model cấu hình ({self.config.model})"
            )

        # Trích xuất dữ liệu phản hồi
        raw_text = raw_res.get("response", "")
        done_reason = str(raw_res.get("done_reason") or ("stop" if raw_res.get("done") else "unknown"))
        prompt_tokens = int(raw_res.get("prompt_eval_count") or 0)
        output_tokens = int(raw_res.get("eval_count") or 0)
        token_usage = TokenUsage(input=prompt_tokens, output=output_tokens)
        context_truncated = prompt_tokens >= self.config.num_ctx
        durations = ollama_durations_ms(raw_res)

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
                context_truncated=context_truncated,
                parse_status="raw_text",
                latency_ms=round(latency_ms, 2),
                **durations,
                token_usage=token_usage,
                fallback_status="none",
                raw_response=raw_text,
                ollama_version=self.ollama_version,
                model_digest=self.model_digest,
            )

        # Xử lý Run B (Structured Output)
        parse_status: Literal["ok", "truncated_json", "invalid_json", "raw_text"] = "ok"
        answer = ""
        evidence_indices: list[int] = []
        rejected_evidence_values: list[str] = []
        abstained = False
        abstention_reason: str | None = None
        needs_clarification = False

        try:
            parsed_json = json.loads(raw_text)
            if not isinstance(parsed_json, dict):
                raise ValueError("JSON phản hồi không phải là dictionary")

            # Nếu JSON hợp lệ nhưng evidence_indices chứa số ngoài [1, 5] (ví dụ [1, 6]),
            # VẪN parse thành công, gán parse_status = 'ok' và giữ nguyên để map_evidence_indices_to_citations xử lý.
            # Giá trị không phải số nguyên ("1", 2.0, true, chuỗi chunk_id) được giữ lại trong
            # rejected_evidence_values để Gate đánh FAIL, không bị bỏ đi trong im lặng.
            raw_indices = parsed_json.get("evidence_indices", [])
            if isinstance(raw_indices, list):
                for idx in raw_indices:
                    if isinstance(idx, int) and not isinstance(idx, bool):
                        evidence_indices.append(idx)
                    else:
                        rejected_evidence_values.append(json.dumps(idx, ensure_ascii=False))
            elif raw_indices is not None:
                rejected_evidence_values.append(json.dumps(raw_indices, ensure_ascii=False))

            answer = str(parsed_json.get("answer") or "").strip()
            abstained = bool(parsed_json.get("abstained", False))
            reason = parsed_json.get("abstention_reason")
            abstention_reason = str(reason).strip() if reason else None
            needs_clarification = bool(parsed_json.get("needs_clarification", False))
            parse_status = "ok"
        except Exception:
            if done_reason == "length":
                parse_status = "truncated_json"
            else:
                parse_status = "invalid_json"
            answer = ""  # Không để lọt JSON thô vào câu trả lời khi parse lỗi

        truncated = (done_reason == "length") or (parse_status == "truncated_json")

        return LLMResponse(
            query_id=query_id,
            run_mode=run_mode,
            answer=answer,
            evidence_indices=evidence_indices,
            rejected_evidence_values=rejected_evidence_values,
            abstained=abstained,
            abstention_reason=abstention_reason,
            needs_clarification=needs_clarification,
            model=self.config.model,
            prompt_version=prompt_version,
            num_ctx=self.config.num_ctx,
            num_predict=self.config.num_predict,
            temperature=self.config.temperature,
            repeat_penalty=self.config.repeat_penalty,
            done_reason=done_reason,
            truncated=truncated,
            context_truncated=context_truncated,
            parse_status=parse_status,
            latency_ms=round(latency_ms, 2),
            **durations,
            token_usage=token_usage,
            fallback_status="none",
            raw_response=raw_text,
            ollama_version=self.ollama_version,
            model_digest=self.model_digest,
        )


OLLAMA_DURATION_FIELDS = {
    "load_duration": "load_duration_ms",
    "prompt_eval_duration": "prompt_eval_duration_ms",
    "eval_duration": "eval_duration_ms",
    "total_duration": "total_duration_ms",
}


def ollama_durations_ms(raw_res: dict[str, Any]) -> dict[str, float | None]:
    """Đọc các trường thời gian (nano giây) Ollama trả cả khi stream=false, đổi sang ms.

    Thiếu trường hoặc giá trị không phải số không âm thì để None, không đặt 0.
    ``ttft_model_ms`` = load + prompt_eval, chỉ tính khi có đủ cả hai.
    """
    out: dict[str, float | None] = {}
    for source, target in OLLAMA_DURATION_FIELDS.items():
        value = raw_res.get(source)
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
        out[target] = round(value / 1_000_000, 2) if valid else None
    load, prompt_eval = out["load_duration_ms"], out["prompt_eval_duration_ms"]
    out["ttft_model_ms"] = round(load + prompt_eval, 2) if load is not None and prompt_eval is not None else None
    return out


def find_model_digest(tags_payload: dict[str, Any], model_name: str) -> str | None:
    """Tìm digest của model trong response /api/tags (``models[].name`` / ``models[].model``)."""
    target = normalize_model_name(model_name)
    for entry in tags_payload.get("models") or []:
        names = {normalize_model_name(entry[key]) for key in ("name", "model") if entry.get(key)}
        if target in names:
            return entry.get("digest")
    return None


def summarize_truncation_and_provenance(responses: list[LLMResponse]) -> dict[str, Any]:
    """
    Tổng hợp thống kê lô chạy:
    - Truncation rate (done_reason == 'length' hoặc parse_status == 'truncated_json')
    - Context truncation rate (prompt_eval_count >= num_ctx)
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
            "context_truncated_count": 0,
            "context_truncated_rate": 0.0,
            "json_parse_failure_count": 0,
            "json_parse_failure_rate": 0.0,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }

    truncation_count = sum(1 for r in responses if r.truncated or r.done_reason == "length")
    context_trunc_count = sum(1 for r in responses if r.context_truncated)
    parse_failures = sum(1 for r in responses if r.parse_status in ("truncated_json", "invalid_json"))

    latencies = sorted(r.latency_ms for r in responses)
    if total == 1:
        p50 = latencies[0]
        p95 = latencies[0]
    else:
        p50 = statistics.median(latencies)
        idx_95 = int(round(0.95 * (total - 1)))
        p95 = latencies[min(idx_95, total - 1)]

    total_in = sum(r.token_usage.input for r in responses)
    total_out = sum(r.token_usage.output for r in responses)

    return {
        "total_queries": total,
        "truncation_count": truncation_count,
        "truncation_rate": round(truncation_count / total, 4),
        "context_truncated_count": context_trunc_count,
        "context_truncated_rate": round(context_trunc_count / total, 4),
        "json_parse_failure_count": parse_failures,
        "json_parse_failure_rate": round(parse_failures / total, 4),
        "latency_p50_ms": round(float(p50), 2),
        "latency_p95_ms": round(float(p95), 2),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
    }
