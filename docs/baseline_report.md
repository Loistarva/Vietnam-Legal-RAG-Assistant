# Báo cáo baseline Retrieval và Zero-shot trên Dev

**Ngày báo cáo:** 2026-11-07  
**Phạm vi:** BM25, Dense, Hybrid RRF, Hybrid + Cross-Encoder Reranker và Zero-shot generation.  
**Lưu ý:** Retrieval và Zero-shot là hai loại đánh giá khác nhau; các metric của chúng không thể so sánh trực tiếp.

## Tóm tắt kết quả Retrieval

Các metric truy xuất dưới đây là trung bình macro trên 75 câu Dev có Gold đã xác minh. Mỗi phương pháp trả 10 kết quả cho mỗi câu (750 kết quả/phương pháp).

| Phương pháp | Recall@5 | Parent Match@5 | MRR@5 | nDCG@5 | Recall@10 | Parent Match@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.6010 | 0.6053 | 0.5733 | 0.5304 | 0.6736 | 0.6872 | 0.5778 | 0.5612 | 0.1480 |
| Dense | 0.6441 | 0.6663 | 0.6489 | 0.6039 | 0.7574 | 0.7751 | 0.6563 | 0.6490 | 0.1587 |
| Hybrid (BM25 + Dense, RRF) | 0.6769 | 0.6903 | 0.6938 | 0.6315 | 0.7395 | 0.7493 | 0.6973 | 0.6600 | 0.1640 |
| **Hybrid + Reranker** | **0.7335** | **0.7475** | **0.7482** | **0.6981** | **0.7921** | **0.8065** | **0.7482** | **0.7240** | **0.1840** |

Hybrid + Reranker đạt điểm cao nhất trong các phương pháp ở toàn bộ metric được liệt kê. So với Hybrid, Recall@10 tăng từ 0.7395 lên 0.7921, Parent Match@10 từ 0.7493 lên 0.8065, MRR@10 từ 0.6973 lên 0.7482 và nDCG@10 từ 0.6600 lên 0.7240. Đây là kết quả mô tả trên Dev, không phải bằng chứng về ý nghĩa thống kê hay bảo đảm chất lượng pháp lý.

## Kết quả Zero-shot generation

Zero-shot được chạy trên bộ con 30 câu Dev, không đưa context vào model. Kết quả được báo cáo riêng, không đặt chung bảng với metric retrieval.

| Model / phạm vi | Exact Match | Token F1 | Lexical relevance (proxy) | Lexical faithfulness (proxy) | Chấm rubric thủ công |
| --- | ---: | ---: | ---: | ---: | ---: |
| `qwen2.5:7b`, 30 câu, không context | 0.0000 | 0.2329 | 1.0000 | 0.4750 | 0/30 |

Các điểm lexical relevance/faithfulness là proxy tự động từ độ trùng từ vựng, không phải điểm rubric do người chấm. Vì chưa có câu nào được chấm rubric thủ công, các giá trị này **không xác nhận** câu trả lời chính xác, trung thành với luật hay an toàn để sử dụng. Exact Match bằng 0 cũng không tự nó chứng minh mọi câu trả lời sai; metric này yêu cầu khớp văn bản tham chiếu sau chuẩn hóa.

## Dữ liệu và cấu hình

- **Retrieval Dev:** `data/benchmark/queries_dev.json` có 270 câu; 75 câu có `gold_context_ids` đã xác minh được chấm, 195 câu draft được bỏ qua.
- **Zero-shot Dev30:** `evaluation/datasets/dev_gold_30_queries_v1.json`; 30 câu được chọn từ Dev. Tài liệu lựa chọn ghi trạng thái manifest là `proposed_pending_user_and_dev2_review`, do đó không xem mẫu này là đại diện cho toàn bộ Dev hoặc là kết quả A/B đã khóa chính thức.
- **Gold retrieval:** `data/benchmark/ground_truth.json`, chỉ dùng `ground_truth.gold_context_ids`.
- **Corpus:** `data/chunking_output/chunks.jsonl`, 2.164 chunk, 24 văn bản; SHA-256 bắt đầu `9a72a35e532f`.
- **BM25:** Elasticsearch index `bm25-e6-verified-20261101`, trường `content_segmented`.
- **Dense:** `BAAI/bge-m3`, 1024 chiều, Qdrant collection `vietnam_legal_chunks`.
- **Hybrid:** BM25 + Dense, Reciprocal Rank Fusion, `rrf_k=60`, candidate depth 50, Top-10.
- **Hybrid + Reranker:** Cross-Encoder `BAAI/bge-reranker-v2-m3` rerank tối đa 50 candidates, giữ Top-5 để đưa vào context; bảng metric tính trên 10 kết quả retrieval đã lưu cho mỗi câu.
- **Zero-shot:** model `qwen2.5:7b`; 30 bản ghi kết quả đều ghi `context_used=false`.
- `as_of_date` được giữ theo từng câu trong các kết quả retrieval.

