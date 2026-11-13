# Định nghĩa metric runtime và từ chối (DoD-13, v1)

Phiên bản: `metrics_runtime_v1` (2026-11-13). Áp dụng cho Run A (zero-shot) và Run B (Controlled RAG) từ lượt chạy sau review PR #45. Các metric chất lượng (Recall@5, MRR@5, Legal Correctness, Context Faithfulness, Citation Precision/Recall/Validity, Hallucination, Answer Relevance) giữ nguyên định nghĩa ở mục "5. Metrics thống nhất" của kế hoạch Sprint 9 và `evaluation/metrics.py`; tài liệu này không đổi chúng.

Hệ thống không stream câu trả lời trước Gate (LLM → buffer → Grounding Gate → SSE chỉ khi PASS), nên TTFT và cost được định nghĩa theo đúng cách hệ thống chạy, không theo cách đo của một chatbot stream.

## 1. Trường dữ liệu dùng để tính

| Trường | Run A (`evaluation/zero_shot.py`) | Run B (`orchestration/rag_pipeline.py`) | Ý nghĩa |
| --- | --- | --- | --- |
| `latency_ms` | có | có | Thời gian toàn bộ một câu, ms. Run A = một lần gọi model; Run B = từ lúc nhận câu hỏi đến lúc có record sau Gate. |
| `latency_breakdown.retrieval_ms` | luôn null | null khi dùng artifact precomputed; có giá trị khi chạy retrieval live | Retrieval + rerank + parent context, ms. |
| `latency_breakdown.llm_total_ms` | có | có nếu có gọi model | Thời gian gateway chờ Ollama trả lời (wall clock), ms. |
| `latency_breakdown.ttft_model_ms` | có | có nếu có gọi model | `load_ms + prompt_eval_ms`: từ lúc gửi đến token đầu tiên của model. |
| `latency_breakdown.load_ms`, `prompt_eval_ms`, `eval_ms` | có | có nếu có gọi model | `load_duration`, `prompt_eval_duration`, `eval_duration` của Ollama (ns → ms). |
| `token_usage.input`, `token_usage.output` | có | có | `prompt_eval_count`, `eval_count` của Ollama. |
| `llm_calls` | luôn 1 | 0 nếu dừng trước LLM, 1 nếu có gọi model | Số lần gọi model cho câu đó. |
| `abstained`, `abstention_reason`, `abstention_source`, `needs_clarification` | không có (Run A không có Gate) | mọi record | Xem mục 4. |
| `cjk_chars` (A), `retrieval_trace.llm.cjk_chars_before_gate` (B) | có | có nếu có gọi model | Số ký tự chữ Hán/kana/Hangul trong câu trả lời của model, trước Gate. |

Giá trị null nghĩa là không đo được. Không thay null bằng 0 khi tính trung bình hay phân vị: câu có giá trị null được loại khỏi phép tính đó và số câu bị loại được ghi cạnh kết quả.

## 2. Latency

### 2.1 TTFT: báo 2 loại

| Loại | Công thức | Ghi chú |
| --- | --- | --- |
| TTFT của model | `latency_breakdown.ttft_model_ms` | Giá trị xấp xỉ vì gateway gọi Ollama với `stream: false`: Ollama trả thời gian nạp model và xử lý prompt, không trả thời điểm phát token đầu tiên. |
| TTFT người dùng thấy | `latency_ms` | Câu trả lời chỉ hiện sau khi qua Gate, nên người dùng không thấy token nào trước khi cả câu sinh xong. TTFT người dùng ≈ total latency. |

### 2.2 Total latency

`latency_ms`. Run B chính thức dùng retrieval tính sẵn (`retrieval_ms = null`), nên `latency_ms` của Run B **không gồm** thời gian retrieval và rerank. Báo cáo phải ghi rõ điều này cạnh con số. Khi chạy live, báo thêm `retrieval_ms` riêng.

### 2.3 p50, p95 và câu khởi động nguội

- Báo p50 và p95 của `latency_ms`, `ttft_model_ms`, `eval_ms`, tách Run A và Run B.
- Phân vị dùng nội suy tuyến tính (`numpy.percentile` mặc định). Với n = 30, p95 gần như là giá trị lớn thứ hai; ghi n cạnh kết quả.
- Câu khởi động nguội = câu có `load_ms > 1000`. Ollama nạp model lần đầu mất tới khoảng 12 giây (đo ngày 11/11), nên các câu này bị loại khỏi p50/p95 và báo riêng: số câu, `query_id`, `load_ms`. Báo cáo ghi rõ đã loại bao nhiêu câu.
- Run B có bước warm-up trong `scripts/run_rag_batch.py`; Run A không có, nên câu đầu tiên của Run A thường là câu khởi động nguội.

