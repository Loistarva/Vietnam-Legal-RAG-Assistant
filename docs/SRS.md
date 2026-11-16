# SRS — Vietnam Legal RAG Assistant (phân hệ Hôn nhân và Gia đình)

| Thuộc tính | Giá trị |
| --- | --- |
| Mã tài liệu | `VN-LEGAL-RAG-SRS` |
| Phiên bản | **2.1 — bản nháp chờ Tech Lead duyệt** |
| Thay thế | SRS 1.0. Giữ nghĩa của FR1–FR5 và NFR1–NFR3; thêm mã con và nhóm mới. |
| Kiến trúc tham chiếu | [`architecture/system_architecture.drawio`](../architecture/system_architecture.drawio). Phần Retrieval và Knowledge Base của sơ đồ là **chuẩn bắt buộc**; các phần khác là kiến trúc mục tiêu, được làm rõ trong tài liệu này. |
| Tài liệu liên quan | [BRD](BRD.md) · [Ma trận truy vết và trạng thái](requirements_traceability.md) · [data_contract.md](data_contract.md) · [metric_definitions_v1.md](../evaluation/metric_definitions_v1.md) |

## Lịch sử phiên bản

| Phiên bản | Ngày | Nội dung |
| --- | --- | --- |
| 1.0 | — | FR1–FR5, giao diện, NFR1–NFR3. |
| 2.1 | 16/11/2026 | Đặc tả toàn hệ thống theo sơ đồ kiến trúc; mỗi khối của sơ đồ có nhóm yêu cầu; mỗi yêu cầu có mã ổn định, tiêu chí chấp nhận, giai đoạn và cách kiểm chứng. Trạng thái triển khai tách sang ma trận truy vết. |

---

## 1. Giới thiệu

### 1.1. Mục đích

SRS là **nguồn yêu cầu duy nhất** của dự án. Code, test, kế hoạch sprint và báo cáo dẫn chiếu tới mã yêu cầu ở đây. Hành vi chưa có trong SRS phải được bổ sung vào SRS trước khi code (mục 10).

### 1.2. Phạm vi sản phẩm

Ứng dụng web hỏi đáp pháp luật Hôn nhân và Gia đình (HNGĐ) Việt Nam theo kiến trúc Agentic RAG. Hệ thống:

- phân loại câu hỏi, trả lời xã giao cho câu không phải pháp lý mà không gọi LLM;
- xác định ngày áp dụng pháp luật và chỉ dùng điều khoản có hiệu lực tại ngày đó;
- truy xuất lai BM25 + vector, xếp hạng lại, lọc theo độ tin cậy;
- hỏi lại khi thiếu dữ kiện, từ chối khi ngoài phạm vi hoặc không có căn cứ;
- sinh câu trả lời tiếng Việt có trích dẫn tới Điều/Khoản/Điểm, chỉ phát ra sau khi qua Grounding Gate;
- quản lý phiên hội thoại, cache, giới hạn truy cập, nhiều model với cơ chế dự phòng;
- nạp và cập nhật kho văn bản từ nguồn chính thức;
- đo và ghi lại chất lượng, độ trễ, chi phí.

**Ngoài phạm vi:** phân tích tài liệu hoặc hình ảnh cá nhân do người dùng tải lên; lĩnh vực pháp luật khác HNGĐ (bị từ chối); thay thế tư vấn của luật sư.

### 1.3. Quy ước

**Mã.** `FRn.m` chức năng · `IRn.m` giao diện · `NFRn.m` phi chức năng. Mã đã phát hành không đổi số, không dùng lại cho nghĩa khác; yêu cầu bị bỏ giữ mã với trạng thái `Dropped`.

**Câu yêu cầu.** "Hệ thống phải…" là bắt buộc; "nên" là khuyến nghị. Dạng sự kiện: *Khi …, hệ thống phải …*.

