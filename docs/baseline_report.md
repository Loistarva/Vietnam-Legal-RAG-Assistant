# Báo cáo baseline Retrieval và Zero-shot

**Ngày báo cáo:** 2026-11-07  
**Phạm vi:** BM25, Dense, Hybrid RRF, Hybrid + Cross-Encoder Reranker trên Dev và Test; Zero-shot generation trên 30 câu Dev.  
**Lưu ý:** Retrieval và Zero-shot là hai loại đánh giá khác nhau; các metric của chúng không so sánh trực tiếp được.

## Tóm tắt kết quả Retrieval trên Dev

Các metric dưới đây là trung bình macro trên 75 câu Dev có Gold đã xác minh. Mỗi phương pháp trả 10 kết quả cho mỗi câu (750 kết quả/phương pháp).

| Phương pháp | Recall@5 | Parent Match@5 | MRR@5 | nDCG@5 | Recall@10 | Parent Match@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.6144 | 0.6168 | 0.5904 | 0.5448 | 0.7036 | 0.7225 | 0.5989 | 0.5828 | 0.1560 |
| Dense | 0.6508 | 0.6717 | 0.6533 | 0.6099 | 0.7685 | 0.7858 | 0.6607 | 0.6568 | 0.1653 |
| Hybrid (BM25 + Dense, RRF) | 0.6725 | 0.6849 | 0.7071 | 0.6358 | 0.7528 | 0.7679 | 0.7129 | 0.6709 | 0.1693 |
| **Hybrid + Reranker** | **0.7335** | **0.7475** | **0.7571** | **0.7040** | **0.7921** | **0.8065** | **0.7571** | **0.7300** | **0.1840** |

Khoảng tin cậy 95% ở @10 (percentile bootstrap theo câu, 10.000 lần, seed 42; `confidence_intervals.average` trong các file metric):

| Phương pháp | Recall@10 | Parent Match@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | [0.613, 0.789] | [0.630, 0.809] | [0.507, 0.689] | [0.502, 0.664] | [0.127, 0.189] |
| Dense | [0.681, 0.850] | [0.701, 0.869] | [0.566, 0.751] | [0.570, 0.740] | [0.135, 0.199] |
| Hybrid | [0.668, 0.831] | [0.685, 0.846] | [0.624, 0.798] | [0.590, 0.748] | [0.139, 0.203] |
| Hybrid + Reranker | [0.714, 0.864] | [0.729, 0.877] | [0.674, 0.836] | [0.653, 0.803] | [0.149, 0.221] |

Khoảng tin cậy của từng phương pháp chồng lên nhau nhiều, nên không dùng chúng để kết luận phương pháp nào hơn. So sánh Hybrid + Reranker với Hybrid trên cùng câu hỏi (bootstrap ghép cặp, như `reranking/evaluation/candidate_text_comparison_dev_75.md`):

| Hybrid + Reranker − Hybrid, Dev | Hiệu trung bình | CI95 | Số câu hơn / kém |
| --- | ---: | ---: | ---: |
| Recall@10 | +0.0393 | [−0.0021, +0.0868] | 10 / 4 |
| MRR@10 | +0.0442 | [−0.0218, +0.1148] | 15 / 10 |
| nDCG@10 | +0.0590 | [+0.0081, +0.1162] | 25 / 17 |

Trên Dev, Hybrid + Reranker hơn Hybrid ở nDCG@10 (CI95 không chứa 0); Recall@10 và MRR@10 tăng nhưng chưa phân biệt được (CI95 của Recall@10 chạm 0: [−0,0021; +0,0868]).

## Kết quả Retrieval trên Test

