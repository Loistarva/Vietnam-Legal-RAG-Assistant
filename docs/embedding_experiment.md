# Embedding Experiment -- Vietnam-Legal-RAG-Assistant

## 1. Bối cảnh bài toán

**Vietnam-Legal-RAG-Assistant** là hệ thống RAG hỗ trợ hỏi đáp dựa trên
**Luật Hôn nhân và Gia đình Việt Nam**.

Mục tiêu của hệ thống không chỉ là tạo ra một câu trả lời có vẻ hợp lý,
mà phải **tìm đúng các Điều/Khoản pháp luật liên quan** để đưa vào
context cho LLM.

Pipeline tổng thể:

``` text
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

Trong pipeline này, module Embedding có nhiệm vụ:

-   chuyển mỗi chunk pháp luật thành vector;
-   tạo vector cho câu hỏi của người dùng;
-   lưu vector và metadata vào Vector DB;
-   hỗ trợ tìm các chunk gần nhất theo ngữ nghĩa;
-   cung cấp Dense Retrieval cho các bước Retrieval tiếp theo.


------------------------------------------------------------------------

# 2. Mục tiêu của thử nghiệm

Mục tiêu của thử nghiệm là lựa chọn một embedding model phù hợp với bài
toán **Legal RAG tiếng Việt**, trong đó ưu tiên:

1.  **Độ chính xác retrieval**: tìm đúng Điều/Khoản liên quan.
2.  Khả năng hiểu tiếng Việt và thuật ngữ pháp lý.
3.  Khả năng xử lý các chunk của Luật Hôn nhân và Gia đình.
4.  Tốc độ tạo embedding và truy vấn.
5.  Kích thước vector và chi phí lưu trữ.
6.  Khả năng triển khai trên môi trường của nhóm.

Đặc biệt, với RAG pháp luật:

> **Độ chính xác của retrieval được ưu tiên hơn tốc độ embedding thuần
> túy.**

Lý do là nếu retrieval không đưa đúng Điều/Khoản vào context thì LLM dù
mạnh vẫn có thể trả lời sai hoặc thiếu căn cứ pháp lý.

------------------------------------------------------------------------

# 3. Đặc trưng của dữ liệu cần Embedding

Dữ liệu của hệ thống là **Luật Hôn nhân và Gia đình**, có cấu trúc:

``` text
Chương
  ↓
Điều
  ↓
Khoản
  ↓
