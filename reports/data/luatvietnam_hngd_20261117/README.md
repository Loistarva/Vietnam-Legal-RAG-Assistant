# Đối chiếu danh mục Hôn nhân gia đình trên LuatVietnam

Ngày kiểm tra: 17/11/2026. Nhánh `data/trial-13-documents`, commit `b0ae67c7f94a587e13d96a7250474333e7766214`.

Nguồn: https://luatvietnam.vn/hon-nhan-gia-dinh-64-f2.html

## Kết quả

| Phân loại trong 313 mục của nguồn | Số lượng |
|---|---:|
| Có trong registry đang nạp và có PDF thực tế | 15 |
| Chỉ có trong vùng chờ / lưu trữ | 0 |
| Chưa tìm thấy file trong kho được đối chiếu | 298 |
| Chưa xác định được danh tính | 0 |
| Tổng | 313 |

Kho hiện có 61 văn bản đang nạp. Có 46 văn bản của kho không xuất hiện trong đúng danh mục nguồn này; chúng không được trừ vào 313 mục. Việc không xuất hiện trong danh mục này không có nghĩa là không có trên toàn bộ website.

## Phương pháp và giới hạn

- Đọc đủ 16 trang: 15 trang x 20 mục + trang cuối 13 mục; kiểm tra 313 mã tài liệu website khác nhau, mọi trang cùng hiển thị tổng 313.
- Đối chiếu số hiệu (chuẩn hóa Unicode, dấu gạch, chữ Đ/Ð và số 0 đầu) với registry đang nạp, metadata vùng chờ corpus_v2/corpus_v3 và bản PDF trial13 lưu trữ. Kiểm tra file tương ứng tồn tại thực tế. Không ghép văn bản theo số hiệu xuất hiện trong nội dung dẫn chiếu của một văn bản khác.
- Đọc trang chi tiết cho 3 mục thiếu số hiệu ở tiêu đề: 6-TT/LN ngày 30/12/1986; Công ước không số ngày 07/11/1962; Nghị quyết không số ngày 27/05/1959. Cả ba không có bản tương ứng trong kho được đối chiếu.
- Bao gồm mọi mục được danh mục trả về, không lọc hiệu lực hoặc tình trạng được sử dụng. Trạng thái `active_corpus` chỉ nói văn bản đang nằm trong corpus, KHÔNG nói văn bản còn hiệu lực pháp luật.
- Không xác nhận tình trạng hiệu lực từng văn bản trong lần đối chiếu này. Nhãn “Đã biết” trên giao diện có trường yêu cầu tài khoản không được diễn giải thành “còn hiệu lực”. Ngày ban hành trong báo cáo là ngày nguồn hiển thị.
- Danh mục gồm cả công văn, kế hoạch, quyết định địa phương, dân số và văn bản lịch sử. 298 mục chưa có không đồng nghĩa với 298 mục nên nạp vào Legal RAG; cần duyệt phạm vi và nguồn chính thức trước khi bổ sung.
- Không sửa corpus, metadata nạp, parser hoặc chunker.

## Các file

- `all_documents.csv`: toàn bộ 313 mục, có số hiệu, tiêu đề, ngày, URL và trạng thái đối chiếu.
- `already_present.csv`: 15 mục đã có, kèm ID và đường dẫn PDF.
- `not_present.csv`: 298 mục chưa có file tương ứng.
- `comparison.json`: dữ liệu đối chiếu đầy đủ.
- `local_active_not_in_category.json`: 46 văn bản đang có trong kho nhưng ngoài danh sách 313 mục của nguồn.
- `listing_records.json`: danh sách trích từ trang nguồn trước đối chiếu.
- `listing_capture_manifest.json`: URL, số mục và SHA-256 HTML từng trang đã kiểm tra.
- `summary.json`: tổng số để kiểm tra tự động.

CSV dùng UTF-8 BOM để mở tiếng Việt trong Excel.

## 15 mục đã có

