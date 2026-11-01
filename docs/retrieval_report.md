# Task 4 – Kiểm thử và đánh giá trên Dev set

> **Lưu ý về phiên bản:** Các kết quả trong báo cáo này là snapshot lịch sử, không phải kết quả trên trạng thái workspace hiện tại. Corpus hiện tại có 2.164 chunk và shared config chọn BGE-M3 1024 chiều; bảng dưới đây được tạo trên corpus 1.159/1.175 chunk và cấu hình BKAI 768 chiều. Nhãn proposal chưa được thẩm định. Xem [nguồn và trạng thái nhãn benchmark](benchmark_label_provenance.md) để biết SHA-256, số lượng và giới hạn sử dụng. Không dùng các metric lịch sử này làm kết quả G3 cho cấu hình hiện tại.

## Lần chạy được báo cáo ngày 2026-10-18

Ngày 2026-10-18, Task 4 được báo cáo trên 285 câu Dev với snapshot corpus 1.159 chunk và `gold_id_proposals_300.json` làm nhãn tạm (file này đã xóa ở 074eb94; proposal được gộp vào `candidate_context_ids` của `data/benchmark/ground_truth.json`). Đây là số liệu lịch sử; tệp kết quả tương ứng không có trong checkout hiện tại và không thể tái lập từ các index đang mở.

| Cấp nhãn | Phương pháp tốt nhất | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| Chunk | Hybrid RRF | 0.7407 | 0.4544 | 0.5145 | 0.0802 |
| Điều | Dense | 0.7846 | 0.5322 | 0.5843 | 0.0839 |

Theo snapshot báo cáo năm 2026-10-18, chunk-level chấm 268 câu và article-level chấm 267 câu; các nhãn phần lớn là proposal chưa xác minh. Trạng thái dataset hiện tại đã thay đổi: 300 nhãn đều draft, không có gold chunk nào được xác nhận. Kết quả trên chỉ là thử nghiệm theo proposal, không phải đánh giá pháp lý chính thức.

Provenance và tình trạng dataset hiện tại được ghi trong [benchmark label provenance](benchmark_label_provenance.md).

## Kết quả snapshot cũ (1.175 chunks)

Đã chạy BM25-only, Dense-only và Hybrid RRF trên cùng 285 câu Dev, cùng corpus đóng băng 1.175 chunk và cùng Top-10. Sau đó `chunks.jsonl` được xuất lại từ 11 file parser, thành corpus 1.159 chunk; các metric bên dưới **chưa được chạy lại trên corpus mới**. Tại thời điểm snapshot cũ, báo cáo ghi 9 câu có `gold_context_ids` và 258 câu dùng candidate chunk IDs; đây không còn là trạng thái nhãn hiện tại. Bảng là phép đo lịch sử trên nhãn pha trộn nên chỉ mang tính thăm dò.

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

Các metric trong cả hai bảng là trung bình macro trên **267 câu có nhãn**; **18 câu chưa có nhãn Điều/chunk bị loại khỏi phép tính** trong snapshot đó. Đây không phải thống kê của bộ nhãn hiện tại.

## Thiết lập thực nghiệm

- Dev: `data/benchmark/queries_dev.json` (285 câu, trường truy vấn `question`).
- Corpus dùng khi chạy benchmark: snapshot 1.175 chunk ID duy nhất (không còn là corpus hiện tại); corpus tại thời điểm báo cáo được ghi là 1.159 chunk ID duy nhất.
- BM25: Elasticsearch 9.5.3, index riêng `task4-legal-dev-1175`.
- Dense: `bkai-foundation-models/vietnamese-bi-encoder` (768 chiều), Qdrant local, collection riêng `task4-bkai-legal-1175`.
- Hybrid: Reciprocal Rank Fusion, candidate depth 50, RRF k=60, Top-10.
- Mỗi phương pháp tạo 2.850 kết quả (10 kết quả × 285 câu hỏi); JSON nằm trong `retrieval/results/`.
- Nhãn Điều lấy từ `gold_article_ids`; nhãn chunk dùng `gold_context_ids` đã xác nhận nếu có, còn lại tạm đối chiếu theo `candidate_context_ids` trong `data/benchmark/ground_truth.json`.

## Nhận xét

Dense dẫn đầu trên cả nhãn Điều và nhãn chunk hiện có; Hybrid cao hơn BM25 nhưng thấp hơn Dense trên ba metric chính. Dense là mô hình dẫn đầu trong lần chạy này, nhưng tổng thể vẫn cần xác nhận thêm vì 258 câu dùng candidate chunks chưa được review và 18 câu chưa có nhãn.

## Tệp kết quả

JSON đầu ra lịch sử không có trong checkout hiện tại. Các CSV dưới đây còn tồn tại nhưng chưa được xác nhận là từ corpus/config hiện tại:

- `retrieval/results/metrics.csv`
- `retrieval/results/article_metrics.csv`

Có thể tái tạo bảng metric từ ba tệp kết quả bằng:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_task4.py
```