Điểm
```

Nội dung có nhiều thuật ngữ pháp lý và các quy định có ngữ nghĩa gần
nhau.

Ví dụ câu hỏi:

> "Bao nhiêu tuổi thì được kết hôn?"

Có thể cần tìm đến chunk chứa quy định:

> "Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên..."

Hoặc:

> "Sau khi ly hôn thì ai được nuôi con?"

có thể liên quan đến các quy định về việc trông nom, chăm sóc, nuôi
dưỡng và giáo dục con sau khi ly hôn.

Do đó embedding model cần có khả năng biểu diễn **ý nghĩa của câu hỏi**,
không chỉ dựa trên việc hai câu có các từ giống nhau.

------------------------------------------------------------------------

# 4. Tiêu chí đánh giá Embedding Model

## 4.1. Retrieval accuracy

Đây là tiêu chí quan trọng nhất.

Model cần đưa chunk pháp luật liên quan vào Top-K.

Các chỉ số có thể sử dụng:

-   Recall@1
-   Recall@5
-   Recall@10
-   MRR@10

Trong kế hoạch của nhóm, mục tiêu Retrieval sau này là:

> **Recall@5 ≥ 85%**

Do đó kết quả Recall@5 trên tập đánh giá pháp luật sẽ là một tiêu chí
quan trọng khi lựa chọn model.

------------------------------------------------------------------------

## 4.2. Khả năng hiểu tiếng Việt

Model phải xử lý tốt:

-   câu hỏi tiếng Việt;
-   cách diễn đạt tự nhiên;
-   từ đồng nghĩa;
-   cách hỏi không trùng nguyên văn với luật.

Ví dụ:

``` text
"Bao nhiêu tuổi thì được kết hôn?"
```

và:

``` text
"Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên..."
```

cần được nhận diện là có quan hệ ngữ nghĩa.

------------------------------------------------------------------------

## 4.3. Khả năng xử lý thuật ngữ pháp lý

Cần đánh giá với các khái niệm như:

-   điều kiện kết hôn;
-   quyền và nghĩa vụ của vợ chồng;
-   tài sản chung của vợ chồng;
-   tài sản riêng;
-   cấp dưỡng;
-   ly hôn;
-   quyền nuôi con;
-   quan hệ giữa cha mẹ và con;
-   hôn nhân có yếu tố nước ngoài.

------------------------------------------------------------------------

## 4.4. Khả năng xử lý chunk dài

Một số Điều/Khoản có nội dung dài.

Model có giới hạn input quá ngắn có thể làm mất một phần nội dung khi
embedding.

Do đó cần xem xét:

-   maximum sequence length;
-   chiến lược chunking;
-   khả năng giữ context của Chương/Điều/Khoản.

------------------------------------------------------------------------

## 4.5. Tốc độ

Ghi nhận:

-   embedding throughput (sent/s);
-   thời gian tạo embedding cho toàn bộ chunk;
-   thời gian tạo embedding cho một query;
-   query latency.

Tốc độ quan trọng nhưng **không được đánh đổi quá nhiều độ chính xác
retrieval để lấy tốc độ**.

------------------------------------------------------------------------

## 4.6. Dimension

Dimension ảnh hưởng đến:

-   dung lượng Vector DB;
-   RAM;
-   thời gian tính toán;
-   chi phí lưu trữ.

Dimension thấp hơn không đồng nghĩa với chất lượng thấp hơn hoặc cao
hơn; cần đánh giá cùng với chất lượng retrieval.

------------------------------------------------------------------------

> Để đảm bảo so sánh công bằng, toàn bộ tài liệu dùng cùng một bộ metric
> chính: `Recall@5`, `MRR@10`, `Recall@10`, `Query latency`,
> `Embedding throughput`, `Vector dimension`, và `Context length`.
> Tên model cũng được chuẩn hóa theo định dạng GitHub/Hub ID nếu có sẵn.

------------------------------------------------------------------------

# 5. Các model được nghiên cứu

Dựa trên benchmark tiếng Việt và các model embedding đã khảo sát, các
ứng viên gồm:

1.  `BAAI/bge-vi-base`
2.  `sBERT-Vi`
3.  `PhoBERT`
4.  `ViEmbedding`
5.  `AITeamVN/Vietnamese_Embedding`
6.  `BAAI/bge-m3`
7.  `intfloat/multilingual-e5-base`
8.  `hivetechVN/vietnamese-sbert-base-law-768-v2`

Không nhất thiết phải đưa cả 8 model vào thực nghiệm. Phần nghiên cứu
dùng để lọc ra các ứng viên phù hợp nhất.

------------------------------------------------------------------------

# 6. Phân tích từng model

## 6.1. BAAI/bge-vi-base

### Kết quả benchmark tham khảo

Theo benchmark Việt 2025 được nhóm cung cấp:

  Chỉ số                   Kết quả
  ------------------- ------------
  Accuracy (STS-Vi)       **0.88**
  MRR@10                  **0.84**
  Tốc độ                950 sent/s
  Dimension                    768

Đây là model có kết quả cao nhất trong bảng benchmark được cung cấp.

### Ưu điểm

-   Kết quả benchmark tiếng Việt rất tốt.
-   MRR@10 cao, phù hợp với mục tiêu retrieval.
-   Dimension 768 tương đối hợp lý cho Vector DB.
-   Có sự cân bằng tốt giữa chất lượng và kích thước vector.
-   Là ứng viên rất mạnh cho tiếng Việt.

### Nhược điểm

-   Benchmark trên STS-Vi không đồng nghĩa với benchmark trực tiếp trên
    Luật Hôn nhân và Gia đình.
-   Cần kiểm tra thực tế khả năng xử lý thuật ngữ pháp lý.
-   Cần kiểm tra khả năng xử lý chunk dài theo chunking strategy của
    nhóm.

### Đánh giá cho dự án

**Rất phù hợp.**

Đây là một trong những model cần ưu tiên thử nghiệm.

------------------------------------------------------------------------

# 7. sBERT-Vi

### Benchmark tham khảo

  Chỉ số                     Kết quả
  ------------------- --------------
  Accuracy (STS-Vi)             0.86
  MRR@10                        0.81
  Tốc độ                1,100 sent/s
  Dimension                      768

### Ưu điểm

-   Chất lượng benchmark tiếng Việt cao.
-   MRR@10 tốt.
-   Nhanh hơn BAAI/bge-vi-base theo benchmark được cung cấp.
-   Dimension 768.
-   Có thể là lựa chọn cân bằng giữa accuracy và tốc độ.

### Nhược điểm

-   Kết quả thấp hơn BAAI/bge-vi-base trong benchmark hiện có.
-   Chưa có bằng chứng trực tiếp đủ mạnh để khẳng định vượt các model
    được fine-tune cho retrieval/legal.
-   Cần thử trên dữ liệu Luật Hôn nhân và Gia đình.

### Đánh giá cho dự án

**Phù hợp, đặc biệt làm model đối chứng.**

------------------------------------------------------------------------

# 8. PhoBERT

### Benchmark tham khảo

  Chỉ số                     Kết quả
  ------------------- --------------
  Accuracy (STS-Vi)             0.82
  MRR@10                        0.77
  Tốc độ                1,200 sent/s
  Dimension                      768

### Ưu điểm

-   Mạnh về biểu diễn ngôn ngữ tiếng Việt.
-   Có tốc độ tốt trong benchmark.
-   Dimension 768.
-   Là baseline quan trọng khi nghiên cứu tiếng Việt.

### Nhược điểm

-   PhoBERT là pretrained language model, không phải bản thân checkpoint
    gốc được thiết kế chuyên biệt cho sentence retrieval.
-   Kết quả benchmark thấp hơn BAAI/bge-vi-base và sBERT-Vi.
-   Cần xem chính xác cách benchmark tạo sentence embedding từ PhoBERT.

### Đánh giá cho dự án

**Phù hợp làm baseline, nhưng không phải ứng viên ưu tiên cho Dense
Retrieval.**

------------------------------------------------------------------------

# 9. ViEmbedding

### Benchmark tham khảo

  Chỉ số                         Kết quả
  ------------------- ------------------
  Accuracy (STS-Vi)                 0.74
  MRR@10                            0.69
  Tốc độ                **2,200 sent/s**
  Dimension                      **300**

### Ưu điểm

-   Nhanh nhất trong benchmark được cung cấp.
-   Dimension chỉ 300.
-   Tiết kiệm dung lượng Vector DB.
-   Có thể phù hợp nếu hệ thống ưu tiên tài nguyên thấp.

### Nhược điểm

-   Accuracy và MRR thấp nhất trong bảng benchmark.
-   Với Legal RAG, mất các chunk liên quan khỏi Top-K có thể ảnh hưởng
    trực tiếp đến độ chính xác câu trả lời.
-   Lợi thế tốc độ chưa đủ để bù lại chênh lệch về retrieval quality nếu
    benchmark thực tế cũng cho kết quả tương tự.

### Đánh giá cho dự án

**Không phải lựa chọn ưu tiên nếu mục tiêu chính là độ chính xác.**

Có thể giữ làm model đối chứng về hiệu năng.

------------------------------------------------------------------------

# 10. AITeamVN/Vietnamese_Embedding

## Thông tin

-   Model được fine-tune từ BGE-M3 cho tiếng Việt.
-   Dimension: **1024**.
-   Maximum sequence length: khoảng **2048 tokens**.
-   Được huấn luyện trên khoảng 300.000 triplets tiếng Việt cho
    retrieval.

## Benchmark đáng chú ý

Model card có benchmark trên **Legal Zalo 2021**, một benchmark có tính
chất pháp lý/retrieval.

Kết quả được công bố:

-   MRR@10: **0.8181**
-   Accuracy@5: **0.9305**
-   Accuracy@10: **0.9568**

Đây là điểm rất quan trọng đối với project vì dữ liệu của nhóm cũng là
dữ liệu pháp luật tiếng Việt.

### Ưu điểm

-   Tập trung vào tiếng Việt.
-   Fine-tune trực tiếp cho retrieval.
-   Có kết quả benchmark trên dữ liệu legal tiếng Việt.
-   Có khả năng là ứng viên rất mạnh cho Legal RAG.
-   Kế thừa nền tảng BGE-M3.

### Nhược điểm

-   Dimension 1024 lớn hơn BAAI/bge-vi-base/sBERT-Vi.
-   Tốn dung lượng Vector DB hơn.
-   Maximum sequence length ngắn hơn BGE-M3.
-   Không được fine-tune riêng cho Luật Hôn nhân và Gia đình.
-   Cần thực nghiệm trên dữ liệu thật của project.

### Đánh giá cho dự án

**Rất phù hợp và là ứng viên ưu tiên cao.**

Đây là model có bằng chứng thực nghiệm trực tiếp đáng chú ý đối với
**legal retrieval tiếng Việt**.

------------------------------------------------------------------------

# 11. BAAI/bge-m3

## Thông tin

-   Multilingual embedding model.
-   Dimension: **1024**.
-   Maximum sequence length: khoảng **8192 tokens**.
-   Được thiết kế cho các bài toán retrieval.

### Ưu điểm

-   Hỗ trợ đa ngôn ngữ.
-   Context rất dài.
-   Phù hợp với các văn bản pháp luật có nội dung dài.
-   Là một baseline mạnh cho retrieval.
-   Có hệ sinh thái và tài liệu tương đối tốt.

### Nhược điểm

-   Lớn hơn một số model tiếng Việt.
-   Dimension 1024.
-   Không được fine-tune chuyên biệt cho tiếng Việt legal trong
    checkpoint gốc.
-   Tốc độ có thể thấp hơn các model nhỏ hơn.

### Đánh giá cho dự án

**Rất phù hợp làm baseline retrieval mạnh và model đối chứng.**

Đặc biệt hữu ích để kiểm tra:

> Một model multilingual + context dài có vượt được model tiếng Việt
> chuyên biệt trên Luật Hôn nhân và Gia đình hay không?

------------------------------------------------------------------------

# 12. intfloat/multilingual-e5-base

### Thông tin

-   Multilingual embedding model.
-   Dimension: **768**.
-   Maximum input length khoảng **512 tokens**.

### Ưu điểm

-   Hỗ trợ nhiều ngôn ngữ.
-   Dimension 768.
-   Có thể triển khai tương đối thuận tiện.
-   Có thể dùng làm baseline multilingual.

### Nhược điểm

-   Context 512 tokens có thể là hạn chế với chunk pháp luật dài.
-   Không chuyên tiếng Việt.
-   Không chuyên legal.
-   Không có lợi thế rõ ràng hơn các ứng viên tiếng Việt trong bài toán
    này.

### Đánh giá cho dự án

**Có thể nghiên cứu nhưng không phải ứng viên ưu tiên.**

------------------------------------------------------------------------

# 13. Vietnamese Legal SBERT

Model:

`hivetechVN/vietnamese-sbert-base-law-768-v2`

### Ưu điểm

-   Có định hướng trực tiếp cho **legal domain**.
-   Đây là đặc điểm rất phù hợp với bài toán của nhóm.
-   Dimension 768, thuận tiện cho Vector DB.
-   Có tiềm năng xử lý tốt thuật ngữ pháp lý tiếng Việt.

### Nhược điểm

-   Cần kiểm tra kỹ benchmark, dataset fine-tuning và license của đúng
    checkpoint.
-   Chưa có đủ kết quả benchmark cùng điều kiện với các model ở bảng
    benchmark Việt 2025 để xếp hạng công bằng.
-   Không nên kết luận model tốt nhất chỉ dựa vào tên "law".

### Đánh giá cho dự án

**Ứng viên nghiên cứu bổ sung rất đáng chú ý**, đặc biệt vì domain của
model gần với domain của project.

Tuy nhiên cần thực nghiệm trực tiếp trước khi xếp trên các model có
benchmark rõ ràng hơn.

------------------------------------------------------------------------

# 14. Bảng so sánh tổng hợp

| Model | Tiếng Việt | Legal retrieval | Retrieval quality | Tốc độ | Dimension | Context length | Đánh giá sơ bộ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BAAI/bge-vi-base` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 768 | Cần kiểm tra | Ứng viên chính |
| `AITeamVN/Vietnamese_Embedding` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 1024 | 2048 | Ứng viên chính |
| `BAAI/bge-m3` | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | 1024 | 8192 | Baseline mạnh |
| `sBERT-Vi` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 768 | Cần kiểm tra | Đối chứng |
| `hivetechVN/vietnamese-sbert-base-law-768-v2` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | TBD | ⭐⭐⭐⭐ | 768 | Cần kiểm tra | Ứng viên bổ sung |
| `PhoBERT` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 768 | Cần kiểm tra | Baseline |
| `ViEmbedding` | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 300 | Cần kiểm tra | Efficiency baseline |
| `intfloat/multilingual-e5-base` | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 768 | 512 | Baseline multilingual |

