# DATA - Legal RAG Assistant

## 1. Mục tiêu

Thư mục `data/` là nơi lưu trữ dữ liệu pháp luật đầu vào, metadata và báo cáo chất lượng cho dự án Vietnam Legal RAG Assistant.

Dữ liệu được tổ chức theo từng loại văn bản và được dùng cho quá trình dựng Knowledge Base, trích xuất nội dung, chia chunk và lưu trữ embedding phục vụ truy xuất trong pipeline RAG.

## 2. Cấu trúc thư mục chuẩn

```text
data/
├── README.md
├── legal_documents_master.xlsx
├── data_quality_report.docx
├── raw_data/
│   ├── README.md
│   ├── laws_and_decrees/
│   │   ├── L01.pdf
│   │   ├── ND01.pdf
│   │   ├── ND02.pdf
│   │   └── ND03.pdf
│   └── circulars/
│       ├── TT01.pdf
│       ├── TT02.pdf
│       ├── TT03.pdf
│       └── TT04.pdf
└── ...
```

## 3. Mô tả từng thành phần

| Thành phần | Chức năng |
|---|---|
| `README.md` | Tài liệu mô tả cấu trúc dữ liệu và chuẩn quản lý dữ liệu. |
| `legal_documents_master.xlsx` | Bảng kiểm kê tổng hợp metadata của tất cả văn bản pháp luật trong hệ thống. |
| `data_quality_report.docx` | Báo cáo kiểm tra chất lượng dữ liệu và trạng thái xử lý lỗi. |
| `raw_data/` | Thư mục chứa file gốc đầy đủ, không chỉnh sửa nội dung pháp luật. |
| `raw_data/laws_and_decrees/` | Lưu các file Luật và Nghị định. |
| `raw_data/circulars/` | Lưu các file Thông tư. |

## 4. Quy tắc quản lý dữ liệu

### 4.1. Dữ liệu gốc

- Giữ nguyên file PDF/DOCX gốc, không chỉnh sửa nội dung pháp luật.
- File phải nằm trong đúng thư mục theo loại văn bản.
- Tên file nên được đặt theo `document_id` đã thống nhất nếu có.
- Không trùng lặp văn bản ngoài ý muốn.

### 4.2. Metadata

File `legal_documents_master.xlsx` là danh mục trung tâm và phải chứa các trường bắt buộc sau:

- `document_id`
- `document_type`
- `document_name`
- `issuing_authority`
- `promulgation_date`
- `effective_date`
- `source`
- `file_path`
- `status`
- `notes`

### 4.3. Định danh điều/chunk

Khi xử lý pipeline, hệ thống sẽ sinh các mã định danh như:

- `L01_D01` → Điều 1 của văn bản `L01`
- `L01_D02_C01` → Chunk 1 của Điều 2 của văn bản `L01`

Mỗi `document_id` phải là duy nhất trong toàn bộ hệ thống.

## 5. Quy trình bổ sung dữ liệu

1. Nhận file văn bản pháp luật.
2. Xác định loại văn bản: Luật, Nghị định hoặc Thông tư.
3. Gán `document_id` theo chuẩn thống nhất.
4. Lưu file vào đúng thư mục trong `raw_data/`.
5. Cập nhật metadata trong `legal_documents_master.xlsx`.
6. Kiểm tra chất lượng dữ liệu và ghi lỗi vào `data_quality_report.docx`.

## 6. Tiêu chí kiểm tra chất lượng

- File tồn tại và mở được.
- Định dạng phù hợp với quy trình xử lý.
- Không có file trùng lặp.
- `document_id` không bị trùng.
- Metadata đầy đủ và chính xác.
- Đường dẫn file khớp với bảng kiểm kê.
- Nguồn và tình trạng hiệu lực được xác minh.

## 7. Mẫu metadata chuẩn

Mẫu dữ liệu tối thiểu:

| document_id | document_type | document_name | issuing_authority | promulgation_date | effective_date | source | file_path | status | notes |
|---|---|---|---|---|---|---|---|---|---|
| L01 | Luật | Luật ... | Quốc hội | 2024-01-01 | 2024-02-01 | Cổng thông tin chính phủ | raw_data/laws_and_decrees/L01.pdf | active | Dữ liệu hợp lệ |
| ND01 | Nghị định | Nghị định ... | Chính phủ | 2024-03-01 | 2024-04-01 | Cổng thông tin Chính phủ | raw_data/laws_and_decrees/ND01.pdf | active | Dữ liệu hợp lệ |
| TT01 | Thông tư | Thông tư ... | Bộ Tài chính | 2024-05-01 | 2024-06-01 | Cổng thông tin Bộ | raw_data/circulars/TT01.pdf | active | Dữ liệu hợp lệ |

## 8. Lưu ý

- Không thay đổi `document_id` sau khi đã dùng trong pipeline.
- Khi bổ sung hoặc thay thế văn bản mới, phải cập nhật bảng kiểm kê và báo cáo chất lượng.
- Chỉ dùng văn bản đã được kiểm tra và xác minh metadata mới cho hệ thống chính thức.

---
**Project:** Vietnam Legal RAG Assistant
**Directory:** data/
**Purpose:** Legal document storage, metadata management, and data quality tracking
