# Báo cáo D5.1 – FastAPI/AskService, router trong pipeline, interface và logging (Sprint 11, Dev 5)

Ngày: 23/11/2026. Nhánh `feature/sprint11-dev5`, dựng từ head PR #55 (`9a0e943`), đã merge `testing` `03a4989` và nhánh PR #58 của Dev 1 (`feature/sprint11-dev1-hardening` `7e7f600`, đã được approve, chưa merge). Căn cứ: SRS 2.1.2 (nhánh `spec/srs-2.1.2`, Tech Lead duyệt 20/11/2026), mục 5.3.4 "Mã lý do, mã lỗi, HTTP", 5.3.5 "Mã chi tiết và `error_code`", 5.4 "`LogEvent`", 5.5 "Interface giữa phân hệ".

## 1. Đối chiếu điều kiện Done của D5.1

| Điều kiện Done | Trạng thái | Bằng chứng |
| --- | --- | --- |
| PR #55 sửa 4 lỗi còn mở | Đã sửa (22/11) | 401 `ApiError` và `NOT_RUN` cho Confidence Filter: `03b54bc`; `LLM_OUTPUT_RAW_TEXT` / `LLM_OUTPUT_TRUNCATED` → `JSON_INVALID` và `action = None` → `INTERNAL_ERROR`: `fdc9547`; router `INVALID_*` → 422, lỗi router → 500: `a3b3c3c` |
| PR #55 đã merge | **Chưa**: PR mở, `REVIEW_REQUIRED`, đi sau `testing` (merge sạch) | Cần Tech Lead review và merge. Nhánh này chứa toàn bộ PR #55 |
| API và CLI dùng cùng `AskService`, router chạy trước retrieval | Đạt | `api/routes/ask.py`, `scripts/run_rag_cli.py` đều gọi `orchestration.wiring.build_ask_service`; `AskService.run` gọi router rồi mới gọi `RAGPipeline` |
| Mỗi dòng bảng SRS 5.3.4 có test | Đạt, 2 dòng skip có lý do | `test/api/test_error_mapping.py` (mục 2) |
| OpenAPI snapshot pass | Đạt | `python -m api.export_openapi --check` |
| Fake pipeline E2E với bản giả của 5 thành phần | Đạt | `test/orchestration/test_interfaces.py::test_ask_service_with_five_fakes` (router, retrieval, gateway, validator, logger giả; test chặn import ES/Qdrant/Ollama) |
| Auth/log events đã che và chung `query_id` | Đạt | `test/api/test_logging_integration.py` (mục 4) và live run (`reports/week11/e2e_report.md`) |

## 2. Bảng mã → test (IR2.5-AC1)