> Các đánh giá bằng sao ở trên là **đánh giá định hướng trước thực
> nghiệm**, không phải kết quả benchmark mới. Model cuối cùng phải được
> đánh giá trên cùng một tập dữ liệu của project, với cùng bộ metric và
> cùng chiến lược chunking.

------------------------------------------------------------------------

# 15. Preliminary Ranking trước khi thử nghiệm

Dựa trên mục tiêu của project:

> **Legal RAG → ưu tiên retrieval accuracy, sau đó cân nhắc tốc độ và
> chi phí.**

Ranking sơ bộ:

## 🥇 1. AITeamVN/Vietnamese_Embedding

Lý do:

-   tiếng Việt;
-   được fine-tune cho retrieval;
-   có benchmark Legal Zalo 2021;
-   phù hợp trực tiếp với bài toán legal retrieval.

Điểm cần kiểm tra:

-   tốc độ;
-   chi phí dimension 1024;
-   chất lượng trên Luật Hôn nhân và Gia đình cụ thể.

------------------------------------------------------------------------

## 🥈 2. BAAI/bge-vi-base

Lý do:

-   dẫn đầu benchmark Việt 2025 được nhóm cung cấp;
-   Accuracy = 0.88;
-   MRR@10 = 0.84;
-   dimension 768;
-   cân bằng tốt giữa chất lượng và hiệu năng.

