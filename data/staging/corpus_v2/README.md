# Corpus v2 — dữ liệu tương thích pipeline testing

Cập nhật chuẩn hóa và kiểm tra ngày **17/11/2026**, trên `feat/corpus-v2`, nền `testing` commit `c1e9f12`. Không sửa code chạy parser, cleaner, chunker hoặc schema. Chỉ cập nhật kiểm tra tiêu đề dài trong `parser/test_parser_unit.py` và dữ liệu kỳ vọng của test.

## Đã hoàn tất

- **20 văn bản mới + 9 văn bản trial được nhận**: có PDF dẫn xuất khổ Letter **612 × 792 pt, cỡ chữ 12 pt**, cùng dạng mẫu L01 trên testing; có lớp chữ tiếng Việt. PDF Công báo gốc, các phần Công báo, phụ lục và chứng cứ nguồn được giữ riêng.
- Đường dẫn dùng ngay bởi code hiện có: `data/raw_data/additional_documents/corpus_v2/`, `parser/extracted_texts_qwen/`, `parser/cleaned_texts/`, `parser/parsed_jsons/`.
- `data/reference/document_versions.json` và `document_aliases.json` đã đồng bộ **57 văn bản** (28 baseline + 29 bổ sung). `source_pdfs.json` có đủ SHA-256 của 57 PDF trong raw_data; kiểm tra bằng script gốc PASS.
- Parser chạy bằng CLI gốc trên 29 TXT mới: **29 thành công, 0 thất bại**. Toàn bộ **57 JSON** hợp lệ theo schema testing. Chuỗi Điều, quan hệ ID cha/con và số Điều dự kiến được kiểm tra.
- Chunker/exporter nguyên bản chạy trên dữ liệu 57 văn bản: **2.051 parent, 4.716 child, 0 ID trùng**, dùng underthesea **9.5.0**. Phạm vi lọc đọc đúng dạng `documents → articles/reason` của `corpus_scope.json`. Tệp chunk và bảng tham chiếu trên nhánh feat đã được đồng bộ; chưa re-index Elasticsearch/Qdrant. Toàn bộ **2.322 chunk baseline được giữ nguyên payload trong corpus mới**, bản snapshot gốc nằm trong `history/baseline_c1e9f12/chunking_output/`; nhánh testing và kết quả A/B không thay đổi.
- **ND17 vẫn hoãn**, nằm ở `data/staging/corpus_v2/hold/`, không được cleaner mặc định phát hiện và không có trong registry/parser đang chạy. Ba văn bản ND14/L09/ND15 ngoài phạm vi không được đưa vào bộ nạp.

## Quy ước dữ liệu để tương thích mà không sửa code

Các Bộ luật được Cổng Chính phủ phân loại là `Luật`; dùng chính giá trị `Luật` cho `metadata.document_type` theo enum của testing. Giữ nguyên tên Bộ luật và `document_id` bắt đầu `bl_`, đồng thời ghi `document_subtype: Bộ luật` trong registry. Parser hiện có lấy ID từ registry nên không cần sửa hàm tạo prefix.

JSON parser chỉ có các trường được schema hiện tại chấp nhận. URL tải, SHA-256, thông tin chuẩn hóa và kiểm tra nằm trong registry/manifest, không nhét trường lạ vào `metadata` của JSON parser. Các tiêu đề Tiểu mục chưa được schema biểu diễn được giữ trong bản gốc và `structure_sidecars`, không đổi nhãn Tiểu mục thành Mục.

Bản dẫn xuất tách phần ký ban hành và phụ lục khỏi phần chính văn đúng cách pipeline testing hiện xử lý; toàn bộ nguồn vẫn giữ riêng. **Phụ lục/biểu mẫu chưa được code hiện tại index độc lập**; không tự tạo Điều/Khoản giả để đưa biểu mẫu hay bảng án phí vào chunk.

Hai bản scan Luật Trẻ em và NQ 326 được bổ sung lớp chữ từ bản in lại/tệp Word trên cổng cơ quan nhà nước; không dùng OCR suy đoán. Luật Trẻ em lấy trang PDF 7–46 của bản in lại trên cổng Tủ sách pháp luật; NQ 326 dùng tệp Word của VKSND Hà Nội. Đường dẫn, URL, SHA-256 và phương pháp nằm trong `normalization_text_evidence`. Giữ cả PDF Công báo gốc để kiểm tra.

