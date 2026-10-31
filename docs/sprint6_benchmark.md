# SPRINT 6 — BENCHMARK HÔN NHÂN VÀ GIA ĐÌNH (300 CÂU)

**Phiên bản:** `2026-10-30 | milestone-100-gold-verified-test-30-dual-frozen`  
**Nhiệm vụ:** Thiết kế 50–100 câu (mở rộng theo yêu cầu lead lên 300); chuẩn hóa schema; xác minh cấp Khoản 100 câu Gold phân tầng; kiểm định 31 nhóm chunk trùng (B5); duyệt `article_index` cho các Điều của Gold (C5); nâng cấp `sync-clauses` hai chiều có backup (C4); chia lại Dev/Test (270/30) theo nhóm Khoản (`seed=42`) và khóa Freeze kép (D2).

## 1. Danh mục các file chuẩn hóa

| File | Trạng thái | Ghi chú |
| --- | --- | --- |
| `schemas/benchmark_schema.json` | Đã cập nhật | Contract cho câu hỏi và Ground Truth có provenance, `gold_clause_ids`, `split` |
| `data/benchmark/queries_dev.json` | Đã cập nhật | **270 câu** phát triển (70 câu đã duyệt cấp Khoản + 200 câu draft) |
| `data/benchmark/queries_test.json` | Đã cập nhật, **frozen** | **30 câu Test** (100% đã duyệt cấp Khoản), chia theo cụm Khoản (`seed=42`) |
| `data/benchmark/ground_truth.json` | **100 Gold Verified** + 200 Draft | 100 câu `source_checked` / `full_text_checked` / `production_verified` |
| `data/benchmark/reviews/gold_review_100_verified.csv` | Đã tạo | Nhật ký xác minh 100 câu Gold phân tầng kèm tên người duyệt thật |
| `docs/test_questions_freeze.json` | Đã tạo, **frozen** | Manifest khóa SHA-256 trên JSON chuẩn hóa cho 30 câu hỏi Test |
| `docs/test_gold_freeze.json` | Đã tạo, **frozen** | Manifest khóa SHA-256 trên JSON chuẩn hóa cho cả câu hỏi và đáp án Gold của 30 câu Test |
| `test/test_benchmark.py` | Đã nâng cấp và chạy | Kiểm thử schema, sync-clauses 2 chiều, tiêu đề Điều `article_index`, rò rỉ Khoản Dev/Test và Freeze kép |
| `docs/sprint6_benchmark.md` | Tài liệu này | Tiến độ, kỹ thuật, phân bố dữ liệu và nghiệm thu Mốc 29/10 – 30/10 |

## 2. Số liệu thực tế (Cập nhật Mốc 29/10 – 30/10)

- **Tổng 300 câu**: **270 Dev** (70 câu đã duyệt + 200 câu draft) / **30 Test** (30/30 câu đã duyệt đầy đủ).
- **100 câu Gold đã xác minh cấp Khoản (D1 + B5)**:
  - Đã đối chiếu toàn văn cấp Khoản (`evidence_level = "full_text_checked"`, `review_status = "source_checked"`, `mapping_status = "production_verified"`, `gold_context_ids_confirmed = true`, `answer_kind = "reviewed_answer"`).
  - Gồm 36 câu từ bộ 60 câu gốc (`HN_001` – `HN_036`, bao gồm trọn 11 câu nền tảng `HN_001` – `HN_011`) và 64 câu từ bộ mở rộng (`HN_061` – `HN_300`, đã biên soạn lại câu trả lời pháp lý trực tiếp thay cho đoạn trích PDF thô).
  - Quy trình duyệt bởi thành viên thật của dự án: **Lê Tuấn Thành** (Dev 3) kiểm nháp 25 câu, **Nguyễn Đình Thắng** (Dev 5) kiểm nháp 25 câu, **Nguyễn Quốc Hòa** (Dev 1) trực tiếp kiểm tra và ký duyệt toàn bộ 100 câu (`verified_at = "2026-10-29"`).
