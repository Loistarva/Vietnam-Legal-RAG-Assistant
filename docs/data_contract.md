# HỢP ĐỒNG DỮ LIỆU (DATA CONTRACT) - HỆ THỐNG LEGAL AI RAG
**Phiên bản:** 2.0 (Kiến trúc 4 tầng)
**Mục đích:** Quy định cấu trúc JSON giao tiếp chuẩn mực giữa Module Parser (Trích xuất) và Module Chunking & Embedding (Phân mảnh và Nhúng).

---

## 1. Kiến trúc Phân cấp (4-Tier Hierarchy)
Dữ liệu văn bản pháp luật truyền tải trong hệ thống bắt buộc tuân thủ cấu trúc cây 4 tầng:
`Document` ➔ `Article` (Điều) ➔ `Clause` (Khoản) ➔ `Chunk` (Đoạn/Điểm).

---

## 2. Quy ước Định danh (Semantic ID Convention)
Tất cả các ID trong hệ thống đóng vai trò là Khóa chính/Khóa ngoại để khôi phục ngữ cảnh (Parent-Child context). ID phải viết thường, không dấu, không khoảng trắng, chỉ dùng ký tự `[a-zA-Z0-9_]`.


*   **Document ID:** `[loại_văn_bản]_[số_hiệu đầy đủ]` (VD: Nghị định 100/2019/NĐ-CP `nd_100_2019_nd_cp`)
*   **Article ID:** `[document_id]_art_[số_điều]` (VD: Điều 6 `nd_100_2019_nd_cp_art_6`)
*   **Clause ID:** `[article_id]_clause_[số_khoản]` (VD: Khoản 2 `nd_100_2019_nd_cp_art_6_clause_2`)
*   **Chunk ID:** `[clause_id]_chunk_[số_thứ_tự_hoặc_điểm]` (VD: `nd_100_2019_nd_cp_art_6_clause_2_chunk_1`)
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

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation)                                                                                       |
| :--- | :--- | :---: |:---------------------------------------------------------------------------------------------------------------------|
| `title` | String | **Có** | Tên văn bản. Ràng buộc: `minLength: 5`.                                                                              |
| `document_type` | String | **Có** | Enum: `["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị"]`.                                                  |
| `document_number` | String | **Có** | Số hiệu văn bản (VD: "100/2019/NĐ-CP").                                                                              |
| `issue_date` | Date | **Có** | Ngày ban hành. Định dạng chuẩn: `YYYY-MM-DD`.                                                                        |
| `effective_date` | Date | **Có** | Ngày có hiệu lực. Định dạng chuẩn: `YYYY-MM-DD`.                                                                     |
| `expiry_date` | Date / Null | Không | Ngày hết hiệu lực (hoặc `null` nếu còn hiệu lực). Định dạng chuẩn: `YYYY-MM-DD`.                                      |
| `source_url` | String | Không | Đường dẫn URL chính thức tra cứu văn bản pháp luật.                                                                 |
| `issuing_body` | String | **Có** | Cơ quan ban hành (VD: "Chính phủ").                                                                                  |
| `validity_status` | String | **Có** | Enum: `["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung", "Không xác định"]`. |

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
| `chunk_id` | String | **Có** | ID duy nhất của Chunk. Định dạng chuẩn: `{clause_id}_chunk_{idx}`. |
| `parent_clause_id` | String | **Có** | Khóa ngoại. Bắt buộc phải khớp chính xác với `clause_id` chứa nó. |
| `clause_id` | String | **Có** | Định danh của Khoản cha. |
| `article_id` | String | **Có** | Định danh của Điều chứa Khoản. |
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
   * Chunker không tự loại văn bản theo `validity_status`; trạng thái được giữ trong metadata để hệ thống retrieval lọc theo thời điểm câu hỏi. Nếu nghiệp vụ chỉ chọn văn bản còn hiệu lực, bộ chọn corpus phải áp dụng điều kiện đó trước khi export.

## 5. Hợp đồng đầu ra Child Chunk JSONL

Parser giữ nguyên JSON nguồn và không cần ghi chunks ngược vào `clauses[].chunks`. Exporter tạo một bản ghi Child Chunk độc lập trên mỗi dòng tại `data/chunking_output/chunks.jsonl`; cấu trúc bản ghi được mô tả trong [`schemas/chunk_payload_schema.json`](../schemas/chunk_payload_schema.json).

