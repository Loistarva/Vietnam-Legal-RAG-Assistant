# Bộ thử bổ sung 13 văn bản — 13/11/2026

Nhánh local: `data/trial-13-documents`, tách từ `testing` tại `cdca079`.

Đã tải **13 PDF gốc**, tạo 13 bản PDF chuẩn hóa theo mẫu L01 trên testing, bổ sung metadata và tạo TXT/JSON/chunk. Tổng corpus đầu vào trên nhánh thử: **41 PDF / 41 JSON văn bản**. Bản gốc của 13 file mới lưu riêng tại `data/source_pdfs/trial13/`; các bản dùng để ingest nằm trong `data/raw_data/additional_documents/`.

## Kết quả

| Chỉ số | Bộ 28 văn bản cũ | Bổ sung 13 | Tổng |
|---|---:|---:|---:|
| Văn bản | 28 | 13 | 41 |
| Parent chunk | 1.079 | 617 | 1.696 |
| Child chunk | 2.322 | 1.676 | 3.998 |

Bộ mới gồm **521 Điều, 1.603 Khoản**. Kiểm tra schema, chuỗi Điều 1..N, số Điều cuối đã đối chiếu, liên kết parent–child, giới hạn parent và ID trùng đều đạt. PDF có lớp chữ, không gọi OCR. `underthesea==9.5.0`.

Toàn bộ 1.079 parent và 2.322 child cũ giữ nguyên ID **và toàn bộ payload** khi so sánh theo ID với commit gốc. Không cần tạo lại embedding cũ chỉ vì thứ tự parent trong file JSON thay đổi; 1.676 child mới chưa được embedding/index.

Kiểm thử hiện có: **651 passed, 1 skipped**. Bộ gốc đối chiếu: 469 passed, 1 skipped. Trường hợp skipped là kiểm thử có sẵn. Xem [tests.log](tests.log), [baseline_tests.log](baseline_tests.log) và [audit.json](audit.json).

## Danh sách 13 văn bản

