# SPRINT 6 — BENCHMARK HÔN NHÂN VÀ GIA ĐÌNH (300 CÂU)

**Phiên bản:** `2026-10-16 | handoff-300-review-required`  
**Nhiệm vụ:** Thiết kế 50–100 câu (mở rộng theo yêu cầu lead lên 300); chuẩn hóa schema; đáp án, giải thích, `gold_context_ids`; Dev/Test; validator; đóng băng Test.

## 1. Danh mục 6 file bắt buộc

| File | Trạng thái | Ghi chú |
| --- | --- | --- |
| `schemas/benchmark_schema.json` | Đã tạo | Contract cho câu hỏi và Ground Truth có provenance |
| `data/benchmark/queries_dev.json` | Đã tạo | 285 câu phát triển |
| `data/benchmark/queries_test.json` | Đã tạo, **frozen** | 15 câu Test từ bản người dùng đưa; SHA-256 manifest |
| `data/benchmark/ground_truth.json` | 300 hàng **DRAFT** | Có `answer_kind`, đáp án nháp và dẫn chiếu; chưa phải Gold đã duyệt |
| `test/test_benchmark.py` | Đã tạo và chạy | Bao gồm lỗi schema, ID, nhãn giả, hiệu lực và Test freeze |
| `docs/sprint6_benchmark.md` | Tài liệu này | Tiến độ, kỹ thuật, giới hạn và nghiệm thu |

## 2. Số liệu thực tế

- **300 câu**: 285 Dev / 15 Test, giữ nguyên 60 câu ban đầu và 15 Test.
- **240 câu mới**: trích PDF làm bản trả lời đối chiếu, thêm mã Điều (không phải mã chunk).
- **300 bản Ground Truth** hiện là nháp, 0 câu có `review_status` được người duyệt xác nhận và 0 câu có `gold_context_ids_confirmed=true`.
- **276 câu** có `candidate_context_ids` là chunk_id của corpus hiện tại (`mapping_status = production_candidate_unverified`, 759 ID, 100% có trong `data/chunking_output/chunks.jsonl`), **24 câu** chưa ánh xạ chunk (`not_mapped`). **Cả 300 câu đều có `gold_context_ids=[]`**: candidate chưa phải Gold đã xác minh.
- L01.pdf (bản gốc Luật 52/2014/QH13) nay parse đủ **133/133 điều**.

### Cấu trúc câu hỏi

| Nhóm kiểm thử | Số câu |
| --- | ---: |
| `current_law` | 219 |
| `partially_expired` | 59 |
| `outdated_law_trap` | 16 |
| `historical_law` | 6 |

| Loại câu | Số câu |
| --- | ---: |
| `situation` | 185 |
| `fact` | 90 |
| `multi_hop` | 25 |

## 3. Công nghệ, nguồn và luồng dữ liệu

Python 3.13, JSON Schema Draft-07, `unittest`. Toàn bộ dữ liệu nằm trong `data/benchmark/` và `schemas/benchmark_schema.json`.

## 4. Hướng dẫn chạy và nghiệm thu kỹ thuật

1. Cài đặt Python 3.13 hoặc môi trường tương thích.
2. Chạy validator:
   ```bash
   python scripts/validate_benchmark.py
   ```
3. Chạy test suite:
   ```bash
   python -m pytest test/test_benchmark.py
   ```

## 5. Quy trình xác minh pháp lý và rà soát chất lượng

Người phụ trách cần kiểm tra nội dung chunk có thực sự trả lời câu hỏi và có thuộc đúng văn bản, Điều/Khoản, ngày áp dụng; đối với câu multi-hop, đối chiếu tất cả điều liên quan. Khi reviewer đã xác minh và có `verified_by`/`verified_at`, mới cập nhật nhãn và chạy nghiệm thu cuối. Đặc biệt các câu hỏi `outdated_law_trap`, `historical_law`, `partially_expired` phải kiểm tra điều khoản sửa đổi/bãi bỏ, không chỉ nhìn `validity_status` ở cấp văn bản.

