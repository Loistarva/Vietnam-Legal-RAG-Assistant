# Báo cáo so sánh Zero-shot và Controlled RAG — Dev30

**Ngày lập:** 16/11/2026  
**Run A:** Zero-shot Qwen2.5:7b, ngày 15/11/2026  
**Run B:** Controlled RAG Qwen2.5:7b, ngày 14/11/2026  
**Mẫu:** 30 câu ghép cặp theo `query_id`; cả 30 câu có trong cả hai run.

## Tóm tắt

Trên 30 câu Dev Gold này, Run B có điểm chấm tổng hợp cao hơn Run A ở Answer Relevance và Legal Correctness. Điểm tổng hợp dùng quy tắc đã thống nhất cho bộ phiếu này: lấy điểm thấp hơn giữa Dev3 và Dev4 cho hai thang điểm 1–5; các nhãn Hallucination bất đồng được xử lý theo ghi chú phân xử Dev2. Kết quả vì vậy là điểm bảo thủ theo quy tắc dự án, không phải trung bình hai người chấm.

Các kiểm định theo cặp cho thấy chênh lệch điểm có ý nghĩa thống kê trong mẫu này. Cần diễn giải thận trọng: chỉ có 30 câu, tập được chọn từ Dev Gold, và khoảng tin cậy không thay thế đánh giá trên tập độc lập.

## Điểm chấm tay đã tổng hợp

| Tiêu chí | Run A mean / median | Run B mean / median | B−A mean | Bootstrap CI 95% cho B−A | Wilcoxon signed-rank |
|---|---:|---:|---:|---:|---:|
| Answer Relevance | 4.03 / 4 | 4.67 / 5 | +0.63 | [+0.20, +1.03] | p = 0.0047 |
| Legal Correctness | 2.60 / 3 | 4.23 / 5 | +1.63 | [+1.17, +2.10] | p = 0.000014 |

CI là percentile bootstrap của trung bình chênh lệch theo câu, 10.000 lần lấy mẫu, seed 42. Wilcoxon là kiểm định hai phía trên chênh lệch cặp; p-value chưa hiệu chỉnh cho nhiều phép thử.

### Hallucination, hành động trả lời và Context Faithfulness

| Metric chấm tay | Run A | Run B |
|---|---:|---:|
| Hallucination = Yes | 25/30 (83.3%) | 4/30 (13.3%) |
| Hành động `answer` | 30/30 | 29/30 |
| Hành động `abstain` | 0/30 | 1/30 |
| Context Faithfulness | N/A | mean 4.52, median 5 trên 29 câu được chấm; 1 câu N/A |

Run B từ chối một câu có đáp án trong Gold (HN_035), nên metric code ghi một false abstention trên 30 câu trả lời được. Context Faithfulness chỉ áp dụng cho B; HN_035 được ghi N/A vì run không sinh câu trả lời có căn cứ để chấm mức hỗ trợ từ context.

Ước lượng Hallucination Rate kèm CI95% Wilson: Run A **83.3% [66.4%, 92.7%]** (25/30); Run B **13.3% [5.3%, 29.7%]** (4/30). Đây là khoảng tin cậy nhị thức trên 30 câu, không điều chỉnh theo thiết kế chọn mẫu Dev Gold.

### Độ đồng thuận người chấm trước khi tổng hợp

Hai bộ phiếu Dev3 và Dev4 đều có điểm cho 60 câu trả lời. Tính trên điểm gốc trước khi chọn điểm thấp hơn:

| Tiêu chí | Kappa | Trọng số |
|---|---:|---|
| Answer Relevance | 0.656 | Quadratic weighted |
| Legal Correctness | 0.826 | Quadratic weighted |
| Hallucination | 0.834 | Cohen's kappa, không trọng số |

Response Action khớp ở 60/60 phiếu. Có 23 bất đồng Answer Relevance, 27 bất đồng Legal Correctness và 5 bất đồng Hallucination. Điểm tổng hợp giữ nguyên hai rationale gốc có gắn nhãn Dev3/Dev4; các nhãn Hallucination lệch có thêm ghi chú phân xử Dev2.

## Metric tính bằng code

### Retrieval cho Run B

Tính trên danh sách rerank Top-5 của 30 câu, so khớp nghiêm ngặt `chunk_id` với `gold_context_ids` đã xác minh:

| Metric | Run B |
|---|---:|
| Strict chunk Recall@5 | 0.880 |
| MRR@5 | 0.843 |
| n | 30 |

### Citation và grounding

| Metric | Run A | Run B |
|---|---:|---:|
| Citation Precision | 0.000 | 0.706 |
| Citation Recall | 0.000 | 0.736 |
| Citation Validity | N/A | 1.000 (52/52 evidence indices hợp lệ) |
| Citation count | 29 sinh; 0 đúng theo metric | 52 sinh; 37 đúng theo metric |

Run A không có context/evidence được cấp cho model; Citation Validity vì vậy không áp dụng. Citation Precision/Recall bằng 0 trong metric này và không đồng nghĩa với Legal Correctness bằng 0. Với Run B, Precision/Recall là điểm tổng hợp từ metric JSON; số citation đếm được báo riêng.

Đối chiếu JSONL hiện có, tổng citation sinh/đúng theo metric là **Run A 29/0** và **Run B 52/37**. Trạng thái Grounding Gate của Run B trong 30 bản ghi JSONL là **29 PASS, 1 ABSTAIN, 0 FAIL, 0 NEEDS_CLARIFICATION**; HN_035 abstain ở confidence filter nên Gate không đánh giá câu đó. Run A là zero-shot, không chạy Grounding Gate.

