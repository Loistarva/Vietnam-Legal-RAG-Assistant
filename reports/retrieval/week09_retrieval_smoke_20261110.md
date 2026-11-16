# Báo cáo kiểm thử nhanh Retrieval Tuần 09

## Môi trường và cấu hình

- Ngày chạy theo log terminal: **2026-11-10**.
- Elasticsearch: `http://127.0.0.1:9200`; index theo config mặc định: `bm25-e6-verified-20261101`.
- Qdrant Server: `http://127.0.0.1:6333`; collection theo config mặc định: `vietnam_legal_chunks`.
- Mô hình Dense: `BAAI/bge-m3`, số chiều 1024.
- Bộ xếp hạng lại: `BAAI/bge-reranker-v2-m3`, backend `cross_encoder` (CPU/float32 theo log).
- Truy xuất: Top-50; RRF K=60; Cross-Encoder trả Top-5.
- Corpus SHA-256: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.
- Retrieval config SHA-256 chuẩn hóa: `08df4180c8c47fe86592bb2a41d8b0e5f88cc0194160a7990990b3c139de8179`.
- Rerank config SHA-256 chuẩn hóa: `b99cf7319ec93eeb49c241904eb89b5e3e6b41fbbc05b56e63347b25693c6471`.
- Git commit không được ghi trong log/JSON runtime đã gửi.
- Ba JSON đầu ra giữ hậu tố `20261109` theo tên lệnh đã chạy, dù log là 10/11/2026; nội dung runtime ghi đúng ngày chạy.

## Tổng hợp kết quả

| Trường hợp | `as_of_date` | Nguồn ngày | Số kết quả | Độ trễ (ms) | Kiểm tra hiệu lực |
|---|---|---|---:|---:|---|
| Hiện tại | 2026-11-10 | `ui` | 5 | 152105.2 | ĐẠT: 5/5 kết quả nằm trong khoảng hiệu lực |
| Lịch sử | 2010-01-01 | `question` | 5 | 115498.5 | ĐẠT: 5/5 kết quả nằm trong khoảng hiệu lực |
| Đã hết hiệu lực | 2026-10-15 | `question` | 5 | 111834.5 | ĐẠT: kết quả đầu là văn bản thay thế nêu việc bãi bỏ Nghị định 10/2015; không có kết quả mang document ID của Nghị định 10/2015 |

## Truy xuất hiện tại

- Query ID: `D47_CURRENT`.
- Query: “Điều kiện kết hôn hiện nay được quy định thế nào?”
- `as_of_date`: `2026-11-10` (nguồn `ui`).
- Backend thực tế: `bm25-e6-verified-20261101` + `vietnam_legal_chunks`.
- Corpus SHA trong runtime config: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.

| Rank | Score | Retrieval rank | Document | Article | Clause |
|---:|---:|---:|---|---|---|
| 1 | 0.956597 | 1 | `l_52_2014_qh13` | `l_52_2014_qh13_art_8` | `l_52_2014_qh13_art_8_clause_1` |
| 2 | 0.817256 | 9 | `ttlt_01_2016_ttlt_tandtc` | `ttlt_01_2016_ttlt_tandtc_art_2` | `ttlt_01_2016_ttlt_tandtc_art_2_clause_5` |
| 3 | 0.759563 | 3 | `l_52_2014_qh13` | `l_52_2014_qh13_art_3` | `l_52_2014_qh13_art_3_clause_5` |
| 4 | 0.669320 | 34 | `nd_123_2015_nd_cp` | `nd_123_2015_nd_cp_art_44` | `nd_123_2015_nd_cp_art_44_clause_2` |
| 5 | 0.609552 | 15 | `l_52_2014_qh13` | `l_52_2014_qh13_art_3` | `l_52_2014_qh13_art_3_clause_12` |

Văn bản ứng viên hạng 1, tạo bằng `reranking.reranker.candidate_text()` ở chế độ `document_breadcrumb_chunk_text`:

```text
Luật Hôn nhân và gia đình 2014 (52/2014/QH13)
Chương II KẾT HÔN > Điều 8. Điều kiện kết hôn > Khoản 1
1. Nam, nữ kết hôn với nhau phải tuân theo các điều kiện sau đây: a) Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên; b) Việc kết hôn do nam và nữ tự nguyện quyết định; c) Không bị mất năng lực hành vi dân sự; d) Việc kết hôn không thuộc một trong các trường hợp cấm kết hôn theo quy định tại các điểm a, b, c và d khoản 2 Điều 5 của Luật này.
```

## Truy xuất theo thời điểm lịch sử

- Query ID: `D47_HISTORICAL`.
- Query: “Tại thời điểm ngày 01 tháng 01 năm 2010, điều kiện kết hôn được quy định thế nào?”
- `as_of_date`: `2010-01-01` (nguồn `question`).
- Backend thực tế: `bm25-e6-verified-20261101` + `vietnam_legal_chunks`.
- Corpus SHA trong runtime config: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.

