# Sprint 11 validator regression

Ngày thực hiện: 22/11/2026. Nhánh `feature/sprint11-dev1-hardening`, từ `testing` tại `03a4989`. Dev 1 mở rộng validator hiện có, giữ nguyên interface `validate_citations(...)` và canonical schema của Dev 3.

## Thay đổi

- Kiểm tra khoảng hiệu lực `[effective_from, effective_to)` bằng `as_of_date` của context. Ngày bắt đầu được nhận; ngày kết thúc bị loại. Mọi evidence đã render vào prompt đều phải qua kiểm tra, kể cả evidence không được cite.
- Kiểm tra thứ tự index liên tục, ngày tra cứu/ngày hiệu lực hợp lệ, khoảng ngày có thứ tự, source_map khớp ngày và metadata hiển thị.
- Trả GroundingResult với mã lỗi ổn định; không sửa citation, sinh câu trả lời hoặc gán nhãn hallucination ngữ nghĩa. Các giới hạn Top-5 và field/enum canonical không đổi.
- Nguồn có nhãn hết hiệu lực hiện tại vẫn có thể qua kiểm tra khi ngày lịch sử nằm trong khoảng hiệu lực. Evidence thiếu cả hai mốc ngày chỉ được kiểm cấu trúc, không được coi là đã xác minh hiệu lực pháp lý.

## Kiểm tra

```powershell
python -m pytest -q test/grounding test/monitoring test/orchestration
python -m pytest -q
python -m ruff check .
git diff --check
```

Bộ test có18 case synthetic tại `evaluation/quality/grounding_cases_sprint11.jsonl`, cùng regression cũ về mapper, provenance và malformed inputs. Mã mới gồm `EVIDENCE_NOT_YET_EFFECTIVE`, `EVIDENCE_EXPIRED_AS_OF_DATE`, `INVALID_EFFECTIVE_INTERVAL`, `INVALID_AS_OF_DATE`, `INVALID_EFFECTIVE_DATE`, `NON_CONTIGUOUS_CONTEXT_INDEX`, `SOURCE_MAP_TEMPORAL_MISMATCH` và `SOURCE_MAP_METADATA_MISMATCH`.

Test `test_run_rag_adapter_uses_benchmark_date` trước đây dùng fixture có hiệu lực2015 nhưng tra cứu2010 và vẫn yêu cầu PASS. Chỉ dữ liệu mô phỏng của test này được đổi thành evidence lịch sử từ2000 và nhãn synthetic; assertion về ngày benchmark, nguồn ngày và PASS được giữ nguyên. Không sửa orchestration production, benchmark hoặc Gold.

Kết quả cuối nằm trong `dev1_validation_summary.json`, `dev1_full_tests.log` và `dev1_api_compatibility_tests.log`. API compatibility chạy trên `9a0e943` với overlay module Dev 1 và bản sửa fixture trên; Dev 5 routes/pipeline không bị sửa. Đây là HTTP với fake services, không phải Qwen live.

## Bàn giao

Dev 5 tiếp tục gọi mapper rồi validator như `docs/citation_validator.md`. Gate vẫn chịu trách nhiệm buffer draft, map lỗi sang response và retry/abstain. Nguồn ngày/hiệu lực phải do Retrieval/Context producer cung cấp đúng; validator không phục hồi chuỗi sửa đổi hoặc chứng minh nội dung khớp pháp luật bằng ID đơn thuần.
