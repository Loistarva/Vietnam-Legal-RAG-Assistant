# Rà hiệu lực hai luật nền

Tiếp sau commit `86bd45c`, đối chiếu thêm nguồn chính thức ngày 23/11/2026 cho Luật Bình đẳng giới và Luật Hòa giải ở cơ sở. Active giữ **84 văn bản và 6.135 chunks**; số văn bản có trạng thái chưa xác định giảm từ 35 xuống **33**. Không sửa parser/chunker, schema hoặc test.

## Metadata được sửa

**73/2006/QH11:** chuyển từ `Không xác định` sang `Sửa đổi bổ sung`. Bản hợp nhất 45/VBHN-VPQH, trang1 và6, ghi khoản3 Điều17 bị bãi bỏ theo khoản5 Điều29 Luật113/2025/QH15, hiệu lực01/07/2026. Điều17 đã ngoài whitelist active nên không mở rộng scope hoặc gán ngày kết thúc cho Điều khác. Giữ PDF bản gốc2006 để parse và bản hợp nhất để đối chiếu; không coi bản hợp nhất là một luật mới. PDF hợp nhất chủ yếu là ảnh: kiểm trang render trực tiếp, không OCR hay ingest bản scan.

**35/2013/QH13:** xác nhận còn hiệu lực tại ngày rà soát. Điều34 Luật16/2026/QH16 xác định mốc thay thế chung **01/03/2027**, được ghi vào `expiry_date`. Khoản2 Điều35 giữ việc tiếp tục áp dụng luật cũ cho vụ việc hòa giải chưa kết thúc trước mốc này. Registry ghi riêng ngoại lệ chuyển tiếp và giới hạn: runtime hiện dùng khoảng ngày chung, chưa mô hình hóa trạng thái từng vụ việc. Cần người duyệt kiểm tra riêng các câu hỏi về vụ việc chuyển tiếp sau01/03/2027; không khẳng định luật cũ hết áp dụng trong mọi tình huống.

PDF Công báo Luật16/2026 được giữ làm nguồn bằng chứng và ứng viên tương lai ngoài active; chưa nhận luật mới làm luật hiện hành trước01/03/2027. `metadata_changes.json` ghi đầy đủ trước/sau; `acquisition.json` ghi URL, SHA-256 và số trang; `integrity_checks.json` kiểm bảo toàn nội dung và ID.

## Bàn giao

`all_data_inventory.json` cập nhật **133 văn bản có tệp**:84 active,43 đang chờ,6 đã loại khỏi phạm vi; thêm3 ứng viên chưa có tệp thành136 mục theo dõi. `legal_review_queue.json` tiếp tục ghi33 trạng thái chưa xác định cùng các mục cần peer review. Báo cáo22/11 là snapshot trước lượt này.

Nguồn đối chiếu: [Bản hợp nhất Bình đẳng giới](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/3/45-vbhn-vpqh.pdf) và [Công báo Luật Hòa giải ở cơ sở mới, trang50](https://congbaocdn.chinhphu.vn/180507251028987904/2026/9/22/470451-1789729815_v1_1790039408_signed.pdf). Xem `validation_summary.json` và `tests_final.log` cho kết quả kiểm thử cuối.