| Rank | Score | Retrieval rank | Document | Article | Clause |
|---:|---:|---:|---|---|---|
| 1 | 0.536192 | 22 | `l_22_2000_qh10` | `l_22_2000_qh10_art_9` | `l_22_2000_qh10_art_9_clause_1` |
| 2 | 0.470137 | 2 | `nd_77_2001_nd_cp` | `nd_77_2001_nd_cp_art_2` | `nd_77_2001_nd_cp_art_2_clause_2` |
| 3 | 0.417470 | 13 | `l_22_2000_qh10` | `l_22_2000_qh10_art_9` | `l_22_2000_qh10_art_9_clause_2` |
| 4 | 0.403068 | 6 | `nd_68_2002_nd_cp` | `nd_68_2002_nd_cp_art_10` | `nd_68_2002_nd_cp_art_10_clause_1` |
| 5 | 0.336455 | 42 | `l_22_2000_qh10` | `l_22_2000_qh10_art_8` | `l_22_2000_qh10_art_8_clause_2` |

Văn bản ứng viên hạng 1, tạo bằng hàm hỗ trợ của bộ xếp hạng lại:

```text
Luật Hôn nhân và gia đình 2000 (22/2000/QH10)
Chương 2 KẾT HÔN > Điều 9. Điều kiện kết hôn > Khoản 1
1. Nam từ hai mươi tuổi trở lên, nữ từ mười tám tuổi trở lên;
```

## Truy xuất văn bản đã hết hiệu lực

- Query ID: `D47_OUTDATED`.
- Query: “Tại ngày 15 tháng 10 năm 2026, Nghị định 10/2015/NĐ-CP còn hiệu lực không?”
- `as_of_date`: `2026-10-15` (nguồn `question`).
- Backend thực tế: `bm25-e6-verified-20261101` + `vietnam_legal_chunks`.
- Corpus SHA trong runtime config: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.

| Rank | Score | Retrieval rank | Document | Article | Clause |
|---:|---:|---:|---|---|---|
| 1 | 0.985368 | 6 | `nd_207_2025_nd_cp` | `nd_207_2025_nd_cp_art_15` | `nd_207_2025_nd_cp_art_15_clause_2` |
| 2 | 0.810907 | 9 | `tt_38_2025_tt_byt` | `tt_38_2025_tt_byt_art_7` | `tt_38_2025_tt_byt_art_7_clause_2` |
| 3 | 0.755450 | 2 | `nd_207_2025_nd_cp` | `nd_207_2025_nd_cp_art_15` | `nd_207_2025_nd_cp_art_15_clause_1` |
| 4 | 0.307000 | 3 | `nd_18_2026_nd_cp` | `nd_18_2026_nd_cp_art_17` | `nd_18_2026_nd_cp_art_17_clause_1` |
| 5 | 0.300834 | 1 | `nd_07_2025_nd_cp` | `nd_07_2025_nd_cp_art_2` | `nd_07_2025_nd_cp_art_2_clause_10` |

Văn bản ứng viên hạng 1, tạo bằng hàm hỗ trợ của bộ xếp hạng lại:

```text
Nghị định 207/2025/NĐ-CP: Quy định về sinh con bằng kỹ thuật hỗ trợ sinh sản và điều kiện mang thai hộ vì mục đích nhân đạo
Chương IV ĐIỀU KHOẢN THI HÀNH > Điều 15. Hiệu lực thi hành > Khoản 2 > Điểm a-c
2. Các quy định và văn bản sau đây hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành: a) Nghị định số 10/2015/NĐ-CP ngày 28 tháng 01 năm 2015 của Chính phủ quy định về sinh con bằng kỹ thuật thụ tinh trong ống nghiệm và điều kiện mang thai hộ vì mục đích nhân đạo; b) Nghị định số 98/2016/NĐ-CP ngày 01 tháng 7 năm 2016 của Chính phủ sửa đổi bổ sung một số điều của Nghị định số 10/2015/NĐ-CP ngày 28 tháng 01 năm 2015 của Chính phủ quy định về sinh con bằng kỹ thuật thụ tinh trong ống nghiệm và điều kiện mang thai hộ vì mục đích nhân đạo; c) Khoản 2 Điều 19 Nghị định số 155/2018/NĐ-CP ngày 12 tháng 11 năm 2018 của Chính phủ sửa đổi bổ sung một số quy định liên quan đến điều kiện đầu tư kinh doanh thuộc phạm vi quản lý nhà nước của Bộ Y tế.
```

## Kết luận và giới hạn

- Cả ba lượt truy xuất hoàn tất; log cho thấy Elasticsearch và Qdrant nhận yêu cầu thành công, Cross-Encoder chấm 50 ứng viên và trả Top-5.
- JSON xác nhận dùng index/collection mặc định trong config và corpus SHA mới; không truyền override tên index hoặc collection.
- Các kết quả trả về phù hợp mốc hiệu lực của từng truy vấn. Với trường hợp văn bản hết hiệu lực, Top-1 là điều khoản của Nghị định 207/2025 nêu việc bãi bỏ Nghị định 10/2015; không có kết quả nào mang số hiệu văn bản `10/2015/NĐ-CP`.
- Đây là kiểm thử nhanh Retrieval, không thay thế đánh giá chất lượng pháp lý hoặc benchmark đầy đủ.
- Đường dẫn trong JSON runtime đã được chuẩn hóa thành đường dẫn tương đối trong repository.
- Git commit không có trong bằng chứng runtime. Bổ sung SHA khi chạy từ commit sạch nếu cần truy xuất nguồn gốc bản phát hành.
- Kiểm thử nhanh runtime D4.7: **3/3 trường hợp hoàn tất và đạt kiểm tra**. C1 dọn dẹp và provenance commit vẫn chưa được nghiệm thu.
