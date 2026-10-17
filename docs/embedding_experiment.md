# Embedding Experiment — Vietnam-Legal-RAG-Assistant

## 1. Bối cảnh bài toán

**Vietnam-Legal-RAG-Assistant** là hệ thống RAG hỗ trợ hỏi đáp dựa trên **Luật Hôn nhân và Gia đình Việt Nam**.

Mục tiêu của hệ thống không chỉ là tạo ra một câu trả lời có vẻ hợp lý, mà phải **tìm đúng các Điều/Khoản pháp luật liên quan** để đưa vào context cho LLM.

Pipeline tổng thể:

```text
Luật Hôn nhân và Gia đình
            ↓
          Parser
            ↓
         Chunking
            ↓
        Embedding
            ↓
       Vector DB
            ↓
        Retrieval
            ↓
        Reranker
            ↓
         RAG / LLM
```

Trong pipeline này, module Embedding & Dense Retrieval có nhiệm vụ:
- Chuyển trường `embed_text` (gồm breadcrumb và nội dung đã word-segment) của mỗi chunk pháp luật thành vector;
- Tạo vector cho câu hỏi của người dùng;
- Lưu vector kèm `chunk_text`, `parent_clause_id` và metadata vào Vector DB (Qdrant);
- Áp dụng bộ lọc tiền truy vấn (Metadata Pre-filter) loại bỏ các văn bản có `validity_status == "Hết hiệu lực"`;
- Cung cấp `DenseRetriever.search(query, top_k)` theo đúng schema chung cho nhánh Dense-only và nhánh Hybrid Retrieval (RRF).

---

## 2. Mục tiêu của thử nghiệm

Mục tiêu của thử nghiệm là lựa chọn một embedding model phù hợp với bài toán **Legal RAG tiếng Việt**, trong đó ưu tiên:

1. **Độ chính xác retrieval**: Tìm đúng Điều/Khoản liên quan (đánh giá qua Strict Match Recall@K và Parent Match Recall@K).
2. **Khả năng hiểu tiếng Việt và thuật ngữ pháp lý**: Nhận diện đồng nghĩa và câu hỏi tự nhiên của người dân.
3. **Khả năng xử lý các chunk của Luật Hôn nhân và Gia đình**: Tương thích với cấu trúc phân mảnh Parent-Child (Child Chunk $\le 256$ tokens).
4. **Tốc độ tạo embedding và truy vấn**: Đo lường throughput và query latency.
5. **Kích thước vector và chi phí lưu trữ**: Đánh giá dung lượng RAM/Disk trên Vector DB.
6. **Khả năng triển khai trên môi trường của nhóm**: Chạy ổn định trên cả CPU và GPU.

Đặc biệt, với RAG pháp luật:

> **Độ chính xác của retrieval được ưu tiên hơn tốc độ embedding thuần túy.**

Lý do là nếu retrieval không đưa đúng Điều/Khoản vào context thì LLM dù mạnh vẫn có thể trả lời sai hoặc thiếu căn cứ pháp lý.

---

## 3. Đặc trưng của dữ liệu cần Embedding

Dữ liệu của hệ thống tuân thủ kiến trúc phân cấp 4 tầng đã chốt ở Sprint 5:

```text
Document (Văn bản)
   ↓
Article (Điều)
   ↓
Clause (Khoản - Parent Chunk)
   ↓
Chunk (Điểm / Phân đoạn - Child Chunk)
```

Nội dung có nhiều thuật ngữ pháp lý và các quy định có ngữ nghĩa gần nhau.

Ví dụ câu hỏi:
> "Bao nhiêu tuổi thì được kết hôn?"

Cần truy xuất đến chunk chứa quy định tại Điều 8 Luật Hôn nhân và Gia đình 2014:
> "Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên..."

Hoặc câu hỏi:
> "Sau khi ly hôn thì ai được nuôi con?"

Cần liên kết đến Điều 81 quy định về việc trông nom, chăm sóc, nuôi dưỡng và giáo dục con sau khi ly hôn. Do đó, embedding model cần biểu diễn chính xác **ý nghĩa pháp lý của câu hỏi** chứ không chỉ khớp từ khóa bề mặt.

