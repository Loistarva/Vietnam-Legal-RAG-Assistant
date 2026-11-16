# Canonical Contracts Specification (`week10_v1.0`)

**Phạm vi:** Task `D3.1` (Kế hoạch Tuần 10)  
**Single Source of Truth:** [schemas/models.py](../schemas/models.py)  
**JSON Schema Draft:** `https://json-schema.org/draft/2020-12/schema`  
**Schema Version:** `SchemaVersionType = Literal["week10_v1.0"]` (`SCHEMA_VERSION = "week10_v1.0"`)

Tài liệu này mô tả bộ hợp đồng dữ liệu chuẩn hóa (Pydantic v2 + JSON Schema) dùng chung giữa Router, Retrieval/Reranker, Context/Prompt Builder, Model Gateway, Grounding Gate, API và Monitoring.

---

## 1. Các tập giá trị chuẩn (Standard Literals)

| Tên kiểu | Giá trị hợp lệ | Mục đích |
| :--- | :--- | :--- |
| `SchemaVersionType` | `"week10_v1.0"` | Khóa cứng phiên bản schema ở mọi canonical model có `schema_version` |
| `RouteType` | `"LEGAL_IN_SCOPE"`, `"NON_LEGAL"`, `"LEGAL_OUT_OF_SCOPE"`, `"MIXED_REVIEW"` | Phân luồng câu hỏi chuẩn hóa ở `RouteDecision` và `AskResponse` |
| `ResponseStatus` | `"SUCCESS"`, `"NEEDS_CLARIFICATION"`, `"ABSTAIN"`, `"ERROR"` | Trạng thái phản hồi chuẩn hóa ở API và `AskResponse` |
| `GroundingStatus` | `"PASS"`, `"FAIL"`, `"NOT_RUN"`, `"ABSTAIN"`, `"NEEDS_CLARIFICATION"` | Trạng thái kiểm định căn cứ ở `GroundingResult` và `AskResponse` |
| `EventStage` | `"api"`, `"router"`, `"retrieval"`, `"rerank"`, `"context"`, `"llm"`, `"citation"`, `"gate"`, `"response"` | 9 chặng phát sinh sự kiện trong `LogEvent` |
| `ErrorCode` | `"AUTH_REQUIRED"`, `"INVALID_REQUEST"`, `"ROUTE_POLICY"`, `"RETRIEVAL_EMPTY"`, `"LOW_CONFIDENCE"`, `"LLM_TIMEOUT"`, `"JSON_INVALID"`, `"CITATION_INVALID"`, `"GROUNDING_FAIL"`, `"INTERNAL_ERROR"` | 10 mã lỗi chuẩn hóa xuyên suốt API, Router, Retrieval, Gateway và Gate |

---

## 2. Ánh xạ `Route` nội bộ của Router sang `RouteType` chuẩn

`RuleRouter` ([agent/router/rule_router.py](../agent/router/rule_router.py)) sử dụng enum nội bộ `Route`. Để thống nhất đầu ra qua contract Week 10, `schemas/models.py` cung cấp hàm `map_router_route_to_canonical(router_route: str) -> RouteType`:

| `Route` trong `RuleRouter` | `RouteType` chuẩn (`week10_v1.0`) | Ghi chú |
| :--- | :--- | :--- |
| `Route.LEGAL_HNGD` | `"LEGAL_IN_SCOPE"` | Truy vấn pháp luật HNGĐ thuộc phạm vi trả lời RAG |
| `Route.NON_LEGAL` | `"NON_LEGAL"` | Câu hỏi ngoài pháp luật / giao tiếp thông thường (không cần retrieval/grounding) |
| `Route.LEGAL_OUT_OF_SCOPE` | `"LEGAL_OUT_OF_SCOPE"` | Câu hỏi pháp luật ngoài phạm vi HNGĐ (hình sự, đất đai, thuế, v.v.) |
| `Route.MIXED_LEGAL_SCOPE` / `Route.LEGAL_SCOPE_UNCERTAIN` | `"MIXED_REVIEW"` | Câu hỏi giao thoa hoặc chưa rõ phạm vi, cần rà soát / làm rõ |

---

## 3. 10 Pydantic Models chuẩn hóa & JSON Schemas tương ứng

Tất cả model đều kế thừa `StrictBaseModel` (`extra="forbid"`, `str_strip_whitespace=True`) để từ chối field lạ, khóa `run_mode`/`top_k`/`metadata` tùy tiện và chuẩn hóa chuỗi đầu vào.

### 3.1. JSON Schemas chuẩn hóa (`schemas/generated/*.schema.json`)

Sinh tự động bằng lệnh `python -m schemas.models` (hàm `export_json_schemas()`), mỗi tệp đều gắn `"$schema"` và `"schema_version": "week10_v1.0"`:

