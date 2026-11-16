# Ollama & Qwen Gateway – Hướng dẫn vận hành

**Phạm vi:** Task `D3.2` / `D3.3` (Kế hoạch Tuần 10)  
**Cấu hình chuẩn:** `model_gateway/config/local_qwen.yaml`  
**Mã nguồn Gateway:** `model_gateway/llm_gateway.py`

---

## 1. Cấu hình baseline (`model_gateway/config/local_qwen.yaml`)

| Tham số | Giá trị chuẩn | Ý nghĩa vận hành |
| :--- | :--- | :--- |
| `provider` | `ollama` | Backend suy luận cục bộ |
| `base_url` | `http://localhost:11434` | Endpoint mặc định của Ollama daemon |
| `model` | `qwen2.5:7b` | Tên + tag chính xác; Gateway so sánh đầy đủ tag qua `normalize_model_name` |
| `temperature` | `0.0` | Greedy decoding, bảo đảm tính tái lập giữa các lần chạy |
| `repeat_penalty` | `1.0` | Khóa tại `1.0` (PR #45 / P45-2) để tránh ép model chuyển sang ký tự CJK |
| `num_predict` | `1024` | Giới hạn token sinh ra tối đa mỗi lượt gọi |
| `num_ctx` | `8192` | Cửa sổ ngữ cảnh (8K tokens) |
| `timeout_seconds` | `120` | Thời gian chờ tối đa mỗi HTTP POST sang `/api/generate` |
| `max_retries` | `1` | Tổng số lần thử tối đa = `1 + max_retries = 2` |
| `cache_enabled` | `false` | Bắt buộc `false` ở môi trường chuẩn (`QwenGateway.__init__` kiểm tra cứng) |
| `fallback_locked` | `true` | Bắt buộc `true`; cấm tự động fallback im lặng sang model khác |

> [!IMPORTANT]
> Khi bật ứng dụng thực tế hoặc benchmark, giữ nguyên `fallback_locked: true` và `cache_enabled: false`. Nếu sửa sai hai tham số này, `QwenGateway` sẽ báo lỗi `GatewayExecutionError` ngay khi khởi tạo.

---

## 2. Cài đặt & kiểm tra sức khỏe Ollama trên Windows (PowerShell)

### 2.1. Kiểm tra cài đặt và tải đúng model `qwen2.5:7b`

```powershell
ollama --version
ollama list
ollama pull qwen2.5:7b
```

Kiểm tra dịch vụ HTTP cục bộ (`/api/version` và `/api/tags`):

```powershell
Invoke-RestMethod http://localhost:11434/api/version
(Invoke-RestMethod http://localhost:11434/api/tags).models | Select-Object name, digest, size
```

Kỳ vọng:
- `version` phản hồi phiên bản Ollama hợp lệ (baseline đã xác minh trên `0.40.16`).
- Danh sách `models` có mục `qwen2.5:7b` với `digest` SHA-256 nhất quán (`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` ở lần xác minh chuẩn).

### 2.2. Smoke test qua Gateway

Kiểm tra kết nối đầu-cuối (Run A + Run B trên câu hỏi chuẩn `HN_003`):

```powershell
python scripts/verify_qwen_live.py
```

Hoặc kiểm tra nhanh `QwenGateway` trong Python:

```powershell
python -c "from model_gateway.llm_gateway import QwenGateway; g = QwenGateway(); print('Ollama:', g.ollama_version, 'Digest:', g.model_digest)"
```

Nếu Ollama chưa chạy hoặc offline khi khởi tạo, `g.ollama_version` và `g.model_digest` giữ `None` (không tự điền giá trị giả), và lời gọi `g.generate(...)` sẽ thất bại nhanh với `GatewayExecutionError`.

---

## 3. Giám sát thời gian & chất lượng phản hồi

`LLMResponse` ghi lại trực tiếp từ Ollama `/api/generate` (quy đổi từ nanosecond sang ms):

- `load_duration_ms`: thời gian nạp model lên VRAM/RAM. Nếu giá trị lớn bất thường ở query đầu tiên sau khi khởi động, đó là **cold start**.
- `prompt_eval_duration_ms`: thời gian xử lý prompt đầu vào.
- `ttft_model_ms`: tổng `load_duration_ms + prompt_eval_duration_ms` (xấp xỉ Time To First Token phía model khi chạy `stream=false`).
- `eval_duration_ms`: thời gian sinh token đầu ra.
- `total_duration_ms`: tổng thời gian xử lý phía Ollama server.
- `token_usage.input` / `token_usage.output`: giữ `null` nếu response không trả `prompt_eval_count` / `eval_count` (không đặt mặc định `0`).

---

## 4. Xử lý sự cố thường gặp (Troubleshooting)

| Triệu chứng / Lỗi | Nguyên nhân gốc | `error_code` / Trạng thái | Cách khắc phục |
| :--- | :--- | :--- | :--- |
| `GatewayExecutionError: Không thể kết nối...` | Ollama service chưa chạy hoặc sai port `11434` | `INTERNAL_ERROR` | Chạy `ollama serve` (hoặc mở Ollama Desktop) rồi kiểm tra lại `http://localhost:11434/api/version`. |
| `GatewayExecutionError` chứa `ReadTimeout` / `timed out` | Prompt quá dài hoặc máy đang thiếu VRAM gây chậm vượt `120s` | `LLM_TIMEOUT` | Kiểm tra tải GPU/RAM (`ollama ps`), warmup model trước bằng một prompt ngắn, kiểm tra `max_context_chars` không vượt ngưỡng. |
| `GatewayExecutionError: Model phản hồi (...) không khớp` | Server đang trả sai model hoặc sai tag (ví dụ `qwen2.5:3b` thay vì `qwen2.5:7b`) | `INTERNAL_ERROR` | Chạy `ollama pull qwen2.5:7b`, đối chiếu `local_qwen.yaml` và xóa cấu hình override sai tag. |
| `parse_status == "truncated_json"`, `truncated == true` | Câu trả lời chạm trần `num_predict=1024` trước khi đóng JSON | `JSON_INVALID` | Rà soát prompt hoặc độ dài evidence; không sửa tay JSON đầu ra. |
| `parse_status == "invalid_json"` | Model trả text ngoài JSON, thiếu khóa `"answer"`, hoặc sinh khóa thừa | `JSON_INVALID` | Bật `structured_output=True` kèm `format` schema; kiểm tra `raw_response_reference` để truy vết phản hồi gốc. |
| `rejected_evidence_values` khác rỗng | Model trả chuỗi/float/bool hoặc chỉ số ngoài `[1, max_evidence_index]` | `CITATION_INVALID` | Grounding Gate tự động chặn phát hành; kiểm tra lại evidence numbering `[1]..[k]` trong `ContextPayload`. |
| `context_truncated == true` | `prompt_eval_count >= 8192` (`num_ctx`) | Cảnh báo cắt ngữ cảnh | Giảm số lượng/độ dài chunk đầu vào (`max_context_chars=6000` ở `ContextPayload`). |
