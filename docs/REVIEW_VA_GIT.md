# BÀN GIAO SPRINT 6 VÀ ĐẨY GITHUB AN TOÀN

## Trạng thái

**Có thể tạo Pull Request để nhóm review bản nháp**, KHÔNG báo benchmark đã có Gold pháp lý. Số liệu: 300 câu, 285 Dev/15 Test; 0/300 Gold xác nhận; 240 đáp án vẫn là trích đoạn PDF chưa viết câu trả lời hoàn chỉnh.

## 1. Chạy kiểm thử trong thư mục ZIP đã giải nén

```powershell
python -m pip install -r requirements.txt
python scripts/validate_benchmark.py
python -m pytest test/test_benchmark.py -v
python scripts/freeze_test.py --verify
python scripts/audit_quality.py
```

**Mong đợi**: 0 lỗi cấu trúc; 41 test OK; câu hỏi Test không thay đổi. `python scripts/validate_benchmark.py --final` phải FAIL cho đến khi có Gold thật và người kiểm duyệt.

## 2. KHÔNG đưa Benchmark vào PR Parser #2

Repo hiện tại: `D:\GitHubProjects\Vietnam-Legal-RAG-Assistant`. Nhánh đang làm việc `feature/legal-data-chunking`, PR #2 đang mở. **Không tiếp tục commit benchmark trên nhánh đó.** Có thể tách một worktree mới để giữ nguyên cả dữ liệu Chunking chưa được theo dõi (untracked) ở thư mục cũ:

```powershell
cd D:\GitHubProjects\Vietnam-Legal-RAG-Assistant
git fetch origin main
git worktree add -b feature/sprint6-benchmark ..\Vietnam-Legal-RAG-Assistant-benchmark origin/main
```

Tại thư mục mới `D:\GitHubProjects\Vietnam-Legal-RAG-Assistant-benchmark`, chép lần lượt **các file của ZIP vào đúng đường dẫn tương ứng**, rà soát xung đột tên file. Không ghi đè mã chunking, parser hay `requirements.txt` hiện hữu của nhóm khi chưa xem diff.

**6 đầu ra tối thiểu phải có**: `schemas/benchmark_schema.json`, `data/benchmark/queries_dev.json`, `data/benchmark/queries_test.json`, `data/benchmark/ground_truth.json`, `test/test_benchmark.py`, `docs/sprint6_benchmark.md`. Đồng thời cần giữ các dependency thực sự được script dùng (`data/reference/*`, `scripts/validate_benchmark.py`, `scripts/freeze_test.py`, `scripts/freeze_gold.py`, v.v.), manifest đóng băng Test, và `jsonschema>=4.21,<5` trong môi trường cài đặt.

Không dùng `git add .` khi chưa kiểm tra. Với bản ZIP này, nếu những đường dẫn không đè lên file của nhóm, có thể stage rõ ràng:

```powershell
git status --short
git add schemas/benchmark_schema.json data/benchmark/ data/reference/ test/test_benchmark.py
git add scripts/validate_benchmark.py scripts/freeze_test.py scripts/freeze_gold.py scripts/check_review_coverage.py scripts/import_chunk_index.py scripts/suggest_chunk_mapping.py scripts/audit_quality.py
git add docs/sprint6_benchmark.md docs/test_questions_freeze.json docs/quality_audit.json docs/quality_review_priorities_dev.csv docs/review_dev_285.csv docs/qa_summary.json docs/handoff_manifest.json
git diff --cached --stat
```

Nếu muốn đưa thêm hướng dẫn, chỉ stage file README/docs phù hợp. **KHÔNG stage `docs/*RESTRICTED*` hoặc bản Test Gold riêng vào repo mọi thành viên đều có quyền đọc.** `ground_truth.json` theo contract vẫn có Test Gold, nên phải giới hạn quyền truy cập repo hoặc tách lớp lưu trữ khi đánh giá chính thức.

Sau khi chạy validator trong repo đích và xem `git diff --cached`, mới commit và push:

```powershell
git commit -m "feat: add Sprint 6 legal QA benchmark draft and validation"
git push -u origin feature/sprint6-benchmark
```

Mở Pull Request mới từ `feature/sprint6-benchmark` → `main` để review; không bấm merge khi nhóm chưa thống nhất.

## 3. Công việc tiếp theo

1. Người duyệt nguồn xem `docs/quality_review_priorities_dev.csv`, chỉnh câu hỏi quá chung và viết lại 240 đáp án hiện đang là đoạn trích điều luật.
2. Soát hiệu lực theo `as_of_date` + người duyệt, thời điểm duyệt.
3. Nhờ bạn Chunking xuất đúng output được hệ thống RAG index; `scripts/import_chunk_index.py` chỉ tạo ứng viên từ chunk, **không tự xác minh index triển khai thật**.
4. Map `gold_context_ids` đã xác minh, chuyển `answer_kind` thành `reviewed_answer` sau duyệt.
5. Chỉ khi `python scripts/validate_benchmark.py --final` PASS, mới `python scripts/freeze_gold.py --create`.
