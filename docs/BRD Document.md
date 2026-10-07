# TÀI LIỆU YÊU CẦU NGHIỆP VỤ (BRD)
**Dự án:** Trợ lý ảo AI Tư vấn Pháp lý (Legal AI Agent) - Phân hệ Luật Hôn nhân & Gia đình.

## 1. Tổng quan dự án (Executive Summary)
Dự án nhằm xây dựng một Trợ lý ảo AI chuyên biệt trong lĩnh vực pháp lý, ứng dụng kiến trúc Advanced Agentic RAG. Khác với các chatbot AI thông thường (thường mắc lỗi "ảo giác" - hallucination), hệ thống này được thiết kế để hoạt động như một "Trợ lý Nghiên cứu Pháp lý", có khả năng tra cứu chính xác văn bản luật, đối soát dữ liệu nghiêm ngặt và đưa ra câu trả lời luôn đi kèm trích dẫn (điều, khoản, văn bản áp dụng). Giai đoạn 1 tập trung vào Luật Hôn nhân và Gia đình 2014 và các văn bản hướng dẫn thi hành.

## 2. Mục tiêu Kinh doanh (Business Objectives)
* **Tự động hóa quy trình tư vấn sơ bộ:** Giảm thiểu 60-70% thời gian chuyên viên pháp lý/luật sư phải trả lời các câu hỏi thường gặp (Q&A cơ bản về thủ tục, mức phạt, quy định chung).
* **Dân chủ hóa kiến thức pháp luật:** Cung cấp cho người dân/khách hàng một công cụ tra cứu pháp luật 24/7 bằng ngôn ngữ tự nhiên, dễ hiểu mà không cần biết chính xác từ khóa kỹ thuật.
* **Giảm thiểu rủi ro pháp lý do tư vấn sai:** Đảm bảo mọi thông tin xuất ra đều có căn cứ pháp lý hiện hành, thông qua cơ chế kiểm duyệt nội bộ (Grounding Gate) và tự động từ chối trả lời (Policy Abstention) nếu không tìm thấy dữ liệu.
* **Tạo lợi thế cạnh tranh:** Ứng dụng AI để nâng cao trải nghiệm khách hàng (Customer Experience) cho các hãng luật hoặc cổng dịch vụ công trực tuyến.

## 3. Các bên liên quan & Người dùng mục tiêu (Stakeholders & Target Audience)
* **Người dùng cuối (End-Users):** Khách hàng của công ty luật, người dân cần giải đáp thắc mắc pháp lý cá nhân (tranh chấp tài sản, thủ tục ly hôn, quyền nuôi con).
* **Chuyên viên Pháp lý (Legal Experts/Knowledge Managers):** Đội ngũ chịu trách nhiệm duy trì, cập nhật và gắn thẻ (tagging metadata) cho các văn bản luật mới vào hệ thống Knowledge Base.
* **Đội ngũ Kỹ thuật (Dev Team):** Xây dựng, bảo trì hạ tầng RAG, tối ưu hóa Vector DB và các pipeline xử lý ngôn ngữ tự nhiên (NLP tiếng Việt).
* **Chủ sở hữu Sản phẩm (Product Owner):** Quản lý định hướng phát triển, đo lường các chỉ số kinh doanh và chất lượng phản hồi (Expert Answer Score).

## 4. Phạm vi dự án (Project Scope)
### 4.1. Trong phạm vi (In-Scope)
* Xây dựng luồng giao tiếp Chatbot UI dạng Streaming.
* Tích hợp bộ dữ liệu văn bản pháp luật: Luật, Nghị định, Thông tư (Phân hệ HN&GĐ).
* Khả năng phân biệt ý định người dùng: Chào hỏi thông thường vs. Câu hỏi pháp lý.
* Khả năng chủ động đặt câu hỏi làm rõ (Active Clarification) khi thiếu ngữ cảnh.
* Cung cấp câu trả lời có trích dẫn nguồn (Citation & Evidence).

### 4.2. Ngoài phạm vi (Out-of-Scope)
* Thay thế hoàn toàn luật sư đại diện bảo vệ quyền lợi hợp pháp tại tòa án.
* Tự động điền đơn từ, soạn thảo hợp đồng, hoặc thực hiện thủ tục hành chính công trực tuyến (chỉ dừng ở mức độ tư vấn thông tin).
* Xử lý hình ảnh/chứng cứ do người dùng tải lên (Giai đoạn này chưa kích hoạt tính năng phân tích tài liệu cá nhân của người dùng).

## 5. Yêu cầu Nghiệp vụ Cốt lõi (Key Business Requirements)
* **BR1. Tính Chính xác và Tuân thủ Tuyệt đối:** Hệ thống không được phép tự tạo ra ("bịa") điều luật. Mọi phản hồi pháp lý phải được truy xuất từ cơ sở dữ liệu nội bộ đã được phê duyệt. Hệ thống thà từ chối trả lời ("Tôi không có đủ thông tin...") còn hơn đưa ra lời khuyên sai lệch.
* **BR2. Nhận thức Thời gian Hiệu lực:** Hệ thống chỉ được phép tư vấn dựa trên các văn bản luật "Còn hiệu lực". Phải có cơ chế tự động lọc bỏ hoặc cảnh báo nếu truy xuất trúng văn bản "Hết hiệu lực".
* **BR3. Hiểu ngôn ngữ tự nhiên Tiếng Việt (Vietnamese NLP):** Xử lý tốt các từ lóng, viết tắt, phương ngữ hoặc cách diễn đạt thông tục của người dân (VD: thay vì hỏi "tài sản chung vợ chồng", người dân hỏi "tiền làm ra lúc cưới nhau có phải chia đôi không").
* **BR4. Trích dẫn Nguồn minh bạch:** Giao diện trả lời phải hiển thị rõ ràng nguồn căn cứ pháp lý để người dùng (và luật sư) có thể click vào xem đối chiếu văn bản gốc ngay lập tức.
* **BR5. Cảnh báo Miễn trừ trách nhiệm (Disclaimer):** Bắt buộc phải có dòng thông báo pháp lý định kỳ hoặc ghim trên giao diện: *"Đây là tư vấn tự động từ AI, chỉ mang tính chất tham khảo. Vui lòng liên hệ luật sư để được tư vấn cụ thể cho trường hợp của bạn."*

## 6. Giả định, Ràng buộc và Phụ thuộc (Assumptions, Constraints & Dependencies)
* **Giả định:** Chất lượng câu trả lời phụ thuộc 100% vào chất lượng file dữ liệu luật đầu vào (đã được bóc tách đúng cấu trúc Document/Article/Chunk).
* **Ràng buộc:** API của các mô hình LLM lớn (Claude 3.5, Llama 3) yêu cầu chi phí vận hành (Token cost). Cần thiết lập giới hạn số lượng câu hỏi/người dùng/ngày (Rate Limiting) để kiểm soát ngân sách.
* **Phụ thuộc:** Hệ thống phụ thuộc vào pipeline tiền xử lý tiếng Việt (Ví dụ: underthesea) để phân tách từ vựng pháp lý chính xác trước khi nhúng (Embedding) vào Vector DB.