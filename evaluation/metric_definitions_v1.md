# Định nghĩa metric runtime và từ chối (DoD-13, v1)

Phiên bản: `metrics_runtime_v1` (2026-11-13). Áp dụng cho Run A (zero-shot) và Run B (Controlled RAG) từ lượt chạy sau review PR #45. Các metric chất lượng (Recall@5, MRR@5, Legal Correctness, Context Faithfulness, Citation Precision/Recall/Validity, Hallucination, Answer Relevance) giữ nguyên định nghĩa ở mục "5. Metrics thống nhất" của kế hoạch Sprint 9 và `evaluation/metrics.py`; tài liệu này không đổi chúng.

Hệ thống không stream câu trả lời trước Gate (LLM → buffer → Grounding Gate → SSE chỉ khi PASS), nên TTFT và cost được định nghĩa theo đúng cách hệ thống chạy, không theo cách đo của một chatbot stream.

## 1. Trường dữ liệu dùng để tính

> **Lưu ý về Run A:** cột Run A dưới đây mô tả record Run A khi Run A chạy qua Qwen Gateway, dùng cùng cấu hình với Run B. Code Run A hiện tại (`evaluation/zero_shot.py`) gọi thẳng `ollama.chat` với tham số riêng, nên chưa ghi các trường `latency_breakdown`, `token_usage`, `cjk_chars`, chưa có manifest và chưa thỏa điều kiện ở mục 6. Dev 2 cần cập nhật Run A trước khi tính metric A/B.

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

### 2.1 TTFT (Time To First Token)

Khi chạy chế độ non-streaming cục bộ qua Ollama (`stream=False`, tuân thủ nguyên tắc *Buffer-then-stream*: toàn bộ câu trả lời phải đi qua kiểm duyệt Grounding Gate trước khi phát ra giao diện), **TTFT phía người dùng (streaming TTFT) là `N/A`** (không áp dụng / không đo được); hệ thống báo cáo `latency_ms` theo p50/p95 và ghi rõ chế độ chạy (precomputed hay live, xem mục 2.2). Ngoài ra, ở tầng engine model, gateway ghi nhận thêm ước lượng `ttft_model_ms`:

| Loại | Trường / Giá trị | Ghi chú |
| --- | --- | --- |
| TTFT streaming (người dùng) | `N/A` (báo `latency_ms` thay thế) | Không áp dụng / không đo được khi chạy non-streaming qua Ollama (`stream=False`, *Buffer-then-stream*). Người dùng chỉ nhận câu trả lời sau khi Gate PASS. Khi chạy live, độ trễ người dùng cảm nhận là `latency_ms` (= `total_latency_ms`). Khi chạy precomputed, `latency_ms` không gồm retrieval và rerank, nên chỉ là cận dưới. |
| TTFT của model (tầng engine) | `latency_breakdown.ttft_model_ms` | Giá trị xấp xỉ (`load_ms + prompt_eval_ms`) từ bộ đếm nano giây của Ollama; dùng để tách thời gian nạp/đọc prompt khỏi thời gian sinh token. |

### 2.2 Phân biệt `latency_ms` và `total_latency_ms`

`orchestration/rag_pipeline.py` bắt đầu đo trước bước lấy candidate (`source.fetch`) và ghi `latency_ms` khi đã có record sau Gate. Phần retrieval trong `latency_ms` vì vậy tùy chế độ chạy:

| Chế độ | `latency_breakdown.retrieval_ms` | `latency_ms` gồm | `total_latency_ms` (đầu cuối) |
| --- | --- | --- | --- |
| `precomputed` (Run B chính thức) | `null` | Thời gian xử lý sau khi đã có retrieval artifact: đọc artifact, confidence filter, dựng context, gọi model, Gate. **Không gồm** retrieval và rerank, vì hai bước này đã chạy ở lần precompute trước. | Không đo được (N/A). Không lấy `latency_ms` thay cho `total_latency_ms`. |
| live (`LivePipelineSource`) | có giá trị (retrieval + rerank + parent context) | Toàn bộ một câu, **đã gồm** `retrieval_ms`. | Bằng `latency_ms`. **Không cộng thêm** `retrieval_ms`, vì như vậy sẽ tính retrieval hai lần. |

