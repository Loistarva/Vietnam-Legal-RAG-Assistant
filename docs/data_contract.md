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

- **Document ID:** Trường `document_id` được lấy trực tiếp từ `data/reference/document_versions.json`; bảng ở Mục 6 trích các văn bản đang có trong corpus. Quy tắc `[loại_văn_bản]_[số_hiệu đầy đủ]` chỉ dùng để đặt ID khi thêm văn bản mới vào registry; ID đã có trong registry không đổi (ghi nhận ngoại lệ rút gọn `ttlt_01_2016_ttlt_tandtc`).
- **Article ID:** `[document_id]_art_[số_điều]` (VD: Điều 6 `nd_100_2019_nd_cp_art_6`). Lưu ý: `data/reference/article_index.json` là bảng nối chính thức giữa mã Điều của benchmark (`gold_article_ids`) và `article_id` dạng slug của corpus.
- **Clause ID:** `[article_id]_clause_[số_khoản]` (VD: Khoản 2 `nd_100_2019_nd_cp_art_6_clause_2`).
- **Chunk ID:** `[clause_id]_chunk_[số_thứ_tự_hoặc_điểm]` (VD: `nd_100_2019_nd_cp_art_6_clause_2_chunk_1`).

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

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Mô tả & Ràng buộc (Validation) |
| :--- | :--- | :---: | :--- |
| `title` | String | **Có** | Tên văn bản. Ràng buộc: `minLength: 5`. |
| `document_type` | String | **Có** | Enum: `["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị", "Nghị quyết", "Thông tư liên tịch"]`. Khi có sự khác biệt giữa tài liệu mô tả và JSON Schema thì JSON Schema là nguồn chuẩn. |
| `document_number` | String | **Có** | Số hiệu văn bản (VD: "100/2019/NĐ-CP"). |
| `issue_date` | Date | **Có** | Ngày ban hành. Định dạng chuẩn: `YYYY-MM-DD`. |
| `effective_date` | Date | **Có** | Ngày có hiệu lực. Định dạng chuẩn: `YYYY-MM-DD`. |
| `expiry_date` | Date / Null | Không | Ngày hết hiệu lực (hoặc `null` nếu còn hiệu lực). Định dạng chuẩn: `YYYY-MM-DD`. |
| `source_url` | String | Không | Đường dẫn URL chính thức tra cứu văn bản pháp luật. |
| `issuing_body` | String | **Có** | Cơ quan ban hành (VD: "Chính phủ"). |
| `validity_status` | String | **Có** | Enum: `["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung", "Không xác định"]`. |
| `source_status` | String / Null | Không | Trạng thái gốc từ nguồn tra cứu văn bản (VD: "Hết hiệu lực một phần"). |
| `provision_status` | String / Null | Không | Mức độ hiệu lực điều khoản (VD: "document_level_only", "requires_review"). Ở chunk, giá trị `repealed` hoặc `amended` nghĩa là Điều/Khoản/Điểm đó có khoảng hiệu lực riêng ghi trong `data/reference/provision_periods.json`. |

**Ánh xạ trạng thái từ registry (`data/reference/document_versions.json`):**

Registry giữ trạng thái gốc theo nguồn tra cứu ở trường `source_status` (trước đây là `status`) và giá trị đã ánh xạ ở `validity_status`. Parser chỉ đọc `validity_status`. Mọi bản ghi phải theo bảng dưới (kiểm bởi `test/schema_test.py::test_registry_validity_status_mapping`):

| `status` (registry) | `validity_status` | Ghi chú |
| :--- | :--- | :--- |
| Còn hiệu lực | Còn hiệu lực | |
| Hết hiệu lực toàn bộ | Hết hiệu lực | Bắt buộc có `expiry_date`. |
| Hết hiệu lực một phần | Sửa đổi bổ sung | Phần lớn văn bản còn áp dụng (`provision_status = requires_review`). Điều/Khoản/Điểm đã bị bãi bỏ hoặc sửa đổi bởi văn bản có trong corpus được ghi ở `data/reference/provision_periods.json`; exporter ghi `effective_to` và `provision_status` của bản ghi đó vào chunk (kiểm bởi `test/test_provision_periods.py`). Bản ghi cấp Điểm làm Khoản đó được tách mỗi Điểm một chunk (`point_ref` = "Điểm a"), câu dẫn thành chunk riêng. Với Khoản bị sửa đổi, `evidence_chunk_id` là chunk của văn bản sửa đổi chứa nội dung mới, nên tại `as_of_date` sau ngày sửa retriever trả nội dung mới thay cho bản cũ. |
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

1. **Giai đoạn 1: Parser (Trích xuất cấu trúc):**
   - Module Parser đọc PDF/HTML và xuất ra JSON tuân thủ chuẩn này đến tầng `Clause`.
   - **Bắt buộc:** Phải làm sạch ký tự rác, không chứa ký tự `\x00` trong chuỗi text.
   - **Cho phép:** Trường `chunks` tại tầng `Clause` được phép để `null`.
2. **Giai đoạn 2: Chunker (Chia nhỏ ngữ nghĩa):**
   - Module Chunking đọc JSON từ Parser, lấy dữ liệu từ `clause_text`.
   - Dựa vào chiến lược độ dài token (Token limit), chia `clause_text` thành nhiều đối tượng `Chunk` và nạp vào mảng `chunks`.
   - Gắn đúng `parent_clause_id` để kết nối lại thành cây.