| STT | Model (`schemas/models.py`) | Tệp JSON Schema (`schemas/generated/`) | Vai trò |
| :-: | :--- | :--- | :--- |
| 1 | `AskRequest` | `ask_request.schema.json` | Yêu cầu hỏi đáp đầu vào (`query`, `as_of_date`, `session_id`, `request_id`, `query_id`) |
| 2 | `AskResponse` | `ask_response.schema.json` | Phản hồi API tách bạch `SUCCESS` / `ABSTAIN` / `NEEDS_CLARIFICATION` / `ERROR` |
| 3 | `RouteDecision` | `route_decision.schema.json` | Quyết định phân luồng (`route`, `reason_code`, `explanation`, `policy_version`) |
| 4 | `Candidate` (`CandidateChunk`) | `candidate.schema.json` | Chunk ứng viên từ Retrieval/Reranker kèm hiệu lực và provenance |
| 5 | `RetrievalBundle` | `retrieval_bundle.schema.json` | Gói kết quả truy xuất (`candidates`, `retrieval_config_version`, `corpus_hash`, `latency_ms`) |
| 6 | `EvidenceItem` | `evidence_item.schema.json` | Mảnh bằng chứng đánh số `[1]..[5]` sau Parent Resolver |
| 7 | `ContextPayload` | `context_payload.schema.json` | Gói ngữ cảnh đầy đủ truyền vào Prompt Builder & Citation Validator |
| 8 | `LLMResponse` | `llm_response.schema.json` | Kết quả từ Model Gateway + metadata thời gian Ollama & provenance |
| 9 | `GroundingResult` | `grounding_result.schema.json` | Kết quả kiểm định căn cứ (`status`, `validated_answer`, `citations`, `violation_codes`, `retryable`) |
| 10 | `LogEvent` | `log_event.schema.json` | Sự kiện log có cấu trúc qua 9 `EventStage` kèm `event_id`, `event_type`, `masked_metadata` |

### 3.2. Phân biệt `StructuredRAGOutput` vs `LLMResponse` ở JSON Schema gốc

Để tránh nhầm lẫn giữa schema JSON đầu ra ngắn của Qwen và schema provenance đầy đủ của `LLMResponse`:

- `schemas/structured_rag_output.schema.json`: schema tường minh của `StructuredRAGOutput` (5 trường dùng ép kiểu tham số `format` của Ollama cho Run B/C).
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

- Trạng thái thành công chuẩn của `AskResponse` là **`"SUCCESS"`** (thay cho `"OK"` hoặc `"answered"` ở một số mock UI cũ). Validator `normalize_legacy_ok_status` tự chuẩn hóa `"OK"` → `"SUCCESS"` ở đầu vào nhưng JSON Schema chuẩn chỉ chấp nhận `"SUCCESS"`.
- Mã lỗi Gate thất bại chuẩn là **`"GROUNDING_FAIL"`** (thay cho `"GATE_FAIL"`).

### 4.4. Quy tắc tách bạch trạng thái của `AskResponse`

`AskResponse.validate_status_separation` thực thi nghiêm ngặt:

| `status` | `answer` | `grounding_status` hợp lệ | Trường bắt buộc khác | Trường bị cấm khác `null` |
| :--- | :--- | :--- | :--- | :--- |
| `SUCCESS` | Chuỗi không rỗng | `"PASS"` (hoặc `"NOT_RUN"`/`"PASS"` nếu `route == "NON_LEGAL"`) | `disclaimer` không rỗng | `clarification`, `abstention_message`, `abstention_reason`, `error_code`, `error` |
| `ABSTAIN` | **Bắt buộc `null`** | `"ABSTAIN"`, `"FAIL"`, `"NOT_RUN"` | `disclaimer` và (`abstention_message` hoặc `abstention_reason`) không rỗng | `answer`, `clarification` |
| `NEEDS_CLARIFICATION` | **Bắt buộc `null`** | `"NEEDS_CLARIFICATION"`, `"NOT_RUN"` | `disclaimer` và `clarification` không rỗng | `answer`, `abstention_message`, `abstention_reason`, `error_code`, `error` |
| `ERROR` | **Bắt buộc `null`** | Khác `"PASS"` (thường `"FAIL"` hoặc `"NOT_RUN"`) | `disclaimer` không rỗng và (`error_code` hoặc `error`) khác `null` | `answer`, `clarification`, `abstention_message`, `abstention_reason` |

> [!IMPORTANT]
> Khi `status` là `"ABSTAIN"`, `"NEEDS_CLARIFICATION"` hoặc `"ERROR"`, trường `answer` **luôn phải là `null`** (không đặt chuỗi rỗng `""` hay câu thông báo vào `answer`), để tránh rò rỉ nháp câu trả lời hoặc nhầm lẫn trên UI.

