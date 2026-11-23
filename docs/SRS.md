# TÀI LIỆU ĐẶC TẢ YÊU CẦU PHẦN MỀM (SRS)
**Dự án:** Hệ thống AI Agent Tư vấn Pháp lý (Phân hệ Luật Hôn nhân & Gia đình)
**Phiên bản:** 1.0

---

## 1. Giới thiệu chung (Introduction)

### 1.1. Mục đích (Purpose)
Tài liệu này đặc tả các yêu cầu kỹ thuật, chức năng và phi chức năng cho hệ thống Trợ lý ảo AI Tư vấn Pháp lý. Tài liệu đóng vai trò là bản thiết kế chuẩn (Technical Blueprint) để đội ngũ phát triển (Backend, AI/ML, Frontend) và kiểm thử (QA/QC) làm cơ sở triển khai và nghiệm thu hệ thống.

### 1.2. Phạm vi (Scope)
Hệ thống là một ứng dụng Web Chatbot ứng dụng kiến trúc Advanced Agentic RAG, chuyên tư vấn các vấn đề thuộc Luật Hôn nhân và Gia đình. Hệ thống có khả năng phân loại câu hỏi, truy xuất ngữ cảnh pháp lý từ cơ sở dữ liệu nội bộ, tự động làm rõ thông tin khi thiếu dữ kiện, và sinh câu trả lời đi kèm trích dẫn điều luật chuẩn xác. Giai đoạn này không bao gồm tính năng phân tích hình ảnh/tài liệu cá nhân của người dùng.

### 1.3. Định nghĩa & Viết tắt (Definitions & Acronyms)
* **RAG (Retrieval-Augmented Generation):** Kỹ thuật tăng cường độ chính xác của LLM bằng cách truy xuất dữ liệu bên ngoài.
* **HyDE (Hypothetical Document Embeddings):** Kỹ thuật sinh câu trả lời giả định để tăng cường chất lượng tìm kiếm vector.
* **RRF (Reciprocal Rank Fusion):** Thuật toán kết hợp điểm số từ nhiều phương pháp tìm kiếm (BM25 và Dense Vector).
* **SSE (Server-Sent Events):** Giao thức truyền dữ liệu một chiều từ server đến client, hỗ trợ hiệu ứng gõ chữ (streaming) cho chatbot.
* **Grounding Gate:** Trạm kiểm duyệt đầu ra của LLM nhằm phát hiện nội dung bịa đặt (Hallucination).

---

## 2. Mô tả tổng quan (Overall Description)

### 2.1. Phân cảnh hệ thống (System Perspective)
Hệ thống vận hành theo kiến trúc vi dịch vụ (Microservices) gồm 6 phân hệ cốt lõi:
1. **Tầng UI:** Giao diện Chatbot và Bảng hiển thị trích dẫn (Citations & Evidence Panel).
2. **Tầng API:** Fast API Gateway quản lý luồng dữ liệu, Rate Limiter, và Cache.
3. **Tầng Agent:** Trung tâm điều phối chứa SuperRouter, Context Aggregator và Self-Reflection Node.
4. **Tầng Retrieval:** Xử lý truy xuất dữ liệu từ Knowledge Base (Elasticsearch & Qdrant) và xếp hạng lại (Reranker).
5. **Tầng LLM:** Cung cấp năng lực sinh văn bản (Citation Prompting) và cơ chế tự chối (Policy Abstention).
6. **Tầng Logging:** Module độc lập lưu trữ lịch sử và đo lường các chỉ số chất lượng RAG.

### 2.2. Đặc điểm người dùng (User Characteristics)
* **Người dùng cuối:** Có nhu cầu tra cứu pháp luật nhưng không rành từ ngữ chuyên ngành. Giao tiếp bằng ngôn ngữ tự nhiên, đôi khi sử dụng từ lóng hoặc diễn đạt thiếu ngữ cảnh.
* **Quản trị viên / Chuyên gia pháp lý:** Cập nhật file luật, thiết lập metadata (tình trạng hiệu lực, ngày ban hành) và giám sát chất lượng hệ thống thông qua các chỉ số đo lường.

---

## 3. Đặc tả Yêu cầu Chức năng (Functional Requirements - FR)

