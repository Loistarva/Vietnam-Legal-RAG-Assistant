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

Hệ thống sử dụng bảng ánh xạ chuẩn hóa chính thức giữa mã file quản lý (`file_code`), định danh hệ thống slug (`document_id`), và số hiệu văn bản:

| Mã File (`file_code`) | Định danh hệ thống (`document_id`) | Số hiệu văn bản (`document_number`) | Trạng thái hiệu lực | Tên văn bản |
| :--- | :--- | :--- | :--- | :--- |
| **L01** | `l_52_2014_qh13` | 52/2014/QH13 | Còn hiệu lực | Luật Hôn nhân và gia đình 2014 |
| **ND01** | `nd_126_2014_nd_cp` | 126/2014/NĐ-CP | Sửa đổi bổ sung | Nghị định quy định chi tiết một số điều và biện pháp thi hành Luật HNGĐ |
| **ND02** | `nd_207_2025_nd_cp` | 207/2025/NĐ-CP | Còn hiệu lực | Nghị định sinh con bằng kỹ thuật hỗ trợ sinh sản và mang thai hộ |
| **ND03** | `nq_01_2024_nq_hdtp` | 01/2024/NQ-HĐTP | Còn hiệu lực | Nghị quyết hướng dẫn áp dụng quy định giải quyết vụ việc hôn nhân và gia đình |
| **TT01** | `ttlt_01_2016_ttlt_tandtc` | 01/2016/TTLT-TANDTC-VKSNDTC-BTP | Còn hiệu lực | Thông tư liên tịch hướng dẫn một số quy định của Luật HNGĐ |
| **TT02** | `tt_02a_2015_tt_btp` | 02a/2015/TT-BTP | Hết hiệu lực | Thông tư hướng dẫn một số điều Nghị định 126/2014/NĐ-CP |
| **TT03** | `tt_32_2016_tt_byt` | 32/2016/TT-BYT | Còn hiệu lực | Thông tư quy định liên quan đến hỗ trợ sinh sản |
| **TT04** | `tt_34_2017_tt_byt` | 34/2017/TT-BYT | Sửa đổi bổ sung | Thông tư tư vấn, sàng lọc, chẩn đoán, điều trị trước sinh và sơ sinh |
| **L02** | `l_22_2000_qh10` | 22/2000/QH10 | Hết hiệu lực | Luật Hôn nhân và gia đình 2000 |
| **ND04** | `nd_10_2015_nd_cp` | 10/2015/NĐ-CP | Hết hiệu lực | Nghị định quy định về sinh con bằng kỹ thuật thụ tinh trong ống nghiệm |
| **ND05** | `nd_70_2001_nd_cp` | 70/2001/NĐ-CP | Hết hiệu lực | Nghị định quy định chi tiết thi hành Luật Hôn nhân và gia đình 2000 |

Quy tắc định danh cấu trúc phân cấp:
- **Article ID**: `[document_id]_art_[số_điều]` (Ví dụ: `l_52_2014_qh13_art_8`). Mã quản lý tương ứng: `L01_D08`.
- **Clause ID**: `[article_id]_clause_[số_khoản]` (Ví dụ: `l_52_2014_qh13_art_8_clause_1`).
- **Chunk ID**: `[clause_id]_chunk_[chỉ_số]` (Ví dụ: `l_52_2014_qh13_art_8_clause_1_chunk_1`).

Các mã này được tạo tự động trong quá trình xử lý dữ liệu, không yêu cầu phải đổi tên file PDF gốc.
Không sử dụng cùng một document_id cho hai văn bản khác nhau.

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
