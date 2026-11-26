# Sprint 11 Dev 1 handoff

Nhánh `feature/sprint11-dev1-hardening` từ `testing` tại03a4989. Module validator/logger/PII/event adapter và18 fixture synthetic đã sẵn sàng review. Chi tiết kết quả chạy nằm trong `dev1_validation_summary.json` và hai log pytest đi kèm.

| Task | Kết quả bàn giao |
|---|---|
|D1.1 P0|Validator mở rộng kiểm tra temporal, source_map và index; giữ interface/schema cũ, mã lỗi ổn định|
|D1.2 P0|Logger async queue có giới hạn, PIIMasker, non-fatal failures, JSONL sample và policy|
|D1.4 P0|API adapter, fake security harness và HTTP compatibility với API branch9a0e943; không sửa routes/wiring của Dev5|
|D1.3 P1|18 case synthetic, expected codes, audit không trùng13 snapshot benchmark/negative/holdout; chờ peer review nhãn|

**Test toàn repo:1490 passed,2 skipped,179 subtests passed.** Một skip có sẵn ở baseline; một skip cho module HTTP integration tùy chọn vì API của Dev5 chưa merge vào testing. Trên nhánh API tương thích, **353 test pass** và OpenAPI check pass. Test này dùng fake backend, không phải Qwen live. Ruff toàn repo và whitespace check pass.

## Cách dùng

Dev5 truyền `StructuredLogger` vào EventSink của AskService/StageEmitter; dùng `PIIMasker(secret_values=configured_keys)`, giữ một instance theo lifecycle ứng dụng và gọi close có timeout ở shutdown. Không thêm event trùng với request/auth/validation events đã có. Hướng dẫn đầy đủ: `docs/operations/logging.md` và `monitoring/log_schema.md`.

Giữ cách gọi mapper rồi `validate_citations(...)` hiện có. Dev3 vẫn sở hữu schema; Dev5 sở hữu Gate, retry/abstain, API status mapping và wiring. Thay đổi ngoài phạm vi module duy nhất là dữ liệu synthetic của test ngày benchmark: evidence mẫu2015 được đổi thành nguồn giả lập có hiệu lực từ2000 để hợp lệ cho câu hỏi2010; không đổi assertions hoặc code orchestration.

## Việc còn cần phối hợp

Dev5 tích hợp production sink/lifecycle, cung cấp secrets an toàn và chạy live E2E cùng UI. Dev3/Dev5 cần duyệt metadata mới trước khi mở rộng allow-list của StageEmitter. Deployment owner chốt quyền truy cập, retention và rotation. Reviewer duyệt nhãn fixture và Tech Lead sign-off. Không thay corpus, schema, prompt, threshold, benchmark/Gold hoặc official A/B output.
