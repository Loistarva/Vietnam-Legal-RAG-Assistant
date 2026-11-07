# Kiểm tra file 30 câu Dev — 06/11/2026

## File bàn giao

`evaluation/datasets/dev_gold_30_queries_v1.json` — JSON array 30 query, giữ nguyên nội dung và metadata query từ baseline. Không chứa đáp án hoặc Gold. Hash canonical: `7f413e19934b6b216c71c90482c27cd9a29e8556842a10fa7c22b505c1340421`.

Trạng thái: **proposed_pending_user_and_dev2_review**. Có thể gửi file để người nhận kiểm tra input/chuẩn bị chạy; chưa tự xác nhận đây là official ID set đã Freeze hoặc cho phép chạy official A/B.

## Kiểm tra đã thực hiện

| Kiểm tra | Kết quả |
| --- | --- |
| Đúng 30 ID duy nhất, thứ tự đồng nhất JSON/manifest/TXT | PASS |
| Loại nguyên danh sách người dùng | 195 ID, giao tập được chọn = 0 |
| Không chọn HN_078 có lỗi gõ | PASS |
| Không chọn query/Gold đang đổi nội dung giữa baseline và D1 head | PASS |
| Mọi câu thuộc Dev source_checked/full_text_checked/reviewed_answer, provenance đầy đủ | PASS |
| Test ID/câu hỏi chuẩn hóa/Gold clause leakage, baseline và D1 head | Không giao |
| Không dùng chunk/document mới của PR #25 | Loại 9 chunk, 4 document; không ID nào được chọn phụ thuộc chúng |
| Gold chunk tồn tại, đủ child chunk của Khoản; hierarchy/Điều/Khoản/citation mapping khớp | PASS |
| Gold nằm trong khoảng hiệu lực metadata tại ngày hỏi | PASS; ngày kết thúc là cận loại trừ |
| Model input không có đáp án/Gold, nội dung query không bị biên tập lại | PASS |
| Loader zero-shot metrics mới nhất lúc kiểm tra | Đọc đủ 30; 0 model calls |
| Test riêng selection | 32 passed |
| Full pytest theo pytest.ini | 674 passed, 1 skipped |
| Benchmark handoff validator | PASS, 270 Dev/30 Test, issues=0 |
| Freeze Test questions và Test Gold | PASS, không đổi |

Raw stdout/stderr/exit code: `dev30_validation_checks_v1.json`. Loader source SHA/hash và kết quả: `dev30_loader_compatibility_v1.json`. Mọi lệnh kiểm tra ghi trong log đều exit 0. Full suite chạy offline/fixtures; skipped không tính là pass. Không chạy inference, không dùng output model hoặc metric để chọn câu.

Tests hồi quy có ca cố tình: ID bị cấm, khoảng ID sai/trùng, chọn Test, trùng Khoản Test, câu hỏi trùng Test, nhét answer vào input, sửa ngày, Gold chưa duyệt/sai split, query/answer đang đổi ở D1, dùng chunk/document thêm, mất chunk, sai hierarchy/citation, thiếu chunk nối tiếp và vượt ngày hết hiệu lực. Các fixture sửa trong bộ nhớ; không thay benchmark thật.

## Rà soát nội dung

Đã đọc 30 câu, đáp án và chunk tương ứng trong repo để chọn các trường hợp có nguồn trực tiếp, ổn định. File `dev_gold_30_selection_review_v1.md` giữ toàn bộ nội dung này để người dùng kiểm tra từng câu; không gán thêm trạng thái đã được con người duyệt.

HN_035 là ca bẫy luật cũ duy nhất. Gold dùng Điều 8 khoản 2 Luật 52/2014 trong corpus cũ; registry ở SHA baseline ghi Luật 22/2000 có `expiry_date=2015-01-01`, trước ngày hỏi 2026-10-15. Đây là kiểm tra metadata kế thừa, không phải xác minh mới toàn bộ lịch sử hiệu lực ngoài hệ thống.

Không chọn HN_288 không có nghĩa kết luận câu này sai; đợt này ưu tiên câu có phần đáp trực tiếp hơn, không cần mở rộng review ví dụ về hình thức giao dịch. Các câu khác không được chọn có thể vẫn hợp lệ; phân biệt lý do loại kỹ thuật với việc không nằm trong mẫu 30.

## Giới hạn và bàn giao

- Mẫu đề xuất bảo thủ: 8 chủ đề, nhưng toàn bộ Gold từ một luật; không đại diện đầy đủ mọi văn bản hoặc temporal test type của Dev. Một số câu chung Khoản, không phải 30 mẫu chứng cứ độc lập.
- Không kiểm HTTP/redirect toàn bộ URL legacy; người duyệt có thể đối chiếu [trang luật chính thức](https://vanban.chinhphu.vn/default.aspx?docid=175351&pageid=27160). Không sửa Gold/URL/Test để làm subset này.
- Đã chặn các nhóm lỗi cụ thể nêu trên, không thể chứng minh không còn mọi lỗi ngữ nghĩa hoặc pháp lý. Dev 2/người dùng cần duyệt cuối và chốt rubric/prompt/date policy/params/Freeze trước official A/B.
- `remaining_reviewed_dev_ids` là phép trừ ID, không phải danh sách tự động phê duyệt để calibration. Cần kiểm các câu đang sửa trong nhánh D1.
- Không sửa canonical Dev/Test, ground_truth, corpus, config hay freeze manifest. Nhánh chuẩn bị: `feature/week09-dev30-selection`; chưa commit/push tại thời điểm lập báo cáo.