| Dòng SRS 5.3.4 | `status` / `grounding_status` / mã / HTTP | Test |
| --- | --- | --- |
| Grounded | SUCCESS / PASS / – / 200 | `test_route_and_retrieval_rows[grounded]` |
| Không phải pháp lý | SUCCESS / NOT_RUN / – / 200 | `test_route_and_retrieval_rows[non-legal]` |
| Ngoài phạm vi, lẫn phạm vi | ABSTAIN / NOT_RUN / `ROUTE_POLICY` / 200 | `test_route_and_retrieval_rows[out-of-scope]`, `[mixed]` |
| Không có ứng viên | ABSTAIN / NOT_RUN / `RETRIEVAL_EMPTY` / 200 | `test_route_and_retrieval_rows[empty]` |
| Dưới ngưỡng tin cậy | ABSTAIN / NOT_RUN / `LOW_CONFIDENCE` / 200 | `test_route_and_retrieval_rows[low-confidence]` |
| Thiếu dữ kiện, hỏi lại (FR3.4) | NEEDS_CLARIFICATION / NOT_RUN / – / 200 | `test_missing_facts_clarification`, **skip**: FR3.4 thuộc đợt 2, cần `missing_facts` của `week10_v1.1` |
| Model từ chối | ABSTAIN / ABSTAIN / – / 200 | `test_gate_rows_hide_model_draft[abstain-…]` |
| Model xin làm rõ | NEEDS_CLARIFICATION / NEEDS_CLARIFICATION / – / 200 | `test_gate_rows_hide_model_draft[clarify-…]` (kiểm `abstention_reason = null`) |
| Đầu ra lỗi / bị cắt | ABSTAIN / FAIL / `JSON_INVALID` / 200 | `test_gate_rows_hide_model_draft[bad_json-…]` |
| Trích dẫn sai | ABSTAIN / FAIL / `CITATION_INVALID` / 200 | `test_gate_rows_hide_model_draft[gate_fail-…]` (`EVIDENCE_INDEX_OUTSIDE_CONTEXT`) |
| Vi phạm Gate khác | ABSTAIN / FAIL / `GROUNDING_FAIL` / 200 | `test_gate_rows_hide_model_draft[context_truncated-…]` (`PROMPT_CONTEXT_TRUNCATED`) |
| Model quá thời gian | ERROR / NOT_RUN / `LLM_TIMEOUT` / 504, retryable | `test_pipeline_error_rows[timeout-…]` |
| Không kết nối được model (v1.1) | ERROR / NOT_RUN / `LLM_UNAVAILABLE` / 503 | `test_pipeline_error_rows[unavailable-…]`, **skip** cho tới khi `ErrorCode` có `LLM_UNAVAILABLE` (test tự chạy khi có) |
| Lỗi khác trong pipeline | ERROR / NOT_RUN / `INTERNAL_ERROR` / 500 | `test_pipeline_error_rows[internal-…]` |
| `ApiError`: thiếu / sai key | 401 `AUTH_REQUIRED` | `test_api_error_rows[missing-key-…]`, `[wrong-key-…]` |
| `ApiError`: request không hợp lệ, query > 2.000 ký tự | 422 `INVALID_REQUEST` | `test_api_error_rows[bad-body-…]`, `[long-query-…]` |
| `ApiError`: lỗi ngoài pipeline | 500 `INTERNAL_ERROR` | `test_api_error_rows[router-failure-…]` |

Mọi dòng `AskResponse` kiểm thêm disclaimer có đúng một lần (FR5.8-AC1); các dòng ABSTAIN/FAIL kiểm `answer = null` và nháp của model không có trong body. Bảng SRS 5.3.5 được kiểm bằng `test_gate_detail_code` (16 mã chi tiết, cả mã lạ → `GROUNDING_FAIL`) và `test_rag_abstention_detail`.

## 3. Interface (SRS 5.5, đợt 0)

`orchestration/interfaces.py` có 7 Protocol theo bảng 5.5: `Router`, `RetrievalSource`, `ContextAggregator`, `PromptBuilder`, `ModelGateway`, `GroundingGate`, `EventSink`. Code hiện có không phải viết lại:

- `orchestration/events.py` và `orchestration/ask_service.py` dùng `EventSink` và `Router` từ `interfaces.py`.
- `rag_pipeline.CandidateSource` và `rag_pipeline.Generator` thu hẹp `RetrievalSource` và `ModelGateway` (thêm `name`; thêm `config` và `max_evidence_index`).
- `RAGPipeline` nhận qua tham số khởi tạo: `context_aggregator`, `prompt_builder`, `gate`, `validator` (mặc định là module thật). Đủ điều kiện IR4.1-AC1: router, retrieval, gateway, validator, logger đều thay được.
- `test/orchestration/test_interfaces.py` kiểm chữ ký của 9 cặp Protocol / module thật.
- Lớp tạo `AskResponse` tách ra `orchestration/response_builder.py` (bảng 5.3.4 và 5.3.5). `AskService` chỉ còn định tuyến, gọi pipeline, phát sự kiện. Hành vi không đổi; test cũ chạy nguyên.