* **FR1. Định tuyến Ý định (Intent Routing & Heuristic Fast-Path)**
  * Hệ thống phải phân loại được đầu vào là câu hỏi giao tiếp thông thường (Non-legal) hay câu hỏi pháp lý (Legal).
  * Với câu hỏi Non-legal, hệ thống phản hồi ngay lập tức bằng kịch bản tĩnh (General Chat Responder), bỏ qua LLM và Retrieval để tiết kiệm tài nguyên.

* **FR2. Lọc và Truy xuất Dữ liệu (Hybrid Search & Pre-filtering)**
  * Hệ thống phải trích xuất metadata từ câu hỏi (năm, loại văn bản) để cấu hình bộ lọc trước khi truy xuất.
  * Thực hiện truy xuất song song BM25 và BGE-M3, hợp nhất bằng RRF và xếp hạng lại lấy Top-10 chunks.

* **FR3. Chủ động Làm rõ (Active Clarification)**
  * Khi điểm tin cậy của tài liệu truy xuất (Confidence Threshold) dưới mức cho phép, hệ thống không được cố gắng trả lời.
  * Tầng Agent phải sinh ra câu hỏi ngược lại (Clarifying question) yêu cầu người dùng bổ sung ngữ cảnh.

* **FR4. Sinh câu trả lời có Trích dẫn (Grounded Generation)**
  * Trước khi đưa cho LLM, hệ thống phải khôi phục ngữ cảnh cha (Parent-Context Resolver) của chunk tìm được.
  * Câu trả lời bắt buộc phải đính kèm thông tin trích dẫn chi tiết (Điều, Khoản, Điểm, Số hiệu văn bản).

* **FR5. Trạm kiểm duyệt và Từ chối (Grounding Gate & Policy Abstention)**
  * Bản nháp của LLM phải được đánh giá qua Grounding Gate.
  * **Lỗi Ảo giác (Hallucination):** Nếu phát hiện bịa đặt, hệ thống ghi log và tự động nới lỏng bộ lọc để thử tìm kiếm lại (Bump Retry).
  * **Từ chối an toàn (Refusal):** Nếu hết lượt retry hoặc dữ kiện gốc trống (Ungrounded), LLM sinh câu từ chối an toàn, nộp lại cho Self-Reflection Node để xuất ra UI.

---

## 4. Yêu cầu Giao diện & Giao tiếp (Interface Requirements)

### 4.1. Giao diện Người dùng (Web UI)
* Cung cấp khu vực nhập liệu (Input box) hỗ trợ Enter để gửi.
* Hiển thị phản hồi dạng Streaming Text (từng ký tự xuất hiện liên tục).
* Có bảng "Citations & Evidence Panel" độc lập bên cạnh hoặc dạng Pop-up/Accordion để hiển thị nguyên văn đoạn luật được trích dẫn.

### 4.2. Giao thức Giao tiếp (Communication Interfaces)
* **Client - API Gateway:** Giao tiếp qua HTTP/HTTPS. Stream dữ liệu sử dụng SSE (Server-Sent Events) theo chuẩn `text/event-stream`.
* **Internal Microservices:** Tầng Agent giao tiếp với LLM và Retrieval thông qua gRPC hoặc RESTful API nội bộ.

---

## 5. Yêu cầu Phi chức năng (Non-Functional Requirements - NFR)

* **NFR1. Độ chính xác Pháp lý (Legal Accuracy)**
  * Tỷ lệ Ảo giác (Hallucination Rate) phải tiệm cận mức 0%.
  * Chỉ sử dụng các văn bản có thuộc tính `validity_status` là "Còn hiệu lực".

* **NFR2. Hiệu năng (Performance)**
  * Thời gian phản hồi byte đầu tiên (TTFB) đối với luồng LLM Streaming phải dưới 2 giây.
  * Áp dụng Semantic Query Cache bằng Redis để phản hồi tức thì dưới 200ms cho các câu hỏi pháp lý trùng lặp.

* **NFR3. Bảo mật và Tính sẵn sàng (Security & Availability)**
  * Tích hợp API Key Guard để chống truy cập trái phép.
  * Rate Limiter (Redis) giới hạn số lượng request trên mỗi IP/Session để chống tấn công DDoS và tiết kiệm ngân sách LLM token.

---