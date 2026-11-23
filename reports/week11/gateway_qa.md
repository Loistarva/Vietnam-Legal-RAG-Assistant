# Báo cáo QA Hardening `QwenGateway` (D3.2)

**Ngày thực hiện:** 23/11/2026  
**Nhánh:** `feature/week11-dev3-contracts-gateway`  
**Tệp liên quan:** `model_gateway/llm_gateway.py`, `model_gateway/config/local_qwen.yaml`, `test/model_gateway/test_structured_output.py`

---

## 1. Phân tách lỗi vận chuyển vs lỗi đầu ra mô hình (`FR6.4`, `FR5.2-AC3`, SRS 5.3.4–5.3.5)

| Tình huống | Cơ chế xử lý trong `QwenGateway` | `error_code` | `retryable` | HTTP tương ứng (API) |
| --- | --- | --- | --- | --- |
| Quá `timeout_seconds` hoặc HTTP 504 | Ném `GatewayExecutionError` sau số lần retry | `LLM_TIMEOUT` | `True` | 504 |
| Không kết nối được Ollama (`ConnectionError`, `OSError`, HTTP 502/503) | Ném `GatewayExecutionError` sau số lần retry | `LLM_UNAVAILABLE` | `True` | 503 |
| Model phản hồi khác cấu hình (`qwen2.5:3b` ≠ `qwen2.5:7b`) | Ném `GatewayExecutionError` (cấm silent fallback) | `INTERNAL_ERROR` | `False` | 500 |
| JSON hỏng / thiếu `answer` / thừa trường / không phải dict | Trả `LLMResponse` hợp lệ (`parse_status="invalid_json"`, `answer=""`) | `JSON_INVALID` | — | 200 (Gate `FAIL` → `ABSTAIN`) |
| Output bị cắt (`done_reason="length"`) khi parse lỗi | Trả `LLMResponse` hợp lệ (`parse_status="truncated_json"`, `truncated=True`, `answer=""`) | `JSON_INVALID` | — | 200 (Gate `FAIL` → `ABSTAIN`) |
| Chỉ số trong `evidence_indices` ngoài `[1, max_evidence_index]` hoặc sai kiểu | Giữ nguyên chỉ số hợp lệ, đẩy phần sai vào `rejected_evidence_values` | `CITATION_INVALID` | — | 200 (Gate `FAIL` → `ABSTAIN`) |

- Lỗi nội dung/cấu trúc phản hồi của LLM **không ném Gateway exception**, không tự sửa JSON hay tự điền `answer`/citation metadata để Grounding Gate kết luận theo đúng contract.

---

## 2. Khóa cấu hình & Provenance (`FR6.2-AC1`, `FR6.6-AC2`, `FR6.7`)

- `model_gateway/config/local_qwen.yaml` bổ sung `config_version: "local_qwen_v1.1"`.
- `QwenGatewayConfig` dùng `ConfigDict(extra="forbid")`, kiểm tra chặt kiểu (`bool` không lọt vào trường `int`/`float`, `provider == "ollama"`, `base_url` có tiền tố `http://` hoặc `https://`, các ngưỡng dương).
- `QwenGateway.load_config(...)` kiểm tra đầy đủ 12 khóa bắt buộc (`REQUIRED_CONFIG_KEYS`) ngay lúc đọc YAML; thiếu bất kỳ khóa nào đều ném `GatewayExecutionError` chỉ rõ tên khóa thiếu.
- Giá trị token (`prompt_eval_count`, `eval_count`) và các mốc thời gian (`load_duration_ms`, `prompt_eval_duration_ms`, `eval_duration_ms`, `total_duration_ms`, `ttft_model_ms`) giữ nguyên `None` (`null`) khi runtime không trả về; `ollama_version` và `model_digest` giữ `None` khi offline.

---

## 3. Rà soát điểm gọi HTTP ngoài `model_gateway/` (`FR6.1-AC1`)

- Đã quét toàn bộ mã nguồn bằng `git grep` và test tĩnh trong `test/model_gateway/test_structured_output.py`: các phân hệ runtime (`orchestration/`, `evaluation/`, `agent/`, `retrieval/`, `reranking/`, `grounding/`, `generation/`) đều không gọi HTTP trực tiếp tới Ollama/LLM provider mà đi qua `QwenGateway`.
- **Ghi chú ngoài phạm vi sở hữu Dev 3:** `scripts/run_rag_batch.py` (`preflight_ollama`, dòng 415–450) hiện vẫn gọi trực tiếp `urllib.request` tới `/api/version`, `/api/tags`, `/api/generate` để warmup trước batch. Dev 3 giữ nguyên không sửa file ngoài phạm vi và ghi nhận để owner `scripts/` có thể chuyển sang dùng `QwenGateway` / `model_gateway/run_metadata.py` ở bước dọn kỹ thuật tiếp theo.
