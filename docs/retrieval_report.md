# Task 4 – Kiểm thử và đánh giá trên Dev set

## Lần chạy mới: corpus hiện tại và proposal 300

Ngày 2026-10-18, Task 4 được chạy lại trên 285 câu Dev với `data/chunking_output/chunks.jsonl` (1.159 chunk) và nhãn candidate trong `data/benchmark/ground_truth.json` làm nhãn tạm. Kết quả được lưu riêng tại `retrieval/results/task4_proposal_300_current/`; lần chạy này không ghi đè các kết quả snapshot cũ bên dưới.

| Cấp nhãn | Phương pháp tốt nhất | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| Chunk | Hybrid RRF | 0.7407 | 0.4544 | 0.5145 | 0.0802 |
| Điều | Dense | 0.7846 | 0.5322 | 0.5843 | 0.0839 |

Chunk-level chấm 268 câu: 9 câu có gold đã xác nhận, 259 câu dùng proposal chưa xác minh, 17 câu không có nhãn chunk. Article-level chấm 267 câu; 18 câu không có nhãn Điều. 27 ID `version_*` bị loại khỏi chunk labels vì đó là metadata văn bản, không phải chunk có thể truy xuất. HN_271 dùng chunk Điều 8 hiện có làm candidate; parser Điều này hiện chưa đầy đủ. Kết quả do đó chỉ là thử nghiệm theo nhãn proposal, không phải đánh giá pháp lý chính thức.

Xem [báo cáo chi tiết và đầu ra lần chạy mới](../retrieval/results/task4_proposal_300_current/report.md).

## Kết quả snapshot cũ (1.175 chunks)

Đã chạy BM25-only, Dense-only và Hybrid RRF trên cùng 285 câu hỏi Dev, cùng corpus đóng băng 1.175 chunk và cùng Top-10. Sau đó `chunks.jsonl` được xuất lại từ 11 file parser, thành corpus 1.159 chunk; các metric bên dưới **chưa được chạy lại trên corpus mới**. Trạng thái ground truth hiện tại: **9 câu có `gold_context_ids` đã xác nhận**, 258 câu chỉ có candidate chunk IDs chưa xác minh, và 18 câu chưa có nhãn chunk. Có `gold_article_ids` cho 267 câu; 9 mục đã source-checked, 258 mục còn draft. Các bảng bao gồm nhãn xác nhận cùng candidate labels, nên metric tổng thể vẫn là thăm dò.

### Đánh giá theo nhãn Điều (`gold_article_ids`)

| Phương pháp | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: |
| BM25-only | 0.7453 | 0.4978 | 0.5454 | 0.0813 |
| Dense-only | **0.8689** | **0.7060** | **0.7299** | 0.0933 |
| Hybrid RRF | 0.8521 | 0.6311 | 0.6724 | 0.0921 |

Đây là đối chiếu ở cấp Điều: mỗi chunk truy xuất được ánh xạ sang `article_id` trong production index. Nếu nhiều chunk thuộc cùng một Điều, Điều đó chỉ được tính một lần ở thứ hạng xuất hiện đầu tiên.

### Đánh giá theo candidate chunk IDs (`candidate_context_ids`)

| Phương pháp | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: |
| BM25-only | 0.5470 | 0.4978 | 0.4408 | 0.1169 |
| Dense-only | **0.7549** | **0.7030** | **0.6500** | **0.1876** |
| Hybrid RRF | 0.6684 | 0.6311 | 0.5716 | 0.1539 |

Các metric trong cả hai bảng là trung bình macro trên **267 câu có nhãn**; **18 câu chưa có nhãn Điều/chunk bị loại khỏi phép tính**. Candidate chunk IDs đều tồn tại trong corpus. Trong 267 câu được chấm chunk-level, 9 dùng `gold_context_ids` đã xác nhận và 258 dùng candidate IDs chưa xác minh.

## Thiết lập thực nghiệm

- Dev: `data/benchmark/queries_dev.json` (285 câu, trường truy vấn `question`).
- Corpus dùng khi chạy benchmark: snapshot 1.175 chunk ID duy nhất (không còn là corpus hiện tại); corpus hiện tại có 1.159 chunk ID duy nhất.
- BM25: Elasticsearch 9.5.3, index riêng `task4-legal-dev-1175`.
- Dense: `bkai-foundation-models/vietnamese-bi-encoder` (768 chiều), Qdrant local, collection riêng `task4-bkai-legal-1175`.\n- Hybrid: Reciprocal Rank Fusion, candidate depth 50, RRF k=60, Top-10.
- Mỗi phương pháp tạo 2.850 kết quả (10 kết quả × 285 câu hỏi); JSON nằm trong `retrieval/results/`.
- Nhãn Điều lấy từ `gold_article_ids`; nhãn chunk dùng `gold_context_ids` đã xác nhận nếu có, còn lại tạm đối chiếu theo `candidate_context_ids` trong `data/benchmark/ground_truth.json`.

## Nhận xét

Dense dẫn đầu trên cả nhãn Điều và nhãn chunk hiện có; Hybrid cao hơn BM25 nhưng thấp hơn Dense trên ba metric chính. Dense là mô hình dẫn đầu trong lần chạy này, nhưng tổng thể vẫn cần xác nhận thêm vì 258 câu dùng candidate chunks chưa được review và 18 câu chưa có nhãn.

## Tệp kết quả

- `retrieval/results/dev_bm25.json`
- `retrieval/results/dev_dense.json`
- `retrieval/results/dev_hybrid.json`
- `retrieval/results/metrics.csv`
- `retrieval/results/article_metrics.csv`

Có thể tái tạo bảng metric từ ba tệp kết quả bằng:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_task4.py
```
