# Kiểm tra gần trùng Router holdout v6

**Yêu cầu: FR1.8-AC1. Trạng thái: đã kiểm tự động, chờ review độc lập.**

Báo cáo cung cấp bằng chứng để reviewer đánh giá tính độc lập của holdout v6 so với các nguồn đã có trong repo. Kiểm tra xác nhận 36 bản ghi hợp lệ, không có câu trùng nguyên văn và có một cặp vượt ngưỡng rà soát gần trùng. Chưa kết luận holdout không chồng lặp ngữ nghĩa. Giữ nguyên dữ liệu v6, nhãn đã được chấp thuận và kết quả lịch sử 34/36; lần kiểm này không chạy Router để dự đoán lại.

## Mốc kiểm tra và cách tái lập

| Thuộc tính | Giá trị |
| --- | --- |
| Ngày kiểm tra | 25/11/2026, theo múi giờ Asia/Saigon |
| Nhánh làm việc | `feature/sprint12-dev4-Router-Retrieval-and-Knowledge-Base` |
| HEAD của baseline | `c266983c9a5b6d802f8ff87f5036c9637fd3a9ac` |
| Holdout được kiểm | `evaluation/router_holdout/router_holdout_week10_v6.jsonl` |
| Script gần trùng | `scripts/audit_router_holdout_similarity.py`, lấy từ `origin/integration/sprint12-local` tại `c3a9622f`; được thêm vào working tree, chưa thuộc HEAD nêu trên tại lúc chạy |
| Thay đổi dữ liệu để kiểm | Không sửa holdout, nhãn, luật Router hoặc kết quả đánh giá cũ |

Chạy tại thư mục gốc repo, trong môi trường Python của dự án:

```powershell
python scripts/validate_router_holdout.py --holdout evaluation/router_holdout/router_holdout_week10_v6.jsonl
python scripts/audit_router_holdout_similarity.py
```

Phải truyền rõ `--holdout` cho validator: giá trị mặc định của script này là bộ cũ `test/agent/data/router_holdout_independent_v1.jsonl`, không phải v6. Script gần trùng hiện chọn trực tiếp v6 trong mã nguồn.

## Phương pháp và phạm vi

Kiểm trùng nguyên văn chuẩn hóa Unicode NFC, chữ thường và khoảng trắng rồi đối chiếu toàn bộ câu hỏi. Kiểm gần trùng chuẩn hóa chữ thường, bỏ dấu tiếng Việt, tách token theo khoảng trắng/dấu câu; tính tỷ lệ tương đồng ký tự bằng `SequenceMatcher` với `autojunk=False` và Jaccard trên tập bigram token.

| Phép đo | Ngưỡng gắn cờ |
| --- | ---: |
| Tương đồng ký tự | ≥ 0,82 |
| Jaccard bigram token | ≥ 0,65 |

Một cặp được gắn cờ nếu đạt ít nhất một ngưỡng. Các ngưỡng là ngưỡng sàng lọc, không được diễn giải thành kết luận về độc lập ngữ nghĩa.

| Nguồn đối chiếu | Số mục |
| --- | ---: |
| `test/agent/data/router_holdout.jsonl` | 40 |
| `test/agent/data/router_holdout_independent_v1.jsonl` | 36 |
| `evaluation/router_holdout/router_holdout_week10_v1.jsonl` đến `v5.jsonl` | 180 |
| `data/benchmark/queries_dev.json` | 270 |
| `evaluation/negative_set/dev_negative_queries_v2.jsonl` | 26 |
| Chuỗi trong `test/agent/test_rule_router.py` | 286 |
| Chuỗi trong `agent/router/rule_router.py` | 757 |
| **Tổng 11 nguồn** | **1.595** |

Tổng cộng 36 × 1.595 = **57.420 cặp** được sàng lọc. Với Python, script dùng AST lấy các hằng chuỗi và vị trí dòng; một mục có thể là câu hỏi, thông báo hoặc chuỗi biểu thức chính quy. Việc so sánh chuỗi regex không kiểm toàn bộ câu mà regex có thể khớp. Phương pháp có thể bỏ sót cách diễn đạt đồng nghĩa và không tự chứng minh nguồn gốc hoặc thời điểm tạo câu hỏi.

