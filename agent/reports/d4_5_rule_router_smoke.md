# Báo cáo smoke test Rule Router — D4.5

## Phần Dev4 đã triển khai

- Tạo `agent.router.RuleRouter` độc lập và contract kết quả `RouteDecision` có cấu trúc.
- Tạo fast-path khớp chính xác sau chuẩn hóa. Danh sách mặc định để trống vì chưa có bộ quy tắc được phê duyệt. Một quy tắc chỉ đủ điều kiện nếu được đánh dấu phê duyệt và có `handler key` cùng tham chiếu trích dẫn không rỗng. Đây chỉ là bước kiểm tra điều kiện định tuyến; Orchestrator phía sau phải xác minh handler có tồn tại và các trích dẫn hợp lệ trước khi thực thi fast-path.
- Định tuyến xác định cho yêu cầu pháp lý thuộc HNGĐ, lĩnh vực pháp lý ngoài phạm vi, yêu cầu trộn phạm vi, trường hợp chưa rõ phạm vi pháp lý và yêu cầu phi pháp lý.
- Giữ nguyên `query_id` và `as_of_date`; từ chối ngày không hợp lệ thay vì tự thay bằng ngày hiện tại.
- Ghi log quyết định định tuyến có cấu trúc, không ghi câu hỏi gốc hoặc câu hỏi đã chuẩn hóa.
- Bổ sung kiểm thử hồi quy cho năm câu hỏi pháp lý thực tế được nêu trong review:
  - Giấy tờ kết hôn với người nước ngoài → `LEGAL_HNGD`.
  - Câu hỏi về luật thuế → `LEGAL_OUT_OF_SCOPE`.
  - Câu hỏi về sa thải trái luật → `LEGAL_OUT_OF_SCOPE`.
  - Tư vấn hợp đồng mua bán nhà đất → `LEGAL_OUT_OF_SCOPE`.
  - Câu hỏi về xử phạt do đỗ xe sai quy định → `LEGAL_OUT_OF_SCOPE`.
- Từ chối các fast-path pattern trùng nhau sau khi chuẩn hóa.
- Chưa triển khai hoặc tích hợp SuperRouter/Orchestrator vì repository chưa có module này. RuleRouter chỉ trả quyết định; không gọi Retrieval, responder hoặc LLM.

## Xác minh

Theo kết quả kiểm tra trong tài liệu review được cung cấp, các file `rule_router.py` và `test_rule_router.py` đã được đặt trong cấu trúc package cô lập tương ứng với `agent/router/` và `test/agent/`, sau đó chạy pytest và biên dịch bytecode:

```text
python -m pytest test/agent/test_rule_router.py -q
25 passed, 23 subtests passed
python -m compileall -q agent test
PASS
```

Để xác minh trong checkout của dự án, chạy:

```powershell
.\.venv\Scripts\python.exe -m pytest .\test\agent\test_rule_router.py -q
```

Phạm vi kiểm thử gồm route/action/reason, thứ tự ưu tiên fast-path, khớp chính xác, ngày hiệu lực, phạm vi pháp lý trộn hoặc chưa rõ, năm ví dụ trong review, pattern trùng sau chuẩn hóa, kiểm tra đầu vào, bảo toàn `as_of_date`, tính xác định và log không chứa câu hỏi.

## Các hạng mục bàn giao còn thiếu

Các hạng mục dưới đây chưa được đánh dấu hoàn tất vì đang chờ đầu vào hoặc xác nhận từ dev phụ trách.

| Hạng mục còn thiếu | Phụ thuộc | Bàn giao hoặc bằng chứng cần có |
|---|---|---|
| Bộ câu hỏi negative có nhãn để đánh giá false positive/false negative | **Dev1** | Cung cấp `evaluation/negative_set/dev_negative_queries_v1.jsonl`. File này chưa có trong repository; không tạo bộ dữ liệu thay thế và chưa thực hiện đánh giá negative-set chính thức. |
| Tích hợp RuleRouter với SuperRouter/Orchestrator | **Dev5** | Cung cấp điểm tích hợp thực tế; xác nhận Orchestrator nhận 5 giá trị route hiện tại hay cần 3 nhóm chính kèm `route_reason`; xác minh handler và citation trước khi chạy fast-path. Trong phạm vi kiểm tra, chưa tìm thấy module Orchestrator trong repository. |
| Sign-off tích hợp và review | **Dev3 và reviewer theo kế hoạch sprint** | Review contract route đã thống nhất và kết quả trên negative set thực tế của Dev1; cung cấp bằng chứng phê duyệt rõ ràng. Trong các file đã xem chưa có bằng chứng sign-off. |

Các từ khóa định tuyến hiện là baseline xác định ban đầu. Chưa nên mô tả classifier là đã hiệu chỉnh cho production cho đến khi đánh giá trên negative set của Dev1 và hoàn tất các bàn giao tích hợp/review nêu trên.
