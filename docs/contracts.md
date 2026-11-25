# Canonical Contracts Specification (`week10_v1.1`)

**Phạm vi:** Task `D3.1` (Kế hoạch Tuần 10–11, bản thống nhất `week10_v1.1`)
**Single Source of Truth:** [schemas/models.py](../schemas/models.py)
**JSON Schema Draft:** `https://json-schema.org/draft/2020-12/schema`
**Schema Version:** `SchemaVersionType = Literal["week10_v1.0", "week10_v1.1"]` (`SCHEMA_VERSION = "week10_v1.1"`). Bộ model chấp nhận payload `week10_v1.0` cũ; payload mới mặc định dùng `week10_v1.1`.

Tài liệu này mô tả bộ hợp đồng dữ liệu chuẩn hóa (Pydantic v2 + JSON Schema) dùng chung giữa Router, Retrieval/Reranker, Context/Prompt Builder, Model Gateway, Grounding Gate, API và Monitoring.

---

## 1. Các tập giá trị chuẩn (Standard Literals)

| Tên kiểu | Giá trị hợp lệ | Mục đích |
| :--- | :--- | :--- |
| `SchemaVersionType` | `"week10_v1.0"`, `"week10_v1.1"` | Giữ tương thích khi đọc `v1.0`; producer mới mặc định phát `v1.1` |
| `RouteType` | `"LEGAL_IN_SCOPE"`, `"NON_LEGAL"`, `"LEGAL_OUT_OF_SCOPE"`, `"MIXED_REVIEW"` | Phân luồng câu hỏi chuẩn hóa ở `RouteDecision` và `AskResponse` |
| `RouteAction` | `"LEGAL_RETRIEVAL"`, `"FAST_PATH"`, `"POLICY_ABSTENTION"`, `"GENERAL_CHAT"` | Hành vi xử lý chuẩn theo bảng SRS 5.3.3 trong `RouteDecision.action` |
| `ResponseStatus` | `"SUCCESS"`, `"NEEDS_CLARIFICATION"`, `"ABSTAIN"`, `"ERROR"` | Trạng thái phản hồi chuẩn hóa ở API và `AskResponse` |
| `GroundingStatus` | `"PASS"`, `"FAIL"`, `"NOT_RUN"`, `"ABSTAIN"`, `"NEEDS_CLARIFICATION"` | Trạng thái kiểm định căn cứ ở `GroundingResult` và `AskResponse` |
| `EventStage` | `"api"`, `"router"`, `"retrieval"`, `"rerank"`, `"confidence"`, `"context"`, `"llm"`, `"citation"`, `"gate"`, `"response"` | 10 chặng phát sinh sự kiện trong `LogEvent` (bổ sung `"confidence"` ở `v1.1`) |
| `ErrorCode` | `"AUTH_REQUIRED"`, `"INVALID_REQUEST"`, `"ROUTE_POLICY"`, `"RETRIEVAL_EMPTY"`, `"LOW_CONFIDENCE"`, `"LLM_TIMEOUT"`, `"LLM_UNAVAILABLE"`, `"JSON_INVALID"`, `"CITATION_INVALID"`, `"GROUNDING_FAIL"`, `"INTERNAL_ERROR"` | 11 mã lỗi chuẩn hóa xuyên suốt API, Router, Retrieval, Gateway và Gate (bổ sung `"LLM_UNAVAILABLE"` ở `v1.1`) |

---

## 2. Ánh xạ `Route` nội bộ của Router sang `RouteType` chuẩn

`RuleRouter` ([agent/router/rule_router.py](../agent/router/rule_router.py)) sử dụng enum nội bộ `Route`. Để thống nhất đầu ra qua contract Week 10, `schemas/models.py` cung cấp hàm `map_router_route_to_canonical(router_route: str) -> RouteType`:

| `Route` trong `RuleRouter` | `RouteType` chuẩn (`week10_v1.1`) | Ghi chú |
| :--- | :--- | :--- |
| `Route.LEGAL_HNGD` | `"LEGAL_IN_SCOPE"` | Truy vấn pháp luật HNGĐ thuộc phạm vi trả lời RAG |
| `Route.NON_LEGAL` | `"NON_LEGAL"` | Câu hỏi ngoài pháp luật / giao tiếp thông thường (không cần retrieval/grounding) |
| `Route.LEGAL_OUT_OF_SCOPE` | `"LEGAL_OUT_OF_SCOPE"` | Câu hỏi pháp luật ngoài phạm vi HNGĐ (hình sự, đất đai, thuế, v.v.) |
| `Route.MIXED_LEGAL_SCOPE` / `Route.LEGAL_SCOPE_UNCERTAIN` | `"MIXED_REVIEW"` | Câu hỏi giao thoa hoặc chưa rõ phạm vi, cần rà soát / làm rõ |

---

## 3. 10 Pydantic Models chuẩn hóa & JSON Schemas tương ứng

Tất cả model đều kế thừa `StrictBaseModel` (`extra="forbid"`, `str_strip_whitespace=True`) để từ chối field lạ, khóa `run_mode`/`top_k`/`metadata` tùy tiện và chuẩn hóa chuỗi đầu vào.

### 3.1. JSON Schemas chuẩn hóa (`schemas/generated/*.schema.json`)

Sinh tự động bằng lệnh `python -m schemas.models` (hàm `export_json_schemas()`), mỗi tệp đều gắn `"$schema"` và `"schema_version": "week10_v1.1"`:

| STT | Model (`schemas/models.py`) | Tệp JSON Schema (`schemas/generated/`) | Vai trò |
| :-: | :--- | :--- | :--- |
| 1 | `AskRequest` | `ask_request.schema.json` | Yêu cầu hỏi đáp đầu vào (`query`, `as_of_date`, `session_id`, `request_id`, `query_id`) |
| 2 | `AskResponse` | `ask_response.schema.json` | Phản hồi API tách bạch `SUCCESS` / `ABSTAIN` / `NEEDS_CLARIFICATION` / `ERROR` |
| 3 | `RouteDecision` | `route_decision.schema.json` | Quyết định phân luồng (`route`, `router_route?`, `action` theo `RouteAction`, `reason_code`, `explanation`, `policy_version`) |
| 4 | `Candidate` (`CandidateChunk`) | `candidate.schema.json` | Chunk ứng viên từ Retrieval/Reranker kèm hiệu lực và provenance |
| 5 | `RetrievalBundle` | `retrieval_bundle.schema.json` | Gói kết quả truy xuất, gồm `metadata_filters` (`MetadataFilters`) và `latency_breakdown` (`RetrievalLatencyBreakdown`) bên cạnh candidates, provenance và latency tổng |
| 6 | `EvidenceItem` | `evidence_item.schema.json` | Mảnh bằng chứng đánh số `[1]..[5]` sau Parent Resolver (thêm `point_ref?` ở `v1.1`) |
| 7 | `ContextPayload` | `context_payload.schema.json` | Gói ngữ cảnh đầy đủ truyền vào Prompt Builder & Citation Validator |
| 8 | `LLMResponse` | `llm_response.schema.json` | Kết quả từ Model Gateway + metadata thời gian Ollama, `missing_facts[]` & provenance |
| 9 | `GroundingResult` | `grounding_result.schema.json` | Kết quả kiểm định căn cứ (`status`, `validated_answer`, `citations`, `violation_codes`, `retryable`) |
| 10 | `LogEvent` | `log_event.schema.json` | Sự kiện log có cấu trúc qua 10 `EventStage` kèm `event_id`, `event_type`, `masked_metadata` |

### 3.2. Phân biệt `StructuredRAGOutput` vs `LLMResponse` ở JSON Schema gốc

Để tránh nhầm lẫn giữa schema JSON đầu ra ngắn của Qwen và schema provenance đầy đủ của `LLMResponse`:

- `schemas/structured_rag_output.schema.json`: schema tường minh của `StructuredRAGOutput` (dùng ép kiểu tham số `format` của Ollama cho Run B/C; thêm `missing_facts` tùy chọn ở `v1.1`).
- `schemas/llm_response.schema.json`: bản legacy trỏ cùng `StructuredRAGOutput.model_json_schema()` được giữ lại để bảo toàn 100% tương thích ngược cho bộ test Sprint 9 (`test/schema_test.py`, `test/test_dev3_sprint9_contracts_prompt_gateway.py`).
- `schemas/generated/llm_response.schema.json`: schema chuẩn Week 10 cho toàn bộ model `LLMResponse` của Gateway.
- `schemas/candidate.schema.json` và `schemas/context_payload.schema.json`: hai tệp legacy thuần từ `CandidateChunk` và `ContextPayload`.

---

## 4. Quy ước định danh, trạng thái & bảo mật đầu vào

### 4.1. Phân biệt `request_id` và `query_id`

- **`request_id`** *(tùy chọn trong `AskRequest`)*: mã định danh do phía client/UI gửi lên để đối chiếu yêu cầu từ phía khách (client tracing / idempotency).
- **`query_id`**: mã định danh duy nhất của một lượt xử lý xuyên suốt toàn bộ pipeline phía server (`api` → `router` → `retrieval` → `rerank` → `context` → `llm` → `citation` → `gate` → `LogEvent` → `AskResponse`). Nếu client không truyền `query_id`, API Gateway phải tự sinh ID/UUID mới trước khi gọi Router.

### 4.2. Khóa tham số phía Server ở `AskRequest`

`AskRequest` chỉ nhận `{schema_version, query, as_of_date, session_id, request_id, query_id}`. Các tham số điều khiển nội bộ (`run_mode`, `top_k`) và `metadata` tự do bị **loại bỏ** (`extra="forbid"`) để client không thể vượt rào chế độ RAG hay đưa PII thô vào log.

### 4.3. Quy ước `ResponseStatus` (`SUCCESS` vs `OK` / `answered`) và `ErrorCode` (`GROUNDING_FAIL`)

- Trạng thái thành công chuẩn của `AskResponse` là **`"SUCCESS"`** (thay cho `"OK"` hoặc `"answered"` ở một số mock UI cũ). Cả Pydantic và JSON Schema đều **chỉ chấp nhận `"SUCCESS"`** (đã loại bỏ alias `"OK"` và `clarification_question` để bảo đảm nhất quán tuyệt đối).
- Mã lỗi Gate thất bại chuẩn là **`"GROUNDING_FAIL"`** (thay cho `"GATE_FAIL"`).

### 4.4. Quy tắc tách bạch trạng thái, `route` ↔ `citations` và bảo mật của `AskResponse`

`AskResponse` bổ sung `as_of_date`, `as_of_date_source` (đều bắt buộc, không có giá trị mặc định; cho client biết chính xác ngày hiệu lực mà server đã áp dụng), `timings: AskTimings` (có `total_ms` cho UI), và `error: ErrorDetail | None` (`{message: str, retryable: bool}`, `extra="forbid"` nhằm ngăn lọt traceback hoặc raw prompt ra API). Validator `validate_status_separation` thực thi nghiêm ngặt:

| `status` | `answer` | `grounding_status` hợp lệ | Ràng buộc `route` / `citations` / `evidence` | Trường bắt buộc & bị cấm khác |
| :--- | :--- | :--- | :--- | :--- |
| `SUCCESS` | Chuỗi không rỗng | `"NOT_RUN"` (`NON_LEGAL`) hoặc `"PASS"` (luồng legal) | **Cấm `LEGAL_OUT_OF_SCOPE`**. Với `NON_LEGAL`: `evidence=[]`, `citations=[]`. Với `LEGAL_IN_SCOPE` / `MIXED_REVIEW`: `citations` không rỗng và mọi `citations[].evidence_index` phải có trong `evidence`. | Bắt buộc `disclaimer`, `as_of_date`. Cấm `clarification`, `abstention_message`, `abstention_reason`, `error_code`, `error`. |
| `ABSTAIN` | **Bắt buộc `null`** | `"ABSTAIN"`, `"FAIL"`, `"NOT_RUN"` | Cho phép mọi `route`; `citations` / `evidence` rỗng khi ngắt trước retrieval/LLM | Bắt buộc `disclaimer`, `as_of_date`, và (`abstention_message` hoặc `abstention_reason`). `error_code` chỉ nhận `ROUTE_POLICY`, `RETRIEVAL_EMPTY`, `LOW_CONFIDENCE`, `GROUNDING_FAIL`, `JSON_INVALID` / `CITATION_INVALID` (chỉ khi `grounding_status="FAIL"`, tức Gate FAIL do JSON hỏng hoặc citation sai) hoặc `null`. Cấm `answer`, `clarification`, `error`. |
| `NEEDS_CLARIFICATION` | **Bắt buộc `null`** | `"NEEDS_CLARIFICATION"`, `"NOT_RUN"` | `clarification` không rỗng | Bắt buộc `disclaimer`, `as_of_date`, `clarification`. Cấm `answer`, `abstention_message`, `abstention_reason`, `error_code`, `error`. |
| `ERROR` | **Bắt buộc `null`** | Khác `"PASS"` (thường `"FAIL"` hoặc `"NOT_RUN"`) | `error` là `ErrorDetail` có kiểu (`{message, retryable}`) | Bắt buộc `disclaimer`, `as_of_date` và **`error_code` khác `null`**. Cấm `answer`, `clarification`, `abstention_message`, `abstention_reason`. |

> [!IMPORTANT]
> - Khi `status` là `"ABSTAIN"`, `"NEEDS_CLARIFICATION"` hoặc `"ERROR"`, trường `answer` **luôn phải là `null`** (không đặt chuỗi rỗng `""` hay câu thông báo vào `answer`), để tránh rò rỉ nháp câu trả lời hoặc nhầm lẫn trên UI.
> - Trong `GroundingResult`: trường canonical là `status`, `validated_answer`, `citations`, `violation_codes`, `retryable`, `abstention_reason` (bắt buộc có `status` hoặc `grounding_status`, bỏ default `"PASS"`, `is_grounded == (status == "PASS")`, và `abstention_reason` chỉ dùng khi `status == "ABSTAIN"`). Các trường cũ (`grounding_status`, `valid_citations`, `invalid_indices`, `unsupported_claims`, `reason`) đã ở trạng thái **deprecated**, chỉ giữ tạm qua `@model_validator` để tương thích với code Sprint 9 (`grounding/citation_validator.py`, `orchestration/rag_pipeline.py`).

---

## 5. Hợp đồng an toàn của Model Gateway (`D3.3` & `D3.4`)

1. **Tách số lượng token không đo được (`TokenUsage`):** `input` và `output` mặc định `None` (`null` trong JSON), chỉ ghi số nguyên không âm khi Ollama trả về `prompt_eval_count` / `eval_count`; **tuyệt đối không bịa `0` khi thiếu số liệu**.
2. **Loại bỏ markdown fence & kiểm tra cấu trúc JSON:**
   - Tự động bóc ` ```json ... ``` ` hoặc ` ``` ... ``` ` trước `json.loads`.
   - Kiểm tra bắt buộc có `"answer"` dạng chuỗi và đối chiếu qua `StructuredRAGOutput.model_validate(...)` (`extra="forbid"`). Khi JSON hỏng hoặc vi phạm cấu trúc: `answer=""`, `error_code="JSON_INVALID"`, `parse_status` là `"truncated_json"` (khi `done_reason == "length"`) hoặc `"invalid_json"`.
