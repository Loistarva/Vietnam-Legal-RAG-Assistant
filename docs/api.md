# HTTP API – Vietnam Legal RAG Assistant (Sprint 10, Dev 5)

API đưa pipeline RAG dùng chung (`orchestration/rag_pipeline.py`) ra HTTP. UI và client khác chỉ gọi API này, không import module Python của backend.

| Mục | Giá trị |
| --- | --- |
| Base URL (local) | `http://127.0.0.1:8000` |
| Contract | `schemas/models.py`, `schema_version = week10_v1.0` (Dev 3) |
| OpenAPI snapshot | [api/openapi.json](../api/openapi.json); Swagger UI ở `/docs`, schema sống ở `/openapi.json` |
| Xác thực | Header `X-API-Key` |
| Code | [api/](../api/), [orchestration/ask_service.py](../orchestration/ask_service.py) |

## 1. Chạy server

```powershell
python -m pip install -r requirements.txt
$env:LEGAL_RAG_API_KEYS = "<key dài ít nhất 16 ký tự>"   # nhiều key: phân tách bằng dấu phẩy

# a) Mock pipeline: không cần Elasticsearch, Qdrant hay Ollama (dùng để làm UI)
$env:LEGAL_RAG_PIPELINE_MODE = "mock"
uvicorn api.main:app --host 127.0.0.1 --port 8000

# b) Pipeline thật
$env:LEGAL_RAG_PIPELINE_MODE = "live"
$env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:QDRANT_URL = "http://localhost:6333"   # hoặc $env:QDRANT_PATH = "<thư mục qdrant_storage>" (chỉ một tiến trình)
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Server không khởi động nếu thiếu `LEGAL_RAG_API_KEYS` hoặc có key ngắn hơn 16 ký tự. Toàn bộ biến môi trường có trong [.env.example](../.env.example). `.env` đã được gitignore; không commit key thật.

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `LEGAL_RAG_API_KEYS` | bắt buộc | Các key hợp lệ |
| `LEGAL_RAG_ENV` | `development` | Ở `production`, không cho phép CORS `*` |
| `LEGAL_RAG_CORS_ORIGINS` | rỗng (tắt CORS) | Origin được gọi từ trình duyệt. Streamlit gọi từ server nên không cần |
| `LEGAL_RAG_MAX_QUERY_CHARS` | `2000` | Câu hỏi dài hơn trả về 422 |
| `LEGAL_RAG_MAX_CONCURRENCY` | `1` | Số câu xử lý đồng thời (một Qwen local, Qdrant embedded) |
| `LEGAL_RAG_PIPELINE_MODE` | `live` | `live` hoặc `mock` |
| `RAG_PRECOMPUTED` | rỗng | Artifact reranked thay cho retrieval live (chỉ dùng cho câu benchmark) |
| `LEGAL_RAG_EVENT_LOG` | rỗng | Đường dẫn tệp JSONL. `monitoring.StructuredLogger` che thông tin định danh cá nhân và các API key đã cấu hình trước khi ghi sự kiện của từng giai đoạn. |

## 2. Endpoint

| Method | Path | Key | Mô tả |
| --- | --- | --- | --- |
| GET | `/api/v1/health` | không | Báo API còn sống, không gọi Retrieval/LLM |
| POST | `/api/v1/ask` | có | Hỏi đáp, trả `AskResponse` |
| POST | `/api/v1/ask/stream` | có | Như `/ask` nhưng trả SSE: các trạng thái trước, câu trả lời sau Gate ([docs/api/sse_events.md](api/sse_events.md)) |

### Request: `AskRequest`

```json
{"query": "Nam phải đủ bao nhiêu tuổi thì được kết hôn?", "as_of_date": "2026-11-16", "session_id": "s-1", "request_id": "ui-42"}
```

- Chỉ `query` là bắt buộc. Gửi field lạ (ví dụ `run_mode`, `top_k`) sẽ bị trả 422: cấu hình retrieval và model do server khóa.
- **Ngày tra cứu** được chọn theo thứ tự: ngày nêu trong câu hỏi ("tại ngày 01/01/2015…") → `as_of_date` → ngày hiện tại.
- `query_id` không bắt buộc. Nếu không gửi, server tự sinh (`q_<UTC>_<hex>`). Giá trị này được trả lại trong body và header `X-Query-ID`, và là khóa để tra log. Header dùng percent-encoding UTF-8 cho các ký tự ngoài nhóm unreserved. Client dùng ID gốc trong JSON để tra log.

Với lỗi 401/422, server cũng trả mã truy vết trong body và header. Event `request_rejected` ghi mã lỗi và HTTP status để đếm các request bị chặn trước pipeline.

### Response: `AskResponse`

| Field | Ghi chú |
| --- | --- |
| `status` | `SUCCESS`, `NEEDS_CLARIFICATION`, `ABSTAIN`, `ERROR`. UI dựa vào field này, không suy ra từ `answer` |
| `as_of_date`, `as_of_date_source` | Ngày hiệu lực server đã áp dụng và nguồn của nó: `query_text` (ngày trong câu hỏi), `user_input` (`as_of_date` của request), `system_today` |
| `route` | `LEGAL_IN_SCOPE`, `NON_LEGAL`, `LEGAL_OUT_OF_SCOPE`, `MIXED_REVIEW` |
| `answer` | Chỉ có khi `status=SUCCESS` (sau Gate PASS, hoặc câu trả lời tĩnh cho non-legal). Không chứa disclaimer |
| `clarification` / `abstention_message` | Lời nhắn cho `NEEDS_CLARIFICATION` / `ABSTAIN` |
| `abstention_reason` | Mã cố định: `LOW_CONFIDENCE`, `EMPTY_RETRIEVAL`, `MODEL_ABSTAINED`, `LEGAL_OUT_OF_SCOPE_MATCH`, mã Gate FAIL… |
| `citations[]` | `evidence_index` → `chunk_id/document_id/article_id/clause_id` |
| `evidence[]` | Nội dung căn cứ cho Evidence Panel: `content`, `document_title`, `breadcrumb`, `validity_status`, `effective_from/to`, `source_url` |
| `grounding_status` | `PASS`, `FAIL`, `ABSTAIN`, `NEEDS_CLARIFICATION`, `NOT_RUN` (không có bước sinh câu trả lời) |
| `disclaimer` | Luôn có; UI hiển thị ở mọi trạng thái |
| `timings` | `total_ms` (thời gian xử lý ở server), `retrieval_ms`, `llm_total_ms`, `ttft_model_ms`, … (ms; `null` = không đo được) |
| `error_code`, `error` | Khi `status=ERROR`: `error_code` bắt buộc, `error` là `ErrorDetail` = `{"message", "retryable"}`; không chứa traceback |

### Trạng thái theo nhánh

| Tình huống | HTTP | `status` | `grounding_status` | `error_code` |
| --- | --- | --- | --- | --- |
| Legal HNGĐ, Gate PASS | 200 | `SUCCESS` | `PASS` | – |
| Non-legal (fast-path, không gọi Retrieval/LLM) | 200 | `SUCCESS` | `NOT_RUN` | – |
| Legal ngoài phạm vi / mixed (Policy Abstention) | 200 | `ABSTAIN` | `NOT_RUN` | `ROUTE_POLICY` |
| Không có evidence | 200 | `ABSTAIN` | `NOT_RUN` | `RETRIEVAL_EMPTY` |
| Top-1 dưới ngưỡng confidence (không gọi LLM) | 200 | `ABSTAIN` | `NOT_RUN` | `LOW_CONFIDENCE` |
| Model hỏi lại | 200 | `NEEDS_CLARIFICATION` | `NEEDS_CLARIFICATION` | – |
| Model từ chối | 200 | `ABSTAIN` | `ABSTAIN` | – |
| Gate FAIL: citation ngoài context | 200 | `ABSTAIN` | `FAIL` | `CITATION_INVALID` |
| Gate FAIL: JSON model hỏng, đầu ra không phải JSON (`LLM_OUTPUT_RAW_TEXT`) hoặc bị cắt | 200 | `ABSTAIN` | `FAIL` | `JSON_INVALID` |
| Gate FAIL khác (ví dụ câu trả lời chứa ký tự CJK) | 200 | `ABSTAIN` | `FAIL` | `GROUNDING_FAIL` |
| Qwen timeout | 504 | `ERROR` | `NOT_RUN` | `LLM_TIMEOUT` |
| Lỗi nội bộ sau định tuyến | 500 | `ERROR` | `NOT_RUN` | `INTERNAL_ERROR` |
| Router lỗi hoặc trả `action` rỗng/không hỗ trợ | 500 | – (`ApiError`) | – | `INTERNAL_ERROR` |
| Thiếu `X-API-Key` | 401 | – (`ApiError`) | – | `AUTH_REQUIRED` |
| Key sai | 401 | – (`ApiError`) | – | `AUTH_REQUIRED` |
| Body sai schema, câu hỏi quá dài | 422 | – (`ApiError`) | – | `INVALID_REQUEST` |
| Router từ chối đầu vào (`INVALID_EMPTY_QUERY`, `INVALID_QUERY_TYPE`, `INVALID_AS_OF_DATE`) | 422 | – (`ApiError`, mã ở `details[].type`) | – | `INVALID_REQUEST` |

Ánh xạ mã chi tiết → `error_code` theo bảng SRS 5.3.5 (`orchestration/ask_service.py`, `gate_fail_error_code`). Mã FAIL chưa có trong bảng thuộc `GROUNDING_FAIL`.

Khi Gate FAIL, bản nháp của model không bao giờ được trả về: response chỉ có `abstention_message`, còn bản nháp chỉ nằm trong record nội bộ để phục vụ đánh giá.

`ApiError` (401/422/500 trước pipeline):

```json
{"schema_version": "week10_v1.0", "error_code": "INVALID_REQUEST", "message": "Request không hợp lệ", "query_id": null,
 "details": [{"loc": ["body", "query"], "msg": "String should have at least 1 character", "type": "string_too_short"}]}
