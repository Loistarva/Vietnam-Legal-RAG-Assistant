# HỢP ĐỒNG DỮ LIỆU (DATA CONTRACT) - HỆ THỐNG LEGAL AI RAG
**Phiên bản:** 2.0 (Kiến trúc 4 tầng)
**Mục đích:** Quy định cấu trúc JSON giao tiếp chuẩn mực giữa Module Parser (Trích xuất) và Module Chunking & Embedding (Phân mảnh và Nhúng).

---

## 1. Kiến trúc Phân cấp (4-Tier Hierarchy)
Dữ liệu văn bản pháp luật truyền tải trong hệ thống bắt buộc tuân thủ cấu trúc cây 4 tầng:
`Document` ➔ `Article` (Điều) ➔ `Clause` (Khoản) ➔ `Chunk` (Đoạn/Điểm).

---

## 2. Quy ước Định danh (Semantic ID Convention)
Tất cả các ID trong hệ thống đóng vai trò là Khóa chính/Khóa ngoại để khôi phục ngữ cảnh (Parent-Child context). ID phải viết thường (hoặc hoa), không dấu, không khoảng trắng, chỉ dùng ký tự `[a-zA-Z0-9_]`.

*   **Document ID:** `[loại_văn_bản]_[số_hiệu]_[năm]` (VD: `nd_100_2019_nd_cp`)
*   **Article ID:** `[document_id]_art_[số_điều]` (VD: `nd_100_2019_nd_cp_art_6`)
*   **Clause ID:** `[article_id]_clause_[số_khoản]` (VD: `nd_100_2019_nd_cp_art_6_clause_2`)
*   **Chunk ID:** `[clause_id]_chunk_[số_thứ_tự_hoặc_điểm]` (VD: `nd_100_2019_nd_cp_art_6_clause_2_chunk_b`)

---

## 3. Đặc tả Chi tiết Đối tượng (Entity Specifications)

### 3.1. Cấp độ Document (Văn bản) & Metadata
*Thực thể gốc chứa toàn bộ thông tin của một văn bản pháp luật.*

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation) |
| :--- | :--- | :---: | :--- |
| `document_id` | String | **Có** | ID duy nhất của văn bản. Regex: `^[a-zA-Z0-9_]+$` |
| `metadata` | Object | **Có** | Xem chi tiết cấu trúc `Metadata` bên dưới. |
| `articles` | Array | **Có** | Danh sách các Điều luật. Ràng buộc: Tối thiểu 1 phần tử (`minItems: 1`). |
| `footnotes` | Array[String] | Không | Danh sách các chú thích, giải nghĩa từ ngữ gắn ở cuối văn bản. Mặc định là mảng rỗng `[]`. |

**Cấu trúc `metadata`:**

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation) |
| :--- | :--- | :---: | :--- |
| `title` | String | **Có** | Tên văn bản. Ràng buộc: `minLength: 5`. |
| `document_type` | String | **Có** | Enum: `["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị"]`. |
| `document_number` | String | **Có** | Số hiệu văn bản (VD: "100/2019/NĐ-CP"). |
| `issue_date` | Date | **Có** | Ngày ban hành. Định dạng chuẩn: `YYYY-MM-DD`. |
| `effective_date` | Date | **Có** | Ngày có hiệu lực. Định dạng chuẩn: `YYYY-MM-DD`. |
| `issuing_body` | String | **Có** | Cơ quan ban hành (VD: "Chính phủ"). |
| `validity_status` | String | **Có** | Enum: `["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung"]`. |

### 3.2. Cấp độ Article (Điều luật)
*Nhóm logic cung cấp ngữ cảnh cha cho các Khoản bên trong.*

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation) |
| :--- | :--- | :---: | :--- |
| `article_id` | String | **Có** | Phải chứa `document_id` ở tiền tố. |
| `article_number` | String | **Có** | Số thứ tự của Điều (VD: "6"). |
| `article_title` | String | Không | Tên/Tiêu đề của Điều (VD: "Xử phạt người điều khiển xe..."). Nếu không có thì để `null`. |
| `chapter` | String | Không | Chương chứa Điều này (VD: "Chương I"). |
| `section` | String | Không | Mục chứa Điều này. |
| `intro` | String | Không | Đoạn văn bản mở đầu Điều trước khi vào các Khoản. |
| `clauses` | Array | **Có** | Danh sách các Khoản. Ràng buộc: `minItems: 1`. |

### 3.3. Cấp độ Clause (Khoản luật) - Điểm giao tiếp Parser & Chunker
*Đơn vị trích xuất cơ bản nhất của Parser.*

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation) |
| :--- | :--- | :---: | :--- |
| `clause_id` | String | **Có** | ID duy nhất của Khoản. |
| `parent_article_id`| String | **Có** | Khóa ngoại. Bắt buộc phải khớp chính xác với `article_id` chứa nó. |
| `clause_number` | String | **Có** | Số thứ tự Khoản (VD: "2"). |
| `clause_text` | String | **Có** | Nội dung chữ thô của toàn bộ Khoản. Ràng buộc: `minLength: 1`, đã được xóa bỏ null byte (`\x00`). |
| `chunks` | Array | **Tùy chọn** | **Parser:** Bỏ qua hoặc để `null`.<br>**Chunker:** Điền danh sách các Chunk sau khi phân mảnh. |

### 3.4. Cấp độ Chunk (Đoạn/Điểm phân mảnh)
*Đơn vị ngữ nghĩa lưu vào Vector DB (Qdrant/Elasticsearch).*

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation) |
| :--- | :--- | :---: | :--- |
| `chunk_id` | String | **Có** | ID duy nhất của Chunk. |
| `parent_clause_id` | String | **Có** | Khóa ngoại. Bắt buộc phải khớp chính xác với `clause_id` chứa nó. |
| `clause_number` | String | Không | Sao chép từ Clause cha xuống để dễ truy xuất. |
| `point_letter` | String | Không | Chữ cái của Điểm (VD: "a", "b", "c"). |
| `chunk_text` | String | **Có** | Nội dung đã cắt nhỏ. Ràng buộc: `minLength: 10`, tuyệt đối không chứa ký tự null byte. |
| `char_count` | Integer | Không | Tổng số ký tự của `chunk_text`. |

---

## 4. Giao thức phối hợp (Workflow Protocol)

1. **Giai đoạn 1: Parser (Trích xuất cấu trúc)**
   * Module Parser đọc PDF/HTML và xuất ra JSON tuân thủ chuẩn này đến tầng `Clause`.
   * **Bắt buộc:** Phải làm sạch ký tự rác, không chứa ký tự `\x00` trong chuỗi text.
   * **Cho phép:** Trường `chunks` tại tầng `Clause` được phép để `null`.
2. **Giai đoạn 2: Chunker (Chia nhỏ ngữ nghĩa)**
   * Module Chunking đọc JSON từ Parser, lấy dữ liệu từ `clause_text`.
   * Dựa vào chiến lược độ dài token (Token limit), chia `clause_text` thành nhiều đối tượng `Chunk` và nạp vào mảng `chunks`.
   * Gắn đúng `parent_clause_id` để kết nối lại thành cây.
3. **Quy tắc Ngoại lệ (Edge Cases):**
   * Nếu một Điều luật không phân chia thành các Khoản (chỉ có một đoạn văn duy nhất), Parser vẫn phải khởi tạo một Clause (VD: `clause_number: "1"`) để bọc lấy đoạn văn đó, giữ vững tính toàn vẹn của cây 4 tầng.
   * Document có `validity_status` là `"Hết hiệu lực"` sẽ không được đưa vào tiến trình Chunking & Embedding.