# Hiệu lực cấp điều/khoản — rà ngày 23/11/2026

Cập nhật bàn giao 24/11/2026: ba đề xuất vướng liên kết bằng chứng có [gói riêng cho người phụ trách code](../evidence_link_handoff_20261124/README.md), gồm vị trí nguồn/hash, lỗi tái hiện và tiêu chí nghiệm thu. Cả ba vẫn pending, chưa thêm vào override active.

Đã áp dụng thêm 13 bản ghi vào `data/reference/provision_periods.json`, tác động 26 child. Tổng số bản ghi đang dùng là 54. Active vẫn 84 văn bản; sau tách đúng Điểm/Khoản trích dẫn có 2.639 parent và 6.165 child, tăng 21 child. Không thay quy phạm trong parser, code, schema, test, Gold hoặc kết quả A/B chính thức.

Phần chạy được với code hiện tại:

- NĐ19/2011: Điều6 kết thúc ở bản sửa2019; điểm đ,e khoản1 Điều31 bị bãi bỏ2019; điểm g khoản1 Điều31 được thay2026; khoản1,3 Điều33 và khoản2,3,5 Điều34 kết thúc2025.
- NĐ24/2019 trung gian: khoản1 và3 Điều16 được trích trong khoản7 Điều1 kết thúc2025, giữ khoản2; toàn khoản8 Điều1 kết thúc2025.
- TT21/2011: điểm d,đ khoản1 Điều6 kết thúc2022; khoản2 Điều4 và khoản3 Điều9 kết thúc2025.
- TT10/2020: điểm c khoản1 Điều3 kết thúc2023; điểm a,b,d cùng khoản2 Điều3 kết thúc2025.
- TT07/2023 trung gian: khoản1 Điều1 (các Điểm thuộc Điều3 được sửa lại toàn bộ) kết thúc2025; không đóng toàn TT07.

`temporal_boundary_checks.json` ghi từng chunk và kiểm tra ngày trước mốc kết thúc/ngày kết thúc. `source_evidence.json` ghi PDF gốc, URL, SHA-256 và trang đã đọc. Có phân biệt số Khoản pháp lý và số Khoản parser đang gộp đoạn.

Phần dữ liệu đã chuẩn bị nhưng code hiện tại chưa tự áp dụng:

| Tệp | Nội dung | Giới hạn tích hợp |
|---|---|---|
| `data/reference/provision_text_changes.json` | 56 phép thay/bỏ câu chữ, 58 vị trí ký tự; có nguồn, câu chữ cũ/mới, ngày và SHA đoạn gốc | Chunker/retrieval chưa nạp tệp; không dùng để đóng cả Khoản |
| `data/reference/intermediate_provision_versions.json` | 4 vùng văn bản trung gian có vị trí và căn cứ sửa tiếp | Chưa có selector cho đoạn gộp nhiều Điều hoặc Khoản trích dẫn không liên tiếp |
| `technical_handoff.json` | 8 nhóm việc tích hợp, gồm căn cứ ở intro/tên Chương và nguồn ngoài active corpus | Không sửa code/test hoặc tạo evidence chunk giả để vượt kiểm tra |
| `mixed_parent_review.json` | 48 parent có child khác khoảng hiệu lực | Cần dựng ngữ cảnh theo child phù hợp thời điểm, không lấy cả parent vì parent có end=null |

Vị trí ký tự dùng Unicode code points trên đúng `clause_text` parser, không phải byte hoặc vị trí trên chunk. Tệp câu chữ chỉ là sổ thay đổi của phiên bản nguồn, không phải văn bản hợp nhất tự tạo. Mốc của một span không được khôi phục văn bản/Điểm đã kết thúc sớm hơn. Ví dụ điểm g khoản1 Điều31 NĐ19 thay chữ năm2025 rồi được thay toàn Điểm năm2026; hai mốc không nhập làm một. Vế phải một lệnh sửa đổi trung gian thay tiếp cũng không đồng nghĩa lệnh sửa đổi lịch sử bị xóa khỏi hệ thống pháp luật.

Có 2.328 child có ngày kết thúc và 3.837 child chưa xác định ngày kết thúc. Không có child nào được tự phê duyệt là hiện hành chỉ vì `effective_to=null`. `temporal_coverage.json` là báo cáo bao phủ, không phải allowlist pháp lý.

`chunk_migration.json` ghi 4 Khoản tách lại và các ID cũ dùng lại nhưng đổi nội dung phân mảnh. Phải xây lại index từ output mới; không tái sử dụng vector cũ theo ID. Production chunk index đã đồng bộ. Gold giữ nguyên; tham chiếu vào ID bị đổi mảnh cần người phụ trách benchmark duyệt lại, không tự sửa nhãn.

Bốn lần tìm literal không có trong các Khoản1–4 Điều13 NĐ19 được ghi là không có thay đổi cần áp dụng ở những vùng ấy, không phải bốn lỗi đang chờ. Các nhận xét cũ được giữ trong báo cáo lịch sử; kết quả mới xem tại thư mục này.

**Chưa thể coi mục hiệu lực đã hoàn tất ở runtime.** Phần thay cụm từ, bốn phạm vi trung gian và context parent cần dev phụ trách tích hợp; dữ liệu và căn cứ đã được chuẩn bị trong phạm vi Dev1. Các chuỗi sửa đổi khác vẫn cần duyệt pháp lý độc lập.

Kiểm tra: **2.260 passed, 1 skipped**; riêng hiệu lực70 test qua. Metadata audit0 lỗi,84 cảnh báo cấp điều/khoản và127 alias chờ duyệt. Manifest PDF, Ruff và negative-set qua (giữ cảnh báo baseline). Đối chiếu mọi Khoản trước/sau cho thấy giữ nguyên toàn bộ ký tự ngoài khoảng trắng; chỉ tách lại phân mảnh.