3. **Quy tắc Ngoại lệ (Edge Cases):**
   - Nếu một Điều luật không phân chia thành các Khoản (chỉ có một đoạn văn duy nhất), Parser vẫn phải khởi tạo một Clause (VD: `clause_number: "1"`) để bọc lấy đoạn văn đó, giữ vững tính toàn vẹn của cây 4 tầng.
   - Chunker không tự loại văn bản theo `validity_status`; trạng thái được giữ trong metadata để hệ thống retrieval lọc theo thời điểm câu hỏi. Nếu nghiệp vụ chỉ chọn văn bản còn hiệu lực, bộ chọn corpus phải áp dụng điều kiện đó trước khi export.

---

## 5. Hợp đồng đầu ra Child Chunk JSONL

Parser giữ nguyên JSON nguồn và không cần ghi chunks ngược vào `clauses[].chunks`. Exporter tạo một bản ghi Child Chunk độc lập trên mỗi dòng tại `data/chunking_output/chunks.jsonl`; cấu trúc bản ghi được mô tả trong [`schemas/chunk_payload_schema.json`](../schemas/chunk_payload_schema.json).

### 5.1. Định danh và Khóa ngoại bắt buộc ở cấp Root
- **`chunk_id` / `id`:** ID duy nhất của Child Chunk theo định dạng chuẩn: `{clause_id}_chunk_{idx}` (trong đó `idx` đếm tuần tự từ 1 trong phạm vi từng Khoản).
- **`parent_clause_id`:** Khóa ngoại bắt buộc, trỏ chính xác đến `clause_id` của Khoản chứa chunk (`parent_clause_id == clause_id`).
- **`clause_id`:** Khóa định danh của Khoản cha chứa chunk.
- **`article_id`:** Khóa định danh của Điều chứa Khoản.
- **`parent_id`:** Khóa ngoại trỏ đến một ParentChunk trong `data/chunking_output/parents.json`, và danh sách `child_ids` của Parent phải khớp với các Child.
- **`doc_id` / `document_id`:** Khóa định danh của Văn bản pháp luật.

Các cặp trường `id`/`chunk_id`, `doc_id`/`document_id` và `text`/`chunk_text` là các alias tương thích tích hợp và phải có giá trị bằng nhau.

### 5.2. Nội dung và Embedding
- **`chunk_text`:** Nội dung văn bản của chunk. Ràng buộc: `minLength: 10`, tuyệt đối không chứa ký tự null byte (`\x00`). Nếu đoạn đuôi cắt cuối cùng trong một Khoản có độ dài dưới 10 ký tự, engine chunking tự động gộp vào chunk liền trước để tránh sinh chunk vụn.
- **`seg_text`:** Nội dung đã tách từ tiếng Việt (Underthesea).
- **`embed_text`:** Chuỗi kết hợp tiêu đề, breadcrumb và nội dung đã tách từ phục vụ sinh vector dense embedding.
- **`embed_text_raw`** *(Tùy chọn):* Chuỗi text kết hợp thô trước khi tách từ.
- **`point_ref`:** Tùy chọn (`["string", "null"]`), chứa thông tin Điểm nếu có hoặc `null`.

### 5.3. Metadata mở rộng

`quoted_clause_number` (chuỗi số, tùy chọn) xác định Khoản được trích bên trong một
Khoản sửa đổi. `clause_number` và `clause_id` vẫn chỉ Khoản của văn bản nguồn.
Khi các Khoản trích dẫn có thời hạn khác nhau, exporter tách child và parent theo
ranh giới này, rồi áp dụng `quoted_clauses` trong `provision_periods.json`.
ID vẫn theo `{clause_id}_chunk_{n}`; không dùng số Khoản trích dẫn làm Khoản nguồn.

Trong `provision_periods.json`, `evidence_chunk_id` là định danh dẫn chứng chính;
`evidence_context_ids` là danh sách có thứ tự của toàn bộ chunk cần đọc để có đủ
câu dẫn và nội dung thay thế. Nếu không khai báo, danh sách mặc định chỉ chứa
`evidence_chunk_id`. Exporter kiểm mọi ID trong nhóm tồn tại và thuộc văn bản
`changed_by`. Trường này phục vụ truy vết/review, không tự mở rộng kết quả top-k
của retriever và không thay thế bộ lọc thời gian.
Trường `metadata` chứa metadata của văn bản cùng `chapter`, `section`, `article_number`, và các trường mở rộng phục vụ lọc downstream: `document_title`, `clause_number`, `source_url`, `effective_from`, `effective_to`.

---

### 5.4. Hợp đồng đầu ra Retrieval & Reranking (Retrieval Envelope)
Cấu trúc chuẩn của kết quả truy xuất và xếp hạng lại được mô tả tại [`schemas/retrieval_schema.json`](../schemas/retrieval_schema.json):
- **Phạm vi áp dụng:**
  - **Truy vấn đơn lẻ (API/CLI):** Đầu ra bắt buộc là một object tuân thủ chặt chẽ `RetrievalEnvelope` (`query_id`, `query`, `retriever`, `results`, `latency_ms`, `top_k`, `config`, `stats`).
  - **Tập kết quả đánh giá hàng loạt (Batch evaluation dump):** Là một mảng JSON các `RetrievalEnvelope` (hoặc JSONL mà mỗi dòng là một `RetrievalEnvelope`). Để đảm bảo tương thích ngược với các file kết quả cũ, các script đánh giá (`scripts/evaluate_task4.py`, `retrieval/retrieval_evaluation.py`) áp dụng cơ chế Graceful Reader để hỗ trợ cả định dạng phẳng `[{"query": ..., "chunk_id": ..., "score": ..., "rank": ...}]`.
