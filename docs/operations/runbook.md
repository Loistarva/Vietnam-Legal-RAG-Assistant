# Runbook – chạy hệ thống local (Web UI → API → RAG → Gate → Log)

Owner: Dev 5 (API/orchestration). Áp dụng cho bản trên nhánh tích hợp Sprint 11, contract `week10_v1.1`. Logger: Dev 1 (`docs/operations/logging.md`). UI: Dev 2 (`frontend/`).

## 1. Thành phần và cổng

| Thành phần | Cách chạy | Địa chỉ mặc định | Kiểm tra |
| --- | --- | --- | --- |
| Elasticsearch 9.x (BM25) | `bin\elasticsearch.bat` (security tắt, single-node) | `http://127.0.0.1:9200` | `curl http://127.0.0.1:9200/_cat/indices` có index trong `retrieval/config.yaml` (`bm25.index`) |
| Qdrant (Dense BGE-M3) | embedded: thư mục `QDRANT_PATH`; hoặc Qdrant server: `QDRANT_URL` | – | metadata index có `corpus_sha256` trùng corpus |
| Ollama + `qwen2.5:7b` | dịch vụ Ollama | `http://localhost:11434` | `curl http://localhost:11434/api/tags` có `qwen2.5:7b` |
| FastAPI | `uvicorn api.main:app --host 127.0.0.1 --port 8000` | `http://127.0.0.1:8000` | `GET /api/v1/health` trả 200, không cần key |
| Streamlit UI | `streamlit run frontend/streamlit_app.py` | `http://localhost:8501` | chọn "API" ở thanh bên |

Qdrant embedded khóa thư mục: chỉ một tiến trình mở được. Muốn chạy API và batch cùng lúc thì dùng Qdrant server (`QDRANT_URL`).

## 2. Biến môi trường

| Biến | Bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `LEGAL_RAG_API_KEYS` | có (API) | Danh sách key, cách nhau bằng dấu phẩy. Không có giá trị mặc định; thiếu thì API không khởi động. Không commit, không ghi vào log. |
| `LEGAL_RAG_PIPELINE_MODE` | không | `live` (mặc định) hoặc `mock` (không cần ES/Qdrant/Ollama, dùng cho UI) |
| `LEGAL_RAG_REGENERATION` | không | `on` (mặc định) cho phép sinh lại tối đa một lần khi câu trả lời bị cắt hoặc dùng ký hiệu căn cứ chưa khai báo. Đặt `off` để tắt. Chế độ đánh giá chính thức luôn tắt sinh lại. |
| `ELASTICSEARCH_URL` | live | URL Elasticsearch |
| `QDRANT_PATH` / `QDRANT_URL` | live | Qdrant embedded hoặc server |
| `HF_HUB_OFFLINE=1` | nên đặt | Dùng model BGE-M3 và reranker đã cache, không tải lại |
| `LEGAL_RAG_EVENT_LOG` | không | File JSONL sự kiện theo stage, ghi qua `monitoring.StructuredLogger` (che PII và các API key đã cấu hình) |
| `LEGAL_RAG_CLARIFICATION_CATALOG` | không | Đường dẫn đến tệp YAML chứa các mẫu câu hỏi làm rõ. Để trống để dùng thông báo chung. Nếu tệp đã cấu hình bị thiếu hoặc không hợp lệ, dịch vụ báo lỗi khi khởi động. |
| `LEGAL_RAG_MAX_CONCURRENCY` | không | Số request xử lý đồng thời (mặc định 1: một Qwen local) |
| `LEGAL_RAG_API_URL`, `LEGAL_RAG_API_KEY`, `LEGAL_RAG_REQUEST_TIMEOUT_SECONDS` | UI | URL `/api/v1/ask`, key client, timeout của UI (mặc định 180 s) |

## 3. Khởi động (PowerShell)

