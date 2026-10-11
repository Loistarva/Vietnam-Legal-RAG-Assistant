# BÁO CÁO CHẤT LƯỢNG DỮ LIỆU

## 1. Tổng quan

Dự án Vietnam Legal RAG Assistant đang sử dụng dữ liệu pháp luật gốc được lưu trong thư mục raw_data theo phân loại:

- laws_and_decrees/
- circulars/

Hiện trạng kiểm tra thực tế cho thấy:

- Các file PDF gốc đang tồn tại trong thư mục raw_data.
- Cấu trúc thư mục đã được tổ chức lại theo chuẩn.
- Metadata và cấu trúc nội dung văn bản cần được kiểm tra và bổ sung đầy đủ trước khi đưa vào quy trình tiền xử lý, chunking và indexing.

---

## 3. Các nhóm lỗi cần kiểm tra

### 01. Lỗi thiếu metadata

- Thiếu số hiệu văn bản (`document_number`).
- Thiếu tên văn bản (`title`).
- Thiếu ngày ban hành hoặc ngày hiệu lực.
- Thiếu cơ quan ban hành, lĩnh vực hoặc nguồn.

### 02. Lỗi định danh và trùng lặp

- Trùng `document_id`.
- Trùng số hiệu văn bản.
- Một văn bản có nhiều cách ghi số hiệu.
- Mã định danh không thống nhất giữa các file.

### 03. Lỗi thông tin pháp lý

- Ngày hiệu lực không hợp lý hoặc bị thiếu.
- Trạng thái hiệu lực chưa rõ.
- Thiếu thông tin văn bản sửa đổi, bổ sung hoặc thay thế.
- Thông tin cơ quan ban hành chưa thống nhất.

### 04. Lỗi file văn bản gốc

- Thiếu file tương ứng với metadata.
- `file_path` sai hoặc không tồn tại.
- File PDF bị lỗi, không mở được.
- PDF scan không trích xuất được văn bản.
- File trích xuất bị mất dấu tiếng Việt hoặc sai thứ tự nội dung.

### 05. Lỗi cấu trúc và khả năng truy xuất RAG

- Không xác định được Chương, Điều, Khoản.
- Số Điều bị mất hoặc sai khi trích xuất.
- Nội dung bị lặp do header/footer.
- Không truy ngược được đoạn nội dung về văn bản nguồn.

---

## 4. Bảng thống kê lỗi

| STT | Loại lỗi | Số lượng | Mức độ | Hướng xử lý |
|---|---|---:|---|---|
| 1 | Thiếu metadata | Chưa kiểm tra | Trung bình | Bổ sung |
| 2 | Trùng mã định danh | Chưa kiểm tra | Cao | Chuẩn hóa ID |
| 3 | Thiếu file gốc | 0 | Cao | Bổ sung file |
| 4 | Sai đường dẫn file | 0 | Cao | Sửa `file_path` |
| 5 | Lỗi trích xuất PDF | Chưa kiểm tra | Cao | Trích xuất lại |
| 6 | Thiếu cấu trúc Điều/Khoản | Chưa kiểm tra | Cao | Kiểm tra và xử lý |

> Ghi chú: Không điền số lượng ước tính nếu chưa kiểm tra thực tế. Nếu chưa phát hiện lỗi, ghi `0`; nếu chưa kiểm tra, ghi `Chưa kiểm tra`.

---

## 6. Đánh giá chất lượng và kết luận

### 1. Dữ liệu hiện tại có những lỗi gì và lỗi nào nghiêm trọng?

Về mặt hiện trạng, dữ liệu đã có cơ sở tổ chức đường dẫn rõ ràng và các file gốc đang tồn tại. Tuy nhiên, các lỗi nghiêm trọng cần ưu tiên là:

- Thiếu metadata bắt buộc cho toàn bộ hồ sơ.
- Chưa kiểm tra đồng bộ hóa `document_id`, số hiệu văn bản và tên văn bản.
- Chưa kiểm tra kỹ thuật trích xuất PDF và cấu trúc Điều/Khoản.
- Chưa xác nhận khả năng truy ngược đoạn văn bản về nguồn gốc trong pipeline RAG.

Các lỗi nghiêm trọng nhất vẫn là các vấn đề thuộc nhóm thiếu metadata, trích xuất PDF và cấu trúc Điều/Khoản, vì chúng trực tiếp ảnh hưởng đến chất lượng truy xuất và độ tin cậy của kết quả trả lời.

### 2. Những lỗi nào đã sửa, lỗi nào còn tồn tại?

Đã sửa:

- Cấu trúc thư mục dữ liệu đã được tổ chức lại theo chuẩn.
- File README và template metadata được tạo để thống nhất định dạng dữ liệu.
- File báo cáo chất lượng dữ liệu đã được chuẩn hóa theo mẫu.

Còn tồn tại:

- Metadata chưa được điền đầy đủ cho toàn bộ văn bản.
- Chưa có kiểm tra toàn bộ tập dữ liệu cho trùng lặp `document_id` và trùng số hiệu văn bản.
- Chưa kiểm tra PDF có trích xuất được văn bản và có giữ nguyên dấu tiếng Việt hay không.
- Chưa xác định chắc chắn cấu trúc Chương/Điều/Khoản cho từng văn bản.

### 3. Dữ liệu đã sẵn sàng cho bước tiền xử lý, chunking và indexing chưa?

Chưa sẵn sàng hoàn toàn.

Dữ liệu hiện mới đáp ứng được giai đoạn tổ chức thư mục và chuẩn hóa cơ bản. Tuy nhiên, để bước vào tiền xử lý, chunking và indexing, cần thực hiện các công việc sau:

1. Hoàn thiện metadata bắt buộc cho từng văn bản.
2. Kiểm tra đồng bộ `document_id`, số hiệu và tên văn bản.
3. Đảm bảo file PDF mở được và trích xuất tiếng Việt chính xác.
4. Xác định cấu trúc Chương/Điều/Khoản trước khi tạo chunk.
5. Kiểm tra lại tính toàn vẹn của `file_path` và liên kết với dữ liệu gốc.

### Kết luận

Dữ liệu hiện tại có mức độ tổ chức cơ bản khá tốt, nhưng chưa đủ điều kiện để đưa trực tiếp vào pipeline RAG ở giai đoạn producción. Các vấn đề chính cần giải quyết trước là metadata, trích xuất PDF, định danh văn bản và cấu trúc tài liệu. Khi các bước này được hoàn tất, dữ liệu mới có thể sẵn sàng cho tiền xử lý, chunking và indexing.

---

**Project:** Vietnam Legal RAG Assistant  
**Report date:** 2026-10-02
