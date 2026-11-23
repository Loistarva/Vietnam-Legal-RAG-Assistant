# Chiến lược Chunking cho Vietnamese Legal RAG Assistant

> **Phiên bản:** 2.0 (Cập nhật đồng bộ theo `system_architecture.drawio` & `docs/data_contract.md`)  
> **Trạng thái:** Đã chuẩn hóa tích hợp với module `parser/`  
> **Mục tiêu:** Định nghĩa quy tắc tạo Parent-Child Chunks từ dữ liệu Structured Legal JSON, kiểm soát token budget, gắn breadcrumb phân cấp và chuẩn bị payload cho Qdrant, Elasticsearch, và Parent-Context Resolver.

---

## 1. Vị trí Module Chunking trong Kiến trúc Hệ thống

Theo sơ đồ kiến trúc tổng thể (`system_architecture.drawio` & `new data_flow.drawio.xml`), luồng xử lý tài liệu phân định rõ ràng giữa **Parser** và **Chunking Engine**:

```
[Raw Legal PDF]
       │
       ▼ (parser/cleaner.py & parser/parser.py)
[Structured Legal JSON] (Document -> Articles -> Raw Clauses/Points)
       │ (Tuân thủ docs/data_contract.md)
       ▼
┌─────────────────────────────────────────────────────────────┐
│             MODULE CHUNKING (chunking_rules.py)             │
│  - Phân bổ ngân sách token (PARENT_MAX_CHARS, CHILD_TOKENS) │
│  - Gộp / Tách Parent Chunks (theo Điều hoặc nhóm Khoản)     │
│  - Tạo Child Chunks (word-segmented qua underthesea)        │
│  - Gắn chuỗi Breadcrumb định vị phân cấp                    │
│  - Gán Semantic ID ([doc_id]_art_[num]_chunk_[cl]_[pt])     │
└─────────────────────────────────────────────────────────────┘
       │                                     │
       ├─────────────────┐                   │
       ▼                 ▼                   ▼
[Elasticsearch Index] [Vector DB: Qdrant] [Parent Store / KV DB]
  (Sparse BM25)      (Dense BGE-M3)      (Phục vụ Parent-Context Resolver)
```

### Phân định trách nhiệm (Separation of Concerns):
* **Module `parser/`:** Chịu trách nhiệm trích xuất cấu trúc văn bản thô (PDF/TXT) thành cây dữ liệu phân cấp JSON (AST): làm sạch số trang/chú thích, nhận diện `Chương`, `Mục`, `Điều`, `Khoản`, `Điểm` và trích xuất `metadata`.
* **Module `chunking/`:** **Không parse lại regex text thô từ đầu**. Module này nhận Structured JSON từ Parser và chịu trách nhiệm tối ưu hóa ngữ nghĩa cho mô hình RAG:
  1. Kiểm soát giới hạn ký tự và token ($\le 1500$ chars cho Parent, $\le 256$ tokens cho Child).
  2. Gom cụm các Khoản ngắn, tách các Điều dài hoặc Khoản dài.
  3. Word-segmentation tiếng Việt (`underthesea`) cho Child embedding.
  4. Đóng gói payload tương thích với Elasticsearch, Qdrant và Parent Key-Value Store.

---

## 2. Nguyên tắc Chunking Phân cấp (Parent - Child)

| # | Nguyên tắc | Chi tiết thực thi |
|---|-----------|-------------------|
| **P1** | **Tôn trọng ranh giới Điều luật** | Đơn vị Parent cơ sở là **Điều** (Article). Một Điều không bao giờ bị cắt xén tùy tiện trừ khi vượt quá ngưỡng $1500$ ký tự. |
| **P2** | **Small-to-Big Retrieval** | **Child Chunks** nhỏ ($\le 256$ tokens) phục vụ tìm kiếm chính xác (Dense BGE-M3 + BM25). Khi trúng tuyển, **Parent Chunk** ($\le 1500$ ký tự) được khôi phục tại bước `Parent-Context Resolver` để cung cấp toàn cảnh quy định cho LLM. |
| **P3** | **Bảo toàn Ngữ cảnh (Breadcrumb Preservation)** | Mọi Chunk (cả Parent và Child) luôn mang chuỗi breadcrumb: `Chương > Mục > Điều > Khoản > Điểm`. |
| **P4** | **Lặp lại Tiêu đề khi tách Điều dài** | Khi một Điều vượt ngưỡng phải chẻ thành nhiều Parent Chunks, tiêu đề Điều `[Điều X. Tiêu đề]` luôn được lặp lại ở đầu mỗi Parent để LLM không bị mất chủ thể điều chỉnh. |
| **P5** | **Tuân thủ Semantic ID** | ID của Parent và Child tuân thủ chặt chẽ Hợp đồng Dữ liệu (`docs/data_contract.md`). |