---

## 4. Tiêu chí đánh giá Embedding Model

### 4.1. Retrieval Accuracy
Model cần đưa chunk pháp luật liên quan vào Top-K. Các chỉ số đánh giá chính trên tập Benchmark Sprint 6:
- **Strict Match Recall@K** ($K \in \{1, 5, 10\}$): `chunk_id` trả về khớp chính xác với `gold_context_ids`.
- **Parent Match Recall@K** ($K \in \{1, 5, 10\}$): `parent_clause_id` của chunk trả về khớp với Khoản cha của `gold_context_ids`.
- **MRR@10** và **NDCG@10**.

Mục tiêu chất lượng Retrieval của hệ thống:
> **Recall@5 ≥ 85%**

### 4.2. Khả năng hiểu tiếng Việt
Model phải xử lý tốt câu hỏi tiếng Việt tự nhiên, từ đồng nghĩa và cách diễn đạt đời thường không trùng nguyên văn câu chữ trong luật.

### 4.3. Khả năng xử lý thuật ngữ pháp lý
Đánh giá trên 6 nhóm chủ đề trọng tâm của Benchmark:
- Kết hôn (điều kiện kết hôn, thẩm quyền đăng ký, kết hôn trái pháp luật);
- Quan hệ giữa vợ và chồng (nhân thân, đại diện);
- Chế độ tài sản của vợ chồng (tài sản chung, tài sản riêng, chia tài sản);
- Ly hôn (thuận tình, đơn phương, chia tài sản và quyền nuôi con khi ly hôn);
- Quan hệ giữa cha mẹ và con;
- Nghĩa vụ cấp dưỡng.

### 4.4. Khả năng xử lý độ dài Chunk
Trong pipeline hiện tại, Child Chunk được giới hạn $\le 256$ tokens kèm chuỗi Breadcrumb (`Chương > Mục > Điều > Khoản`), do đó mọi model có `max_seq_length >= 256` đều không bị cắt cụt thông tin.

### 4.5. Tốc độ (Latency & Throughput)
Ghi nhận:
- Embedding throughput (`chunks/s`);
- Thời gian tạo index cho toàn bộ corpus;
- Thời gian mã hóa câu hỏi (`query_encode_ms`) và tìm kiếm vector (`vector_search_ms`).

### 4.6. Kích thước Vector (Dimension)
Ảnh hưởng trực tiếp đến dung lượng lưu trữ Qdrant, bộ nhớ RAM và tốc độ tính khoảng cách Cosine.

---

## 5. Các Model được nghiên cứu và đưa vào thực nghiệm

Dự án đã khảo sát các dòng mô hình phổ biến cho tiếng Việt và tiến hành chạy thực nghiệm trực tiếp với 3 model ID xác thực trên Hugging Face:

1. `AITeamVN/Vietnamese_Embedding`
2. `bkai-foundation-models/vietnamese-bi-encoder`
3. `BAAI/bge-m3`

*(Lưu ý: Một số tên model trong giai đoạn khảo sát lý thuyết ban đầu như `BAAI/bge-vi-base` không tồn tại model ID chính thức trên Hugging Face nên được thay thế hoàn toàn bằng `bkai-foundation-models/vietnamese-bi-encoder`).*

---

## 6. Phân tích chi tiết các ứng viên

### 6.1. `bkai-foundation-models/vietnamese-bi-encoder`
- **Đặc điểm kỹ thuật:** Mô hình Bi-Encoder chuyên biệt cho tiếng Việt, yêu cầu tách từ (word segmentation) bằng `underthesea` trước khi encode. Độ dài tối đa 256 tokens, kích thước vector **768 chiều**.
- **Tương thích kiến trúc:** Khớp hoàn toàn với thiết kế Child Chunk ($\le 256$ tokens, đã tích hợp `underthesea` tạo trường `embed_text` từ Sprint 5).
- **Đánh giá:** Ứng viên hàng đầu về sự cân bằng giữa độ chính xác tiếng Việt, tốc độ truy vấn nhanh và dung lượng lưu trữ tối ưu.