---

## 5. Hợp đồng an toàn của Model Gateway (`D3.3` & `D3.4`)

1. **Tách số lượng token không đo được (`TokenUsage`):** `input` và `output` mặc định `None` (`null` trong JSON), chỉ ghi số nguyên không âm khi Ollama trả về `prompt_eval_count` / `eval_count`; **tuyệt đối không bịa `0` khi thiếu số liệu**.
2. **Loại bỏ markdown fence & kiểm tra cấu trúc JSON:**
   - Tự động bóc ` ```json ... ``` ` hoặc ` ``` ... ``` ` trước `json.loads`.
   - Kiểm tra bắt buộc có `"answer"` dạng chuỗi và đối chiếu qua `StructuredRAGOutput.model_validate(...)` (`extra="forbid"`). Khi JSON hỏng hoặc vi phạm cấu trúc: `answer=""`, `error_code="JSON_INVALID"`, `parse_status` là `"truncated_json"` (khi `done_reason == "length"`) hoặc `"invalid_json"`.
3. **Kiểm tra phạm vi chỉ số trích dẫn (`max_evidence_index`):**
   - Nếu truyền `max_evidence_index`, mọi chỉ số nguyên ngoài `[1, max_evidence_index]` (cùng giá trị phi số nguyên) bị đưa vào `rejected_evidence_values` và gắn `error_code="CITATION_INVALID"`.
   - Khi không truyền `max_evidence_index`, giữ nguyên tương thích ngược cho Grounding Gate xử lý.
4. **Mã lỗi vận chuyển (`GatewayExecutionError.error_code`):** Timeout kết thúc retry mang `error_code="LLM_TIMEOUT"`; các lỗi kết nối/HTTP/sai model mang `error_code="INTERNAL_ERROR"`.
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

## 7. Migration Note (Cập nhật Contract Tuần 10 cho Dev 1, Dev 2, Dev 4, Dev 5)

| Thành viên | Điểm cần đồng bộ sang Contract `week10_v1.0` |
| :--- | :--- |
| **Dev 1 (Grounding & Validator)** | `GroundingResult` giữ tương thích ngược với `grounding_status`, `is_grounded`, `valid_citations`, `invalid_indices`, `reason`; khi nâng cấp tuần 10 sử dụng thêm `status`, `validated_answer`, `citations`, `violation_codes`, `retryable`, `abstention_reason` (mã `"GROUNDING_FAIL"` thay cho `"GATE_FAIL"`). |
| **Dev 2 (Evaluation & Monitoring)** | Đọc/ghi log theo `LogEvent` mới: dùng `event_id`, `event_type`, `duration_ms`, `masked_metadata` và 9 `EventStage` (`api`, `router`, `retrieval`, `rerank`, `context`, `llm`, `citation`, `gate`, `response`); xử lý `TokenUsage.input`/`output` có thể là `null`. |
| **Dev 4 (Router & Retrieval)** | Khi xuất `RouteDecision` ra API/Pipeline dùng `map_router_route_to_canonical()` để chuyển `Route` (`LEGAL_HNGD`, `MIXED_LEGAL_SCOPE`, `LEGAL_SCOPE_UNCERTAIN`...) sang `RouteType` (`LEGAL_IN_SCOPE`, `NON_LEGAL`, `LEGAL_OUT_OF_SCOPE`, `MIXED_REVIEW`) kèm `reason_code`, `explanation`, `policy_version`. Gói truy xuất dùng `RetrievalBundle` mới (`retrieval_config_version`, `corpus_hash`, `precomputed`, `latency_ms`). |
| **Dev 5 (API Gateway & Orchestration)** | Nhận `AskRequest` đã khóa (`query`, `as_of_date`, `session_id`, `request_id`, `query_id`; không nhận `run_mode`/`top_k`/`metadata`). Sinh `query_id` nếu thiếu. Trả `AskResponse` dùng `status="SUCCESS"` (không dùng `"OK"`/`"answered"`), luôn gán `disclaimer` không rỗng, để `answer=None` ở mọi nhánh `ABSTAIN`/`NEEDS_CLARIFICATION`/`ERROR`, điền `evidence: list[EvidenceItem]`, `timings`, và phân biệt `grounding_status="NOT_RUN"` cho nhánh `NON_LEGAL` hoặc dừng sớm trước LLM. |

---

## 8. Lệnh tái tạo & kiểm chứng hợp đồng

```powershell
python -m schemas.models
python -m pytest -q test/schemas/test_contracts.py test/model_gateway/test_structured_output.py
```