- [207/2025/NĐ-CP](https://luatvietnam.vn/y-te/nghi-dinh-207-2025-nd-cp-cua-chinh-phu-quy-dinh-ve-sinh-con-bang-ky-thuat-ho-tro-sinh-san-va-dieu-kien-mang-thai-ho-vi-muc-dich-nhan-dao-405740-d1.html) — `nd_207_2025_nd_cp`
- [06/2025/NĐ-CP](https://luatvietnam.vn/hon-nhan-gia-dinh/nghi-dinh-06-2025-nd-cp-cua-chinh-phu-sua-doi-bo-sung-mot-so-dieu-cua-cac-nghi-dinh-ve-nuoi-con-nuoi-384884-d1.html) — `nd_06_2025_nd_cp`
- [01/2024/NQ-HĐTP](https://luatvietnam.vn/hon-nhan-gia-dinh/nghi-quyet-01-2024-nq-hdtp-huong-dan-ap-dung-phap-luat-giai-quyet-vu-viec-hngd-342776-d1.html) — `nq_01_2024_nq_hdtp`
- [76/2023/NĐ-CP](https://luatvietnam.vn/chinh-sach/nghi-dinh-76-2023-nd-cp-quy-dinh-chi-tiet-luat-phong-chong-bao-luc-gia-dinh-274524-d1.html) — `nd_76_2023_nd_cp`
- [13/2022/QH15](https://luatvietnam.vn/chinh-sach/luat-phong-chong-bao-luc-gia-dinh-2022-so-13-2022-qh15-238397-d1.html) — `l_13_2022_qh15`
- [01/2016/TTLT-TANDTC-VKSNDTC-BTP](https://luatvietnam.vn/chinh-sach/thong-tu-lien-tich-01-2016-ttlt-tandtc-vksndtc-btp-bo-tu-phap-102486-d1.html) — `ttlt_01_2016_ttlt_tandtc`
- [02a/2015/TT-BTP](https://luatvietnam.vn/hon-nhan-gia-dinh/thong-tu-02a-2015-tt-btp-bo-tu-phap-93822-d1.html) — `tt_02a_2015_tt_btp`
- [10/2015/NĐ-CP](https://luatvietnam.vn/y-te/nghi-dinh-10-2015-nd-cp-chinh-phu-92494-d1.html) — `nd_10_2015_nd_cp`
- [126/2014/NĐ-CP](https://luatvietnam.vn/hon-nhan-gia-dinh/nghi-dinh-126-2014-nd-cp-chinh-phu-92019-d1.html) — `nd_126_2014_nd_cp`
- [52/2014/QH13](https://luatvietnam.vn/hon-nhan-gia-dinh/luat-hon-nhan-va-gia-dinh-2014-so-52-2014-qh13-87930-d1.html) — `l_52_2014_qh13`
- [22/2013/TT-BTP](https://luatvietnam.vn/hon-nhan-gia-dinh/thong-tu-22-2013-tt-btp-bo-tu-phap-84131-d1.html) — `tt_22_2013_tt_btp`
- [24/2013/NĐ-CP](https://luatvietnam.vn/hon-nhan-gia-dinh/nghi-dinh-24-2013-nd-cp-huong-dan-luat-hon-nhan-va-gia-dinh-77599-d1.html) — `nd_24_2013_nd_cp`
- [19/2011/NĐ-CP](https://luatvietnam.vn/chinh-sach/nghi-dinh-19-2011-nd-cp-chinh-phu-60300-d1.html) — `nd_19_2011_nd_cp`
- [16/2010/TT-BTP](https://luatvietnam.vn/hon-nhan-gia-dinh/thong-tu-16-2010-tt-btp-bo-tu-phap-56083-d1.html) — `tt_16_2010_tt_btp`
- [77/2001/NĐ-CP](https://luatvietnam.vn/hon-nhan-gia-dinh/nghi-dinh-77-2001-nd-cp-chinh-phu-12555-d1.html) — `nd_77_2001_nd_cp`
