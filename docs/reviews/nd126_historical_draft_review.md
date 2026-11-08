# Sửa thời điểm 26 câu draft NĐ126/2014 trên nền PR #36

Base: `2b0c043` (`fix/gold-context-300-rework`). Ngày kiểm: 08/11/2026.

## Quyết định

Chuyển đúng 26 câu có candidate thuộc Điều 19-50 NĐ126/2014 sang `historical_law`
và ngày hỏi 31/12/2015. Thời điểm lịch sử được viết rõ trong câu hỏi và đáp án,
không chỉ đổi trường metadata. Các Điều này bị bãi bỏ từ 01/01/2016 theo điểm đ
khoản 2 Điều 45 NĐ123/2015; ngày đã chọn nằm trước mốc này và sau ngày bắt đầu
hiệu lực của mọi candidate, kể cả Luật52/2014 ở HN_276/277.

Căn cứ: [NĐ123/2015 bản Chính phủ](https://vanban.chinhphu.vn/?pageid=27160&docid=182158),
Điều 45 khoản 1 và khoản 2 điểm đ; PDF Công báo trong repo trang 22 (trang in 23),
đã đối chiếu ở báo cáo PR #37.

Chọn hướng lịch sử để giữ chủ đề/căn cứ hiện có. Không gán quy định cũ cho năm
2026; không tự thay bằng một thủ tục hiện hành cần thêm văn bản ngoài corpus.

## Phạm vi

- 26 ID và trước/sau từng câu: `nd126_historical_draft_audit.json`.
- Giữ nguyên candidate, gold_context_ids rỗng, confirmed=false, draft và các
  trường verified_by/verified_at. Kiểm thời gian không đồng nghĩa duyệt đáp án
  pháp lý; các đoạn trả lời trích xuất vẫn cần biên tập/duyệt nội dung trước khi
  chuyển thành gold. Không tăng số Dev đã duyệt: vẫn 75 câu.
- HN_207 là sửa bổ sung từ review PR #35: bỏ tiêu đề chương lẫn trong đáp án,
  lấy đúng nội dung hai chunk khoản 1-2 Điều 18. Vẫn giữ draft/candidate.
- Sửa theo review PR #39: đáp án HN_225, HN_226, HN_232, HN_234, HN_236 có đuôi
  tên Điều ở đầu đoạn trích (HN_236 còn dính tiêu đề chương sau, HN_234 dừng ở
  "3."). Dựng lại từ đúng nội dung các candidate như HN_207; vẫn giữ draft. Các
  đáp án khác trong 26 câu vẫn là đoạn trích bị cắt ở khoảng 1.000 ký tự, cần
  biên tập khi duyệt.
- Không đổi Test, 75 câu Dev đã duyệt, corpus, cấu hình retrieval hoặc manifest
  Test. Không chạy lại Test. Kết quả retrieval lưu sẵn chưa được chạy lại cho
  các draft thay đổi; không chỉnh hash của kết quả cũ để giả khớp dữ liệu mới.

## Kiểm tra

- Mọi candidate của 26 câu đều qua bộ lọc tại ngày hỏi mới.
- Benchmark validator PASS, 0 lỗi.
- check_split --strict PASS, 0 lỗi, 0 cảnh báo.
- Kiểm lại Test questions/gold freeze và test regression cho dữ liệu draft.

## Việc còn lại

HN_063 đã xử lý trong commit tiếp theo của cùng nhánh; xem `hn063_candidate_narrowing.md`.
Hai câu chưa mapping HN_039/HN_048 chưa xử lý. HN_078 vẫn giữ nguyên vì đã source_checked; nhận xét biên tập
được ghi trong báo cáo review dữ liệu PR #35.