3. **Kiểm tra phạm vi chỉ số trích dẫn (`max_evidence_index`):**
   - Nếu truyền `max_evidence_index`, mọi chỉ số nguyên ngoài `[1, max_evidence_index]` (cùng giá trị phi số nguyên) bị đưa vào `rejected_evidence_values` và gắn `error_code="CITATION_INVALID"`.
   - Khi không truyền `max_evidence_index`, giữ nguyên tương thích ngược cho Grounding Gate xử lý.
4. **Mã lỗi vận chuyển (`GatewayExecutionError.error_code`):** Timeout kết thúc retry mang `error_code="LLM_TIMEOUT"` (`retryable=True`); không kết nối được Ollama/HTTP 502–503 mang `error_code="LLM_UNAVAILABLE"` (`retryable=True`); sai model cấu hình mang `error_code="INTERNAL_ERROR"` (`retryable=False`).
5. **Tham chiếu phản hồi gốc (`raw_response_reference`):** Chuỗi an toàn dạng `ollama://<run_mode>/<query_id>#sha256:<12-hex>`.

---

## 6. Danh mục Payload mẫu (`schemas/examples/`)

- [ask_request_valid.json](../schemas/examples/ask_request_valid.json)
- [ask_response_ok.json](../schemas/examples/ask_response_ok.json)
- [ask_response_abstain.json](../schemas/examples/ask_response_abstain.json)
- [ask_response_needs_clarification.json](../schemas/examples/ask_response_needs_clarification.json)
- [ask_response_error_timeout.json](../schemas/examples/ask_response_error_timeout.json)
- [route_decision_out_of_scope.json](../schemas/examples/route_decision_out_of_scope.json)
- [retrieval_bundle_valid.json](../schemas/examples/retrieval_bundle_valid.json)
- [log_event_generate.json](../schemas/examples/log_event_generate.json)

---

## 7. Migration Note (Cập nhật Contract `week10_v1.1` cho Dev 1, Dev 2, Dev 4, Dev 5)

| Thành viên | Điểm cần đồng bộ sang Contract `week10_v1.1` |
| :--- | :--- |
| **Dev 1 (Grounding & Validator)** | `GroundingResult` giữ tạm các trường **deprecated** (`grounding_status`, `valid_citations`, `invalid_indices`, `reason`) để tương thích với `citation_validator.py`; khi nâng cấp chuyển sang `status`, `validated_answer`, `citations`, `violation_codes`, `retryable`, `abstention_reason` (mã `"GROUNDING_FAIL"` thay cho `"GATE_FAIL"`, lưu ý `abstention_reason` chỉ dùng ở nhánh `ABSTAIN`). |
| **Dev 2 (Evaluation & Monitoring)** | Đọc/ghi log theo `LogEvent` mới: dùng `event_id`, `event_type`, `duration_ms`, `masked_metadata` và 10 `EventStage` (thêm `"confidence"`); xử lý `TokenUsage.input`/`output` có thể là `null`; `RAGOutputRecord.route` cho phép gán nhãn route chuẩn. |
| **Dev 4 (Router & Retrieval)** | Khi xuất `RouteDecision` ra API/Pipeline dùng `map_router_route_to_canonical()` kèm `router_route?` và `action` thuộc `RouteAction` (`LEGAL_RETRIEVAL`, `FAST_PATH`, `POLICY_ABSTENTION`, `GENERAL_CHAT`). `RetrievalBundle` `v1.1` bổ sung `metadata_filters` (`MetadataFilters`) và `latency_breakdown` (`RetrievalLatencyBreakdown`, giá trị chưa đo là `null`). |
| **Dev 5 (API Gateway & Orchestration)** | Nhận `AskRequest` đã khóa; ánh xạ `LLM_UNAVAILABLE` sang HTTP 503 (`retryable=True`); đồng bộ `stage="confidence"`, `EvidenceItem.point_ref`, `missing_facts`, và tái sinh `api/openapi.json` bằng `python -m api.export_openapi`. |

---

## 8. Lệnh tái tạo & kiểm chứng hợp đồng

```powershell
python -m schemas.models
python -m pytest -q test/schemas/test_contracts.py test/model_gateway/test_structured_output.py
```