## Temporal checks

`retrieval/evaluation/retrieval_report.md` ghi nhận các kiểm tra sau cho BM25, Dense và Hybrid:

| Phương pháp | Temporal Violation Rate | Vi phạm / kết quả đã kiểm tra | Thiếu metadata ngày |
| --- | ---: | ---: | ---: |
| BM25 | 0.0000 | 0 / 750 | 0 |
| Dense | 0.0000 | 0 / 750 | 0 |
| Hybrid | 0.0000 | 0 / 750 | 0 |

Bảng này không bao gồm Hybrid + Reranker hoặc Zero-shot; không suy rộng kết quả temporal của ba phương pháp trên sang các nhánh đó.

## Định nghĩa metric

- **Strict Recall@K:** với từng câu hỏi, số `gold_context_id` phân biệt trong Top-K chia cho tổng số gold ID của câu; lấy trung bình macro theo câu.
- **Parent Match@K:** tỷ lệ `parent_clause_id` gold phân biệt được tìm thấy trong parent ID của Top-K.
- **MRR@K:** nghịch đảo thứ hạng của gold chunk đầu tiên trong Top-K.
- **nDCG@K:** xếp hạng theo nhãn liên quan nhị phân của gold chunk.
- **Precision@10:** số chunk gold trong Top-10 chia cho 10.
- **Exact Match / Token F1:** so sánh câu trả lời với đáp án tham chiếu sau chuẩn hóa; Zero-shot dùng Unicode NFKC, không phân biệt hoa thường, bỏ dấu câu và tách theo khoảng trắng.
- **Lexical relevance / faithfulness:** điểm proxy suy từ từ vựng; không thay thế đánh giá rubric của người chấm.

## Giới hạn và diễn giải

- Retrieval chỉ chấm 75/270 câu Dev đã có Gold xác minh; không bao phủ 195 câu draft.
- Zero-shot dùng một bộ con 30 câu riêng, không cùng mẫu với 75 câu retrieval. Không so sánh điểm Zero-shot với Recall, MRR, nDCG hoặc Precision.
- Chưa có rubric scoring thủ công cho 30 câu Zero-shot. Cần người có chuyên môn kiểm tra nội dung và căn cứ pháp lý trước khi đưa ra kết luận về chất lượng câu trả lời.
- Không có kiểm định ý nghĩa thống kê/độ bất định trong các file metric; chênh lệch là mô tả trên snapshot.
- Đây không phải đánh giá end-to-end của RAG có context, cũng không đại diện cho chất lượng production.
- Test không được dùng để chọn cấu hình và không nằm trong bảng Dev này. Lần chạy xác thực Test hiện dừng ở `HN_181` do query trong `retrieval/results/test/hybrid_reranker_test.json` khác câu chuẩn trong `queries_test.json` (bị lặp từ “bảo vệ”); cần sửa/đồng bộ kết quả và chạy lại validation trước khi báo cáo metric Test.
- Các metric retrieval lấy từ `evaluation/results/bm25_dev_metrics.json`, `dense_dev_metrics.json`, `hybrid_dev_metrics.json` và `hybrid_reranker_dev_metrics.json`. Zero-shot lấy từ `evaluation/results/zero_shot_dev30_metrics.json`; các bản ghi dự đoán nằm trong `evaluation/results/zero_shot_dev30_results.json`.

## Kết luận

Trên 75 câu Dev đã xác minh, Hybrid + Reranker là phương pháp retrieval dẫn đầu trong các metric được báo cáo. Zero-shot `qwen2.5:7b` trên 30 câu Dev không có context đạt Token F1 0.2329; kết quả lexical chỉ mang tính tham khảo và chưa có chấm rubric thủ công. Hai kết quả trả lời hai câu hỏi đánh giá khác nhau: khả năng lấy chứng cứ và khả năng sinh câu trả lời không có chứng cứ truy xuất.
