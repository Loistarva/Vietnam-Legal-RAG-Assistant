# Lượt 1: bổ sung văn bản trung ương

Ngày chuẩn bị: 17/11/2026. Nhánh `data/trial-13-documents`; baseline trước lượt này: 61 văn bản, 2.170 parent, 4.995 child.

## Kết quả chuẩn bị dữ liệu

- Tải được **19 PDF nguồn chính thức** cho 19 văn bản trung ương (Công báo/Cổng thông tin Chính phủ).
- **11 văn bản** được chuẩn hóa và đưa vào `data/raw_data`, registry/metadata, đầu ra parser và chunking. Tổng: **72 văn bản, 2.344 parent, 5.382 child**.
- **8 văn bản giữ chờ**, không có trong registry hoặc đầu vào mặc định: 5 bản chưa đạt tương thích trích xuất/số hiệu, 3 bản sửa đổi hỗn hợp cần duyệt phạm vi chi tiết.
- Chưa đạt mục tiêu tối đa 30 văn bản/lượt. Không tính bản chờ hoặc bản chỉ có trang metadata thành văn bản đã thêm.

## 11 văn bản đã thêm

| Số hiệu | Điều toàn văn | Phạm vi đưa vào chunk |
|---|---:|---|
| 110/2013/NĐ-CP | 75 | Điều 1–4, 28–30, 32–33, 47–51, 74–75; loại nội dung ngoài HNGĐ |
| 66/2025/TT-BCA | 18 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |
| 110/2025/NĐ-CP | 17 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |
| 24/2011/TT-BVHTTDL | 11 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |
| 11/2021/TT-BTP | 3 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |
| 01/2025/TT-BTP | 3 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |
| 24/2014/TT-BTP | 2 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |
| 06/2012/NĐ-CP | 5 | Điều 2, 3, 5; loại Điều trộn nhiều loại hộ tịch/chứng thực |
| 12/2011/TT-BTP | 10 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |
| 15/2014/TT-BTP | 16 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |
| 21/2011/TT-BTP | 18 | Toàn bộ phần Điều; phụ lục/biểu mẫu giữ ở nguồn và sidecar |

## Chuẩn dữ liệu và kiểm tra

- PDF nạp là bản phái sinh phục vụ pipeline, Letter 612×792 pt, Times New Roman 12 pt, Unicode native. PDF chính thức nguyên trạng lưu riêng tại `data/source_pdfs/central_batch1`, HTML thuộc tính tại `data/source_documents/central_batch1`; URL, SHA-256 và đường dẫn ghi trong metadata.
- Kiểm tra thứ tự token từ/số/dấu câu từ text chuẩn hóa sang PDF; kiểm tra từ của phần Điều được bảo toàn trong JSON parser; kiểm tra số Điều và schema.
- Với TT01/2025, thêm khoảng trắng trong dấu `./ .` ở đoạn trích sửa đổi để parser không cắt trước Điều 2–3; không thay từ, số hoặc thứ tự dấu câu. Dấu kết thúc thật ở cuối văn bản được giữ nguyên.
- Phụ lục, biểu mẫu và phần ký không được coi là đã index đầy đủ; giữ ở bản nguồn và `annex_and_terminal_text`.
- Hai văn bản hỗn hợp dùng dữ liệu `corpus_scope.json` theo cơ chế hiện có. NĐ67/2015, TT05/2012, TT09b/2013 chưa đưa vào index vì Điều sửa đổi trộn nhiều nội dung.
- Đã đối chiếu hình thức trang đầu/cuối 11 PDF chuẩn hóa và kiểm tra toàn bộ tọa độ chữ không vượt lề.
- Các bản cũ không đổi: 61 registry record trước đó, 4.995 child và 2.170 parent giữ nguyên payload. Không sửa cleaner, parser, chunker, schema hoặc workflow CI.
- Chưa re-index Elasticsearch/Qdrant, chưa chạy lại Run A/Run B chính thức.

## Tình trạng hiệu lực

Ngày hiệu lực ban đầu đối chiếu với thuộc tính nguồn chính thức. Không tự ghi “còn hiệu lực” cho văn bản chưa rà soát đầy đủ chuỗi sửa đổi. NĐ110/2013 ghi hết hiệu lực 01/09/2020 theo CSDL quốc gia; TT12/2011 và TT24/2014 ghi hết hiệu lực 26/02/2021 theo Điều 9.1 TT10/2020. Các bản còn lại ghi “Không xác định” / `requires_review`; dữ liệu này chưa phải phê duyệt hiệu lực cấp Điều/Khoản.

## 8 văn bản giữ chờ

- **08a/2010/TT-BTP**: PDF nguồn quét/thiếu lớp chữ hoặc số hiệu kiểu cũ chưa tương thích parser; giữ bản nguồn, chưa có bản nạp được xác nhận.
- **24/2017/TT-BYT**: PDF nguồn quét/thiếu lớp chữ hoặc số hiệu kiểu cũ chưa tương thích parser; giữ bản nguồn, chưa có bản nạp được xác nhận.
- **09b/2013/TT-BTP**: Sửa đổi biểu mẫu hộ tịch nhiều loại việc; chưa duyệt phạm vi chi tiết.
- **82/2020/NĐ-CP**: PDF nguồn quét/thiếu lớp chữ hoặc số hiệu kiểu cũ chưa tương thích parser; giữ bản nguồn, chưa có bản nạp được xác nhận.
- **144/2021/NĐ-CP**: PDF nguồn quét/thiếu lớp chữ hoặc số hiệu kiểu cũ chưa tương thích parser; giữ bản nguồn, chưa có bản nạp được xác nhận.
- **67/2015/NĐ-CP**: Điều 1 trộn sửa đổi nhiều lĩnh vực; allowlist hiện tại chỉ theo Điều nên chưa đưa vào corpus.
- **05/2012/TT-BTP**: Sửa đổi biểu mẫu hộ tịch nhiều loại việc; chưa duyệt phạm vi chi tiết.
- **02/2016/TTLT-BNG-BTP**: PDF nguồn quét/thiếu lớp chữ hoặc số hiệu kiểu cũ chưa tương thích parser; giữ bản nguồn, chưa có bản nạp được xác nhận.

Ngoài 19 bản đã tải, các trang nguồn đã kiểm tra của Luật02/2007, NĐ08/2009, NĐ87/2001 và NĐ158/2005 chỉ đưa tệp Word/RTF, chưa tải được bản PDF phù hợp trong lượt này. Không tính bốn bản đó vào số đã thêm.

## Bằng chứng

- `catalog.csv`: danh sách 19 văn bản, trạng thái đã nhận/chờ và nguồn.
- `acquisition.json`, `normalization.json`: tải nguồn và kết quả kỹ thuật từng bản.
- `content_layout_checks.json`, `parser_replay.json`: bảo toàn nội dung, số Điều, bố cục và chạy lại parser với registry hiện tại.
- `normalized_contact_sheet.png`: trang đầu/cuối các bản đã nhận.
- `tests.log`, `tests.xml`, `negative_set.log`, `chunker.log`: kết quả kiểm tra, xem trạng thái cuối trong `validation.json`.

## Kết quả test cuối

**2058 tests và 221 subtests qua; 1 skipped; 0 lỗi/failed.** Lint runtime PASS, source manifest PASS, negative-set validator không có issue (2 cảnh báo corpus khác baseline là dự kiến). Đã cập nhật bảng tra production_chunk_index theo corpus mới, chưa re-index dịch vụ.