### 5.1. Định danh và Khóa ngoại bắt buộc ở cấp Root
* **`chunk_id` / `id`**: ID duy nhất của Child Chunk theo định dạng chuẩn: `{clause_id}_chunk_{idx}` (trong đó `idx` đếm tuần tự từ 1 trong phạm vi từng Khoản).
* **`parent_clause_id`**: Khóa ngoại bắt buộc, trỏ chính xác đến `clause_id` của Khoản chứa chunk (`parent_clause_id == clause_id`).
* **`clause_id`**: Khóa định danh của Khoản cha chứa chunk.
* **`article_id`**: Khóa định danh của Điều chứa Khoản.
* **`parent_id`**: Khóa ngoại trỏ đến một ParentChunk trong `data/chunking_output/parents.json`, và danh sách `child_ids` của Parent phải khớp với các Child.
* **`doc_id` / `document_id`**: Khóa định danh của Văn bản pháp luật.

Các cặp trường `id`/`chunk_id`, `doc_id`/`document_id` và `text`/`chunk_text` là các alias tương thích tích hợp và phải có giá trị bằng nhau.

### 5.2. Nội dung và Embedding
* **`chunk_text`**: Nội dung văn bản của chunk. Ràng buộc: `minLength: 10`, tuyệt đối không chứa ký tự null byte (`\x00`). Nếu đoạn đuôi cắt cuối cùng trong một Khoản có độ dài dưới 10 ký tự, engine chunking tự động gộp vào chunk liền trước để tránh sinh chunk vụn.
* **`seg_text`**: Nội dung đã tách từ tiếng Việt (Underthesea).
* **`embed_text`**: Chuỗi kết hợp tiêu đề, breadcrumb và nội dung đã tách từ phục vụ sinh vector dense embedding.
* **`embed_text_raw`** *(Tùy chọn)*: Chuỗi text kết hợp thô trước khi tách từ.
* **`point_ref`**: Tùy chọn (`["string", "null"]`), chứa thông tin Điểm nếu có hoặc `null`.

### 5.3. Metadata mở rộng
Trường `metadata` chứa metadata của văn bản cùng `chapter`, `section`, `article_number`, và các trường mở rộng phục vụ lọc downstream: `document_title`, `clause_number`, `source_url`, `effective_from`, `effective_to`.

---

## 6. Bảng Ánh xạ Định danh Văn bản (Document ID Mapping Registry)

Bảng ánh xạ chuẩn hóa chính thức giữa mã file quản lý (`file_code`), định danh hệ thống slug (`document_id`), số hiệu văn bản pháp luật, tên văn bản và trạng thái hiệu lực:

| Mã File (`file_code`) | Định danh hệ thống (`document_id`) | Số hiệu văn bản (`document_number`) | Trạng thái hiệu lực (`validity_status`) | Tên văn bản |
| :--- | :--- | :--- | :--- | :--- |
| **L01** | `l_52_2014_qh13` | 52/2014/QH13 | Còn hiệu lực | Luật Hôn nhân và gia đình 2014 |
| **ND01** | `nd_126_2014_nd_cp` | 126/2014/NĐ-CP | Sửa đổi bổ sung | Nghị định quy định chi tiết một số điều và biện pháp thi hành Luật HNGĐ |
| **ND02** | `nd_207_2025_nd_cp` | 207/2025/NĐ-CP | Còn hiệu lực | Nghị định sinh con bằng kỹ thuật hỗ trợ sinh sản và điều kiện mang thai hộ |
| **ND03** | `nq_01_2024_nq_hdtp` | 01/2024/NQ-HĐTP | Còn hiệu lực | Nghị quyết hướng dẫn áp dụng quy định giải quyết vụ việc hôn nhân và gia đình |
| **TT01** | `ttlt_01_2016_ttlt_tandtc` | 01/2016/TTLT-TANDTC-VKSNDTC-BTP | Còn hiệu lực | Thông tư liên tịch hướng dẫn một số quy định của Luật Hôn nhân và gia đình |
| **TT02** | `tt_02a_2015_tt_btp` | 02a/2015/TT-BTP | Hết hiệu lực | Thông tư hướng dẫn một số điều Nghị định 126/2014/NĐ-CP |
| **TT03** | `tt_32_2016_tt_byt` | 32/2016/TT-BYT | Còn hiệu lực | Thông tư quy định liên quan đến hỗ trợ sinh sản |
| **TT04** | `tt_34_2017_tt_byt` | 34/2017/TT-BYT | Sửa đổi bổ sung | Thông tư tư vấn, sàng lọc, chẩn đoán, điều trị trước sinh và sơ sinh |
| **L02** | `l_22_2000_qh10` | 22/2000/QH10 | Hết hiệu lực | Luật Hôn nhân và gia đình 2000 |
| **ND04** | `nd_10_2015_nd_cp` | 10/2015/NĐ-CP | Hết hiệu lực | Nghị định quy định về sinh con bằng kỹ thuật thụ tinh trong ống nghiệm |
| **ND05** | `nd_70_2001_nd_cp` | 70/2001/NĐ-CP | Hết hiệu lực | Nghị định quy định chi tiết thi hành Luật Hôn nhân và gia đình 2000 |