- `total_latency_ms` là tên dùng trong báo cáo, không phải trường trong record Run B.
- `total_latency_ms` cũng khác `stats.total_latency_ms` trong retrieval envelope (`docs/sprint6_integration.md`, `reranking/pipeline.py`): trường đó chỉ gồm retrieval + rerank, không gồm thời gian gọi model.
- Khi chạy live, báo cả `retrieval_ms` và phần còn lại (`latency_ms - retrieval_ms`) để thấy retrieval chiếm bao nhiêu.
- Báo cáo Run B chính thức dùng `latency_ms` và ghi cạnh con số: "precomputed, không gồm retrieval và rerank".

### 2.3 p50, p95 và câu khởi động nguội

- Báo p50 và p95 của `latency_ms`, `ttft_model_ms`, `eval_ms`, tách riêng Run A và Run B; ghi rõ chế độ chạy theo mục 2.2.
- **Chỉ tính trên các câu có gọi model (`llm_calls = 1`).**
  - Câu dừng ở confidence filter (`llm_calls = 0`) không gọi model nên `latency_ms` gần 0. Gộp vào sẽ kéo phân vị Run B xuống, trong khi ở Run A cả 30 câu đều gọi model.
  - Các câu này được báo riêng: số câu, `query_id`, `latency_ms`.
  - Có thể ghi thêm p50/p95 trên toàn bộ câu để tham chiếu, nhưng phải ghi rõ `n`.
  - Ví dụ: Run B v1.1 ngày 13/11 (`evaluation/results/dev/20261113_controlled_rag_qwen25_dev30_post_fix/`, máy Dev 3 RTX 4060, precomputed) có n = 29, p50 = 4 754,98 ms, p95 = 6 558,70 ms. HN_035 (`llm_calls = 0`) là 0,14 ms. Trên cả 30 câu: p50 = 4 698,81 ms, p95 = 6 552,61 ms. Lượt này không có câu khởi động nguội (`load_ms` lớn nhất 9,11 ms).
- Phân vị dùng nội suy tuyến tính (`numpy.percentile` mặc định). Luôn ghi rõ `n` cạnh kết quả.
- Câu khởi động nguội = câu có `load_ms > 1000`. Ollama nạp model lần đầu mất tới khoảng 12 giây (đo ngày 11/11), nên các câu này bị loại khỏi p50/p95 và báo riêng: số câu, `query_id`, `load_ms`. Báo cáo ghi rõ đã loại bao nhiêu câu.
- Run B có bước warm-up trong `scripts/run_rag_batch.py`; Run A không có, nên câu đầu tiên của Run A thường là câu khởi động nguội.

## 3. Cost/request

**Cost/request = `$0.00` (0 USD)** khi suy luận nội bộ bằng mô hình local Ollama (`qwen2.5:7b`) cho cả Run A và Run B. Thay cho chi phí USD, mỗi run báo cáo thêm chỉ số tài nguyên thực tế:

| Chỉ số | Công thức |
| --- | --- |
| Token input trung bình | trung bình `token_usage.input` trên các câu có `llm_calls = 1` |
| Token output trung bình | trung bình `token_usage.output` trên các câu có `llm_calls = 1` |
| Số lần gọi model | tổng `llm_calls` và trung bình `llm_calls` trên mọi câu (Run B < 1 nếu có câu dừng trước LLM) |
| Thời gian GPU/CPU sinh token | trung bình và p95 của `eval_ms` trên các câu có `llm_calls = 1` |

Chi phí API chỉ phát sinh và được ghi nhận khi kích hoạt Run C qua model API bên ngoài: `cost_usd = token_input × đơn giá input + token_output × đơn giá output`, ghi đơn giá và ngày lấy đơn giá trong manifest.

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