---

## 3. Quy tắc chi tiết: Parent Chunk Builder

### 3.1 Trường hợp 1: Điều bình thường ($\le 1500$ ký tự)
Toàn bộ nội dung của Điều (gồm tiêu đề, lời dẫn, các khoản, điểm) trở thành **1 Parent Chunk duy nhất**.

* **Semantic ID:** `{doc_id}_art_{article_number}` (VD: `nd_100_2019_nd_cp_art_6`).
* **Breadcrumb:** `Chương I ... > Mục 1 ... > Điều 6. Xử phạt người điều khiển xe mô tô...`
* **Nội dung:** 
  ```text
  [Điều 6. Xử phạt người điều khiển xe mô tô...]
  1. Phạt tiền từ...
  2. Phạt tiền từ...
    a) Hành vi A...
    b) Hành vi B...
  ```

### 3.2 Trường hợp 2: Điều DÀI (> 1500 ký tự)
Khi tổng ký tự của Điều vượt quá $1500$ ký tự, hệ thống gom nhóm các Khoản liên tiếp thành nhiều Parent Chunks:

* **Semantic ID:** `{doc_id}_art_{article_number}_p{index}` (VD: `l01_art_2_p1`, `l01_art_2_p2`).
* **Quy tắc lặp lại Header:** Mỗi Parent Chunk con đều bắt đầu bằng header của Điều:
  ```text
  [Điều 2. Những nguyên tắc cơ bản...] (Lặp lại ở mỗi Parent)
  Khoản 4. ...
  Khoản 5. ...
  ```
* **Cập nhật Breadcrumb:** Breadcrumb được mở rộng thêm phạm vi nhóm Khoản, ví dụ:
  `Chương I > Điều 2. Những nguyên tắc cơ bản > Khoản 4-5`

---

## 4. Quy tắc chi tiết: Child Chunk Builder

Child Chunk là đơn vị đưa vào vector hóa (BGE-M3) và lập chỉ mục BM25.

### 4.1 Giới hạn kích thước
* `CHILD_MAX_TOKENS = 256`: Tương thích với `max_seq_length` của các mô hình embedding tiếng Việt (BKAI, BGE-M3).
* `CHILD_MAX_UNITS = 200`: Giới hạn đơn vị từ sau word-segmentation.
* `CHILD_MIN_WORDS = 20`: Ngưỡng lọc / gom nhóm để loại trừ chunk rác.

### 4.2 Chiến lược sinh Child Chunks từ Parent
1. **Một Khoản đủ độ dài ($\ge 20$ từ và $\le 200$ từ):** Trở thành 1 Child Chunk độc lập.
   * Semantic ID: `{parent_id}_chunk_{clause_number}` (VD: `nd_100_2019_nd_cp_art_6_chunk_2`).
2. **Khoản có nhiều Điểm chi tiết:** Mỗi điểm kết hợp với phần dẫn của khoản tạo thành 1 Child Chunk:
   * Semantic ID: `{parent_id}_chunk_{clause_number}_{point_letter}` (VD: `nd_100_2019_nd_cp_art_6_chunk_2_b`).
3. **Các Khoản ngắn liên tiếp (< 20 từ):** Hệ thống tự động gom các khoản ngắn kề nhau vào cùng 1 Child Chunk để đảm bảo tính trọn vẹn của ý nghĩa pháp lý.
4. **Trường hợp Khoản đơn lẻ quá dài (> 200 từ):** Cắt theo ranh giới câu hoặc trượt cửa sổ sliding window với overlap 40 từ.

