# Kiểm tra lại PDF và pipeline theo nhánh testing

> Cập nhật sau yêu cầu chỉnh PDF: **đã tạo đủ 13 bản PDF chuẩn hóa thật**. Phần mô tả “chưa tái dàn trang” bên dưới là kết quả kiểm tra trước bước chỉnh. Kết quả mới nhất: [PDF_STANDARDIZED.md](PDF_STANDARDIZED.md).

Ngày kiểm tra: 13/11/2026. Bộ tham chiếu là 28 PDF của `origin/testing` tại commit `cdca079`; đối chiếu trực quan trang đầu L01 và 13 file mới, đồng thời kiểm tra lớp chữ trên toàn bộ 387 trang mới.

## Đã đổi form PDF chưa?

**Chưa tái dàn trang/chỉnh trực tiếp 13 PDF gốc.** File tải về vẫn giữ nguyên byte và SHA-256. Những gì đã chuẩn hóa là tên file, metadata, bản TXT đầu vào và JSON/chunk.

Chính bộ testing có nhiều định dạng: 15 file khổ Letter, các file còn lại khổ A4 hoặc phối hợp trang dọc/ngang. Vì vậy không có một bộ thông số khổ giấy/font chung cho toàn bộ PDF testing. File mới là bản gốc có lớp chữ, cấu trúc Điều/Khoản tương thích pipeline; không phải bản sao bố cục L01.

Chi tiết đối chiếu: [testing_pdf_formats.json](testing_pdf_formats.json), [pdf_check.json](pdf_check.json).

## Lỗi phát hiện và đã xử lý

Khi trích xuất trực tiếp từ PDF, câu xác nhận Quốc hội thông qua bị gộp vào khoản cuối ở ba văn bản:

- Luật 60/2014/QH13, Điều 77.
- Luật 52/2010/QH12, Điều 52; còn có dòng gạch dưới phân cách.
- Luật 35/2013/QH13, Điều 33.

Đã sửa tại bước chuẩn bị TXT: tách câu xác nhận ban hành khỏi nội dung điều khoản, giữ trích xuất nguyên gốc trong `original_extracted_texts/`. Không thay đổi PDF, parser, cleaner hoặc chunker. Số Điều/Khoản và tổng số chunk không đổi. Cả 13 JSON đã được kiểm tra không còn câu xác nhận này trong clause_text.

## Kết quả kiểm tra

- 13/13 PDF đọc được; 387 trang không phát hiện ký tự thay thế Unicode U+FFFD hay null trong lớp chữ.
- 13/13 đầu vào trích xuất trực tiếp cho số Điều bằng bản đã chuẩn bị, và đạt kiểm tra cấu trúc JSON. Bản đã chuẩn bị còn tách sạch câu ban hành và ký tự phân cách.
- Đối chiếu đủ 521 Điều, 1.603 Khoản của bộ mới với chuỗi Điều và số Điều cuối đã xác định; kiểm tra schema và quan hệ parent–child đều đạt.
- Xuất corpus 41 văn bản thành công: 1.696 parent, 3.998 child, không trùng ID. Payload của 28 văn bản cũ không đổi.
- Bộ kiểm thử hiện có được chạy lại sau sửa; kết quả chi tiết tại [tests.log](tests.log).

## Giới hạn còn lại

- Hai trang PDF 25–26 của TT 10/2020 có rất ít chữ. Đã xem trực quan: đây là các trang biểu mẫu trống có tiêu đề gia hạn/sửa đổi giấy phép, không phải lỗi mất chữ do trích xuất.
- Parser hiện chỉ lập chỉ mục phần Điều chính, chưa lập chỉ mục riêng biểu mẫu/phụ lục. PDF gốc vẫn có phụ lục.
- Hai intro dài ở NĐ 19/2011, Điều 7 và 13 bị rút gọn trong embed_text theo giới hạn cấu hình; exporter xác nhận bảo toàn nội dung nguồn trong các trường nội dung/parent. Chưa thay đổi giới hạn chunker.
- Hiệu lực hiện tại và sửa đổi cấp Điều/Khoản của 13 văn bản mới vẫn chưa được xác minh; bộ này dùng để thử ingest/parse/chunk.
- Kiểm tra tự động và xem trực quan mẫu không thay thế rà thủ công toàn bộ câu chữ pháp luật.

Nếu mục tiêu là chạy cùng parser/chunker trên testing thì bộ thử đã đáp ứng các kiểm tra trên. Nếu mục tiêu là 13 PDF phải có bố cục nhìn giống hệt một PDF mẫu, phần tái dàn trang đó chưa được thực hiện.
