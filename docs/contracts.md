# Canonical Contracts Specification (`week10_v1.0`)

**Phạm vi:** Task `D3.1` (Kế hoạch Tuần 10)  
**Single Source of Truth:** `schemas/models.py`  
**JSON Schema Draft:** `https://json-schema.org/draft/2020-12/schema`  
**Schema Version:** `week10_v1.0`

Tài liệu này mô tả bộ hợp đồng dữ liệu chuẩn hóa (Pydantic v2 + JSON Schema) dùng chung giữa Router, Retrieval/Reranker, Context/Prompt Builder, Model Gateway, Grounding Gate, API và Monitoring.

---

## 1. Các tập giá trị chuẩn (Standard Literals)

| Tên kiểu | Giá trị hợp lệ | Mục đích |
| :--- | :--- | :--- |
| `RouteType` | `"FACTUAL_LEGAL"`, `"OUT_OF_SCOPE"`, `"AMBIGUOUS"`, `"SYSTEM_META"` | Phân luồng câu hỏi ở `RouteDecision` và `AskResponse` |
| `ResponseStatus` | `"OK"`, `"ABSTAIN"`, `"NEEDS_CLARIFICATION"`, `"ERROR"` | Trạng thái phản hồi ở tầng API và log |
| `GroundingStatus` | `"PASS"`, `"FAIL"`, `"ABSTAIN"`, `"NEEDS_CLARIFICATION"` | Trạng thái kiểm định căn cứ ở `GroundingResult` và `RAGOutputRecord` |
| `EventStage` | `"request"`, `"route"`, `"retrieve"`, `"context"`, `"generate"`, `"grounding"`, `"response"`, `"error"` | Giai đoạn phát sinh sự kiện trong `LogEvent` |
| `ErrorCode` | `"LLM_TIMEOUT"`, `"JSON_INVALID"`, `"CITATION_INVALID"`, `"GATE_FAIL"`, `"INTERNAL_ERROR"` | Mã lỗi chuẩn hóa khi hệ thống lỗi hoặc phản hồi LLM vi phạm hợp đồng |

---

## 2. 10 Pydantic Models chuẩn hóa & JSON Schemas tương ứng

Tất cả model đều kế thừa `StrictBaseModel` (`extra="forbid"`, `str_strip_whitespace=True`) để từ chối field lạ hoặc khoảng trắng thừa.

### 2.1. JSON Schemas chuẩn hóa (`schemas/generated/*.schema.json`)

Sinh tự động bằng lệnh `python -m schemas.models` (hàm `export_json_schemas()`), mỗi tệp đều gắn `"$schema"` và `"schema_version": "week10_v1.0"`:

| STT | Model (`schemas/models.py`) | Tệp JSON Schema (`schemas/generated/`) | Vai trò |
| :-: | :--- | :--- | :--- |
| 1 | `AskRequest` | `ask_request.schema.json` | Yêu cầu hỏi đáp đầu vào (`query`, `as_of_date`, `run_mode`, `top_k`) |
| 2 | `AskResponse` | `ask_response.schema.json` | Phản hồi API chuẩn hóa tách biệt `OK` / `ABSTAIN` / `NEEDS_CLARIFICATION` / `ERROR` |
| 3 | `RouteDecision` | `route_decision.schema.json` | Quyết định phân luồng từ Router (`route`, `should_retrieve`, `rule_id`) |
| 4 | `Candidate` (`CandidateChunk`) | `candidate.schema.json` | Chunk ứng viên từ Retrieval/Reranker kèm hiệu lực và provenance |
| 5 | `RetrievalBundle` | `retrieval_bundle.schema.json` | Gói danh sách `CandidateChunk` trước bước xây ngữ cảnh |
| 6 | `EvidenceItem` | `evidence_item.schema.json` | Mảnh bằng chứng đánh số `[1]..[5]` sau Parent Resolver |
| 7 | `ContextPayload` | `context_payload.schema.json` | Gói ngữ cảnh đầy đủ truyền vào Prompt Builder & Citation Validator |
| 8 | `LLMResponse` | `llm_response.schema.json` | Kết quả từ Model Gateway + metadata thời gian Ollama & provenance |
| 9 | `GroundingResult` | `grounding_result.schema.json` | Kết quả kiểm định căn cứ pháp lý và danh sách `MappedCitation` |
| 10 | `LogEvent` | `log_event.schema.json` | Sự kiện log có cấu trúc cho từng chặng xử lý của một `trace_id` |

### 2.2. JSON Schemas tương thích ngược (`schemas/*.schema.json`)

Để giữ tương thích ngược 100% với bài kiểm thử Sprint 9 / Run B và tham số `format` của Ollama:

- `schemas/candidate.schema.json`: xuất `CandidateChunk.model_json_schema()` thuần.
- `schemas/context_payload.schema.json`: xuất `ContextPayload.model_json_schema()` thuần.
- `schemas/llm_response.schema.json`: xuất `StructuredRAGOutput.model_json_schema()` thuần (schema 5 trường dùng trực tiếp làm Ollama `format` cho Run B/C), phân biệt với `schemas/generated/llm_response.schema.json` là toàn bộ wrapper provenance `LLMResponse`.

---

