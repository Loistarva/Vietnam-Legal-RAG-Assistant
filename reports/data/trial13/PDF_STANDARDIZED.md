# Đã chuẩn hóa 13 PDF theo mẫu testing

Ngày thực hiện: 13/11/2026. Nhánh: `data/trial-13-documents`.

- Mẫu tham chiếu: `data/raw_data/laws_and_decrees/L01.pdf` của testing.
- Bản đã chỉnh: `data/raw_data/additional_documents/` (13 file có tên document_id trong manifest).
- Bản gốc nguyên byte tải về: `data/source_pdfs/trial13/`.

## Bố cục đã chỉnh

Đưa trang về khổ Letter **612 × 792 pt**, đặt nội dung cân giữa trang và đổi tỷ lệ chữ chính từ khoảng **14 pt thành 12 pt** theo L01. Trang ngang nếu có được giữ hướng ngang với khổ Letter tương ứng.

Dùng phép đặt lại trang PDF vector, không OCR, không dựng lại nội dung từ JSON. Các bảng, hình, số Điều/Khoản, phụ lục và số trang gốc vẫn được giữ; không dồn đoạn hoặc đổi cách xuống dòng của bản gốc. Vì thế khổ trang và tỷ lệ chữ được chuẩn hóa theo L01, còn đầu mục Công báo và phân trang nguồn vẫn giữ để đối chiếu.

Bản mới là bản dẫn xuất phục vụ xử lý dữ liệu: không mang chữ ký số/annotation của bản gốc. Bản gốc có chữ ký vẫn được giữ riêng.

## Kiểm tra sau chỉnh

- **13 file, 387 trang**, số trang của từng file không đổi.
- Đối chiếu tập ký tự không tính khoảng trắng của từng trang (loại riêng metadata chữ ký số) không thấy mất ký tự. Một số khoảng cách giữa chữ ở phần biểu mẫu thay đổi khi thư viện trích xuất lại; nội dung vector được giữ.
- Ảnh nội dung được giữ. Đã xem ảnh render trang đầu của cả 13 file bên cạnh mẫu L01; nội dung nằm gọn trong trang.
- Kết quả JSON parse của cả 13 văn bản **giống hệt trước khi đổi khổ/tỷ lệ PDF**: 521 Điều, 1.603 Khoản. Không phải chỉ so số Điều; đã so toàn bộ object JSON.
- Xuất chunk thành công: corpus 41 văn bản có 1.696 parent, 3.998 child, không trùng ID. Toàn bộ payload cũ của 28 văn bản giữ nguyên.
- Chạy lại kiểm thử sau đổi PDF: **651 passed, 1 skipped**.

Chi tiết máy đọc: [standardized_pdf_check.json](standardized_pdf_check.json), [standardized_parse_comparison.json](standardized_parse_comparison.json), [audit.json](audit.json), [tests.log](tests.log).

Đây là chuẩn hóa hình thức PDF và kiểm tra ingest. Phạm vi chunk phần Điều chính và việc chưa xác minh hiệu lực hiện tại của 13 văn bản vẫn như báo cáo bộ thử; không có thay đổi đánh giá hiệu lực pháp luật.

## Chạy lại

```powershell
python -X utf8 scripts/trial13_standardize_pdfs.py
python -X utf8 scripts/trial13_prepare.py
python -X utf8 chunking/export_legal_chunks.py
python -X utf8 scripts/trial13_audit.py
```

Manifest lưu riêng SHA-256 của PDF nguồn và PDF chuẩn hóa. Downloader dùng bản nguồn đã lưu, không ghi đè bản chuẩn hóa khi chạy lại với manifest hiện tại.