### 4.3 Chuẩn bị trường Vector Embedding (`embed_text`)
Để vector embedding thể hiện đầy đủ ngữ nghĩa và tăng độ chính xác của Dense Retrieval:
$$\text{embed\_text} = \text{word\_segment}(\text{title}) + \text{" "} + \text{word\_segment}(\text{breadcrumb}) + \text{" "} + \text{word\_segment}(\text{body})$$
* Việc thêm `title` và `breadcrumb` giúp phân biệt chính xác hai điều khoản có nội dung tương tự nhau nhưng thuộc hai văn bản hoặc hai chương khác nhau.

---

## 5. Cấu trúc Bản ghi và Tích hợp Cơ sở Dữ liệu

### 5.1 Bản ghi Parent Chunk (Lưu tại Key-Value / Parent Store)
Phục vụ node **`Parent-Context Resolver`** tra cứu khi nhận được `parent_id` từ kết quả tìm kiếm:

```json
{
  "parent_id": "nd_100_2019_nd_cp_art_6",
  "doc_id": "nd_100_2019_nd_cp",
  "title": "Nghị định quy định xử phạt vi phạm hành chính...",
  "text": "[Điều 6. Xử phạt người điều khiển xe...]\n1. Phạt tiền...\n2. Phạt tiền...",
  "breadcrumb": "Chương II > Mục 1 > Điều 6. Xử phạt...",
  "article_ref": "Điều 6",
  "clause_refs": "Khoản 1-2",
  "chunk_type": "ARTICLE",
  "child_ids": [
    "nd_100_2019_nd_cp_art_6_chunk_2_b",
    "nd_100_2019_nd_cp_art_6_chunk_2_c"
  ],
  "metadata": {
    "document_type": "Nghị định",
    "document_number": "100/2019/NĐ-CP",
    "effective_date": "2020-01-01",
    "validity_status": "Còn hiệu lực"
  }
}
```

### 5.2 Bản ghi Child Chunk (Lưu tại Qdrant & Elasticsearch)
Phục vụ **`Dense Vector Search (BGE-M3)`** và **`Sparse Search (BM25)`**:

```json
{
  "id": "nd_100_2019_nd_cp_art_6_chunk_2_b",
  "parent_id": "nd_100_2019_nd_cp_art_6",
  "doc_id": "nd_100_2019_nd_cp",
  "title": "Nghị định quy định xử phạt vi phạm hành chính...",
  "text": "Phạt tiền từ 300.000 đồng đến 400.000 đồng đối với người điều khiển xe thực hiện hành vi: Không đội mũ bảo hiểm...",
  "seg_text": "Phạt_tiền từ 300.000 đồng đến 400.000 đồng đối_với người điều_khiển xe thực_hiện hành_vi : Không đội mũ_bảo_hiểm...",
  "embed_text": "Nghị_định quy_định... Chương II > Điều 6 > Khoản 2 > Điểm b Phạt_tiền từ 300.000...",
  "breadcrumb": "Chương II > Điều 6 > Khoản 2 > Điểm b",
  "article_ref": "Điều 6",
  "clause_ref": "Khoản 2",
  "point_ref": "Điểm b",
  "chunk_type": "ARTICLE",
  "document_type": "Nghị định",
  "document_number": "100/2019/NĐ-CP",
  "effective_date": "2020-01-01",
  "validity_status": "Còn hiệu lực"
}
```

---

## 6. Xử lý các Trường hợp Ngoại lệ (Fallback)

1. **Văn bản phi cấu trúc hoặc văn bản rỗng:**
   * Nếu văn bản không có danh sách `articles` hợp lệ (chỉ có văn bản phẳng `content_text`), hệ thống chuyển tự động sang **Sliding Window Fallback** (`max_words = 260`, `overlap = 40 words`).
2. **Khoản/Điểm không thể phân rã:**
   * Toàn bộ nội dung Điều luật được đưa vào 1 Parent Chunk và 1 Child Chunk duy nhất mang hậu tố `_chunk_0`.
3. **Văn bản hết hiệu lực:**
   * Thuộc tính `validity_status = "Hết hiệu lực"` được lưu trong metadata của mọi chunk để phục vụ **`Metadata & Temporal Pre-filter`** tại tầng Retrieval trước khi chạy Vector Search.

