# Chiến lược Chunking cho Vietnamese Legal RAG Assistant

> **Phiên bản:** 2.1 (Cập nhật đồng bộ theo `system_architecture.drawio`, `docs/data_contract.md` và đặc tả Sprint 5/Sprint 6)  
> **Trạng thái:** Đã chuẩn hóa tích hợp với module `parser/`  
> **Mục tiêu:** Định nghĩa quy tắc tạo Parent-Child Chunks từ dữ liệu Structured Legal JSON, kiểm soát token budget, gắn breadcrumb phân cấp và chuẩn bị payload cho Qdrant, Elasticsearch, và Parent-Context Resolver.

---

## 1. Vị trí Module Chunking trong Kiến trúc Hệ thống

Theo sơ đồ kiến trúc tổng thể (`system_architecture.drawio` & `new data_flow.drawio.xml`), luồng xử lý tài liệu phân định rõ ràng giữa **Parser**, **Vietnamese NLP Pipeline (underthesea)** và **Chunking Engine**:

```
[Raw Legal PDF]
       │
       ▼ (parser/cleaner.py & parser/parser.py)
[Structured Legal JSON] (Document -> Articles -> Clauses)
       │ (Tuân thủ docs/data_contract.md)
       ▼
┌─────────────────────────────────────────────────────────────┐
│             MODULE CHUNKING (chunking_rules.py)             │
│  - Phân bổ ngân sách token (PARENT_MAX_CHARS, CHILD_TOKENS) │
│  - Tách Parent Chunks (theo Điều hoặc nhóm Khoản)           │
│  - Tạo Child Chunks: mỗi chunk thuộc đúng 1 Khoản           │
│  - Tách từ underthesea cho seg_text / embed_text            │
│  - Gắn chuỗi Breadcrumb định vị phân cấp                    │
│  - Gán Semantic ID ({clause_id}_chunk_{n})                  │
└─────────────────────────────────────────────────────────────┘
       │                                     │
       ├─────────────────┐                   │
       ▼                 ▼                   ▼
[Elasticsearch Index] [Vector DB: Qdrant] [Parent Store / KV DB]
  (Sparse BM25)      (Dense BGE-M3)      (Phục vụ Parent-Context Resolver)
```

### Phân định trách nhiệm (Separation of Concerns):
* **Module `parser/`:** Chịu trách nhiệm trích xuất cấu trúc văn bản thô (PDF/TXT) thành cây dữ liệu phân cấp JSON (AST): làm sạch số trang/chú thích, nhận diện `Chương`, `Mục`, `Điều`, `Khoản` và trích xuất `metadata`. Điều không chia Khoản được bọc trong một `clause_1` giả định (Sprint 5). Parser không tách Điểm.
* **Module `chunking/`:** **Không parse lại regex text thô từ đầu**. Module này nhận Structured JSON từ Parser và chịu trách nhiệm tối ưu hóa ngữ nghĩa cho mô hình RAG:
  1. Kiểm soát giới hạn ký tự và token ($\le 1500$ chars cho Parent, $\le 256$ tokens cho Child).
  2. Tách các Điều dài thành nhiều Parent, tách các Khoản dài thành nhiều Child; không gộp nội dung qua ranh giới Khoản.
  3. Tách cấu trúc Child theo đơn vị whitespace trên văn bản gốc để ranh giới chunk và nội dung ổn định giữa các môi trường. `underthesea` tạo `seg_text`/`embed_text` và là bắt buộc: thiếu thư viện thì `word_segment()` và exporter dừng, không rơi về văn bản gốc. Phiên bản underthesea được ghi vào `chunking_report.json` để phía truy vấn tách từ cùng phiên bản.
  4. Đóng gói payload tương thích với Elasticsearch, Qdrant và Parent Key-Value Store.

---

## 2. Nguyên tắc Chunking Phân cấp (Parent - Child)

