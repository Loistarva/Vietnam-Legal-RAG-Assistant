# Live E2E trên `testing` – S12-D5.1 (Sprint 12, Dev 5)

Ngày 26/11/2026. Căn cứ: SRS 2.1.3 (PR #68), mục 5.3.4 "Mã lý do, mã lỗi, HTTP" và 5.4 "`LogEvent`"; kế hoạch Sprint 12 V1.5, task S12-D5.1.

## 1. Phạm vi và SHA

- Code: `origin/testing` `7d3c174` (merge PR #61, chứa toàn bộ PR #59), checkout sạch ở worktree riêng, không có thay đổi local.
- PR #59 và #61 đã merge `testing` `c266983` (PR #63, contract `week10_v1.1`) và `5e745af` (PR #53) trước khi merge. Xung đột ở `orchestration/ask_service.py`, `orchestration/wiring.py`, `test/orchestration/test_ask_service.py`: `RuleRouterAdapter` lấy từ `agent/router/adapter.py` (PR #64), `GENERAL_CHAT_MESSAGE` từ `agent/config.py`. Full suite trên nhánh #61 trước khi merge: 1.923 passed, 2 skipped; CI xanh.
- Dịch vụ: Elasticsearch 9.5.3 (`bm25-e6-verified-20261101`), Qdrant embedded (BGE-M3, collection `vietnam_legal_chunks`, metadata `corpus_sha256` `7105c484…6b023` khớp corpus trên `testing`), Ollama `qwen2.5:7b` digest `845dbda0…697e`, prompt `v1.2_controlled_rag`.
- Máy: Windows 11, NVIDIA GeForce RTX 3050 Ti Laptop GPU 4 GB.
- Lệnh: `uvicorn api.main:app` (mode `live`, `LEGAL_RAG_EVENT_LOG` bật), rồi `python scripts/run_live_e2e.py --event-log <log> --out <dir>`.

## 2. Kết quả (lượt 2, 13/13 đạt)

| Case | HTTP | `status` / `grounding_status` | `error_code` | Thời gian (ms) |
| --- | --- | --- | --- | --- |
| Thiếu API key | 401 | – | `AUTH_REQUIRED` | 36 |
| Sai API key | 401 | – | `AUTH_REQUIRED` | 9 |
| Câu hỏi rỗng | 422 | – | `INVALID_REQUEST` | 16 |
| Câu hỏi > 2.000 ký tự | 422 | – | `INVALID_REQUEST` | 7 |
| Pháp lý: tuổi kết hôn | 200 | SUCCESS / PASS | – | 33.747 |
| Pháp lý: tài sản chung | 200 | SUCCESS / PASS | – | 46.458 |
| Pháp lý: ngày trong câu hỏi | 200 | SUCCESS / PASS | – | 34.820 |
| Không phải pháp lý | 200 | SUCCESS / NOT_RUN | – | 65 |
| Ngoài phạm vi | 200 | ABSTAIN / NOT_RUN | `ROUTE_POLICY` | 20 |
| Dưới ngưỡng tin cậy (HN_035) | 200 | ABSTAIN / NOT_RUN | `LOW_CONFIDENCE` | 15.192 |
| UI (Streamlit AppTest → API): pháp lý | – | SUCCESS / PASS | – | 28.330 |
| UI: không phải pháp lý | – | SUCCESS / NOT_RUN | – | 132 |
| UI: ngoài phạm vi | – | ABSTAIN / NOT_RUN | `ROUTE_POLICY` | 97 |

Log: 80 sự kiện, mọi dòng là JSON, không chứa API key đúng hay sai, thứ tự stage của từng `query_id` khớp kỳ vọng. Bằng chứng: [live/live_e2e_results.json](live/live_e2e_results.json), [live/live_events.jsonl](live/live_events.jsonl).

Lượt 1 (cùng SHA) đạt 12/13: case tuổi kết hôn trả `LLM_TIMEOUT` 504 sau 433 s, vì lúc đó máy đang chạy full pytest song song và đây là lần gọi Qwen đầu tiên (nạp model). Lượt 2 chạy khi máy rảnh. API vẫn trả đúng mã của bảng 5.3.4 cho lỗi timeout.

## 3. Chưa chạy live

| Case kế hoạch | Lý do | Bằng chứng hiện có |
| --- | --- | --- |
| Gate FAIL | Qwen không tạo citation sai theo yêu cầu; không chèn lỗi vào bản `testing` đang đo | `test/api/test_error_mapping.py` (`gate_fail`, `bad_json`), fake pipeline |
| Ollama tắt (503 `LLM_UNAVAILABLE`) | Gateway không có biến môi trường đổi `base_url`; cần dừng dịch vụ Ollama của máy | `test_pipeline_error_rows[unavailable-LLM_UNAVAILABLE-503-True]` |
| Timeout chủ động | Chỉ xảy ra ngẫu nhiên (lượt 1) | Lượt 1 ở trên; `test_pipeline_error_rows[timeout…]` |

## 4. Phát hiện

- `agent/router/rule_router.py` `to_canonical()` (Dev 4, PR #64) không điền `RouteDecision.router_route` (trường `week10_v1.1`, SRS mục 5.6). Adapter cũ của Dev 5 có điền. Cần sửa ở module của Dev 4.
- `retrieval_config_version` trong log vẫn là hash rút gọn `sha256:a650eac52ec2ba74` (đã ghi ở báo cáo tuần 11, D4.3).