Điểm cần kiểm tra:

-   khả năng retrieval trên domain pháp luật;
-   xử lý chunk dài;
-   so sánh trực tiếp với Vietnamese_Embedding.

------------------------------------------------------------------------

## 🥉 3. BAAI/bge-m3

Lý do:

-   retrieval-oriented;
-   context dài;
-   phù hợp với văn bản pháp luật;
-   baseline mạnh.

Điểm hạn chế:

-   lớn hơn;
-   dimension 1024;
-   không chuyên legal Việt Nam.

------------------------------------------------------------------------

## 4. sBERT-Vi

Có benchmark tiếng Việt tốt và tốc độ khá tốt.

Tuy nhiên, bằng chứng trực tiếp cho legal retrieval hiện chưa mạnh bằng
Vietnamese_Embedding.

------------------------------------------------------------------------

## 5. hivetechVN/vietnamese-sbert-base-law-768-v2

Rất đáng chú ý vì được định hướng cho legal domain.

Tuy nhiên cần benchmark trực tiếp trước khi có thể xếp cao hơn các model
có số liệu rõ ràng.

------------------------------------------------------------------------

## 6. PhoBERT

Là baseline tiếng Việt tốt nhưng không phải lựa chọn retrieval chuyên
biệt nhất.

------------------------------------------------------------------------