### 6.2. `AITeamVN/Vietnamese_Embedding`
- **Đặc điểm kỹ thuật:** Fine-tune từ nền tảng `BAAI/bge-m3` trên khoảng 300.000 triplets tiếng Việt. Kích thước vector **1024 chiều**, độ dài tối đa **2048 tokens**.
- **Benchmark tham khảo:** Đạt kết quả cao trên tập Legal Zalo 2021 (MRR@10: `0.8181`, Accuracy@5: `0.9305`).
- **Đánh giá:** Ứng viên rất mạnh về chất lượng ngữ nghĩa pháp lý tiếng Việt, nhưng kích thước mô hình lớn và độ trễ trên CPU cao hơn đáng kể so với BKAI.

### 6.3. `BAAI/bge-m3`
- **Đặc điểm kỹ thuật:** Mô hình đa ngôn ngữ (Multilingual), kích thước vector **1024 chiều**, hỗ trợ context dài tới **8192 tokens**.
- **Đánh giá:** Đóng vai trò là baseline đa ngôn ngữ mạnh để đối chứng với các mô hình chuyên biệt tiếng Việt.

### 6.4. Các mô hình khảo sát lý thuyết khác (Đối chứng tài liệu)
- **`sBERT-Vi` & `PhoBERT`:** Mạnh về biểu diễn ngôn ngữ tiếng Việt tổng quát (768 chiều), nhưng `PhoBERT` gốc không được huấn luyện bằng hàm mục tiêu Contrastive Learning cho bài toán bất đối xứng (Query-to-Passage Retrieval).
- **`ViEmbedding`:** Tốc độ rất nhanh (dimension 300) nhưng độ chính xác ngữ nghĩa thấp, dễ làm rơi Điều/Khoản quan trọng khỏi Top-K.
- **`intfloat/multilingual-e5-base`:** Đa ngôn ngữ 768 chiều (max 512 tokens), không có lợi thế vượt trội so với BKAI và AITeamVN trên văn bản luật Việt Nam.
- **`hivetechVN/vietnamese-sbert-base-law-768-v2`:** Định hướng domain pháp luật nhưng thiếu thông tin công bố rõ ràng về tập dữ liệu huấn luyện và license.

---

## 7. Bảng tổng hợp 3 Model chạy thực nghiệm

| Model ID đã chạy | Hướng tiếp cận | Max Tokens | Dimension | Vai trò trong dự án |
| :--- | :--- | ---: | ---: | :--- |
| `bkai-foundation-models/vietnamese-bi-encoder` | Vietnamese Bi-Encoder + Word Segmentation (`underthesea`) | 256 | 768 | Ứng viên chính (Tối ưu tốc độ & tương thích `embed_text`) |
| `AITeamVN/Vietnamese_Embedding` | Fine-tuned từ BGE-M3 cho Retrieval/Legal tiếng Việt | 2048 | 1024 | Ứng viên chính (Ưu tiên chất lượng ngữ nghĩa) |
| `BAAI/bge-m3` | Multilingual Dense Retrieval, context dài | 8192 | 1024 | Baseline đa ngôn ngữ đối chứng |

---

## 8. Giao thức tích hợp với Chunking & Data Contract (Sprint 5 $\rightarrow$ Sprint 6)

Module Embedding & Dense Retrieval tuân thủ tuyệt đối Hợp đồng Dữ liệu dùng chung:

```text
Parser (parser/parsed_jsons/*.json)
   ↓
Chunking (chunking/chunking_rules.py)
   ↓
Embedding & Indexing (scripts/build_index.py -> LegalVectorStore)
   ↓
Dense Retrieval (embedding/dense_retriever.py)
```

### 8.1. Schema Chunk đầu vào (Input Contract)
Mỗi bản ghi chunk chuyển sang cho `DenseRetriever.index_chunks()` bắt buộc phân biệt rõ `chunk_text` và `embed_text`:

```json
{
  "document_id": "l_52_2014_qh13",
  "article_id": "l_52_2014_qh13_art_8",
  "clause_id": "l_52_2014_qh13_art_8_clause_1",
  "chunk_id": "l_52_2014_qh13_art_8_clause_1_chunk_1",
  "parent_clause_id": "l_52_2014_qh13_art_8_clause_1",
  "chunk_text": "Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên.",
  "embed_text": "Chương II > Điều 8. Điều kiện kết hôn > Khoản 1: Nam từ đủ 20 tuổi trở_lên, nữ từ đủ 18 tuổi trở_lên.",
  "metadata": {
    "document_number": "52/2014/QH13",
    "document_title": "Luật Hôn nhân và gia đình",
    "article_number": "Điều 8",
    "clause_number": "Khoản 1",
    "validity_status": "Còn hiệu lực",
    "source_url": "[https://vbpl.vn/tw/Pages/vbpq-toanvan.aspx?ItemID=36870](https://vbpl.vn/tw/Pages/vbpq-toanvan.aspx?ItemID=36870)"
  }
}
```

### 8.2. Schema Kết quả Truy xuất (Retrieval Output Contract)
Hàm `DenseRetriever.retrieve(query, top_k, query_id)` trả về đúng cấu trúc chuẩn của Sprint 6:

```json
{
  "query_id": "Q_DEV_001",
  "retriever": "dense",
  "results": [
    {
      "chunk_id": "l_52_2014_qh13_art_8_clause_1_chunk_1",
      "document_id": "l_52_2014_qh13",
      "article_id": "l_52_2014_qh13_art_8",
      "clause_id": "l_52_2014_qh13_art_8_clause_1",
      "parent_clause_id": "l_52_2014_qh13_art_8_clause_1",
      "rank": 1,
      "score": 0.65203,
      "chunk_text": "Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên.",
      "metadata": {
        "document_number": "52/2014/QH13",
        "document_title": "Luật Hôn nhân và gia đình",
        "article_number": "Điều 8",
        "clause_number": "Khoản 1",
        "validity_status": "Còn hiệu lực",
        "source_url": "[https://vbpl.vn/tw/Pages/vbpq-toanvan.aspx?ItemID=36870](https://vbpl.vn/tw/Pages/vbpq-toanvan.aspx?ItemID=36870)"
      }
    }
  ]
}
```

---

## 9. Kết quả thực nghiệm (Smoke Test & Benchmark Latency)

Thực nghiệm đo đạc hiệu năng runtime được thực hiện trên tập fixture tiêu chuẩn gồm 321 child chunks (SHA-256: `f1d9af4423dd337072d467cf6fad31aa1436859eb77035ba6eb14d22796cce0b`; toàn bộ corpus tích hợp cuối Sprint 5 đạt 807 child chunks trên 9 văn bản).
- **Cấu hình truy vấn:** Query mẫu *"Điều kiện về độ tuổi kết hôn được quy định như thế nào?"*, `top_k = 5`, `batch_size = 32`, chuẩn hóa vector Cosine, Qdrant local embedded.
- **Môi trường phần cứng & phần mềm:** Windows 11 / Python 3.12 / PyTorch CPU, `sentence-transformers`, `qdrant-client`, `underthesea`.

| Model ID | Tiền xử lý / Max Tokens | Dim | Model Load (s) | Embed 321 Chunks (s) | Throughput (chunks/s) | Query Encode (ms) | Qdrant Search (ms) | Tổng Latency Query (ms) | Top-1 Hit (Cosine Score) | Dung lượng Vector (Bytes) |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- | ---: |
| `AITeamVN/Vietnamese_Embedding` | Nguyên văn / 2048 | 1024 | 41.399 | 456.061 | 0.70 | 272.36 | 34.28 | 306.64 | Điều 8, Khoản 1 (`0.60566`) | 1,314,816 |
| `bkai-foundation-models/vietnamese-bi-encoder` | Word-segment (`underthesea`) / 256 | 768 | 80.983 | 53.319 | **6.02** | **64.13** | **10.96** | **75.09** | Điều 8, Khoản 1 (`0.65203`) | **986,112** |
| `BAAI/bge-m3` | Nguyên văn / 8192 | 1024 | 214.229 | 249.314 | 1.29 | 361.74 | 45.47 | 407.22 | Điều 8, Khoản 1 (`0.73843`) | 1,314,816 |