| # | Nguyên tắc | Chi tiết thực thi |
|---|-----------|-------------------|
| **P1** | **Tôn trọng ranh giới Điều luật** | Đơn vị Parent cơ sở là **Điều** (Article). Một Điều không bao giờ bị cắt xén tùy tiện trừ khi vượt quá ngưỡng $1500$ ký tự. |
| **P2** | **Small-to-Big Retrieval** | **Child Chunks** nhỏ ($\le 256$ tokens) phục vụ tìm kiếm chính xác (Dense BGE-M3 + BM25). Khi trúng tuyển, **Parent Chunk** ($\le 1500$ ký tự) được khôi phục tại bước `Parent-Context Resolver` để cung cấp toàn cảnh quy định cho LLM. |
| **P3** | **Bảo toàn Ngữ cảnh (Breadcrumb Preservation)** | Breadcrumb của Child: `Chương > Mục > Điều N. Tiêu đề > Khoản K > Điểm x-y`, chỉ ghi đúng Khoản của chính chunk. Breadcrumb của Parent của Điều dài ghi dải Khoản (`Khoản 1-10`). |
| **P4** | **Lặp lại Tiêu đề khi tách Điều dài** | Khi một Điều vượt ngưỡng phải chẻ thành nhiều Parent Chunks, tiêu đề Điều `[Điều X. Tiêu đề]` luôn được lặp lại ở đầu mỗi Parent để LLM không bị mất chủ thể điều chỉnh. |
| **P5** | **Tuân thủ Semantic ID** | ID của Parent và Child tuân thủ chặt chẽ Hợp đồng Dữ liệu (`docs/data_contract.md`). `chunk_id` là khóa xuyên suốt retrieval, reranking và citation (Sprint 6), nên chỉ phụ thuộc `clause_id` và số thứ tự phần trong Khoản. |
| **P6** | **Nguyên văn để trích dẫn** | `text`/`chunk_text` là nguyên văn của Khoản (hoặc phần của Khoản). Ngữ cảnh bổ sung (intro của Điều, câu dẫn danh sách Điểm) chỉ đưa vào `embed_text`/`embed_text_raw`. |

---

## 3. Quy tắc chi tiết: Parent Chunk Builder

### 3.1 Trường hợp 1: Điều bình thường ($\le 1500$ ký tự)
Toàn bộ nội dung của Điều (gồm tiêu đề, intro, các khoản, điểm) trở thành **1 Parent Chunk duy nhất**.

* **Semantic ID:** `{doc_id}_art_{article_number}` (VD: `l_22_2000_qh10_art_10`).
* **Breadcrumb:** `Chương 2 KẾT HÔN > Điều 10. Những trường hợp cấm kết hôn`
* **clause_refs:** dải Khoản thật của Điều (`Khoản 1-5`), rỗng với Điều không chia Khoản.
* **Nội dung:** 
  ```text
  [Điều 10. Những trường hợp cấm kết hôn]
  Việc kết hôn bị cấm trong những trường hợp sau đây:
  1. Người đang có vợ hoặc có chồng;
  2. Người mất năng lực hành vi dân sự;
  ...
  ```

### 3.2 Trường hợp 2: Điều DÀI (> 1500 ký tự)
Khi tổng ký tự của Điều vượt quá $1500$ ký tự, hệ thống gom nhóm các Khoản liên tiếp thành nhiều Parent Chunks:

* **Semantic ID:** `{doc_id}_art_{article_number}_p{index}` (VD: `l_22_2000_qh10_art_8_p1`, `l_22_2000_qh10_art_8_p2`).
* **Quy tắc lặp lại Header:** Mỗi Parent Chunk con đều bắt đầu bằng header của Điều; intro chỉ nằm ở Parent đầu. Header giữ tiêu đề Điều đầy đủ; chỉ breadcrumb rút gọn tiêu đề dài hơn 120 ký tự bằng “...”:
  ```text
  [Điều 8. Giải thích từ ngữ] (Lặp lại ở mỗi Parent)
  11. ...
  12. ...
  ```