Ở NQ 326, nhãn `Điều 23:` được chuẩn hóa thành `Điều 23.`; ở NĐ 301, dấu chấm sau nhãn Điều **bên trong đoạn trích** được chuẩn hóa thành dấu hai chấm để parser không nhầm số Điều trích thành số Khoản. Chỉ chuẩn hóa dấu phân cách cấu trúc, không đổi chữ, số Điều hoặc nội dung quy phạm. Các số Điều đúng đã đối chiếu: NQ 326 có 48 Điều, TT 07/2023/TT-BTP có 3 Điều, TT 07/2023/TT-BNG có 23 Điều; không dùng các số đếm lẫn từ phụ lục ở bản khảo sát đầu.

## Phạm vi và các phần chưa được tuyên bố hoàn tất

Phạm vi nạp thực thi là `data/reference/corpus_scope.json`; PDF/JSON toàn văn là bản nguồn, không có nghĩa toàn văn được index. NĐ 104/2022 Điều 12 sửa **nuôi con nuôi** tại NĐ 19/2011; phần hộ tịch nằm ở **khoản 2 Điều 13**. Vì exporter chỉ lọc cấp Điều, Điều 13 trộn nhiều ngành chưa được index. Tương tự, chưa index Điều 24 NĐ 120/2025 và Điều 5 Luật 85/2025 khi chưa chọn được phần hỗn hợp phù hợp mà vẫn giữ đúng ID. Các đoạn chưa index được liệt kê trong `ingest_scope.json`.

**Chưa hoàn tất rà soát hiệu lực cấp Điều/Khoản và cập nhật provision_periods cho toàn bộ văn bản bổ sung.** Không tự biến trạng thái chưa kiểm tra thành “Còn hiệu lực”; giữ `Không xác định` hoặc `Sửa đổi bổ sung` cùng `requires_review`. Tất cả ứng viên giữ `production_ingest_allowed: false`. Đây là dữ liệu đã tương thích kỹ thuật, chưa phải xác nhận toàn bộ corpus là pháp luật hiện hành. Các cờ này là thông tin bàn giao; ứng dụng hiện tại không tự thực thi chúng như một hàng rào an toàn.

NQ 35/2000 vẫn là mục P0-A cần xác minh PDF và trạng thái giữa các bản ghi nguồn mâu thuẫn, chưa nhận vào 20 tệp mới. Luật Hộ tịch 03/2026/QH16 chưa được đưa vào nhóm áp dụng cho thời điểm 2026 vì nguồn Công báo ghi hiệu lực từ 01/03/2027.

Đã xử lý các ca test ngưỡng tiêu đề **40 từ** bằng cách đối chiếu **31 tiêu đề chính thức** với bản PDF nguồn. Test hiện kiểm tra chính xác từng tiêu đề và SHA-256 nguồn trong `test/fixtures/corpus_v2_reviewed_long_titles.json`; không bỏ test, không nâng ngưỡng chung và không rút ngắn tiêu đề pháp luật. Nhóm kiểm tra parser/schema/PDF/tham chiếu: **698 passed, 1 skipped**. Báo cáo đầy đủ tại `reports/data/corpus_v2/final_data_tests.log`; kết quả toàn repo được lưu riêng trong `full_suite_after_title_fix.log` và XML tương ứng. Lỗi ánh xạ registry/chunk trước đó đã được xử lý bằng đồng bộ dữ liệu sinh ra và bảng Mục 6 của data contract.

## Tệp bàn giao

- `CATALOG.md`, `catalog.csv`: danh mục 20 văn bản mới và lý do chọn.
- `document_versions.json`: bản sao 20 metadata ứng viên; registry đang dùng thực tế ở `data/reference/document_versions.json`.
- `retained_trial13_metadata.json`, `trial13_decisions.json`, `hold/`: quyết định nhận/hoãn/loại của trial13.
- `SHA256SUMS.txt`: mã băm PDF/TXT/JSON dẫn xuất.
- `reports/data/corpus_v2/current_validation.json`: kiểm tra kỹ thuật mới nhất.
- `compatibility/export_fixture/data/chunking_output/`: output chạy thử của exporter gốc, chỉ dùng đối chiếu.
- `history/pre_normalization/`: gói khảo sát cũ, không dùng làm đầu vào hiện hành.

Sau khi người phụ trách pháp lý chốt hiệu lực và phạm vi: người phụ trách ingest có thể dùng nguyên code hiện tại để parse/chunk phần dữ liệu tương thích này, rồi thực hiện re-index và benchmark theo quy trình nhóm. Không merge vào testing hoặc ghi đè kết quả A/B trong bước chuẩn bị data này.

## K?t qu? test to?n repo sau s?a

1776 passed, 206 subtests passed, 1 skipped, 0 failures, 0 errors. Xem `reports/data/corpus_v2/full_suite_final.xml`. Suite ki?m tra c? vi?c t? ch?i s? d?ng freeze/nh?n l?ch s? kh?ng c?n ph? h?p; kh?ng ??ng ngh?a b? negative c? ?? ???c duy?t cho corpus v2.
