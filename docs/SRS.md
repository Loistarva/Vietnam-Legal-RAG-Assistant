# SRS — Vietnam Legal RAG Assistant (phân hệ Hôn nhân và Gia đình)

| Thuộc tính | Giá trị |
| --- | --- |
| Mã tài liệu | `VN-LEGAL-RAG-SRS` |
| Phiên bản | **2.1 — baseline, Tech Lead duyệt 16/11/2026; mục 5 sửa 17/11/2026** |
| Thay thế | SRS 1.0. Giữ nghĩa của FR1–FR5 và NFR1–NFR3; thêm mã con và nhóm mới. |
| Kiến trúc tham chiếu | [`architecture/system_architecture.drawio`](../architecture/system_architecture.drawio). Phần Retrieval và Knowledge Base của sơ đồ là **chuẩn bắt buộc**; các phần khác là kiến trúc mục tiêu, được làm rõ trong tài liệu này. |
| Tài liệu liên quan | [BRD](BRD.md) · [Ma trận truy vết và trạng thái](requirements_traceability.md) · [Mẫu feature spec](feature_specs/TEMPLATE.md) · [data_contract.md](data_contract.md) · [metric_definitions_v1.md](../evaluation/metric_definitions_v1.md) |

## Lịch sử phiên bản

| Phiên bản | Ngày | Nội dung |
| --- | --- | --- |
| 1.0 | — | FR1–FR5, giao diện, NFR1–NFR3. |
| 2.1 | 16/11/2026 | Tech Lead duyệt làm baseline: mọi yêu cầu chuyển Approved, D-01–D-10 chốt theo phương án đề xuất. Đặc tả toàn hệ thống theo sơ đồ kiến trúc. Mỗi yêu cầu có mã ổn định, giai đoạn, phụ thuộc, cách kiểm chứng; mọi yêu cầu GĐ1–GĐ2 có tiêu chí chấp nhận. Thêm Definition of Ready, thứ tự làm GĐ2, quy trình feature spec cho GĐ3. Trạng thái triển khai tách sang ma trận truy vết. |
| 2.1 (sửa) | 17/11/2026 | Mục 5 viết lại theo contract `week10_v1.0` đang có trong code: `route` hai tầng (`Route` của router → `RouteType` công khai, `action` quyết định hành vi), tên trường `AskResponse` theo code, lỗi chặn trước pipeline trả `ApiError`, `LogEvent` 9 stage. Thêm lộ trình contract (5.6): ba thay đổi `week10_v1.1` đã duyệt, các trường để sau. Thêm điều kiện 7 vào Definition of Ready. Sửa D-01, D-02 và tiêu chí FR1.3–FR1.6, FR3.1, FR3.3, FR4.7, FR6.4, FR7.1, FR9.9, IR1.3, IR2.2. |

---

## 1. Giới thiệu

### 1.1. Mục đích

SRS là **nguồn yêu cầu duy nhất** của dự án. Code, test, kế hoạch sprint và báo cáo dẫn chiếu tới mã yêu cầu ở đây. Hành vi chưa có trong SRS phải được bổ sung vào SRS trước khi code (mục 12).

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

**Mã.** `FRn.m` chức năng · `IRn.m` giao diện · `NFRn.m` phi chức năng. Mã đã phát hành không đổi số, không dùng lại cho nghĩa khác; yêu cầu bị bỏ giữ mã với trạng thái `Dropped`. Tiêu chí chấp nhận có mã `<mã yêu cầu>-ACk`.

**Câu yêu cầu.** "Hệ thống phải…" là bắt buộc; "nên" là khuyến nghị. Dạng sự kiện: *Khi …, hệ thống phải …*.