| Mã | Số hiệu / PDF local | Tên | Điều | Parent | Child | PDF nguồn |
|---|---|---|---:|---:|---:|---|
| L05 | [60/2014/QH13](../../../data/source_pdfs/trial13/l_60_2014_qh13.pdf) | LUẬT HỘ TỊCH | 77 | 83 | 195 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2014/11/5264/10513-1-201411651166-602014qh13pdf) |
| L06 | [52/2010/QH12](../../../data/source_pdfs/trial13/l_52_2010_qh12.pdf) | LUẬT NUÔI CON NUÔI | 52 | 58 | 158 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2010/6/2961/1192-1-2010562-563-522010qh12pdf) |
| L07 | [13/2022/QH15](../../../data/source_pdfs/trial13/l_13_2022_qh15.pdf) | Luật phòng, chống bạo lực gia đình | 56 | 65 | 212 | [Nguồn](https://datafiles.chinhphu.vn/cpp/files/vbpq/2023/4/luat13.pdf) |
| TT14 | [10/2020/TT-BTP](../../../data/source_pdfs/trial13/tt_10_2020_tt_btp.pdf) | ban hành, hướng dẫn việc ghi chép, sử dụng, quản lý và lưu trữ Sổ, mẫu giấy tờ, hồ sơ nuôi con nuôi | 9 | 13 | 33 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2020/12/33164/34634-1-2021281-28210-2020-tt-btp.pdf) |
| ND14 | [06/2011/NĐ-CP](../../../data/source_pdfs/trial13/nd_06_2011_nd_cp.pdf) | quy định chi tiết và hướng dẫn thi hành một số điều của Luật Người cao tuổi | 20 | 21 | 61 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2011/1/729/3966-1-201171-72-062011nd-cppdf) |
| L08 | [35/2013/QH13](../../../data/source_pdfs/trial13/l_35_2013_qh13.pdf) | Luật Hòa giải ở cơ sở | 33 | 34 | 103 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2013/6/6398/3284-1-2013407-408-352013qh13pdf) |
| ND15 | [28/2012/NĐ-CP](../../../data/source_pdfs/trial13/nd_28_2012_nd_cp.pdf) | quy định chi tiết và hướng dẫn thi hành một số điều của Luật người khuyết tật | 35 | 45 | 120 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2012/4/117/10683-1-2012343-344-282012nd-cppdf) |
| L09 | [51/2010/QH12](../../../data/source_pdfs/trial13/l_51_2010_qh12.pdf) | LUẬT NGƯỜI KHUYẾT TẬT | 53 | 59 | 184 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2010/6/3086/1275-1-2010570-571-512010qh12pdf) |
| ND16 | [19/2011/NĐ-CP](../../../data/source_pdfs/trial13/nd_19_2011_nd_cp.pdf) | Quy định chi tiết thi hành một số điều của Luật Nuôi con nuôi | 52 | 64 | 152 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2011/3/4925/5109-1-2011171-172-192011nd-cppdf) |
| ND17 | [56/2017/NĐ-CP](../../../data/source_pdfs/trial13/nd_56_2017_nd_cp.pdf) | Quy định chi tiết một số điều của Luật trẻ em | 58 | 69 | 194 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2017/5/23704/17553-1-2017363-36456-2017-nd-cp.pdf) |
| ND18 | [76/2023/NĐ-CP](../../../data/source_pdfs/trial13/nd_76_2023_nd_cp.pdf) | Quy định chi tiết một số điều của Luật Phòng, chống bạo lực gia đình | 45 | 64 | 179 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2023/11/40354/46907-1-20231133-113476-2023-nd-cp.pdf) |
| ND19 | [114/2016/NĐ-CP](../../../data/source_pdfs/trial13/nd_114_2016_nd_cp.pdf) | Quy định lệ phí đăng ký nuôi con nuôi, lệ phí cấp giấy phép hoạt động của tổ chức con nuôi nước ngoài | 11 | 14 | 31 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2016/7/20467/14937-1-1142016nd-cp15018pdf) |
| ND20 | [15/2014/NĐ-CP](../../../data/source_pdfs/trial13/nd_15_2014_nd_cp.pdf) | Quy định chi tiết một số điều và biện pháp thi hành Luật hòa giải ở cơ sở | 20 | 28 | 54 | [Nguồn](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2014/2/6628/3438-1-2014317-318-152014nd-cppdf) |

## Đã chuẩn hóa những gì

- Đặt tên PDF theo `document_id`; bản gốc giữ nguyên byte tải về trong `data/source_pdfs/trial13/`. Bản PDF dùng ingest được chuyển khổ Letter 612×792 pt, cân giữa trang và tỷ lệ nội dung chính từ 14 pt xuống 12 pt theo L01, giữ bảng/ảnh/phụ lục vector. Chữ ký số/annotation của bản gốc không được sao sang bản dẫn xuất. Cả hai bản có SHA-256 riêng trong [downloads.json](downloads.json).
- Bổ sung 13 bản ghi vào `data/reference/document_versions.json`, đồng bộ mã quản lý và bảng ánh xạ trong `docs/data_contract.md`, `data/raw_data/README.md`.
- Lưu trích xuất gốc tại [original_extracted_texts](original_extracted_texts/). Bản đưa vào `parser/extracted_texts_qwen/` đã bỏ dòng metadata chữ ký số và dòng phân cách chỉ gồm gạch; không sửa câu chữ pháp luật. Thư mục có tên qwen theo quy ước repo, nhưng bộ này dùng native text PyMuPDF.
- Sau kiểm tra lại, tách câu xác nhận Quốc hội thông qua ở cuối 5 Luật khỏi đầu vào parser (vẫn giữ ở bản trích xuất gốc và metadata). Việc này sửa câu ban hành bị gộp vào khoản cuối ở Luật 60/2014, 52/2010 và 35/2013; hai Luật còn lại vốn đã được parser cắt đúng. Không sửa nội dung điều khoản.
- Chạy cleaner hiện có để bỏ Công báo/số trang, chuẩn Unicode/dấu thanh; lưu đúng định dạng và newline mà kiểm thử yêu cầu. Bản cleaned có thể tái tạo từ bản extracted đã chuẩn bị.
- Ngày ban hành Luật 51/2010 và 52/2010 lấy **17/06/2010** theo câu thông qua ở cuối PDF; trang tra cứu Chính phủ hiển thị ngày khác. Có ghi chú metadata.
- Giữ nguyên tiêu đề dài thật ở NĐ 28/2012 Điều 18 (47 từ), NĐ 76/2023 Điều 10 (43 từ), TT 10/2020 Điều 5 (41 từ), đối chiếu font đậm trên PDF. Chỉ bổ sung ba ngoại lệ vào allowlist kiểm thử sẵn có; không nới ngưỡng chung.