```powershell
# 1. Elasticsearch và Ollama đã chạy (mục 1)
# 2. API
$env:LEGAL_RAG_API_KEYS = "<key>"
$env:HF_HUB_OFFLINE = "1"
$env:ELASTICSEARCH_URL = "http://127.0.0.1:9200"
$env:QDRANT_PATH = "<thư mục>\data\indexes\qdrant_storage"
$env:LEGAL_RAG_EVENT_LOG = "logs\api_events.jsonl"
uvicorn api.main:app --host 127.0.0.1 --port 8000

# 3. UI (cửa sổ khác)
$env:LEGAL_RAG_API_URL = "http://127.0.0.1:8000/api/v1/ask"
$env:LEGAL_RAG_API_KEY = "<key>"
$env:LEGAL_RAG_REQUEST_TIMEOUT_SECONDS = "300"
streamlit run frontend/streamlit_app.py
```

Request legal đầu tiên chậm (nạp BGE-M3 và reranker, khoảng 1 phút trên GPU 4 GB). Các request sau chủ yếu là thời gian Qwen.

## 4. Kiểm tra sau khi chạy

```powershell
python -m pytest -q                       # gồm mock E2E test/e2e/test_web_to_rag.py
python -m api.export_openapi --check      # OpenAPI khớp code
$env:LEGAL_RAG_API_KEY = "<key>"
python scripts/run_live_e2e.py --event-log logs\api_events.jsonl --out reports\week11\live
```

`run_live_e2e.py` gửi các ca 401/422, Legal PASS, câu ngày trong câu hỏi, Non-legal, ngoài phạm vi, dưới ngưỡng tin cậy qua API, rồi ba ca qua chính script Streamlit (AppTest, chế độ "API"). Script đối chiếu `query_id` giữa phản hồi, header `X-Query-ID` và log, kiểm thứ tự stage theo FR9.9 và kiểm log không chứa API key. Mã thoát 1 khi có ca sai.

## 5. Log và dữ liệu nhạy cảm

- Log chỉ có id, phiên bản, số đếm, điểm, trạng thái, mã lỗi (`orchestration/events.py`, `SAFE_METADATA_KEYS`). Không ghi câu hỏi, prompt, câu trả lời của model hay header.
- `StructuredLogger` ghi nền qua hàng đợi có giới hạn; lỗi ghi log không làm đổi phản hồi (FR9.10). Đọc `logger.stats` để biết số sự kiện bị bỏ. API đóng logger khi tắt (lifespan).
- Thư mục `logs/` không đưa vào Git (trừ mẫu tổng hợp của Dev 1).

## 6. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
| --- | --- | --- |
| API không khởi động: thiếu key | `LEGAL_RAG_API_KEYS` rỗng hoặc có key ngắn hơn 16 ký tự | Đặt key ngẫu nhiên từ 16 ký tự trở lên |
| 401 `AUTH_REQUIRED` | thiếu/sai `X-API-Key` | Kiểm `LEGAL_RAG_API_KEY` của UI trùng key server |
| 422 `INVALID_REQUEST` | body sai, query rỗng hoặc dài hơn 2.000 ký tự | Sửa request; body lỗi là `ApiError`, có `details[]` |
| 504 `LLM_TIMEOUT` | Qwen chạy quá `timeout_seconds` (`model_gateway/config/local_qwen.yaml`) | Thử lại; kiểm GPU/RAM. Không đổi model ngầm |
| 503 `LLM_UNAVAILABLE` | Ollama tắt hoặc không kết nối được sau `max_retries` | Bật lại Ollama (`ollama serve`), kiểm `ollama list` có `qwen2.5:7b`; client thử lại (`retryable = true`) |
| Lỗi khóa thư mục Qdrant | hai tiến trình cùng mở Qdrant embedded | Dừng tiến trình kia hoặc dùng `QDRANT_URL` |
| UI báo "Không gọi được API" | API chưa chạy hoặc sai URL | `GET /api/v1/health`; kiểm `LEGAL_RAG_API_URL` |

## 7. Dừng

Ctrl+C ở cửa sổ uvicorn và Streamlit (logger được đóng, sự kiện còn trong hàng đợi được ghi xong trong 2 s). Dừng Elasticsearch và Ollama nếu không dùng.
