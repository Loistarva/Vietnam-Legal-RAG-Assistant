# KẾT QUẢ KIỂM TRA BẢN SỬA BENCHMARK 300 CÂU

Ngày: 16/10/2026 | Hình thức: **đóng gói để review trên GitHub, chưa được nghiệm thu Gold**.

| Kiểm tra | Kết quả |
|---|---|
| Số câu hỏi | 300 = 285 Dev + 15 Test |
| Số Ground Truth | 300, toàn bộ `draft` |
| Nhãn Gold production đã xác nhận | **0/300** |
| Chunk smoke chuyển sang `candidate_context_ids` | 34 câu |
| Candidate chưa đủ căn cứ | 2 câu |
| Chưa được map chunk | 264 câu |
| Đáp án dạng đoạn trích PDF cần viết lại | **240 câu** |
| Câu có cảnh báo cách hỏi có thể quá chung | **50** (đây chỉ là cảnh báo) |
| Đáp án nghi dính tiêu đề chương PDF | **4** (cần xem bản gốc) |
| Unit test | **41/41 PASS** |
| Test questions freeze | **PASS**, SHA-256: `0b4b3a2f75a02ace122333fedddb45a8b36229217841619ea55107c36cacdbdf` |
| `validate_benchmark.py` chế độ handoff | **PASS** |
| `validate_benchmark.py --final` | **FAIL ĐÚNG THIẾT KẾ**, chờ duyệt và Gold thật |

## Tài liệu đáng xem trước khi gửi lead

- `docs/quality_review_priorities_dev.csv`: bảng Dev có số cờ rủi ro từng câu, không phải bảng đã chấm đúng sai.
- `docs/REVIEW_VA_GIT.md`: tách PR Benchmark khỏi PR Parser #2.
- `docs/sprint6_benchmark.md`: yêu cầu, hướng dẫn validator/freeze và tình trạng còn thiếu.
- Bộ bảng review **Test** được đóng riêng trong ZIP `BENCHMARK_SPRINT6_TEST_REVIEW_RIENG.zip`.

## Cảnh báo quan trọng

1. Không ghi 240 trích đoạn PDF thành "300 câu đã có đáp án chuẩn".
2. Không dùng Gold trong production trước khi chunk mapping được nhóm Chunking xác nhận bằng index thực tế và xác minh nguồn, hiệu lực điều/khoản.
3. `data/benchmark/ground_truth.json` theo contract yêu cầu vẫn bao gồm nhãn Test; nếu các thành viên tối ưu mô hình nhìn được repo thì Test không còn là holdout bí mật. Phải kiểm soát quyền đọc hoặc kiến trúc dữ liệu khi sử dụng để chấm điểm chính thức.
4. Không tự động merge Pull Request vào main.