## 7. ViEmbedding

Rất nhanh và vector nhỏ, nhưng chất lượng benchmark thấp hơn đáng kể.

Chỉ nên ưu tiên nếu hệ thống bị giới hạn mạnh về tài nguyên.

------------------------------------------------------------------------

## 8. intfloat/multilingual-e5-base

Có ưu điểm multilingual và dimension 768, nhưng không có lợi thế rõ ràng
đối với dữ liệu pháp luật tiếng Việt của project.

------------------------------------------------------------------------

# 16. Ba model đề xuất đưa vào thực nghiệm

đề xuất chọn:

``` text
1. AITeamVN/Vietnamese_Embedding
2. BAAI/bge-vi-base
3. BAAI/bge-m3
```

Lý do:

  Model                                     Vai trò
  ----------------------------------------- ---------------------------------------
  **AITeamVN/Vietnamese_Embedding**         Ứng viên accuracy/legal-oriented
  **BAAI/bge-vi-base**                     Ứng viên accuracy + efficiency
  **BAAI/bge-m3**                          Baseline retrieval mạnh + context dài

Ba model này tạo ra một thử nghiệm có ý nghĩa:

``` text
Vietnamese legal-oriented
          VS
Vietnamese high-performing
          VS
Multilingual retrieval-oriented
```

------------------------------------------------------------------------

# 17. Dependency với Chunking

Embedding phụ thuộc trực tiếp vào output của Chunking.

``` text
Parser
   ↓
Chunking
   ↓
chunking_examples.json
   ↓
Embedding
   ↓
Vector DB
```

Input tối thiểu:

``` json
{
  "chunk_id": "LHN-GD_D8_K1",
  "text": "...",
  "metadata": {
    "document_id": "Luat_Hon_Nhan_Gia_Dinh",
    "chapter": "...",
    "article": "...",
    "clause": "..."
  }
}
```