## 3. Quy tắc tách biệt trạng thái của `AskResponse`

`AskResponse.validate_status_separation` thực thi bất biến loại trừ lẫn nhau để ngăn lỗi trộn trạng thái:

| `status` | `grounding_status` bắt buộc | `abstained` | `needs_clarification` | `error_code` | Ràng buộc bổ sung |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `OK` | `"PASS"` | `false` | `false` | `null` | `answer` không rỗng |
| `ABSTAIN` | `"ABSTAIN"` hoặc `"FAIL"` | `true` | `false` | `null` | `abstention_reason` không rỗng |
| `NEEDS_CLARIFICATION` | `"NEEDS_CLARIFICATION"` | `false` | `true` | `null` | Dùng khi câu hỏi thiếu ngữ cảnh hoặc mơ hồ |
| `ERROR` | khác `"PASS"` (ví dụ `"FAIL"`) | `false` | `false` | khác `null` | Bắt buộc có `error_code` thuộc `ErrorCode` |

---

## 4. Hợp đồng an toàn của Model Gateway (`D3.3` & `D3.4`)

1. **Tách số lượng token không đo được (`TokenUsage`):** `input` và `output` có giá trị mặc định `None` (`null` trong JSON). Gateway chỉ ghi số nguyên khi Ollama trả về `prompt_eval_count` / `eval_count` không âm; **tuyệt đối không bịa `0` khi thiếu số liệu**.
2. **Loại bỏ markdown fence & kiểm tra cấu trúc JSON:**
   - Tự động bóc ` ```json ... ``` ` hoặc ` ``` ... ``` ` trước `json.loads`.
   - Kiểm tra bắt buộc có `"answer"` dạng chuỗi và đối chiếu qua `StructuredRAGOutput.model_validate(...)` (`extra="forbid"`) để từ chối JSON thiếu khóa bắt buộc hoặc có khóa thừa lạ. Khi lỗi cấu trúc hoặc JSON hỏng: `answer=""`, `error_code="JSON_INVALID"`, `parse_status` là `"truncated_json"` (nếu `done_reason == "length"`) hoặc `"invalid_json"`.
3. **Kiểm tra phạm vi chỉ số trích dẫn (`max_evidence_index`):**
   - Nếu `max_evidence_index` được truyền vào (`generate(..., max_evidence_index=len(evidence_items))`), các chỉ số nguyên ngoài `[1, max_evidence_index]` (cùng mọi phần tử không phải `int` như `bool`, `float`, `str`) sẽ bị loại khỏi `evidence_indices`, lưu JSON-encoded vào `rejected_evidence_values` và gắn `error_code="CITATION_INVALID"`.
   - Khi không truyền `max_evidence_index`, hành vi legacy vẫn được giữ nguyên cho số nguyên ngoài `[1, 5]` để Grounding Gate xử lý.
4. **Mã lỗi vận chuyển (`GatewayExecutionError.error_code`):** Lỗi timeout kết thúc retry mang `error_code="LLM_TIMEOUT"`; các lỗi kết nối, HTTP hoặc sai lệch model mang `error_code="INTERNAL_ERROR"`.
5. **Tham chiếu phản hồi gốc (`raw_response_reference`):** Tạo mã định danh an toàn dạng `ollama://<run_mode>/<query_id>#sha256:<12-hex>` cho mọi phản hồi không rỗng từ model.

---

## 5. Danh mục Payload mẫu (`schemas/examples/`)

- [ask_request_valid.json](file:///C:/Users/Laptop%20K1/IdeaProjects/Vietnam-Legal-RAG-Assistant/schemas/examples/ask_request_valid.json)
- [ask_response_ok.json](file:///C:/Users/Laptop%20K1/IdeaProjects/Vietnam-Legal-RAG-Assistant/schemas/examples/ask_response_ok.json)
- [ask_response_abstain.json](file:///C:/Users/Laptop%20K1/IdeaProjects/Vietnam-Legal-RAG-Assistant/schemas/examples/ask_response_abstain.json)
- [ask_response_needs_clarification.json](file:///C:/Users/Laptop%20K1/IdeaProjects/Vietnam-Legal-RAG-Assistant/schemas/examples/ask_response_needs_clarification.json)
- [ask_response_error_timeout.json](file:///C:/Users/Laptop%20K1/IdeaProjects/Vietnam-Legal-RAG-Assistant/schemas/examples/ask_response_error_timeout.json)
- [route_decision_out_of_scope.json](file:///C:/Users/Laptop%20K1/IdeaProjects/Vietnam-Legal-RAG-Assistant/schemas/examples/route_decision_out_of_scope.json)
- [retrieval_bundle_valid.json](file:///C:/Users/Laptop%20K1/IdeaProjects/Vietnam-Legal-RAG-Assistant/schemas/examples/retrieval_bundle_valid.json)
- [log_event_generate.json](file:///C:/Users/Laptop%20K1/IdeaProjects/Vietnam-Legal-RAG-Assistant/schemas/examples/log_event_generate.json)

---

## 6. Lệnh tái tạo & kiểm chứng hợp đồng

```powershell
python -m schemas.models
python -m pytest -q test/schemas/test_contracts.py test/model_gateway/test_structured_output.py
```