* **Cập nhật Breadcrumb:** Breadcrumb của Parent được mở rộng thêm phạm vi nhóm Khoản, ví dụ:
  `Chương 1 NHỮNG QUY ĐỊNH CHUNG > Điều 8. Giải thích từ ngữ > Khoản 11-14`. Một Khoản bị tách qua hai Parent chỉ ghi một số (`Khoản 3`, không ghi `Khoản 3-3`).
* **Ngân sách intro:** Parent đầu chứa header + intro + phần đầu của Khoản đầu. Nếu không vừa, phần đầu của Khoản đầu được tách nhỏ hơn; intro trên khoảng 1.300 ký tự thì chunker báo lỗi thay vì sinh Parent quá ngưỡng. Intro trùng nguyên văn với đầu Khoản đầu tiên được bỏ, phép so sánh dùng Khoản gốc chứ không dùng phần đầu sau khi Khoản đã bị tách.

---

## 4. Quy tắc chi tiết: Child Chunk Builder

Child Chunk là đơn vị đưa vào vector hóa (BGE-M3) và lập chỉ mục BM25.

### 4.1 Giới hạn kích thước
* `CHILD_MAX_TOKENS = 256`: Tương thích với `max_seq_length` của các mô hình embedding tiếng Việt (BKAI, BGE-M3). Phần ngữ cảnh của `embed_text` được cắt để tổng số đơn vị của `embed_text` không vượt ngưỡng này.
* `CHILD_MAX_UNITS = 200`: Giới hạn 200 đơn vị whitespace trong văn bản gốc của mỗi Child (đơn vị tách nhỏ: 190); không phụ thuộc phiên bản tokenizer.
* `CHILD_MIN_WORDS = 20`: Mảnh dưới 20 từ **của cùng một Khoản** được gộp với mảnh liền kề, hoặc dời ranh giới với mảnh trước, nếu vẫn vừa giới hạn. Khoản ngắn trọn vẹn (vd “5. Giữa những người cùng giới tính.”) vẫn là một chunk riêng.
* `CHILD_MIN_CHARS = 10`: Đuôi dưới 10 ký tự luôn gộp vào chunk liền trước (`data_contract.md`, mục 5.2); exporter dừng nếu còn chunk dưới 10 ký tự.
* `CHILD_CONTEXT_MAX_WORDS = 60`: Số từ tối đa của phần ngữ cảnh (intro + câu dẫn) trong `embed_text`.
* Các ngưỡng đọc từ config (`child_max_units`, `child_min_words`, `child_max_tokens`, `child_context_max_words`), nên `run_experiment.py` so sánh được các cấu hình.

### 4.2 Chiến lược sinh Child Chunks từ Parent
1. **Một Khoản ($\le 200$ từ):** Trở thành 1 Child Chunk độc lập.
   * Semantic ID: `{clause_id}_chunk_1` (VD: `l_52_2014_qh13_art_5_clause_1_chunk_1`), `parent_clause_id = clause_id`.
2. **Điều không chia Khoản:** Chunk vẫn mang `clause_id = ..._clause_1` theo contract, nhưng `clause_ref = null`, `metadata.clause_number = null` và breadcrumb không ghi “Khoản 1”. Nhận diện: Điều chỉ có một clause và nội dung không mở đầu bằng “1.”.
3. **Khoản dài có danh sách Điểm (a), b), c)…):** Cắt tại ranh giới Điểm, gom các Điểm trọn vẹn vào từng phần; một Điểm chỉ bị tách theo câu khi tự nó vượt giới hạn. Mỗi phần ghi `point_ref` theo dải Điểm (`Điểm a-e`, `Điểm g-i`) và breadcrumb thêm dải Điểm. Phần thứ 2 trở đi mang câu dẫn của Khoản (“2. Cấm các hành vi sau đây:”) trong `embed_text`, không chép vào `text`. Dấu Điểm chỉ được nhận khi đứng đầu dòng hoặc sau “:”, “;”, “.” và chữ cái tăng liên tục từ “a” (bỏ f, j, w, z).
   * Semantic ID: `{clause_id}_chunk_{n}` (VD: `l_52_2014_qh13_art_5_clause_2_chunk_2`).
