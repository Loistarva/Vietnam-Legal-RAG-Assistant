# SPRINT 6 — BENCHMARK HÔN NHÂN VÀ GIA ĐÌNH (300 CÂU)

**Phiên bản:** `2026-10-31 | gold-105-verified-test-30-refrozen`  
**Nhiệm vụ:** Thiết kế 50–100 câu (mở rộng theo yêu cầu lead lên 300); chuẩn hóa schema; xác minh cấp Khoản các câu Gold phân tầng; câu cho các nhóm chunk trùng (B5); duyệt `article_index` cho các Điều của Gold (C5); `sync-clauses` hai chiều có backup (C4); chia lại Dev/Test (270/30) theo nhóm Khoản và khóa Freeze kép (D2).

## 1. Danh mục các file chuẩn hóa

| File | Trạng thái | Ghi chú |
| --- | --- | --- |
| `schemas/benchmark_schema.json` | Đã cập nhật | Contract cho câu hỏi và Ground Truth có provenance, `gold_clause_ids`, `split` |
| `data/benchmark/queries_dev.json` | Đã cập nhật | **270 câu** phát triển (75 câu đã duyệt cấp Khoản + 195 câu draft) |
| `data/benchmark/queries_test.json` | Đã cập nhật, **frozen** | **30 câu Test** (100% đã duyệt cấp Khoản) |
| `data/benchmark/ground_truth.json` | **105 Gold Verified** + 195 Draft | 105 câu `source_checked` / `full_text_checked` / `production_verified` |
| `data/benchmark/reviews/gold_review_verified.csv` | Đã tạo | Nhật ký xác minh 105 câu Gold kèm tên người duyệt |
| `docs/test_questions_freeze.json` | **frozen** | Manifest khóa SHA-256 trên JSON chuẩn hóa cho 30 câu hỏi Test |
| `docs/test_gold_freeze.json` | **frozen** | Manifest khóa SHA-256 trên JSON chuẩn hóa cho cả câu hỏi và đáp án Gold của 30 câu Test |
| `test/test_benchmark.py` | Đã nâng cấp và chạy | Kiểm thử schema, sync-clauses 2 chiều, tiêu đề Điều `article_index`, hiệu lực của gold tại `as_of_date`, rò rỉ Khoản Dev/Test và Freeze kép |
| `docs/sprint6_benchmark.md` | Tài liệu này | Tiến độ, phân bố dữ liệu và nghiệm thu |

## 2. Số liệu thực tế (31/10/2026)

- **Tổng 300 câu**: **270 Dev** (75 câu đã duyệt + 195 câu draft) / **30 Test** (30/30 câu đã duyệt).
- **105 câu Gold đã xác minh cấp Khoản (D1)**: `evidence_level = "full_text_checked"`, `review_status = "source_checked"`, `mapping_status = "production_verified"`, `gold_context_ids_confirmed = true`, `answer_kind = "reviewed_answer"`.
  - 41 câu từ bộ 60 câu gốc và 64 câu từ bộ mở rộng (đáp án viết lại thành câu trả lời trực tiếp).
  - Người duyệt (`verified_by`): Nguyễn Quốc Hòa (Dev 1) ký 92 câu ngày 29/10, trong đó 20 câu do Lê Tuấn Thành (Dev 3) và 24 câu do Nguyễn Đình Thắng (Dev 5) kiểm nháp; Nguyễn Đình Thắng ký 13 câu soạn lại ngày 31/10 (dưới đây).
