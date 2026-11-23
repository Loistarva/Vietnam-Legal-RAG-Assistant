# SSE cho `POST /api/v1/ask/stream`

Client gửi cùng body và API key như khi gọi `POST /api/v1/ask`. Request bị từ chối trả JSON với HTTP 401 hoặc 422. Request hợp lệ trả HTTP 200, `Content-Type: text/event-stream` và header `X-Query-ID`. [Contract HTTP](../api.md)

| Event | Khi nào | JSON trong trường `data` |
| --- | --- | --- |
| `status` | Server nhận request hoặc pipeline chuyển giai đoạn | `sse_version`, `query_id`, `phase` và `elapsed_ms`. Event đầu còn có `schema_version`. |
| `final` | Pipeline hoàn tất với `SUCCESS`, `NEEDS_CLARIFICATION` hoặc `ABSTAIN` | Toàn bộ `AskResponse`, cùng cấu trúc với endpoint JSON. Khi Gate FAIL, `answer` là `null`. |
| `error` | Pipeline hoặc server gặp lỗi | `query_id`, `error_code`, `message` cho client và `response` chứa `AskResponse` khi pipeline trả về `ERROR`. Lỗi xảy ra trước khi dựng được `AskResponse` dùng `ApiError`. |

Mỗi event có `id` tăng dần. Ở phiên bản `sse_v2`, client đọc các event `status` đến khi gặp đúng một `final` hoặc `error`. Kết nối đóng ngay sau event này. Client đọc trực tiếp JSON của event cuối và dùng `status` để hiển thị câu trả lời, yêu cầu làm rõ, thông báo từ chối hoặc lỗi.

Ví dụ event đầu tiên

```text
event: status
id: 0
data: {"schema_version":"week10_v1.0","sse_version":"sse_v2","query_id":"q_1","phase":"accepted","elapsed_ms":1.5}
```

Luồng pháp lý có đủ evidence đi qua `accepted → routing → retrieving → reranking → generating → validating`. Mỗi phase xuất hiện tối đa một lần. Câu xã giao kết thúc sau `routing`. Nếu thiếu evidence, luồng dừng sau `reranking`. Event trạng thái chỉ chứa tiến độ. Nội dung câu trả lời pháp lý xuất hiện sau khi Gate duyệt.

Server ghi `stream_first_status` và `stream_final` để đo riêng thời điểm phát trạng thái đầu và kết quả cuối. Khi client ngắt kết nối sớm, server ghi `client_disconnected`. Lời gọi Qwen đang chạy hoàn tất trong worker rồi trả slot.
