# Vietnam-Legal-RAG-Assistant

Agent truy xuất và trả trích đoạn pháp luật với nguồn dẫn. Tích hợp OpenAI để
chọn nguồn; mặc định chạy offline, chưa sinh tư vấn pháp lý tự do.

- [Cấu hình OpenAI và chạy API JSON/SSE](docs/OPENAI_API.md)
- [Kết quả kiểm tra HTTP với chỉ mục thật](data/structure_v2/api/http_smoke.json)

## Dev 1 — validator và logging (Tuần 10)

[Hướng dẫn bàn giao D1.1–D1.5](docs/dev1_handoff.md): validator citation độc lập,
logger JSONL theo query_id, che PII/secrets, taxonomy và QA bằng fixture.
Không cần API/LLM; contract Dev 3 và tích hợp live Dev 5 còn chờ xác nhận.
Log runtime dùng `logs/runtime/` (không đưa lên Git); tắt bằng `enabled=False`.
