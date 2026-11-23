# Review cảnh báo metadata và alias — 23/11/2026

Đã duyệt phân loại toàn bộ **84 cảnh báo + 127 alias** của snapshot `05bc4ed`, đồng thời rà phần mới sau khi nhận lại NĐ 06/2012: hiện có **85 cảnh báo + 131 alias nhập nhằng**. Không xóa mục hợp lệ để giảm số cảnh báo.

## Quyết định

- Hoàn tất review chất lượng dữ liệu; chưa xác nhận thay Dev 2/Dev 3 và chưa chứng nhận hiệu lực pháp lý toàn bộ Điều/Khoản.
- 85 cảnh báo đều là `provision_effectivity_not_independently_verified`: giữ cờ cảnh báo vì xác minh cấp văn bản không tương đương xác minh toàn bộ provision. Từng văn bản có PDF/hash, số chunk, khoảng ngày, override và việc tiếp theo trong `metadata_warning_decisions.json`.
- 131 alias đều có ứng viên truy vết được từ registry, kết quả không có ngữ cảnh giữ `ambiguous` và không chọn document_id. Giữ toàn bộ ứng viên, không xóa luật lịch sử. Chi tiết từng alias, từng ứng viên, loại+năm và kết quả resolver trong `alias_decisions.json`.
- Không sửa dữ liệu pháp lý, alias sinh tự động, parser, chunker hoặc code. `review_status=pending_peer_review` của artifact vẫn được giữ đúng hợp đồng builder/loader; quyết định data review lưu riêng và gắn fingerprint để không áp dụng nhầm snapshot.

## Phân nhóm alias

| Nhóm | Số lượng |
|---|---|
| short_number_cross_authority | 3 |
| year_only | 34 |
| type_and_number_without_year | 48 |
| type_and_year | 40 |
| shared_title_or_short_title | 6 |

Alias mới do NĐ 06/2012: `nd 6`, `nd so 6`, `nghi dinh 6`, `nghi dinh so 6`.

## Kiểm tra

- Metadata audit hiện tại: 0 lỗi cấu trúc. Toàn bộ PDF của 85 văn bản được đối chiếu SHA-256.
- Tái dựng alias riêng theo từng văn bản để kiểm tra nguồn của mọi ứng viên; kiểm tra không ngữ cảnh, hint loại+năm và số hiệu đầy đủ/canonical ID/file code.
- `summary.json` ghi số lượt kiểm tra và fingerprint của snapshot. **60 test alias/metadata pass**; audit read-only PASS (0 lỗi, 85 cảnh báo, 131 alias). Kết quả ghi riêng trong `validation.json`.

## Phần chưa được coi là đóng

Cần tiếp tục xác minh pháp lý cấp Điều/Khoản, các thay cụm từ/bản trung gian và điều kiện chuyển tiếp đã nêu trong báo cáo provision trước đó. Không suy diễn `effective_to=null` là còn hiệu lực; không suy diễn `resolved` là văn bản áp dụng cho vụ việc. Alias chỉ có năm/loại+năm vẫn yếu ngay cả khi lọc còn một ứng viên.