- **16 câu thuộc 31 nhóm chunk trùng nội dung giữa văn bản cũ và mới (B5)**:
  - Đã khảo sát 31 nhóm (62 chunks) trùng nội dung văn bản giữa Luật HNGĐ 2000 (`22/2000/QH10`) và Luật HNGĐ 2014 (`52/2014/QH13`) hoặc giữa NĐ `10/2015/NĐ-CP` và NĐ `207/2025/NĐ-CP`.
  - Đưa 16 câu rơi vào các cặp trùng này vào tập 100 câu đã duyệt (11 câu ở Dev, 5 câu ở Test) và chỉ gắn `gold_clause_ids` / `gold_context_ids` của văn bản đang có hiệu lực tại `as_of_date`.
- **200 câu Draft còn lại**: 176 câu có `candidate_context_ids` (`production_candidate_unverified`) và 24 câu `not_mapped` (`HN_037` – `HN_060`).
- **Đồng bộ `article_index.json` (C5)**:
  - Chuẩn hóa tiêu đề Điều (`article_title`) cho toàn bộ **799 bản ghi** khớp 100% với `parser/parsed_jsons/*.json`.
  - Duyệt và cập nhật `verification_status = "source_checked"` cho toàn bộ **88 Điều** được sử dụng bởi 100 câu Gold đã duyệt.

### Phân bố 100 câu đã duyệt và Tập Test (30 câu) vs Dev đã duyệt (70 câu)

Nguyên tắc chia tập **D2 (Clause-Group Stratified Split, `seed = 42`)**:
1. Gom 100 câu đã duyệt thành **72 cụm Khoản (Clause Clusters)** dựa trên đồ thị liên thông của `gold_clause_ids` (và cặp câu hỏi gần trùng cùng Điều).
2. Phân bổ nguyên cụm vào Dev (70 câu đã duyệt + 200 câu draft = 270 câu) hoặc Test (30 câu) với `seed = 42` sao cho **số Khoản (`gold_clause_ids`) bị trùng giữa Test và Dev đã duyệt bằng 0 (`0 overlap`)**.

| Chiều phân tầng | Tập 100 câu đã duyệt | Dev đã duyệt (70 câu) | Test (30 câu - 30%) | Tổng bộ 300 câu |
| --- | ---: | ---: | ---: | ---: |
| **Theo `test_type`** | | | | |
| `current_law` | 81 | 57 | 24 | 219 |
| `partially_expired` | 17 | 12 | 5 | 59 |
| `outdated_law_trap` | 2 | 1 | 1 | 16 |
| `historical_law` | 0 *(24 câu ngoài corpus)* | 0 | 0 | 6 |
| **Theo `question_type`** | | | | |
| `fact` | 43 | 30 | 13 | 90 |
| `situation` | 43 | 30 | 13 | 185 |
| `multi_hop` | 14 | 10 | 4 | 25 |
| **Theo `difficulty`** | | | | |
| `easy` | 26 | 18 | 8 | 51 |
| `medium` | 51 | 36 | 15 | 186 |
| `hard` | 23 | 16 | 7 | 63 |
| **Theo `category`** | | | | |
| `ket_hon` | 14 | 10 | 4 | 39 |
| `tai_san` | 14 | 11 | 3 | 39 |
| `ly_hon` | 12 | 7 | 5 | 25 |
| `con_cai` | 11 | 8 | 3 | 68 |
| `vo_chong` | 10 | 7 | 3 | 38 |
| `cap_duong` | 10 | 7 | 3 | 22 |
| `nguyen_tac_quy_dinh` | 10 | 7 | 3 | 15 |
| `mang_thai_ho` | 10 | 7 | 3 | 24 |
| `hieu_luc` | 3 | 2 | 1 | 23 |
| `yeu_to_nuoc_ngoai` | 3 | 2 | 1 | 4 |
| `thu_tuc` | 3 | 2 | 1 | 3 |
| **Đặc tính kiểm định** | | | | |
| Câu thuộc cặp trùng **B5** | 16 | 11 | 5 | — |
| Nguồn câu gốc (`HN_001`–`HN_060`) | 36 | 25 | 11 | 60 |
| Nguồn mở rộng (`HN_061`–`HN_300`) | 64 | 45 | 19 | 240 |

