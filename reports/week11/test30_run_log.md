# Nhật ký lượt chạy Test 30 – Sprint 11 (Dev 5)

Theo D-12 (SRS 2.1.2, mục 8 "Quyết định kiến trúc", duyệt 20/11/2026, phương án A): KPI BO-02, BO-03 kết luận trên Test 30; Dev30 chỉ để theo dõi. Mỗi bộ prompt, model, ngưỡng đã đóng băng chỉ chạy Test 30 một lần. File này ghi mọi quyết định chạy hoặc không chạy; không sửa dòng cũ, chỉ thêm dòng mới.

| Ngày | Task | Tập | Quyết định | Lý do / căn cứ | Ảnh hưởng tới file cũ |
| --- | --- | --- | --- | --- | --- |
| 23/11/2026 | D5.2 | Dev30, Run B (`evaluation/results/dev/20261110_controlled_rag_qwen25_dev30/` và các lượt 13–14/11) | **NO REPLAY (D-12)** | Dev30 chỉ để theo dõi; kết quả 29 PASS / 1 ABSTAIN của lượt prompt v1.2 giữ nguyên. Verdict audit SHA precompute là việc của Dev 4 (D4.4), ghi vào hồ sơ run cũ khi có. | Không file nào trong `evaluation/results/dev/` bị sửa |
| 23/11/2026 | D5.5 | Test 30 (`docs/test_gold_freeze.json`, 30 ID, sha256 `59a9cdf0…8811`) | **NOT RUN, chưa đủ điều kiện** | Thiếu ba đầu vào bắt buộc: (1) validator manifest NFR4.2 của Dev 3 (D3.4, `run_metadata.py`) chưa có trên `testing` hay nhánh nào; (2) Tech Lead chưa ghi prompt version cho lượt Test 30 (mục 10.1 của kế hoạch); (3) Run B cần candidate Top-50 của 30 ID Test trên corpus `7105c484…` (precompute của Dev 4 hoặc retrieval live có manifest). Chạy khi thiếu các điều kiện này sẽ dùng mất lượt Test duy nhất của bộ cấu hình (D-12). | Không có |

## Điều kiện để chạy D5.5

1. `docs/test_gold_freeze.json` và `docs/test_run_config_freeze.json` khớp hash trên commit chạy (FR9.7-AC1, SRS 12.1).
2. Tech Lead ghi prompt version (v1.2 hiện hành hoặc bản mới của D3.3).
3. Validator D3.4 chấp nhận manifest của cả hai lượt.
4. Run A và Run B cùng model digest và tham số sinh; temperature 0; cache tắt; working tree sạch (`--require-clean-checkout`).
5. Mỗi lượt ghi vào `evaluation/results/test30/<run_id>/` mới, không ghi đè.

Nếu chưa đủ trước khi đóng Sprint 11, D5.5 chuyển sang Sprint 12 với trạng thái NOT RUN.
