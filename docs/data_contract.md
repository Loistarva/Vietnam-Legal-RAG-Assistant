# HỢP ĐỒNG DỮ LIỆU (DATA CONTRACT) - HỆ THỐNG LEGAL AI RAG
**Phiên bản:** 2.0 (Kiến trúc 4 tầng)
**Mục đích:** Quy định cấu trúc JSON giao tiếp chuẩn mực giữa Module Parser (Trích xuất) và Module Chunking & Embedding (Phân mảnh và Nhúng).

---

## 1. Kiến trúc Phân cấp (4-Tier Hierarchy)
Dữ liệu văn bản pháp luật truyền tải trong hệ thống bắt buộc tuân thủ cấu trúc cây 4 tầng:
`Document` ➔ `Article` (Điều) ➔ `Clause` (Khoản) ➔ `Chunk` (Đoạn/Điểm).

---

## 2. Quy ước Định danh (Semantic ID Convention)
Tất cả các ID trong hệ thống đóng vai trò là Khóa chính/Khóa ngoại để khôi phục ngữ cảnh (Parent-Child context). ID phải viết thường, không dấu, không khoảng trắng, chỉ dùng ký tự `[a-z0-9_]`.


*   **Document ID:** Trường `document_id` được lấy trực tiếp từ `data/reference/document_versions.json`; bảng ở Mục 6 trích các văn bản đang có trong corpus. Quy tắc `[loại_văn_bản]_[số_hiệu đầy đủ]` chỉ dùng để đặt ID khi thêm văn bản mới vào registry; ID đã có trong registry không đổi (ghi nhận ngoại lệ rút gọn `ttlt_01_2016_ttlt_tandtc`).
*   **Article ID:** `[document_id]_art_[số_điều]` (VD: Điều 6 `nd_100_2019_nd_cp_art_6`). Lưu ý: `data/reference/article_index.json` là bảng nối chính thức giữa mã Điều của benchmark (`gold_article_ids`) và `article_id` dạng slug của corpus.
*   **Clause ID:** `[article_id]_clause_[số_khoản]` (VD: Khoản 2 `nd_100_2019_nd_cp_art_6_clause_2`)
*   **Chunk ID:** `[clause_id]_chunk_[số_thứ_tự_hoặc_điểm]` (VD: `nd_100_2019_nd_cp_art_6_clause_2_chunk_1`)
---

## 3. Đặc tả Chi tiết Đối tượng (Entity Specifications)

### 3.1. Cấp độ Document (Văn bản) & Metadata
*Thực thể gốc chứa toàn bộ thông tin của một văn bản pháp luật.*

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation) |
| :--- | :--- | :---: | :--- |
| `document_id` | String | **Có** | ID duy nhất của văn bản. Regex: `^[a-z0-9_]+$` |
| `metadata` | Object | **Có** | Xem chi tiết cấu trúc `Metadata` bên dưới. |
| `articles` | Array | **Có** | Danh sách các Điều luật. Ràng buộc: Tối thiểu 1 phần tử (`minItems: 1`). |
| `footnotes` | Array[String] | Không | Danh sách các chú thích, giải nghĩa từ ngữ gắn ở cuối văn bản. Mặc định là mảng rỗng `[]`. |

**Cấu trúc `metadata`:**

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation)                                                                                       |
| :--- | :--- | :---: |:---------------------------------------------------------------------------------------------------------------------|
| `title` | String | **Có** | Tên văn bản. Ràng buộc: `minLength: 5`.                                                                              |
| `document_type` | String | **Có** | Enum: `["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị", "Nghị quyết", "Thông tư liên tịch"]`. Khi có sự khác biệt giữa tài liệu mô tả và JSON Schema thì JSON Schema là nguồn chuẩn. |
| `document_number` | String | **Có** | Số hiệu văn bản (VD: "100/2019/NĐ-CP").                                                                              |
| `issue_date` | Date | **Có** | Ngày ban hành. Định dạng chuẩn: `YYYY-MM-DD`.                                                                        |
| `effective_date` | Date | **Có** | Ngày có hiệu lực. Định dạng chuẩn: `YYYY-MM-DD`.                                                                     |
| `expiry_date` | Date / Null | Không | Ngày hết hiệu lực (hoặc `null` nếu còn hiệu lực). Định dạng chuẩn: `YYYY-MM-DD`.                                      |
| `source_url` | String | Không | Đường dẫn URL chính thức tra cứu văn bản pháp luật.                                                                 |
| `issuing_body` | String | **Có** | Cơ quan ban hành (VD: "Chính phủ").                                                                                  |
| `validity_status` | String | **Có** | Enum: `["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung", "Không xác định"]`. |
| `source_status` | String / Null | Không | Trạng thái gốc từ nguồn tra cứu văn bản (VD: "Hết hiệu lực một phần"). |
| `provision_status` | String / Null | Không | Mức độ hiệu lực điều khoản (VD: "document_level_only", "requires_review"). |

