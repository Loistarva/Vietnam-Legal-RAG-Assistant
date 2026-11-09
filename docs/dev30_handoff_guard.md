# D1.4 — Guard cho manifest Dev30 được bàn giao

Thực hiện 07/11/2026 trên nhánh chung `feature/week09-dev1-planning`.

## Đã có bàn giao của Dev 2

`origin/testing` đã nhận bộ Dev30 qua PR #32. Manifest được đưa vào lịch sử ở commit `02557bdf56ddfed02ca500ca7752456fe9c75428`, author **minhanhltnc**. Có các file:

- `evaluation/manifests/dev_gold_30_manifest.json`.
- `evaluation/datasets/dev_gold_30_queries_v1.json`.
- `evaluation/rubrics/dev_gold_30_ids_v1.txt`.
- `evaluation/review/dev30_confirmation_v1.json`.
- Rubric guide/score của Dev 2: `evaluation/rubrics/zero_shot_rubric_guide_v1.md` và `zero_shot_dev30_manual_scores_v1.csv`.

Manifest v1 vẫn giữ `proposed_pending_user_and_dev2_review` để bảo toàn phiên bản đề xuất. **File xác nhận riêng** có `status=confirmed_for_zero_shot_baseline`; file này được thêm tại commit `a7c6b766e2e15fb7f4573a385695b4a2b69c3d37` của Thang Nguyen (Dev 5), nội dung ghi xác nhận trên PR #32 và Dev 2 kiểm lại khi review. Không giả tên tác giả hoặc đổi status manifest để coi đó là xác nhận mới của Dev 1.

Đây là bàn giao/xác nhận **baseline zero-shot**, không tự chứng minh đã khóa prompt A/B, generation params, M1 hoặc có quyền chạy official A/B. D1.4 không đọc điểm/model output để chọn lại câu và không chạy inference.

## Các file Dev 1 thực hiện

- `evaluation/dev30_guard.py`: guard độc lập, stdlib-only, không cần Git history/network/model.
- `scripts/check_dev30_handoff.py`: CLI read-only, exit khác 0 khi fail.
- `test/evaluation/test_dev30_no_test_leakage.py`: đường dẫn canonical của D1.4; có test positive trên artifacts thật và các ca lỗi bằng fixture.

```powershell
python scripts/check_dev30_handoff.py
python -m pytest test/evaluation/test_dev30_no_test_leakage.py -q
```

Thiếu manifest, confirmation, ID file hoặc Gold không được skip/tự chọn lại 30 câu. Chỉ đọc các đường dẫn bàn giao canonical; không tìm một file proposal khác để cho test pass.

## Điều kiện kiểm tra

1. Đúng 30 ID duy nhất, đúng thứ tự giữa manifest, JSON và ID list; canonical query/ID hashes đúng.
2. Query giữ nguyên so với `queries_dev.json`, `split=dev`, ngày ISO/as_of_date không đổi; không đưa đáp án hoặc Gold vào input.
3. Gold selected có `source_checked`, full text đã kiểm, reviewed answer, mapping confirmed và reference answer không rỗng.
4. Không giao ID với Test; không trùng câu hỏi chuẩn hóa; không giao declared Gold clause **hoặc parent clause từ chunk**. Các chunk khác nhau cùng parent clause vẫn bị phát hiện. Không fallback parent thiếu thành chunk ID để che leakage.
5. Gold Test phải có đủ label/chunk/parent hợp lệ; thiếu/chệch mapping thì fail thay vì bỏ qua. Corpus không được có ID trùng.
6. Manifest selected Gold content fingerprint còn khớp. `source_git_blob_sha256` trong proposal là inventory baseline cũ; binding dữ liệu hiện tại dùng hashes LF-normalized trong confirmation của Dev 2/5. Không bắt current GT byte-equal proposal cũ khi thay đổi đã được xác nhận chỉ là metadata người duyệt.
7. Confirmation phải đúng scope/status/path/count/owner/date và đủ hashes cho query file, Dev source, current GT và corpus. Test questions/Gold phải khớp freeze/hash/ID list hiện tại.

Fail nêu reason code để sửa đầu vào cụ thể; guard không sửa manifest, dữ liệu hoặc re-freeze.

## Kết quả của tập được bàn giao

30/30 Dev đã duyệt; **44 Khoản / 45 chunk Gold duy nhất**; Test có 58 Khoản Gold duy nhất. Giao ID, câu hỏi chuẩn hóa, chunk và Khoản đều **0**. Dataset query canonical SHA-256 vẫn `7f413e19934b6b216c71c90482c27cd9a29e8556842a10fa7c22b505c1340421`; danh sách 30 câu giữ nguyên.

Nhánh planning đã được merge cập nhật từ `origin/testing` để kiểm chính các file bàn giao đang được nhóm sử dụng. Những sửa Gold/Test và re-freeze từ upstream được nhận qua merge, không phải D1.4 tự chỉnh Test; logs có hash trước/sau chứng minh guard chỉ đọc. Không thay dữ liệu đã chấm hoặc chạy lại holdout.

Kết quả test và provenance: `reports/data/dev30_handoff_d14_20261107.md` và raw JSON đi kèm. Reviewer theo kế hoạch: **Dev 2 + Tech Lead**. Guard PASS chứng minh điều kiện dữ liệu/leakage trong phạm vi này, không phải review pháp lý độc lập hay phê duyệt official evaluation.

## Cập nhật 08/11: tích hợp corpus mới

Hash toàn file Dev/Gold/corpus khác bản xác nhận chỉ sinh input_warnings, không chặn vì thay đổi ngoài Dev30. File 30 queries vẫn bị khóa; từng query phải bằng bản gốc trong Dev hiện tại; selected_gold_content_hash, gold chunk identity/content/effectivity theo dev30_selected_chunk_hashes_v1.json và Test questions/gold freeze vẫn bắt buộc. Fingerprint 45 chunk được đối chiếu từ e0cea35 tới testing mới, không thay đổi selection/confirmation của Dev 2/5.
