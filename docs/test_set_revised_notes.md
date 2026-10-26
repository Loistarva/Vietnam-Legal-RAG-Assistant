# Bộ Test đã chỉnh cấu trúc proposal

- `queries_test_revised.json` giữ nguyên 15 câu hỏi và metadata của `queries_test.json`.
- `gold_id_proposals_300_test_revised.json` giữ đủ 300 proposal để tương thích bộ dữ liệu; chỉ 15 hàng có ID trong `queries_test.json` được chỉnh. 285 hàng ngoài Test giữ nguyên. File gốc được giữ nguyên.
- Chỉ dùng nội dung proposal và dữ liệu `chunks.jsonl` để chỉnh. Các nhãn vẫn ở trạng thái chưa xác minh pháp lý.

## Chỉnh sửa

- HN_004, HN_008: bỏ trạng thái xác minh gắn với placeholder `TEST_REVIEWER`; giữ nguyên chunk proposal và hạ trạng thái về draft.
- HN_012, HN_016, HN_020, HN_024, HN_028, HN_032, HN_036: loại ID gold khỏi danh sách candidate để không vừa là gold vừa là candidate.
- HN_036: thay gold chunk điều 131(3) bằng chunk điều 132(1), là đoạn trong corpus nói Luật 52/2014 có hiệu lực từ 01/01/2015 và Luật 22/2000 hết hiệu lực; bỏ version ID khỏi tập chunk gold và lưu riêng ở `gold_document_version_ids`.
- HN_040 và HN_056: ánh xạ proposal TT 02a/2015 sang chunk TT 15/2015 Điều 31 khoản 1 và điểm g khoản 2, nơi corpus ghi ngày hiệu lực TT15 và nêu rõ việc bãi bỏ TT02a.
- HN_044: chuyển ID phiên bản sang `gold_document_version_ids`; thêm chunk Điều 1 và Điều 7 khoản 1 của TT38 cùng Điều 15 khoản 1 của NĐ207 để truy xuất thông tin phạm vi và ngày hiệu lực.
- HN_048: thêm chunk NĐ 126/2014 Điều 1 khoản 1 về phạm vi hôn nhân có yếu tố nước ngoài; giữ version ID của TT 07/2002 riêng để ghi nhận hiệu lực hết năm 2018. Chunk hiện tại là evidence theo chủ đề, còn kết luận hết hiệu lực được giữ ở metadata cấp văn bản.
- HN_052: thêm chunk Luật 22/2000 Điều 109 về ngày luật có hiệu lực; giữ version ID riêng để đối chiếu mốc hết hiệu lực 2015 với ngày hỏi năm 2012.
- HN_060: thêm chunk NĐ 123/2015 Điều 1 khoản 1; metadata trên chunk ghi tình trạng văn bản hết hiệu lực một phần. Giữ version ID riêng để lưu nhãn trạng thái văn bản.
- Thêm `benchmark_unit` để phân biệt nhãn chunk và nhãn cấp văn bản. `gold_document_version_ids` không được tính như chunk ID trong Recall@5/MRR@5.

## Giới hạn sử dụng

HN_048 có chunk theo chủ đề NĐ 126/2014, nhưng ngày hết hiệu lực của TT 07/2002 vẫn cần được đọc từ metadata version đi kèm; cần kiểm tra retrieval có trả metadata version hay không. HN_052 và HN_060 có chunk trong corpus cùng version ID ở trường riêng. HN_044 cần đọc metadata tiêu đề văn bản cùng chunk khi đánh giá quan hệ giữa Thông tư 38 và Nghị định 207. Các hàng còn lại vẫn là proposal chưa xác minh, không tự động trở thành gold đã được review. Không dùng file mới để tuyên bố điểm benchmark chính thức cho đến khi hoàn tất review các nhãn còn thiếu.