---

## 7. Kết quả Thử nghiệm & Đánh giá Cấu hình (Evaluation Matrix)

Dựa trên script thử nghiệm `run_experiment.py` thực thi trên toàn bộ các tệp dữ liệu mẫu trong dự án (`L01.json`, `ND01.json`, `TT01.json`, `sample_documents.json`, `parsed_output_test.json`), bảng số liệu so sánh 4 cấu hình đã được xuất tại [`chunking_evaluation.xlsx`](file:///d:/AI_PRJ/Vietnam-Legal-RAG-Assistant/chunking/chunking_evaluation.xlsx):

| Cấu hình | Ngưỡng Parent (chars) | Ngưỡng Child (tokens) | Min Child (từ) | Tổng Parent | Tổng Child | Tỷ lệ Child/Parent | Parent TB (chars) | Child TB (từ) | Bao phủ Breadcrumb | Đánh giá & Khuyến nghị |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Config A (Baseline)** | **1500** | **256** | **20** | **250** | **572** | **2.29** | **551.9** | **78.4** | **100%** | **KHUYẾN NGHỊ**: Cân bằng hoàn hảo giữa khả năng bao quát của Parent và độ chính xác của Child. |
| **Config B (Small)** | 800 | 128 | 15 | 352 | 668 | 1.90 | 412.5 | 58.2 | 100% | Phù hợp khi dùng Embedding context hẹp (128 tokens); số lượng parent tăng 40%. |
| **Config C (Large)** | 2500 | 512 | 30 | 225 | 513 | 2.28 | 610.2 | 87.1 | 100% | Giữ ngữ cảnh rộng nhưng tăng nguy cơ mất tập trung (dilution) khi so khớp vector. |
| **Config D (Strict)** | 1500 | 256 | 1 | 250 | 596 | 2.38 | 551.9 | 72.8 | 100% | Không gom khoản ngắn $\rightarrow$ sinh ra nhiều chunk vụn (< 20 từ) gây nhiễu Vector DB. |

Các trường hợp mẫu minh họa (Điều bình thường, Điều dài tách Parent, Khoản có nhiều Điểm, và Định dạng DB Payload) được lưu trữ đầy đủ trong [`chunking_examples.json`](file:///d:/AI_PRJ/Vietnam-Legal-RAG-Assistant/chunking/chunking_examples.json).

---

## 8. Tổng kết

Việc tinh chỉnh và loại bỏ bộ Parser trùng lặp trong module Chunking mang lại các lợi ích trực tiếp:
1. **Kiến trúc sạch (Clean Architecture):** Tách bạch rõ ranh giới: `parser/` xử lý cấu trúc file PDF/TXT $\rightarrow$ `chunking/` xử lý tối ưu hóa token và quan hệ Parent-Child cho RAG.
2. **Khớp chuẩn với `system_architecture.drawio`:** Dữ liệu đầu ra của Chunking tương thích trực tiếp với các node `Vector DB (Qdrant)`, `Elasticsearch Index` và `Parent-Context Resolver`.
3. **Tuân thủ `data_contract.md`:** Đảm bảo toàn bộ Semantic ID và schema metadata nhất quán trên toàn hệ thống.
4. **Đáp ứng đầy đủ 4 Sản phẩm đầu ra của Yêu cầu dự án:**
   * [`chunking_strategy.md`](file:///d:/AI_PRJ/Vietnam-Legal-RAG-Assistant/chunking/chunking_strategy.md): Tài liệu chiến lược & nguyên tắc.
   * [`chunking_rules.py`](file:///d:/AI_PRJ/Vietnam-Legal-RAG-Assistant/chunking/chunking_rules.py): Mã nguồn module chunking.
   * [`chunking_evaluation.xlsx`](file:///d:/AI_PRJ/Vietnam-Legal-RAG-Assistant/chunking/chunking_evaluation.xlsx): Bảng Excel đánh giá so sánh các cấu hình.
   * [`chunking_examples.json`](file:///d:/AI_PRJ/Vietnam-Legal-RAG-Assistant/chunking/chunking_examples.json): File JSON chứa các mẫu chunking thực tế.
