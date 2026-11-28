# BRD — Vietnam Legal RAG Assistant (phân hệ Hôn nhân và Gia đình)

| Thuộc tính | Giá trị |
| --- | --- |
| Mã tài liệu | `VN-LEGAL-RAG-BRD` |
| Phiên bản | **2.2.0 — tích hợp phân hệ Tóm tắt bản án pháp luật (25/11/2026), kế thừa bản 2.1.1 (duyệt 20/11/2026) và baseline 2.1 (duyệt 16/11/2026)** |
| Tài liệu liên quan | [SRS 2.2.0](SRS.md) · [Ma trận truy vết và trạng thái](requirements_traceability.md) · sơ đồ [system_architecture.drawio](../architecture/system_architecture.drawio) |
| Người duyệt | Tech Lead / PM |

BRD trả lời **vì sao** làm dự án và **thế nào là thành công**. Hệ thống làm gì nằm ở SRS; đã làm đến đâu nằm ở ma trận truy vết.

## Lịch sử phiên bản

| Phiên bản | Ngày | Nội dung |
| --- | --- | --- |
| 2.1 | 16/11/2026 | Tech Lead duyệt làm baseline cùng mục tiêu KPI. BRD cho toàn dự án, bám sơ đồ kiến trúc: mục tiêu, năng lực nghiệp vụ, quy tắc nghiệp vụ, ba giai đoạn, KPI có định nghĩa, tập đo và mục tiêu. |
| 2.1.1 | 20/11/2026 | Tập đo của BO-02, BO-03 đổi từ "Tập A/B" sang A/B trên Test 30 (SRS D-12, Tech Lead duyệt 20/11/2026), vì Dev30 đã được dùng để chỉnh prompt. Mục tiêu KPI không đổi. |
| 2.2.0 | 25/11/2026 | Tích hợp phân hệ Tóm tắt bản án pháp luật HNGĐ: bổ sung mục tiêu & KPI (`BO-JS-01`–`BO-JS-08`, gồm rubric `Expert Quality`), năng lực nghiệp vụ (`BC-12`), quy tắc nghiệp vụ (`BR-JS-09`, `BR-JS-11`), và đồng bộ phạm vi sản phẩm với SRS 2.2.0. |

---

## 1. Tóm tắt

Người dân và người học luật khó tra cứu đúng quy định Hôn nhân và Gia đình: văn bản bị sửa đổi, thay thế nhiều lần, và câu trả lời phụ thuộc vào thời điểm xảy ra sự việc. Model ngôn ngữ dùng một mình thường bịa số điều luật, lẫn luật cũ và luật mới, hoặc trả lời theo luật nước ngoài.

Dự án xây một trợ lý hỏi đáp pháp luật HNGĐ: chỉ trả lời khi có căn cứ trong kho văn bản đã kiểm định, trích dẫn tới Điều/Khoản/Điểm, áp dụng văn bản có hiệu lực tại ngày tra cứu, hỏi lại khi thiếu dữ kiện và từ chối khi ngoài phạm vi. Hệ thống được xây theo kiến trúc Agentic RAG trong sơ đồ dự án, gồm bảy phân hệ: Web UI, API, Agent, Retrieval, LLM, Knowledge Base, Evaluation & Logging.

## 2. Bối cảnh và vấn đề

### 2.1. Hiện trạng

1. **Văn bản phân tán, chồng lớp.** Luật HNGĐ 1986, 2000, 2014 cùng các nghị định, thông tư, nghị quyết hướng dẫn phải đối chiếu chéo; nhiều điều khoản bị sửa đổi hoặc bãi bỏ từng phần.
2. **Bẫy hiệu lực theo thời gian.** Điều khoản đã hết hiệu lực hôm nay vẫn là căn cứ đúng cho sự việc xảy ra trước đó.
3. **Rủi ro của model sinh văn bản tự do.** Bịa số điều luật; nhầm quy định cũ và mới; trả lời theo luật nước ngoài hoặc chuyển sang ngôn ngữ khác.
4. **Câu hỏi đời thường thiếu dữ kiện.** Người hỏi không biết tình huống của mình cần những dữ kiện nào (thời điểm kết hôn, có đăng ký hay không, tài sản chung hay riêng).

