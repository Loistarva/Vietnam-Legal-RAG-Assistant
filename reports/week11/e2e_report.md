# Báo cáo D5.4 – Live E2E Web UI → API → RAG → Gate → Log (Sprint 11, Dev 5)

Ngày chạy: 23/11/2026. Code: nhánh `feature/sprint11-dev5`; code chạy live tương ứng commit `b3b2001` (sau đó chỉ đổi tên tham số trong Protocol `PromptBuilder`, không đổi hành vi). Lệnh: `python scripts/run_live_e2e.py` (mục 5). Kết quả thô: [live/live_e2e_results.json](live/live_e2e_results.json), log: [live/live_events.jsonl](live/live_events.jsonl).

## 1. Kết luận

13/13 ca live đạt, gồm 3 ca đi qua chính Streamlit UI của Dev 2. Mọi ca có cùng `query_id` ở body, header `X-Query-ID` và log; thứ tự stage đúng FR9.9-AC1/AC2; log 75 dòng JSON, không chứa API key đúng hay key sai, không chứa câu hỏi.

Chưa có bằng chứng live cho bốn nhánh: Gate FAIL, JSON lỗi / bị cắt, LLM timeout, model không kết nối. Bốn nhánh này có test tự động với Gateway giả (mục 3). Lý do ở mục 4.

## 2. Ca live

| Ca | Đường đi | HTTP | `status` / `grounding_status` / `error_code` | Thời gian | Stage trong log (theo thứ tự) |
| --- | --- | --- | --- | --- | --- |
| Thiếu `X-API-Key` | API | 401 | `AUTH_REQUIRED` (`ApiError`) | 5 ms | `api` |
| Key sai | API | 401 | `AUTH_REQUIRED` | 2 ms | `api` |
| Query rỗng | API | 422 | `INVALID_REQUEST` | 25 ms | `api` |
| Query 2.001 ký tự | API | 422 | `INVALID_REQUEST` | 3 ms | `api` |
| "Nam phải đủ bao nhiêu tuổi thì được kết hôn?" (ngày chọn 23/11/2026) | API | 200 | SUCCESS / PASS / – | 17,0 s | api router retrieval rerank context llm citation gate response |
| "Vợ chồng có quyền và nghĩa vụ gì đối với tài sản chung?" | API | 200 | SUCCESS / PASS / – | 33,9 s | như trên |
| "Tại ngày 01/01/2015, điều kiện kết hôn về độ tuổi là gì?" | API | 200 | SUCCESS / PASS / – | 18,1 s | như trên |
| "Hôm nay thời tiết Hà Nội thế nào?" | API | 200 | SUCCESS / NOT_RUN / – | 7 ms | api router response |
| "Thủ tục thành lập doanh nghiệp tư nhân thế nào?" | API | 200 | ABSTAIN / NOT_RUN / `ROUTE_POLICY` | 23 ms | api router response |
| HN_035 (as_of 15/10/2026) | API | 200 | ABSTAIN / NOT_RUN / `LOW_CONFIDENCE` | 2,6 s | api router retrieval rerank response |
| UI: "Nữ phải đủ bao nhiêu tuổi thì được kết hôn?" | Streamlit → API | 200 | SUCCESS / PASS / – | 17,5 s | api router retrieval rerank context llm citation gate response |
| UI: "Xin chào, bạn là ai?" | Streamlit → API | 200 | SUCCESS / NOT_RUN / – | 86 ms | api router response |
| UI: "Thủ tục thành lập doanh nghiệp tư nhân thế nào?" | Streamlit → API | 200 | ABSTAIN / NOT_RUN / `ROUTE_POLICY` | 78 ms | api router response |

Mỗi request còn một sự kiện `api` `request_completed` sau `response`. Stage `retrieval` có hai sự kiện (`retrieval_started`, `retrieval_finished`), `llm` có hai (`generation_started`, `generation_finished`).

Kiểm thêm:

- **Gate PASS → citation đúng điều luật.** Câu tuổi kết hôn trích `l_52_2014_qh13_art_8_clause_1_chunk_1` (Luật HNGĐ 2014, Điều 8 khoản 1). Câu tài sản chung trích Điều 29 khoản 1 và Điều 30 khoản 2.
- **Ngày tra cứu (FR2.1).** Ngày chọn → `as_of_date_source = user_input`. Ngày trong câu hỏi → `2015-01-01`, `query_text`; câu trả lời ghi "có hiệu lực tại ngày 2015-01-01" và dùng Luật 2014 (hiệu lực từ 01/01/2015, khoảng nửa mở). Không gửi ngày → `system_today`.
- **Fast path (FR1.9-AC2, FR1.2-AC1).** Non-legal và ngoài phạm vi không có sự kiện `retrieval` hay `llm`.
- **Dưới ngưỡng (FR3.3-AC1).** HN_035 không có sự kiện `llm` (không gọi Qwen), `abstention_reason = LOW_CONFIDENCE`.
- **UI (IR1.3, FR5.8-AC1).** Câu trả lời hiển thị trong khung chat; mỗi tin nhắn của trợ lý có đúng một disclaimer; lịch sử giữ đủ 6 tin nhắn sau 3 câu; UI không báo lỗi. UI gửi `session_id`, `request_id` và không gửi `as_of_date` khi người dùng không chọn ngày.
- **Log (FR9.9, NFR3.4).** Sự kiện `llm` ghi `model = qwen2.5:7b`, `model_digest 845dbda0…697e`, `prompt_version v1.2_controlled_rag`, số token, `ttft_model_ms`. Sự kiện `retrieval` ghi `corpus_version`/`corpus_hash` `sha256:7105c484…6b023` và `retrieval_config_version`.

## 3. Nhánh chỉ có test tự động

| Nhánh | Test (FastAPI TestClient, Gateway / Ollama giả) |
| --- | --- |
| Gate FAIL, trích dẫn ngoài context | `test/api/test_error_mapping.py::test_gate_rows_hide_model_draft[gate_fail-…]`; `test/e2e/test_web_to_rag.py` |
| JSON lỗi / bị cắt → ABSTAIN `JSON_INVALID`, HTTP 200 | `test_gate_rows_hide_model_draft[bad_json-…]`, `test_gate_detail_code[...]` |
| LLM timeout → ERROR `LLM_TIMEOUT`, 504 | `test_pipeline_error_rows[timeout-…]`; `test/e2e/test_web_to_rag.py` |
| Model không kết nối → ERROR `LLM_UNAVAILABLE`, 503 | `test_pipeline_error_rows[unavailable-…]`: skip, `ErrorCode` của `week10_v1.0` chưa có mã này. Hiện tại trả ERROR `INTERNAL_ERROR` 500 |
| Rỗng (`RETRIEVAL_EMPTY`) | `test_route_and_retrieval_rows[empty]` |

## 4. Giới hạn của lần chạy

- **Gate FAIL, JSON lỗi:** không ép được Qwen thật trả citation sai hay JSON hỏng với prompt v1.2 trên các câu thử; ca thật đã gặp là HN_300 ở Run B 10/11.
- **Timeout, mất kết nối:** cần đổi `timeout_seconds` trong `model_gateway/config/local_qwen.yaml` hoặc tắt Ollama trên máy dùng chung. Lần này không làm; nên chạy ở buổi live có người điều phối.
- **Không có ảnh chụp màn hình.** UI chạy qua `streamlit.testing.v1.AppTest` (đúng script và `api_client` của UI, không qua trình duyệt). Ảnh chụp trình duyệt thuộc frontend QA của Dev 2 (D2.5).
- **Router:** bản trên `testing` (`rule_router_v2`). Router v3 và Retrieval Adapter của Dev 4 (PR #56) chưa merge, chưa freeze (S11-03). Khi merge, chạy lại lệnh ở mục 5.
- **Provenance:** `retrieval_config_version` trong log là `sha256:a650eac52ec2ba74`, tức là hash rút gọn dùng làm version. Đây là lỗi D4.3 (gán version vào trường hash) của Retrieval Adapter, Dev 4 sửa.

## 5. Lệnh tái chạy

```powershell
# API: xem docs/operations/runbook.md mục 3 (ES, Qdrant embedded, Ollama, LEGAL_RAG_EVENT_LOG)
uvicorn api.main:app --host 127.0.0.1 --port 8000
# Kiểm tra live (cửa sổ khác)
$env:LEGAL_RAG_API_KEY = "<key của server>"
python scripts/run_live_e2e.py --event-log <file LEGAL_RAG_EVENT_LOG> --out reports/week11/live
# Mock E2E (CI, không cần dịch vụ)
python -m pytest -q test/e2e test/api
```

Môi trường: xem `reports/week11/performance_smoke.md`.
