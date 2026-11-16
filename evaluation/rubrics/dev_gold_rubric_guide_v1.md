# Rubric chấm mù A/B trên Dev Gold 30 (v1)

**Phạm vi:** Run A (Zero-shot) và Run B (Controlled RAG), cùng 30 `query_id` Dev Gold đã khóa.  
**Đơn vị chấm:** một câu trả lời cho một câu hỏi; tổng cộng 60 câu trả lời A/B.  
**Thang chính:** Answer Relevance và Legal Correctness chấm cho cả A và B. Context Faithfulness chỉ chấm cho B.

## 1. Mục tiêu và nguyên tắc

Rubric này ghi nhận đánh giá của người chấm. Không dùng lexical score, Token F1, Citation Precision/Recall, Citation Validity hoặc Grounding Gate thay cho điểm chấm tay.

- Chấm A và B độc lập, không biết nhãn run trong giai đoạn chấm mù.
- Dựa vào cùng câu hỏi, `as_of_date`, Gold đã duyệt và nguồn Gold đã xác minh.
- Chấm từng tiêu chí độc lập. Câu trả lời có thể liên quan đúng câu hỏi nhưng sai luật.
- Ghi lý do ngắn, nêu kết luận/claim bị chấm và căn cứ Gold liên quan.
- Không xem câu trả lời A/B theo cặp trong lúc chấm; ghép cặp sau khi khóa điểm.

## 2. Phân biệt các tiêu chí

| Tiêu chí | Phạm vi | Câu hỏi đánh giá |
|---|---|---|
| Answer Relevance | A và B | Câu trả lời có đáp ứng đúng trọng tâm câu hỏi không? |
| Legal Correctness | A và B | Kết luận pháp lý có đúng theo Gold và pháp luật áp dụng tại `as_of_date` không? |
| Context Faithfulness / Evidence Grounding | Chỉ B | Các claim pháp lý có được hỗ trợ trực tiếp bởi `ContextPayload` đã cấp cho model không? |
| Hallucination | A và B | Có ít nhất một claim pháp lý không được Gold hỗ trợ hoặc mâu thuẫn với nguồn áp dụng không? |
| Response action | A và B | Câu trả lời kết luận, từ chối, yêu cầu làm rõ hay không rõ hành động? Dùng cho phân tích abstention; không phải điểm chất lượng. |

**Không gộp Legal Correctness với Context Faithfulness.** Một câu trả lời có thể đúng luật nhưng B không có bằng chứng hỗ trợ trong context; ngược lại, B có thể trích đúng context nhưng context/Gate không chứng minh kết luận đúng theo pháp luật tại ngày áp dụng.

Sprint 9 yêu cầu không gọi Legal Correctness là Faithfulness. Trường `faithfulness_score` trong bảng chấm Zero-shot cũ thuộc rubric lịch sử, không được đổi tên hoặc nhập thẳng thành Legal Correctness hay Context Faithfulness trong bộ A/B này.

## 3. Tài liệu Gold người chấm được xem

Điều phối viên chuẩn bị cùng một gói Gold cho từng `query_id`:

1. Câu hỏi nguyên văn và `as_of_date` lấy từ benchmark.
2. Đáp án chuẩn và giải thích đã duyệt trong `data/benchmark/ground_truth.json`.
3. Toàn văn clause/chunk Gold tương ứng trong `data/chunking_output/chunks.jsonl`, cùng nguồn đã xác minh nếu cần xác định hiệu lực tại `as_of_date`.
4. Với Context Faithfulness của B: `ContextPayload` thực tế đã cấp cho B, đúng phiên bản run. Không dùng top-k retrieval thay cho context thực tế.

Không đưa nhãn `A`/`B`, prompt, tên model hoặc thông tin run vào phiếu chấm mù. Citation display giữa A và B được chuẩn hóa trước khi phát phiếu; không sửa nội dung answer hoặc bỏ citation sai.

## 4. Thang điểm Answer Relevance (1–5, A/B chung)