------------------------------------------------------------------------

# 18. Thiết kế thực nghiệm

## 18.1. Dataset

Cả ba model sử dụng:

-   cùng chunk;
-   cùng query;
-   cùng Vector DB strategy;
-   cùng Top-K;
-   cùng hardware nếu có thể.

``` text
Model A ─┐
Model B ─┼→ cùng dataset → cùng query set → so sánh
Model C ─┘
```

## 18.2. Query set

Query nên phản ánh các dạng câu hỏi thực tế về Luật Hôn nhân và Gia
đình:

-   điều kiện kết hôn;
-   độ tuổi kết hôn;
-   trường hợp cấm kết hôn;
-   quyền/nghĩa vụ của vợ chồng;
-   tài sản chung/riêng;
-   cấp dưỡng;
-   ly hôn;
-   quyền nuôi con;
-   quan hệ cha mẹ và con;
-   hôn nhân có yếu tố nước ngoài.

## 18.3. Chỉ số

Ưu tiên:

``` text
Recall@5
MRR@10
```

Ngoài ra:

``` text
Recall@1
Recall@10
Query latency
Embedding throughput
Vector dimension
Memory/storage
```

------------------------------------------------------------------------

# 19. Kết quả thực nghiệm

| Model | Recall@5 | MRR@10 | Query latency | Embedding throughput | Dimension |
| --- | --- | --- | --- | --- | --- |
| `AITeamVN/Vietnamese_Embedding` | TBD | TBD | TBD | TBD | 1024 |
| `BAAI/bge-vi-base` | TBD | TBD | TBD | TBD | 768 |
| `BAAI/bge-m3` | TBD | TBD | TBD | TBD | 1024 |

> Bảng trên là template lưu kết quả thực nghiệm. Các giá trị thực tế sẽ
> được điền sau khi chạy cùng một tập query và cùng một chiến lược chunking.

------------------------------------------------------------------------

# 20. Quy tắc lựa chọn model cuối cùng

Model cuối cùng được chọn theo thứ tự ưu tiên:

### Ưu tiên 1 -- Retrieval quality

Nếu một model có Recall@5/MRR@10 tốt hơn rõ rệt trên dữ liệu Luật Hôn
nhân và Gia đình, ưu tiên model đó.

### Ưu tiên 2 -- Latency

Nếu chất lượng hai model tương đương, ưu tiên model có query latency
thấp hơn.

### Ưu tiên 3 -- Resource

Nếu chất lượng và tốc độ tương đương, ưu tiên:

-   dimension nhỏ hơn;
-   model nhẹ hơn;
-   ít RAM/VRAM hơn.

### Quy tắc thực tế

Ví dụ:

``` text
Model A: Recall@5 = 93%, latency = 80 ms
Model B: Recall@5 = 87%, latency = 40 ms
```

→ Chọn **A** vì RAG pháp luật ưu tiên độ chính xác.

Ngược lại:

``` text
Model A: Recall@5 = 92%, latency = 80 ms
Model B: Recall@5 = 91.5%, latency = 35 ms
```

→ Có thể cân nhắc **B** vì chất lượng gần tương đương nhưng tốc độ tốt
hơn.

------------------------------------------------------------------------

# 21. Kết luận

Tuy nhiên, ranking sơ bộ cho mục tiêu **Legal RAG -- ưu tiên độ chính
xác nhưng vẫn xét tốc độ** là:

| Ranking | Model | Lý do chính |
| --- | --- | --- |
| 🥇 1 | `AITeamVN/Vietnamese_Embedding` | Có định hướng Vietnamese retrieval và bằng chứng benchmark legal |
| 🥈 2 | `BAAI/bge-vi-base` | Benchmark Việt mạnh, MRR cao, dimension 768 |
| 🥉 3 | `BAAI/bge-m3` | Retrieval mạnh, context dài, baseline tốt |
| 4 | `sBERT-Vi` | Chất lượng Việt tốt và khá nhanh |
| 5 | `hivetechVN/vietnamese-sbert-base-law-768-v2` | Rất sát domain nhưng cần benchmark trực tiếp |
| 6 | `PhoBERT` | Baseline tiếng Việt tốt nhưng không chuyên retrieval |
| 7 | `ViEmbedding` | Rất nhanh nhưng chất lượng thấp hơn |
| 8 | `intfloat/multilingual-e5-base` | Multilingual tốt nhưng ít lợi thế cho bài toán này |