## 3. Cost/request

Qwen chạy local, nên chi phí API là 0 USD cho Run A và Run B. Thay cho chi phí USD, mỗi run báo:

| Chỉ số | Công thức |
| --- | --- |
| Token input trung bình | trung bình `token_usage.input` trên các câu có `llm_calls = 1` |
| Token output trung bình | trung bình `token_usage.output` trên các câu có `llm_calls = 1` |
| Số lần gọi model | tổng `llm_calls` và trung bình `llm_calls` trên mọi câu (Run B < 1 nếu có câu dừng trước LLM) |
| Thời gian GPU/CPU sinh token | trung bình và p95 của `eval_ms` trên các câu có `llm_calls = 1` |

Chi phí USD chỉ áp dụng cho Run C nếu chạy API trả phí: `cost_usd = token_input × đơn giá input + token_output × đơn giá output`, ghi đơn giá và ngày lấy đơn giá trong manifest.

## 4. Abstention

Chỉ Run B có Gate và 4 trường từ chối. Mọi record Run B có đủ 4 trường:

| Trường hợp | `grounding_status` | `abstained` | `abstention_reason` | `abstention_source` | `needs_clarification` | `llm_calls` |
| --- | --- | --- | --- | --- | --- | --- |
| Trả lời bình thường | PASS | false | null | null | false | 1 |
| Confidence chặn trước LLM | ABSTAIN | true | `LOW_CONFIDENCE` hoặc `EMPTY_RETRIEVAL` | `confidence_filter` | false | 0 |
| Model tự từ chối | ABSTAIN | true | `MODEL_ABSTAINED` | `model` | false | 1 |
| Model yêu cầu hỏi lại | NEEDS_CLARIFICATION | false | null | `model` | true | 1 |
| Gate chặn | FAIL | true | mã lỗi của Gate, ví dụ `ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES`, `ANSWER_NOT_VIETNAMESE` | `grounding_gate` | false | 1 |
| Router chặn (khi nối router) | ABSTAIN | true | mã của router | `router` | false | 0 |

Gate FAIL tính là từ chối vì người dùng chỉ nhận thông báo không kết luận. `abstention_reason` luôn là mã cố định; lý do model tự viết nằm ở `retrieval_trace.llm.abstention_reason` và không dùng để đếm.

| Chỉ số | Công thức |
| --- | --- |
| Tỷ lệ từ chối | số câu `abstained = true` / tổng số câu; báo thêm tỷ lệ tách theo `abstention_source` (`confidence_filter`, `model`, `grounding_gate`, `router`) |
| Tỷ lệ hỏi lại | số câu `needs_clarification = true` / tổng số câu |
| False-abstention | số câu có gold đủ căn cứ (câu thuộc Dev30 có `gold_clause_ids` không rỗng) mà `abstained = true` hoặc `needs_clarification = true` / số câu có gold đủ căn cứ |

Run A không có Gate nên không có tỷ lệ từ chối theo nguồn. Nếu cần so sánh, câu Run A được coi là từ chối khi người chấm rubric đánh dấu "từ chối/không kết luận"; ghi rõ đây là nhãn thủ công.

Khả năng từ chối đúng đo trên tập câu âm (`evaluation/negative_set/`), không đo trên Dev30.

## 5. Tỷ lệ câu trả lời không phải tiếng Việt

Chỉ số đề xuất thêm sau Run B 10/11 (HN_025, HN_062 trả lời tiếng Trung):

- Run A: số câu `cjk_chars > 0` / số câu có gọi model.
- Run B: số câu `retrieval_trace.llm.cjk_chars_before_gate > 0` / số câu có `llm_calls = 1`. Đo trước Gate để thấy model còn lỗi hay không; sau Gate, câu trả lời người dùng nhận phải có 0 ký tự CJK (Gate trả FAIL `ANSWER_NOT_VIETNAMESE`).

Ký tự CJK = các dải U+3000–U+303F, U+3040–U+30FF, U+3400–U+9FFF, U+F900–U+FAFF, U+AC00–U+D7AF, U+20000–U+2FA1F (`orchestration.rag_pipeline.count_cjk_chars`).

## 6. Điều kiện so sánh A/B công bằng

Run A và Run B chỉ được so sánh khi hai manifest có cùng `model`, `model_digest`, `temperature`, `repeat_penalty`, `num_predict`, `num_ctx` và cùng lấy `as_of_date` từ benchmark (`as_of_date_source = benchmark`). Khác bất kỳ giá trị nào thì báo cáo phải ghi rõ và không kết luận về hiệu ứng RAG.