**Không sửa** `parser/parser.py`, `parser/cleaner.py`, `chunking/chunking_rules.py`, `chunking/export_legal_chunks.py`. Các kiểm tra hash/mã nguồn trong audit xác nhận điều này.

## Phạm vi của lần thử

- Đây là bộ thử khả năng tiếp nhận dữ liệu, có mở rộng sang nuôi con nuôi, bảo vệ gia đình, người cao tuổi, người khuyết tật và hòa giải. **Chưa phải bản phát hành căn cứ pháp luật hiện hành**.
- Cả 13 bản ghi mới để `validity_status = Không xác định`, `provision_status = requires_review`, `trial_only = true`. Ngày hiệu lực là ngày hiệu lực ban đầu trong bản gốc; chưa xác minh toàn bộ sửa đổi/bãi bỏ hiện tại. Cờ trial_only nằm ở registry để quản lý, không phải bộ lọc runtime đã được triển khai. Chỉ thử trên nhánh này.
- PDF gốc vẫn có đầy đủ phụ lục. Parser hiện có chỉ đưa phần Điều chính vào JSON/chunk; biểu mẫu/phụ lục của NĐ 56/2017, NĐ 76/2023, TT 10/2020 chưa được lập chỉ mục riêng.
- Cảnh báo thiếu Chương I ở TT 10/2020 và NĐ 114/2016 là bình thường vì văn bản không chia Chương. Báo cáo chunking còn cảnh báo hiệu lực chưa xác minh, intro dài và mảnh ngắn; xem [chunking_report.json](../../../data/chunking_output/chunking_report.json).
- Đã kiểm tra tự động toàn bộ cấu trúc, so sánh payload cũ và xem trực quan mẫu PDF/tiêu đề dài. Chưa rà pháp lý thủ công mọi câu của 13 văn bản.
- Bản scan Luật Trẻ em 102/2016 đã được loại khỏi bộ thử; không tính thành một trong 13 file.

## Chạy lại từ thư mục gốc worktree

Môi trường đã chạy thành công trên máy này: `D:/GitHubProjects/Vietnam-Legal-RAG-Assistant-benchmark/.venv-gold/Scripts/python.exe`. Các lệnh dưới dùng `python` tương ứng môi trường có dependencies dự án, thêm `beautifulsoup4` cho bước tải file.

```powershell
python -X utf8 scripts/trial13_download.py
python -X utf8 scripts/trial13_standardize_pdfs.py
python -X utf8 scripts/trial13_prepare.py
python -X utf8 chunking/export_legal_chunks.py
python -X utf8 scripts/trial13_audit.py
python -X utf8 -m pytest parser/test_parser_unit.py parser/test_cleaner.py test/test_chunking.py -q --basetemp=tmp/trial13/pytest
```

Để chỉ parse lại 13 TXT đã chuẩn bị mà không trích xuất lại PDF, dùng `parser/test_parser.py --skip-clean --only` với tên stem trong danh sách. `--only` ở entry point hiện có chỉ lọc bước parse; không lọc cleaner nếu bỏ `--skip-clean`. Bước `trial13_prepare.py` luôn xử lý đúng manifest 13 văn bản.

Chưa commit/push, chưa merge vào `testing`, chưa cập nhật vector DB hoặc benchmark.
