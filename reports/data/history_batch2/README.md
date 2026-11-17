# Lượt 2 — văn bản lịch sử về hôn nhân và gia đình

Chuẩn bị ngày 17–18/11/2026 trên nhánh `data/trial-13-documents`. Baseline: commit `51abcd7`, 72 văn bản, 2.344 parent, 5.382 child.

## Kết quả

Đã lấy tệp đính kèm chính thức cho **10 ứng viên**. Nhận **5 văn bản** vào raw_data, metadata, parser và corpus; **5 bản giữ chờ**. Kho tăng từ **72 lên 77 văn bản**. Không tính bản giữ chờ là đã nạp; chưa đạt mục tiêu tối đa 30 văn bản/lượt.

**Nguồn lịch sử chủ yếu là Word/RTF chính thức, không phải PDF có chữ ký.** Các PDF bàn giao là bản phái sinh Unicode phục vụ ingest. Giữ nguyên tệp đính kèm chính thức và HTML thuộc tính, kèm URL/SHA-256; không mô tả PDF phái sinh là bản ký gốc.

## 5 văn bản đã nhận

| Số hiệu | Điều toàn văn | Hiệu lực ban đầu | Hết hiệu lực toàn bộ |
|---|---:|---|---|
| 158/2005/NĐ-CP | 99 | 2006-04-01 | 2016-01-01 |
| 83/1998/NĐ-CP | 97 | 1998-10-25 | 2006-04-01 |
| 02/2007/QH12 | 46 | 2008-07-01 | 2023-07-01 |
| 08/2009/NĐ-CP | 22 | 2009-03-21 | 2023-12-25 |
| 110/2009/NĐ-CP | 33 | 2010-01-27 | 2013-12-28 |

NĐ83/1998 và NĐ158/2005 là văn bản hộ tịch hỗn hợp: chỉ các Điều trong `data/reference/corpus_scope.json` được chunk. Toàn văn vẫn giữ trong JSON parser. NĐ158 tạm loại các Điều đã sửa bởi NĐ06/2012, phần nuôi con nuôi bị bãi bỏ bởi NĐ19/2011 và các Điều trộn loại việc, chờ rà soát khoảng áp dụng cấp Khoản. NĐ83 không đưa phần quản lý cán bộ, khai tử hoặc phần yếu tố nước ngoài cần chuỗi thay thế riêng vào corpus.

## Nguồn và hiệu lực

- NĐ83/1998: ban hành 10/10/1998; hiệu lực sau 15 ngày kể từ ngày ký; thay thế từ 01/04/2006 theo Điều 98 NĐ158/2005.
- NĐ158/2005: hiệu lực 01/04/2006 theo Điều 98; bãi bỏ từ 01/01/2016 theo Điều 45.1 và 45.2.b NĐ123/2015.
- Luật02/2007: ngày ban hành theo phần đầu và câu thông qua trong tệp Word là **21/11/2007**, khác ngày 05/12/2007 trên bảng thuộc tính Chính phủ. Đã ghi sự khác biệt trong metadata; dùng ngày của văn bản. Hiệu lực 01/07/2008 theo Điều 45; hết hiệu lực 01/07/2023 theo Điều 56.2 Luật13/2022.
- NĐ08/2009: hiệu lực 21/03/2009; hết hiệu lực 25/12/2023 theo Điều 42.1–2 NĐ76/2023.
- NĐ110/2009: hiệu lực 27/01/2010 theo Điều 32; hết hiệu lực toàn bộ 28/12/2013 theo hồ sơ CSDL quốc gia: https://vbpl.moj.gov.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=23846 . Đây là đối chiếu hồ sơ được công khai, không suy ra từ nhãn “Đã biết”.

Không coi ngày hết hiệu lực toàn bộ là xác nhận mọi Điều/Khoản chưa từng sửa đổi trước đó. Metadata vẫn ghi `provision_status: requires_review`; phạm vi nạp được giới hạn thận trọng. Chưa phê duyệt pháp lý đầy đủ chuỗi sửa đổi cấp Khoản.

## Chuẩn hóa và kiểm tra nội dung