Test gồm 30 câu đã đóng băng; mỗi phương pháp có 300 kết quả (30 câu × Top-10). Số dưới đây là lần chạy thứ tư, trên corpus có khoảng hiệu lực cấp Điều/Khoản/Điểm (D1) và có thêm các văn bản sửa đổi Nghị định 123/2015/NĐ-CP, Thông tư 04/2020/TT-BTP (Nghị định 87/2020, 07/2025, 18/2026, Thông tư 04/2024; chỉ các Điều thuộc phạm vi); index được dựng lại, cấu hình retrieval, reranker và câu hỏi, gold Test không đổi. Hai lần đầu (trước và sau khi PR #27 sửa câu HN_181) chạy trên corpus gốc; lần ba chạy sau khi ghi `effective_to` cho Điều/Khoản bị bãi bỏ bởi văn bản đã có trong corpus. Recall@10 của cả bốn phương pháp giống nhau ở cả bốn lần; so với lần ba, BM25 đổi MRR@10 −0,017, nDCG@10 −0,008, Hybrid + Reranker đổi MRR@10, nDCG@10 +0,001, Dense và Hybrid gần như không đổi (chênh dưới 0,001) (nhật ký ở mục 6 của `docs/sprint6_benchmark.md`). Các file kết quả có đủ 30 query, nội dung query khớp `queries_test.json` (SHA-256 bắt đầu `521eff66a6a0`).

| Phương pháp | Recall@5 | Parent Match@5 | MRR@5 | nDCG@5 | Recall@10 | Parent Match@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.8150 | 0.8317 | 0.8650 | 0.7866 | 0.8672 | 0.8728 | 0.8650 | 0.8117 | 0.1767 |
| Dense | 0.8339 | 0.8283 | 0.8333 | 0.7806 | 0.9061 | 0.9006 | 0.8375 | 0.8132 | 0.1800 |
| Hybrid (BM25 + Dense, RRF) | 0.8689 | 0.8744 | **0.9278** | **0.8539** | 0.9367 | 0.9311 | **0.9333** | **0.8827** | 0.1900 |
| Hybrid + Reranker | **0.8978** | **0.8978** | 0.8694 | 0.8447 | **0.9561** | **0.9561** | 0.8750 | 0.8693 | **0.1967** |

Khoảng tin cậy 95% ở @10:

| Phương pháp | Recall@10 | Parent Match@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | [0.767, 0.953] | [0.776, 0.951] | [0.758, 0.958] | [0.707, 0.906] | [0.140, 0.217] |
| Dense | [0.839, 0.965] | [0.829, 0.962] | [0.732, 0.932] | [0.724, 0.892] | [0.147, 0.213] |
| Hybrid | [0.870, 0.989] | [0.861, 0.987] | [0.856, 1.000] | [0.810, 0.948] | [0.153, 0.230] |
| Hybrid + Reranker | [0.898, 1.000] | [0.898, 1.000] | [0.778, 0.958] | [0.793, 0.939] | [0.157, 0.237] |

| Hybrid + Reranker − Hybrid, Test | Hiệu trung bình | CI95 | Số câu hơn / kém |
| --- | ---: | ---: | ---: |
| Recall@10 | +0.0194 | [+0.0000, +0.0500] | 2 / 0 |
| MRR@10 | −0.0583 | [−0.1722, +0.0500] | 3 / 5 |
| nDCG@10 | −0.0134 | [−0.0890, +0.0558] | 7 / 5 |

Trên Test, Hybrid + Reranker có Recall, Parent Match và Precision cao nhất; Hybrid có MRR@5, MRR@10, nDCG@5 và nDCG@10 cao nhất. Không chênh lệch nào giữa hai phương pháp phân biệt được: Recall@10 chỉ khác ở 2/30 câu, MRR@10 và nDCG@10 có CI95 chứa 0. Với 30 câu, CI95 rộng tới khoảng ±0,1. Các điểm Test chỉ để báo cáo cuối, không dùng để chọn hay tinh chỉnh cấu hình.

## Temporal checks

Chunk trả về trong Top-10 không có hiệu lực tại `as_of_date` của câu hỏi, theo `effective_from`, `effective_to` của `data/chunking_output/chunks.jsonl` (`retrieval.temporal.is_effective_at`), trên các câu được chấm:

| Phương pháp | Dev: vi phạm / đã kiểm tra | Test: vi phạm / đã kiểm tra | Thiếu metadata ngày |
| --- | ---: | ---: | ---: |
| BM25 | 0 / 750 | 0 / 300 | 0 |
| Dense | 0 / 750 | 0 / 300 | 0 |
| Hybrid | 0 / 750 | 0 / 300 | 0 |
| Hybrid + Reranker | 0 / 750 | 0 / 300 | 0 |

Temporal Violation Rate bằng 0 ở cả 8 file. Corpus hiện tại (SHA-256 sau khi đổi CRLF thành LF bắt đầu `c18239351424`) có khoảng hiệu lực riêng cho các Điều/Khoản/Điểm bị bãi bỏ hoặc sửa đổi, ghi trong 28 bản ghi của `data/reference/provision_periods.json`: 3 của Nghị định 126/2014/NĐ-CP (Điều 19–50, điểm a khoản 1 và khoản 2 Điều 63), 16 của Nghị định 123/2015/NĐ-CP (theo Nghị định 87/2020, 07/2025, 18/2026), 5 của Nghị định 87/2020/NĐ-CP, 2 của Thông tư 04/2020/TT-BTP (theo Thông tư 04/2024), 1 của Thông tư 34/2017/TT-BYT và 1 của Thông tư 57/2015/TT-BYT. Khoản bị sửa đổi trỏ tới chunk của văn bản sửa đổi chứa nội dung mới, nên tại `as_of_date` sau ngày sửa retriever trả nội dung mới. Đo lại bằng corpus hiện tại các kết quả chạy trước: trên corpus gốc, Dev có 71, 55, 66, 85 chunk vi phạm (ở 19, 12, 16, 12 câu) với BM25, Dense, Hybrid, Hybrid + Reranker, Test có 6, 4, 3, 7; lần ba (chưa có văn bản sửa đổi Nghị định 123/2015, Thông tư 04/2020) còn 5, 1, 2, 2 trên Dev và 2, 2, 3, 1 trên Test. Còn chưa ghi: các thay đổi chỉ bãi bỏ cụm từ, tên Điều 3 Nghị định 123/2015, Phụ lục 5 Thông tư 04/2020 (`not_applied`), và các văn bản sửa đổi ban hành sau Nghị định 18/2026, Thông tư 04/2024 chưa được kiểm (D1 trong `docs/sprint6_issue_recheck_after_merge.docx`).

## Kết quả Zero-shot generation

Zero-shot chạy `qwen2.5:7b` trên 30 câu Dev, không đưa context vào model. Tập 30 câu được xác nhận ngày 07/11/2026 (`evaluation/review/dev30_confirmation_v1.json`): cả 30 câu có gold đã xác nhận, không thuộc Test, không dùng chung Khoản với gold Test, gold đều thuộc Luật 52/2014/QH13 và có hiệu lực tại `as_of_date`.

| Chỉ số | Giá trị |
| --- | ---: |
| Exact Match | 0.0000 |
| Token F1 | 0.2329 |
| Answer Relevance chấm tay (1–5) | 4.43 (chuẩn hóa 0.8583) |
| Faithfulness chấm tay (1–5) | 2.53 (chuẩn hóa 0.3833) |
| Số câu chấm tay | 30/30 |

Điểm chấm tay theo `evaluation/rubrics/zero_shot_rubric_guide_v1.md`, bảng điểm và căn cứ từng câu ở `evaluation/rubrics/zero_shot_dev30_manual_scores_v1.csv`. Faithfulness: 7 câu điểm 4, 9 câu điểm 3, 7 câu điểm 2, 7 câu điểm 1; không câu nào đạt 5, vì câu nào cũng có ít nhất một chỗ sai: dẫn sai số Điều, nêu lần sửa đổi không có thật, trích dẫn bịa hoặc diễn giải chưa chính xác. 7 câu có kết luận chính sai (HN_009, HN_021, HN_035, HN_087, HN_155, HN_297, HN_299), trong đó HN_035 (câu bẫy văn bản cũ) nói Luật 2014 vẫn cấm hôn nhân cùng giới. Model thường trả lời đúng trọng tâm (16 câu Relevance 5) nhưng nội dung pháp lý không đáng tin khi không có context.

| Chủ đề | Số câu | Relevance | Faithfulness | Token F1 |
| --- | ---: | ---: | ---: | ---: |
| ket_hon | 7 | 4.43 | 2.43 | 0.1907 |
| tai_san | 5 | 4.80 | 3.20 | 0.2407 |
| cap_duong | 5 | 4.40 | 2.20 | 0.2676 |
| ly_hon | 3 | 4.33 | 2.67 | 0.1764 |
| con_cai | 3 | 5.00 | 3.33 | 0.1650 |
| nguyen_tac_quy_dinh | 3 | 4.00 | 2.33 | 0.3194 |
| vo_chong | 2 | 4.00 | 2.50 | 0.2108 |
| mang_thai_ho | 2 | 4.00 | 1.00 | 0.3538 |

Token F1 không phản ánh độ đúng: nhóm `mang_thai_ho` có Token F1 cao nhất nhưng cả 2 câu đều sai kết luận. File metric vẫn ghi điểm lexical tự động để tham khảo (lexical relevance 1.0000, lexical faithfulness 0.4750), nhưng không dùng: lexical relevance cho 5/5 ở cả 30 câu, lexical faithfulness chỉ trùng điểm chấm tay ở 5/30 câu.

## Dữ liệu và cấu hình

- **Retrieval Dev:** `data/benchmark/queries_dev.json` có 270 câu; 75 câu có `gold_context_ids` đã xác minh được chấm, 195 câu draft được bỏ qua.
- **Retrieval Test:** 30/30 câu trong Test đã đóng băng được chấm với Gold; mỗi phương pháp có 300 kết quả Top-10.
- **Zero-shot Dev30:** `evaluation/datasets/dev_gold_30_queries_v1.json`, chọn bởi Dev 1 (`evaluation/manifests/dev_gold_30_manifest.json`), xác nhận ở `evaluation/review/dev30_confirmation_v1.json`.
- **Gold retrieval:** `data/benchmark/ground_truth.json`, chỉ dùng `ground_truth.gold_context_ids`.
- **Corpus:** `data/chunking_output/chunks.jsonl`, 2.322 chunk, 28 văn bản (văn bản sửa đổi nhiều văn bản chỉ lấy các Điều thuộc phạm vi, `data/reference/corpus_scope.json`), có khoảng hiệu lực cấp Điều/Khoản/Điểm (D1); SHA-256 (CRLF → LF) bắt đầu `c18239351424`.
- **BM25:** Elasticsearch index `bm25-e6-verified-20261101`, trường `content_segmented`.
- **Dense:** `BAAI/bge-m3`, 1024 chiều, Qdrant collection `vietnam_legal_chunks`; chọn trên Dev so với bkai và AITeamVN (`retrieval/evaluation/dense_model_comparison_dev_75.md`).
- **Hybrid:** BM25 + Dense, Reciprocal Rank Fusion, `rrf_k=60`, candidate depth 50, Top-10.
- **Hybrid + Reranker:** Cross-Encoder `BAAI/bge-reranker-v2-m3` rerank tối đa 50 candidates, `candidate_text: document_breadcrumb_chunk_text`, giữ Top-5 để đưa vào context; bảng metric tính trên 10 kết quả đã lưu cho mỗi câu.
- **Zero-shot:** `qwen2.5:7b` qua Ollama, `temperature` 0, `num_predict` 512 (câu trả lời HN_299 bị cắt); 30 bản ghi kết quả đều ghi `context_used=false`; prompt không đưa `as_of_date` vào.
- `as_of_date` được giữ theo từng câu trong các kết quả retrieval.

## Định nghĩa metric

- **Strict Recall@K:** với từng câu hỏi, số `gold_context_id` phân biệt trong Top-K chia cho tổng số gold ID của câu; lấy trung bình macro theo câu.
- **Parent Match@K:** tỷ lệ `parent_clause_id` gold phân biệt được tìm thấy trong parent ID của Top-K.
- **MRR@K:** nghịch đảo thứ hạng của gold chunk đầu tiên trong Top-K.
- **nDCG@K:** xếp hạng theo nhãn liên quan nhị phân của gold chunk.
- **Precision@10:** số chunk gold trong Top-10 chia cho 10.
- **Khoảng tin cậy:** percentile bootstrap 95% cho trung bình macro, lấy mẫu lại câu hỏi 10.000 lần, seed 42 (`evaluation/metrics.py`). So sánh ghép cặp lấy mẫu lại hiệu số điểm từng câu giữa hai phương pháp (`scripts/baseline_report_extras.py`).
- **Exact Match / Token F1:** so sánh câu trả lời với đáp án tham chiếu sau chuẩn hóa; Zero-shot dùng Unicode NFKC, không phân biệt hoa thường, bỏ dấu câu và tách theo khoảng trắng.
- **Answer Relevance / Faithfulness:** điểm chấm tay 1–5, chuẩn hóa `(điểm − 1) / 4`, theo hướng dẫn chấm.

## Giới hạn và diễn giải

- Retrieval chỉ chấm 75/270 câu Dev đã có Gold xác minh; không bao phủ 195 câu draft.
- Test chỉ có 30 câu, nên CI95 rộng và chênh lệch giữa các phương pháp trên Test phần lớn không phân biệt được.
- Zero-shot dùng một bộ con 30 câu riêng, chỉ về Luật 52/2014/QH13, không cùng mẫu với 75 câu retrieval và không có câu historical_law. Một số câu dùng chung Khoản gold, nên 30 câu không phải 30 quan sát độc lập.
- Điểm chấm tay do một người chấm (Dev 5, có Claude hỗ trợ đối chiếu chunk gold), chưa có người chấm thứ hai. Điểm gắn với đúng câu trả lời đã lưu (`prediction_sha256`); chạy lại model thì phải chấm lại.
- Đây không phải đánh giá end-to-end của RAG có context, cũng không đại diện cho chất lượng production.
- Nguồn số: Dev từ `evaluation/results/{bm25,dense,hybrid,hybrid_reranker}_dev_metrics.json`; Test từ `evaluation/results/{bm25,dense,hybrid,hybrid_reranker}_test_metrics.json`; temporal và so sánh ghép cặp từ `evaluation/results/baseline_report_extras.json` (`python scripts/baseline_report_extras.py`); Zero-shot từ `evaluation/results/zero_shot_dev30_metrics.json`, `zero_shot_dev30_scored.json`, câu trả lời ở `zero_shot_dev30_results.json`.

## Kết luận

Trên Dev, Hybrid + Reranker dẫn đầu mọi metric retrieval và hơn Hybrid ở nDCG@10 với CI95 không chứa 0; Recall@10 tăng 0,039 nhưng CI95 chạm 0. Trên Test, Hybrid + Reranker có Recall cao nhất còn Hybrid có MRR và nDCG cao nhất, nhưng chênh lệch giữa hai phương pháp không phân biệt được với 30 câu. Không phương pháp nào trả chunk hết hiệu lực theo metadata hiện có, kể cả các Điều/Khoản đã bị bãi bỏ mà kết quả trên corpus cũ còn trả về. Zero-shot `qwen2.5:7b` không có context trả lời đúng trọng tâm (Relevance 4.43/5) nhưng nội dung pháp lý kém (Faithfulness 2.53/5, 7/30 câu sai kết luận, không câu nào không có lỗi); đây là mức so sánh cho RAG có context ở sprint sau.