| Điểm | Mô tả |
|---:|---|
| 5 | Trả lời trực tiếp, đúng trọng tâm và đáp ứng đủ các ý được hỏi. |
| 4 | Trả lời đúng trọng tâm nhưng thiếu một ý phụ hoặc có phần lan man nhỏ. |
| 3 | Chỉ trả lời một phần; thiếu một ý chính hoặc phần đáng kể không đi vào yêu cầu. |
| 2 | Hiểu sai trọng tâm, trả lời vòng tránh, hoặc từ chối dù câu hỏi yêu cầu câu trả lời cụ thể. |
| 1 | Rỗng, hầu như không liên quan, hoặc hoàn toàn không đáp ứng câu hỏi. |

Không hạ Relevance chỉ vì câu trả lời sai luật; ghi lỗi đó ở Legal Correctness/Hallucination.

## 5. Thang điểm Legal Correctness (1–5, A/B chung)

Đánh giá kết luận và điều kiện pháp lý theo Gold và quy định áp dụng tại `as_of_date`. Citation đúng hình thức không chứng minh kết luận đúng.

| Điểm | Mô tả |
|---:|---|
| 5 | Kết luận đúng; các điều kiện/ngoại lệ trọng yếu và mốc hiệu lực được nêu chính xác khi cần. |
| 4 | Kết luận chính đúng; thiếu chi tiết phụ hoặc có sai sót nhỏ không làm đổi cách hiểu/kết quả. |
| 3 | Đúng một phần nhưng thiếu điều kiện quan trọng, có nhận định pháp lý sai đáng kể, hoặc kết luận còn nhập nhằng. |
| 2 | Phần lớn sai hoặc có mâu thuẫn lớn; chỉ giữ được một phần nhỏ đúng. |
| 1 | Kết luận chính sai, trái Gold/nguồn áp dụng, hoặc áp dụng văn bản hết hiệu lực cho câu hỏi hiện hành. |

Nếu câu hỏi không thể kết luận từ Gold, không tự suy diễn luật: chấm mức độ đúng của phần trả lời/giới hạn mà Gold cho phép và ghi rõ thiếu dữ kiện hay thiếu căn cứ.

## 6. Context Faithfulness / Evidence Grounding (1–5, chỉ B)

Đối chiếu từng claim pháp lý quan trọng trong answer với `ContextPayload` thực tế của B. Tiêu chí này chỉ hỏi claim có được context hỗ trợ không; không chấm tính đúng luật ngoài context.

| Điểm | Mô tả |
|---:|---|
| 5 | Mọi claim pháp lý trọng yếu đều được context hỗ trợ; không thêm claim ngoài căn cứ. |
| 4 | Các claim và kết luận chính được hỗ trợ; có chi tiết phụ không nêu trong context nhưng không làm đổi kết luận. |
| 3 | Có một claim quan trọng không được context hỗ trợ hoặc bỏ mất điều kiện/ngoại lệ trong context. |
| 2 | Nhiều claim quan trọng thiếu căn cứ trong context, hoặc diễn giải context sai đáng kể. |
| 1 | Kết luận chính không được context hỗ trợ hoặc trực tiếp trái với context. |

Ghi `N/A` cho A; không chấm 0 và không suy context cho Zero-shot. Grounding Gate `PASS` không tự động nhận điểm 5.

## 7. Hallucination (nhãn riêng, A/B)

Ghi `yes` nếu câu trả lời có **ít nhất một claim pháp lý** không được nguồn đánh giá hỗ trợ hoặc mâu thuẫn với nguồn. Nếu không có, ghi `no`.

- Với A: đối chiếu Gold/nguồn Gold đã xác minh và `as_of_date`.
- Với B: đối chiếu Gold và, khi claim dựa trên bằng chứng đã cấp, ContextPayload.
- Tính cả số Điều/Khoản, văn bản, ngày hiệu lực, ngoại lệ, chế tài hoặc thủ tục bịa/sai.
- Không tính câu xã giao/disclaimer không mang claim pháp lý.
- Ghi claim cụ thể và nguồn mâu thuẫn/không hỗ trợ trong rationale.

Hallucination là nhãn riêng; không tính bằng `1 − Faithfulness`, `1 − Legal Correctness` hay từ Gate status.

## 8. Response action và abstention

Mỗi câu trả lời nhận một nhãn hành động:

| Nhãn | Quy tắc |
|---|---|
| `answer` | Có đưa ra câu trả lời/kết luận cho câu hỏi. |
| `abstain` | Từ chối hoặc nói không đủ căn cứ và không kết luận. |
| `clarify` | Chủ yếu yêu cầu thêm dữ kiện, chưa kết luận tình huống. |
| `unclear` | Không thể xác định hành động từ nội dung. |