## Kết quả tự động

| Kiểm tra | Kết quả |
| --- | --- |
| Schema và kiểm trùng nguyên văn v6 | `VALIDATION PASSED`, exit code 0 |
| Bản ghi hợp lệ | 36/36 |
| Phân bố route | `LEGAL_HNGD`: 10; `LEGAL_OUT_OF_SCOPE`: 8; `LEGAL_SCOPE_UNCERTAIN`: 6; `MIXED_LEGAL_SCOPE`: 6; `NON_LEGAL`: 6 |
| Trùng nguyên văn với nguồn đối chiếu | 0 |
| Lỗi validation trong script gần trùng | 0 |
| Cặp vượt ngưỡng | 1 |
| Script gần trùng | Hoàn tất, exit code 0; vẫn cần kết luận của reviewer |

## Cặp cần reviewer đánh giá

| Thuộc tính | Holdout | Nguồn đối chiếu |
| --- | --- | --- |
| Vị trí | `W16RH_011`, dòng 11 của [holdout v6](../../evaluation/router_holdout/router_holdout_week10_v6.jsonl) | Dòng 360 của [test Router](../../test/agent/test_rule_router.py) tại SHA baseline |
| Nội dung | Doanh nghiệp vi phạm quy định về tập trung kinh tế và cạnh tranh không lành mạnh có thể bị áp dụng biện pháp xử lý nào? | Doanh nghiệp vi phạm quy định về tập trung kinh tế và cạnh tranh không lành mạnh bị xử lý thế nào? |
| Expected route | `LEGAL_OUT_OF_SCOPE` | `LEGAL_OUT_OF_SCOPE` |
| Expected action | `POLICY_ABSTENTION` | `POLICY_ABSTENTION` |

| Phép đo | Điểm | Vượt ngưỡng |
| --- | ---: | --- |
| Tương đồng ký tự | 0,865 | Có, ≥ 0,82 |
| Jaccard bigram | 0,567 | Không, < 0,65 |

**Nhận xét sơ bộ phục vụ review:** hai câu có cùng chủ đề, cùng route/action kỳ vọng và phần lớn câu chữ giống nhau; khác biệt chủ yếu nằm ở cách hỏi về biện pháp xử lý. Đây là dấu hiệu cần xem xét khả năng diễn đạt lại cùng một tình huống. Nhận xét này chưa thay thế kết luận độc lập của reviewer và không chứng minh câu nào được tạo trước hoặc lấy từ câu nào.

Reviewer cần xác định:

1. Khác biệt giữa hai câu có tạo ra tình huống hoặc điều kiện quyết định route mới không, hay chỉ thay cách diễn đạt?
2. Có bằng chứng về thời điểm tạo, nguồn gốc câu hỏi và việc sử dụng câu regression khi xây dựng holdout không? Nếu thiếu, ghi rõ chưa xác minh được; không suy ra trình tự chỉ từ ngày đồng bộ metadata.
3. Kết quả đối chiếu hỗ trợ hay giới hạn thế nào đối với tuyên bố tính độc lập của holdout v6? Có cần bổ sung nguồn hoặc phương pháp rà soát không?

## Hash và phân biệt bằng chứng lịch sử

Hash bên dưới dùng SHA-256 trên bytes sau chuẩn hóa CRLF → LF. Đây là hash tại mốc kiểm tra, không phải tất cả đều là hash tại lượt dự đoán lịch sử.