```

## 3. Ví dụ curl (ba nhánh nghiệp vụ)

PowerShell: dùng `curl.exe` (không dùng alias `curl`), hoặc `Invoke-RestMethod`.

```bash
KEY="<key>"
# Legal trong phạm vi -> SUCCESS + citations + evidence
curl -s -X POST http://127.0.0.1:8000/api/v1/ask -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"query": "Nam phải đủ bao nhiêu tuổi thì được kết hôn?", "as_of_date": "2026-11-16"}'
# Non-legal -> SUCCESS, grounding NOT_RUN
curl -s -X POST http://127.0.0.1:8000/api/v1/ask -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"query": "Hôm nay thời tiết Hà Nội thế nào?"}'
# Legal ngoài phạm vi -> ABSTAIN, ROUTE_POLICY
curl -s -X POST http://127.0.0.1:8000/api/v1/ask -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"query": "Thủ tục thành lập doanh nghiệp tư nhân thế nào?"}'
# Thiếu key -> 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/api/v1/ask -d '{"query": "x"}' -H "Content-Type: application/json"
```

```powershell
$h = @{ "X-API-Key" = $env:LEGAL_RAG_API_KEYS.Split(",")[0] }
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/ask -Headers $h -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes('{"query": "Nam phải đủ bao nhiêu tuổi thì được kết hôn?"}'))
```

Response mẫu (live, rút gọn; xem [reports/week10/e2e_report.md](../reports/week10/e2e_report.md)):

```json
{"schema_version": "week10_v1.0", "query_id": "q_20261116T145131_b2272742", "as_of_date": "2026-11-16",
 "as_of_date_source": "user_input", "status": "SUCCESS", "route": "LEGAL_IN_SCOPE",
 "answer": "Theo quy định có hiệu lực tại ngày 2026-11-16, nam phải đủ 20 tuổi trở lên để kết hôn theo điểm a khoản 1 Điều 8 của Luật Hôn nhân và gia đình 2014.",
 "citations": [{"evidence_index": 1, "chunk_id": "l_52_2014_qh13_art_8_clause_1_chunk_1", "document_id": "l_52_2014_qh13", "...": "..."}],
 "evidence": [{"evidence_index": 1, "document_title": "Luật Hôn nhân và gia đình 2014", "breadcrumb": "Chương II KẾT HÔN > Điều 8. Điều kiện kết hôn > Khoản 1", "...": "..."}],
 "grounding_status": "PASS", "disclaimer": "Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.",
 "timings": {"total_ms": 44040.1, "retrieval_ms": 11975.8, "llm_total_ms": 31942.4, "ttft_model_ms": 2822.8, "...": "..."}, "error_code": null, "error": null}