### Nhận xét kết quả thực nghiệm:
1. **Độ chính xác trên truy vấn mẫu:** Cả 3 mô hình đều xếp hạng chính xác chunk quy định tuổi kết hôn (Điều 8, Khoản 1 Luật Hôn nhân và Gia đình) ở vị trí **Top-1** (`rank = 1`).
2. **Hiệu năng và Độ trễ (Latency):** Trên môi trường CPU, `bkai-foundation-models/vietnamese-bi-encoder` có tốc độ vượt trội gấp **8.6 lần** về tốc độ lập chỉ mục (`6.02 chunks/s` so với `0.70 chunks/s` của AITeamVN) và độ trễ truy vấn chỉ **75.09 ms/query** (nhanh hơn 4 lần so với AITeamVN và 5.4 lần so với BGE-M3).
3. **Đánh giá trên bộ Benchmark đầy đủ:** Khi Dev 1 bàn giao `data/benchmark/queries_dev.json` kèm `gold_context_ids` và Dev 2 chạy `evaluation/benchmark_runner.py`, nhóm sẽ đối chiếu **Strict Match Recall@5**, **Parent Match Recall@5** và **MRR@10** để chốt model chính thức trước khi đóng băng chạy Test set.

---

## 10. Hướng dẫn cấu hình, tạo Index và Kiểm thử (Dev 3 Runbook)

### 10.1. Cài đặt thư viện
```bash
python -m pip install -r embedding/requirements.txt
python -m pip install -r embedding/requirements-bkai.txt
```

### 10.2. Tạo và lưu Vector Index (`scripts/build_index.py`)
Chạy lệnh sau từ thư mục gốc của repository để bóc tách chunks từ `parser/parsed_jsons/` (hoặc `data/processed/`), tạo embedding và lưu Qdrant index vào `data/indexes/`:

```bash
# Chạy với model mặc định (bkai-foundation-models/vietnamese-bi-encoder)
python scripts/build_index.py --model bkai-foundation-models/vietnamese-bi-encoder

# Hoặc chạy với AITeamVN/Vietnamese_Embedding
python scripts/build_index.py --model AITeamVN/Vietnamese_Embedding

# Chạy chế độ Mock (không cần tải model nặng) để kiểm tra luồng tích hợp nhanh
python scripts/build_index.py --mock
```

Sau khi chạy xong, toàn bộ dữ liệu chỉ mục được lưu tại:
- `data/indexes/qdrant_storage/`: Dữ liệu Vector DB của Qdrant.
- `data/indexes/index_metadata.json`: Lưu tên model, số chiều vector, số lượng chunks, throughput và thời gian chạy.

### 10.3. Sử dụng `DenseRetriever` trong Code (Phục vụ Dev 2 & Dev 4)
```python
from embedding.vector_store import LegalVectorStore
from embedding.dense_retriever import DenseRetriever

store = LegalVectorStore(
    collection_name="vietnam_legal_chunks",
    dimension=768,
    storage_path="data/indexes/qdrant_storage",
)
retriever = DenseRetriever(
    vector_store=store,
    model_name="bkai-foundation-models/vietnamese-bi-encoder",
)

# 1. Lấy danh sách kết quả cho Hybrid Fusion (Dev 4)
candidates = retriever.search("Điều kiện kết hôn theo quy định pháp luật là gì?", top_k=50)

# 2. Lấy kết quả đóng gói theo Retrieval Schema (Dev 2 Evaluation)
output = retriever.retrieve(
    query="Điều kiện kết hôn theo quy định pháp luật là gì?",
    top_k=5,
    query_id="Q_DEV_001",
)
```

### 10.4. Chạy Unit Tests cho Dense Retriever
```bash
pytest test/test_dense_retriever.py -q
```