- **Trường bao ngoài (Envelope fields):**
  - `query_id`: Định danh duy nhất của câu truy vấn (bắt buộc).
  - `retriever`: Tên của pipeline/retriever sử dụng (bắt buộc).
  - `results`: Danh sách các candidate chunks sau khi truy xuất hoặc rerank (bắt buộc).
  - `latency_ms`: Tổng thời gian thực thi tính bằng mili-giây.
  - `top_k`: Số lượng kết quả trả về yêu cầu.
  - `config`: Cấu hình chi tiết của retriever và reranker.
  - `stats`: Thống kê số lượng candidates và độ trễ từng giai đoạn.
- **Chi tiết phần tử (`RetrievalResultItem`):**
  Mỗi phần tử trong `results` bắt buộc có: `chunk_id`, `document_id`, `article_id`, `clause_id`, `parent_clause_id`, `rank`, `score`, `chunk_text`, `metadata`. Các trường thứ hạng và điểm trung gian (`source_ranks`, `source_scores`, `rrf_score`, `reranker_score`) được lưu đúng vị trí quy định trong schema, không đặt ở root của item.

---

### 5.5. Hợp đồng Giao diện Truy xuất, Lọc Hiệu lực Thời điểm & Xử lý Truy vấn Rỗng (Issues E1, E14)

Để đảm bảo kết quả truy xuất chính xác theo dòng thời gian và xử lý lỗi đồng nhất toàn hệ thống, mọi module truy xuất (Dense, BM25, Hybrid, Pipeline) thống nhất tuân thủ các quy định sau:

#### 1. Chữ ký hàm chuẩn mực (Function Signatures)
- **BM25 (`ElasticsearchBM25Retriever.search`):** `top_k` bắt buộc truyền, không có giá trị mặc định.
  ```python
  def search(
      self,
      query: str,
      top_k: int,
      *,
      as_of_date: str | None = None,
  ) -> list[dict[str, Any]]: ...
  ```
- **Hybrid (`HybridRetriever.search`):** `top_k=None` thì lấy `HybridSearchConfig.top_k` (mặc định `10`; khi dựng qua `build_hybrid_retriever` lấy `retrieval.retrieval_top_k = 50` trong `retrieval/config.yaml`).
  ```python
  def search(
      self,
      query: str,
      top_k: int | None = None,
      *,
      as_of_date: str | None = None,
  ) -> list[dict[str, Any]]: ...
  ```
- **Hybrid Envelope Retrieval (`HybridRetriever.retrieve`):**
  ```python
  def retrieve(
      self,
      query: str,
      top_k: int | None = None,
      *,
      as_of_date: str | None = None,
  ) -> dict[str, list[dict[str, Any]]]: ...
  ```
- **Toàn bộ Pipeline (`RetrievalPipeline.run`):**
  ```python
  def run(
      self,
      query: str,
      top_k: int | None = None,
      *,
      query_id: str = "Q_CLI_001",
      as_of_date: str | None = None,
  ) -> dict[str, Any]: ...
  ```
- **Dense Retrieval (`DenseRetriever.search`):**
  ```python
  def search(
      self,
      query: str,
      top_k: int = 5,
      exclude_expired: bool = True,
      as_of_date: str | None = None,
      filters: dict[str, Any] | None = None,
  ) -> list[dict[str, Any]]: ...
  ```
  *Lưu ý:* Tham số `exclude_expired` được giữ lại cho mục đích tương thích ngược. Tham số `filters` hiện chỉ được nhận để giữ tương thích, chưa được áp dụng: `LegalVectorStore.search` bỏ qua giá trị này. Lọc theo thời điểm chỉ do `as_of_date` quyết định.

#### 2. Khoảng hiệu lực pháp lý (Validity Period)
Một chunk pháp luật được xác định là có hiệu lực tại thời điểm `as_of_date` khi và chỉ khi thỏa mãn khoảng nửa mở:
$$\text{effective\_from} \le \text{as\_of\_date} < \text{effective\_to}$$

- **Quy ước biên mở (Unbounded dates):**
  - Nếu `effective_from` là `null` (`None` hoặc rỗng): văn bản được coi là đã có hiệu lực từ trước thời điểm khảo sát ($-\infty < \text{as\_of\_date}$).
  - Nếu `effective_to` là `null` (`None` hoặc rỗng): văn bản hiện vẫn đang duy trì hiệu lực và chưa có ngày hết hiệu lực ($\text{as\_of\_date} < +\infty$).
- **Cùng ngữ nghĩa ở mọi tầng:** Mọi tầng áp dụng đúng ngữ nghĩa của `retrieval.temporal.is_effective_at` và đọc ngày qua `retrieval.temporal.effective_period`. Elasticsearch lọc bằng range query (`ElasticsearchBM25Retriever.build_temporal_filter`), Qdrant lọc trước Top-K bằng `LegalVectorStore.build_active_legal_filter`; `is_effective_at` dùng để kiểm lại sau truy xuất. Backend mới phải lọc trước Top-K với cùng ngữ nghĩa này.