- **Sửa ngày 31/10, sau khi kiểm PR data/gold:**
  - 8 câu (HN_208, HN_210, HN_215, HN_219, HN_220, HN_221, HN_230, HN_231) từng lấy gold từ Điều 19, 21, 26, 30, 31, 32, 41, 42 Nghị định 126/2014/NĐ-CP. Các Điều 19–50 đã bị bãi bỏ từ 01/01/2016 theo điểm đ khoản 2 Điều 45 Nghị định 123/2015/NĐ-CP. Gold chuyển sang khoản 1, khoản 2 Điều 45 Nghị định 123/2015/NĐ-CP; đáp án nêu Điều đã bị bãi bỏ; chunk Nghị định 126/2014 chuyển vào `outdated_context_ids`. Chunk của Nghị định 126/2014 không có `effective_to`, nên bộ lọc theo thời điểm không loại được các Điều này; `test_verified_gold_in_force_at_as_of_date` chặn gold rơi vào Điều 19–50.
  - 5 câu `historical_law` được duyệt: HN_051 (2010-06-01, khoản 5 Điều 10 Luật 22/2000), HN_052 (2012-03-01, Điều 109 Luật 22/2000), HN_054 (2024-06-01, Điều 24 Nghị định 10/2015), HN_055 (2015-12-01, khoản 1 Điều 17 Thông tư 02a/2015), HN_056 (2017-03-01, khoản 1, 2 Điều 31 Thông tư 15/2015). Gold là chunk có hiệu lực tại `as_of_date`. HN_053 (“Luật 52/2014 đã có hiệu lực chưa” tại 2014-07-01) chưa duyệt: căn cứ duy nhất là Điều 132 Luật 52/2014, chưa có hiệu lực tại ngày đó nên bị bộ lọc loại.
  - `temporal_note` của các câu đã duyệt ghi việc kiểm `effective_from`/`effective_to` của chunk gold theo `chunks.jsonl`.
- **Cặp chunk trùng (B5)**: corpus có 31 nhóm (62 chunk) trùng nội dung giữa văn bản cũ và mới: 16 nhóm Thông tư 04/2020–Thông tư 15/2015, 11 nhóm Luật 22/2000–Luật 52/2014, 2 nhóm Nghị định 32/2002–Nghị định 77/2001, 1 nhóm Nghị định 10/2015–Nghị định 207/2025, 1 nhóm Nghị định 126/2014–Nghị định 68/2002. 15 câu đã duyệt có chunk gold trùng với chunk Hết hiệu lực của văn bản cũ; chunk cũ ghi vào `outdated_context_ids`. Các câu này đều hỏi tại 2026-10-15; chưa có câu cho cặp Thông tư 04/2020–Thông tư 15/2015.
- **195 câu Draft còn lại**: 176 câu có `candidate_context_ids` (`production_candidate_unverified`) và 19 câu `not_mapped`.
- **`article_index.json` (C5)**: `article_title` của 799 dòng lấy theo `article_title` của `parser/parsed_jsons/*.json` (“Điều N. Tiêu đề”, hoặc “Điều N” khi Điều không có tiêu đề). 86 Điều được gold đã duyệt dùng tới có `verification_status = "source_checked"`; các dòng còn lại để sau 2/11.

### Phân bố 105 câu đã duyệt, Dev đã duyệt (75 câu) và Test (30 câu)

Nguyên tắc chia (D2): Test chỉ gồm câu đã duyệt; câu dùng chung Khoản gold hoặc gần trùng câu hỏi nằm cùng một phía; phân tầng theo `test_type`, `question_type`, `difficulty`. Bản chia 30/10 không kèm script; ngày 31/10, 5 câu chuyển từ Test sang Dev (HN_215, HN_219, HN_230, HN_231 vì cùng gold Điều 45 Nghị định 123/2015 với 4 câu Dev; HN_169 vì gần trùng HN_168) và 5 câu Dev đã duyệt cùng tầng, không dùng chung Khoản, chuyển sang Test (HN_081, HN_194, HN_198, HN_240, HN_246). `test_no_clause_leakage_between_dev_and_test` kiểm 0 Khoản gold chung giữa Dev và Test. Câu Dev draft chưa có gold; khi duyệt thêm, câu có Khoản trùng với Test sẽ làm test này fail.

