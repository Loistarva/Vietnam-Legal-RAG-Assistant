# Bổ sung căn cứ từ PDF nguồn cho 240 câu mới – bản nháp cần duyệt

Đã thay 240 giá trị `answer=CHUA_XAC_MINH...` bằng **đoạn trích PDF nguồn**, không còn ô đáp án placeholder đối với 240 câu bổ sung. Đoạn trích là bằng chứng máy trích xuất, **không phải đáp án pháp lý cuối cùng**, có thể chưa bao quát toàn bộ điều luật. Mã Điều (`gold_article_ids`) được ánh xạ theo `data/reference/article_index.json`, không phải mã chunk.

**Không có `gold_context_ids` production được xác nhận** cho 240 câu mới. Không được tính Recall/MRR/nDCG trên toàn bộ 300 câu khi chưa rà soát và duyệt nhãn. 60 câu ban đầu vẫn ở trạng thái `draft`; 15 câu Test và manifest freeze nguyên vẹn.

File kiểm tra nguồn: `docs/answer_source_audit.csv`. File để người review điền: `docs/ground_truth_review_sheet.csv`. Nguồn PDF đã sử dụng: `L01.pdf` (bản hợp nhất 2025, chỉ 131 điều), `ND01.pdf`, `ND02.pdf`, `ND03.pdf` được cung cấp trong phiên làm việc; **không được gói trong ZIP** để tránh tăng dung lượng/tạo bản sao dữ liệu gốc của nhóm. Các tài liệu này không chứng minh mọi quy định còn hiệu lực ở cấp điều khoản vào 2026.

---

# Báo cáo mở rộng Benchmark lên 300 câu — 16/10/2026

## 1. Kết quả

| Thành phần | Số lượng | Trạng thái |
| --- | ---: | --- |
| Câu hỏi gốc | 60 | Giữ nguyên nội dung, Test không đổi |
| Câu hỏi mới theo tiêu đề Điều | 215 | Chỉ có nguồn gợi ý từ metadata — chưa xác minh đáp án |
| Câu hỏi mới multi-hop | 25 | Ghép hai điều cần đối chiếu — chưa xác minh đáp án |
| **Tổng** | **300** | **285 Dev / 15 Test** |

**QUAN TRỌNG:** Với 240 câu mới, `answer` đã có trích xuất PDF tự động để người review đối chiếu, nhưng CHƯA phải đáp án pháp lý được duyệt. `gold_article_ids` đã được ánh xạ tới mục Điều trong metadata, còn `gold_context_ids = []`, `mapping_status = not_mapped`, `review_status = draft`; dẫn chiếu `citations` chỉ là đầu mối kiểm tra. Các câu này **không đủ điều kiện tính Recall/MRR/nDCG** cho đến khi gán Gold, xác minh nội dung, nguồn và ID chunk của production index.

## 2. Nguồn câu hỏi

Bản mở rộng sử dụng **chỉ** `data/reference/article_index.json` trong ZIP gốc và ghép nội dung dựa trên tên Điều. Không dùng website mới, không tự giả định nội dung điều/khoản hoặc hiệu lực pháp lý. Cụ thể:

- Luật Hôn nhân và gia đình 2014: 131 Điều đưa vào ngân hàng câu hỏi.
- Nghị định 126/2014/NĐ-CP: 55 Điều đưa vào ngân hàng câu hỏi.
- Nghị định 207/2025/NĐ-CP: 17 Điều đưa vào ngân hàng câu hỏi.
- Nghị quyết 01/2024/NQ-HĐTP: 12 Điều đưa vào ngân hàng câu hỏi.

- Không sinh câu từ `L01_D132` và `L01_D133` vì PDF L01 trong pipeline hiện thiếu hai Điều này.
- Metadata `article_index.json` của ND01 mới có 55 tiêu đề; có thể cần đồng bộ lại với parser 67 điều.
- ND01 có trạng thái hết hiệu lực **một phần** trong registry; phải kiểm chứng hiệu lực đúng điều/khoản trước khi chốt nhãn.
- Chưa sử dụng Thông tư trong 240 câu mới vì bộ chunking hiện báo cáo mới xử lý 7 PDF luật/nghị định/nghị quyết, chưa xác thực corpus Thông tư.

## 3. Phân bố câu hỏi (300)

### Chủ đề

| Chủ đề | Số câu |
| --- | ---: |
| `tai_san` | 58 |
| `ket_hon` | 40 |
| `con_cai` | 38 |
| `ly_hon` | 38 |
| `nguyen_tac_quy_dinh` | 27 |
| `mang_thai_ho` | 26 |
| `hieu_luc` | 25 |
| `cap_duong` | 21 |
| `vo_chong` | 15 |
| `thu_tuc` | 6 |
| `yeu_to_nuoc_ngoai` | 6 |

### Loại câu

| Loại | Số câu |
| --- | ---: |
| `situation` | 185 |
| `fact` | 90 |
| `multi_hop` | 25 |

### Nhóm kiểm thử

| Nhóm | Số câu |
| --- | ---: |
| `current_law` | 219 |
| `partially_expired` | 59 |
| `outdated_law_trap` | 16 |
| `historical_law` | 6 |

## 4. Cách sử dụng an toàn

1. Dùng 300 câu cho bước xây dựng **ngân hàng câu hỏi / review chủ đề**.
2. Dùng **chỉ các câu đã được xác minh Gold/ID production** để đánh giá định lượng retrieval. Hiện cả 60 bản gốc cũng mới là bản draft, không được kết luận chính thức chỉ vì validator PASS.
3. Với mỗi câu mới: mở văn bản nguồn tương ứng, kiểm chứng câu hỏi có ý nghĩa, biên soạn `answer`, `explanation`, xác nhận citation ở cấp điều/khoản và trạng thái hiệu lực tại `as_of_date`.
4. Gắn `gold_article_ids`, `gold_context_ids` từ **chunk thực tế của nhóm** (không dùng ID giả hoặc chunk smoke chưa xác nhận). Ghi người và ngày review, cập nhật `review_status`.
5. Các ví dụ thực nghiệm nên nêu rõ số mẫu **gold-verified** thay vì lấy tổng 300 làm mẫu hợp lệ.

## 5. Test freeze và kiểm thử

- File `queries_test.json` vẫn là bản 15 câu gốc, hash không đổi. Không tự ý trộn câu Dev mới vào Test.
- `scripts/validate_benchmark.py` cập nhật giới hạn trên từ 100 thành 300, còn các quy tắc kiểm tra ID, nguồn, ngày và trạng thái mapping giữ nguyên.
- `tests/test_benchmark.py` cập nhật số liệu lên 300 và có kiểm tra mới rằng 240 câu chưa được đánh dấu xác minh giả.
- `docs/manual_review.csv` có checklist cho cả 300 câu.
- **Chỉ khi gold đã được duyệt** mới chạy `python scripts/validate_benchmark.py --final` và đóng băng Test Gold.

## 6. Ghi chú cho lead

> Đã mở rộng từ 60 lên 300 câu, giữ nguyên 15 câu Test đóng băng. Trong 240 câu mới, có 215 câu theo từng Điều và 25 câu cần đối chiếu hai Điều. Đây là **bộ câu hỏi dự thảo**; cần review/hoàn thiện Ground Truth và mapping chunk trước khi được xem là benchmark đánh giá retrieval chính thức. Không báo có 300 gold đã xác minh.
