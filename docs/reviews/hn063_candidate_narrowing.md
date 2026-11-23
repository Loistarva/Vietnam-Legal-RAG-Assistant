# HN_063: thu hẹp candidate theo câu hỏi cụ thể

Trước: câu hỏi chung về mọi thuật ngữ chuyên ngành, đáp án trích dở đến đầu
khoản 5, candidate gồm cả 25 Khoản Điều 3. Cắt candidate mà giữ câu hỏi này
sẽ không còn đủ căn cứ đáp ứng yêu cầu.

Sau: hỏi rõ cách định nghĩa/phân biệt hôn nhân, kết hôn và chung sống như vợ
chồng tại khoản 1, 5, 7 Điều 3 Luật 52/2014. Đáp án diễn đạt đúng ba định nghĩa,
không suy rộng sang hậu quả pháp lý hoặc điều kiện khác. Candidate còn ba
chunk; gold_clause_ids (trường phạm vi tham chiếu của draft) đồng bộ ba Khoản.
Gold context vẫn rỗng, confirmed=false, draft và verified_by/verified_at giữ nguyên.

Nguồn nội dung đối chiếu: ba chunk và parsed JSON từ PDF Luật trong repo.
[Trang văn bản chính thức](https://vanban.chinhphu.vn/?classid=1&docid=175351&pageid=27160)
xác định văn bản; lượt mở trang Chính phủ/CSDL quốc gia ngày kiểm trả lỗi máy
chủ, không coi là đã tải lại và xác thực PDF trực tuyến. Cần người phụ trách
xác nhận trước khi chuyển thành gold.

Audit trước/sau: `hn063_candidate_narrowing.json`. Mapping audit PR #25 giữ
nguyên như lịch sử, tài liệu provenance cập nhật số lượng hiện tại.

Không đổi Test, 75 câu Dev đã duyệt hoặc corpus. Kết quả retrieval cũ chưa
được chạy lại cho câu draft đã viết lại; chưa công bố metric mới.