### Runtime, token, truncation và chi phí

| Metric | Run A | Run B |
|---|---:|---:|
| Số câu gọi LLM | 30/30 | 29/30 |
| `latency_ms` p50 / p95 | 6.85 s / 14.41 s | 31.84 s / 50.25 s |
| Token input trung bình / output trung bình | 622 / 152 | 2,469 / 188 |
| Truncation | 0/30 | 0/30 |
| Câu trả lời không phải tiếng Việt | 0/30 | 0/30 |
| Chi phí suy luận | $0.00 | $0.00 |

Run A có một lượt khởi động nguội HN_001 (`load_ms` = 14.23 s). Sau khi loại câu này, p50/p95 của Run A là 6.74 s / 12.46 s (n=29). Run B là chế độ precomputed: `latency_ms` không gồm retrieval và rerank, nên không thể dùng trực tiếp để kết luận Run B chậm hơn nếu so với thời gian end-to-end của một lần chạy live. Cả hai run dùng suy luận local Ollama; chi phí USD bằng 0 theo manifest metric.

#### Latency theo stage của Run B (JSONL, n=29 câu có gọi LLM)

| Stage | p50 | p95 | Phạm vi |
|---|---:|---:|---|
| Retrieval | N/A | N/A | Kết quả retrieval được nạp precomputed; `retrieval_ms` null |
| Load model | 11.97 ms | 20.86 ms | `load_ms` |
| Prompt evaluation | 2,900.25 ms | 3,695.92 ms | `prompt_eval_ms` |
| Sinh output | 28,603.21 ms | 46,638.21 ms | `eval_ms` |
| LLM tổng | 31,833.33 ms | 50,247.00 ms | `llm_total_ms` |
| Đến token đầu (TTFT) | 2,914.97 ms | 3,711.05 ms | `ttft_model_ms` |

Các p95 stage dùng percentile tuyến tính (95th percentile) trên giá trị khác null; p50 dùng median. Stage là thời gian Ollama ghi trong JSONL, không cộng thành end-to-end vì các mốc có thể lồng nhau.

Metric tự động phụ trợ: Exact Match = 0.000 cho cả hai; Token F1 = 0.273 (A) và 0.376 (B). Các metric lexical này đo trùng khớp văn bản, không thay thế các rubric pháp lý hoặc Context Faithfulness.

## Phân tích lỗi tiêu biểu

- **Zero-shot thêm claim pháp lý ngoài căn cứ:** HN_007-A gắn hành vi bị cấm với “vi phạm nghiêm trọng quy định về trung thành”; trường hợp này được phân xử Hallucination = Yes.
- **Controlled RAG diễn đạt ngoại lệ quá rộng:** HN_016-B mở rộng ngoại lệ tại Điều 40 vượt quá nội dung nguồn; được phân xử Hallucination = Yes.
- **Kết luận pháp lý sai dù câu trả lời có vẻ trôi chảy:** HN_035-A hiểu sai tình trạng pháp luật năm 2026. Điểm Legal Correctness thấp kéo kết quả Run A xuống.
- **RAG không đảm bảo câu trả lời luôn đúng:** HN_299-B đưa thông tin sai về chủ thể và cách xác định mức cấp dưỡng; Legal Correctness tổng hợp là 1.
- **Citation cần được xem cùng phạm vi áp dụng:** một số citation trong B có thể kém liên quan dù là evidence hợp lệ; Citation Validity cao không đồng nghĩa Citation Precision hoặc Legal Correctness cao.
- **Từ chối nhầm:** HN_035-B abstain dù câu hỏi có căn cứ trong Gold; đây là false abstention.

## Giới hạn và cách đọc kết quả

1. Đây là 30 câu Dev Gold, không phải kết quả holdout Test; không dùng để khẳng định chất lượng ngoài phạm vi mẫu này.
2. Điểm AR/LC tổng hợp chọn mức thấp hơn trong hai điểm Dev3/Dev4 theo chỉ đạo cho bảng này. Cách này có xu hướng hạ điểm so với trung bình hoặc adjudication đầy đủ; kết quả B−A nên được hiểu là so sánh theo quy tắc tổng hợp bảo thủ đã chọn.
3. Hallucination là nhãn thủ công. Năm bất đồng được phân xử riêng; rationale gốc của cả hai người chấm vẫn được giữ trong bảng.
4. Context Faithfulness chỉ có cho B, có một trường hợp N/A, nên không phải phép so sánh A/B.
5. Thời gian B là precomputed, không gồm retrieval/rerank; không so trực tiếp với latency end-to-end live.
6. Các p-value là phân tích trên một mẫu nhỏ và chưa điều chỉnh multiple testing; xem như bằng chứng mô tả cho tập 30 câu.

## Nguồn dữ liệu

- Bảng cặp theo câu và điểm Dev2: `evaluation/results/dev/20261116_ab_per_question.csv`
- Phiếu tổng hợp blind: `evaluation/results/dev/Blind_scroring/blinded_ab_scoring_v1_final.csv`
- Phiếu Dev3/Dev4 và Context Faithfulness B-only: `evaluation/results/dev/Blind_scroring/`
- Metric Run A: `evaluation/results/metrics_A_B_results/20261115_zero_shot_qwen25_dev30_metrics.json`
- Metric Run B: `evaluation/results/metrics_A_B_results/results_metrics.json`
- Kết quả retrieval Run B: `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2/results.jsonl`
- Định nghĩa metric và quy tắc thời gian: `evaluation/metric_definitions_v1.md`

