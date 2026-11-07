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
  - Người duyệt (`verified_by`): Nguyễn Thị Quỳnh Hoa (Dev 1) ký 92 câu ngày 29/10, trong đó 20 câu do Lê Tuấn Thành (Dev 3) và 24 câu do Nguyễn Đình Thắng (Dev 5) kiểm nháp (Nguyễn Đình Thắng xác nhận ngày 02/11, ghi ở `review_notes` của `gold_review_verified.csv`; đáp án HN_156, HN_181, HN_246, HN_256, HN_268, HN_298 sửa cho khớp chunk gold); Nguyễn Đình Thắng ký 13 câu soạn lại ngày 31/10 (dưới đây).
- **Xác nhận kiểm nháp Dev 3 — Issue D1 (Loistarva tại PR #27):** đã xác nhận đối chiếu toàn văn cấp Khoản với văn bản nguồn và `data/chunking_output/chunks.jsonl` cho **20/20 câu** do Lê Tuấn Thành kiểm nháp, Nguyễn Thị Quỳnh Hoa duyệt. Gồm **15 Dev**: HN_061, HN_062, HN_130, HN_169, HN_176, HN_177, HN_187, HN_271, HN_284, HN_288, HN_290, HN_294, HN_296, HN_299, HN_300; **5 Test**: HN_066, HN_128, HN_173, HN_283, HN_292. `gold_article_ids`, `gold_clause_ids`, `gold_context_ids` của cả 20 câu chính xác, chứa đủ nội dung trả lời và có hiệu lực tại `as_of_date = 2026-10-15`, gồm 8 câu thuộc cặp trùng B5 (HN_062, HN_169, HN_173, HN_176, HN_177, HN_187, HN_299, HN_300). Loistarva đồng ý bổ sung đáp án HN_130 tại `cad4b22` và chuẩn hóa tên người duyệt tại `7f4e8a2`. Xác nhận đã ghi trong `review_notes` của 20 dòng CSV; lần bổ sung này chỉ cập nhật nhật ký và tài liệu, giữ nguyên dữ liệu và hash Test.
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
| 02/11/2026 | fix/d1-draft-check | Test chưa chạy lần nào. Bỏ chữ lặp “bảo vệ bảo vệ” trong câu hỏi HN_181 (lỗi đánh máy, phát hiện khi xác nhận kiểm nháp D1); gold, đáp án và danh sách ID Test không đổi. Đóng băng lại cả hai manifest bằng `--create --force` (manifest gold băm cả câu hỏi Test). | Questions: `9dd472f56972…c3876`<br>Gold: `d3ea86d491d0…12f08` |
| 02/11/2026 | fix/d1-draft-check | Test chưa chạy lần nào. Sửa anchor `dieu_N` trong `source_url` của 12 citation Nghị quyết 01/2024/NQ-HĐTP (HN_264–HN_275, lệch +3 so với số Điều được dẫn; đã mở trên trình duyệt: `anchor=dieu_5` nhảy tới Điều 5), trong đó có câu Test HN_268; sửa cùng anchor của 12 Điều ND03 trong `data/reference/article_index.json` và `data/normalized_metadata.json`. Câu hỏi Test không đổi. Đóng băng lại gold bằng `freeze_gold.py --create --force`. | Questions: `9dd472f56972…c3876`<br>Gold: `5a6bd4117f22…b5d01` |
| 02/11/2026 | fix/d1-draft-check | Test chưa chạy lần nào. Đáp án HN_081 bỏ câu suy diễn “mọi hành vi xúc phạm … đều vi phạm nghĩa vụ nhân thân”, không có trong Điều 21 Luật 52/2014/QH13 (rà lại đáp án 105 câu đã duyệt với chunk gold); gold và câu hỏi Test không đổi. Đóng băng lại gold bằng `freeze_gold.py --create --force`. | Questions: `9dd472f56972…c3876`<br>Gold: `09941456ee39…c519f` |
| 02/11/2026 | fix/d1-draft-check | Test chưa chạy lần nào. Sửa tên người duyệt trong `verified_by` (ghi sai “Nguyễn Quốc Hòa”) thành “Nguyễn Thị Quỳnh Hoa” ở 92 câu đã duyệt, gồm 30/30 câu Test, cùng `gold_review_verified.csv` và mục 2 của tài liệu này; nội dung câu hỏi, gold, đáp án không đổi. Đóng băng lại gold bằng `freeze_gold.py --create --force`. | Questions: `9dd472f56972…c3876`<br>Gold: `1fa2e53d1389…4f986` |
| 02/11/2026 | fix/d1-draft-check | Test chưa chạy lần nào. Khi xác nhận kiểm nháp D1, sửa đáp án 4 câu Test cho khớp chunk gold: HN_156 (khoản 2 Điều 96 Luật 52/2014/QH13: xác nhận của cơ sở y tế là yêu cầu thêm khi lập cùng thỏa thuận với cơ sở y tế, không phải “hoặc” thay công chứng), HN_181 (khoản 3 Điều 121: thêm “pháp luật và tập quán quốc tế”), HN_246 (khoản 2, khoản 3 Điều 57 Nghị định 126/2014/NĐ-CP: thời hạn 30 ngày theo từng trường hợp), HN_268 (Điều 5 Nghị quyết 01/2024/NQ-HĐTP: bỏ ý “không có khả năng thanh toán phần chênh lệch” chỉ có ở Ví dụ 2). Gold và câu hỏi Test không đổi. Đóng băng lại gold bằng `freeze_gold.py --create --force`. | Questions: `9dd472f56972…c3876`<br>Gold: `59a9cdf02f76…68811` |
| 07/11/2026 | fix/metrics | Chạy Test lần đầu cho BM25, Dense, Hybrid, Hybrid + Reranker bằng `scripts/run_final_test.py` (d76c6f8, kết quả commit ở 133b257), trên câu hỏi và gold Test trước PR #27. Sau khi gộp testing (PR #27 sửa câu HN_181 và đáp án 4 câu Test), chạy lại một lần trên 25fadec (kết quả commit ở c19f50f) với cùng config và code: chỉ danh sách chunk của HN_181 đổi ở BM25, Dense, Hybrid + Reranker, metric từng câu không đổi. Không chỉnh cấu hình sau khi xem kết quả Test. Manifest không đổi. | Lần 1: Questions `d3eb903c5e65…2f517`, Gold `f3b4e856a6fd…c1c87`<br>Lần 2: Questions `9dd472f56972…c3876`, Gold `59a9cdf02f76…68811` |
| 07/11/2026 | fix/leftover-after-0211 | Chạy Test lần 3 cho 4 phương pháp bằng `scripts/run_final_test.py` (b90d886, kết quả commit ở d13fa01), vì corpus đổi: 131 chunk có `effective_to` cấp Điều/Khoản (D1), nên index BM25 và Qdrant dựng lại. Trên corpus cũ, top-10 Test của BM25, Dense, Hybrid + Reranker có 4, 2, 6 chunk đã bị bãi bỏ. Câu hỏi, gold Test, cấu hình retrieval và reranker không đổi (chỉ thêm một dòng chú thích về model dense trong `retrieval/config.yaml`); `docs/test_run_config_freeze.json` cập nhật hash corpus và hash config trước khi chạy (1c5cad7, b604c4f). Hash corpus từ nay tính sau khi đổi CRLF thành LF ở cả phía retrieval (b991328). Recall@10 của cả bốn phương pháp không đổi; các metric khác của Hybrid và Hybrid + Reranker đổi từ 0,011 trở xuống. Không chỉnh cấu hình sau khi xem kết quả Test. | Questions `9dd472f56972…c3876`, Gold `59a9cdf02f76…68811` (không đổi) |

## 7. Quyết định định nghĩa Recall

Với mỗi câu hỏi có `gold_context_ids` đã xác nhận, Recall@K được tính:

```text
Recall@K = hits / len(gold)
hits = số gold ID phân biệt xuất hiện trong top-K kết quả
gold = tập gold_context_ids đã xác nhận của câu hỏi
```

Điểm Recall@K của benchmark là trung bình macro điểm từng câu hỏi đủ điều kiện. Cách này khác mục 14.4 của kế hoạch, vốn dùng **hit-based**: mỗi câu chỉ nhận 1 nếu top-K có ít nhất một gold ID, và 0 nếu không có. Hit-based đo tỷ lệ câu có tìm được ít nhất một kết quả phù hợp; Recall ở đây đo phần gold được truy hồi. Vì một câu có thể có nhiều gold context, Recall phân biệt truy hồi một phần với truy hồi đầy đủ, thay vì cho hai trường hợp cùng điểm như hit-based. Lý do chọn là cần phản ánh độ bao phủ các căn cứ gold của câu trả lời.

Khi tạo `baseline_report`, phải ghi cùng định nghĩa và cách tổng hợp này; không gọi chỉ số hit-based là Recall. Có thể báo cáo hit rate riêng nếu cần đo tỷ lệ câu có ít nhất một kết quả phù hợp.