SRS 5.5 lệch code hai chỗ. Đã sửa SRS (không đổi code) ở commit `a149a1c` trên nhánh `spec/srs-2.1.2` (chưa push), dòng lịch sử "2.1.2 (sửa)" ngày 23/11/2026, chờ Tech Lead xác nhận:

1. `generate(...)`: `QwenGateway.generate` có thêm tham số tùy chọn `max_evidence_index` (PR #49), pipeline dùng ở chế độ production. SRS nay ghi tham số này; `interfaces.ModelGateway` giữ chữ ký tối thiểu, `Generator` của pipeline thêm tham số.
2. `build_controlled_rag_prompt(payload)`: code đặt tên tham số `context_payload`. SRS và Protocol nay dùng `context_payload`, positional-only (Gate cũng vậy). SRS ghi thêm validator truyền được qua tham số khởi tạo (IR4.1-AC1).

## 4. Logging (FR9.9, FR9.10, NFR3.4)

- `LEGAL_RAG_EVENT_LOG` có giá trị → sink là `monitoring.StructuredLogger` của Dev 1, `PIIMasker(secret_values=<các API key đã cấu hình>)`. Không có → `NullEventSink`. Không còn fallback sang `JsonlEventSink`.
- API (lifespan) và CLI đóng logger do chúng tạo (`close(timeout=2.0)`); không đóng sink của service được inject.
- Không thêm sự kiện mới. Sự kiện API (`request_received`, `request_rejected`, `request_completed`) và sự kiện stage giữ tên cũ, theo hướng dẫn của Dev 1 (`docs/operations/logging.md`).
- Test (`test/api/test_logging_integration.py`, 9 ca): thứ tự stage FR9.9-AC1 trên Gate PASS; nhánh xã giao chỉ có `api`, `router`, `response` (AC2); 401 có sự kiện `AUTH_REQUIRED`, log không chứa key đúng hay key sai; email và số điện thoại trong câu hỏi không vào log; logger lỗi ở mọi lần ghi thì phản hồi y hệt (FR9.10-AC1); lifespan che key và đóng logger; CLI ghi đủ sự kiện trước khi thoát.

Chưa làm, chờ đầu vào:

- Stage `confidence` (v1.1): quyết định ngưỡng vẫn ghi ở stage `rerank`, `event_type = confidence_checked`.
- Latency theo stage (`bm25_ms`, `dense_ms`, `rrf_ms`): Dev 1 đã cho phép trong logger, nhưng retrieval chưa trả các số này (Retrieval Adapter của Dev 4, PR #56). Khi có, thêm khóa vào `SAFE_METADATA_KEYS` của `StageEmitter`.

## 5. Kiểm thử

| Lệnh | Kết quả |
| --- | --- |
| `python -m pytest -q` | 1732 passed, 3 skipped (1 skip có sẵn ở `parser/`, 2 skip có lý do ở mục 2), 179 subtests passed |
| `python -m ruff check .` | All checks passed |
| `python -m api.export_openapi --check` | pass |

## 6. Việc cần người khác

| Việc | Ai |
| --- | --- |
| Review và merge PR #55, sau đó PR của nhánh này | Tech Lead |
| Merge PR #58 (logger), vì nhánh này dùng `monitoring/` | Tech Lead / Dev 1 |
| `week10_v1.1` vào `schemas/models.py` (`LLM_UNAVAILABLE`, stage `confidence`, `point_ref`, `missing_facts`, `RouteDecision.action` dạng Literal). PR #56 chỉ có `MetadataFilters`, `RetrievalLatencyBreakdown`, `RAGOutputRecord.route` | Dev 3 (D3.1) |
| Xác nhận bản sửa SRS 5.5 (`a149a1c`) | Tech Lead |
| Đưa SRS 2.1.2 lên `testing` (nhánh `spec/srs-2.1.2` chưa push) | Dev 5 + Tech Lead |