```

## 4. Mock server cho UI (Dev 2)

`LEGAL_RAG_PIPELINE_MODE=mock` chạy router thật cùng pipeline thật (confidence filter, context, Gate). Chỉ retrieval và model là giả lập: evidence có nhãn `[MOCK]`/`[Dữ liệu giả lập]`. Thêm marker vào câu hỏi để thử từng trạng thái của UI:

| Marker trong `query` | Kết quả |
| --- | --- |
| (không có) | `SUCCESS` với 2 citation, 2 evidence |
| `[mock:empty]` | `ABSTAIN`, `RETRIEVAL_EMPTY` |
| `[mock:low]` | `ABSTAIN`, `LOW_CONFIDENCE` |
| `[mock:clarify]` | `NEEDS_CLARIFICATION` |
| `[mock:abstain]` | `ABSTAIN` (model từ chối) |
| `[mock:gate_fail]` | `ABSTAIN`, `grounding_status=FAIL`, `CITATION_INVALID` |
| `[mock:bad_json]` | `ABSTAIN`, `FAIL`, `JSON_INVALID` |
| `[mock:timeout]` | HTTP 504, `ERROR`, `LLM_TIMEOUT` |

Câu non-legal và câu ngoài phạm vi đi qua router thật, nên vẫn cho ra `NON_LEGAL` / `LEGAL_OUT_OF_SCOPE`.

Client Streamlit trên nhánh `testing` dùng timeout mặc định 180 giây. Khi nhận HTTP 500 hoặc 504 từ pipeline, client đọc `error.message` trong `AskResponse`. Khi dùng endpoint SSE, client đọc `AskResponse` ngay trong event `final` và hiển thị `message` của event `error`.

## 5. Thay đổi contract

- `api/openapi.json` là snapshot; [test/api/test_openapi_contract.py](../test/api/test_openapi_contract.py) fail khi app khác snapshot. Khi đổi route hoặc schema: chạy `python -m api.export_openapi`, review diff trong PR và báo Dev 2.
- Model request/response nằm ở `schemas/models.py` (Dev 3). API không định nghĩa schema thứ hai; `ApiError` chỉ dùng cho lỗi xảy ra trước pipeline.
