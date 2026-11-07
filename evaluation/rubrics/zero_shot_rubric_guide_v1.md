# Hướng dẫn chấm tay Zero-shot (v1)

Dùng cho bảng `evaluation/rubrics/zero_shot_dev30_manual_scores_v1.csv`, nạp bằng
`--rubric-input` của `scripts/run_zero_shot_dev.py` hoặc `python -m evaluation.evaluate_zero_shot`.
Hai thang giữ đúng thang 1–5 của `compute_rubric_scores` (`evaluation/evaluate_zero_shot.py`);
điểm chuẩn hóa 0–1 là `(điểm − 1) / 4`.

Người chấm đọc câu hỏi, đáp án tham chiếu trong `data/benchmark/ground_truth.json` và **toàn văn các
chunk gold** (`gold_context_ids`, tra trong `data/chunking_output/chunks.jsonl`). Không dùng điểm lexical
hay Token F1 khi chấm. Chấm hai thang độc lập: câu trả lời đúng trọng tâm nhưng sai luật vẫn có thể
được Relevance cao.

## Answer Relevance (câu trả lời có trả lời đúng câu được hỏi không)

| Điểm | Mức |
| ---: | --- |
| 5 | Trả lời thẳng câu hỏi, đúng trọng tâm, đủ các ý được hỏi. |
| 4 | Có trả lời câu hỏi, nhưng thiếu một phần được hỏi hoặc lan sang nội dung không được hỏi. |
| 3 | Chỉ trả lời gián tiếp hoặc một phần nhỏ; phần lớn nói chuyện khác. |
| 2 | Hiểu sai câu hỏi, né hoặc từ chối mà không trả lời. |
| 1 | Rỗng hoặc không liên quan. |

## Faithfulness (nội dung có khớp quy định trong chunk gold không)

| Điểm | Mức |
| ---: | --- |
| 5 | Kết luận và các ý chính khớp chunk gold; không có nội dung pháp lý sai, không có căn cứ bịa. |
| 4 | Kết luận đúng; chỉ sai nhỏ về căn cứ (số Điều sai, nêu lần “sửa đổi, bổ sung” không có thật) hoặc thêm chi tiết không có trong gold nhưng không trái luật. |
| 3 | Kết luận đúng, nhưng có trích dẫn bịa (đoạn “trích nguyên văn” không có trong luật), hoặc một nhận định sai, hoặc thiếu điều kiện quan trọng của quy định. |
| 2 | Chỉ đúng một phần, hoặc kết luận đúng nhưng kèm nhận định trái quy định có thể làm người hỏi hiểu sai (chế tài, mức tiền, điều kiện bịa). |
| 1 | Kết luận chính sai hoặc trái chunk gold; dẫn văn bản không còn hiệu lực cho câu hỏi về luật hiện hành. |

## Cột của bảng chấm

`query_id`, `answer_relevance_score`, `faithfulness_score` (số nguyên 1–5), `rubric_rationale`
(căn cứ của điểm, nêu Điều/Khoản gold và chỗ sai), `grader`, `prediction_sha256` (SHA-256 của câu trả lời
đã chấm, `evaluate_zero_shot.prediction_sha256`). `evaluate_zero_shot` dừng khi thiếu file, trùng `query_id`,
điểm ngoài 1–5, có ID ngoài tập câu hỏi được chấm, hoặc câu trả lời khác câu trả lời đã chấm. Chạy lại model
thì câu trả lời đổi, phải chấm tay lại.