#### 3. Quy ước khi không truyền ngày (`as_of_date=None`)
- **Thời điểm mặc định duy nhất:** Khi người dùng hoặc API không truyền `as_of_date` (`as_of_date=None`), hệ thống chỉ có DUY NHẤT một cách xử lý là lấy ngày chạy hiện tại theo lịch địa phương thông qua hàm chuẩn hóa `retrieval.temporal.normalize_as_of_date(None)` (`date.today().isoformat()`).
- **Không lọc tĩnh theo `validity_status`:** Tuyệt đối không áp dụng bộ lọc tĩnh cứng theo trường `validity_status` (ví dụ không lọc `validity_status == "Còn hiệu lực"`). Trường `validity_status` chỉ đóng vai trò hiển thị và trích dẫn thông tin cho người dùng (như đã quy định tại Mục 3.1), vì một văn bản dù hiện tại ghi `Hết hiệu lực` thì đối với một câu hỏi trong quá khứ trước ngày hết hiệu lực (`expiry_date`), văn bản đó vẫn có đầy đủ hiệu lực thi hành và là căn cứ pháp lý chính xác.

#### 4. Quy tắc xử lý câu hỏi `historical_law` và `outdated_law_trap`
- Đối với các câu hỏi thuộc nhóm `test_type` là `historical_law` (hỏi về luật cũ tại thời điểm quá khứ) hoặc `outdated_law_trap` (bẫy văn bản hết hiệu lực):
  - Hệ thống **vẫn lọc theo `as_of_date` của chính câu hỏi**, tuyệt đối không được tắt bộ lọc thời điểm.
  - Nhờ có bộ lọc $\text{effective\_from} \le \text{as\_of\_date} < \text{effective\_to}$, câu hỏi lịch sử với `as_of_date` rơi vào giai đoạn áp dụng của luật cũ sẽ truy xuất chính xác chunk của luật cũ tại thời điểm đó, đồng thời loại bỏ các luật mới chưa ra đời.

#### 5. Ràng buộc Pipeline, Candidate hai bước & Benchmark
- **Bắt buộc hỗ trợ `as_of_date`:** `HybridRetriever` và `RetrievalPipeline` bắt buộc kiểm tra chữ ký của retriever thành phần; nếu retriever không nhận `as_of_date`, hệ thống từ chối thực thi và raise lỗi (`TypeError` hoặc `ValueError`) để ngăn chặn việc trả kết quả chưa qua thẩm định thời điểm.
- **Quy trình Candidate hai bước (`PrecomputedRetriever`):** Khi chạy tách rời 2 process (Lần 1 chạy retrieval lưu candidate vào file với `--reranker none`, Lần 2 nạp candidate qua `PrecomputedRetriever` để rerank): `PrecomputedRetriever` kiểm tra nghiêm ngặt `as_of_date` lưu trong `config` của lần 1; nếu lệch với `as_of_date` của lần 2, hệ thống lập tức báo lỗi `ValueError`.
- **Khóa cố định trên Benchmark:** Toàn bộ câu hỏi trong bộ benchmark (`queries_dev.json`, `queries_test.json`) bắt buộc phải có giá trị `as_of_date` cụ thể, không được để trống, nhằm đảm bảo các chỉ số đánh giá (Hit@K, Recall@K, MRR, nDCG) có tính tất định và không bị sai lệch theo thời gian chạy kiểm thử thực tế.

#### 6. Quy định xử lý câu hỏi rỗng và kết quả rỗng (Issue E14)
- **Câu hỏi rỗng (Empty Query):** Nếu `query` là `None`, chuỗi rỗng `""`, hoặc chuỗi chỉ chứa ký tự khoảng trắng: mọi retriever (`ElasticsearchBM25Retriever`, `DenseRetriever`, `HybridRetriever`) và `RetrievalPipeline` đều bắt buộc fail-fast và raise `ValueError` (ví dụ: `"query phải là chuỗi không rỗng"` hoặc `"Câu hỏi không được rỗng."`).
- **Kết quả rỗng (Empty Results):** Khi kho dữ liệu rỗng (store rỗng) hoặc không có bất kỳ chunk nào thỏa mãn điều kiện truy vấn và bộ lọc thời điểm: hệ thống trả về danh sách kết quả rỗng `results: []` trong `RetrievalEnvelope` (hoặc mảng `[]` đối với các phương thức `search()`), tuyệt đối không làm gián đoạn hệ thống hay ném ngoại lệ không mong muốn.

---

## 6. Bảng Ánh xạ Định danh Văn bản (Document ID Mapping Registry)

Bảng ánh xạ chuẩn hóa chính thức giữa mã file quản lý (`file_code`), định danh hệ thống slug (`document_id`), số hiệu văn bản pháp luật, tên văn bản và trạng thái hiệu lực:

| Mã File (`file_code`) | Định danh hệ thống (`document_id`) | Số hiệu văn bản (`document_number`) | Trạng thái hiệu lực (`validity_status`) | Tên văn bản |
| :--- | :--- | :--- | :--- | :--- |
| **L01** | `l_52_2014_qh13` | 52/2014/QH13 | Còn hiệu lực | Luật Hôn nhân và gia đình 2014 |
| **ND01** | `nd_126_2014_nd_cp` | 126/2014/NĐ-CP | Sửa đổi bổ sung | Quy định chi tiết một số điều và biện pháp thi hành Luật Hôn nhân và gia đình |
| **ND02** | `nd_207_2025_nd_cp` | 207/2025/NĐ-CP | Còn hiệu lực | Quy định về sinh con bằng kỹ thuật hỗ trợ sinh sản và điều kiện mang thai hộ vì mục đích nhân đạo |
| **ND03** | `nq_01_2024_nq_hdtp` | 01/2024/NQ-HĐTP | Còn hiệu lực | Hướng dẫn áp dụng một số quy định của pháp luật trong giải quyết vụ việc về hôn nhân và gia đình |
| **TT01** | `ttlt_01_2016_ttlt_tandtc` | 01/2016/TTLT-TANDTC-VKSNDTC-BTP | Còn hiệu lực | Hướng dẫn thi hành một số quy định của Luật Hôn nhân và gia đình |
| **TT02** | `tt_02a_2015_tt_btp` | 02a/2015/TT-BTP | Hết hiệu lực | Hướng dẫn thi hành một số điều của Nghị định số 126/2014/NĐ-CP ngày 31 tháng 12 năm 2014 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **TT03** | `tt_32_2016_tt_byt` | 32/2016/TT-BYT | Còn hiệu lực | Quy định việc chi trả các chi phí thực tế để bảo đảm chăm sóc sức khỏe sinh sản của bên nhờ mang thai hộ vì mục đích nhân đạo |
| **TT04** | `tt_34_2017_tt_byt` | 34/2017/TT-BYT | Sửa đổi bổ sung | Hướng dẫn tư vấn, sàng lọc, chẩn đoán, điều trị trước sinh và sơ sinh |
| **TT05** | `tt_30_2019_tt_byt` | 30/2019/TT-BYT | Không xác định | Sửa đổi, bổ sung một số điều của Thông tư số 34/2017/TT-BYT ngày 18 tháng 8 năm 2017 của Bộ trưởng Bộ Y tế hướng dẫn tư vấn, sàng lọc, chẩn đoán, điều trị trước sinh và sơ sinh |
| **L02** | `l_22_2000_qh10` | 22/2000/QH10 | Hết hiệu lực | Luật Hôn nhân và gia đình 2000 |
| **L03** | `l_21_lct_hdnn7` | 21-LCT/HĐNN7 | Hết hiệu lực | Luật Hôn nhân và gia đình 1986 |
| **ND05** | `nd_70_2001_nd_cp` | 70/2001/NĐ-CP | Hết hiệu lực | Quy định chi tiết thi hành Luật Hôn nhân và gia đình |
| **ND06** | `nd_32_2002_nd_cp` | 32/2002/NĐ-CP | Hết hiệu lực | Quy định việc áp dụng Luật Hôn nhân và gia đình đối với các dân tộc thiểu số |
| **ND07** | `nd_68_2002_nd_cp` | 68/2002/NĐ-CP | Hết hiệu lực | Quy định chi tiết thi hành một số điều của Luật Hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **ND08** | `nd_77_2001_nd_cp` | 77/2001/NĐ-CP | Hết hiệu lực | Quy định chi tiết về đăng ký kết hôn theo Nghị quyết số 35/2000/QH10 của Quốc hội về việc thi hành Luật Hôn nhân và gia đình |
| **TT06** | `tt_07_2001_tt_btp` | 07/2001/TT-BTP | Hết hiệu lực | Hướng dẫn thi hành một số quy định của Nghị định số 77/2001/NĐ-CP ngày 22 tháng 10 năm 2001 của Chính phủ quy định chi tiết về đăng ký kết hôn theo Nghị quyết số 35/2000/QH10 của Quốc hội |
| **TT07** | `tt_07_2002_tt_btp` | 07/2002/TT-BTP | Hết hiệu lực | Hướng dẫn thi hành một số điều của Nghị định số 68/2002/NĐ-CP ngày 10 tháng 7 năm 2002 của Chính phủ quy định chi tiết thi hành một số điều của Luật Hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **TT08** | `tt_15_2015_tt_btp` | 15/2015/TT-BTP | Hết hiệu lực | Quy định chi tiết thi hành một số điều của Luật Hộ tịch và Nghị định số 123/2015/NĐ-CP ngày 15 tháng 11 năm 2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch |
| **ND04** | `nd_10_2015_nd_cp` | 10/2015/NĐ-CP | Hết hiệu lực | Quy định về sinh con bằng kỹ thuật thụ tinh trong ống nghiệm và điều kiện mang thai hộ vì mục đích nhân đạo |
| **TT09** | `tt_04_2020_tt_btp` | 04/2020/TT-BTP | Sửa đổi bổ sung | Quy định chi tiết thi hành một số điều của Luật Hộ tịch và Nghị định số 123/2015/NĐ-CP ngày 15 tháng 11 năm 2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch |
| **TT10** | `tt_57_2015_tt_byt` | 57/2015/TT-BYT | Sửa đổi bổ sung | Quy định chi tiết một số điều của Nghị định số 10/2015/NĐ-CP ngày 28 tháng 01 năm 2015 của Chính phủ quy định về sinh con bằng kỹ thuật thụ tinh trong ống nghiệm và điều kiện mang thai hộ vì mục đích nhân đạo |
| **TT11** | `tt_38_2025_tt_byt` | 38/2025/TT-BYT | Còn hiệu lực | Quy định chi tiết một số điều của Nghị định số 207/2025/NĐ-CP ngày 15 tháng 7 năm 2025 của Chính phủ quy định về sinh con bằng kỹ thuật hỗ trợ sinh sản và điều kiện mang thai hộ vì mục đích nhân đạo |
| **ND09** | `nd_123_2015_nd_cp` | 123/2015/NĐ-CP | Sửa đổi bổ sung | Quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch |
| **L04** | `l_81_2025_qh15` | 81/2025/QH15 | Còn hiệu lực | Luật sửa đổi, bổ sung một số điều của Luật Tổ chức Tòa án nhân dân |
| **ND12** | `nd_87_2020_nd_cp` | 87/2020/NĐ-CP | Sửa đổi bổ sung | Quy định về Cơ sở dữ liệu hộ tịch điện tử, đăng ký hộ tịch trực tuyến |
| **ND11** | `nd_07_2025_nd_cp` | 07/2025/NĐ-CP | Sửa đổi bổ sung | Sửa đổi, bổ sung một số điều của các Nghị định trong lĩnh vực hộ tịch, quốc tịch, chứng thực |
| **ND13** | `nd_18_2026_nd_cp` | 18/2026/NĐ-CP | Còn hiệu lực | Sửa đổi, bổ sung một số nghị định để cắt giảm, đơn giản hóa thủ tục hành chính, điều kiện kinh doanh thuộc phạm vi quản lý của Bộ Tư pháp |
| **TT13** | `tt_04_2024_tt_btp` | 04/2024/TT-BTP | Còn hiệu lực | Sửa đổi, bổ sung một số điều của Thông tư số 02/2020/TT-BTP ngày 08/4/2020 của Bộ trưởng Bộ Tư pháp ban hành, hướng dẫn sử dụng, quản lý mẫu sổ quốc tịch và mẫu giấy tờ về quốc tịch và Thông tư số 04/2020/TT-BTP ngày 28/5/2020 của Bộ trưởng Bộ Tư pháp quy định chi tiết thi hành một số điều của Luật Hộ tịch và Nghị định số 123/2015/NĐ-CP ngày 15/11/2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch |
| **L10** | `l_102_2016_qh13` | 102/2016/QH13 | Sửa đổi bổ sung | Luật Trẻ em |
| **BL02** | `bl_92_2015_qh13` | 92/2015/QH13 | Sửa đổi bổ sung | Bộ Luật Tố tụng dân sự |
| **L11** | `l_34_2024_qh15` | 34/2024/QH15 | Sửa đổi bổ sung | Luật Tổ chức Tòa án nhân dân |
| **ND21** | `nd_24_2019_nd_cp` | 24/2019/NĐ-CP | Sửa đổi bổ sung | Sửa đổi, bổ sung một số điều của Nghị định số 19/2011/NĐ-CP ngày 21 tháng 3 năm 2011 của Chính phủ quy định chi tiết thi hành một số điều của Luật nuôi con nuôi |
| **ND22** | `nd_06_2025_nd_cp` | 06/2025/NĐ-CP | Không xác định | Sửa đổi, bổ sung một số điều của các Nghị định về nuôi con nuôi |
| **TT15** | `tt_07_2023_tt_btp` | 07/2023/TT-BTP | Sửa đổi bổ sung | Sửa đổi Thông tư 10/2020 về nuôi con nuôi |
| **ND23** | `nd_104_2022_nd_cp` | 104/2022/NĐ-CP | Không xác định | Sửa đổi, bổ sung một số điều của các nghị định liên quan đến việc nộp, xuất trình sổ hộ khẩu, sổ tạm trú giấy khi thực hiện thủ tục hành chính, cung cấp dịch vụ công |
| **ND24** | `nd_120_2025_nd_cp` | 120/2025/NĐ-CP | Không xác định | Quy định về phân định thẩm quyền của chính quyền địa phương 02 cấp trong lĩnh vực quản lý nhà nước của Bộ Tư pháp |
| **L12** | `l_85_2025_qh15` | 85/2025/QH15 | Không xác định | Luật sửa đổi, bổ sung một số điều của Bộ Luật tố tụng dân sự, Luật Tố tụng hành chính, Luật Tư pháp người chưa thành niên, Luật Phá sản và Luật Hòa giải, đối thoại tại Tòa án |
| **TT17** | `tt_10_2025_tt_btp` | 10/2025/TT-BTP | Không xác định | Sửa đổi, bổ sung một số điều của Thông tư số 10/2020/TT-BTP ngày 28 tháng 12 năm 2020 của Bộ trưởng Bộ Tư pháp ban hành, hướng dẫn việc ghi chép, sử dụng, quản lý và lưu trữ Sổ, mẫu giấy tờ, hồ sơ nuôi con nuôi được sửa đổi, bô sung một số điều theo Thông tư số 07/2023/TT-BTP |
| **ND25** | `nd_63_2024_nd_cp` | 63/2024/NĐ-CP | Sửa đổi bổ sung | Quy định việc thực hiện liên thông điện tử 02 nhóm thủ tục hành chính: Đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi; đăng ký khai tử, xóa đăng ký thường trú, giải quyết mai táng phí, tử tuất |
| **L13** | `l_58_2020_qh14` | 58/2020/QH14 | Sửa đổi bổ sung | Luật Hòa giải, đối thoại tại tòa án |
| **TT18** | `tt_01_2022_tt_btp` | 01/2022/TT-BTP | Sửa đổi bổ sung | Quy định chi tiết một số điều và biện pháp thi hành Nghị định số 87/2020/NĐ-CP ngày 28 tháng 7 năm 2020 của Chính phủ quy định về Cơ sở dữ liệu hộ tịch điện tử, đăng ký hộ tịch trực tuyến |
| **TT19** | `tt_03_2023_tt_btp` | 03/2023/TT-BTP | Không xác định | Sửa đổi Thông tư 01/2022 về hộ tịch điện tử |
| **TT21** | `tt_07_2025_tt_bng` | 07/2025/TT-BNG | Không xác định | Sửa đổi, bổ sung một số điều của Thông tư số 07/2023/TT-BNG ngày 29 tháng 12 năm 2023 của Bộ trưởng Bộ Ngoại giao hướng dẫn việc đăng ký và quản lý hộ tịch tại Cơ quan đại diện ngoại giao, Cơ quan đại diện lãnh sự của Việt Nam ở nước ngoài |
| **L05** | `l_60_2014_qh13` | 60/2014/QH13 | Không xác định | LUẬT HỘ TỊCH |
| **L06** | `l_52_2010_qh12` | 52/2010/QH12 | Không xác định | LUẬT NUÔI CON NUÔI |
| **L07** | `l_13_2022_qh15` | 13/2022/QH15 | Không xác định | Luật phòng, chống bạo lực gia đình |
| **TT14** | `tt_10_2020_tt_btp` | 10/2020/TT-BTP | Sửa đổi bổ sung | ban hành, hướng dẫn việc ghi chép, sử dụng, quản lý và lưu trữ Sổ, mẫu giấy tờ, hồ sơ nuôi con nuôi |
| **L08** | `l_35_2013_qh13` | 35/2013/QH13 | Còn hiệu lực | Luật Hòa giải ở cơ sở |
| **ND16** | `nd_19_2011_nd_cp` | 19/2011/NĐ-CP | Sửa đổi bổ sung | Quy định chi tiết thi hành một số điều của Luật Nuôi con nuôi |
| **ND18** | `nd_76_2023_nd_cp` | 76/2023/NĐ-CP | Không xác định | Quy định chi tiết một số điều của Luật Phòng, chống bạo lực gia đình |
| **ND19** | `nd_114_2016_nd_cp` | 114/2016/NĐ-CP | Không xác định | Quy định lệ phí đăng ký nuôi con nuôi, lệ phí cấp giấy phép hoạt động của tổ chức con nuôi nước ngoài |
| **ND20** | `nd_15_2014_nd_cp` | 15/2014/NĐ-CP | Không xác định | Quy định chi tiết một số điều và biện pháp thi hành Luật hòa giải ở cơ sở |
| **NQ02** | `nq_326_2016_ubtvqh14` | 326/2016/UBTVQH14 | Không xác định | Án phí và lệ phí Tòa án |
| **BL01** | `bl_91_2015_qh13` | 91/2015/QH13 | Không xác định | Bộ Luật Dân sự |
| **TT16** | `tt_09_2022_tt_btp` | 09/2022/TT-BTP | Không xác định | Bãi bỏ một số nội dung tại các Thông tư trong lĩnh vực trợ giúp pháp lý, hộ tịch do Bộ trưởng Bộ Tư pháp ban hành |
| **ND26** | `nd_301_2026_nd_cp` | 301/2026/NĐ-CP | Không xác định | Sửa đổi, bổ sung một số điều của Nghị định số 63/2024/NĐ-CP ngày 10 tháng 6 năm 2024 của Chính phủ quy định việc thực hiện liên thông điện tử 02 nhóm thủ tục hành chính: đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi; đăng ký khai tử, xóa đăng ký thường trú, giải quyết mai táng phí, tử tuất |
| **ND28** | `nd_24_2013_nd_cp` | 24/2013/NĐ-CP | Hết hiệu lực | quy định chi tiết thi hành một số điều của Luật hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **TT22** | `tt_22_2013_tt_btp` | 22/2013/TT-BTP | Hết hiệu lực | quy định chi tiết và hướng dẫn thi hành một số điều của Nghị định số 24/2013/NĐ-CP ngày 28 tháng 3 năm 2013 của Chính phủ quy định chi tiết thi hành một số điều của Luật Hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **TT23** | `tt_16_2010_tt_btp` | 16/2010/TT-BTP | Hết hiệu lực | hướng dẫn việc ghi vào sổ hộ tịch việc ly hôn đã tiến hành ở nước ngoài |
| **TTLT01** | `ttlt_03_2016_ttlt_btp_bng_bca_bldtbxh` | 03/2016/TTLT-BTP-BNG-BCA-BLĐTBXH | Không xác định | hướng dẫn việc theo dõi tình hình phát triển của trẻ em Việt Nam được cho làm con nuôi nước ngoài và bảo vệ trẻ em trong trường hợp cần thiết |
| **ND29** | `nd_110_2013_nd_cp` | 110/2013/NĐ-CP | Hết hiệu lực | quy định xử phạt vi phạm hành chính trong lĩnh vực bổ trợ tư pháp, hành chính tư pháp, hôn nhân và gia đình, thi hành án dân sự, phá sản doanh nghiệp, hợp tác xã |
| **TT24** | `tt_66_2025_tt_bca` | 66/2025/TT-BCA | Không xác định | quy định công tác giám sát việc thực hiện quyết định cấm tiếp xúc theo quy định của Luật Phòng, chống bạo lực gia đình |
| **ND30** | `nd_110_2025_nd_cp` | 110/2025/NĐ-CP | Không xác định | quy định Cơ sở dữ liệu về phòng, chống bạo lực gia đình |
| **TT26** | `tt_11_2021_tt_btp` | 11/2021/TT-BTP | Không xác định | sửa đổi, bổ sung một số điều của Thông tư số 21/2011/TT-BTP ngày 21 tháng 11 năm 2011 của Bộ trưởng Bộ Tư pháp về việc quản lý Văn phòng con nuôi nước ngoài tại Việt Nam |
| **TT27** | `tt_01_2025_tt_btp` | 01/2025/TT-BTP | Không xác định | sửa đổi, bổ sung một số điều của Thông tư số 21/2011/TT-BTP ngày 21 tháng 11 năm 2011 của Bộ trưởng Bộ Tư pháp về việc quản lý Văn phòng con nuôi nước ngoài tại Việt Nam đã được sửa đổi, bổ sung một số điều theo Thông tư số 11/2021/TT-BTP ngày 28 tháng 12 năm 2021 của Bộ trưởng Bộ Tư pháp |
| **TT28** | `tt_24_2014_tt_btp` | 24/2014/TT-BTP | Hết hiệu lực | sửa đổi, bổ sung một số điều của Thông tư số 12/2011/TT-BTP ngày 27 tháng 6 năm 2011 của Bộ Tư pháp về việc ban hành và hướng dẫn việc ghi chép, lưu trữ, sử dụng biểu mẫu nuôi con nuôi |
| **TT32** | `tt_12_2011_tt_btp` | 12/2011/TT-BTP | Hết hiệu lực | về việc ban hành và hướng dẫn việc ghi chép, lưu trữ, sử dụng biểu mẫu nuôi con nuôi |
| **TT34** | `tt_15_2014_tt_btp` | 15/2014/TT-BTP | Không xác định | hướng dẫn tìm gia đình thay thế ở nước ngoài cho trẻ em khuyết tật, trẻ em mắc bệnh hiểm nghèo, trẻ em từ 5 tuổi trở lên, hai trẻ em trở lên là anh chị em ruột cần tìm gia đình thay thế |
| **TT35** | `tt_21_2011_tt_btp` | 21/2011/TT-BTP | Sửa đổi bổ sung | về việc quản lý Văn phòng con nuôi nước ngoài tại Việt Nam |
| **ND33** | `nd_158_2005_nd_cp` | 158/2005/NĐ-CP | Hết hiệu lực | Về đăng ký và quản lý hộ tịch |
| **ND34** | `nd_83_1998_nd_cp` | 83/1998/NĐ-CP | Hết hiệu lực | Đăng ký hộ tịch |
| **L14** | `l_02_2007_qh12` | 02/2007/QH12 | Hết hiệu lực | LUẬT PHÒNG, CHỐNG BẠO LỰC GIA ĐÌNH |
| **ND35** | `nd_08_2009_nd_cp` | 08/2009/NĐ-CP | Hết hiệu lực | Quy định chi tiết và hướng dẫn thi hành một số điều của Luật Phòng, chống bạo lực gia đình |
| **ND37** | `nd_110_2009_nd_cp` | 110/2009/NĐ-CP | Hết hiệu lực | Quy định xử phạt vi phạm hành chính trong lĩnh vực phòng, chống bạo lực gia đình |
| **TT36** | `tt_08_2025_tt_btp` | 08/2025/TT-BTP | Không xác định | quy định về phân định thẩm quyền của chính quyền địa phương 02 cấp và phân cấp trong lĩnh vực quản lý nhà nước của Bộ Tư pháp |
| **ND38** | `nd_282_2025_nd_cp` | 282/2025/NĐ-CP | Không xác định | quy định xử phạt vi phạm hành chính trong lĩnh vực an ninh, trật tự, an toàn xã hội; phòng, chống tệ nạn xã hội; phòng, chống bạo lực gia đình |
| **ND39** | `nd_347_2026_nd_cp` | 347/2026/NĐ-CP | Không xác định | Sửa đổi, bổ sung một số điều của Nghị định số 169/2025/NĐ-CP ngày 30 tháng 6 năm 2025 của Chính phủ quy định hoạt động khoa học, công nghệ, đổi mới sáng tạo và sản phẩm, dịch vụ về dữ liệu; Nghị định số 105/2025/NĐ-CP ngày 15 tháng 5 năm 2025 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Phòng cháy, chữa cháy và cứu nạn, cứu hộ; Nghị định số 106/2025/NĐ-CP ngày 15 tháng 5 năm 2025 của Chính phủ quy định xử phạt vi phạm hành chính trong lĩnh vực phòng cháy, chữa cháy và cứu nạn, cứu hộ; Nghị định số 282/2025/NĐ-CP ngày 30 tháng 10 năm 2025 của Chính phủ quy định xử phạt vi phạm hành chính trong lĩnh vực an ninh, trật tự, an toàn xã hội; phòng, chống tệ nạn xã hội; phòng, chống bạo lực gia đình |
| **TTLT07** | `ttlt_01_2019_ttlt_tandtc_bng` | 01/2019/TTLT-TANDTC-BNG | Không xác định | quy định về trình tự, thủ tục phối hợp giữa Tòa án nhân dân và Cơ quan đại diện nước Cộng hòa xã hội chủ nghĩa Việt Nam ở nước ngoài để thực hiện một số hoạt động tố tụng dân sự và tố tụng hành chính ở nước ngoài |
| **L15** | `l_102_2025_qh15` | 102/2025/QH15 | Không xác định | Luật Tương trợ tư pháp dân sự |
| **ND40** | `nd_158_2026_nd_cp` | 158/2026/NĐ-CP | Không xác định | Quy định chi tiết một số điều và biện pháp thi hành Luật Tương trợ tư pháp về dân sự |
| **L16** | `l_73_2006_qh11` | 73/2006/QH11 | Sửa đổi bổ sung | Luật Bình đẳng giới |
| **L17** | `l_24_2008_qh12` | 24/2008/QH12 | Không xác định | LUẬT QUỐC TỊCH VIỆT NAM |
| **L19** | `l_68_2020_qh14` | 68/2020/QH14 | Không xác định | luật Cư trú |
| **L20** | `l_11_2017_qh14` | 11/2017/QH14 | Không xác định | luật Trợ giúp pháp lý |