**Giai đoạn** (định nghĩa ở [BRD mục 5](BRD.md#5-phạm-vi-và-giai-đoạn)):

| Mã | Tên | Ý nghĩa |
| --- | --- | --- |
| GĐ1 | Lõi RAG có kiểm soát | Chứng minh bằng thực nghiệm A/B rằng RAG có kiểm duyệt tốt hơn model dùng một mình. |
| GĐ2 | Ứng dụng hoàn chỉnh | Người dùng hỏi qua Web/API; định tuyến, làm rõ, từ chối, log, bảo mật cơ bản. |
| GĐ3 | Vận hành mở rộng | Cache, giới hạn truy cập, phiên hội thoại, nhiều model và dự phòng, kiểm tra ngữ nghĩa, nạp văn bản tự động, ReactJS. |

Yêu cầu của giai đoạn sau không được làm hỏng yêu cầu đã đạt của giai đoạn trước.

**Trạng thái spec.** `Agreed` đã có trong SRS 1.0, sơ đồ kiến trúc hoặc kế hoạch đã thống nhất · `Proposed` mới hoặc thay đổi, chờ Tech Lead duyệt · `Dropped`. Trạng thái **triển khai** không ghi ở đây mà ở [ma trận truy vết](requirements_traceability.md).

**Kiểm chứng.** `T` test tự động · `A` artifact lượt chạy (kết quả + manifest) · `R` chấm hoặc duyệt thủ công · `I` kiểm tra tài liệu, cấu hình.

**Tham số.** Giá trị số (Top-K, ngưỡng, ngân sách ngữ cảnh, timeout…) nằm trong file cấu hình có phiên bản. SRS nêu giá trị theo sơ đồ hoặc giá trị mặc định; đổi giá trị không cần sửa SRS nhưng phải tăng phiên bản cấu hình (NFR4.3).

### 1.4. Thuật ngữ

| Thuật ngữ | Nghĩa |
| --- | --- |
| `as_of_date` | Ngày áp dụng pháp luật cho câu hỏi, `YYYY-MM-DD`. |
| Parent / child chunk | Parent: một Điều hoặc nhóm Khoản liên tiếp của một Điều (≤ 1.500 ký tự), dùng làm ngữ cảnh. Child: đoạn ≤ 256 token dùng để truy xuất. |
| Evidence | Mục ngữ cảnh đã đánh số `[1]..[n]` đưa vào prompt. |
| Grounding Gate | Bước kiểm duyệt bản nháp của LLM trước khi phát ra. |
| Run A / Run B | A: model trả lời không ngữ cảnh. B: RAG có kiểm duyệt. Cùng model và tham số sinh. |
| Dev Gold / Test | Câu hỏi có đáp án đã duyệt nguồn; Test là tập đóng băng, không dùng để chỉnh. |
| Tập câu âm | Câu hỏi không được phép trả lời bình thường: không phải pháp lý, ngoài phạm vi, kho không có nguồn, thiếu dữ kiện. |

---

## 2. Kiến trúc tổng thể

### 2.1. Phân hệ và khối chức năng

| Phân hệ | Khối trên sơ đồ | Nhóm yêu cầu |
| --- | --- | --- |
| Web UI | Chatbot Interface (ReactJS); Citations & Evidence Panel | IR1 |
| API | Fast API Gateway (SSE Streaming / WebSocket Controller); Security & API Key Guard; Rate Limiter (Redis); Semantic Query & Reranker Cache (Redis); Session & History Manager (PostgreSQL) | IR2, FR7, NFR2, NFR3 |
| Agent | Heuristic Fast-Path; General Chat Responder; SuperRouter (Intent Routing, HyDE Query Rewriting, Metadata Filters Extraction); Context Aggregator; Active Clarification (Fallback); Policy Abstention | FR1, FR2.1–FR2.3, FR3, FR4, FR5 |
| Retrieval | Metadata & Temporal Pre-filter; Sparse Search (BM25); Dense Vector Search (BGE-M3); Rank Fusion (RRF); Cross-Encoder Neural Reranker (bge-reranker-v2-m3); Confidence Threshold Filter (LLM Judge + MMR); Parent-Context Resolver | FR2, FR3, FR4.1 |
| LLM | Citation & Context Prompt Builder; Model Gateway (LiteLLM Proxy): OpenAI-Compatible Interface, Semantic Prompt & KV Cache (Redis), Model Router, Cascading Fallback Matrix & Retry, Exception Detector & User Notifier, SSE Streaming Proxy Controller; External Foundation Models (Primary, Fallback, Local Offline); Grounding Gate; Verified Grounded Answer + Citations Map | FR4, FR5, FR6 |
| Knowledge Base | Raw Data Sources; Vision-LLM Parser (Qwen 3 VL); Vietnamese NLP Pipeline (underthesea_mixed Tokenizer); Hierarchical Parent-child Chunking; Elasticsearch Index; Vector DB (Qdrant) | FR8 |
| Evaluation & Logging | Citation Accuracy; Grounding & Faithfulness Rate; Latency & Token Cost Metrics; Recall@5 & MRR | FR9 |

### 2.2. Luồng dữ liệu (theo các cạnh của sơ đồ)

**Truy vấn**

```text
Chatbot UI ──HTTP / SSE──► FastAPI Gateway ──► API Key Guard ──► Rate Limiter ──► Session & History Manager
     ▲                         │  └─ Semantic Query & Reranker Cache (hit → trả kết quả đã kiểm duyệt)
     │                         ▼
     │                  Validated Query Payload ──► Heuristic Fast-Path
     │                         ├─ Non-legal ──► General Chat Responder ──On-hand answer──► Gateway
     │                         └─ Legal ──► SuperRouter (Intent Routing · HyDE · Metadata Filters Extraction)
     │                                        └─ Filter + Rewritten Query ──► Metadata & Temporal Pre-filter
     │                                              ├─► BM25 (Elasticsearch) ─┐
     │                                              └─► Dense BGE-M3 (Qdrant) ┴─► RRF ──Top-50 fused──► Cross-Encoder
     │                                                                              ──Top-10──► Confidence Filter (LLM Judge + MMR)
     │                     Active Clarification ◄──Low confidence / rỗng──────────────────────────┤
     │                     └─Clarifying Question──► Gateway                          Passed chunks ▼
     │                                                     Parent-Context Resolver ──Grounded Parent Context──► Context Aggregator
     │                                                     ──Consolidated Context Payload──► Citation & Context Prompt Builder
     │                                                     ──Prompt Request──► Model Gateway (LiteLLM)
     │                                                          OpenAI-compatible ─► Prompt & KV Cache ─(miss)─► Model Router
     │                                                          ─► Primary ─(fail)─► Cascading Fallback & Retry ─► Fallback / Local
     │                                                          └─(all failed)─► Exception Detector ──Outage Alert──► Gateway
     │                                                          Model ──Stream Tokens──► SSE Streaming Proxy ──Forward Stream──► Grounding Gate
     │                                                                         ├─ Grounded ──► Verified Answer + Citations Map ──Answer──► Gateway
     │                                                                         │                └─Citation Mapping Data──► Evidence Panel
     │                                                                         └─ Ungrounded ──► Policy Abstention ──Refusal──► Gateway
     └──────────────────────────────────── Gateway ──► UI
```

**Nạp kho văn bản**

```text
Raw Data Sources ─► Vision-LLM Parser (Qwen 3 VL) ─► Vietnamese NLP Pipeline (underthesea_mixed)
   ──Processed Text──► Hierarchical Parent-child Chunking ─┬─Vector Embeddings──► Qdrant
                                                           └─Text Indexing──────► Elasticsearch
```

**Đo lường:** Retrieval → Recall@5 & MRR · Grounding Gate → Grounding & Faithfulness Rate · Verified Answer → Citation Accuracy · Model Gateway → Latency & Token Cost.

Hai nguyên tắc chi phối toàn luồng:

1. **Không có câu trả lời nào tới người dùng mà chưa qua Grounding Gate.** Token của model đi vào Gate (SSE Streaming Proxy → Gate), không đi thẳng tới UI. Kết quả lấy từ cache cũng phải là kết quả đã qua Gate.
2. **Ngày áp dụng là một phần của câu hỏi.** Mọi bộ lọc, khóa cache và log đều mang `as_of_date`.

---

## 3. Yêu cầu chức năng

Cột: **Mã · Yêu cầu · Khối sơ đồ · GĐ · Trạng thái · KC.** Tiêu chí chấp nhận (AC) viết dạng *Given/When/Then* ngay sau bảng.

### FR1. Định tuyến ý định — Heuristic Fast-Path, General Chat Responder, SuperRouter

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR1.1 | Hệ thống phải phân loại mọi câu hỏi hợp lệ là **không phải pháp lý** hoặc **pháp lý** bằng luật heuristic, không gọi LLM. | Heuristic Fast-Path | GĐ2 | Agreed (1.0 FR1) | T |
| FR1.2 | Khi câu hỏi không phải pháp lý, hệ thống phải trả lời bằng kịch bản tĩnh, bỏ qua Retrieval và LLM, không đưa kết luận pháp lý. | General Chat Responder | GĐ2 | Agreed (1.0 FR1) | T |
| FR1.3 | Với câu hỏi pháp lý, SuperRouter phải xác định ý định và phạm vi: thuộc HNGĐ, ngoài HNGĐ, lẫn cả hai, hoặc chưa chắc chắn; kết quả là một giá trị `route` (mục 5.3) kèm `route_reason`. | SuperRouter / Intent Routing | GĐ2 | Agreed | T |
| FR1.4 | Khi câu hỏi thuộc lĩnh vực pháp luật khác HNGĐ, hoặc lẫn nội dung ngoài phạm vi không tách được, hệ thống phải từ chối theo policy và nêu rõ phạm vi hỗ trợ, không chạy truy xuất. | Intent Routing → Policy Abstention | GĐ2 | Agreed | T |
| FR1.5 | Khi phạm vi chưa chắc chắn, hệ thống phải tiếp tục truy xuất và để Confidence Filter quyết định (FR3). | Intent Routing | GĐ2 | Proposed | T |
| FR1.6 | Heuristic non-legal không được ghi đè tín hiệu pháp lý: câu có cả lời chào và câu hỏi pháp lý phải đi nhánh pháp lý. | Heuristic Fast-Path | GĐ2 | Agreed | T |
| FR1.7 | Câu hỏi rỗng, chỉ có khoảng trắng hoặc vượt độ dài tối đa phải bị từ chối với `INVALID_REQUEST` trước mọi stage. | Session & History Manager (Validated Query Payload) | GĐ1 | Agreed | T |
| FR1.8 | Bộ luật định tuyến phải được đo trên một tập holdout độc lập, không dùng để chỉnh luật. | — | GĐ2 | Agreed | A |

- **FR1.2-AC1** Given "Xin chào", Then `route = NON_LEGAL`, `status = SUCCESS`, `grounding_status = NOT_RUN`, không gọi LLM, có disclaimer.
- **FR1.4-AC1** Given toàn bộ câu "ngoài phạm vi" của tập câu âm, Then mỗi câu có `status = ABSTAIN`, `reason_code = ROUTE_POLICY`, không gọi LLM.
- **FR1.6-AC1** Given "Chào bạn, cho hỏi tuổi kết hôn của nữ là bao nhiêu?", Then `route = LEGAL_HNGD`.

### FR2. Lọc trước và truy xuất lai — SuperRouter, Metadata & Temporal Pre-filter, BM25, Dense, RRF, Cross-Encoder, Cache

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR2.1 | Hệ thống phải xác định `as_of_date` và ghi `as_of_date_source`: đánh giá benchmark dùng ngày của câu trong benchmark (`benchmark`); tương tác theo thứ tự ngày nêu trong câu hỏi (`query_text`) → ngày người dùng chọn (`user_input`) → hôm nay (`system_today`). Câu chỉ nêu năm: năm đã qua lấy 31/12, năm hiện tại lấy hôm nay, năm tương lai lấy 01/01. | Metadata Filters Extraction | GĐ1 | Agreed (1.0 FR2) | T |
| FR2.2 | Hệ thống phải trích thêm bộ lọc metadata từ câu hỏi khi có: số hiệu văn bản, loại văn bản, cơ quan ban hành, năm ban hành, số Điều. Bộ lọc chỉ thu hẹp kết quả; không tìm thấy gì với bộ lọc thì bỏ bộ lọc metadata (không bỏ bộ lọc hiệu lực) và ghi lại. | Metadata Filters Extraction | GĐ3 | Agreed (1.0 FR2) | T |
| FR2.3 | Hệ thống nên tạo câu truy vấn viết lại (HyDE) để tăng độ phủ. Câu viết lại chỉ dùng cho truy xuất; prompt và Gate dùng câu gốc; câu viết lại được ghi log. | HyDE Query Rewriting | GĐ3 | Agreed (sơ đồ) | T, A |
| FR2.4 | Hệ thống phải chỉ trả về chunk có hiệu lực tại `as_of_date` theo khoảng nửa mở `effective_from ≤ as_of_date < effective_to` (`effective_to` rỗng = chưa hết hiệu lực). Khoảng hiệu lực cấp Điều/Khoản/Điểm ưu tiên hơn cấp văn bản. Lọc **trước** khi lấy Top-K, cùng một ngữ nghĩa ở mọi nhánh. | Metadata & Temporal Pre-filter | GĐ1 | Agreed (1.0 FR2; NFR1) | T, A |
| FR2.5 | Nhánh sparse phải tìm BM25 trên Elasticsearch, trên văn bản đã tách từ tiếng Việt, có trọng số cho breadcrumb. | Sparse Search (BM25) | GĐ1 | Agreed | T |
| FR2.6 | Nhánh dense phải tìm vector BGE-M3 trên Qdrant. Khi mở collection, hệ thống phải đối chiếu tên model, số chiều và hash corpus; lệch thì dừng. | Dense Vector Search (BGE-M3) | GĐ1 | Agreed | T |
| FR2.7 | Hai nhánh chạy với cùng bộ lọc và được hợp nhất bằng RRF, cho ra **Top-50** ứng viên. | Rank Fusion (RRF) | GĐ1 | Agreed (sơ đồ) | T |
| FR2.8 | Cross-Encoder `bge-reranker-v2-m3` phải chấm lại Top-50 trên chuỗi (tên văn bản + breadcrumb + nội dung) và chuyển **Top-10** sang Confidence Filter. | Cross-Encoder Neural Reranker | GĐ1 | Agreed (sơ đồ; D-04) | T |
| FR2.9 | Khi bật cache, hệ thống phải lưu kết quả truy xuất/rerank và câu trả lời đã qua Gate. Khóa cache phải gồm câu hỏi chuẩn hóa, `as_of_date`, hash corpus, phiên bản cấu hình retrieval, prompt, model và ngưỡng. Cache hit theo ngữ nghĩa phải có ngưỡng tương đồng và không áp dụng khi `as_of_date` khác. | Semantic Query & Reranker Cache | GĐ3 | Agreed (sơ đồ; 1.0 NFR2) | T |
| FR2.10 | Chế độ hai bước (truy xuất tính trước, sinh sau) phải dừng nếu artifact không khớp corpus, cấu hình hoặc `as_of_date` của từng câu. | — | GĐ1 | Agreed | T |
| FR2.11 | Mỗi kết quả phải mang `retrieval_trace`: ứng viên (id, điểm từng nhánh, hạng, nguồn), bộ lọc đã áp dụng, `corpus_version`, `retrieval_config_version`. | — | GĐ1 | Agreed | T |

- **FR2.1-AC1** Given "Năm 2010 kết hôn…", không chọn ngày, Then `as_of_date = 2010-12-31`, `as_of_date_source = query_text`.
- **FR2.4-AC1** Given `as_of_date = 2010-01-01`, Then không ứng viên nào có `effective_from > 2010-01-01` hoặc `effective_to ≤ 2010-01-01`.
- **FR2.9-AC1** Given cùng câu hỏi với hai `as_of_date` khác nhau, Then không có cache hit chéo.

### FR3. Ngưỡng tin cậy và làm rõ — Confidence Threshold Filter (LLM Judge + MMR), Active Clarification

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR3.1 | Confidence Filter phải loại ứng viên có điểm dưới ngưỡng bằng chứng và quyết định "đủ tin cậy" dựa trên điểm hạng 1 so với ngưỡng (GĐ1), cộng thêm đánh giá liên quan bằng LLM Judge (GĐ3). | Confidence Threshold Filter | GĐ1 / GĐ3 | Agreed (1.0 FR3; sơ đồ) | T |
| FR3.2 | Confidence Filter nên dùng MMR để chọn các ứng viên vừa liên quan vừa không trùng lặp; số ứng viên qua lọc (passed chunks) tối đa `max_evidence` (mặc định 5). | Confidence Threshold Filter | GĐ3 | Agreed (sơ đồ) | T, A |
| FR3.3 | Khi không có ứng viên hoặc không đủ tin cậy, hệ thống **không được** gọi model sinh câu trả lời; luồng chuyển sang Active Clarification. | Confidence Filter → Active Clarification | GĐ1 | Agreed (1.0 FR3; sơ đồ) | T |
| FR3.4 | Active Clarification phải chọn một trong hai: (a) câu hỏi thiếu dữ kiện có thể bổ sung → sinh câu hỏi làm rõ nêu cụ thể dữ kiện cần (`NEEDS_CLARIFICATION`); (b) kho không có căn cứ → từ chối an toàn (`ABSTAIN`). | Active Clarification (Fallback) | GĐ2 | Agreed (1.0 FR3) | T, R |
| FR3.5 | Khi người dùng trả lời câu hỏi làm rõ trong cùng phiên, hệ thống phải ghép với câu hỏi trước rồi chạy lại từ SuperRouter. Số vòng làm rõ tối đa có cấu hình (mặc định 2); quá số vòng thì từ chối. | Active Clarification + Session Manager | GĐ3 | Proposed | T |
| FR3.6 | Khi model tự báo cần làm rõ, hệ thống phải trả `NEEDS_CLARIFICATION`, không kèm kết luận pháp lý. | Grounding Gate | GĐ1 | Agreed | T |
| FR3.7 | Ngưỡng chỉ được đổi bằng phiên bản cấu hình mới, hiệu chỉnh trên Dev và tập câu âm, không dùng Test, kèm báo cáo quét ngưỡng. | — | GĐ1 | Agreed | I, A |

- **FR3.3-AC1** Given điểm hạng 1 dưới ngưỡng, Then không gọi model, `llm_calls = 0`.
- **FR3.4-AC1** Given "Tôi muốn ly hôn thì chia tài sản thế nào?" (không nêu tài sản chung/riêng, thời điểm), Then `status = NEEDS_CLARIFICATION` và câu làm rõ nêu ít nhất một dữ kiện cụ thể.

### FR4. Sinh câu trả lời có trích dẫn — Parent-Context Resolver, Context Aggregator, Citation & Context Prompt Builder

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR4.1 | Với mỗi chunk qua lọc, hệ thống phải khôi phục parent của nó (Điều hoặc nhóm Khoản của Điều). | Parent-Context Resolver | GĐ1 | Agreed (1.0 FR4) | T |
| FR4.2 | Context Aggregator phải gộp parent trùng, sắp theo thứ tự cuối cùng, giữ trong ngân sách ngữ cảnh (mặc định 6.000 ký tự) và đánh số evidence liên tục `1..n`; mỗi số ánh xạ 1-1 sang `chunk_id`, `document_id`, `article_id`, `clause_id` trong `source_map`. | Context Aggregator | GĐ1 | Agreed | T |
| FR4.3 | Mỗi evidence phải mang nhãn đọc được: tên và số hiệu văn bản, breadcrumb (Chương > Điều > Khoản > Điểm), tình trạng hiệu lực tại `as_of_date`. | Context Aggregator | GĐ1 | Agreed | T |
| FR4.4 | Prompt phải: chỉ cho phép dùng evidence đã cấp; chỉ pháp luật Việt Nam; tiếng Việt; nêu `as_of_date`; yêu cầu từ chối khi không đủ căn cứ; yêu cầu đầu ra có cấu trúc `{answer, evidence_indices, abstained, abstention_reason, needs_clarification}`. | Citation & Context Prompt Builder | GĐ1 | Agreed | T |
| FR4.5 | Model chỉ trả số evidence; hệ thống tự ánh xạ sang trích dẫn. Model không được tự tạo `chunk_id` hay số hiệu văn bản cho trích dẫn. | Prompt Builder; Citations Map | GĐ1 | Agreed (1.0 FR4) | T |
| FR4.6 | Prompt có phiên bản; mọi thay đổi nội dung tăng phiên bản; mỗi kết quả ghi phiên bản và SHA-256 của prompt đã gửi. | Prompt Builder | GĐ1 | Agreed | T, A |
| FR4.7 | Trích dẫn hiển thị phải có số hiệu văn bản, Điều, Khoản, Điểm (nếu có) và hiệu lực, lấy từ metadata kho. | Verified Answer + Citations Map | GĐ1 | Agreed (1.0 FR4) | T |

### FR5. Grounding Gate và từ chối — Grounding Gate, Verified Grounded Answer + Citations Map, Policy Abstention

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR5.1 | Toàn bộ đầu ra của model (kể cả dạng stream) phải đi vào Gate. Không phần nào của bản nháp được gửi tới người dùng trước khi Gate kết luận. | SSE Streaming Proxy → Grounding Gate | GĐ1 | Agreed (1.0 FR5; sơ đồ) | T |
| FR5.2 | **Kiểm tra cấu trúc.** Gate chỉ kết luận *Grounded* khi: đầu ra parse được và không bị cắt; chỉ số evidence hợp lệ, nằm trong ngữ cảnh và khớp metadata nguồn; mọi ký hiệu `[k]` trong câu trả lời đã khai báo; câu trả lời không rỗng, không chứa `chunk_id`, không có ký tự CJK; model không tự từ chối. | Grounding Gate | GĐ1 | Agreed | T |
| FR5.3 | **Kiểm tra ngữ nghĩa.** Gate nên kiểm tra từng khẳng định pháp lý có được evidence hỗ trợ (NLI hoặc LLM Judge) trước khi kết luận *Grounded*. Bộ kiểm tra phải được đánh giá trên tập có nhãn trước khi bật. | Grounding Gate | GĐ3 | Agreed (1.0 FR5) | T, R |
| FR5.4 | Khi *Grounded*, hệ thống phải tạo Verified Answer kèm Citations Map và gửi Citation Mapping Data cho Evidence Panel. | Verified Grounded Answer + Citations Map | GĐ1 | Agreed (sơ đồ) | T |
| FR5.5 | Khi *Ungrounded*, Policy Abstention phải trả thông báo từ chối cố định (không phải nội dung model) và mã lý do có thể đếm. | Policy Abstention | GĐ1 | Agreed (1.0 FR5; sơ đồ) | T |
| FR5.6 | Với vi phạm có thể sửa (đầu ra bị cắt, ký hiệu chưa khai báo), hệ thống có thể sinh lại **tối đa một lần**; lần sinh lại không được bỏ bộ lọc hiệu lực. Mặc định tắt trong đánh giá official. | Grounding Gate | GĐ2 | Proposed (thay "Bump Retry" 1.0; D-06) | T |
| FR5.7 | Khi kết quả không phải SUCCESS, các trường `abstained`, `abstention_reason`, `abstention_source` không được rỗng; `abstention_source` ∈ {`router`, `confidence_filter`, `clarification`, `model`, `grounding_gate`}. | Policy Abstention | GĐ1 | Agreed | T |
| FR5.8 | Mọi phản hồi tới người dùng, ở mọi nhánh, phải có câu khuyến cáo cố định (BRD BR-05). | Gateway | GĐ1 | Agreed | T |

- **FR5.2-AC1** Given model trích `[7]` khi chỉ có 5 evidence, Then Ungrounded, người dùng nhận thông báo từ chối, không thấy nội dung model.
- **FR5.2-AC2** Given câu trả lời chứa ký tự Hán, Then Ungrounded với lý do `ANSWER_NOT_VIETNAMESE`.

### FR6. Model Gateway — LiteLLM Proxy, Prompt & KV Cache, Model Router, Fallback, Exception Notifier, SSE Proxy

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR6.1 | Mọi lời gọi model phải đi qua một gateway có giao diện tương thích OpenAI; module khác không gọi trực tiếp provider. | OpenAI-Compatible Interface | GĐ1 (một provider) / GĐ3 | Agreed (sơ đồ) | T |
| FR6.2 | Model, tham số sinh (temperature, độ dài tối đa, ngữ cảnh tối đa, repeat penalty), timeout và số lần thử lại nằm trong cấu hình có phiên bản. | Model Router | GĐ1 | Agreed | I, T |
| FR6.3 | Model Router phải chọn model theo thứ tự: Primary → Fallback → Local Offline, theo ma trận dự phòng có cấu hình. Thử lại có giới hạn số lần và thời gian. | Model Router; Cascading Fallback Matrix & Retry | GĐ3 | Agreed (sơ đồ) | T |
| FR6.4 | Khi tất cả model thất bại, hệ thống phải trả `status = ERROR`, `error.code = LLM_UNAVAILABLE`, phát sự kiện cảnh báo cho Gateway và ghi log; không trả câu trả lời từ nguồn khác. | Exception Detector & User Notifier | GĐ2 | Agreed (sơ đồ) | T |
| FR6.5 | Khi bật cache prompt, cache hit phải đi tiếp qua Grounding Gate như đầu ra mới; khóa cache gồm SHA-256 prompt, model và tham số sinh. | Semantic Prompt & KV Cache | GĐ3 | Agreed (sơ đồ) | T |
| FR6.6 | Gateway phải ghi cho mỗi lời gọi: model thực sự đã dùng, digest/phiên bản, tham số, `done_reason`, đã bị cắt hay chưa, token vào/ra, các mốc thời gian (tải model, xử lý prompt, sinh), chi phí ước tính. Giá trị runtime không trả về thì để rỗng, không tự điền 0. | Model Gateway → Latency & Token Cost Metrics | GĐ1 | Agreed | T |
| FR6.7 | Trong đánh giá official, model và tham số phải cố định: tắt fallback, tắt cache. Dữ liệu chỉ được gửi tới provider bên ngoài khi đã che PII (NFR3.4) và được phê duyệt. | Model Router | GĐ1 | Agreed | A |
| FR6.8 | Hệ thống phải chạy được ở chế độ chỉ dùng model local, không cần mạng ra ngoài. | Local Offline Models | GĐ1 | Agreed | A |

### FR7. Phiên và lịch sử hội thoại — Session & History Manager

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR7.1 | Hệ thống phải gắn mỗi request với một `session_id` (do client gửi hoặc hệ thống tạo) và một `query_id` duy nhất. | Session & History Manager | GĐ2 | Agreed | T |
| FR7.2 | Hệ thống phải lưu mỗi lượt hỏi đáp của phiên: câu hỏi đã che PII, `as_of_date`, route, status, trích dẫn, phiên bản cấu hình, thời điểm. | Session & History Manager (PostgreSQL) | GĐ3 | Agreed (sơ đồ) | T |
| FR7.3 | Lịch sử phiên chỉ dùng để hiểu câu hỏi tiếp theo (làm rõ, tham chiếu "trường hợp trên"); không được dùng làm căn cứ pháp lý thay cho evidence. | SuperRouter | GĐ3 | Proposed | T |
| FR7.4 | Dữ liệu phiên có thời hạn lưu và quyền truy cập theo chính sách (NFR7). Người dùng có thể yêu cầu xóa phiên. | Session & History Manager | GĐ3 | Proposed | T, I |

### FR8. Knowledge Base — Raw Data Sources, Vision-LLM Parser, NLP Pipeline, Parent-child Chunking, Elasticsearch, Qdrant

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR8.1 | Mỗi văn bản trong kho phải có nguồn chính thức (CSDL VBQPPL, Công báo…) ghi URL hoặc mã nguồn, và một bản ghi trong danh mục phiên bản văn bản. | Raw Data Sources | GĐ1 | Agreed | I, T |
| FR8.2 | Văn bản dạng PDF hoặc ảnh quét phải được chuyển thành văn bản bằng Vision-LLM (Qwen 3 VL hoặc tương đương), sau đó làm sạch. Kết quả bóc tách được lưu lại để tái lập, không bóc tách lại khi trả lời câu hỏi. | Vision-LLM Parser | GĐ1 | Agreed (sơ đồ) | I, A |
| FR8.3 | Bộ phân tích phải nhận diện cấu trúc Phần/Chương/Mục/Điều/Khoản/Điểm và tạo breadcrumb. | Vision-LLM Parser → NLP Pipeline | GĐ1 | Agreed | T |
| FR8.4 | Pipeline NLP tiếng Việt phải giữ đồng thời văn bản gốc (cho embedding và trích dẫn) và văn bản đã tách từ bằng underthesea (cho BM25). Phiên bản tokenizer được khóa. | Vietnamese NLP Pipeline (underthesea_mixed) | GĐ1 | Agreed (sơ đồ) | T |
| FR8.5 | Chunking phân cấp: parent là Điều hoặc nhóm Khoản liên tiếp của một Điều (≤ 1.500 ký tự); child ≤ 256 token, không vượt ranh giới Khoản; nguyên văn được giữ. Định danh: `{document_id}_art_{n}`, `{article_id}_clause_{n}`, `{clause_id}_chunk_{k}`. | Hierarchical Parent-child Chunking | GĐ1 | Agreed | T |
| FR8.6 | Mỗi chunk phải có metadata: số hiệu, loại văn bản, cơ quan ban hành, ngày ban hành, `effective_from`, `effective_to`, `validity_status`, trạng thái cấp điều khoản (bị bãi bỏ, sửa đổi), tham chiếu Điều/Khoản/Điểm. | Chunking | GĐ1 | Agreed | T |
| FR8.7 | Khi một điều khoản bị sửa đổi, bãi bỏ hoặc thay thế, kho phải ghi khoảng hiệu lực riêng cho điều khoản đó và liên kết tới văn bản sửa đổi/thay thế. | Raw Data Sources; Chunking | GĐ1 | Agreed | T |
| FR8.8 | Child chunk phải được đánh chỉ mục vào Elasticsearch (văn bản đã tách từ) và Qdrant (vector), mỗi chỉ mục ghi hash corpus, tên model, số chiều. | Elasticsearch Index; Vector DB | GĐ1 | Agreed (sơ đồ) | T |
| FR8.9 | Kho có phiên bản: định danh bằng SHA-256 của file chunk (chuẩn hóa xuống dòng). Mỗi lần thêm hoặc sửa văn bản phải tạo phiên bản mới, đánh chỉ mục lại, xóa cache liên quan, chạy lại bộ kiểm tra hồi quy. | Knowledge Base | GĐ1 (thủ công) / GĐ3 (tự động) | Agreed | T, A |
| FR8.10 | Quản trị viên phải cập nhật được văn bản và metadata hiệu lực qua quy trình có kiểm duyệt; người duyệt pháp lý xác nhận trước khi phiên bản mới được dùng. | Knowledge Base | GĐ3 | Agreed (1.0 §2.2) | R |

### FR9. Đánh giá và giám sát — Evaluation & Logging

| Mã | Yêu cầu | Khối | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| FR9.1 | Hệ thống phải đo Recall@5 và MRR cho truy xuất, ghi rõ stage (sau RRF/sau rerank) và đơn vị (chunk/parent). | Recall@5 & MRR | GĐ1 | Agreed (sơ đồ) | A |
| FR9.2 | Hệ thống phải đo Citation Accuracy: Citation Precision, Citation Recall theo Gold, Citation Validity trước Gate. | Citation Accuracy | GĐ1 | Agreed (sơ đồ) | A |
| FR9.3 | Hệ thống phải đo Grounding & Faithfulness Rate: tỷ lệ Grounded/Ungrounded của Gate và Context Faithfulness chấm theo rubric. | Grounding & Faithfulness Rate | GĐ1 | Agreed (sơ đồ) | A, R |
| FR9.4 | Hệ thống phải đo latency (p50/p95 theo stage, thời gian tới byte đầu tiên, thời gian tới câu trả lời đã kiểm duyệt), token và chi phí cho mỗi câu hỏi. | Latency & Token Cost Metrics | GĐ1 | Agreed (sơ đồ) | A |
| FR9.5 | Ngoài bốn nhóm trên, đánh giá chất lượng phải có Legal Correctness, Hallucination Rate, Answer Relevance, tỷ lệ từ chối, từ chối nhầm, tỷ lệ làm rõ; định nghĩa theo `evaluation/metric_definitions_v1.md`. | Evaluation | GĐ1 | Agreed | I |
| FR9.6 | Đánh giá A/B phải dùng cùng tập câu hỏi, cùng model và tham số sinh; chấm mù (ẩn nhãn, trộn thứ tự), hai người chấm độc lập, báo độ đồng thuận (Weighted Cohen's Kappa) và khoảng tin cậy. | Evaluation | GĐ1 | Agreed | R, A |
| FR9.7 | Tập Test phải đóng băng bằng hash và không dùng để chỉnh tham số; kiểm tra rò rỉ chạy trong CI. | Evaluation | GĐ1 | Agreed | T |
| FR9.8 | Chạy lô phải ghi kết quả từng câu, lỗi, và manifest (NFR4.2) vào thư mục mới; hỗ trợ chạy tiếp; không ghi đè kết quả cũ. | Evaluation | GĐ1 | Agreed | T |
| FR9.9 | Mỗi request phải sinh chuỗi log có cấu trúc (JSONL) theo `query_id`, mỗi stage một sự kiện (mục 5.4): route, phiên bản prompt/model/cấu hình, hash corpus, latency, trích dẫn, kết quả Gate, mã lỗi. | Evaluation & Logging | GĐ2 | Agreed (1.0 §2.1) | T |
| FR9.10 | Lỗi của logger không được làm thay đổi hoặc chặn câu trả lời. | Evaluation & Logging | GĐ2 | Agreed | T |
| FR9.11 | Hệ thống nên có dashboard theo dõi các chỉ số FR9.1–FR9.5 theo phiên bản cấu hình. | Evaluation & Logging | GĐ3 | Proposed | I |

---

## 4. Yêu cầu giao diện

### IR1. Web UI — Chatbot Interface, Citations & Evidence Panel

| Mã | Yêu cầu | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- |
| IR1.1 | Ô nhập câu hỏi hỗ trợ Enter để gửi; hiển thị lịch sử hội thoại của phiên. | GĐ2 | Agreed (1.0 §4.1) | T |
| IR1.2 | Bộ chọn ngày tra cứu; khi người dùng không chọn, hiển thị ngày hệ thống đã áp dụng và lý do (lấy từ câu hỏi hay hôm nay). | GĐ2 | Agreed | T |
| IR1.3 | Hiển thị theo `status`: câu trả lời, câu hỏi làm rõ, thông báo từ chối hoặc lỗi. Hiển thị trạng thái xử lý trong lúc chờ (từ sự kiện SSE). | GĐ2 | Agreed | T |
| IR1.4 | Citations & Evidence Panel (cột bên hoặc accordion): với mỗi trích dẫn hiển thị tên, số hiệu văn bản, Điều/Khoản/Điểm, nguyên văn evidence, hiệu lực tại `as_of_date`; bấm ký hiệu `[k]` trong câu trả lời thì mở evidence tương ứng. | GĐ2 | Agreed (1.0 §4.1; sơ đồ) | T |
| IR1.5 | Luôn hiển thị câu khuyến cáo. | GĐ2 | Agreed | T |
| IR1.6 | UI chỉ gọi API; không truy cập trực tiếp cơ sở dữ liệu, Qdrant, Elasticsearch hoặc model. | GĐ2 | Agreed | I |
| IR1.7 | Giao diện production dùng ReactJS theo sơ đồ; bản prototype có thể dùng framework khác nếu giữ nguyên contract API. | GĐ2 prototype / GĐ3 ReactJS | Agreed | I |

### IR2. API — Fast API Gateway, SSE/WebSocket, API Key Guard

| Mã | Yêu cầu | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- |
| IR2.1 | `POST /api/v1/ask` nhận `AskRequest`, trả `AskResponse` (mục 5.3). | GĐ2 | Agreed | T |
| IR2.2 | Mọi endpoint trừ health yêu cầu header `X-API-Key`; thiếu hoặc sai → HTTP 401 `AUTH_REQUIRED`. | GĐ2 | Agreed (1.0 NFR3) | T |
| IR2.3 | Có `GET /api/v1/health` (không gọi model) và tài liệu OpenAPI (`/docs`, `/openapi.json`). | GĐ2 | Agreed | T |
| IR2.4 | Stream qua SSE (`text/event-stream`): event `status` cho từng stage; event `final` chứa `AskResponse` sau Gate; event `error` khi lỗi hoặc outage. Nội dung câu trả lời chỉ có trong `final` (FR5.1). WebSocket là phương án thay thế với cùng loại event. | GĐ2 (SSE) / GĐ3 (WebSocket) | Agreed (1.0 §4.2; sơ đồ) | T |
| IR2.5 | Ánh xạ trạng thái sang HTTP theo mục 5.3.4; không trả prompt thô hay secret. | GĐ2 | Agreed | T |

### IR3. Giao diện dòng lệnh

| Mã | Yêu cầu | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- |
| IR3.1 | CLI hỏi một câu, tùy chọn ngày tra cứu; in route, status, câu trả lời, trích dẫn, evidence, kết quả Gate, khuyến cáo; exit code 0 SUCCESS, 3 ABSTAIN/NEEDS_CLARIFICATION, 1 ERROR, 2 sai cú pháp. | GĐ2 | Proposed | T |
| IR3.2 | CLI chạy lô cho đánh giá (FR9.8). | GĐ1 | Agreed | T |

### IR4. Giao tiếp nội bộ

| Mã | Yêu cầu | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- |
| IR4.1 | Các phân hệ giao tiếp qua interface công khai (mục 5.5) với dữ liệu theo contract (mục 5.2). Triển khai có thể là gọi hàm trong một tiến trình hoặc REST/gRPC giữa các dịch vụ; đổi cách triển khai không đổi contract. | GĐ1 | Agreed (1.0 §4.2) | I |

---

## 5. Dữ liệu và contract

### 5.1. Dữ liệu của hệ thống

| Dữ liệu | Nơi lưu | Ghi chú |
| --- | --- | --- |
| Danh mục văn bản và phiên bản | `data/reference/document_versions.json` | FR8.1 |
| Khoảng hiệu lực cấp điều khoản | `data/reference/provision_periods.json` | FR8.7 |
| Parent, child chunk | `data/chunking_output/parents.json`, `chunks.jsonl` | FR8.5–FR8.6 |
| Chỉ mục | Elasticsearch, Qdrant | FR8.8 |
| Cache | Redis | FR2.9, FR6.5, NFR3.2 |
| Phiên, lịch sử | PostgreSQL | FR7 |
| Log | JSONL | FR9.9 |
| Benchmark, Gold, tập câu âm, kết quả đánh giá | `data/benchmark/`, `evaluation/` | FR9 |

### 5.2. Nguồn sự thật của contract

`schemas/models.py` (Pydantic) là nguồn duy nhất; JSON Schema trong `schemas/` được sinh tự động, không sửa tay. Thay đổi phá vỡ tương thích phải tăng `schema_version`, cập nhật ví dụ và test. Contract gồm: `AskRequest`, `AskResponse`, `RouteDecision`, `RetrievalBundle`, `CandidateChunk`, `EvidenceItem`, `ContextPayload`, `LLMResponse`, `GroundingResult`, `LogEvent`, bản ghi kết quả chạy lô.

### 5.3. Contract API (Proposed — D-01, D-02, D-03)

#### 5.3.1. `AskRequest`

| Trường | Kiểu | Bắt buộc | Ràng buộc |
| --- | --- | --- | --- |
| `query` | string | có | Sau khi bỏ khoảng trắng: 1–2.000 ký tự. |
| `as_of_date` | `YYYY-MM-DD` | không | Ngày người dùng chọn. |
| `session_id` | string | không | Hệ thống tạo nếu không có. |
| `request_id` | string | không | Dùng làm `query_id` nếu có. |

Request công khai không có tham số model, Top-K hay chế độ chạy; các giá trị này lấy từ cấu hình.

#### 5.3.2. `AskResponse`

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `schema_version`, `query_id`, `session_id` | string | |
| `status` | `SUCCESS` · `NEEDS_CLARIFICATION` · `ABSTAIN` · `ERROR` | Client dựa vào trường này. |
| `route` | enum 5.3.3 \| null | |
| `as_of_date`, `as_of_date_source` | string | FR2.1 |
| `answer` | string \| null | Chỉ khi SUCCESS; không chứa câu khuyến cáo. |
| `clarification` | string \| null | Chỉ khi NEEDS_CLARIFICATION. |
| `message` | string \| null | Thông báo từ chối khi ABSTAIN. |
| `citations[]` | `{evidence_index, document_id, document_number, article_id, clause_id, point_ref, label}` | FR4.7 |
| `evidence[]` | `{evidence_index, document_title, document_number, breadcrumb, content, validity_status, effective_from, effective_to}` | IR1.4 |
| `grounding_status` | `PASS` · `FAIL` · `ABSTAIN` · `NEEDS_CLARIFICATION` · `NOT_RUN` | `NOT_RUN` khi không gọi model. |
| `reason_code` | string \| null | 5.3.4 |
| `disclaimer` | string | Luôn có. |
| `timings` | `{total_ms, first_status_ms, retrieval_ms, llm_ms, gate_ms}` | Stage không chạy = null. |
| `versions` | `{prompt_version, model, corpus_version, retrieval_config_version, threshold_config_version}` | |
| `cache` | `{hit: bool, layer}` \| null | FR2.9, FR6.5 |
| `error` | `{code, message}` \| null | Chỉ khi ERROR. |

#### 5.3.3. `route`

`LEGAL_HNGD` · `LEGAL_SCOPE_UNCERTAIN` · `LEGAL_OUT_OF_SCOPE` · `MIXED_LEGAL_SCOPE` · `NON_LEGAL` (trùng enum `Route` của `agent/router/rule_router.py`).

#### 5.3.4. Mã lý do, mã lỗi, HTTP

| Nhánh | `status` | `grounding_status` | `reason_code` / `error.code` | HTTP |
| --- | --- | --- | --- | --- |
| Grounded | SUCCESS | PASS | — | 200 |
| Không phải pháp lý | SUCCESS | NOT_RUN | — | 200 |
| Ngoài phạm vi / lẫn phạm vi | ABSTAIN | NOT_RUN | `ROUTE_POLICY` | 200 |
| Không có ứng viên | ABSTAIN hoặc NEEDS_CLARIFICATION (FR3.4) | NOT_RUN | `RETRIEVAL_EMPTY` | 200 |
| Dưới ngưỡng tin cậy | ABSTAIN hoặc NEEDS_CLARIFICATION (FR3.4) | NOT_RUN | `LOW_CONFIDENCE` | 200 |
| Model từ chối | ABSTAIN | ABSTAIN | `MODEL_ABSTAINED` | 200 |
| Model xin làm rõ | NEEDS_CLARIFICATION | NEEDS_CLARIFICATION | `MODEL_NEEDS_CLARIFICATION` | 200 |
| Đầu ra lỗi / bị cắt | ABSTAIN | FAIL | `JSON_INVALID` | 200 |
| Trích dẫn sai | ABSTAIN | FAIL | `CITATION_INVALID` | 200 |
| Vi phạm Gate khác | ABSTAIN | FAIL | `GROUNDING_FAIL` | 200 |
| Thiếu / sai API key | ERROR | — | `AUTH_REQUIRED` | 401 |
| Request không hợp lệ | ERROR | — | `INVALID_REQUEST` | 422 |
| Vượt giới hạn truy cập | ERROR | — | `RATE_LIMITED` | 429 |
| Model quá thời gian | ERROR | — | `LLM_TIMEOUT` | 504 |
| Mọi model thất bại | ERROR | — | `LLM_UNAVAILABLE` | 503 |
| Lỗi khác | ERROR | — | `INTERNAL_ERROR` | 500 |

Mã chi tiết của Gate (ví dụ `CITATION_OUTSIDE_CONTEXT`, `ANSWER_NOT_VIETNAMESE`) nằm trong `retrieval_trace` và log; `reason_code` công khai là nhóm ở bảng trên.

### 5.4. `LogEvent`

`event_id`, `query_id`, `session_id`, `stage` ∈ {`api`, `session`, `router`, `retrieval`, `rerank`, `confidence`, `context`, `llm`, `citation`, `gate`, `response`}, `event_type`, `timestamp` (UTC), `status`, `duration_ms?`, `masked_metadata`.

### 5.5. Interface giữa phân hệ

| Producer → Consumer | Interface |
| --- | --- |
| Router → Orchestrator | `route(request) -> RouteDecision` |
| Retrieval → Orchestrator | `retrieve(request, as_of_date, filters) -> RetrievalBundle` |
| Orchestrator → Model Gateway | `generate(ContextPayload, PromptConfig) -> LLMResponse` |
| Validator → Gate | `validate(ContextPayload, LLMResponse) -> GroundingResult` |
| Mọi phân hệ → Logger | `emit(LogEvent)` |
| API → UI | HTTP JSON / SSE theo OpenAPI |
| Chạy lô → Evaluation | JSONL kết quả + manifest |

---

## 6. Yêu cầu phi chức năng

| Mã | Yêu cầu | GĐ | Trạng thái | KC |
| --- | --- | --- | --- | --- |
| **NFR1** | **Độ chính xác pháp lý** | | | |
| NFR1.1 | Hallucination Rate (rubric riêng, chấm mù) phải thấp hơn model dùng một mình và tiến tới 0; mục tiêu số ở BRD. | GĐ1 | Agreed (1.0 NFR1, diễn đạt lại) | R, A |
| NFR1.2 | Không evidence nào được dùng nếu không có hiệu lực tại `as_of_date` (Temporal Violation Rate = 0). Thay cho "chỉ dùng văn bản Còn hiệu lực" của 1.0 vì sự việc trong quá khứ cần văn bản đã hết hiệu lực. | GĐ1 | Agreed | T, A |
| NFR1.3 | Câu trả lời bằng tiếng Việt; tỷ lệ câu có ký tự CJK sau Gate = 0. | GĐ1 | Agreed | T, A |
| **NFR2** | **Hiệu năng** | | | |
| NFR2.1 | Byte đầu tiên (sự kiện trạng thái) tới client < 2 giây kể từ khi API nhận request. | GĐ2 | Agreed (1.0 NFR2, áp cho sự kiện trạng thái vì FR5.1) | A |
| NFR2.2 | Cache hit (FR2.9) trả kết quả < 200 ms. | GĐ3 | Agreed (1.0 NFR2) | A |
| NFR2.3 | Thời gian tới câu trả lời đã kiểm duyệt (p50, p95) được đo trên máy tham chiếu ghi trong manifest; ngưỡng ở BRD. So sánh latency chỉ hợp lệ khi cùng máy. | GĐ1 | Proposed (D-10) | A |
| **NFR3** | **Bảo mật và sẵn sàng** | | | |
| NFR3.1 | API Key Guard (IR2.2). | GĐ2 | Agreed (1.0 NFR3) | T |
| NFR3.2 | Rate limit bằng Redis theo IP và session, có cấu hình; vượt → 429 `RATE_LIMITED`. | GĐ3 | Agreed (1.0 NFR3) | T |
| NFR3.3 | Không lưu secret, API key, `.env`, file model trong Git; key đọc từ biến môi trường hoặc kho secret. | GĐ1 | Agreed | I, T |
| NFR3.4 | Che email, số điện thoại, số CMND/CCCD trước khi ghi log, lưu lịch sử hoặc gửi tới model bên ngoài. Quy tắc và giới hạn sai sót ghi trong chính sách log. | GĐ2 | Proposed (D-07) | T |
| NFR3.5 | Khi model chính lỗi, dịch vụ vẫn trả lời được qua model dự phòng (FR6.3); khi mọi model lỗi, người dùng nhận thông báo rõ ràng (FR6.4). | GĐ3 | Agreed (sơ đồ) | T |
| **NFR4** | **Tái lập** | | | |
| NFR4.1 | Lượt đánh giá official: temperature 0, tắt cache, khóa fallback, working tree sạch. | GĐ1 | Agreed | A |
| NFR4.2 | Manifest ghi tối thiểu: git branch, SHA, trạng thái working tree; hash benchmark, danh sách câu, corpus, cấu hình retrieval/rerank/model/ngưỡng; artifact tính trước; model, digest, phiên bản runtime, tham số sinh; phiên bản prompt; máy chạy; thời gian bắt đầu/kết thúc. | GĐ1 | Agreed | T |
| NFR4.3 | Mọi file cấu hình có phiên bản hoặc hash, được ghi vào kết quả. | GĐ1 | Agreed | T |
| **NFR5** | **Độ tin cậy** | | | |
| NFR5.1 | Sai chiều vector, thiếu tokenizer đúng phiên bản, thiếu khóa cấu hình, artifact không khớp → dừng với lỗi rõ ràng, không tự chọn mặc định. | GĐ1 | Agreed | T |
| NFR5.2 | Truy cập đồng thời vào chỉ mục vector phải an toàn (dùng Qdrant server khi có nhiều tiến trình). | GĐ2 | Agreed | I |
| **NFR6** | **Bảo trì và kiểm thử** | | | |
| NFR6.1 | CI chạy toàn bộ test trên mỗi push và PR. | GĐ1 | Agreed | T |
| NFR6.2 | Mỗi yêu cầu bắt buộc của giai đoạn hiện hành có ít nhất một test (`@pytest.mark.req("<mã>")`) hoặc artifact trong ma trận truy vết; CI kiểm tra marker trỏ tới mã có trong SRS. | GĐ2 | Proposed | T |
| NFR6.3 | Mỗi phân hệ test được độc lập bằng mock của interface (mục 5.5). | GĐ1 | Agreed | T |
| **NFR7** | **Quyền riêng tư và lưu trữ** | | | |
| NFR7.1 | Thời hạn lưu log và lịch sử phiên có cấu hình; hết hạn thì xóa. | GĐ3 | Proposed | T |
| NFR7.2 | Mặc định không ghi câu hỏi và prompt thô; chỉ ghi phiên bản, hash và nội dung đã che. | GĐ2 | Agreed | T |
| NFR7.3 | Căn cứ pháp lý về bảo vệ dữ liệu cá nhân phải được người duyệt pháp lý xác nhận còn hiệu lực. | GĐ2 | Proposed (D-09) | R |
| **NFR8** | **Chi phí** | | | |
| NFR8.1 | Chi phí mỗi câu hỏi được ghi theo model thực sự đã dùng; có ngân sách theo ngày khi dùng provider trả phí. | GĐ3 | Proposed | A |

---

## 7. Ghi chú thiết kế

Các điểm cần lưu ý khi hiện thực sơ đồ. Đây không phải yêu cầu mới.

| Điểm | Ghi chú |
| --- | --- |
| Top-50 → Top-10 → passed chunks | Reranker giữ Top-10 (FR2.8); Confidence Filter chọn tối đa `max_evidence` chunk qua lọc (FR3.2). Khi chưa có LLM Judge + MMR, có thể cắt trực tiếp Top-`max_evidence` sau reranker; phải ghi trong cấu hình. |
| Stream và Gate | Theo sơ đồ, token đi SSE Proxy → Gate. UI nhận sự kiện trạng thái trong lúc chờ và câu trả lời sau Gate (IR2.4). |
| Low confidence → Active Clarification | Sơ đồ đưa cả trường hợp "rỗng" sang làm rõ. FR3.4 tách: thiếu dữ kiện → hỏi lại; kho không có căn cứ → từ chối. |
| Ngoài phạm vi | Sơ đồ không vẽ cạnh Intent Routing → Policy Abstention; FR1.4 bổ sung theo BRD BR-04. |
| Bump Retry (SRS 1.0) | Sơ đồ không có vòng lặp nới bộ lọc; FR5.6 thay bằng sinh lại có giới hạn, không bỏ bộ lọc hiệu lực. |
| Self-Reflection Node (SRS 1.0) | Không có trên sơ đồ; vai trò được chia cho kiểm tra ngữ nghĩa ở Gate (FR5.3) và Policy Abstention (FR5.5). |
| Model trên sơ đồ | Tên model (Claude 3.5 Sonnet, DeepSeek-V3, Qwen-2.5, GPT-4o, Llama-3.3) là ví dụ; danh sách thật nằm trong cấu hình Model Router. Đánh giá official dùng một model cố định (FR6.7). |
| Vision-LLM Parser | Dùng cho văn bản luật nguồn khi nạp kho, không dùng cho tài liệu người dùng (ngoài phạm vi). |

---

## 8. Quyết định còn mở

Khi chưa có quyết định, nhóm làm theo phương án đề xuất. Tech Lead ghi kết quả và đổi trạng thái yêu cầu liên quan.

| Mã | Câu hỏi | Phương án đề xuất | Kết quả |
| --- | --- | --- | --- |
| D-01 | Enum `route` công khai | 5 giá trị ở 5.3.3 | |
| D-02 | Bộ `status`, mã lý do, mã lỗi, HTTP | Bảng 5.3.4 | |
| D-03 | `NOT_RUN` trong `grounding_status` | Thêm vào `AskResponse`; bản ghi chạy lô cũ giữ nguyên | |
| D-04 | Số evidence tối đa sau Confidence Filter | `max_evidence = 5`; Top-10 sau reranker theo sơ đồ | |
| D-05 | Số vòng làm rõ tối đa | 2 | |
| D-06 | Sinh lại có giới hạn khi Gate lỗi có thể sửa | Tối đa 1 lần; tắt trong đánh giá official | |
| D-07 | Quy tắc che PII | Email, điện thoại, CMND/CCCD; trước log, lịch sử, model ngoài | |
| D-08 | Mục tiêu KPI | Bảng KPI ở BRD | |
| D-09 | Văn bản pháp lý về dữ liệu cá nhân áp dụng | Người duyệt pháp lý xác nhận | |
| D-10 | Máy tham chiếu đo latency | Ghi cấu hình máy trong manifest; so sánh cùng máy | |

---

## 9. Ánh xạ SRS 1.0 → 2.1

| SRS 1.0 | 2.1 |
| --- | --- |
| §2.1 sáu phân hệ (UI, API, Agent, Retrieval, LLM, Logging) | Mục 2.1, thêm Knowledge Base theo sơ đồ |
| §2.2 người dùng cuối; quản trị viên / chuyên gia | BRD mục 4; FR8.10 |
| FR1 phân loại, fast-path | FR1.1–FR1.8 |
| FR2 trích metadata | FR2.1 (ngày), FR2.2 (khác) |
| FR2 BM25 + BGE-M3, RRF, rerank Top-10 | FR2.4–FR2.8 |
| FR3 ngưỡng tin cậy, câu hỏi làm rõ | FR3.1–FR3.7 |
| FR4 parent context, trích dẫn chi tiết | FR4.1–FR4.7 |
| FR5 Gate, Bump Retry, Self-Reflection | FR5.1–FR5.8 (xem mục 7) |
| §4.1 Web UI, streaming, Evidence Panel | IR1, IR2.4 |
| §4.2 HTTP/SSE; gRPC/REST nội bộ | IR2, IR4.1 |
| NFR1 hallucination ≈ 0; chỉ "Còn hiệu lực" | NFR1.1–NFR1.3 |
| NFR2 TTFB < 2 s; Redis cache < 200 ms | NFR2.1–NFR2.3 |
| NFR3 API key; rate limit Redis | NFR3.1–NFR3.5 |
| — (mới theo sơ đồ) | FR6 Model Gateway, FR7 Session, FR8 Knowledge Base, FR9 Evaluation & Logging, NFR4–NFR8 |

---

## 10. Quản lý thay đổi spec

1. Thay đổi hành vi bắt đầu bằng PR sửa SRS, Tech Lead duyệt, rồi mới tới PR code.
2. Thay đổi kiến trúc thì sửa sơ đồ và SRS trong cùng PR.
3. PR code ghi mã yêu cầu trong mô tả; test gắn `@pytest.mark.req("<mã>")`.
4. Mỗi lần sửa SRS: tăng phiên bản, thêm dòng lịch sử. Không đổi số mã; bỏ yêu cầu thì để `Dropped` kèm lý do.
5. Kế hoạch sprint chọn yêu cầu theo mã và giai đoạn; trạng thái triển khai và số đo chỉ cập nhật ở [ma trận truy vết](requirements_traceability.md) và báo cáo lượt chạy.