| Chiều phân tầng | Tập 105 câu đã duyệt | Dev đã duyệt (75 câu) | Test (30 câu) | Tổng bộ 300 câu |
| --- | ---: | ---: | ---: | ---: |
| **Theo `test_type`** | | | | |
| `current_law` | 81 | 57 | 24 | 219 |
| `partially_expired` | 17 | 12 | 5 | 59 |
| `outdated_law_trap` | 2 | 1 | 1 | 16 |
| `historical_law` | 5 | 5 | 0 | 6 |
| **Theo `question_type`** | | | | |
| `fact` | 43 | 29 | 14 | 90 |
| `situation` | 48 | 36 | 12 | 185 |
| `multi_hop` | 14 | 10 | 4 | 25 |
| **Theo `difficulty`** | | | | |
| `easy` | 26 | 18 | 8 | 30 |
| `medium` | 56 | 43 | 13 | 212 |
| `hard` | 23 | 14 | 9 | 58 |
| **Theo `category`** | | | | |
| `ket_hon` | 15 | 12 | 3 | 40 |
| `tai_san` | 14 | 11 | 3 | 58 |
| `ly_hon` | 12 | 9 | 3 | 38 |
| `con_cai` | 11 | 9 | 2 | 38 |
| `vo_chong` | 10 | 5 | 5 | 15 |
| `cap_duong` | 10 | 8 | 2 | 21 |
| `nguyen_tac_quy_dinh` | 10 | 5 | 5 | 27 |
| `mang_thai_ho` | 11 | 8 | 3 | 26 |
| `hieu_luc` | 6 | 5 | 1 | 25 |
| `yeu_to_nuoc_ngoai` | 3 | 1 | 2 | 6 |
| `thu_tuc` | 3 | 2 | 1 | 6 |
| **Đặc tính kiểm định** | | | | |
| Câu thuộc cặp trùng **B5** | 15 | 11 | 4 | — |
| Nguồn câu gốc (`HN_001`–`HN_060`) | 41 | 30 | 11 | 60 |
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
   `--create` từ chối khi manifest đã có; chỉ đóng băng lại với `--create --force` và ghi lý do vào mục 6.
3. Chạy validator:
   ```bash
   python scripts/validate_benchmark.py
   ```
4. Chạy test suite:
   ```bash
   python -m pytest test/test_benchmark.py -v
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
| 30/10/2026 | 0890ac9 | Duyệt cấp Khoản 100 câu Gold; chia lại Dev (270) / Test (30) theo cụm Khoản; khóa cả `test_questions_freeze.json` và `test_gold_freeze.json` trên JSON chuẩn hóa. | Questions: `54e3d267a9aa…53787`<br>Gold: `ebed2311e41f…72fed` |
| 31/10/2026 | fix/gold-followup | Test chưa chạy lần nào. Sửa gold 4 câu Test dùng Điều đã bãi bỏ của Nghị định 126/2014 và đưa cả 8 câu cùng gold Điều 45 Nghị định 123/2015 về Dev; HN_169 về Dev (gần trùng HN_168); thay bằng HN_081, HN_194, HN_198, HN_240, HN_246; ghi `temporal_note`, `outdated_context_ids` cho câu đã duyệt. Đóng băng lại bằng `--create --force`. | Questions: `d3eb903c5e65…2f517`<br>Gold: `d3d083e3372e…f80c5` |
| 31/10/2026 | fix/gold-followup | Test chưa chạy lần nào. Sửa anchor `dieu_N` trong `source_url` của 56 citation Nghị định 126/2014 (lệch một Điều so với số Điều được dẫn), trong đó có 5 câu Test HN_193, HN_194, HN_198, HN_240, HN_246; câu hỏi Test không đổi. Đóng băng lại gold bằng `freeze_gold.py --create --force`. | Questions: `d3eb903c5e65…2f517`<br>Gold: `f3b4e856a6fd…c1c87` |