4. **Khoản dài không có danh sách Điểm (> 200 từ):** Cắt theo ranh giới câu; câu tự nó quá dài thì cắt theo số từ.
5. **Không gộp các Khoản ngắn liên tiếp:** Mỗi chunk thuộc đúng một Clause (`data_contract.md`, mục 3.4) để Strict Match và Parent Match (Sprint 6) tính được.

### 4.3 Chuẩn bị trường Vector Embedding (`embed_text`)
Để vector embedding thể hiện đầy đủ ngữ nghĩa và tăng độ chính xác của Dense Retrieval:
$$\text{embed\_text} = \text{seg}(\text{title}) + \text{seg}(\text{breadcrumb}) + \text{seg}(\text{intro} + \text{câu dẫn}) + \text{seg}(\text{body})$$
* Việc thêm `title` và `breadcrumb` giúp phân biệt chính xác hai điều khoản có nội dung tương tự nhau nhưng thuộc hai văn bản hoặc hai chương khác nhau.
* Intro của Điều (vd “Việc kết hôn bị cấm trong những trường hợp sau đây:”) được đưa vào mọi Child của Điều; nếu không, intro chỉ nằm trong Parent và không truy xuất được. Khi thiếu chỗ, câu dẫn được giữ trước, intro bị cắt bớt và ghi cảnh báo trong report.
* `embed_text_raw` có cùng nội dung nhưng không tách từ (cho model không cần tách từ như BGE-M3). `seg_text` chỉ là `text` đã tách từ.

---

## 5. Cấu trúc Bản ghi và Tích hợp Cơ sở Dữ liệu

### 5.1 Bản ghi Parent Chunk (Lưu tại Key-Value / Parent Store)
Phục vụ node **`Parent-Context Resolver`** tra cứu khi nhận được `parent_id` từ kết quả tìm kiếm:

```json
{
  "parent_id": "l_52_2014_qh13_art_5_p1",
  "doc_id": "l_52_2014_qh13",
  "title": "Luật Hôn nhân và gia đình",
  "text": "[Điều 5. Bảo vệ chế độ hôn nhân và gia đình]\n1. Quan hệ hôn nhân...\n2. Cấm các hành vi sau đây: a) ...",
  "breadcrumb": "Chương I NHỮNG QUY ĐỊNH CHUNG > Điều 5. Bảo vệ chế độ hôn nhân và gia đình > Khoản 1-2",
  "article_ref": "Điều 5",
  "clause_refs": "Khoản 1-2",
  "chunk_type": "ARTICLE",
  "child_ids": [
    "l_52_2014_qh13_art_5_clause_1_chunk_1",
    "l_52_2014_qh13_art_5_clause_2_chunk_1",
    "l_52_2014_qh13_art_5_clause_2_chunk_2"
  ],
  "metadata": {
    "document_type": "Luật",
    "document_number": "52/2014/QH13",
    "effective_date": "2015-01-01",
    "validity_status": "Còn hiệu lực"
  }
}
```

### 5.2 Bản ghi Child Chunk (Lưu tại Qdrant & Elasticsearch)
Phục vụ **`Dense Vector Search (BGE-M3)`** và **`Sparse Search (BM25)`** (trích các trường chính):

