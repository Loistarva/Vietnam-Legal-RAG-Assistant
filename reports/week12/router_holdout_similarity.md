# FR1.8-AC1 — Kiểm tra gần trùng Router holdout v6

**Trạng thái: chờ review độc lập.** Bộ v6 có 36 câu, 0 trùng nguyên văn và 1 cặp vượt ngưỡng rà soát. Chưa đủ bằng chứng để kết luận holdout không gần trùng. Kết quả phân loại lịch sử 34/36 và nhãn đã duyệt được giữ nguyên.

| ID holdout | Nguồn đối chiếu | Độ tương đồng ký tự | Jaccard bigram |
| --- | --- | ---: | ---: |
| `W16RH_011` | `test/agent/test_rule_router.py:360` | 0,865 | 0,567 |

## Phương pháp

Chạy `python scripts/audit_router_holdout_similarity.py` từ gốc repo. Validator hiện có kiểm trùng nguyên văn sau chuẩn hóa NFC, chữ thường và khoảng trắng. Bước gần trùng bỏ dấu tiếng Việt, chuẩn hóa chữ thường và tách từ theo khoảng trắng hoặc dấu câu. Một cặp cần review khi tỷ lệ tương đồng ký tự của `SequenceMatcher` đạt ≥ 0,82 hoặc Jaccard của tập bigram từ liên tiếp đạt ≥ 0,65. Các ngưỡng dùng để sàng lọc, không thay thế review ngữ nghĩa và có thể bỏ sót câu diễn đạt bằng từ khác.

Phạm vi gồm 11 nguồn với 1.595 mục so sánh và 57.420 cặp. Các nguồn là 40 câu hồi quy Router, 36 câu R4IH, 180 câu v1–v5, 270 câu Dev, 26 câu Negative Set v2, 286 chuỗi trích từ test Router và 757 chuỗi trích từ source luật Router. Các chuỗi Python được trích bằng AST và tham chiếu theo dòng. Đối chiếu source bao gồm chuỗi trong biểu thức chính quy ở dạng văn bản, nên phép đo không kiểm mọi câu mà biểu thức có thể khớp. Script chỉ in ID, tham chiếu nguồn, điểm và hash.

## Hash và handoff

- Source Router v5 hiện tại dùng một SHA-256 chuẩn hóa LF là `081152e3e71795454b702c57092987703bd281f943cdfc3b740076a393780067`, trùng hồ sơ freeze snapshot `d76244d8`.
- SHA-256 LF của holdout v6 hiện tại là `b9eeb081552b0eaf87326fd86f9426818aee615c8e70b5fd96857c8effd670b8`. Metadata nguồn và review ở [hồ sơ v6](../../evaluation/router_holdout/router_holdout_week10_v6.md).
- Hash của source tại lượt 34/36 là bằng chứng lịch sử của lượt đó. Hồ sơ [D4.2](../../evaluation/router_holdout/router_holdout_report.md) ghi rõ giới hạn bằng chứng về thời điểm freeze trước lượt chạy.
- Người kiểm độc lập cần đối chiếu cặp được gắn cờ và xác nhận mức độ chồng lặp ngữ nghĩa. Dev 4 giữ FR1.8-AC1 ở trạng thái chờ review cho đến khi có kết luận và bằng chứng freeze phù hợp.
