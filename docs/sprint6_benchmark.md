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
| `tests/test_benchmark.py` | Đã tạo và chạy | Bao gồm lỗi schema, ID, nhãn giả, hiệu lực và Test freeze |
| `docs/sprint6_benchmark.md` | Tài liệu này | Tiến độ, kỹ thuật, giới hạn và nghiệm thu |

## 2. Số liệu thực tế

- **300 câu**: 285 Dev / 15 Test, giữ nguyên 60 câu ban đầu và 15 Test.
- **240 câu mới**: trích PDF làm bản trả lời đối chiếu, thêm mã Điều (không phải mã chunk).
- **300 bản Ground Truth** hiện là nháp, 0 câu có `review_status` được người duyệt xác nhận và 0 câu có `gold_context_ids_confirmed=true`.
- **34 câu** có `candidate_context_ids` từ bộ chunk *smoke*, **2 câu** có candidate ID chỉ hỗ trợ một phần, **264 câu** chưa ánh xạ chunk. **Cả 300 câu đều có `gold_context_ids=[]`**, không phải độ phủ Gold production.
- L01.pdf trong pipeline mới nhận được **131/133 điều**; hai điều 132–133 có trong bản Luật gốc khác. Không tự điền bằng chứng từ văn bản khác phiên bản.

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

Python 3.13, JSON/JSON Schema Draft 2020-12, `jsonschema`, `unittest`, SHA-256, CSV. Nguồn gồm bộ ZIP 60 câu người dùng cung cấp, registry metadata/Điều đi kèm và trích đoạn từ PDF dự án trong lần mở rộng 240 câu. **Đối với 240 câu mở rộng, trường `answer` chứa **đoạn trích Điều luật tự động** và **chưa phải câu trả lời trực tiếp cho từng câu hỏi**. Validator cuối yêu cầu `answer_kind=reviewed_answer` sau khi sửa đáp án và review có chữ ký. Một đường link `source_url` hoặc đoạn văn bản trích ra không chứng minh trạng thái hiệu lực theo ngày hỏi; việc phê duyệt cần thực hiện thủ công.**

## 4. Validator và đóng băng Test

Trong thư mục chứa ZIP đã giải nén:

```powershell
python -m pip install -r requirements.txt
python scripts/validate_benchmark.py
python -m unittest discover -s tests -v
python scripts/freeze_test.py --verify
python scripts/check_review_coverage.py
```

`validate_benchmark.py` trong chế độ mặc định xác nhận schema, ID, citation, quan hệ Điều–chunk, ngày hiệu lực đã biết, và Test SHA-256. **PASS ở chế độ này là PASS kỹ thuật cấu trúc.**

```powershell
python scripts/validate_benchmark.py --final
```

Lệnh `--final` có chủ ý **FAIL** cho đến khi hoàn tất duyệt pháp lý và ánh xạ mã chunk được index thật. Đừng thay dữ liệu để ép lệnh PASS. Khi đã đủ toàn bộ Ground Truth có nguồn và reviewer và được đồng ý, chạy:

```powershell
python scripts/freeze_gold.py --create
python scripts/freeze_gold.py --verify
```

Câu Test ban đầu được khóa bởi `docs/test_questions_freeze.json`. **Gold Test chưa khóa** — không được tuyên bố đã đóng băng đáp án Test.

## 5. Cần phối hợp với người làm Chunking

Yêu cầu họ xuất **đúng `chunks.jsonl` dùng khi index BM25/Dense**, không phải output smoke thử. Chạy:

```powershell
python scripts/import_chunk_index.py --input path/to/chunks.jsonl
```

Kết quả là `data/reference/production_chunk_index.json` (bản registry chờ review) và `docs/production_chunk_candidates.csv` (ID gợi ý với căn cứ và overlap từ khóa). Công cụ không tự sửa `ground_truth.json`, không giả mạo sự xác nhận `production_verified`.

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
