# Sprint 12 — Bàn giao nhánh review

Nhánh `integration/sprint12-review` lấy `testing` tại `7d3c174` làm nền. Nền này đã có #63, #53, #61 và thay đổi #59 đi kèm. Các sửa đổi riêng về gateway, log, UI, truy vết parent, ngày tra cứu và audit holdout được chuyển sang nhánh review. Kết quả Dev30 từ #53, schema và cấu hình Test 30 giữ theo nền `testing`.

- Pytest toàn repo trên cây code của nhánh review: 1.935 đạt, 2 bỏ qua. Ruff theo cấu hình CI đạt.
- NFR3.3-AC1: Gitleaks v8.24.2 quét snapshot. Cục bộ, snapshot sạch trả 0 và fixture token giả ngoài repo trả 1. Ba giá trị giả cố định trong test auth được ngoại lệ theo cả đường dẫn và giá trị. Bước CI dùng checksum bản phát hành và che giá trị trong log. Còn thiếu bằng chứng GitHub CI và PR kiểm chứng check đỏ.
- FR1.8-AC1: audit đã tạo danh sách rà soát. Người kiểm độc lập cần xác nhận cặp `W16RH_011` và bằng chứng freeze trước lượt v6 lịch sử. Xem [báo cáo audit](router_holdout_similarity.md).
- FR6.1-AC1: `scripts/run_rag_batch.py` có preflight Ollama gửi HTTP trực tiếp ngoài gateway. Dev 3 cần xác nhận phạm vi giai đoạn và xử lý đường gọi hiện có trước khi kết luận tiêu chí.
- SRS 2.1.3 và BRD 2.1.1 nằm trên nhánh `spec/srs-2.1.3-testing`, đang chờ tích hợp riêng. FR3.4, FR5.6 và FR2.11 còn các điểm đặc tả hoặc contract cần chốt. NFR6.2 thuộc đợt 3, sau đợt 2 theo SRS mục 9.
- Live E2E, BO-04, BO-05 và NFR2.1 cần runtime và SHA `testing`. Test 30 official cần S12-DEC-01 và Top-50 đúng manifest. Chưa chạy lượt official.
