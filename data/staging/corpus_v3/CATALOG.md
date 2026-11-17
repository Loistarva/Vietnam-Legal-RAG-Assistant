# Đợt danh sách khoảng 30 — 4 văn bản được thêm, 1 giữ chờ

Đã chuẩn hóa 5 văn bản trong danh sách được lọc theo chủ đề; chỉ 4 văn bản vào đầu vào mặc định. Tổng corpus 61 văn bản, 2.170 parent, 4.995 child. Các ứng viên còn lại chưa được duyệt nạp.

| Số hiệu | File code | Điều | PDF | Trạng thái |
|---|---|---:|---|---|
| 24/2013/NĐ-CP | ND28 | 45 | `data/raw_data/additional_documents/corpus_v3/nd_24_2013_nd_cp.pdf` | Đã thêm |
| 22/2013/TT-BTP | TT22 | 19 | `data/raw_data/additional_documents/corpus_v3/tt_22_2013_tt_btp.pdf` | Đã thêm |
| 16/2010/TT-BTP | TT23 | 10 | `data/raw_data/additional_documents/corpus_v3/tt_16_2010_tt_btp.pdf` | Đã thêm |
| 03/2016/TTLT-BTP-BNG-BCA-BLĐTBXH | TTLT01 | 22 | `data/raw_data/additional_documents/corpus_v3/ttlt_03_2016_ttlt_btp_bng_bca_bldtbxh.pdf` | Đã thêm |
| 69/2006/NĐ-CP | ND27 | 3 | `data/staging/corpus_v3/hold/nd_69_2006_nd_cp.pdf` | Hold, chưa index |

Toàn bộ 5 PDF qua cleaner/parser/schema hiện có, chữ native và SHA-256 nguồn được lưu. Không sửa parser/chunker/schema. 1902 tests và 210 subtests qua, 1 skipped vì tập trường hợp lỗi đã biết rỗng. Validator negative chạy đúng lệnh CI: không có issue; hai cảnh báo chỉ ghi nhận corpus đã đổi so với baseline57.

TT16/2010 và TT22/2013 đã hết hiệu lực 10/04/2015; NĐ24/2013 có hai mốc bãi bỏ 15/02/2015 và 01/01/2016, đã ghi khoảng hiệu lực cấp Điều bằng dữ liệu provision_periods. TTLT03/2016 vẫn ghi cần rà soát trạng thái mới nhất. NĐ69/2006 ở vùng hold dù kỹ thuật đã qua, do cần đối chiếu dẫn chiếu/phạm vi bãi bỏ. Chưa re-index ES/Qdrant hoặc chạy lại A/B official.
