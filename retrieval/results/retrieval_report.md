# Báo cáo Retrieval — Tuần 7

**Ngày:** 26/10/2026  
**Nhãn đánh giá:** `gold_id_proposals_300.json` trên Dev và `gold_id_proposals_300_test_revised.json` trên Test. Nhãn là proposal, chưa được xác minh pháp lý đầy đủ; không dùng `ground_truth.json`.

## 1. Tuning trên Dev

- Dev có 285 câu; 267 câu có nhãn chunk đối chiếu được. Loại 18 câu chỉ có ID `version_*` không xuất hiện trong corpus chunk; không tính chúng là truy xuất hụt.
- Metric là macro Recall@5 và MRR@5 theo đúng 5 thứ hạng. Top-50 BM25/Dense được hợp nhất bằng RRF k=60; trọng số được quét 21 mức từ 0 đến 1, bước 0,05.
- So sánh chunking chọn E: parent 1.500 ký tự; child tối đa 256 token theo cấu hình, 350 đơn vị chunker, tối thiểu 30 từ; fallback overlap 40 từ (giữ cố định ở mọi phương án); 1.923 chunks.

| Phương pháp trên E | Recall@5 | MRR@5 | Latency truy xuất trung bình |
| --- | ---: | ---: | ---: |
| BM25-only | 0,7503 | 0,6043 | 28,5 ms mean (median 16,6; p95 62,4) |
| Dense-only | 0,7647 | 0,6218 | 409,6 ms mean (median 141,0; p95 239,7) |
| Hybrid RRF đã tune (BM25/Dense 0,35/0,65) | **0,8246** | **0,6521** | **172,2 ms mean (median 155,3; p95 264,0)** |

Latency từng nhánh được đo riêng trên đủ 285 query Dev và đã ghi ở `E/dev_latency.json`. Mean Dense gồm cold start 73,7 giây của encoder ở query đầu; mean 409,6 ms, median 141,0 ms, p95 239,7 ms, còn mean sau query đầu là 151,6 ms. BM25 có mean 28,5 ms, median 16,6 ms, p95 62,4 ms. Hybrid mean 172,2 ms, median 155,3 ms, p95 264,0 ms. Hybrid chạy BM25 và Dense song song rồi áp dụng RRF; số đo không gồm Cross-Encoder. Ranking metrics Hybrid được tính lại offline từ cùng Top-50 BM25/Dense theo trọng số 0,35/0,65.

### So sánh chunking và fusion trên Dev

| Phương án | Parent chars | Child token / units | Chunks | BM25/Dense | Recall@5 | MRR@5 | Latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 1.500 | 256 / 200 | 2.011 | 0,45 / 0,55 | 0,8196 | 0,6459 | 310,6 |
| B | 800 | 128 / 100 | 2.655 | 0,45 / 0,55 | 0,7959 | 0,6069 | 381,2 |
| C | 2.500 | 512 / 350 | 1.906 | 0,30 / 0,70 | 0,8227 | 0,6463 | 284,8 |
| **E — chọn trên Dev** | **1.500** | **256 / 350** | **1.923** | **0,35 / 0,65** | **0,8246** | **0,6521** | **172,2** |

Latency A/B/C lấy từ lượt truy xuất trước ở 0,65/0,35; latency E được đo riêng ở đúng trọng số đã chọn 0,35/0,65. Metric ranking từng phương án được tính lại trên cùng danh sách BM25/Dense. Tokenizer BGE có giới hạn 256 token; E có 74/1.923 chunks (3,85%) dài hơn giới hạn và bị cắt khi embedding. Đây là điểm cần xử lý ở vòng Dev kế tiếp.

## 2. Lượt Test đầu — Config A

Lượt Test đã chạy trước khi hoàn tất tuning Dev, trên Config A và RRF 1:1. Cross-Encoder là model thật `BAAI/bge-reranker-v2-m3`, chạy CPU trên cùng 50 ứng viên Hybrid; metric tính Top-5.

| Phương pháp trên lượt Test Config A | Recall@5 (15 câu) | MRR@5 | Latency thực đo |
| --- | ---: | ---: | ---: |
| BM25-only* | 0,3111 | 0,1433 | 5.964,9 ms mean; median 172,3; p95 86.565,9 |
| Hybrid RRF 1:1 | 0,2889 | 0,2500 | 5.964,9 ms mean; median 172,3; p95 86.565,9 |
| Hybrid + Cross-Encoder thật | 0,5778 | 0,4556 | 56.240,5 ms mean; median 52.164,6; p95 95.667,3 |

*BM25-only và Hybrid được ghi từ cùng một lần `HybridRetriever.retrieve()` chạy hai nhánh song song; do đó latency Test 5.964,9 ms là latency truy xuất kết hợp, không phải BM25 riêng. Cold start làm tăng mean/p95. Cross-Encoder latency đã gồm retrieval và rerank. Không có lỗi ở 15 query. Lượt này chưa áp dụng temporal pre-filter.

