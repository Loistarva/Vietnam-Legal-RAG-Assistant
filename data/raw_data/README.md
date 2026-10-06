# DATA - Legal RAG Assistant

## 1. Giới thiệu

Thư mục `data/` lưu trữ và quản lý dữ liệu pháp luật đầu vào cho dự án Legal RAG Assistant.

Dữ liệu được sử dụng để xây dựng Knowledge Base (KB), phục vụ quá trình truy xuất thông tin và trả lời câu hỏi pháp luật bằng Retrieval-Augmented Generation (RAG).

## 2. Cấu trúc thư mục

```text
data/
├── raw_data/
│   ├── laws_and_decrees/
│   └── circulars/
├── legal_documents_master.xlsx
├── data_quality_report.docx
└── README.md
```

### Mô tả

| Thành phần | Chức năng |
|---|---|
| `raw_data/` | Lưu trữ các văn bản pháp luật gốc. |
| `laws_and_decrees/` | Chứa các file Luật và Nghị định. |
| `circulars/` | Chứa các file Thông tư. |
| `legal_documents_master.xlsx` | Danh mục tổng hợp và metadata của văn bản pháp luật. |
| `data_quality_report.docx` | Báo cáo kết quả kiểm tra chất lượng dữ liệu. |
| `README.md` | Hướng dẫn tổ chức, đặt tên và quản lý dữ liệu. |

## 3. Quy tắc đặt tên file
### 3.1. Quy tắc quản lý tên file văn bản gốc

Các văn bản pháp luật được lưu dưới dạng file PDF/DOCX , bao gồm đầy đủ các Chương, Điều, Khoản. 

- Giữ nguyên tên file gốc nếu đã lấy trên thư viện pháp luật.
- Đường dẫn file phải được ghi chính xác trong bảng kiểm kê.

Ví dụ:

```text
raw_data/
├── laws_and_decrees/
│   ├── [các file Luật và Nghị định gốc]
│   └── ...
└── circulars/
    ├── [các file Thông tư gốc]
    └── ...
```

### 3.2. Quy tắc định danh Điều và chunk

Khi xử lý dữ liệu để xây dựng Knowledge Base, hệ thống sẽ trích xuất nội dung từ file gốc và tạo mã định danh cho từng Điều hoặc chunk.

Ví dụ:

- `L01_D01`: Điều 1 của văn bản có `document_id = L01`.
- `L01_D02`: Điều 2 của văn bản có `document_id = L01`.
- `L01_D02_C01`: Chunk 1 của Điều 2.

Các mã này được tạo trong quá trình xử lý dữ liệu, không yêu cầu phải đổi tên file PDF gốc.
Không sử dụng cùng một document_id cho hai văn bản khác nhau. Khi đổi tên file, cần cập nhật đường dẫn tương ứng trong bảng kiểm kê.

## 4. Bảng kiểm kê văn bản

File `legal_documents_master.xlsx` là danh mục quản lý tập trung cho các văn bản trong hệ thống.

Bảng cần thống nhất mã định danh, loại văn bản, thông tin ban hành, hiệu lực, nguồn và đường dẫn file gốc theo các trường metadata mà nhóm đã thống nhất.

Mỗi văn bản cần có bản ghi tương ứng trong bảng kiểm kê. Không xem mỗi dòng metadata ở cấp Điều hoặc Khoản là một văn bản pháp luật độc lập.

## 5. Quy trình bổ sung dữ liệu

1. Nhận file văn bản pháp luật từ thành viên phụ trách.
2. Xác định loại văn bản: Luật, Nghị định hoặc Thông tư.
3. Đặt tên file theo document_id đã thống nhất.
4. Lưu file vào đúng thư mục trong `raw_data/`.
5. Kiểm tra file có mở được và nội dung có đầy đủ hay không.
6. Đối chiếu thông tin với `legal_documents_master.xlsx`.
7. Ghi nhận lỗi hoặc metadata còn thiếu trong `data_quality_report.docx`.

## 6. Kiểm tra chất lượng dữ liệu

Các tiêu chí kiểm tra:

- File tồn tại và mở được.
- Định dạng file phù hợp với quy trình xử lý.
- Không có file trùng lặp ngoài ý muốn.
- document_id không bị trùng.
- Metadata bắt buộc được điền đầy đủ.
- Tên file và đường dẫn khớp với bảng kiểm kê.
- Văn bản có thông tin nguồn và tình trạng hiệu lực để đối chiếu.

Các lỗi phát hiện cần được ghi lại, kèm document_id, mô tả lỗi và trạng thái xử lý.

## 7. Sử dụng dữ liệu trong pipeline RAG

Dữ liệu trong `raw_data/` là nguồn đầu vào cho pipeline xử lý văn bản.

Quy trình dự kiến:

1. Đọc file văn bản pháp luật.
2. Trích xuất nội dung.
3. Phân tích cấu trúc văn bản như Chương, Điều, Khoản và Điểm.
4. Chia nội dung thành các đoạn (chunks).
5. Gắn metadata và mã định danh nguồn.
6. Tạo embedding và lập chỉ mục để phục vụ truy xuất trong Knowledge Base.

Bảng kiểm kê hỗ trợ quản lý và liên kết metadata; nội dung dùng để truy xuất được lấy từ văn bản gốc sau khi xử lý.

## 8. Nguyên tắc quản lý

- Giữ nguyên file gốc, không chỉnh sửa trực tiếp nội dung pháp luật.
- Không tự ý thay đổi document_id sau khi đã được sử dụng trong pipeline.
- Khi bổ sung hoặc thay thế văn bản, cập nhật bảng kiểm kê và báo cáo chất lượng.
- Kiểm tra nguồn và tình trạng hiệu lực của văn bản trước khi sử dụng làm căn cứ trả lời.
- Không đưa file chưa kiểm tra vào bộ dữ liệu chính thức.

---
**Project:** Vietnam Legal RAG Assistant  
**Directory:** data/  
**Purpose:** Legal document storage and metadata management