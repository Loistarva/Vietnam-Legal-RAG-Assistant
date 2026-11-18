# SSE events – `POST /api/v1/ask/stream` (`sse_v1`)

Body, API key, pipeline và lỗi 401/403/422 giống `POST /api/v1/ask` ([docs/api.md](../api.md)). Response là `text/event-stream`, header `X-Query-ID`.

## Thứ tự event

```
status(accepted) → status(routing) → status(retrieving) → status(reranking)
  → status(generating) → status(validating) → <final> → done
```

`<final>` là đúng **một** trong các event sau:

| Event | Khi nào | `data` |
| --- | --- | --- |
| `verified_answer` | `status=SUCCESS` (Gate PASS, hoặc non-legal) | `{"sse_version", "elapsed_ms", "response": AskResponse}` |
| `clarification` | `NEEDS_CLARIFICATION` | như trên |
| `abstention` | `ABSTAIN` (policy, confidence, Gate FAIL, model từ chối) | như trên |
| `error` | `ERROR` (`LLM_TIMEOUT`, `INTERNAL_ERROR`) | như trên; nếu không dựng được AskResponse: `{"status": "ERROR", "error_code", "message"}` |

Các phase không chạy thì không được phát. Ví dụ: non-legal chỉ có `accepted, routing`; low confidence không có `generating`. Mỗi phase phát tối đa một lần.

Ví dụ từ lần chạy live (rút gọn):

```
event: status
id: 0
data: {"schema_version": "week10_v1.0", "sse_version": "sse_v1", "query_id": "q_…", "phase": "accepted", "elapsed_ms": 2.48}

event: status
id: 5
data: {"sse_version": "sse_v1", "query_id": "q_…", "phase": "validating", "elapsed_ms": 85777.66}

event: verified_answer
id: 6
data: {"sse_version": "sse_v1", "elapsed_ms": 85787.9, "response": {"status": "SUCCESS", "answer": "…", "citations": […], "evidence": […], …}}

event: done
id: 7
data: {"sse_version": "sse_v1", "query_id": "q_…", "status": "SUCCESS", "elapsed_ms": 85791.4}
```

## Quy tắc an toàn

- Status event được dựng từ stage `LogEvent`, vốn không bao giờ chứa câu hỏi, prompt hay câu trả lời. Vì vậy client không nhận được gì của bản nháp trước khi Gate quyết định.
- Câu trả lời chỉ có trong event cuối, tức là sau Gate (buffer → Gate → phát). Hiện **không** stream từng token; nếu sau này stream token thì cũng chỉ được stream sau Gate PASS.
- `elapsed_ms` tính từ lúc nhận request. Server log riêng `stream_first_status` (byte trạng thái đầu tiên) và `stream_final` (event cuối), để không trộn TTFB trạng thái với thời gian ra câu trả lời đã kiểm chứng.
- Client ngắt kết nối: stream dừng và server ghi `client_disconnected`. Lời gọi pipeline đang chạy (request tới Qwen local) không hủy được; nó chạy xong trong worker thread rồi trả slot.

Client đọc stream: mỗi event là các dòng `event:`, `id:`, `data:` (JSON một dòng), phân tách bằng một dòng trống. Kết thúc khi nhận `done`.