**Giai đoạn** (định nghĩa ở [BRD mục 5](BRD.md#5-phạm-vi-và-giai-đoạn)):

| Mã | Tên | Ý nghĩa |
| --- | --- | --- |
| GĐ1 | Lõi RAG có kiểm soát | Chứng minh bằng thực nghiệm A/B rằng RAG có kiểm duyệt tốt hơn model dùng một mình. |
| GĐ2 | Ứng dụng hoàn chỉnh | Người dùng hỏi qua Web/API; định tuyến, làm rõ, từ chối, log, bảo mật cơ bản. |
| GĐ3 | Vận hành mở rộng | Cache, giới hạn truy cập, phiên hội thoại, nhiều model và dự phòng, kiểm tra ngữ nghĩa, nạp văn bản tự động, ReactJS. |

Yêu cầu của giai đoạn sau không được làm hỏng yêu cầu đã đạt của giai đoạn trước. Yêu cầu ghi hai giai đoạn (ví dụ "GĐ1 / GĐ3") có phần cơ bản ở giai đoạn đầu và phần mở rộng ở giai đoạn sau; tiêu chí chấp nhận trong SRS là của phần giai đoạn đầu.

**Trạng thái spec.** `Approved` đã được Tech Lead duyệt · `Proposed` yêu cầu mới hoặc thay đổi sau baseline, chờ duyệt · `Dropped` không làm nữa, có lý do. Toàn bộ yêu cầu của bản 2.1 được duyệt ngày 16/11/2026; ngoặc sau `Approved` ghi nguồn của yêu cầu (SRS 1.0, sơ đồ) hoặc "mới 2.1". Trạng thái **triển khai** không ghi ở đây mà ở [ma trận truy vết](requirements_traceability.md).

**Phụ thuộc.** Cột *Phụ thuộc* liệt kê yêu cầu, contract (mục 5) hoặc quyết định mở (mục 8) phải có trước. "—" là không phụ thuộc gì ngoài phần đã có của GĐ1.

**Kiểm chứng.** `T` test tự động · `A` artifact lượt chạy (kết quả + manifest) · `R` chấm hoặc duyệt thủ công · `I` kiểm tra tài liệu, cấu hình.

**Tham số.** Giá trị số (Top-K, ngưỡng, ngân sách ngữ cảnh, timeout…) nằm trong file cấu hình có phiên bản. SRS nêu giá trị theo sơ đồ hoặc giá trị mặc định; đổi giá trị không cần sửa SRS nhưng phải tăng phiên bản cấu hình (NFR4.3).

### 1.4. Thuật ngữ

| Thuật ngữ | Nghĩa |
| --- | --- |
| `as_of_date` | Ngày áp dụng pháp luật cho câu hỏi, `YYYY-MM-DD`. |
| Parent / child chunk | Parent: một Điều hoặc nhóm Khoản liên tiếp của một Điều (≤ 1.500 ký tự), dùng làm ngữ cảnh. Child: đoạn ≤ 256 từ (đếm trên văn bản đã tách từ) dùng để truy xuất. |
| Evidence | Mục ngữ cảnh đã đánh số `[1]..[n]` đưa vào prompt. |
| Grounding Gate | Bước kiểm duyệt bản nháp của LLM trước khi phát ra. |
| Run A / Run B | A: model trả lời không ngữ cảnh. B: RAG có kiểm duyệt. Cùng model và tham số sinh. |
| Dev Gold / Dev30 / Test | Câu có đáp án đã duyệt nguồn; 30 câu official cho A/B; tập Test đóng băng, không dùng để chỉnh. |
| Tập câu âm | Câu hỏi không được trả lời bình thường, 4 nhóm: `non_legal`, `legal_out_of_scope`, `missing_corpus_evidence`, `insufficient_facts`. |
| Bộ hồi quy | Các tập cố định dùng để kiểm tra lại sau mỗi thay đổi: Dev30, tập câu âm, holdout router. |

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

Cột: **Mã · Yêu cầu · Khối sơ đồ · GĐ · Phụ thuộc · Trạng thái · KC.** Tiêu chí chấp nhận nằm ngay sau mỗi bảng. Yêu cầu GĐ3 có tiêu chí chấp nhận trong feature spec (mục 11).

### FR1. Định tuyến ý định — Heuristic Fast-Path, General Chat Responder, SuperRouter

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR1.1 | Hệ thống phải phân loại mọi câu hỏi hợp lệ là **không phải pháp lý** hoặc **pháp lý** bằng luật heuristic, không gọi LLM. | Heuristic Fast-Path | GĐ2 | — | Approved (1.0 FR1) | T |
| FR1.2 | Khi câu hỏi không phải pháp lý, hệ thống phải trả lời bằng kịch bản tĩnh, bỏ qua Retrieval và LLM, không đưa kết luận pháp lý. | General Chat Responder | GĐ2 | FR1.1, FR1.9, FR5.8 | Approved (1.0 FR1) | T |
| FR1.3 | Với câu hỏi pháp lý, SuperRouter phải xác định ý định và phạm vi: thuộc HNGĐ, ngoài HNGĐ, lẫn cả hai, hoặc chưa chắc chắn; kết quả là `Route` của router, `action` và `route_reason`, chuyển thành `RouteDecision` theo bảng 5.3.3. | SuperRouter / Intent Routing | GĐ2 | D-01 | Approved | T |
| FR1.4 | Khi câu hỏi thuộc lĩnh vực pháp luật khác HNGĐ, hoặc lẫn nội dung ngoài phạm vi không tách được, hệ thống phải từ chối theo policy và nêu rõ phạm vi hỗ trợ, không chạy truy xuất. | Intent Routing → Policy Abstention | GĐ2 | FR1.3, FR1.9, D-02 | Approved | T |
| FR1.5 | Khi phạm vi chưa chắc chắn, hệ thống phải tiếp tục truy xuất và để Confidence Filter quyết định (FR3). | Intent Routing | GĐ2 | FR1.3, FR1.9 | Approved (mới 2.1) | T |
| FR1.6 | Heuristic non-legal không được ghi đè tín hiệu pháp lý: câu có cả lời chào và câu hỏi pháp lý phải đi nhánh pháp lý. | Heuristic Fast-Path | GĐ2 | FR1.1 | Approved | T |
| FR1.7 | Câu hỏi rỗng, chỉ có khoảng trắng, không phải chuỗi hoặc vượt độ dài tối đa (mặc định 2.000 ký tự) phải bị từ chối với `INVALID_REQUEST` trước mọi stage. | Session & History Manager (Validated Query Payload) | GĐ1 | — | Approved | T |
| FR1.8 | Bộ luật định tuyến phải được đo trên một tập holdout độc lập, không dùng để chỉnh luật. | — | GĐ2 | FR1.3 | Approved | A |
| FR1.9 | Orchestrator phải gọi Heuristic Fast-Path và SuperRouter trước Retrieval cho mọi request qua API và CLI, và hành động theo `route`. | Heuristic Fast-Path → SuperRouter | GĐ2 | FR1.1, FR1.3, mục 5.5 | Approved | T |

Tiêu chí chấp nhận:

- **FR1.1-AC1** Given bộ hồi quy router và holdout, When phân loại, Then số lần gọi Model Gateway = 0 và độ chính xác phân loại pháp lý / không pháp lý trên holdout ≥ 90% (BRD BO-04), ghi trong báo cáo router.
- **FR1.1-AC2** Given 6 câu `non_legal` của tập câu âm, Then cả 6 được phân loại không phải pháp lý.
- **FR1.2-AC1** Given "Xin chào", Then `route = NON_LEGAL`, `status = SUCCESS`, `grounding_status = NOT_RUN`, `llm_calls = 0`, `citations = []`, có disclaimer.
- **FR1.2-AC2** Câu trả lời xã giao lấy từ tập kịch bản cố định trong cấu hình và không chứa số hiệu văn bản hay chữ "Điều".
- **FR1.3-AC1** Given bất kỳ câu pháp lý nào, Then `Route` của router thuộc 5 giá trị và `action` đúng cột tương ứng ở bảng 5.3.3; `RouteDecision.route` là `RouteType` ánh xạ theo bảng đó; `reason_code` thuộc enum lý do của router.
- **FR1.4-AC1** Given 8 câu `legal_out_of_scope` của tập câu âm, Then mỗi câu `status = ABSTAIN`, `error_code = ROUTE_POLICY`, số lần gọi Retrieval = 0, `llm_calls = 0`.
- **FR1.4-AC2** Thông báo từ chối có cụm nêu phạm vi ("Hôn nhân và gia đình") và disclaimer.
- **FR1.5-AC1** Given router xếp câu vào `LEGAL_SCOPE_UNCERTAIN`, Then `action = LEGAL_RETRIEVAL`, `route = MIXED_REVIEW` và Retrieval chạy; nếu không đủ tin cậy thì `abstention_source = confidence_filter`; nếu Gate PASS thì `status = SUCCESS`.
- **FR1.6-AC1** Given "Chào bạn, cho hỏi tuổi kết hôn của nữ là bao nhiêu?", Then `Route` của router là `LEGAL_HNGD` (`route = LEGAL_IN_SCOPE`).
- **FR1.7-AC1** Given `query = "   "` hoặc `query` dài 2.001 ký tự hoặc `query = 123`, Then `INVALID_REQUEST` (HTTP 422 ở API) và không stage nào chạy.
- **FR1.8-AC1** Holdout có 30–40 câu, có metadata nguồn; báo cáo similarity audit cho thấy không câu nào trùng hoặc gần trùng với bộ luật và bộ hồi quy; router được đóng băng (ghi version/hash) trước khi chạy holdout.
- **FR1.9-AC1** Given một request qua API, Then trong log sự kiện `router` có trước mọi sự kiện `retrieval`.
- **FR1.9-AC2** Given request `NON_LEGAL` hoặc `LEGAL_OUT_OF_SCOPE`, Then số lần gọi Retrieval và Model Gateway = 0.

### FR2. Lọc trước và truy xuất lai — SuperRouter, Metadata & Temporal Pre-filter, BM25, Dense, RRF, Cross-Encoder, Cache

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR2.1 | Hệ thống phải xác định `as_of_date` và ghi `as_of_date_source`: đánh giá benchmark dùng ngày của câu trong benchmark (`benchmark`); tương tác theo thứ tự ngày nêu trong câu hỏi (`query_text`) → ngày người dùng chọn (`user_input`) → hôm nay (`system_today`). Câu chỉ nêu năm: năm đã qua lấy 31/12, năm hiện tại lấy hôm nay, năm tương lai lấy 01/01. | Metadata Filters Extraction | GĐ1 | — | Approved (1.0 FR2) | T |
| FR2.2 | Hệ thống phải trích thêm bộ lọc metadata từ câu hỏi khi có: số hiệu văn bản, loại văn bản, cơ quan ban hành, năm ban hành, số Điều. Bộ lọc chỉ thu hẹp kết quả; không tìm thấy gì với bộ lọc thì bỏ bộ lọc metadata (không bỏ bộ lọc hiệu lực) và ghi lại. | Metadata Filters Extraction | GĐ3 | FR2.1, FR8.6 | Approved (1.0 FR2) | T |
| FR2.3 | Hệ thống nên tạo câu truy vấn viết lại (HyDE) để tăng độ phủ. Câu viết lại chỉ dùng cho truy xuất; prompt và Gate dùng câu gốc; câu viết lại được ghi log. | HyDE Query Rewriting | GĐ3 | FR6.1, FR9.9 | Approved (sơ đồ) | T, A |
| FR2.4 | Hệ thống phải chỉ trả về chunk có hiệu lực tại `as_of_date` theo khoảng nửa mở `effective_from ≤ as_of_date < effective_to` (`effective_to` rỗng = chưa hết hiệu lực). Khoảng hiệu lực cấp Điều/Khoản/Điểm ưu tiên hơn cấp văn bản. Lọc **trước** khi lấy Top-K, cùng một ngữ nghĩa ở mọi nhánh. | Metadata & Temporal Pre-filter | GĐ1 | FR8.7 | Approved (1.0 FR2; NFR1) | T, A |
| FR2.5 | Nhánh sparse phải tìm BM25 trên Elasticsearch, trên văn bản đã tách từ tiếng Việt, có trọng số cho breadcrumb. | Sparse Search (BM25) | GĐ1 | FR8.4, FR8.8 | Approved | T |
| FR2.6 | Nhánh dense phải tìm vector BGE-M3 trên Qdrant. Khi mở collection, hệ thống phải đối chiếu tên model, số chiều và hash corpus; lệch thì dừng. | Dense Vector Search (BGE-M3) | GĐ1 | FR8.8 | Approved | T |
| FR2.7 | Hai nhánh chạy với cùng bộ lọc và được hợp nhất bằng RRF, cho ra **Top-50** ứng viên. | Rank Fusion (RRF) | GĐ1 | FR2.5, FR2.6 | Approved (sơ đồ) | T |
| FR2.8 | Cross-Encoder `bge-reranker-v2-m3` phải chấm lại Top-50 trên chuỗi (tên văn bản + breadcrumb + nội dung) và chuyển **Top-10** sang Confidence Filter. | Cross-Encoder Neural Reranker | GĐ1 | FR2.7, D-04 | Approved (sơ đồ) | T |
| FR2.9 | Khi bật cache, hệ thống phải lưu kết quả truy xuất/rerank và câu trả lời đã qua Gate. Khóa cache phải gồm câu hỏi chuẩn hóa, `as_of_date`, hash corpus, phiên bản cấu hình retrieval, prompt, model và ngưỡng. Cache hit theo ngữ nghĩa phải có ngưỡng tương đồng và không áp dụng khi `as_of_date` khác. | Semantic Query & Reranker Cache | GĐ3 | IR2.1, FR8.9 | Approved (sơ đồ; 1.0 NFR2) | T |
| FR2.10 | Chế độ hai bước (truy xuất tính trước, sinh sau) phải dừng nếu artifact không khớp corpus, cấu hình hoặc `as_of_date` của từng câu. | — | GĐ1 | — | Approved | T |
| FR2.11 | Mỗi kết quả phải mang `retrieval_trace`: ứng viên (id, điểm từng nhánh, hạng, nguồn), bộ lọc đã áp dụng, `corpus_version`, `retrieval_config_version`. | — | GĐ1 | — | Approved | T |

Tiêu chí chấp nhận:

- **FR2.1-AC1** Given "Năm 2010 kết hôn…", không chọn ngày, Then `as_of_date = 2010-12-31`, `as_of_date_source = query_text`.
- **FR2.1-AC2** Given UI chọn `2015-06-01` và câu hỏi không nêu ngày, Then `as_of_date = 2015-06-01`, `as_of_date_source = user_input`.
- **FR2.1-AC3** Given không ngày nào, Then `as_of_date` = ngày hệ thống, `as_of_date_source = system_today`.
- **FR2.1-AC4** Given chạy benchmark, Then mọi câu dùng `as_of_date` của benchmark, `as_of_date_source = benchmark`, kể cả khi câu hỏi có nêu năm.
- **FR2.4-AC1** Given `as_of_date = 2010-01-01`, Then không ứng viên nào có `effective_from > 2010-01-01` hoặc `effective_to ≤ 2010-01-01`.
- **FR2.4-AC2** Given chunk có `effective_to = D`, Then chunk được trả về khi `as_of_date = D − 1 ngày` và không được trả về khi `as_of_date = D`.
- **FR2.4-AC3** Given một Khoản có khoảng hiệu lực riêng khác văn bản chứa nó, Then hệ thống dùng khoảng của Khoản.
- **FR2.4-AC4** Cùng một bộ dữ liệu và `as_of_date`, bộ lọc Elasticsearch, bộ lọc Qdrant và chế độ precomputed cho cùng tập chunk hợp lệ.
- **FR2.5-AC1** Given thiếu thư viện tách từ hoặc khác phiên bản khóa trong cấu hình, When khởi tạo nhánh BM25, Then báo lỗi và không truy vấn.
- **FR2.5-AC2** Truy vấn BM25 tìm trên trường đã tách từ, trường nội dung và breadcrumb với trọng số breadcrumb trong cấu hình.
- **FR2.6-AC1** Given collection có model, số chiều hoặc hash corpus khác cấu hình, When mở collection, Then báo lỗi trước khi tìm.
- **FR2.7-AC1** Given hai danh sách xếp hạng, Then điểm hợp nhất của mỗi ứng viên = Σ 1/(`rrf_k` + hạng) trên các nhánh chứa nó; đầu ra tối đa 50 ứng viên, giữ `retrieval_sources`.
- **FR2.8-AC1** Given 50 ứng viên, Then đầu ra sắp theo `reranker_score` giảm dần, độ dài bằng tham số đầu ra của reranker (mục tiêu 10; xem D-04), chuỗi chấm điểm là `document_breadcrumb_chunk_text`.
- **FR2.8-AC2** Pipeline live không có reranker thì dừng với lỗi cấu hình.
- **FR2.10-AC1** Given artifact precomputed có `as_of_date`, hash corpus, `candidate_text` hoặc cấu hình reranker khác lượt chạy, Then lỗi nêu `query_id` và lượt chạy dừng.
- **FR2.10-AC2** Given artifact thiếu `query_id` cần chạy hoặc câu hỏi khác, Then lỗi.
- **FR2.11-AC1** Mỗi kết quả có `retrieval_trace.candidates[]` với `chunk_id`, `document_id`, `article_id`, `clause_id`, điểm, hạng; `corpus_version` và `retrieval_config_version` không rỗng.

### FR3. Ngưỡng tin cậy và làm rõ — Confidence Threshold Filter (LLM Judge + MMR), Active Clarification

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR3.1 | Confidence Filter phải loại ứng viên có điểm dưới ngưỡng bằng chứng và quyết định "đủ tin cậy" dựa trên điểm hạng 1 so với ngưỡng (GĐ1), cộng thêm đánh giá liên quan bằng LLM Judge (GĐ3). | Confidence Threshold Filter | GĐ1 / GĐ3 | FR2.8 | Approved (1.0 FR3; sơ đồ) | T |
| FR3.2 | Confidence Filter nên dùng MMR để chọn các ứng viên vừa liên quan vừa không trùng lặp; số ứng viên qua lọc (passed chunks) tối đa `max_evidence` (mặc định 5). | Confidence Threshold Filter | GĐ3 | FR3.1, D-04 | Approved (sơ đồ) | T, A |
| FR3.3 | Khi không có ứng viên hoặc không đủ tin cậy, hệ thống **không được** gọi model sinh câu trả lời; luồng chuyển sang Active Clarification. | Confidence Filter → Active Clarification | GĐ1 | FR3.1 | Approved (1.0 FR3; sơ đồ) | T |
| FR3.4 | Active Clarification phải chọn một trong hai: (a) câu hỏi thiếu dữ kiện có thể bổ sung → sinh câu hỏi làm rõ nêu cụ thể dữ kiện cần (`NEEDS_CLARIFICATION`); (b) kho không có căn cứ → từ chối an toàn (`ABSTAIN`). | Active Clarification (Fallback) | GĐ2 | FR3.3, D-02, D-05 | Approved (1.0 FR3) | T, R |
| FR3.5 | Khi người dùng trả lời câu hỏi làm rõ trong cùng phiên, hệ thống phải ghép với câu hỏi trước rồi chạy lại từ SuperRouter. Số vòng làm rõ tối đa có cấu hình (mặc định 2); quá số vòng thì từ chối. | Active Clarification + Session Manager | GĐ3 | FR3.4, FR7.2, D-05 | Approved (mới 2.1) | T |
| FR3.6 | Khi model tự báo cần làm rõ, hệ thống phải trả `NEEDS_CLARIFICATION`, không kèm kết luận pháp lý. | Grounding Gate | GĐ1 | — | Approved | T |
| FR3.7 | Ngưỡng chỉ được đổi bằng phiên bản cấu hình mới, hiệu chỉnh trên Dev và tập câu âm, không dùng Test, kèm báo cáo quét ngưỡng. | — | GĐ1 | — | Approved | I, A |

Tiêu chí chấp nhận:

- **FR3.1-AC1** Given điểm reranker [0,90; 0,40; 0,05], `min_evidence_score = 0,1`, `min_top1_score = 0,5`, Then ứng viên 0,05 bị loại khỏi ngữ cảnh và luồng tiếp tục.
- **FR3.1-AC2** Given điểm hạng 1 = 0,087 < 0,5, Then không đủ tin cậy, `error_code = LOW_CONFIDENCE`, `abstention_source = confidence_filter`.
- **FR3.3-AC1** Given không đủ tin cậy hoặc không có ứng viên, Then `llm_calls = 0`, `done_reason = not_generated`.
- **FR3.3-AC2** Given retriever trả rỗng, Then `error_code = RETRIEVAL_EMPTY`.
- **FR3.4-AC1** Given các câu `insufficient_facts` của tập câu âm, Then ≥ 70% có `status = NEEDS_CLARIFICATION` (BRD BO-04); mỗi câu làm rõ nêu ít nhất một dữ kiện cụ thể (ví dụ thời điểm kết hôn, có đăng ký kết hôn không, tài sản có trước hay sau hôn nhân) và không có kết luận pháp lý.
- **FR3.4-AC2** Given các câu `missing_corpus_evidence` của tập câu âm, Then ≥ 80% có `status = ABSTAIN` với thông báo "không đủ căn cứ" (BRD BO-04).
- **FR3.4-AC3** Phản hồi làm rõ có `clarification` không rỗng, `answer = null`, `citations = []`, có disclaimer.
- **FR3.6-AC1** Given model trả `needs_clarification = true`, Then `status = NEEDS_CLARIFICATION`, `grounding_status = NEEDS_CLARIFICATION`, nội dung trả về là thông báo làm rõ, không phải nội dung model.
- **FR3.7-AC1** Given ngưỡng trong cấu hình thay đổi, Then `threshold_config_version` khác bản trước, có báo cáo quét mới, và báo cáo không đọc file Test.
- **FR3.7-AC2** Mọi kết quả ghi `threshold_config_version`.

### FR4. Sinh câu trả lời có trích dẫn — Parent-Context Resolver, Context Aggregator, Citation & Context Prompt Builder

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR4.1 | Với mỗi chunk qua lọc, hệ thống phải khôi phục parent của nó (Điều hoặc nhóm Khoản của Điều). | Parent-Context Resolver | GĐ1 | FR8.5 | Approved (1.0 FR4) | T |
| FR4.2 | Context Aggregator phải gộp parent trùng, sắp theo thứ tự cuối cùng, giữ trong ngân sách ngữ cảnh (mặc định 6.000 ký tự) và đánh số evidence liên tục `1..n`; mỗi số ánh xạ 1-1 sang `chunk_id`, `document_id`, `article_id`, `clause_id` trong `source_map`. | Context Aggregator | GĐ1 | FR4.1 | Approved | T |
| FR4.3 | Mỗi evidence phải mang nhãn đọc được: tên và số hiệu văn bản, breadcrumb (Chương > Điều > Khoản > Điểm), tình trạng hiệu lực tại `as_of_date`. | Context Aggregator | GĐ1 | FR8.6 | Approved | T |
| FR4.4 | Prompt phải: chỉ cho phép dùng evidence đã cấp; chỉ pháp luật Việt Nam; tiếng Việt; nêu `as_of_date`; yêu cầu từ chối khi không đủ căn cứ; yêu cầu đầu ra có cấu trúc `{answer, evidence_indices, abstained, abstention_reason, needs_clarification}`. | Citation & Context Prompt Builder | GĐ1 | FR4.2 | Approved | T |
| FR4.5 | Model chỉ trả số evidence; hệ thống tự ánh xạ sang trích dẫn. Model không được tự tạo `chunk_id` hay số hiệu văn bản cho trích dẫn. | Prompt Builder; Citations Map | GĐ1 | FR4.2 | Approved (1.0 FR4) | T |
| FR4.6 | Prompt có phiên bản; mọi thay đổi nội dung tăng phiên bản; mỗi kết quả ghi phiên bản và SHA-256 của prompt đã gửi. | Prompt Builder | GĐ1 | — | Approved | T, A |
| FR4.7 | Trích dẫn hiển thị phải có số hiệu văn bản, Điều, Khoản, Điểm (nếu có) và hiệu lực, lấy từ metadata kho. | Verified Answer + Citations Map | GĐ1 | FR4.5, FR8.6 | Approved (1.0 FR4) | T |

Tiêu chí chấp nhận:

- **FR4.1-AC1** Given chunk có `parent_id`, Then nội dung evidence tương ứng chứa toàn văn parent đó.
- **FR4.1-AC2** Given `parent_id` không có trong kho parent, Then evidence dùng nội dung chunk, `retrieval_trace` ghi số parent bị thiếu và `chunk_id` tương ứng, log có cảnh báo; không im lặng bỏ qua.
- **FR4.2-AC1** Given 3 chunk thuộc cùng một parent, Then parent xuất hiện một lần trong ngữ cảnh.
- **FR4.2-AC2** Given ngữ cảnh đã dựng, Then chỉ số evidence = `[1..n]` liên tục, khóa của `source_map` = cùng tập, `total_chars ≤ max_context_chars`; vi phạm thì contract `ContextPayload` báo lỗi.
- **FR4.3-AC1** Mỗi evidence có `document_title`, `document_number`, `breadcrumb`, `validity_status`, `effective_from` không rỗng; `effective_to` có thể rỗng.
- **FR4.4-AC1** Prompt B đã dựng chứa `as_of_date`, danh sách evidence `[1]..[n]`, quy tắc chỉ dùng evidence, quy tắc chỉ pháp luật Việt Nam, quy tắc trả lời tiếng Việt, quy tắc từ chối.
- **FR4.4-AC2** Schema đầu ra gửi cho model có đủ 5 trường, không cho thêm trường lạ.
- **FR4.5-AC1** Given model trả `evidence_indices = [1, 3]`, Then citations được dựng từ `source_map[1]` và `source_map[3]`.
- **FR4.5-AC2** Given câu trả lời chứa một `chunk_id` có trong ngữ cảnh, Then Gate kết luận Ungrounded với lý do `ANSWER_CONTAINS_CHUNK_ID`.
- **FR4.6-AC1** Mỗi kết quả có `prompt_version` và SHA-256 của prompt; hai câu giống nhau với cùng ngữ cảnh và cùng phiên bản cho cùng SHA-256.
- **FR4.6-AC2** Sửa nội dung template mà không đổi hằng phiên bản thì test kiểm tra phiên bản prompt báo lỗi.
- **FR4.7-AC1** Mỗi citation tra ngược được tới `document_number`, Điều, Khoản, Điểm (nếu có) và `validity_status` qua metadata kho.
- **FR4.7-AC2** Ở API, citation lấy nhãn từ phần tử `evidence` cùng `evidence_index`; Given chunk có `point_ref`, Then phần tử `evidence` đó có `point_ref` *(v1.1, mục 5.6)*.

### FR5. Grounding Gate và từ chối — Grounding Gate, Verified Grounded Answer + Citations Map, Policy Abstention

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR5.1 | Toàn bộ đầu ra của model (kể cả dạng stream) phải đi vào Gate. Không phần nào của bản nháp được gửi tới người dùng trước khi Gate kết luận. | SSE Streaming Proxy → Grounding Gate | GĐ1 | — | Approved (1.0 FR5; sơ đồ) | T |
| FR5.2 | **Kiểm tra cấu trúc.** Gate chỉ kết luận *Grounded* khi: đầu ra parse được và không bị cắt; chỉ số evidence hợp lệ, nằm trong ngữ cảnh và khớp metadata nguồn; mọi ký hiệu `[k]` trong câu trả lời đã khai báo; câu trả lời không rỗng, không chứa `chunk_id`, không có ký tự CJK; model không tự từ chối. | Grounding Gate | GĐ1 | FR4.2, FR4.5 | Approved | T |
| FR5.3 | **Kiểm tra ngữ nghĩa.** Gate nên kiểm tra từng khẳng định pháp lý có được evidence hỗ trợ (NLI hoặc LLM Judge) trước khi kết luận *Grounded*. Bộ kiểm tra phải được đánh giá trên tập có nhãn trước khi bật. | Grounding Gate | GĐ3 | FR5.2, FR9.3 | Approved (1.0 FR5) | T, R |
| FR5.4 | Khi *Grounded*, hệ thống phải tạo Verified Answer kèm Citations Map và gửi Citation Mapping Data cho Evidence Panel. | Verified Grounded Answer + Citations Map | GĐ1 | FR5.2 | Approved (sơ đồ) | T |
| FR5.5 | Khi *Ungrounded*, Policy Abstention phải trả thông báo từ chối cố định (không phải nội dung model) và mã lý do có thể đếm. | Policy Abstention | GĐ1 | FR5.2 | Approved (1.0 FR5; sơ đồ) | T |
| FR5.6 | Với vi phạm có thể sửa (đầu ra bị cắt, ký hiệu chưa khai báo), hệ thống có thể sinh lại **tối đa một lần**; lần sinh lại không được bỏ bộ lọc hiệu lực. Mặc định tắt trong đánh giá official. | Grounding Gate | GĐ2 | FR5.2, D-06 | Approved (mới 2.1, thay "Bump Retry" 1.0) | T |
| FR5.7 | Khi kết quả không phải SUCCESS, các trường `abstained`, `abstention_reason`, `abstention_source` không được rỗng; `abstention_source` ∈ {`router`, `confidence_filter`, `clarification`, `model`, `grounding_gate`}. | Policy Abstention | GĐ1 | — | Approved | T |
| FR5.8 | Mọi phản hồi tới người dùng, ở mọi nhánh, phải có câu khuyến cáo cố định (BRD BR-05). | Gateway | GĐ1 | — | Approved | T |

Tiêu chí chấp nhận:

- **FR5.1-AC1** Given Gate kết luận Ungrounded, Then phản hồi không chứa bất kỳ đoạn nào của câu trả lời model.
- **FR5.1-AC2** Given chế độ stream (GĐ2), Then client không nhận token câu trả lời nào trước sự kiện `final`.
- **FR5.2-AC1** Given model trích `[7]` khi chỉ có 5 evidence, Then Ungrounded với lý do nhóm citation.
- **FR5.2-AC2** Given câu trả lời chứa ký tự Hán, Then Ungrounded với lý do `ANSWER_NOT_VIETNAMESE`.
- **FR5.2-AC3** Given `done_reason = length` hoặc JSON không parse được, Then Ungrounded với lý do nhóm đầu ra lỗi.
- **FR5.2-AC4** Given câu trả lời có `[2]` nhưng `evidence_indices = [1]`, Then Ungrounded với lý do `ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES`.
- **FR5.2-AC5** Given đầu ra hợp lệ, mọi trích dẫn thuộc ngữ cảnh, Then Grounded với lý do `CITATIONS_MATCH_SELECTED_CONTEXT`.
- **FR5.4-AC1** Given Grounded, Then `citations` không rỗng, mỗi citation có `evidence_index` thuộc `evidence_indices`, và dữ liệu evidence tương ứng có sẵn cho Evidence Panel.
- **FR5.5-AC1** Given Ungrounded, Then nội dung trả về là thông báo từ chối cố định kèm disclaimer, `grounding_status = FAIL`, lý do chi tiết nằm trong `retrieval_trace.gate`.
- **FR5.6-AC1** Given lần sinh đầu bị cắt và sinh lại được bật, Then có đúng một lần sinh lại (`llm_calls = 2`); lần hai Grounded thì SUCCESS, không thì ABSTAIN.
- **FR5.6-AC2** Lần sinh lại dùng cùng tập evidence (không bỏ bộ lọc hiệu lực, không đổi `as_of_date`).
- **FR5.6-AC3** Manifest đánh giá official ghi sinh lại = tắt.
- **FR5.7-AC1** Với từng nhánh router chặn, không đủ tin cậy, model từ chối, model xin làm rõ, Gate Ungrounded: ba trường không rỗng và `abstention_source` đúng nhánh.
- **FR5.8-AC1** Với mỗi nhánh SUCCESS, NON_LEGAL, ABSTAIN, NEEDS_CLARIFICATION, FAIL, ERROR do người dùng nhìn thấy: phản hồi có disclaimer đúng một lần.

### FR6. Model Gateway — LiteLLM Proxy, Prompt & KV Cache, Model Router, Fallback, Exception Notifier, SSE Proxy

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR6.1 | Mọi lời gọi model phải đi qua một gateway có giao diện tương thích OpenAI; module khác không gọi trực tiếp provider. | OpenAI-Compatible Interface | GĐ1 (một provider) / GĐ3 | — | Approved (sơ đồ) | T |
| FR6.2 | Model, tham số sinh (temperature, độ dài tối đa, ngữ cảnh tối đa, repeat penalty), timeout và số lần thử lại nằm trong cấu hình có phiên bản. | Model Router | GĐ1 | — | Approved | I, T |
| FR6.3 | Model Router phải chọn model theo thứ tự: Primary → Fallback → Local Offline, theo ma trận dự phòng có cấu hình. Thử lại có giới hạn số lần và thời gian. | Model Router; Cascading Fallback Matrix & Retry | GĐ3 | FR6.1, FR6.4 | Approved (sơ đồ) | T |
| FR6.4 | Khi tất cả model thất bại, hệ thống phải trả `status = ERROR`, `error_code = LLM_UNAVAILABLE` *(v1.1)* (hoặc `LLM_TIMEOUT` nếu do quá thời gian), phát sự kiện cảnh báo cho Gateway và ghi log; không trả câu trả lời từ nguồn khác. | Exception Detector & User Notifier | GĐ2 | FR6.1, D-02 | Approved (sơ đồ) | T |
| FR6.5 | Khi bật cache prompt, cache hit phải đi tiếp qua Grounding Gate như đầu ra mới; khóa cache gồm SHA-256 prompt, model và tham số sinh. | Semantic Prompt & KV Cache | GĐ3 | FR6.1, FR5.2 | Approved (sơ đồ) | T |
| FR6.6 | Gateway phải ghi cho mỗi lời gọi: model thực sự đã dùng, digest/phiên bản, tham số, `done_reason`, đã bị cắt hay chưa, token vào/ra, các mốc thời gian (tải model, xử lý prompt, sinh), chi phí ước tính. Giá trị runtime không trả về thì để rỗng, không tự điền 0. | Model Gateway → Latency & Token Cost Metrics | GĐ1 | — | Approved | T |
| FR6.7 | Trong đánh giá official, model và tham số phải cố định: tắt fallback, tắt cache. Dữ liệu chỉ được gửi tới provider bên ngoài khi đã che PII (NFR3.4) và được phê duyệt. | Model Router | GĐ1 | — | Approved | A |
| FR6.8 | Hệ thống phải chạy được ở chế độ chỉ dùng model local, không cần mạng ra ngoài. | Local Offline Models | GĐ1 | — | Approved | A |

Tiêu chí chấp nhận:

- **FR6.1-AC1** (GĐ1) Ngoài module gateway, không module nào gọi HTTP tới provider model (kiểm tra bằng test quét import hoặc mock transport).
- **FR6.2-AC1** Given cấu hình thiếu một khóa bắt buộc, Then gateway báo lỗi khi khởi tạo; Given cấu hình hợp lệ, Then kết quả và manifest ghi đúng các giá trị đã cấu hình.
- **FR6.4-AC1** Given provider không kết nối được sau số lần thử lại, Then `status = ERROR`, `error_code = LLM_UNAVAILABLE` *(v1.1)*, `error.retryable = true`, HTTP 503; Given quá `timeout_seconds`, Then `error_code = LLM_TIMEOUT`, `error.retryable = true`, HTTP 504.
- **FR6.4-AC2** Khi lỗi xảy ra, log có sự kiện stage `llm` trạng thái lỗi; chế độ SSE gửi event `error`.
- **FR6.6-AC1** Mỗi kết quả có `model`, `done_reason`, `truncated`, `token_usage`; manifest có digest và phiên bản runtime.
- **FR6.6-AC2** Given runtime không trả mốc thời gian, Then trường tương ứng là `null`, không phải 0.
- **FR6.7-AC1** Manifest official có `temperature = 0`, cache tắt, fallback khóa; Run A và Run B cùng model digest và tham số sinh.
- **FR6.8-AC1** Given không có mạng ra ngoài, Then một lượt chạy trên model local hoàn tất (ghi bằng artifact).

### FR7. Phiên và lịch sử hội thoại — Session & History Manager

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR7.1 | Hệ thống phải gắn mỗi request với một `query_id` duy nhất và mang `session_id` của client (nếu có) vào log. Sinh `session_id` khi thiếu và trả lại trong phản hồi làm cùng FR7.2 (mục 5.6). | Session & History Manager | GĐ2 | IR2.1 | Approved | T |
| FR7.2 | Hệ thống phải lưu mỗi lượt hỏi đáp của phiên: câu hỏi đã che PII, `as_of_date`, route, status, trích dẫn, phiên bản cấu hình, thời điểm. | Session & History Manager (PostgreSQL) | GĐ3 | FR7.1, NFR3.4 | Approved (sơ đồ) | T |
| FR7.3 | Lịch sử phiên chỉ dùng để hiểu câu hỏi tiếp theo (làm rõ, tham chiếu "trường hợp trên"); không được dùng làm căn cứ pháp lý thay cho evidence. | SuperRouter | GĐ3 | FR7.2 | Approved (mới 2.1) | T |
| FR7.4 | Dữ liệu phiên có thời hạn lưu và quyền truy cập theo chính sách (NFR7). Người dùng có thể yêu cầu xóa phiên. | Session & History Manager | GĐ3 | FR7.2, NFR7.1 | Approved (mới 2.1) | T, I |

Tiêu chí chấp nhận:

- **FR7.1-AC1** Given request có `session_id`, Then mọi sự kiện log của request mang giá trị đó. Phần sinh và trả lại `session_id` kiểm khi thay đổi contract ở mục 5.6 được hiện thực.
- **FR7.1-AC2** Given 1.000 request tương tác không gửi `query_id`, Then 1.000 `query_id` khác nhau và `request_id` của client được trả lại nguyên giá trị. Ở chạy lô, `query_id` lấy từ benchmark và tính duy nhất do run manifest kiểm.

### FR8. Knowledge Base — Raw Data Sources, Vision-LLM Parser, NLP Pipeline, Parent-child Chunking, Elasticsearch, Qdrant

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR8.1 | Mỗi văn bản trong kho phải có nguồn chính thức (CSDL VBQPPL, Công báo…) ghi URL hoặc mã nguồn, và một bản ghi trong danh mục phiên bản văn bản. | Raw Data Sources | GĐ1 | — | Approved | I, T |
| FR8.2 | Văn bản dạng PDF hoặc ảnh quét phải được chuyển thành văn bản bằng Vision-LLM (Qwen 3 VL hoặc tương đương), sau đó làm sạch. Kết quả bóc tách được lưu lại để tái lập, không bóc tách lại khi trả lời câu hỏi. | Vision-LLM Parser | GĐ1 | FR8.1 | Approved (sơ đồ) | I, A |
| FR8.3 | Bộ phân tích phải nhận diện cấu trúc Phần/Chương/Mục/Điều/Khoản/Điểm và tạo breadcrumb. | Vision-LLM Parser → NLP Pipeline | GĐ1 | FR8.2 | Approved | T |
| FR8.4 | Pipeline NLP tiếng Việt phải giữ đồng thời văn bản gốc (cho embedding và trích dẫn) và văn bản đã tách từ bằng underthesea (cho BM25). Phiên bản tokenizer được khóa. | Vietnamese NLP Pipeline (underthesea_mixed) | GĐ1 | FR8.3 | Approved (sơ đồ) | T |
| FR8.5 | Chunking phân cấp: parent là Điều hoặc nhóm Khoản liên tiếp của một Điều (≤ 1.500 ký tự); child ≤ 256 từ, không vượt ranh giới Khoản; nguyên văn được giữ. Định danh: `{document_id}_art_{n}`, `{article_id}_clause_{n}`, `{clause_id}_chunk_{k}`. | Hierarchical Parent-child Chunking | GĐ1 | FR8.4 | Approved | T |
| FR8.6 | Mỗi chunk phải có metadata: số hiệu, loại văn bản, cơ quan ban hành, ngày ban hành, `effective_from`, `effective_to`, `validity_status`, trạng thái cấp điều khoản (bị bãi bỏ, sửa đổi), tham chiếu Điều/Khoản/Điểm. | Chunking | GĐ1 | FR8.1 | Approved | T |
| FR8.7 | Khi một điều khoản bị sửa đổi, bãi bỏ hoặc thay thế, kho phải ghi khoảng hiệu lực riêng cho điều khoản đó và liên kết tới văn bản sửa đổi/thay thế. | Raw Data Sources; Chunking | GĐ1 | FR8.6 | Approved | T |
| FR8.8 | Child chunk phải được đánh chỉ mục vào Elasticsearch (văn bản đã tách từ) và Qdrant (vector), mỗi chỉ mục ghi hash corpus, tên model, số chiều. | Elasticsearch Index; Vector DB | GĐ1 | FR8.5, FR8.9 | Approved (sơ đồ) | T |
| FR8.9 | Kho có phiên bản: định danh bằng SHA-256 của file chunk (chuẩn hóa xuống dòng). Mỗi lần thêm hoặc sửa văn bản phải tạo phiên bản mới, đánh chỉ mục lại, xóa cache liên quan, chạy lại bộ hồi quy. | Knowledge Base | GĐ1 (thủ công) / GĐ3 (tự động) | FR8.5 | Approved | T, A |
| FR8.10 | Quản trị viên phải cập nhật được văn bản và metadata hiệu lực qua quy trình có kiểm duyệt; người duyệt pháp lý xác nhận trước khi phiên bản mới được dùng. | Knowledge Base | GĐ3 | FR8.9 | Approved (1.0 §2.2) | R |

Tiêu chí chấp nhận:

- **FR8.1-AC1** Mọi văn bản trong danh mục có `document_number`, `source_url` không rỗng; mọi `document_id` xuất hiện trong chunk đều có trong danh mục.
- **FR8.2-AC1** Mỗi văn bản có file văn bản đã bóc tách lưu trong repo; chunking đọc từ file đã lưu; đường trả lời câu hỏi không import module bóc tách.
- **FR8.3-AC1** Mỗi chunk có `breadcrumb` bắt đầu từ cấp cao nhất có trong văn bản và kết thúc ở Điều; `article_ref`, `clause_ref`, `point_ref` khớp với định danh.
- **FR8.4-AC1** Mỗi chunk có văn bản gốc (`embed_text_raw`) và văn bản đã tách từ (`seg_text`); phiên bản tokenizer trong cấu hình khớp phiên bản đã dùng khi tạo.
- **FR8.5-AC1** Mọi parent ≤ 1.500 ký tự; mọi child ≤ 256 từ theo cách đếm của chunking; mọi `chunk_id` khớp mẫu định danh; mọi `parent_id` của chunk có trong kho parent; mỗi chunk thuộc đúng một `clause_id`.
- **FR8.5-AC2** Nội dung child là đoạn nguyên văn của văn bản nguồn (không viết lại).
- **FR8.6-AC1** Các trường metadata bắt buộc không rỗng (trừ `effective_to`); `validity_status` thuộc enum {Còn hiệu lực, Hết hiệu lực, Sắp có hiệu lực, Sửa đổi bổ sung, Không xác định}.
- **FR8.7-AC1** Given một điều khoản có bản ghi khoảng hiệu lực riêng, Then chunk của nó có `effective_from`/`effective_to` bằng khoảng đó và có tham chiếu văn bản sửa đổi/thay thế.
- **FR8.8-AC1** Số tài liệu trong chỉ mục Elasticsearch và số điểm trong Qdrant bằng số child chunk; metadata chỉ mục có hash corpus, model, số chiều.
- **FR8.9-AC1** Cùng một file chunk cho cùng SHA-256 trên Windows và Linux; sửa một dòng thì hash đổi; chỉ mục cũ dùng với corpus mới thì FR2.6-AC1 báo lỗi.
- **FR8.9-AC2** (GĐ1) Mỗi lần đổi corpus có ghi chú thay đổi và kết quả chạy lại bộ hồi quy.

### FR9. Đánh giá và giám sát — Evaluation & Logging

| Mã | Yêu cầu | Khối | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- | --- |
| FR9.1 | Hệ thống phải đo Recall@5 và MRR cho truy xuất, ghi rõ stage (sau RRF/sau rerank) và đơn vị (chunk/parent). | Recall@5 & MRR | GĐ1 | — | Approved (sơ đồ) | A |
| FR9.2 | Hệ thống phải đo Citation Accuracy: Citation Precision, Citation Recall theo Gold, Citation Validity trước Gate. | Citation Accuracy | GĐ1 | — | Approved (sơ đồ) | A |
| FR9.3 | Hệ thống phải đo Grounding & Faithfulness Rate: tỷ lệ Grounded/Ungrounded của Gate và Context Faithfulness chấm theo rubric. | Grounding & Faithfulness Rate | GĐ1 | FR9.6 | Approved (sơ đồ) | A, R |
| FR9.4 | Hệ thống phải đo latency (p50/p95 theo stage, thời gian tới byte đầu tiên, thời gian tới câu trả lời đã kiểm duyệt), token và chi phí cho mỗi câu hỏi. | Latency & Token Cost Metrics | GĐ1 | FR6.6, NFR2.3 | Approved (sơ đồ) | A |
| FR9.5 | Ngoài bốn nhóm trên, đánh giá chất lượng phải có Legal Correctness, Hallucination Rate, Answer Relevance, tỷ lệ từ chối, từ chối nhầm, tỷ lệ làm rõ; định nghĩa theo `evaluation/metric_definitions_v1.md`. | Evaluation | GĐ1 | FR9.6 | Approved | I |
| FR9.6 | Đánh giá A/B phải dùng cùng tập câu hỏi, cùng model và tham số sinh; chấm mù (ẩn nhãn, trộn thứ tự), hai người chấm độc lập, báo độ đồng thuận (Weighted Cohen's Kappa) và khoảng tin cậy. | Evaluation | GĐ1 | FR6.7 | Approved | R, A |
| FR9.7 | Tập Test phải đóng băng bằng hash và không dùng để chỉnh tham số; kiểm tra rò rỉ chạy trong CI. | Evaluation | GĐ1 | — | Approved | T |
| FR9.8 | Chạy lô phải ghi kết quả từng câu, lỗi, và manifest (NFR4.2) vào thư mục mới; hỗ trợ chạy tiếp; không ghi đè kết quả cũ. | Evaluation | GĐ1 | — | Approved | T |
| FR9.9 | Mỗi request phải sinh chuỗi log có cấu trúc (JSONL) theo `query_id`, mỗi stage một sự kiện (mục 5.4): route, phiên bản prompt/model/cấu hình, hash corpus, latency, trích dẫn, kết quả Gate, mã lỗi. | Evaluation & Logging | GĐ2 | FR7.1, NFR3.4, mục 5.4 | Approved (1.0 §2.1) | T |
| FR9.10 | Lỗi của logger không được làm thay đổi hoặc chặn câu trả lời. | Evaluation & Logging | GĐ2 | FR9.9 | Approved | T |
| FR9.11 | Hệ thống nên có dashboard theo dõi các chỉ số FR9.1–FR9.5 theo phiên bản cấu hình. | Evaluation & Logging | GĐ3 | FR9.9 | Approved (mới 2.1) | I |

Tiêu chí chấp nhận:

- **FR9.1-AC1** File metric retrieval có Recall@5, MRR@5 (và @10), mỗi giá trị ghi stage và đơn vị, tính bằng `evaluation/metrics.py`, kèm khoảng tin cậy bootstrap.
- **FR9.2-AC1** Citation Precision = trích dẫn khớp Gold / trích dẫn đã sinh; Citation Recall = Khoản Gold được trích / Khoản Gold; Citation Validity tính trên đầu ra trước Gate. Báo cáo ghi cả tử số và mẫu số.
- **FR9.3-AC1** Báo cáo có số lượng PASS, FAIL, ABSTAIN, NEEDS_CLARIFICATION của Gate, và điểm Context Faithfulness trung bình từ chấm mù.
- **FR9.4-AC1** Báo cáo có p50, p95 tổng và theo stage trên các câu có gọi model, token vào/ra trung bình, chi phí mỗi câu; số câu bị loại (ví dụ lượt khởi động) được ghi.
- **FR9.4-AC2** (GĐ2) Qua API, báo cáo có thời gian tới byte đầu tiên và thời gian tới câu trả lời đã kiểm duyệt, tách riêng.
- **FR9.5-AC1** Báo cáo đánh giá ghi phiên bản định nghĩa metric và có đủ các metric trong yêu cầu, metric chưa đo ghi "chưa đo".
- **FR9.6-AC1** Phiếu chấm không có nhãn A/B; thứ tự trộn bằng seed được ghi; ít nhất 10 câu chấm đôi; báo cáo có Weighted Cohen's Kappa, hiệu B − A kèm CI95 hoặc kiểm định Wilcoxon.
- **FR9.7-AC1** Given tập Dev30 chứa một ID của Test hoặc dùng chung Khoản Gold với Test, Then test chống rò rỉ báo lỗi; hash Test khác giá trị đã đóng băng thì lượt chạy official dừng.
- **FR9.8-AC1** Given thư mục kết quả đã tồn tại, Then lượt chạy từ chối ghi; `--resume` bỏ qua câu đã xong; lỗi từng câu ghi vào file lỗi, không dừng cả lượt.
- **FR9.9-AC1** Given một request đi hết pipeline, Then log có các sự kiện cùng `query_id` theo thứ tự `api`, `router`, `retrieval`, `rerank`, `confidence`, `context`, `llm`, `citation`, `gate`, `response` (`confidence` từ `week10_v1.1`; trước đó quyết định ngưỡng ghi ở `rerank`); mỗi dòng parse được JSON và có các trường ở mục 5.4.
- **FR9.9-AC2** Given request đi nhánh xã giao, Then log chỉ có `api`, `router`, `response`.
- **FR9.10-AC1** Given logger ném lỗi ở mọi lần ghi, Then phản hồi giống hệt trường hợp logger hoạt động; lỗi logger được báo ở kênh riêng.

---

## 4. Yêu cầu giao diện

### IR1. Web UI — Chatbot Interface, Citations & Evidence Panel

| Mã | Yêu cầu | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| IR1.1 | Ô nhập câu hỏi hỗ trợ Enter để gửi; hiển thị lịch sử hội thoại của phiên. | GĐ2 | IR2.1 | Approved (1.0 §4.1) | T |
| IR1.2 | Bộ chọn ngày tra cứu; khi người dùng không chọn, hiển thị ngày hệ thống đã áp dụng và lý do (lấy từ câu hỏi hay hôm nay). | GĐ2 | IR2.1, FR2.1 | Approved | T |
| IR1.3 | Hiển thị theo `status`: câu trả lời, câu hỏi làm rõ, thông báo từ chối hoặc lỗi. Hiển thị trạng thái xử lý trong lúc chờ (từ sự kiện SSE). | GĐ2 | IR2.1, IR2.4, D-02 | Approved | T |
| IR1.4 | Citations & Evidence Panel (cột bên hoặc accordion): với mỗi trích dẫn hiển thị tên, số hiệu văn bản, Điều/Khoản/Điểm, nguyên văn evidence, hiệu lực tại `as_of_date`; bấm ký hiệu `[k]` trong câu trả lời thì mở evidence tương ứng. | GĐ2 | IR2.1, FR5.4, FR4.7 | Approved (1.0 §4.1; sơ đồ) | T |
| IR1.5 | Luôn hiển thị câu khuyến cáo. | GĐ2 | FR5.8 | Approved | T |
| IR1.6 | UI chỉ gọi API; không truy cập trực tiếp cơ sở dữ liệu, Qdrant, Elasticsearch hoặc model. | GĐ2 | IR2.1 | Approved | I |
| IR1.7 | Giao diện production dùng ReactJS theo sơ đồ; bản prototype có thể dùng framework khác nếu giữ nguyên contract API. | GĐ2 prototype / GĐ3 ReactJS | IR2.3 | Approved | I |

Tiêu chí chấp nhận (chạy với API giả lập theo OpenAPI):

- **IR1.1-AC1** Nhấn Enter gửi câu hỏi; Shift+Enter xuống dòng (nếu framework hỗ trợ); câu hỏi và phản hồi xuất hiện theo thứ tự trong lịch sử phiên.
- **IR1.2-AC1** Given người dùng chọn ngày, Then request có `as_of_date` đó; Given không chọn, Then request không có `as_of_date` và UI hiển thị `as_of_date` cùng `as_of_date_source` từ phản hồi.
- **IR1.3-AC1** Với mỗi giá trị `status`, UI hiển thị đúng trường (`answer`, `clarification`, `abstention_message`, `error.message`); không suy trạng thái từ trường rỗng.
- **IR1.3-AC2** Given API chậm hoặc timeout, Then UI hiển thị thông báo lỗi thân thiện, không treo.
- **IR1.4-AC1** Given phản hồi có 3 evidence, Then panel có 3 mục với đủ trường; bấm `[2]` mở mục 2.
- **IR1.4-AC2** Given phản hồi không có citation, Then panel ghi "không có căn cứ trích dẫn".
- **IR1.5-AC1** Mọi trạng thái hiển thị đều có disclaimer lấy từ trường `disclaimer`.
- **IR1.6-AC1** Mã nguồn UI không import module backend; mọi lời gọi mạng đi qua một API client.
- **IR1.7-AC1** (GĐ2) Thay URL API trong cấu hình là đủ để UI dùng API thật thay cho API giả lập; không sửa backend.

### IR2. API — Fast API Gateway, SSE/WebSocket, API Key Guard

| Mã | Yêu cầu | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| IR2.1 | `POST /api/v1/ask` nhận `AskRequest`, trả `AskResponse` (mục 5.3). | GĐ2 | mục 5.3, D-01, D-02, D-03, FR1.9 | Approved | T |
| IR2.2 | Mọi endpoint trừ health yêu cầu header `X-API-Key`; thiếu hoặc sai → HTTP 401 `AUTH_REQUIRED`, body `ApiError` (mục 5.3.4). | GĐ2 | — | Approved (1.0 NFR3) | T |
| IR2.3 | Có `GET /api/v1/health` (không gọi model) và tài liệu OpenAPI (`/docs`, `/openapi.json`). | GĐ2 | IR2.1 | Approved | T |
| IR2.4 | Stream qua SSE (`text/event-stream`): event `status` cho từng stage; event `final` chứa `AskResponse` sau Gate; event `error` khi lỗi hoặc outage. Nội dung câu trả lời chỉ có trong `final` (FR5.1). WebSocket là phương án thay thế với cùng loại event. | GĐ2 (SSE) / GĐ3 (WebSocket) | IR2.1, FR5.1, FR9.9 | Approved (1.0 §4.2; sơ đồ) | T |
| IR2.5 | Ánh xạ trạng thái sang HTTP theo mục 5.3.4; không trả prompt thô hay secret. | GĐ2 | D-02 | Approved | T |

Tiêu chí chấp nhận:

- **IR2.1-AC1** Given request hợp lệ, Then phản hồi hợp lệ theo JSON Schema của `AskResponse` sinh từ `schemas/models.py`.
- **IR2.1-AC2** Given request có trường lạ hoặc sai kiểu, Then HTTP 422 `INVALID_REQUEST`.
- **IR2.2-AC1** Thiếu header → 401; sai key → 401; đúng key → 200; key đọc từ biến môi trường, không có giá trị mặc định trong code.
- **IR2.2-AC2** Phản hồi 401 không tiết lộ key hợp lệ hay cấu hình.
- **IR2.3-AC1** `GET /api/v1/health` trả 200 khi không có key và không gọi Model Gateway (số lần gọi = 0).
- **IR2.3-AC2** `/openapi.json` có `/api/v1/ask` với schema `AskRequest`, `AskResponse` và các mã HTTP ở 5.3.4.
- **IR2.4-AC1** Given request SSE, Then chuỗi event là 0 hoặc nhiều `status`, rồi đúng một `final` hoặc một `error`; không có token câu trả lời trong `status`.
- **IR2.4-AC2** `final` bằng phản hồi JSON của cùng request khi gọi không stream.
- **IR2.4-AC3** Given Gate Ungrounded, Then `final` chứa thông báo từ chối, không chứa nội dung model.
- **IR2.5-AC1** Mỗi dòng của bảng 5.3.4 có một test kiểm tra `status`, `grounding_status`, mã và HTTP.
- **IR2.5-AC2** Không phản hồi nào chứa prompt, header, biến môi trường hay stack trace.

### IR3. Giao diện dòng lệnh

| Mã | Yêu cầu | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| IR3.1 | CLI hỏi một câu, tùy chọn ngày tra cứu; in route, status, câu trả lời, trích dẫn, evidence, kết quả Gate, khuyến cáo; exit code 0 SUCCESS, 3 ABSTAIN/NEEDS_CLARIFICATION, 1 ERROR, 2 sai cú pháp. | GĐ2 | FR1.9, FR2.1 | Approved (mới 2.1) | T |
| IR3.2 | CLI chạy lô cho đánh giá (FR9.8). | GĐ1 | FR9.8 | Approved | T |

Tiêu chí chấp nhận:

- **IR3.1-AC1** Mỗi `status` cho đúng exit code; tùy chọn sai cho exit code 2.
- **IR3.1-AC2** `--as-of-date 2015-06-01` cho `as_of_date_source = user_input` khi câu hỏi không nêu ngày.
- **IR3.1-AC3** Given Gate Ungrounded, Then CLI không in nội dung model.
- **IR3.2-AC1** Lệnh chạy lô nhận file ID và file benchmark, tạo thư mục kết quả theo FR9.8, exit khác 0 khi có bản ghi không hợp lệ.

### IR4. Giao tiếp nội bộ

| Mã | Yêu cầu | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| IR4.1 | Các phân hệ giao tiếp qua interface công khai (mục 5.5) với dữ liệu theo contract (mục 5.2). Triển khai có thể là gọi hàm trong một tiến trình hoặc REST/gRPC giữa các dịch vụ; đổi cách triển khai không đổi contract. | GĐ1 | mục 5.5 | Approved (1.0 §4.2) | I |

Tiêu chí chấp nhận:

- **IR4.1-AC1** Orchestrator nhận router, retrieval, gateway, validator, logger qua tham số khởi tạo hoặc cấu hình; một test chạy hết pipeline với bản giả của cả năm thành phần, không cần Elasticsearch, Qdrant hay model.

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

`schemas/models.py` (Pydantic) là nguồn duy nhất của contract; chỉ owner contract sửa file này. JSON Schema sinh tự động vào `schemas/generated/*.schema.json` bằng `python -m schemas.models`, không sửa tay; ví dụ hợp lệ ở `schemas/examples/`. Các file `*.schema.json` ở gốc `schemas/` là schema dữ liệu (benchmark, chunk, metadata) hoặc bản trước contract hiện hành, không phải nguồn của các model dưới đây.

Contract gồm: `AskRequest`, `AskResponse`, `RouteDecision`, `RetrievalBundle`, `CandidateChunk`, `EvidenceItem`, `ContextPayload`, `LLMResponse`, `GroundingResult`, `LogEvent`, bản ghi kết quả chạy lô (`RAGOutputRecord`).

**Phiên bản hiện hành: `week10_v1.0`.** Mục 5.3–5.4 mô tả đúng phiên bản này. Chỗ ghi *(v1.1)* là thay đổi đã duyệt ở mục 5.6 nhưng chưa có trong code; nó chỉ ràng buộc khi `schema_version` của code đạt phiên bản đó.

### 5.3. Contract API (duyệt 16/11/2026, sửa 17/11/2026 — D-01, D-02, D-03)

#### 5.3.1. `AskRequest`

| Trường | Kiểu | Bắt buộc | Ràng buộc |
| --- | --- | --- | --- |
| `schema_version` | string | không | Mặc định phiên bản hiện hành. |
| `query` | string | có | Không rỗng sau khi bỏ khoảng trắng; API từ chối quá 2.000 ký tự (FR1.7). |
| `as_of_date` | `YYYY-MM-DD` | không | Ngày người dùng chọn. |
| `session_id` | string | không | Client giữ; hệ thống mang vào log (FR7.1). |
| `request_id` | string | không | Mã của client; trả lại nguyên giá trị trong `AskResponse`. |
| `query_id` | string | không | Chỉ dùng cho chạy lô (ví dụ `HN_001`). Request tương tác để trống, hệ thống sinh. |

Request không nhận trường nào khác (`extra = forbid`): không có tham số model, Top-K hay chế độ chạy; các giá trị này lấy từ cấu hình.

#### 5.3.2. `AskResponse`

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `schema_version` | string | |
| `query_id` | string | Mã truy vết xuyên pipeline, trùng `query_id` trong log. |
| `request_id` | string \| null | Trả lại từ request. |
| `status` | `SUCCESS` · `NEEDS_CLARIFICATION` · `ABSTAIN` · `ERROR` | Client dựa vào trường này. |
| `route` | `RouteType` (5.3.3) | Luôn có. |
| `as_of_date` | `YYYY-MM-DD` | FR2.1 |
| `as_of_date_source` | `benchmark` · `query_text` · `user_input` · `system_today` | FR2.1 |
| `answer` | string \| null | Chỉ khi SUCCESS; không chứa câu khuyến cáo. |
| `clarification` | string \| null | Chỉ khi NEEDS_CLARIFICATION. |
| `abstention_message` | string \| null | Thông báo từ chối cho người dùng, chỉ khi ABSTAIN. API luôn điền. |
| `abstention_reason` | string \| null | Lý do chi tiết, chỉ khi ABSTAIN: `reason_code` của router, lý do của Confidence Filter, model hoặc Gate. |
| `citations[]` | `{evidence_index, chunk_id, document_id, article_id, clause_id, parent_clause_id?}` | Chỉ trỏ tới evidence. Nhãn hiển thị (FR4.7, IR1.4) lấy từ phần tử `evidence` cùng `evidence_index`. |
| `evidence[]` | `{evidence_index, chunk_id, parent_clause_id, document_id, article_id, clause_id, content, validity_status, effective_from?, effective_to?, source_url?, document_title?, document_number?, article_number?, clause_number?, breadcrumb?, provision_status?}`; thêm `point_ref?` *(v1.1)* | FR4.3, IR1.4 |
| `grounding_status` | `PASS` · `FAIL` · `ABSTAIN` · `NEEDS_CLARIFICATION` · `NOT_RUN` | `NOT_RUN` khi Gate không chạy (D-03). |
| `error_code` | `ErrorCode` \| null | Mã nhóm ở 5.3.4, dùng chung cho lý do từ chối và lỗi. Bắt buộc khi ERROR. |
| `error` | `{message, retryable}` \| null | Chỉ khi ERROR; không chứa traceback, prompt hay secret. |
| `disclaimer` | string | Luôn có. |
| `timings` | `{total_ms, retrieval_ms, llm_total_ms, ttft_model_ms, load_ms, prompt_eval_ms, eval_ms}` | Không chạy hoặc không đo được = null. |

Ràng buộc (validator của `AskResponse` kiểm):

- Mỗi `status` chỉ điền trường của nó; ngoài SUCCESS, `answer = null`.
- SUCCESS của câu pháp lý: `grounding_status = PASS`, `citations` không rỗng, mọi `evidence_index` của citation có trong `evidence`.
- SUCCESS với `route = NON_LEGAL`: `grounding_status = NOT_RUN`, `evidence` và `citations` rỗng.
- `route = LEGAL_OUT_OF_SCOPE` không bao giờ SUCCESS; `route = MIXED_REVIEW` có thể SUCCESS (5.3.3).
- ABSTAIN có `abstention_message` hoặc `abstention_reason`; `JSON_INVALID` và `CITATION_INVALID` chỉ đi với `grounding_status = FAIL`.

Không nằm trong `AskResponse` mà ghi ở log (5.4): phiên bản prompt, model, corpus, cấu hình retrieval và ngưỡng; thông tin cache; thời gian tới sự kiện trạng thái đầu tiên; thời gian của Gate.

#### 5.3.3. `route` và `action`

Router dùng hai tầng nhãn. **`action` quyết định hành vi**; `RouteType` công khai dùng để hiển thị và thống kê.

| `Route` của router | `action` | `RouteType` công khai | Hành vi |
| --- | --- | --- | --- |
| `LEGAL_HNGD` | `LEGAL_RETRIEVAL` hoặc `FAST_PATH` | `LEGAL_IN_SCOPE` | Chạy RAG (`FAST_PATH` hiện chạy RAG như `LEGAL_RETRIEVAL`). |
| `LEGAL_SCOPE_UNCERTAIN` | `LEGAL_RETRIEVAL` | `MIXED_REVIEW` | Chạy RAG; Confidence Filter và Gate quyết định (FR1.5). Có thể SUCCESS. |
| `MIXED_LEGAL_SCOPE` | `POLICY_ABSTENTION` | `MIXED_REVIEW` | ABSTAIN, `ROUTE_POLICY` (FR1.4). |
| `LEGAL_OUT_OF_SCOPE` | `POLICY_ABSTENTION` | `LEGAL_OUT_OF_SCOPE` | ABSTAIN, `ROUTE_POLICY` (FR1.4). |
| `NON_LEGAL` | `GENERAL_CHAT` | `NON_LEGAL` | SUCCESS, `NOT_RUN` (FR1.2). |

- `RouteDecision.route` mang `RouteType`, ánh xạ bằng `map_router_route_to_canonical`; `Route` gốc nằm trong `RouteDecision.reason_code` và `explanation`.
- Sự kiện log stage `router` ghi `route`, `action`, `reason_code`, `policy_version`.
- Đánh giá router (FR1.8, tập câu âm) chấm trên `Route` gốc và `action`, không chấm trên `RouteType`.

#### 5.3.4. Mã lý do, mã lỗi, HTTP

Phản hồi có body `AskResponse`:

| Nhánh | `status` | `grounding_status` | `error_code` | HTTP |
| --- | --- | --- | --- | --- |
| Grounded | SUCCESS | PASS | — | 200 |
| Không phải pháp lý | SUCCESS | NOT_RUN | — | 200 |
| Ngoài phạm vi / lẫn phạm vi | ABSTAIN | NOT_RUN | `ROUTE_POLICY` | 200 |
| Không có ứng viên | ABSTAIN | NOT_RUN | `RETRIEVAL_EMPTY` | 200 |
| Dưới ngưỡng tin cậy | ABSTAIN | NOT_RUN | `LOW_CONFIDENCE` | 200 |
| Thiếu dữ kiện, hỏi lại (FR3.4) | NEEDS_CLARIFICATION | NOT_RUN | — | 200 |
| Model từ chối | ABSTAIN | ABSTAIN | — | 200 |
| Model xin làm rõ | NEEDS_CLARIFICATION | NEEDS_CLARIFICATION | — | 200 |
| Đầu ra lỗi / bị cắt | ABSTAIN | FAIL | `JSON_INVALID` | 200 |
| Trích dẫn sai | ABSTAIN | FAIL | `CITATION_INVALID` | 200 |
| Vi phạm Gate khác | ABSTAIN | FAIL | `GROUNDING_FAIL` | 200 |
| Model quá thời gian | ERROR | NOT_RUN | `LLM_TIMEOUT`, `retryable = true` | 504 |
| Không kết nối được model / mọi model thất bại *(v1.1)* | ERROR | NOT_RUN | `LLM_UNAVAILABLE`, `retryable = true` | 503 |
| Lỗi khác trong pipeline | ERROR | NOT_RUN | `INTERNAL_ERROR` | 500 |

Lỗi chặn trước pipeline có body `ApiError` `{schema_version, error_code, message, query_id?, details[]}` (lớp API định nghĩa, dùng `ErrorCode` của contract):

| Nhánh | `error_code` | HTTP |
| --- | --- | --- |
| Thiếu hoặc sai API key | `AUTH_REQUIRED` | 401 |
| Request không hợp lệ | `INVALID_REQUEST` | 422 |
| Lỗi ngoài pipeline | `INTERNAL_ERROR` | 500 |

HTTP 403 để dành cho key hợp lệ nhưng không đủ quyền (chưa dùng). Mã chi tiết (`route_reason` của router; `violation_codes` của Gate như `CITATION_OUTSIDE_CONTEXT`, `ANSWER_NOT_VIETNAMESE`) nằm trong `abstention_reason` và log; `error_code` công khai là nhóm ở các bảng trên.

### 5.4. `LogEvent`

Trường: `schema_version`, `event_id`, `query_id`, `stage`, `event_type`, `timestamp` (ISO-8601, UTC), `status`, `duration_ms?`, `error_code?`, `masked_metadata`.

`stage` ∈ {`api`, `router`, `retrieval`, `rerank`, `context`, `llm`, `citation`, `gate`, `response`}; thêm `confidence` *(v1.1)*.

`masked_metadata` đã che PII (NFR3.4) và mang tối thiểu các thông tin FR9.9 yêu cầu:

| Stage | Nội dung tối thiểu |
| --- | --- |
| `api` | `session_id` nếu client gửi; khi stream: thời gian tới sự kiện trạng thái đầu tiên (NFR2.1). |
| `router` | `route`, `action`, `reason_code`, `policy_version`. |
| `retrieval` | `corpus_version`, `corpus_hash`, `retrieval_config_version`, số ứng viên. |
| `confidence` *(v1.1)* | Điểm hạng 1, ngưỡng, `threshold_config_version`, quyết định. Trước v1.1 ghi ở stage `rerank` với `event_type` riêng. |
| `llm` | `model`, `prompt_version`, `ttft_model_ms`, số token. |
| `gate` | Kết quả, `violation_codes`. |
| `response` | `status`, `grounding_status`, `error_code`, `total_ms`, số citation và evidence. |

Khi có cache (FR2.9, FR6.5), stage tương ứng ghi cache hit/miss và tầng cache.

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

### 5.6. Lộ trình contract

Thay đổi contract đi theo thứ tự: ghi vào bảng này và Tech Lead duyệt → owner contract sửa `schemas/models.py`, tăng `schema_version`, thêm test tương thích ngược → bỏ dấu *(v1.x)* ở mục 5.3–5.4 và cập nhật ma trận truy vết. Trong cùng dòng `week10_v1.x` chỉ được **thêm** (giá trị enum, trường optional) và `SchemaVersionType` vẫn nhận phiên bản cũ, để bản ghi cũ còn hợp lệ. Đổi tên, bỏ trường hay đổi nghĩa cần phiên bản chính mới.

| Thay đổi | Yêu cầu | Phiên bản | Trạng thái |
| --- | --- | --- | --- |
| `ErrorCode` thêm `LLM_UNAVAILABLE` (HTTP 503); Gateway trả mã này khi không kết nối được model | FR6.4 | `week10_v1.1` | Duyệt 17/11/2026 |
| `EventStage` thêm `confidence` | FR9.9, FR3.1 | `week10_v1.1` | Duyệt 17/11/2026 |
| `EvidenceItem.point_ref` (optional) | FR4.7, IR1.4 | `week10_v1.1` | Duyệt 17/11/2026 |
| `RetrievalBundle.metadata_filters`, `RetrievalBundle.latency_breakdown` (optional) | FR2.11, FR9.4 | `week10_v1.1` | Đề xuất, chờ owner contract và Tech Lead |
| `AskResponse.session_id`, `LogEvent.session_id`, stage `session` | FR7.1, FR7.2 | Khi FR7.2 vào sprint | Dự kiến |
| `ErrorCode` thêm `RATE_LIMITED` (HTTP 429) | NFR3.2 | Khi NFR3.2 vào sprint | Dự kiến |

---

## 6. Yêu cầu phi chức năng

| Mã | Yêu cầu | GĐ | Phụ thuộc | Trạng thái | KC |
| --- | --- | --- | --- | --- | --- |
| **NFR1** | **Độ chính xác pháp lý** | | | | |
| NFR1.1 | Hallucination Rate (rubric riêng, chấm mù) phải thấp hơn model dùng một mình và tiến tới 0; mục tiêu số ở BRD. | GĐ1 | FR9.6 | Approved (1.0 NFR1, diễn đạt lại) | R, A |
| NFR1.2 | Không evidence nào được dùng nếu không có hiệu lực tại `as_of_date` (Temporal Violation Rate = 0). Thay cho "chỉ dùng văn bản Còn hiệu lực" của 1.0 vì sự việc trong quá khứ cần văn bản đã hết hiệu lực. | GĐ1 | FR2.4 | Approved | T, A |
| NFR1.3 | Câu trả lời bằng tiếng Việt; tỷ lệ câu có ký tự CJK sau Gate = 0. | GĐ1 | FR5.2 | Approved | T, A |
| **NFR2** | **Hiệu năng** | | | | |
| NFR2.1 | Byte đầu tiên (sự kiện trạng thái) tới client < 2 giây kể từ khi API nhận request. | GĐ2 | IR2.4, NFR2.3 | Approved (1.0 NFR2, áp cho sự kiện trạng thái vì FR5.1) | A |
| NFR2.2 | Cache hit (FR2.9) trả kết quả < 200 ms. | GĐ3 | FR2.9 | Approved (1.0 NFR2) | A |
| NFR2.3 | Thời gian tới câu trả lời đã kiểm duyệt (p50, p95) được đo trên máy tham chiếu ghi trong manifest; ngưỡng ở BRD. So sánh latency chỉ hợp lệ khi cùng máy. | GĐ1 | D-10 | Approved (mới 2.1) | A |
| **NFR3** | **Bảo mật và sẵn sàng** | | | | |
| NFR3.1 | API Key Guard (IR2.2). | GĐ2 | IR2.2 | Approved (1.0 NFR3) | T |
| NFR3.2 | Rate limit bằng Redis theo IP và session, có cấu hình; vượt → 429 `RATE_LIMITED`. | GĐ3 | IR2.1, FR7.1 | Approved (1.0 NFR3) | T |
| NFR3.3 | Không lưu secret, API key, `.env`, file model trong Git; key đọc từ biến môi trường hoặc kho secret. | GĐ1 | — | Approved | I, T |
| NFR3.4 | Che email, số điện thoại, số CMND/CCCD trước khi ghi log, lưu lịch sử hoặc gửi tới model bên ngoài. Quy tắc và giới hạn sai sót ghi trong chính sách log. | GĐ2 | D-07 | Approved (mới 2.1) | T |
| NFR3.5 | Khi model chính lỗi, dịch vụ vẫn trả lời được qua model dự phòng (FR6.3); khi mọi model lỗi, người dùng nhận thông báo rõ ràng (FR6.4). | GĐ3 | FR6.3, FR6.4 | Approved (sơ đồ) | T |
| **NFR4** | **Tái lập** | | | | |
| NFR4.1 | Lượt đánh giá official: temperature 0, tắt cache, khóa fallback, working tree sạch. | GĐ1 | — | Approved | A |
| NFR4.2 | Manifest ghi tối thiểu: git branch, SHA, trạng thái working tree; hash benchmark, danh sách câu, corpus, cấu hình retrieval/rerank/model/ngưỡng; artifact tính trước; model, digest, phiên bản runtime, tham số sinh; phiên bản prompt; máy chạy (hệ điều hành, CPU, GPU, VRAM); thời gian bắt đầu/kết thúc. | GĐ1 | — | Approved | T |
| NFR4.3 | Mọi file cấu hình có phiên bản hoặc hash, được ghi vào kết quả. | GĐ1 | — | Approved | T |
| **NFR5** | **Độ tin cậy** | | | | |
| NFR5.1 | Sai chiều vector, thiếu tokenizer đúng phiên bản, thiếu khóa cấu hình, artifact không khớp → dừng với lỗi rõ ràng, không tự chọn mặc định. | GĐ1 | — | Approved | T |
| NFR5.2 | Truy cập đồng thời vào chỉ mục vector phải an toàn (dùng Qdrant server khi có nhiều tiến trình). | GĐ2 | — | Approved | I |
| **NFR6** | **Bảo trì và kiểm thử** | | | | |
| NFR6.1 | CI chạy toàn bộ test trên mỗi push và PR. | GĐ1 | — | Approved | T |
| NFR6.2 | Mỗi yêu cầu bắt buộc của giai đoạn hiện hành có ít nhất một test (`@pytest.mark.req("<mã>")`) hoặc artifact trong ma trận truy vết; CI kiểm tra marker trỏ tới mã có trong SRS. | GĐ2 | — | Approved (mới 2.1) | T |
| NFR6.3 | Mỗi phân hệ test được độc lập bằng mock của interface (mục 5.5). | GĐ1 | IR4.1 | Approved | T |
| **NFR7** | **Quyền riêng tư và lưu trữ** | | | | |
| NFR7.1 | Thời hạn lưu log và lịch sử phiên có cấu hình; hết hạn thì xóa. | GĐ3 | FR7.2 | Approved (mới 2.1) | T |
| NFR7.2 | Mặc định không ghi câu hỏi và prompt thô; chỉ ghi phiên bản, hash và nội dung đã che. | GĐ2 | FR9.9, NFR3.4 | Approved | T |
| NFR7.3 | Căn cứ pháp lý về bảo vệ dữ liệu cá nhân phải được người duyệt pháp lý xác nhận còn hiệu lực. | GĐ2 | D-09 | Approved (mới 2.1) | R |
| **NFR8** | **Chi phí** | | | | |
| NFR8.1 | Chi phí mỗi câu hỏi được ghi theo model thực sự đã dùng; có ngân sách theo ngày khi dùng provider trả phí. | GĐ3 | FR6.3 | Approved (mới 2.1) | A |

Tiêu chí chấp nhận:

- **NFR1.1-AC1** Báo cáo chấm mù có Hallucination Rate của A và B với CI95; B < A.
- **NFR1.2-AC1** Mỗi lượt chạy official báo Temporal Violation Rate của evidence đã dùng; giá trị = 0.
- **NFR1.3-AC1** Mọi câu trả lời phát ra trong lượt chạy official có 0 ký tự CJK (đếm bằng cùng hàm của Gate).
- **NFR2.1-AC1** Trên máy tham chiếu, qua API với Dev30, p95 thời gian tới byte trạng thái đầu tiên < 2 s.
- **NFR2.3-AC1** Manifest ghi hệ điều hành, CPU, GPU, VRAM; báo cáo so sánh latency chỉ ghép các lượt cùng cấu hình máy, khác máy thì ghi "không so sánh được".
- **NFR3.1-AC1** Như IR2.2-AC1.
- **NFR3.3-AC1** CI chạy quét secret và chặn khi phát hiện mẫu key; `.env` nằm trong `.gitignore`; CI chặn file `.pyc` được track.
- **NFR3.4-AC1** Given câu hỏi chứa email, số điện thoại (10–11 số, có hoặc không có +84), số CMND (9 số) hoặc CCCD (12 số), Then log và lịch sử chứa nhãn che (`[REDACTED_EMAIL]`, `[REDACTED_PHONE]`, `[REDACTED_ID]`), không chứa giá trị gốc.
- **NFR3.4-AC2** Chính sách log liệt kê các trường hợp che nhầm hoặc bỏ sót đã biết.
- **NFR4.1-AC1** Given working tree có thay đổi và chạy với `--require-clean-checkout`, Then lượt chạy từ chối; manifest official có cache tắt, fallback khóa, temperature 0.
- **NFR4.2-AC1** Test kiểm tra manifest có đủ các khóa trong yêu cầu.
- **NFR4.3-AC1** Mỗi kết quả có hash hoặc phiên bản của cấu hình retrieval, rerank, model, ngưỡng.
- **NFR5.1-AC1** Mỗi điều kiện trong yêu cầu có một test gây lỗi và kiểm tra thông báo lỗi nêu rõ nguyên nhân.
- **NFR5.2-AC1** Given API và chạy lô cùng lúc trên Qdrant server, Then không có lỗi khóa; ở chế độ Qdrant nhúng, tiến trình thứ hai bị từ chối với thông báo rõ ràng.
- **NFR6.1-AC1** Một PR có test hỏng thì check CI đỏ.
- **NFR6.2-AC1** Given marker trỏ tới mã không có trong SRS, Then CI đỏ; báo cáo liệt kê yêu cầu bắt buộc chưa có test hoặc artifact.
- **NFR6.3-AC1** Test của mỗi phân hệ chạy được khi không có Elasticsearch, Qdrant và model; test cần dịch vụ thật được đánh dấu riêng.
- **NFR7.2-AC1** Với cấu hình mặc định, log không chứa nguyên văn câu hỏi hay prompt; bật cờ debug mới ghi, và cờ này tắt trong cấu hình production.
- **NFR7.3-AC1** Chính sách log ghi văn bản pháp lý áp dụng, người duyệt pháp lý và ngày xác nhận.

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

Tech Lead đã duyệt cả 10 quyết định theo phương án đề xuất ngày 16/11/2026; D-01, D-02 sửa ngày 17/11/2026 cho khớp contract `week10_v1.0`. Quyết định mới phát sinh thêm vào bảng này với mã tiếp theo; yêu cầu phụ thuộc quyết định chưa chốt thì chưa đạt Definition of Ready (mục 10).

| Mã | Câu hỏi | Phương án | Chặn | Kết quả |
| --- | --- | --- | --- | --- |
| D-01 | Enum `route` công khai | Hai tầng: 5 `Route` của router → 4 `RouteType` công khai; `action` quyết định hành vi (5.3.3) | FR1.3, IR2.1 | Duyệt 16/11/2026; sửa 17/11/2026 |
| D-02 | Bộ `status`, mã lý do, mã lỗi, HTTP | Bảng 5.3.4: `error_code` dùng chung cho lý do từ chối và lỗi; lỗi chặn trước pipeline trả `ApiError` 401/422; `LLM_UNAVAILABLE` ở `week10_v1.1` | FR1.4, FR3.4, FR6.4, IR1.3, IR2.1, IR2.5 | Duyệt 16/11/2026; sửa 17/11/2026 |
| D-03 | `NOT_RUN` trong `grounding_status` | Thêm vào `AskResponse`; bản ghi chạy lô cũ giữ nguyên | IR2.1 | Duyệt 16/11/2026 |
| D-04 | Số evidence tối đa sau Confidence Filter | `max_evidence = 5`; Top-10 sau reranker theo sơ đồ | FR2.8, FR3.2 | Duyệt 16/11/2026 |
| D-05 | Cách sinh câu hỏi làm rõ; số vòng tối đa | GĐ2: mẫu câu theo nhóm dữ kiện thiếu do model chọn; tối đa 2 vòng ở GĐ3 | FR3.4, FR3.5 | Duyệt 16/11/2026 |
| D-06 | Sinh lại có giới hạn khi Gate lỗi có thể sửa | Tối đa 1 lần; tắt trong đánh giá official | FR5.6 | Duyệt 16/11/2026 |
| D-07 | Quy tắc che PII | Email, điện thoại, CMND/CCCD; trước log, lịch sử, model ngoài | NFR3.4, FR9.9 | Duyệt 16/11/2026 |
| D-08 | Mục tiêu KPI | Bảng KPI ở BRD | BRD | Duyệt 16/11/2026 theo bảng KPI của BRD; BO-05 p95 và BO-08 chưa có số. |
| D-09 | Văn bản pháp lý về dữ liệu cá nhân áp dụng | Người duyệt pháp lý xác nhận | NFR7.3 | Duyệt 16/11/2026. Việc xác nhận văn bản do người duyệt pháp lý làm trước khi mở cho người dùng thật (NFR7.3). |
| D-10 | Máy tham chiếu đo latency | Ghi cấu hình máy trong manifest; so sánh cùng máy | NFR2.3, NFR2.1 | Duyệt 16/11/2026. Máy tham chiếu cụ thể và ngưỡng p95 (BRD BO-05) chốt khi có lượt đo đầu tiên trên máy đó. |

---

## 9. Thứ tự làm GĐ2

Các yêu cầu trong cùng một đợt làm song song được nhờ mock theo contract (mục 5). Một đợt chỉ bắt đầu khi phụ thuộc của nó ở đợt trước đã xong.

| Đợt | Nội dung | Yêu cầu | Điều kiện bắt đầu |
| --- | --- | --- | --- |
| 0 | Đưa contract đã chốt vào code | D-01, D-02, D-03, D-07 (đã chốt); mục 5.2–5.4 vào `schemas/models.py`; các dòng `week10_v1.1` ở mục 5.6; interface mục 5.5 (Protocol hoặc lớp trừu tượng) | Đã bắt đầu: `week10_v1.0` xong; còn `week10_v1.1` và interface 5.5 |
| 1 | Khung API, router trong pipeline, log, UI với API giả lập | FR1.9, FR1.1–FR1.6, IR2.1, IR2.2, IR2.3, IR2.5, NFR3.1, FR7.1, FR9.9, NFR3.4, NFR7.2, IR1.1–IR1.6, FR6.4 | Đợt 0 xong |
| 2 | Stream, hỏi lại, sinh lại, CLI, độ bền log | IR2.4, NFR2.1, FR3.4, FR5.6, IR3.1, FR9.10, IR1.7 | IR2.1 và FR1.9 xong; D-05, D-06 chốt |
| 3 | Đo và nghiệm thu | FR1.8, NFR5.2, NFR6.2, NFR7.3; đo BO-04 và BO-05 trên toàn hệ thống | Đợt 2 xong |

Việc còn lại của GĐ1 không phụ thuộc GĐ2 và làm song song: chấm mù A/B (FR9.3, FR9.5, FR9.6, NFR1.1), máy tham chiếu (NFR2.3, NFR4.2), Top-10 sau reranker (FR2.8, D-04), ánh xạ nhãn ngày tương tác (FR2.1).

---

## 10. Definition of Ready và Definition of Done

### 10.1. Definition of Ready

Một yêu cầu chỉ được đưa vào sprint khi đủ cả 7 điều kiện:

1. Trạng thái spec là `Approved`.
2. Có tiêu chí chấp nhận trong SRS (GĐ1–GĐ2) hoặc trong feature spec đã duyệt (GĐ3).
3. Tham số cần thiết có giá trị mặc định hoặc nằm trong cấu hình đã có.
4. Không còn quyết định mở chặn nó (cột *Chặn* ở mục 8).
5. Các yêu cầu ở cột *Phụ thuộc* đã xong, hoặc có mock theo contract để làm song song.
6. Đã biết cách kiểm chứng: tên file test dự kiến hoặc artifact cần nộp.
7. Mọi trường contract mà tiêu chí chấp nhận dùng đã có trong `schema_version` hiện hành; nếu chưa, việc thay đổi contract (mục 5.6) được xếp trước trong cùng sprint.

### 10.2. Definition of Done

Một yêu cầu được coi là xong khi:

1. Mọi tiêu chí chấp nhận của nó có test pass (gắn `@pytest.mark.req("<mã>")`) hoặc artifact được nộp.
2. CI xanh.
3. Ma trận truy vết được cập nhật: trạng thái *Có*, bằng chứng, commit.
4. Nếu hành vi khác SRS thì SRS đã được sửa trước (mục 12).

---

## 11. Feature spec cho yêu cầu GĐ3

Yêu cầu GĐ3 trong SRS chỉ nói **cái gì** ở mức kiến trúc; SRS không đoán trước tham số và chi tiết của những phần còn xa.

**Quy trình.** Khi một khối GĐ3 được xếp vào sprint, nhóm viết một **feature spec ngắn** cho khối đó (tham số, tiêu chí chấp nhận, cách đo) rồi mới đưa vào sprint:

1. Người được giao khối tạo file `docs/feature_specs/<mã-khối>-<tên-ngắn>.md` theo [mẫu](feature_specs/TEMPLATE.md), ví dụ `FR2.9-semantic-cache.md`.
2. Feature spec gồm: yêu cầu SRS được hiện thực; thiết kế ngắn; tham số và giá trị mặc định; tiêu chí chấp nhận dạng Given/When/Then; cách đo và tập dữ liệu; ảnh hưởng tới KPI và yêu cầu đã có; rủi ro; quyết định cần chốt.
3. Tech Lead duyệt feature spec qua PR. Chỉ sau khi duyệt, các yêu cầu trong đó mới đạt Definition of Ready.
4. Feature spec không được làm yếu yêu cầu đã có của SRS. Nếu cần đổi câu yêu cầu SRS thì sửa SRS trong cùng PR.
5. Khi khối đã xong, ma trận truy vết trỏ tới feature spec như một phần bằng chứng.

Các yêu cầu GĐ3 cần feature spec: FR2.2, FR2.3, FR2.9, FR3.1 (phần LLM Judge), FR3.2, FR3.5, FR5.3, FR6.1 (phần nhiều provider), FR6.3, FR6.5, FR7.2–FR7.4, FR8.9 (phần tự động), FR8.10, FR9.11, IR1.7 (ReactJS), IR2.4 (WebSocket), NFR2.2, NFR3.2, NFR3.5, NFR7.1, NFR8.1.

---

## 12. Quản lý thay đổi spec

### 12.1. Mức ràng buộc với nhóm phát triển

| Loại | Ràng buộc | Muốn khác thì |
| --- | --- | --- |
| Câu yêu cầu, tiêu chí chấp nhận, quy tắc nghiệp vụ (BRD mục 6) | **Bắt buộc.** Hành vi của code phải khớp. | PR sửa SRS/BRD trước, Tech Lead duyệt, rồi mới sửa code. |
| Contract (mục 5: schema, enum, mã lỗi, HTTP, interface) | **Bắt buộc** theo phiên bản hiện hành, kể cả tên trường và giá trị enum. Chỗ ghi *(v1.x)* chưa hiện thực thì chưa ràng buộc. | Theo mục 5.6: ghi thay đổi, Tech Lead duyệt, owner contract sửa `schemas/models.py`, tăng `schema_version`, test tương thích ngược, báo các bên dùng. |
| Mã yêu cầu | **Bắt buộc** ghi trong PR code và marker test. | — |
| Tham số (Top-K, ngưỡng, timeout…) | Theo file cấu hình có phiên bản; SRS chỉ ghi mặc định. | Đổi cấu hình, tăng phiên bản, chạy lại bộ hồi quy; không cần sửa SRS. |
| Cách hiện thực bên trong module (thuật toán, cấu trúc code, thư viện) | **Tự do**, miễn đạt tiêu chí chấp nhận và giữ contract. | — |
| Ghi chú thiết kế (mục 7) | Hướng dẫn, không bắt buộc. | — |

Khi gặp chỗ SRS sai, thiếu hoặc không làm được: dừng phần đó, mở issue hoặc PR sửa SRS nêu mã yêu cầu, làm tiếp phần khác. Không tự diễn giải lại rồi code.

### 12.2. Quy trình

1. Thay đổi hành vi bắt đầu bằng PR sửa SRS (hoặc feature spec), Tech Lead duyệt, rồi mới tới PR code.
2. Thay đổi kiến trúc thì sửa sơ đồ và SRS trong cùng PR.
3. PR code ghi mã yêu cầu trong mô tả; test gắn `@pytest.mark.req("<mã>")`.
4. Mỗi lần sửa SRS: tăng phiên bản, thêm dòng lịch sử. Không đổi số mã; bỏ yêu cầu thì để `Dropped` kèm lý do.
5. Kế hoạch sprint chọn yêu cầu theo mã, giai đoạn và thứ tự ở mục 9; chỉ chọn yêu cầu đạt Definition of Ready. Trạng thái triển khai và số đo chỉ cập nhật ở [ma trận truy vết](requirements_traceability.md) và báo cáo lượt chạy.

---

## 13. Ánh xạ SRS 1.0 → 2.1

| SRS 1.0 | 2.1 |
| --- | --- |
| §2.1 sáu phân hệ (UI, API, Agent, Retrieval, LLM, Logging) | Mục 2.1, thêm Knowledge Base theo sơ đồ |
| §2.2 người dùng cuối; quản trị viên / chuyên gia | BRD mục 4; FR8.10 |
| FR1 phân loại, fast-path | FR1.1–FR1.9 |
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