Nhãn thủ công này có thể dùng để kiểm tra hành vi A; abstention rate và false-abstention chính thức của B lấy từ output có cấu trúc và được tính bằng code. Khả năng từ chối đúng cần tập câu âm; không suy ra từ 30 câu Dev Gold đều có căn cứ.

## 9. Quy trình blind scoring

1. Chỉ bắt đầu sau khi cả A và B của cùng 30 ID đã hoàn tất và được đóng băng.
2. Tạo 60 phiếu trả lời, gán `blind_id` ngẫu nhiên; xáo thứ tự và ẩn nhãn A/B. Giữ bảng ánh xạ `blind_id → query_id/run` riêng, chỉ điều phối viên được xem.
3. Chuẩn hóa cách hiển thị citation theo Sprint 9 nhưng giữ nguyên citation sai/thiếu để người chấm đánh giá.
4. Hai người chấm độc lập cùng chấm toàn bộ khoảng 60 câu trả lời. Chọn trước 10/60 câu để cả hai chấm; nên chọn 5 cặp query có cả A và B để kiểm tra độ đồng thuận mà không lộ nhãn.
5. Mỗi rater khóa điểm và rationale trước khi mở bảng ánh xạ. Sau đó ghép A/B theo `query_id`, báo paired B−A; weighted kappa cho điểm thứ bậc nếu đủ dữ liệu.
6. Không sửa câu trả lời, rubric, threshold hay prompt sau khi xem điểm. Bất đồng có thể được adjudicate riêng; giữ nguyên điểm gốc của hai rater.

Context Faithfulness là tiêu chí B-only và cần xem ContextPayload, nên chấm trong phần/phiếu B riêng; không đưa context vào 60 phiếu blind chung vì nó làm lộ Run B.

## 10. Cột của phiếu chấm

Phiếu blind cho mỗi rater có tối thiểu:

`Blind ID`, `Question`, `As of Date`, `Gold Answer`, `Gold Explanation`, `Answer`, `Citations`, `Answer Relevance`, `Legal Correctness`, `Hallucination`, `Response Action`, `Rationale`, `Grader`. CSV dùng dấu chấm phẩy làm dấu phân cách để Excel theo thiết lập vùng Việt Nam mở đúng cột.

Phiếu B-only bổ sung `context_payload` hoặc tham chiếu bất biến tới payload và `context_faithfulness_score`, `context_faithfulness_rationale`. Không ghi `run=A/B` trong phiếu gửi rater; mapping được giữ tách biệt cho tới khi điểm đã khóa.

Sau khi mở mapping, bảng tổng hợp điều phối viên cần giữ `blind_id`, `query_id`, `run`, rater, điểm, nhãn Hallucination/response action, rationale và hash answer. Hash và mapping chỉ nằm trong bảng điều phối viên riêng, không nằm trong phiếu gửi rater. Mỗi câu trả lời A/B phải giữ thành dòng riêng; không gộp điểm theo cặp trước khi tính độ đồng thuận.

## 11. Tóm tắt và so sánh

- Báo mean/median và phân bố điểm cho Answer Relevance, Legal Correctness; báo Context Faithfulness riêng cho B.
- Báo tỷ lệ câu có `hallucination_present=yes`; nêu rõ mẫu số và số câu thiếu điểm.
- Báo response action riêng; false-abstention tính trên câu đủ căn cứ, không trên toàn bộ câu âm.
- So sánh A/B theo cặp cùng `query_id`, báo chênh lệch B−A và CI95 hoặc Wilcoxon signed-rank khi phù hợp. Với 30 cặp, diễn giải thận trọng.
- Không trộn điểm chấm tay vào metric JSON tự động nếu chưa có bước nhập/aggregate được duyệt.

## 12. Liên hệ với rubric Zero-shot cũ

`zero_shot_rubric_guide_v1.md` và `zero_shot_dev30_manual_scores_v1.csv` là tài liệu/điểm lịch sử của Run A. Cột `faithfulness_score` cũ không tự động chuyển thành `legal_correctness_score` hoặc `context_faithfulness_score`; hash answer phải khớp trước khi dùng lại điểm. Rubric A/B này và score sheet mới phải được version hóa riêng.