- Letter 612×792 pt, Times New Roman 12pt, chữ Unicode native; không cần OCR cho các bản đã nhận.
- Đọc tệp Word bằng bảng piece-table và kiểm tra không có phần footnote chưa trích xuất ở 5 bản nhận. Tệp `.rtf` của NĐ83 thực chất là Word nhị phân; nhận diện bằng magic bytes, không suy theo phần mở rộng.
- Chuyển TCVN3/ABC bằng ánh xạ ký tự có kiểm tra đảo ngược, giữ bản gốc; lưu bảng mã tại `tcvn3_character_map.json`. Chỉ chuẩn hóa chữ hoa của nhãn/tiêu đề Chương, Mục và cách viết số thứ tự tương đương.
- Phần HTML toàn văn có ký tự U+FFFD ở một số trang. Dùng tệp đính kèm Word gốc thay cho đoán chữ bị lỗi trên HTML.
- NĐ158: nhãn Mục I chuẩn thành Mục 1, giữ nguyên thứ tự và nội dung. NĐ83: nhãn Điều95 đặt riêng dòng để parser không lấy câu quy phạm làm tiêu đề; chuẩn hóa các dòng tiếp nối tiêu đề Chương/Mục.
- NĐ08 Điều20 có tiêu đề dài thật 41 từ. Đã đối chiếu nguyên văn với Word chính thức và ghi kỳ vọng chính xác trong fixture dữ liệu; không đổi ngưỡng hay code parser.
- Kiểm tra đủ Điều: 99 + 97 + 46 + 22 + 33; toàn bộ từ của phần quy phạm có trong JSON, tính đúng các tiêu đề Mục lặp lại ở các Chương khác nhau. Không miễn kiểm tra khi báo lệch từ.
- Kiểm tra tọa độ chữ toàn bộ PDF và xem trang đầu/cuối. Cleaner/parser/schema và replay với registry hiện tại đều qua cho 5 bản đã nhận.

## 5 bản giữ chờ

- **87/2001/NĐ-CP**: (23, 25)
- **35/2000/QH10**: Original numbered sections or unsupported legal type/identifier. Do not invent Articles or map a Pháp lệnh to another type.
- **28/L/CTN**: Official attachment contains Lệnh 28-L/CTN promulgating a separate Pháp lệnh. Do not treat the promulgating order number as the ordinance number; legal type/identity and body boundary require review.
- **12/2003/NĐ-CP**: (4, 26)
- **01/2008/TT-BTP**: Original numbered sections or unsupported legal type/identifier. Do not invent Articles or map a Pháp lệnh to another type.

NĐ87/2001 có 25 Điều nhưng parser hiện tại chỉ nhận 23; NĐ12/2003 có 26 Điều nhưng chỉ nhận 4 do các Điều không có tiêu đề trước Khoản đánh số. Không thêm tiêu đề giả hoặc đổi Khoản thành Điều để ép qua kiểm tra. Tệp mang số 28/L/CTN là gói có lệnh công bố và pháp lệnh riêng: chưa gán số của lệnh cho pháp lệnh.

PDF đọc lưu trữ của cả 10 ứng viên nằm ở `data/staging/history_batch2/archive_pdf`; chỉ 5 PDF trong `data/raw_data/additional_documents/history_batch2` là đầu vào đã nhận. Bản thử trong `compatibility` không có nghĩa được phép nạp.

## Bằng chứng kiểm tra

Xem `validation.json` để biết kết quả cuối; `catalog.csv` có danh mục và đường dẫn; `acquisition.json` lưu nguồn/SHA-256; `encoding_conversion.json`, `content_layout_checks.json`, `parser_replay.json`, `normalized_contact_sheet.png` lưu bằng chứng chuyển mã/nội dung/bố cục. Log test đầu tiên là lần phát hiện lỗi, kết quả cuối nằm trong `tests_final.log` và `tests_final.xml`.

Không sửa code cleaner/parser/chunker/schema/workflow. Không re-index Elasticsearch/Qdrant, không chạy lại Run A/Run B chính thức.

## Kết quả kiểm tra cuối

**2130 tests và 226 subtests qua, 1 skipped; 0 lỗi/failed.** Metadata audit 0 lỗi; lint và PDF SHA-256 manifest PASS. Negative-set validator không có issue, 2 cảnh báo khác baseline là dự kiến. Corpus: 2,509 parent, 5,784 child; toàn bộ 5.382 child và 2.344 parent cũ giữ nguyên payload.

## Rà soát độc lập ngày 18/11/2026

Đã đồng bộ danh sách tiêu đề Điều trong normalization.json của NĐ83/1998 với JSON parser cuối cùng. Đây là lỗi báo cáo cũ sau chuẩn hóa; PDF, metadata nạp và chunk không cần thay đổi. Kiểm tra riêng SHA-256 nguồn/bản lưu trữ/PDF nạp/JSON parser/Unicode, vùng chờ, metadata và gói ZIP được lưu ở independent_audit.json.