| Đối tượng | SHA-256 LF |
| --- | --- |
| Holdout v6 hiện tại | `b9eeb081552b0eaf87326fd86f9426818aee615c8e70b5fd96857c8effd670b8` |
| Source Router hiện tại | `081152e3e71795454b702c57092987703bd281f943cdfc3b740076a393780067` |
| Test Router được đối chiếu | `c868129c653dbbdf2c76ecb3a24aaf7019ad52eb1678fbc49c7fd7f9ca8c986d` |
| Script validator | `97e4aaff6d8c34e6717d18f996b073c0dd1e17ff03c83d662640370132bc82bc` |
| Script kiểm gần trùng | `fd0156869c4401131fab4524edbaa88ad9563172633e107b3b0963d23cc851fb` |

Theo [hồ sơ v6](../../evaluation/router_holdout/router_holdout_week10_v6.md), source Router tại lượt đánh giá lịch sử có hash LF `996bd6a0894aeaf964f188f032961329ec6cdecfe1575bcf80df685aa068f2f7`, khác source hiện tại. Không gán lại kết quả 34/36 cho source hiện tại. Metadata `INDEPENDENT_REVIEW_COMPLETE` của v6 ghi nhận review nhãn trước đây theo xác nhận của project owner; không thay thế review gần trùng trong báo cáo này. Hồ sơ vẫn ghi `review_date=null` và `review_before_prediction=null`.

## Phiếu kết luận review độc lập

**Reviewer điền trực tiếp phần này. Các ô hiện để trống, chưa có sign-off.**

| Thông tin | Reviewer điền |
| --- | --- |
| Họ tên hoặc ID reviewer | Chưa điền |
| Vai trò và xác nhận độc lập với người tạo gói kiểm tra | Chưa điền |
| Ngày review | Chưa điền |
| SHA commit chứa báo cáo và script đã review | Chưa điền sau khi commit |
| Đã đối chiếu hash holdout và nguồn | Chưa điền |
| Kết luận cặp `W16RH_011` ↔ test dòng 360 | Chọn một: **ĐỘC LẬP / GẦN TRÙNG NGỮ NGHĨA / CHƯA ĐỦ BẰNG CHỨNG** |
| Lý do, chỉ rõ khác biệt hoặc nội dung trùng ý nghĩa | Chưa điền |
| Bằng chứng nguồn gốc/thời điểm hoặc giới hạn chưa xác minh | Chưa điền |
| Nhận xét về phạm vi và giới hạn của phép kiểm | Chưa điền |
| Đề xuất xử lý FR1.8-AC1 | Chưa điền |
| Tham chiếu review hoặc chữ ký xác nhận | Chưa điền |

Nếu kết luận **ĐỘC LẬP**, reviewer giải thích khác biệt có ý nghĩa đối với trường hợp kiểm thử; vẫn ghi giới hạn của phương pháp. Nếu kết luận **GẦN TRÙNG NGỮ NGHĨA**, chuyển Tech Lead quyết định cách xử lý và phản ánh giới hạn vào báo cáo nghiệm thu. Nếu **CHƯA ĐỦ BẰNG CHỨNG**, liệt kê thông tin còn cần và người cung cấp.

## Trạng thái bàn giao và điều kiện đóng

- [x] Chọn đúng holdout v6, kiểm 36 bản ghi và đủ 5 nhóm route.
- [x] Chạy kiểm trùng nguyên văn và gần trùng; ghi phương pháp, ngưỡng, phạm vi, cặp bị gắn cờ và hash.
- [x] Giữ nguyên holdout, luật Router và kết quả lịch sử.
- [ ] Commit báo cáo cùng script; ghi SHA được review vào phiếu.
- [ ] Reviewer độc lập điền kết luận, lý do và bằng chứng.
- [ ] Tech Lead xử lý các giới hạn về độc lập/freeze nếu còn; xác nhận điều kiện nghiệm thu FR1.8-AC1.
- [ ] Cập nhật ma trận truy vết theo kết luận đã được xác nhận.

**FR1.8-AC1 tiếp tục ở trạng thái chờ review độc lập.** Không sửa/thay câu v6 hoặc chạy lại dự đoán để giữ kết quả đẹp; v6 đã được tiêu thụ và kết quả lịch sử 34/36 được bảo toàn.