### 2.2. Giải pháp mong muốn

- **Không căn cứ thì không kết luận.** Mỗi kết luận pháp lý dựa trên đoạn văn bản có thật trong kho.
- **Đúng thời điểm.** Chỉ dùng quy định có hiệu lực tại ngày tra cứu.
- **Hỏi lại thay vì đoán.** Thiếu dữ kiện thì hỏi lại; ngoài phạm vi thì nói rõ.
- **Truy vết được.** Từ câu trả lời lần ngược được tới văn bản, Điều, Khoản và phiên bản hệ thống đã tạo ra nó.
- **Minh bạch trách nhiệm.** Luôn nói rõ thông tin chỉ để tham khảo.
- **Bền và tiết kiệm.** Có cache, giới hạn truy cập, model dự phòng; chạy được hoàn toàn local.

---

## 3. Mục tiêu và KPI

Định nghĩa metric theo `evaluation/metric_definitions_v1.md`. Kết luận dựa trên tập Test hoặc chấm mù; Dev đã dùng để chỉnh chỉ để theo dõi. Mọi so sánh trên tập nhỏ phải kèm khoảng tin cậy. Với BO-02 và BO-03, tập A/B dùng để kết luận là Test 30 theo SRS D-12; Dev30 đã dùng để chỉnh prompt nên chỉ để theo dõi. Số đo hiện tại xem [ma trận truy vết, mục KPI](requirements_traceability.md#kpi).

| Mã | Mục tiêu nghiệp vụ | KPI | Tập đo | Mục tiêu | GĐ đo lần đầu |
| --- | --- | --- | --- | --- | --- |
| BO-01 | Tìm đúng căn cứ pháp lý | Recall@5 sau rerank (chunk-level) | Test | ≥ 0,85 | GĐ1 |
| | | MRR@5 sau rerank | Test | ≥ 0,80 | GĐ1 |
| | | Temporal Violation Rate trong kết quả | Dev + Test | 0 | GĐ1 |
| BO-02 | Trả lời đúng luật hơn model dùng một mình | Legal Correctness, chấm mù, hiệu RAG − model một mình | Tập A/B held-out (D-12) | > 0, CI95 không chứa 0 | GĐ1 |
| | | Hallucination Rate | Tập A/B held-out (D-12) | RAG < model một mình; ≤ 10% | GĐ1 |
| | | Context Faithfulness | Tập A/B held-out (D-12), RAG | ≥ 4/5 | GĐ1 |
| BO-03 | Trích dẫn đúng và kiểm chứng được | Citation Precision / Recall theo Gold | Tập A/B held-out (D-12) | ≥ 0,80 / ≥ 0,80 | GĐ1 |
| | | Citation Validity trước Gate | Tập A/B held-out (D-12) | 100% | GĐ1 |
| | | Câu trả lời không phải tiếng Việt | Mọi lượt chạy | 0 | GĐ1 |
| BO-04 | Từ chối và hỏi lại đúng lúc | Tập câu âm xử lý đúng (toàn hệ thống): không phải pháp lý → trả lời xã giao; ngoài phạm vi → từ chối; kho không có căn cứ → từ chối; thiếu dữ kiện → hỏi lại | Tập câu âm | ≥ 90% / ≥ 90% / ≥ 80% / ≥ 70% | GĐ2 |
| | | Từ chối nhầm (câu có căn cứ bị từ chối) | Dev Gold | ≤ 5% | GĐ1 |
| BO-05 | Trải nghiệm dùng được | Byte trạng thái đầu tiên | API | < 2 s | GĐ2 |
| | | Thời gian tới câu trả lời đã kiểm duyệt, p95 | Máy tham chiếu | Tech Lead đặt sau khi chọn máy tham chiếu | GĐ2 |
| | | Cache hit | API | < 200 ms | GĐ3 |
| BO-06 | Minh bạch, an toàn | Phản hồi có câu khuyến cáo | Mọi phản hồi | 100% | GĐ1 |
| | | Rò rỉ PII hoặc secret trong log, lịch sử | Bộ test PII | 0 | GĐ2 |
| | | Request trái phép bị chặn | Bộ test bảo mật | 100% | GĐ2 |
| BO-07 | Vận hành bền, chi phí kiểm soát | Tỷ lệ request trả lời được khi model chính lỗi | Kiểm thử sự cố | ≥ 99% | GĐ3 |
| | | Chi phí / câu hỏi | Mọi lượt chạy | 0 ở chế độ local; trong ngân sách khi dùng provider trả phí | GĐ1 |
| BO-08 | Kho văn bản cập nhật được | Thời gian từ khi có văn bản sửa đổi tới khi hệ thống áp dụng | Quy trình cập nhật | Tech Lead đặt | GĐ3 |

Mục tiêu trong bảng được Tech Lead duyệt ngày 16/11/2026 (SRS D-08). Hai mục chưa có số: p95 thời gian tới câu trả lời (BO-05, chốt khi chọn máy tham chiếu) và thời gian cập nhật kho (BO-08, chốt khi viết feature spec của FR8.9–FR8.10). Đổi mục tiêu sau baseline phải qua PR sửa BRD.

### 3.2. Mục tiêu và KPI — Phân hệ Tóm tắt bản án pháp luật (`BO-JS-01` – `BO-JS-08`)

| Mã | Mục tiêu nghiệp vụ | KPI | Tập đo | Mục tiêu | GĐ đo lần đầu |
| --- | --- | --- | --- | --- | --- |
| BO-JS-01 | Tự động hóa tóm tắt bản án | Endpoint `POST /api/v1/summarize` và tab Streamlit UI hoạt động ổn định, không hồi quy Q&A | API, Web UI & bộ test Q&A | Vận hành ổn định; 100% test hồi quy Q&A PASS | Sprint 12 |
| BO-JS-02 | Rút ngắn thời gian nắm bắt nội dung vụ án | Thời gian người dùng trích xuất đủ 5 nhóm thông tin cốt lõi qua bản tóm tắt có cấu trúc so với đọc bản án toàn văn | Usability Test | Thời gian trích xuất giảm rõ rệt (mục tiêu giảm ≥ 40%) | Sprint 12 |
| BO-JS-03 | Bảo đảm độ chính xác tình tiết | Factual Accuracy ($FA$, micro-average theo atomic claim trên tập Accepted, kèm macro-average) & Acceptance Rate ($AR = N_{\text{accepted}} / N_{\text{total}}$); bắt buộc báo cáo song hành $AR$, nếu $AR = 0\%$ tự động kết luận `FAIL` | Test (20 bản án đã freeze) | $FA \ge 90\%$ (kèm báo cáo $AR$; $AR = 0\% \Rightarrow \text{FAIL}$) | Sprint 12 |
| BO-JS-04 | Kiểm soát tỷ lệ bỏ sót tình tiết trọng yếu | Critical-fact Omission Rate ($CFO$, tính trên toàn bộ $N_{\text{total}}$ bản án Test; `QA_FAILED` không được miễn trừ khỏi đánh giá độ phủ hệ thống; tách bạch thêm trên Accepted) | Test (20 bản án đã freeze) | $CFO < 10\%$ | Sprint 12 |
| BO-JS-05 | Đạt chuẩn chất lượng đánh giá chuyên môn | Expert Quality Score theo rubric 5 tiêu chí có trọng số (thang 1–5); áp dụng Hard Gate tối đa 2,0 / 5,0 (`FAIL`) nếu sai hoặc thiếu quyết định chính | Test (20 bản án đã freeze) | $\ge 4,0 / 5,0$ (không vi phạm Hard Gate) | Sprint 12 |
| BO-JS-06 | Bảo toàn tuyệt đối phán quyết của Tòa án | Decision Accuracy ($DA$ trên bản án phát hành) & Decision Coverage ($DC$ theo từng mục quyết định trọng yếu) | Dev (10) + Test (20) | $DA = 100\%$ / $DC = 100\%$ | Sprint 12 |
| BO-JS-07 | Bảo đảm khả năng truy vết kiểm chứng | Tỷ lệ mục ở trạng thái `PRESENT` trong bản tóm tắt phát hành (`PASS` / `PASS_WITH_WARNINGS`) có `source_refs` ánh xạ chính xác tới `paragraph_id` (`Pxxx_yyy`) trong bản án gốc | Dev (10) + Test (20) | 100% | Sprint 12 |
| BO-JS-08 | An toàn dữ liệu & không gây hồi quy | Rò rỉ nội dung bản án/PII trong log; tỷ lệ PASS bộ kiểm thử hồi quy Q&A (`test/api`, `test/e2e`, `test/orchestration`, `test/schemas`) | Bộ test PII & CI Q&A | 0 rò rỉ; 100% test hồi quy Q&A PASS | Sprint 12 |

**Rubric đánh giá chuyên môn `Expert Quality >= 4.0 / 5.0` (`BO-JS-05`, thang điểm 1–5):**

| STT | Tiêu chí | Trọng số | Nội dung đánh giá |
| :---: | --- | :---: | --- |
| 1 | Độ chính xác tình tiết (*Factual correctness*) | 30% | Khớp sự kiện, số tiền, ngày tháng, vai trò đương sự, không suy diễn |
| 2 | Tính đầy đủ tình tiết trọng yếu (*Critical-fact completeness*) | 25% | Phủ đủ các tình tiết cốt lõi, điều kiện, ngoại lệ, phủ định |
| 3 | Bảo toàn phán quyết của Tòa (*Decision preservation*) | 25% | Giữ đúng toàn bộ quyết định của Hội đồng xét xử |
| 4 | Tính mạch lạc pháp lý & phân biệt chủ thể/vai trò (*Legal coherence & attribution*) | 10% | Phân tách rõ lời trình bày nguyên đơn/bị đơn và nhận định của Tòa |
| 5 | Cấu trúc & khả năng đọc hiểu (*Readability & structure*) | 10% | Tiếng Việt chuẩn mực, bố cục 5 phần rõ ràng |

> **Quy tắc chốt chặn (Hard Gate):** Bất kỳ bản án nào bị bỏ sót hoặc làm sai lệch quyết định chính của Tòa án thì điểm tổng kết tối đa không vượt quá **2,0 / 5,0** và bị tính là **KHÔNG ĐẠT**, bất kể điểm trung bình trọng số các tiêu chí khác cao.

---

## 4. Các bên liên quan và người dùng

### 4.1. Các bên liên quan

| Vai trò | Quan tâm | Trách nhiệm |
| --- | --- | --- |
| Tech Lead / PM | Phạm vi, chất lượng, tiến độ | Duyệt BRD, SRS, mục tiêu KPI, quyết định mở |
| Người duyệt pháp lý | Đúng luật, đúng hiệu lực | Duyệt Gold, chấm mù, duyệt văn bản mới vào kho, xác nhận căn cứ pháp lý về dữ liệu cá nhân |
| Nhóm phát triển | Kiến trúc, chất lượng code | Hiện thực SRS; đề xuất thay đổi spec qua PR |
| Hội đồng đánh giá | Tính tái lập, độc lập của số liệu | Xem manifest và báo cáo đánh giá |

### 4.2. Người dùng

| Người dùng | Nhu cầu | Kênh |
| --- | --- | --- |
| Người dân | Hỏi bằng ngôn ngữ đời thường (tuổi kết hôn, ly hôn, chia tài sản, nuôi con, cấp dưỡng); được hỏi lại khi thiếu dữ kiện; hiểu căn cứ | Web UI |
| Người học / làm pháp lý | Quy định tại một thời điểm cụ thể; trích dẫn tới Điều/Khoản/Điểm; xem nguyên văn | Web UI, API |
| Quản trị viên / chuyên gia pháp lý | Thêm, cập nhật văn bản và metadata hiệu lực; theo dõi chất lượng | Quy trình nạp kho, dashboard |
| Kỹ sư đánh giá, vận hành | Chạy đánh giá tái lập; theo dõi latency, chi phí, sự cố model | CLI, log, dashboard |

---

## 5. Phạm vi và giai đoạn

### 5.1. Năng lực nghiệp vụ

| Mã | Năng lực | Phân hệ trên sơ đồ | SRS |
| --- | --- | --- | --- |
| BC-01 | Hỏi đáp pháp luật HNGĐ có trích dẫn | Agent, Retrieval, LLM | FR2, FR4, FR5 |
| BC-02 | Phân luồng câu hỏi: xã giao, ngoài phạm vi, pháp lý HNGĐ | Agent (Heuristic Fast-Path, SuperRouter) | FR1 |
| BC-03 | Áp dụng pháp luật theo ngày tra cứu | Retrieval (Metadata & Temporal Pre-filter), Knowledge Base | FR2.1, FR2.4, FR8.7 |
| BC-04 | Hỏi lại khi thiếu dữ kiện, từ chối khi không có căn cứ | Agent (Active Clarification, Policy Abstention) | FR3, FR5.5 |
| BC-05 | Xem nguyên văn căn cứ và hiệu lực | Web UI (Citations & Evidence Panel) | IR1.4, FR5.4 |
| BC-06 | Hội thoại nhiều lượt có lịch sử | API (Session & History Manager) | FR7 |
| BC-07 | Truy cập có kiểm soát qua API | API (API Key Guard, Rate Limiter) | IR2, NFR3 |
| BC-08 | Phản hồi nhanh cho câu hỏi lặp lại | API (Semantic Query & Reranker Cache), LLM (Prompt & KV Cache) | FR2.9, FR6.5 |
| BC-09 | Hoạt động liên tục khi model lỗi | LLM (Model Router, Cascading Fallback, Exception Notifier) | FR6 |
| BC-10 | Nạp và cập nhật kho văn bản | Knowledge Base | FR8 |
| BC-11 | Đo và giám sát chất lượng, chi phí | Evaluation & Logging | FR9 |
| BC-12 | Tóm tắt bản án pháp luật HNGĐ có cấu trúc 5 trường, gắn nguồn và kiểm chứng chất lượng đa tầng | Summarization, API, Web UI, LLM | FR10.1–FR10.8, NFR10.1–NFR10.4 |

### 5.2. Giai đoạn

| Giai đoạn | Mục tiêu | Năng lực | Điều kiện hoàn thành |
| --- | --- | --- | --- |
| **GĐ1 — Lõi RAG có kiểm soát** | Chứng minh RAG có kiểm duyệt tốt hơn model dùng một mình | BC-01, BC-03, BC-05 (dữ liệu), BC-10 (thủ công), BC-11 (đánh giá lô); một model local | KPI GĐ1 ở mục 3 có số đo trên Test và chấm mù; kết quả tái lập được từ manifest |
| **GĐ2 — Ứng dụng hoàn chỉnh** | Người dùng hỏi qua Web/API an toàn | BC-02, BC-04, BC-05 (UI), BC-07 (API key), log có cấu trúc, che PII | KPI GĐ2 có số đo; điều kiện ở mục 8 đạt trước khi mở cho người dùng thật |
| **GĐ3 — Vận hành mở rộng** | Hiện thực đầy đủ sơ đồ kiến trúc | BC-06, BC-07 (rate limit), BC-08, BC-09, BC-10 (tự động), HyDE, LLM Judge + MMR, kiểm tra ngữ nghĩa ở Gate, ReactJS, dashboard | KPI GĐ3 có số đo; không làm giảm KPI GĐ1–GĐ2 |

Lịch cụ thể theo sprint nằm trong kế hoạch sprint; kế hoạch chọn yêu cầu SRS theo mã và giai đoạn.

### 5.3. Ngoài phạm vi

- Lĩnh vực pháp luật khác HNGĐ (hệ thống từ chối).
- Phân tích tài liệu hoặc hình ảnh cá nhân ngoài phạm vi bản án pháp luật HNGĐ dạng PDF có text / TXT (tệp PDF scan cần OCR và hồ sơ cá nhân khác vẫn nằm ngoài phạm vi).
- Tư vấn thay luật sư, soạn đơn từ, đại diện pháp lý.
- Ứng dụng di động riêng.

---

## 6. Quy tắc nghiệp vụ

| Mã | Quy tắc | SRS |
| --- | --- | --- |
| BR-01 | Không có căn cứ trong kho thì không đưa kết luận pháp lý; hỏi lại hoặc từ chối. | FR3, FR5 |
| BR-02 | Chỉ áp dụng pháp luật Việt Nam trong kho đã kiểm định; không dùng kiến thức luật nước ngoài. | FR4.4, FR5.2 |
| BR-03 | Áp dụng văn bản có hiệu lực tại ngày tra cứu. Ngày xác định theo thứ tự: ngày nêu trong câu hỏi → ngày người dùng chọn → hôm nay; người dùng luôn thấy ngày đã áp dụng. | FR2.1, FR2.4, IR1.2 |
| BR-04 | Câu hỏi ngoài HNGĐ bị từ chối và nói rõ phạm vi; câu không phải pháp lý được trả lời xã giao, không kết luận pháp lý. | FR1 |
| BR-05 | Mọi phản hồi có câu: *"Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."* | FR5.8 |
| BR-06 | Câu trả lời chỉ tới người dùng sau khi qua kiểm duyệt căn cứ, kể cả khi lấy từ cache. | FR5.1, FR6.5 |
| BR-07 | Trích dẫn ghi số hiệu văn bản và Điều/Khoản/Điểm, do hệ thống ghép từ metadata. | FR4.5, FR4.7 |
| BR-08 | Thông tin cá nhân không được lưu thô hay gửi ra dịch vụ bên ngoài; dịch vụ bên ngoài chỉ được dùng khi đã che PII và được phê duyệt. | NFR3.4, FR6.7 |
| BR-09 | Lịch sử hội thoại chỉ giúp hiểu câu hỏi, không thay thế căn cứ pháp lý. | FR7.3 |
| BR-10 | Văn bản mới hoặc sửa đổi chỉ được đưa vào kho sau khi người duyệt pháp lý xác nhận. | FR8.10 |
| BR-11 | Số liệu đánh giá phải tái lập được; không dùng tập Test để chỉnh hệ thống. | FR9.6–FR9.8, NFR4 |
| BR-12 | Câu trả lời bằng tiếng Việt. | NFR1.3 |
| BR-JS-09 | Không lưu tệp bản án mặc định sau khi xử lý, không ghi log nội dung bản án hoặc PII; bắt buộc ẩn danh hóa toàn bộ PII (thay thế họ tên đương sự, con chung, người liên quan bằng ký hiệu như `Nguyên đơn Ông A`, `Bị đơn Bà B`, `Cháu C`; che/mã hóa số CMND/CCCD, địa chỉ cư trú và thông tin tài khoản) cho toàn bộ 30 bản án HNGĐ (10 Dev, 20 Test) trước khi lưu vào `data/judgment_benchmark/` hoặc đưa vào đánh giá. | FR10.1, NFR10.3 |
| BR-JS-11 | Khóa cứng ranh giới tập Dev (10 bản án) và tập Test (20 bản án) bằng mã băm SHA-256 (`dataset_sha256`); cấm dùng output LLM thô làm ground truth và cấm tuning prompt dựa trên tập Test. | NFR10.1, NFR10.4 |

---

## 7. Luồng nghiệp vụ (góc nhìn người dùng)

1. Người dùng mở phiên, nhập câu hỏi, có thể chọn ngày tra cứu.
2. Hệ thống kiểm tra quyền truy cập và giới hạn truy cập; câu hỏi lặp lại với cùng ngày có thể được trả ngay từ cache.
3. Câu hỏi không phải pháp lý → trả lời xã giao. Pháp lý ngoài HNGĐ → từ chối, nêu phạm vi.
4. Câu hỏi HNGĐ → hệ thống xác định ngày áp dụng, tìm điều khoản có hiệu lực tại ngày đó.
5. Không đủ căn cứ → nếu thiếu dữ kiện thì hỏi lại; người dùng trả lời trong cùng phiên và hệ thống xử lý lại. Nếu kho không có căn cứ thì từ chối.
6. Đủ căn cứ → hệ thống soạn câu trả lời và kiểm duyệt. Qua kiểm duyệt → hiển thị câu trả lời, trích dẫn, nguyên văn và hiệu lực. Không qua → báo không đưa ra kết luận.
7. Model chính lỗi → hệ thống chuyển model dự phòng; mọi model lỗi → báo sự cố rõ ràng.
8. Mọi trường hợp đều kèm câu khuyến cáo.

**Luồng cập nhật kho:** văn bản mới hoặc sửa đổi từ nguồn chính thức → bóc tách → gắn metadata hiệu lực → người duyệt pháp lý xác nhận → đánh chỉ mục phiên bản mới → kiểm tra hồi quy → áp dụng.

---

## 8. Ràng buộc, giả định, phụ thuộc

**Ràng buộc**

- Chạy được hoàn toàn local trên máy có GPU 4–8 GB VRAM (model local qua Ollama, Elasticsearch, Qdrant); dịch vụ bên ngoài là tùy chọn.
- Đánh giá official dùng một model và một bộ tham số cố định; đổi thì tăng phiên bản và chạy lại.
- Thành phần hạ tầng theo sơ đồ: Redis (cache, rate limit), PostgreSQL (phiên, lịch sử), Elasticsearch, Qdrant.

**Giả định**

- Kho văn bản HNGĐ và metadata hiệu lực được người duyệt pháp lý kiểm định.
- Có người chấm pháp lý cho mỗi lượt chấm mù.

**Điều kiện trước khi mở cho người dùng thật:** che PII hoạt động và có test; API key và rate limit; BO-04 đạt mục tiêu; người duyệt pháp lý xác nhận căn cứ pháp lý về dữ liệu cá nhân (SRS D-09).

---

## 9. Rủi ro nghiệp vụ

| Mã | Rủi ro | Mức | Biện pháp | SRS |
| --- | --- | :---: | --- | --- |
| RK-01 | Áp dụng điều khoản đã bị sửa đổi hoặc bãi bỏ một phần | Cao | Khoảng hiệu lực cấp điều khoản; lọc theo ngày | FR2.4, FR8.7 |
| RK-02 | Model trả lời theo luật nước ngoài hoặc ngôn ngữ khác | Rất cao | Quy tắc trong prompt; Gate chặn | FR4.4, FR5.2 |
| RK-03 | Gate kết luận Grounded nhưng nội dung sai | Cao | Kiểm tra ngữ nghĩa (GĐ3); đo hallucination bằng chấm mù | FR5.3, NFR1.1 |
| RK-04 | Cache trả kết quả của ngày hoặc phiên bản khác | Cao | Khóa cache gồm ngày và phiên bản; xóa cache khi đổi kho | FR2.9, FR8.9 |
| RK-05 | Lộ thông tin cá nhân qua log, lịch sử hoặc provider ngoài | Cao | Che PII; chỉ dùng provider ngoài khi được duyệt | NFR3.4, FR6.7 |
| RK-06 | Model dự phòng cho chất lượng thấp hơn model chính | Trung bình | Gate áp dụng như nhau; ghi model đã dùng; đo riêng theo model | FR6.6 |
| RK-07 | Rò rỉ tập Test vào quá trình chỉnh | Cao | Đóng băng bằng hash; kiểm tra rò rỉ trong CI | FR9.7 |
| RK-08 | Người chấm thiên vị | Trung bình | Chấm mù, trộn thứ tự, đo độ đồng thuận | FR9.6 |
| RK-09 | Hỏi lại hoặc từ chối quá nhiều làm hệ thống vô dụng | Trung bình | Theo dõi từ chối nhầm và số vòng làm rõ | BO-04, FR3.5 |
| RK-10 | Kho văn bản lạc hậu so với văn bản mới ban hành | Trung bình | Quy trình cập nhật có kiểm duyệt | FR8.9, FR8.10 |

---

## 10. Tiêu chí nghiệm thu

Một giai đoạn được nghiệm thu khi:

1. Mọi yêu cầu SRS bắt buộc của giai đoạn đó có trạng thái *Có* trong ma trận truy vết, kèm test hoặc artifact.
2. Mọi KPI của giai đoạn có số đo mới, ghi nguồn. KPI chưa đạt ghi rõ là chưa đạt, kèm hướng xử lý và mốc; không đánh dấu hoàn thành.
3. Không KPI nào của giai đoạn trước bị giảm có ý nghĩa.