```json
{
  "id": "l_52_2014_qh13_art_5_clause_2_chunk_2",
  "chunk_id": "l_52_2014_qh13_art_5_clause_2_chunk_2",
  "parent_id": "l_52_2014_qh13_art_5_p1",
  "clause_id": "l_52_2014_qh13_art_5_clause_2",
  "parent_clause_id": "l_52_2014_qh13_art_5_clause_2",
  "title": "Luật Hôn nhân và gia đình",
  "text": "g) Thực hiện sinh con bằng kỹ thuật hỗ trợ sinh sản vì mục đích thương mại...; h) Bạo lực gia đình; i) ...",
  "seg_text": "g ) Thực_hiện sinh con bằng kỹ_thuật hỗ_trợ sinh_sản vì mục_đích thương_mại ...",
  "embed_text": "Luật Hôn_nhân và gia_đình Chương I ... > Khoản 2 > Điểm g-i 2 . Cấm các hành_vi sau đây : g ) Thực_hiện ...",
  "breadcrumb": "Chương I NHỮNG QUY ĐỊNH CHUNG > Điều 5. Bảo vệ chế độ hôn nhân và gia đình > Khoản 2 > Điểm g-i",
  "article_ref": "Điều 5",
  "clause_ref": "Khoản 2",
  "point_ref": "Điểm g-i",
  "chunk_type": "ARTICLE",
  "document_type": "Luật",
  "document_number": "52/2014/QH13",
  "effective_date": "2015-01-01",
  "validity_status": "Còn hiệu lực"
}
```

---

## 6. Xử lý các Trường hợp Ngoại lệ (Fallback)

1. **Văn bản phi cấu trúc hoặc văn bản rỗng:**
   * Nếu văn bản không có danh sách `articles` hợp lệ (chỉ có văn bản phẳng `content_text`), hệ thống chuyển tự động sang **Sliding Window Fallback** (`max_words = 260`, `overlap = 40 words`).
2. **Khoản/Điểm không thể phân rã:**
   * Điều có clause rỗng: toàn bộ nội dung Điều được đưa vào 1 Parent Chunk và 1 Child Chunk duy nhất mang hậu tố `_chunk_1`.
3. **Văn bản hết hiệu lực:**
   * Thuộc tính `validity_status = "Hết hiệu lực"` được lưu trong metadata của mọi chunk để phục vụ **`Metadata & Temporal Pre-filter`** tại tầng Retrieval trước khi chạy Vector Search.

---

## 7. Xuất corpus chunks

Chạy exporter từ thư mục gốc repository, trên môi trường có `underthesea` (thiếu thì exporter dừng):

```powershell
.\.venv\Scripts\python.exe chunking\export_legal_chunks.py
```

Exporter đọc toàn bộ JSON trong `parser/parsed_jsons/` và sinh:

* `data/chunking_output/chunks.jsonl` — Child chunks, một bản ghi JSON trên mỗi dòng.
* `data/chunking_output/parents.json` — Parent chunks liên kết với Child chunks.
* `data/chunking_output/chunking_report.json` — Số lượng, nguồn, phiên bản underthesea, kết quả theo từng văn bản và cảnh báo sinh từ kiểm tra thật.
* Payload của mỗi dòng `chunks.jsonl` tuân theo [`schemas/chunk_payload_schema.json`](../schemas/chunk_payload_schema.json).

Quy tắc chia nội dung lấy từ `chunking/chunking_rules.py`. Trước khi ghi file, exporter kiểm tra và dừng nếu sai:

* ID ASCII, ID duy nhất, liên kết Parent–Child, `clause_id` của mọi chunk có trong parser;
* giới hạn 1.500 ký tự của Parent, 200 đơn vị từ và tối thiểu 10 ký tự của Child;
* breadcrumb của Child chỉ chứa đúng Khoản của chunk (không dải Khoản, không “(phần”), Điều không chia Khoản không ghi Khoản;
* thứ tự token của nội dung clause so với parser, intro có trong Parent và trong `embed_text` của ít nhất một Child;
* các alias payload.

Cảnh báo (không dừng): mảnh dưới 20 từ không gộp được, intro bị cắt bớt trong `embed_text`, văn bản có `validity_status = "Không xác định"`. Các kiểm tra này xác nhận độ toàn vẹn so với JSON parser; chúng không chứng minh JSON parser đã chép đủ hoặc chính xác toàn văn luật. Các nguồn thiếu điều hoặc bị cắt phải được xử lý ở parser/nguồn pháp luật.

## 8. Kết quả Thử nghiệm & Đánh giá Cấu hình (Evaluation Matrix)

Dựa trên script thử nghiệm `run_experiment.py --export-reports` thực thi trên 21 văn bản trong `parser/parsed_jsons/` (cùng nguồn với exporter), bảng số liệu so sánh 4 cấu hình đã được xuất tại [`chunking_evaluation.xlsx`](chunking_evaluation.xlsx). “Mảnh < 20 từ” đếm chunk dưới 20 từ thuộc Khoản bị tách thành nhiều chunk.

| Cấu hình | Ngưỡng Parent (chars) | Ngưỡng Child (tokens / từ) | Min Child (từ) | Tổng Parent | Tổng Child | Tỷ lệ Child/Parent | Parent TB (chars) | Child TB (từ) | Mảnh < 20 từ | Chunk có point_ref | Đánh giá & Khuyến nghị |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Config A (Baseline)** | **1500** | **256 / 200** | **20** | **923** | **2003** | **2.17** | **743.4** | **70.0** | **0** | **153** | **KHUYẾN NGHỊ**: Đủ ngữ cảnh cho Parent, Child vừa giới hạn 256 token của BKAI/BGE-M3. |
| **Config B (Small)** | 800 | 128 / 100 | 15 | 1353 | 2647 | 1.96 | 529.0 | 53.1 | 68 | 489 | Phù hợp khi dùng Embedding context hẹp (128 tokens); Parent tăng 47%, nhiều Khoản bị cắt vụn. |
| **Config C (Large)** | 2500 | 512 / 350 | 30 | 806 | 1900 | 2.36 | 842.5 | 73.8 | 0 | 26 | Giữ ngữ cảnh rộng nhưng Child vượt 256 token của BKAI; rủi ro loãng vector. |
| **Config D (Strict)** | 1500 | 256 / 200 | 1 | 923 | 2003 | 2.17 | 743.4 | 70.0 | 3 | 153 | Không áp quy tắc gộp mảnh: còn 3 mảnh vụn của Khoản bị tách. |

Các trường hợp mẫu minh họa (Điều bình thường, Điều dài tách Parent, Khoản có danh sách Điểm, Điều có intro và Định dạng DB Payload) được lưu trữ đầy đủ trong [`chunking_examples.json`](chunking_examples.json).

---

## 9. Tổng kết

Việc tinh chỉnh và loại bỏ bộ Parser trùng lặp trong module Chunking mang lại các lợi ích trực tiếp:
1. **Kiến trúc sạch (Clean Architecture):** Tách bạch rõ ranh giới: `parser/` xử lý cấu trúc file PDF/TXT $\rightarrow$ `chunking/` xử lý tối ưu hóa token và quan hệ Parent-Child cho RAG.
2. **Khớp chuẩn với `system_architecture.drawio`:** Dữ liệu đầu ra của Chunking tương thích trực tiếp với các node `Vector DB (Qdrant)`, `Elasticsearch Index` và `Parent-Context Resolver`.
3. **Tuân thủ `data_contract.md`:** Đảm bảo toàn bộ Semantic ID và schema metadata nhất quán trên toàn hệ thống.
4. **Đáp ứng đầy đủ 4 Sản phẩm đầu ra của Yêu cầu dự án:**
   * [`chunking_strategy.md`](chunking_strategy.md): Tài liệu chiến lược & nguyên tắc.
   * [`chunking_rules.py`](chunking_rules.py): Mã nguồn module chunking.
   * [`chunking_evaluation.xlsx`](chunking_evaluation.xlsx): Bảng Excel đánh giá so sánh các cấu hình.
   * [`chunking_examples.json`](chunking_examples.json): File JSON chứa các mẫu chunking thực tế.