## 6. Hướng dẫn reviewer và chia sẻ

- `docs/review_dev_285.csv`: bảng cần review của Dev; có thể gửi cho người kiểm duyệt nguồn. `docs/quality_review_priorities_dev.csv` có cảnh báo rủi ro từng câu Dev.
- `docs/review_test_15_RESTRICTED.csv` và `docs/quality_review_priorities_test_RESTRICTED.csv`: chỉ có trong gói kiểm duyệt riêng, **không đẩy vào repository dùng để tuning Retrieval**.
- `docs/answer_source_audit.csv`: thông tin trích xuất nguồn cho 240 câu mở rộng. Bỏ các bảng review trùng/đã cũ để giảm nhầm lẫn.
- `data/reference/context_registry.json` giữ dữ liệu *smoke* để truy nguyên, không dùng làm final Gold.
- `docs/handoff_manifest.json`: hash nguồn, hash Test và phiên bản.

## 7. Bảng trạng thái nghiệm thu

| Yêu cầu lead | Hiện trạng |
| --- | --- |
| Xây 50–100 câu (mở rộng 300) | Đạt số lượng; cần rà chất lượng câu mới |
| Chuẩn hóa schema | Đạt kiểm thử tự động |
| Xác minh câu trả lời, lời giải thích | **Chưa đạt** — 300 draft, cần người rà soát nội dung và hiệu lực |
| Gold context IDs | **Chưa đạt** — chưa có nhãn đã xác minh từ index thật |
| Chia Dev/Test | Đạt 285/15 |
| Validator kiểm tra dữ liệu | Đạt ở mức cấu trúc; Final có bộ chặn an toàn |
| Đóng băng Test set | Đạt đối với câu hỏi Test; Gold Test chờ duyệt |

**Kết luận để báo lead:** Đã bàn giao đủ sáu file và bộ kiểm thử cho 300 câu theo cấu trúc chuẩn. Sản phẩm là **benchmark draft có kiểm định cấu trúc**, không phải tập 300 câu Gold đã được người duyệt và gắn với production chunk. Không được báo hoàn tất `gold_context_ids` trước khi nhận index thật.

## 8. Đồng bộ Article Registry

Đã bổ sung **181 bản ghi** vào `data/reference/article_index.json`, nâng từ 261 lên **442 mục của 12 văn bản** theo snapshot metadata cập nhật của dự án. Các bản ghi mới đánh dấu `metadata_only_unverified`; riêng L01_D132–L01_D133 mới có trong metadata, không có trong PDF L01 đã parse và chưa được dùng làm bằng chứng truy xuất.

## 9. Những điểm đã sửa sau kiểm toán 16/10/2026

- **Sửa dữ liệu nguy hiểm:** 34 ID smoke không còn được gọi là `gold_context_ids`; chuyển sang `candidate_context_ids`. Số Gold thực sự xác nhận là **0/300**.
- **Thêm `answer_kind`** cho cả 300 câu; phân biệt 60 đáp án nháp với 240 đoạn trích PDF tự động. `--final` chặn đoạn trích PDF chưa biên soạn lại.
- **Thêm kiểm toán chất lượng** `scripts/audit_quality.py` và hai bảng ưu tiên Dev/Test tách biệt; kiểm tra câu hỏi quá chung, câu trả lời quá dài, nghi dính tiêu đề chương, nguồn chưa xác minh và hiệu lực theo thời điểm. Các cảnh báo không tự kết luận đúng/sai về pháp luật.
- **41 unit tests** PASS; manifest khóa 15 câu Test giữ nguyên SHA-256.
- **Chưa được xem là hoàn thành:** review nội dung câu hỏi/đáp án, ngày hiệu lực từng điều khoản, kiểm tra 2 Điều thiếu 132–133 của L01 và xác nhận ID production chunk từ thành viên Chunking.
- Đáp án Test hiện nằm trong file Ground Truth chung. Nếu repo cho phép người tối ưu RAG xem, cần quy trình phân quyền riêng để tránh học thuộc nhãn Test trước khi đánh giá.