## 3. Công nghệ, nguồn và luồng dữ liệu

Python 3.13, JSON Schema Draft 2020-12, `unittest` / `pytest`. Toàn bộ dữ liệu nằm trong `data/benchmark/`, `data/reference/` và `schemas/benchmark_schema.json`.

## 4. Hướng dẫn chạy và nghiệm thu kỹ thuật

1. Đồng bộ hai chiều `gold_clause_ids` ↔ `gold_context_ids` (tự động tạo backup trước khi ghi):
   ```bash
   python scripts/prepare_production_benchmark.py --sync-clauses
   ```
2. Kiểm tra khóa Freeze kép (Câu hỏi Test + Gold Test):
   ```bash
   python scripts/freeze_test.py --verify
   python scripts/freeze_gold.py --verify
   ```
3. Chạy validator:
   ```bash
   python scripts/validate_benchmark.py
   ```
4. Chạy test suite:
   ```bash
   python -m pytest test/test_benchmark.py tests/test_benchmark.py -v
   ```

## 5. Bảng Ánh xạ Tên trường (Field Name Mapping Contract)

| Khái niệm nghiệp vụ | Tên trường chính thức (`schemas/benchmark_schema.json`) | Tên trường trong đầu ra Retrieval / Evaluation | Mô tả & Ràng buộc |
| :--- | :--- | :--- | :--- |
| **Mã câu hỏi** | `id` | `query_id` | Định danh duy nhất của câu hỏi (`HN_001` .. `HN_300`). |
| **Phân loại chủ đề** | `category` | `category` (alias `topic`) | Nhóm chủ đề câu hỏi (`ket_hon`, `ly_hon`, `tai_san`, `con_cai`, v.v.). |
| **Đáp án chuẩn** | `answer` | `expected_answer` | Nội dung câu trả lời chuẩn tham chiếu đã duyệt (`reviewed_answer`) hoặc nháp. |
| **Tập phân chia** | `split` | `split` | Thuộc tập phát triển (`"dev"`, 270 câu) hoặc tập kiểm thử (`"test"`, 30 câu). |
| **Thời điểm câu hỏi** | `as_of_date` | `as_of_date` | Mốc thời gian áp dụng luật (`YYYY-MM-DD`). |

## 6. Nhật ký đóng băng Test và cập nhật ID

| Ngày | Commit | Thay đổi | SHA-256 Test |
| --- | --- | --- | --- |
| 16/10/2026 | b230265 | Đóng băng 15 câu Test lần đầu. | `0b4b3a2f75a0…cdbdf` |
| 22/10/2026 | ee755a5 | Thêm trường `split` vào 15/15 câu Test. | `6942c3353a62…fb889` |
| 25/10/2026 | 146a6c9 | Sinh lại `production_chunk_index.json` từ corpus. | `6942c3353a62…fb889` |
| 27/10/2026 | 074eb94 | Hợp nhất candidate từ `gold_id_proposals_300.json` vào `ground_truth.json`. | `6942c3353a62…fb889` |
| 30/10/2026 | data/gold | Duyệt cấp Khoản 100 câu Gold phân tầng (D1+B5+C5+C4); chia lại Dev (270) / Test (30) theo cụm Khoản (`seed=42`, 0 rò rỉ Khoản) và khóa Freeze kép cả `test_questions_freeze.json` lẫn `test_gold_freeze.json` trên JSON chuẩn hóa (D2). | Questions: `54e3d267a9aa…53787`<br>Gold: `ebed2311e41f…72fed` |
