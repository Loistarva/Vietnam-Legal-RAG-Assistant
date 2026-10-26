# Lượt chạy Retrieval trên Test — 26/10/2026

## Cập nhật: đánh giá lại cấu hình E đã khóa

Sau khi chốt E trên Dev, đã chạy một lượt trên cùng `queries_test.json` bằng corpus/index E và Cross-Encoder thật. Test đã được xem trước đó ở lượt Config A, nên đây là đánh giá lại, không phải phép đo độc lập mới. Không tham số nào được tune theo kết quả.

| Phương pháp | Recall@5 | MRR@5 | Latency mean / median / p95 (ms) |
| --- | ---: | ---: | ---: |
| BM25-only | 0,3111 | 0,1433 | 511,4 / 392,5 / 1.006,9 |
| Hybrid RRF 0,35/0,65 | 0,4222 | 0,3300 | 1.677,7 / 891,3 / 8.497,3 |
| Hybrid + Cross-Encoder thật | **0,6444** | **0,5222** | 52.904,0 / 48.686,8 / 83.839,5 |

Chi tiết cấu hình, metric theo query, ánh xạ chunk và Top-50/Top-10: [`Config E report`](config_e_final/test_config_e_report.md), [`metrics JSON`](config_e_final/test_config_e_metrics.json), [`rankings JSON`](config_e_final/test_config_e_rankings.json).

Recall@5 Config E chưa đạt mục tiêu 85%. `as_of_date` từng query hiện chưa được truyền vào hai nhánh Hybrid; các kết quả này chưa xác nhận đầy đủ temporal pre-filter theo sơ đồ.

---

## Thiết lập

- Bộ câu hỏi: `data/benchmark/queries_test_revised.json` (15 câu; nội dung giống `queries_test.json`).
- Nhãn đối chiếu: `data/benchmark/gold_id_proposals_300_test_revised.json`.
- Corpus: `data/chunking_output/chunks.jsonl` (2.011 chunks).
- Index thưa: Elasticsearch `legal-child-chunks-current`.
- Index vector: Qdrant `vietnam_legal_chunks_current`; model embedding `bkai-foundation-models/vietnamese-bi-encoder`.
- Hybrid: BM25 và Dense chạy song song, hợp nhất RRF với `k=60`, tối đa 50 ứng viên.
- Metric: tính trên 5 thứ hạng đầu; kết quả Top-10 được cắt còn Top-5, reranker trả trực tiếp Top-5.
- Tệp đầu ra: `test_bm25.json`, `test_hybrid.json`, `hybrid_reranker_cross_encoder.json`, `hybrid_reranker_cross_encoder_eval.json` và `test_proposal_metrics_top5_revised.json` trong thư mục này.

## Kết quả theo proposal IDs

File `gold_id_proposals_300_test_revised.json` có proposal cho cả 15 câu Test. Cả 15 câu đều có ít nhất một `gold_context_id` khớp ID trong `chunks.jsonl`. Với HN_048, HN_052 và HN_060, chunk IDs được gắn thêm để chấm retrieval cấp chunk; version ID chứa evidence trạng thái/ngày hiệu lực được lưu riêng ở `gold_document_version_ids`.

| Giai đoạn xếp hạng | Recall@5 (15 câu) | MRR@5 (15 câu) |
| --- | ---: | ---: |
| Chỉ BM25 | 0,3111 | 0,1433 |
| Hybrid RRF | 0,2889 | 0,2500 |
| Hybrid + Cross-Encoder `BAAI/bge-reranker-v2-m3` | 0,5778 | 0,4556 |

Cả 15 câu hiện đều có chunk ID đối chiếu, đồng thời giữ metadata version liên quan ở trường riêng. HN_048 dùng chunk NĐ 126/2014 Điều 1 theo chủ đề; ngày hết hiệu lực của TT 07/2002 vẫn nằm trong version metadata riêng. HN_052 dùng Luật 22/2000 Điều 109; HN_060 dùng NĐ 123/2015 Điều 1 với metadata tình trạng hiệu lực một phần. Các con số là so khớp proposal chưa xác minh đầy đủ. HN_004 và HN_008 đã hạ về draft; ID trùng gold/candidate đã được loại; HN_036 dùng chunk Điều 132(1). Chi tiết ở `docs/test_set_revised_notes.md`.

Dòng Hybrid + Cross-Encoder dùng model thật `BAAI/bge-reranker-v2-m3`, chạy trên CPU. File mock trước đó được giữ lại làm kết quả thử luồng, không dùng làm kết quả Cross-Encoder.

## Latency và lỗi

- BM25/Hybrid: runner Dev 4 đo một lần gọi `HybridRetriever.retrieve()` gồm BM25, Dense chạy song song và RRF; cùng một latency được ghi vào hai loại kết quả. Đây là **latency truy xuất kết hợp**, không phải phép đo riêng cho BM25 và Hybrid. Trên 15 câu: trung bình 5.964,9 ms, trung vị 172,3 ms, p95 86.565,9 ms. Cold start/nạp model làm tăng phần đuôi; xem số liệu theo câu trong file metric JSON.
- Hybrid + Cross-Encoder thật: latency đầu-cuối trung bình 56.240,5 ms, trung vị 52.164,6 ms, p95 95.667,3 ms; riêng bước rerank trung bình 51.676,9 ms, trung vị 49.921,0 ms, p95 80.659,0 ms. Chạy CPU; lượt đầu gồm 23.299,9 ms nạp model. Số theo từng query nằm trong `hybrid_reranker_cross_encoder_metrics.json`.
- Cấu hình Cross-Encoder: 50 ứng viên đầu vào, Top-5 đầu ra, `batch_size=16`, `max_length=512`, `candidate_text=chunk_text`; RRF giữ `k=60`. Không đổi tham số theo Test.
- Truy xuất đủ 15 câu, không có lỗi theo câu.
- Cross-Encoder thật và dense query encoder đã được nạp; cả 15 query rerank thành công, mỗi query chấm đủ 50 ứng viên. Không có lỗi theo query.
- Pipeline reranker cảnh báo không nhận `as_of_date`; lượt này chưa áp dụng lọc thời gian theo từng câu. Không xem đây là đánh giá đầy đủ pipeline production có metadata/temporal pre-filter.

## Diễn giải

Lượt này đã chạy lại Hybrid retrieval trên cùng 15 câu, lấy 50 candidate RRF cho mỗi query rồi chấm bằng Cross-Encoder thật; metric được tính trên `gold_id_proposals_300_test_revised.json`. Recall@5 là 57,78%, chưa đạt mục tiêu 85%. Đây là kết quả proposal chưa được xác minh đầy đủ. Temporal filter chưa được áp dụng theo từng câu; không dùng kết quả Test để tune.

Các tệp JSON giữ nguyên khóa kỹ thuật theo hợp đồng dữ liệu để script có thể đọc lại; phần văn bản giải thích trong báo cáo này đã được Việt hóa.






