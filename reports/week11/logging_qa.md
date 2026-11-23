# Sprint 11 logging QA

Ngày thực hiện: 22/11/2026. Dev 1 bàn giao StructuredLogger, PIIMasker và APIEventAdapter theo LogEvent canonical. Hướng dẫn tích hợp: `docs/operations/logging.md`; policy: `docs/privacy/logging_policy.md`.

## Bằng chứng

| Nhóm | Kiểm tra |
|---|---|
|PII và secret|Email, số điện thoại, ID9/12 chữ số, Bearer/token prefixes, secret được cấu hình; giá trị nằm trong field được phép vẫn phải che|
|Metadata|Bỏ raw query/prompt/draft ở production, header/environment/secret keys và key ngoài allow-list; debug opt-in vẫn che dữ liệu|
|Hàng đợi|Queue có giới hạn; emit không chờ sink/disk; queue đầy có bộ đếm và không làm lỗi request|
|Lỗi|Sink và diagnostic callback ném exception không làm fail câu trả lời; không ghi raw exception message|
|Vòng đời|flush/close có timeout; sink bị treo không bắt shutdown đợi vô hạn; emit sau close được bỏ an toàn|
|Correlation|Cùng query_id xuyên stage; query_id có PII dùng HMAC trong process, không gộp hai request khác nhau thành một nhãn che chung|
|API adapter|Fake harness cho401/403/422; alternate sink chỉ nhận event đã che; API policy/status thực do Dev 5 quyết định|
|HTTP compatibility|Trên API branch9a0e943, request401/422 và legal PASS được ghi bằng logger mới; lỗi sink không phá response. Backend services đều là fake|

`logs/sample_request.jsonl` có9 event synthetic,3 query_id;7 event tạo một request chain,2 event minh họa auth/validation rejection. `logging_sample_validation.json` xác nhận parse bằng canonical LogEvent và không chứa các literal PII/secret synthetic đầu vào. Số đo/hash trong sample là minh họa, không phải benchmark runtime hoặc hash corpus production.

Kết quả pytest/Ruff/OpenAPI cuối nằm trong `dev1_validation_summary.json`. Một cảnh báo deprecation của Starlette/AnyIO trong môi trường compatibility không làm fail test.

## Điểm tích hợp còn thuộc Dev 5

- Cắm sink vào app/AskService lifecycle; dùng cùng instance và gọi close có timeout khi shutdown.
- API branch hiện đã phát request/auth/validation/stage events; tránh thêm event trùng. Dùng adapter cho boundary chưa có emit hoặc gọi `event(...)` với tên hiện tại.
- Bàn giao secret values từ settings cho masker. Align allow-list StageEmitter khi thêm hash/timing fields đã được Dev 3 duyệt.
- Chạy live UI–API–Retrieval–Qwen–Gate với query_id trace và chốt policy lưu trữ/retention. Báo cáo này không xác nhận live E2E hoặc thay sign-off của Dev 5/Tech Lead.