**Ánh xạ trạng thái từ registry (`data/reference/document_versions.json`):**

Registry giữ trạng thái gốc theo nguồn tra cứu ở trường `source_status` (trước đây là `status`) và giá trị đã ánh xạ ở `validity_status`. Parser chỉ đọc `validity_status`. Mọi bản ghi phải theo bảng dưới (kiểm bởi `test/schema_test.py::test_registry_validity_status_mapping`):

| `status` (registry) | `validity_status` | Ghi chú |
| :--- | :--- | :--- |
| Còn hiệu lực | Còn hiệu lực | |
| Hết hiệu lực toàn bộ | Hết hiệu lực | Bắt buộc có `expiry_date`. |
| Hết hiệu lực một phần | Sửa đổi bổ sung | Phần lớn văn bản còn áp dụng; chưa ghi Điều/Khoản nào hết hiệu lực (`provision_status = requires_review`). |
| Có điều khoản bị sửa đổi / bãi bỏ | Sửa đổi bổ sung | |
| Cần kiểm tra trạng thái mới nhất | Không xác định | Exporter cảnh báo khi gặp giá trị này. |

`Sắp có hiệu lực` dành cho văn bản có `effective_date` sau ngày xuất corpus; hiện chưa bản ghi nào dùng. `validity_status` dùng để hiển thị và trích dẫn, không dùng để lọc: retrieval lọc theo khoảng `effective_from`/`effective_to` của chunk (mục 5.3) so với thời điểm của câu hỏi, vì văn bản hết hiệu lực vẫn là đáp án đúng cho câu hỏi về thời điểm trước `expiry_date`.

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

### 5.4. Hợp đồng đầu ra Retrieval & Reranking (Retrieval Envelope)
Cấu trúc chuẩn của kết quả truy xuất và xếp hạng lại được mô tả tại [`schemas/retrieval_schema.json`](../schemas/retrieval_schema.json):
* **Phạm vi áp dụng:**
  - **Truy vấn đơn lẻ (API/CLI):** Đầu ra bắt buộc là một object tuân thủ chặt chẽ `RetrievalEnvelope` (`query_id`, `query`, `retriever`, `results`, `latency_ms`, `top_k`, `config`, `stats`).
  - **Tập kết quả đánh giá hàng loạt (Batch evaluation dump):** Là một mảng JSON các `RetrievalEnvelope` (hoặc JSONL mà mỗi dòng là một `RetrievalEnvelope`). Để đảm bảo tương thích ngược với các file kết quả cũ, các script đánh giá (`scripts/evaluate_task4.py`, `retrieval/retrieval_evaluation.py`) áp dụng cơ chế Graceful Reader để hỗ trợ cả định dạng phẳng `[{"query": ..., "chunk_id": ..., "score": ..., "rank": ...}]`.
* **Trường bao ngoài (Envelope fields):**
  - `query_id`: Định danh duy nhất của câu truy vấn (bắt buộc).
  - `retriever`: Tên của pipeline/retriever sử dụng (bắt buộc).
  - `results`: Danh sách các candidate chunks sau khi truy xuất hoặc rerank (bắt buộc).
  - `latency_ms`: Tổng thời gian thực thi tính bằng mili-giây.
  - `top_k`: Số lượng kết quả trả về yêu cầu.
  - `config`: Cấu hình chi tiết của retriever và reranker.
  - `stats`: Thống kê số lượng candidates và độ trễ từng giai đoạn.
* **Chi tiết phần tử (`RetrievalResultItem`):**
  Mỗi phần tử trong `results` bắt buộc có: `chunk_id`, `document_id`, `article_id`, `clause_id`, `parent_clause_id`, `rank`, `score`, `chunk_text`, `metadata`. Các trường thứ hạng và điểm trung gian (`source_ranks`, `source_scores`, `rrf_score`, `reranker_score`) được lưu đúng vị trí quy định trong schema, không đặt ở root của item.

---

## 6. Bảng Ánh xạ Định danh Văn bản (Document ID Mapping Registry)

Bảng ánh xạ chuẩn hóa chính thức giữa mã file quản lý (`file_code`), định danh hệ thống slug (`document_id`), số hiệu văn bản pháp luật, tên văn bản và trạng thái hiệu lực:

| Mã File (`file_code`) | Định danh hệ thống (`document_id`) | Số hiệu văn bản (`document_number`) | Trạng thái hiệu lực (`validity_status`) | Tên văn bản |
| :--- | :--- | :--- | :--- | :--- |
| **L01** | `l_52_2014_qh13` | 52/2014/QH13 | Còn hiệu lực | Luật Hôn nhân và gia đình |
| **ND01** | `nd_126_2014_nd_cp` | 126/2014/NĐ-CP | Sửa đổi bổ sung | Quy định chi tiết một số điều và biện pháp thi hành Luật Hôn nhân và gia đình |
| **ND02** | `nd_207_2025_nd_cp` | 207/2025/NĐ-CP | Còn hiệu lực | Sinh con bằng kỹ thuật hỗ trợ sinh sản và điều kiện mang thai hộ vì mục đích nhân đạo |
| **ND03** | `nq_01_2024_nq_hdtp` | 01/2024/NQ-HĐTP | Còn hiệu lực | Hướng dẫn áp dụng một số quy định về giải quyết vụ việc hôn nhân và gia đình |
| **TT01** | `ttlt_01_2016_ttlt_tandtc` | 01/2016/TTLT-TANDTC-VKSNDTC-BTP | Còn hiệu lực | Hướng dẫn một số quy định Luật Hôn nhân và gia đình |
| **TT02** | `tt_02a_2015_tt_btp` | 02a/2015/TT-BTP | Hết hiệu lực | Hướng dẫn một số điều Nghị định 126/2014 về hôn nhân có yếu tố nước ngoài |
| **TT03** | `tt_32_2016_tt_byt` | 32/2016/TT-BYT | Còn hiệu lực | Quy định liên quan đến hỗ trợ sinh sản |
| **TT04** | `tt_34_2017_tt_byt` | 34/2017/TT-BYT | Sửa đổi bổ sung | Tư vấn, sàng lọc, chẩn đoán, điều trị trước sinh và sơ sinh |
| **TT05** | `tt_30_2019_tt_byt` | 30/2019/TT-BYT | Không xác định | Sửa đổi, bổ sung một số điều về sàng lọc, chẩn đoán trước sinh và sơ sinh |
| **L02** | `l_22_2000_qh10` | 22/2000/QH10 | Hết hiệu lực | Luật Hôn nhân và gia đình 2000 |
| **L03** | `l_21_lct_hdnn7` | 21-LCT/HĐNN7 | Hết hiệu lực | Luật Hôn nhân và gia đình năm 1986 |
| **ND05** | `nd_70_2001_nd_cp` | 70/2001/NĐ-CP | Hết hiệu lực | Quy định chi tiết thi hành Luật Hôn nhân và gia đình 2000 |
| **ND06** | `nd_32_2002_nd_cp` | 32/2002/NĐ-CP | Hết hiệu lực | Áp dụng Luật Hôn nhân và gia đình đối với dân tộc thiểu số |
| **ND07** | `nd_68_2002_nd_cp` | 68/2002/NĐ-CP | Hết hiệu lực | Hôn nhân và gia đình có yếu tố nước ngoài |
| **ND08** | `nd_77_2001_nd_cp` | 77/2001/NĐ-CP | Hết hiệu lực | Đăng ký kết hôn theo Nghị quyết 35/2000/QH10 |
| **TT08** | `tt_15_2015_tt_btp` | 15/2015/TT-BTP | Hết hiệu lực | Quy định chi tiết thi hành Luật Hộ tịch và Nghị định 123/2015 |
| **ND04** | `nd_10_2015_nd_cp` | 10/2015/NĐ-CP | Hết hiệu lực | Thụ tinh trong ống nghiệm và mang thai hộ vì mục đích nhân đạo |
| **TT09** | `tt_04_2020_tt_btp` | 04/2020/TT-BTP | Sửa đổi bổ sung | Quy định chi tiết một số điều về hộ tịch |
| **TT10** | `tt_57_2015_tt_byt` | 57/2015/TT-BYT | Sửa đổi bổ sung | Chi tiết một số điều Nghị định 10/2015 về thụ tinh trong ống nghiệm |
| **TT11** | `tt_38_2025_tt_byt` | 38/2025/TT-BYT | Còn hiệu lực | Chi tiết một số điều Nghị định 207/2025 về hỗ trợ sinh sản |
| **ND09** | `nd_123_2015_nd_cp` | 123/2015/NĐ-CP | Sửa đổi bổ sung | Quy định chi tiết một số điều của Luật Hộ tịch |