Lượt đầu dùng Config A và RRF 1:1 trước khi hoàn tất tuning Dev. Kết quả này được giữ lại làm lịch sử; không đại diện cấu hình E.

## 3. Đánh giá lại Test — Config E đã khóa

Sau khi chọn E trên Dev, đã chạy một lượt trên cùng 15 query Test để đo cấu hình cuối. Đây là Test lặp lại sau khi kết quả Config A đã được xem, nên không được xem là một phép đo độc lập mới. Không tham số nào được tune theo kết quả này.

| Phương pháp trên lượt Test Config E | Recall@5 (15 câu) | MRR@5 | Latency thực đo (mean / median / p95) |
| --- | ---: | ---: | ---: |
| BM25-only | 0,3111 | 0,1433 | 511,4 / 392,5 / 1.006,9 ms |
| Hybrid RRF 0,35/0,65 | 0,4222 | 0,3300 | 1.677,7 / 891,3 / 8.497,3 ms |
| Hybrid + Cross-Encoder thật | **0,6444** | **0,5222** | 52.904,0 / 48.686,8 / 83.839,5 ms |

Lượt này dùng chunking E (1.923 chunks), index Elasticsearch `legal-child-chunks-dev-cfge`, Qdrant `vietnam_legal_dev_cfge`, embedding BKAI Vietnamese Bi-Encoder, RRF Top-50/k=60/trọng số 0,35/0,65, Cross-Encoder thật `BAAI/bge-reranker-v2-m3` rerank Top-10. Metric tính trên Top-5. Hai nhãn chunk bị đổi ranh giới ở E được ánh xạ bằng text span trong cùng `clause_id`; proposal gốc không sửa.

Recall@5 64,44% chưa đạt mục tiêu 85%. Nhãn vẫn là proposal. Retriever hiện chưa truyền `as_of_date` theo từng query; bộ lọc trạng thái hết hiệu lực dùng trạng thái hiện tại, vì vậy chưa đánh giá đủ temporal pre-filter trong sơ đồ. Muốn có phép đo độc lập sau khi tiếp tục phát triển cần một Test set mới chưa xem.

## 4. Cấu hình Retrieval được chọn trên Dev

- Chunking E: 1.500 ký tự parent; 256 token / 350 units child; tối thiểu 30 từ; fallback overlap 40 từ. Overlap chỉ áp dụng cho nhánh fallback window và không được tune riêng.
- BM25 Elasticsearch: `legal-child-chunks-dev-cfge`, trường `content_segmented`.
- Dense Qdrant: `vietnam_legal_dev_cfge`, `bkai-foundation-models/vietnamese-bi-encoder`, storage `retrieval/results/dev_tuning/chunking_variants/E/vector_index/qdrant_storage`.
- Fusion: weighted RRF, `k=60`, BM25 0,35 / Dense 0,65; 50 ứng viên.
- Cross-Encoder mặc định: `BAAI/bge-reranker-v2-m3`, 50 đầu vào, Top-10 đầu ra; Parent-Context Resolver dùng `E/parents.json`.
- Benchmark tuần 7 đo Top-5; pipeline tích hợp trả Top-10. Cấu hình nằm trong `retrieval/config.yaml` và `reranking/config.yaml`. Config E có metric Test riêng ở bảng trên; đó là lượt đánh giá lại trên Test đã dùng trước đó.

## Tệp bàn giao

- Báo cáo chunking / metric Dev chi tiết: [`dev_chunking_evaluation.md`](dev_tuning/chunking_variants/dev_chunking_evaluation.md).
- JSON theo query và cấu hình: [`dev_chunking_evaluation.json`](dev_tuning/chunking_variants/dev_chunking_evaluation.json).
- Latency riêng BM25/Dense/Hybrid trên Dev: [`dev_latency.json`](dev_tuning/chunking_variants/E/dev_latency.json).
- Báo cáo Test Config A và lượt đánh giá lại Config E: [`test_report.md`](test_run/test_report.md), [`test_config_e_report.md`](test_run/config_e_final/test_config_e_report.md), cùng JSON kết quả trong `retrieval/results/test_run/`.
- Hướng dẫn tái lập: [`week7_retrieval_reproduction.md`](../../docs/week7_retrieval_reproduction.md).
- Manifest phiên bản/hash dữ liệu, corpus và index: [`reproducibility_manifest.json`](dev_tuning/chunking_variants/reproducibility_manifest.json).
- Script chạy: `scripts/build_dev_chunking_variants.py`, `scripts/evaluate_dev_rrf_weights.py`, `scripts/evaluate_dev_chunking_variants.py`, `scripts/measure_dev_retrieval_latency.py`, `scripts/evaluate_dev_cross_encoder.py`, `scripts/evaluate_test_config_e.py`, `retrieval/run_dev_retrieval.py`.
