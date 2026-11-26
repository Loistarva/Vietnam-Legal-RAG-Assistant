# Rà soát PR #53 — chấm Dev Gold 30 của Dev 4

Ngày kiểm: 26/11/2026, Asia/Saigon. **Đề xuất đóng PR với lý do nội dung đã được đưa vào testing qua các commit khác.** Không cần rebase/merge lại bộ điểm này. Báo cáo chuẩn bị local; chưa đăng comment, chưa đóng hoặc sửa PR.

## Trạng thái và phạm vi

- [PR #53](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/53): `Complete A/B Evaluation Scoring for Dev Gold 30 - DEV4`, đang OPEN, chưa merge.
- Head `ab-evaluation-scoring-integrity`: `f4fa6c6ff8844265faacebdaa42aee269a1d76a2`; một commit riêng, ba file thay đổi (+152/-61 dòng, gồm XLSX).
- HEAD `testing` xác minh trực tiếp bằng `git ls-remote`: `c266983c9a5b6d802f8ff87f5036c9637fd3a9ac`. Đã fetch nhánh và đối chiếu với local remote ref.
- Merge-base: `c1e9f12be503f05f07aeaca76bc1d06cd9c85d3c`. API PR trả base SHA này; không dùng nó thay HEAD testing hiện tại.
- GitHub báo `mergeable=true`, `mergeable_state=clean`. Mô phỏng `git merge-tree --write-tree` trên hai HEAD trên thành công, exit 0, tree `43de9e10de420c990a8726dc1ae47ea9c427a1d7`. Không checkout, merge vào nhánh hoặc thay working tree. Không có xung đột kỹ thuật được phát hiện; vẫn có vấn đề trùng nội dung và vị trí lưu.
- Hai check `pytest` trên head PR đều success. Đây là kết quả CI lịch sử của head, không phải một lượt CI mới trên merge với testing hiện tại. API không có formal review; có một comment review ngày 16/11, không xem comment đó là approval.

## Nội dung còn giá trị và phần đã được tích hợp

| File trong PR | Bản tương ứng đã có trên testing | Kết luận |
| --- | --- | --- |
| `evaluation/results/dev/blinded_ab_scoring_v1.csv` | `evaluation/results/dev/Blind_scroring/blinded_ab_scoring_v1_dev4.csv` | Trùng từng byte; SHA-256 cả hai `b0f84ccf3f822ba842b78838166823ee8c0a3fe5e90d940f50fcff375abc3017` |
| `evaluation/results/dev/blinded_ab_scoring_v1.xlsx` | `evaluation/results/dev/Blind_scroring/blinded_ab_scoring_v1_dev4.xlsx` | Trùng từng byte; SHA-256 cả hai `1219632646523dae740705a08065a9cf6c820af7162812b545ee3aadd157cbbb` |
| `evaluation/results/dev/context_faithfulness_b_only_v1.csv` | `evaluation/results/dev/Blind_scroring/context_faithfulness_b_only_v1.csv` | Cùng 30 Query ID; mọi ô của các cột chung bằng nhau. PR có thêm cột `Blind ID` |

Commit `34ce14c89748a916ac6aa3b462aa01e2aff2030e` đã đưa phiếu Dev4 vào thư mục theo từng rater. Commit `d07de3cd2d27ecd31372cfede0e5c7856e9d4c61` thêm phiếu Dev3, tổng hợp và báo cáo Dev30. Commit `39e33cdd` bỏ Blind ID ở các file kết quả liên quan. Các commit này đã thuộc lịch sử testing.

Giá trị của PR là điểm/rationale gốc Dev4 và Context Faithfulness B-only. Các dữ liệu này đã được giữ trên testing; đóng PR không làm mất phần chấm Dev4. Không đánh giá lại nội dung pháp lý hoặc tự sửa điểm trong lượt rà soát này.

## Kiểm dữ liệu độc lập

Kiểm trực tiếp blobs tại hai SHA bằng Python CSV parser và đọc XML bên trong XLSX, không sửa workbook hoặc score:

- Phiếu mù: 60 dòng, 60 Blind ID duy nhất, 13 cột; Grader đều Dev4; ngày đều `2026-10-15`.
- Bảy cột đầu vào so với phiếu chung trên testing: 0 ô thay đổi. Các trường chấm/rationale đều đủ; AR/LC đều trong 1–5.
- CSV và sheet XLSX của PR khớp toàn bộ giá trị, gồm header và 60 dòng.
- XLSX PR có sheet `Blind Scoring`; template chung testing có `Blind scoring` và `Quick guide`. Merge PR sẽ thay workbook chung bằng bản Dev4 thiếu Quick guide. Không chỉnh workbook vì không có dữ liệu mới cần tích hợp.
- B-only: 30 dòng; 29 điểm số và một N/A; các giá trị 5/4/3/1 có số lượng 22/2/4/1. Bản testing giữ nguyên điểm, answer, payload, rationale, provenance và grader so với PR, chỉ không có cột Blind ID.
- JSON kết quả đối chiếu: [pr53_review_checks.json](pr53_review_checks.json). Hash so sánh là bytes gốc trong Git, không chuẩn hóa LF.

Không đọc mapping riêng hoặc mở điểm Test 30. Không suy ra tính độc lập lịch sử chỉ từ nhãn Grader hoặc điểm đầy đủ. Không chạy lại Qwen/retrieval. Không kiểm giao diện hiển thị Excel vì không chỉnh workbook; kiểm tính đồng bộ dữ liệu qua XML.

## Lý do đề xuất đóng

1. Không có điểm Dev4 mới cần merge: CSV và XLSX đã được bảo toàn nguyên byte tại đường dẫn theo rater.
2. Merge sẽ ghi điểm Dev4 vào đường dẫn chung `blinded_ab_scoring_v1.*`, làm khó phân biệt template/phiếu từng người, đồng thời bỏ sheet hướng dẫn của workbook chung.
3. Phiếu B-only tạo thêm ở thư mục chung sẽ lặp lại dữ liệu đã có và khôi phục cột Blind ID vốn được bỏ khỏi bản kết quả trên testing. Không cần thêm bản này để bảo toàn điểm.
4. Báo cáo tổng hợp Dev30 đã có ở `reports/evaluation/week09_zero_shot_vs_rag_20261116.md`. PR không bổ sung code, metric hoặc phương pháp tổng hợp mới.

Theo S12-D4.1, lựa chọn phù hợp là **đóng có lý do**, thay vì cập nhật/rebase một PR có nội dung đã được tích hợp. Không khẳng định PR #53 đã merge; ghi rõ đã được thay thế bởi các commit nêu trên.

## Nội dung sẵn để dùng khi đóng PR

> Đề xuất đóng PR #53 vì phần chấm Dev4 đã được tích hợp vào testing qua commit 34ce14c8 và phần tổng hợp tại d07de3cd. Kiểm trên testing c266983c và head PR f4fa6c6f xác nhận CSV/XLSX Dev4 trong PR trùng từng byte với các file `Blind_scroring/blinded_ab_scoring_v1_dev4.*`. Phiếu B-only cũng khớp toàn bộ 30 câu và các cột chung; bản testing đã bỏ cột Blind ID. Vì vậy không còn dữ liệu chấm mới cần merge. Giữ bộ điểm theo rater và báo cáo Dev30 hiện có trên testing; tránh ghi đè workbook chung hoặc tạo thêm bản kết quả trùng. PR được đóng do nội dung đã tích hợp qua commit khác, không phải loại bỏ kết quả chấm Dev4.

Đây là bản nháp local. Người có trách nhiệm có thể dùng nội dung trên để đóng PR và cập nhật S12-D4.1. Nếu các SHA remote đổi sau thời điểm rà soát, cần đối chiếu lại trước khi thực hiện.
