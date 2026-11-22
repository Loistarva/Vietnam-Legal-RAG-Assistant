# Báo cáo E2E Tuần 10 – CLI/API → Router → RAG → Grounding Gate (Dev 5, D5.7)

Ngày chạy: 2026-11-16. Nhánh `feature/week10-fastapi-integration` trên `testing` 01fe249 (sau khi PR #49 merge). Lần chạy live ở mục 3 làm trên contract 9d57092, trước hai commit cuối của #49; hai commit đó chỉ thêm field vào `AskResponse` (`as_of_date`, `as_of_date_source`, `timings.total_ms`, `ErrorDetail`), không đổi luồng xử lý.

## 1. Phạm vi và kết luận

| Bước D5.7 | Kiểm thử tự động (fake retrieval + fake Ollama HTTP) | Live (ES + Qdrant + Qwen thật) |
| --- | --- | --- |
| 1. Legal HNGĐ đủ evidence: API → Router → Retrieval → Context → Qwen → Validator → Gate | PASS | PASS (3/3 câu, Gate PASS, citation đúng Điều 8 / Điều 29–30) |
| 2. Non-legal fast-path không gọi Retrieval/LLM | PASS (đếm lời gọi = 0) | PASS (28 ms, không có event retrieval/llm) |
| 3. Legal ngoài phạm vi → Policy Abstention | PASS | PASS (`ROUTE_POLICY`, 14 ms) |
| 4. Evidence rỗng / low confidence không gọi generation | PASS (cả hai) | PASS cho low confidence (HN_035, top-1 = 0.087 < 0.5); evidence rỗng chưa tái hiện được trên corpus thật |
| 5. Citation ngoài context → Gate FAIL, không lộ draft | PASS (`[1, 7]`, `[3]`, marker `[4]` trong answer) | Không ép được model trả citation sai; trường hợp thật là HN_300 ở Run B 10/11 |
| 6. Log theo `query_id` xuyên các stage | PASS | PASS (8 request, mỗi request một `query_id` từ `api` đến `api`) |
| UI → API | Chưa làm: UI của Dev 2 (PR #51) chưa nối vào API live | – |

Chỉ bước "UI → API" chưa làm, vì cần PR #51 của Dev 2. Các nhánh nghiệp vụ còn lại đều có test tự động; nhánh Gate FAIL và evidence rỗng chưa có bằng chứng live.

## 2. Môi trường live

| Thành phần | Giá trị |
| --- | --- |
| Máy | Windows 11, RTX 3050 Ti 4 GB, 16 GB RAM, Python 3.14.10 (`D:\AI_PRJ\.venv-vlra`) |
| Elasticsearch | 9.5.3 local, index `bm25-e6-verified-20261101` |
| Qdrant | embedded, `vietnam_legal_chunks` (BGE-M3, 2.322 chunk) |
| Corpus | `sha256:7105c484…6b023` (khớp metadata index) |
| Retrieval config | `sha256:a650eac52ec2ba74`; confidence `conf_v1_20261109` |
| Model | Ollama 0.40.16, `qwen2.5:7b`, digest `845dbda0ea48…697e`, `repeat_penalty 1.0`, timeout 120 s |
| Router | `rule_router_v2` (bản trên `testing`; Router v3 của Dev 4 ở nhánh `sprint10_Dev4_Rule-Router_Retrieval-Adapter` chưa merge) |
| Run mode | `C_production_rag` (Run B chính thức vẫn là `B_controlled_rag`, không đổi) |

## 3. Kết quả live qua HTTP (`uvicorn api.main:app`)

| Case | HTTP | status / route / grounding | error_code | Thời gian client | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| Thiếu `X-API-Key` | 401 | – | `AUTH_REQUIRED` | 11 ms | Bị chặn trước pipeline |
| Key sai | 403 | – | `AUTH_REQUIRED` | 23 ms | |
| Body rỗng | 422 | – | `INVALID_REQUEST` | 38 ms | |
| "Nam phải đủ bao nhiêu tuổi thì được kết hôn?" (request đầu) | 200 | SUCCESS / LEGAL_IN_SCOPE / PASS | – | 72,4 s | retrieval 57,4 s gồm nạp BGE-M3 + reranker lần đầu |
| "Vợ chồng có quyền và nghĩa vụ gì đối với tài sản chung?" | 200 | SUCCESS / LEGAL_IN_SCOPE / PASS | – | 44,1 s | citation Điều 29 k1, Điều 30 k2; retrieval 12,0 s, LLM 31,9 s |
| "Tại ngày 01/01/2015, điều kiện kết hôn về độ tuổi là gì?" | 200 | SUCCESS / LEGAL_IN_SCOPE / PASS | – | 30,2 s | ngày lấy từ câu hỏi: answer ghi "tại ngày 2015-01-01" |
| "Hôm nay thời tiết Hà Nội thế nào?" | 200 | SUCCESS / NON_LEGAL / NOT_RUN | – | 28 ms | |
| "Thủ tục thành lập doanh nghiệp tư nhân thế nào?" | 200 | ABSTAIN / LEGAL_OUT_OF_SCOPE / NOT_RUN | `ROUTE_POLICY` | 14 ms | |
| HN_035 (tiền đề sai, as_of 2026-10-15) | 200 | ABSTAIN / LEGAL_IN_SCOPE / ABSTAIN | `LOW_CONFIDENCE` | 14,8 s | top-1 0.087; không gọi Qwen |
| SSE "Điều kiện để được nhận con nuôi là gì?" | 200 | ABSTAIN | `LOW_CONFIDENCE` | first byte 115 ms, final 20,3 s | top-1 0.485 |
| SSE "Nữ phải đủ bao nhiêu tuổi thì được kết hôn?" | 200 | SUCCESS | – | first byte 17 ms, `verified_answer` 85,8 s | answer chỉ có ở event cuối |

Bảng trên là lần chạy ngày 16/11 ở `29d3b70`. Từ `03b54bc` (22/11, theo SRS 2.1.2): key sai trả 401 thay vì 403; câu bị Confidence Filter từ chối (HN_035, câu nuôi con nuôi) có `grounding_status = NOT_RUN`; SSE dùng `sse_v2`, event cuối là `final` thay cho `verified_answer` + `done`. Chưa chạy live lại sau các thay đổi này; test tự động đã phủ.

Thời gian là số đo của một lần chạy trên máy GPU 4 GB, không phải số đo NFR. Kế hoạch yêu cầu không tuyên bố đạt NFR khi chưa đo trên môi trường đích. Thời gian LLM dao động 15–70 s cho cùng một loại câu, vì Qwen chạy chung GPU với BGE-M3 và reranker trong cùng tiến trình API.

Log (`LEGAL_RAG_EVENT_LOG`): 74 event, parse JSON được, không chứa API key và không chứa nội dung câu hỏi. Ví dụ chuỗi stage của một câu legal: `api router retrieval retrieval rerank context llm llm citation gate response api`.

## 4. Lệnh tái chạy

```powershell
# Tự động (không cần dịch vụ)
python -m pytest -q test/orchestration test/api test/e2e
python -m api.export_openapi --check

# Live
C:\tools\elasticsearch-9.5.3\bin\elasticsearch.bat           # cửa sổ riêng
$env:HF_HUB_OFFLINE = "1"; $env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:QDRANT_PATH = "<repo có index>\data\indexes\qdrant_storage"
python scripts/run_rag_cli.py --as-of-date 2026-11-16 "Nam phải đủ bao nhiêu tuổi thì được kết hôn?"
$env:LEGAL_RAG_API_KEYS = "<key>"; $env:LEGAL_RAG_EVENT_LOG = "logs/api_events.jsonl"
uvicorn api.main:app --host 127.0.0.1 --port 8000
# rồi gọi theo docs/api.md mục 3
```

## 5. Known issues (owner, mốc)

| # | Vấn đề | Ảnh hưởng | Owner / đề xuất |
| --- | --- | --- | --- |
| K1 | UI chưa nối vào API live; client Streamlit gọi `raise_for_status()` (mất body 504/500) và timeout 60 s < thời gian một câu live | W10-07 chưa có live E2E | Dev 2, sau khi PR này merge (docs/api.md mục 4) |
| K2 | Logger chính thức (Dev 1, D1.2) chưa có trên `testing`; hiện dùng `JsonlEventSink` tạm, có allow-list key metadata | W10-08 cần logger + PII masker của Dev 1 | Dev 1: implement `emit(LogEvent)` rồi gắn vào `orchestration.wiring.build_event_sink` |
| K3 | ~~Request bị 401/403/422 không sinh `LogEvent`~~ | Đã xong ở `03b54bc`: 401/422/500 trước pipeline ghi event `api` / `request_rejected` có `http_status`, `error_code` | – |
| K4 | Router v3 chưa merge; live chạy `rule_router_v2` | Định tuyến có thể khác sau khi merge | Dev 4; chạy lại bảng mục 3 sau khi merge |
| K5 | Request đầu tiên nạp model mất khoảng 57 s; LLM 15–70 s trên GPU 4 GB | Latency, timeout phía UI | Dev 5: warm-up ở lifespan (P1); triển khai trên máy đủ VRAM |
| K6 | Qdrant embedded chỉ cho một tiến trình | API và batch không chạy song song được | Dùng `QDRANT_URL` (Qdrant server, Dev 4) |
| K7 | SSE không hủy được lời gọi Qwen đang chạy khi client ngắt | Tốn tài nguyên tới khi xong | Ghi nhận; cần gateway stream/cancel (Dev 3, P2) |
| K8 | ~~Contract thiếu `timings.total_ms`, `as_of_date`/`as_of_date_source`~~ | Đã xong: PR #49 merge (01fe249) thêm các field; API đã điền | – |
| K9 | Chưa có bounded recovery (thử lại tối đa một lần khi Gate FAIL có thể sửa) | FR5 phần recovery chưa đạt | Dev 5 + Dev 1, P1 |
| K10 | Câu hỏi nuôi con nuôi được route vào HNGĐ nhưng confidence thấp (0.485) | Có thể là thiếu văn bản trong corpus | Dev 4 / chủ corpus kiểm tra |