## 10. Bảng Ánh xạ Tên trường (Field Name Mapping Contract)

Nhằm đảm bảo tính tương thích và nhất quán giữa quy chuẩn Benchmark Sprint 6, các tài liệu kỹ thuật và mã nguồn kiểm thử / retrieval:
- **Đầu vào Benchmark:** Bắt buộc sử dụng khóa `id` (VD: `HN_001` .. `HN_300`).
- **Đầu ra Retrieval & Evaluation:** Tất cả các module pipeline, retriever và đánh giá bắt buộc sử dụng chuẩn duy nhất `query_id` (loại bỏ alias `question_id` khỏi mọi đầu ra chính thức).

Bảng ánh xạ chuẩn tắc giữa các tên trường:

| Khái niệm nghiệp vụ | Tên trường chính thức (`schemas/benchmark_schema.json`) | Tên trường trong đầu ra Retrieval / Evaluation | Mô tả & Ràng buộc |
| :--- | :--- | :--- | :--- |
| **Mã câu hỏi** | `id` | `query_id` | Định danh duy nhất của câu hỏi (VD: `HN_001` .. `HN_300`). Bắt buộc. |
| **Phân loại chủ đề** | `category` | `category` (alias `topic`) | Nhóm chủ đề câu hỏi (VD: `ket_hon`, `ly_hon`, `tai_san`, `con_chung`, v.v.). |
| **Đáp án chuẩn** | `answer` | `expected_answer` | Nội dung câu trả lời chuẩn tham chiếu hoặc trích xuất từ văn bản pháp luật. |
| **Tập phân chia** | `split` | `split` | Thuộc tập phát triển (`"dev"`, 285 câu) hoặc tập kiểm thử (`"test"`, 15 câu). Enum: `["dev", "test"]`. |
| **Thời điểm câu hỏi** | `as_of_date` | `as_of_date` | Mốc thời gian áp dụng luật (VD: `"2026-10-15"`). Định dạng chuẩn `YYYY-MM-DD`. |

## 11. Nhật ký đóng băng Test và cập nhật ID

Mọi thay đổi `data/benchmark/queries_test.json` phải qua review và được ghi vào bảng này (ngày, commit, lý do, SHA-256 cũ và mới của `docs/test_questions_freeze.json`). Thay đổi chunk_id của candidate hoặc proposal cũng ghi ở đây.

| Ngày | Commit | Thay đổi | SHA-256 Test |
| --- | --- | --- | --- |
| 16/10/2026 | b230265 | Đóng băng 15 câu Test lần đầu. | `0b4b3a2f75a0…cdbdf` |
| 22/10/2026 | ee755a5 | Thêm trường `split` vào 15/15 câu Test; nội dung câu hỏi và danh sách ID không đổi, `freeze_test.py --verify` PASS. Lần đóng băng lại này không có review riêng; ghi bổ sung ngày 25/10. | `0b4b3a2f75a0…cdbdf` → `6942c3353a62…fb889` |
| 25/10/2026 | 146a6c9 | Sinh lại `production_chunk_index.json` từ corpus 664634e (2.011 chunk). Map lại theo nội dung chunk: candidate của HN_255, HN_265, HN_266, HN_267, HN_269 (các Khoản NQ 01/2024 và một phần Khoản NĐ 207/2025 Điều 9 đổi ranh giới); toàn bộ chunk_id của `gold_id_proposals_300.json` (sang `{clause_id}_chunk_{n}`, giữ nguyên ID `version_*`). Test không đổi. | `6942c3353a62…fb889` (không đổi) |
| 27/10/2026 | refactor | Hợp nhất toàn bộ candidate/proposal từ `gold_id_proposals_300.json` vào `ground_truth.json`; xóa bỏ file thừa `gold_id_proposals_300.json`. Test không đổi. | `6942c3353a62…fb889` (không đổi) |
