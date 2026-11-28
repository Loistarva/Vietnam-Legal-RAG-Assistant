# Hỏi lại theo `missing_facts` và sinh lại có giới hạn – S12-D5.2 (Sprint 12, Dev 5)

Ngày 26/11/2026. Nhánh `feature/sprint12-dev5` (đặt trên `testing` sau PR #61). Căn cứ: SRS 2.1.3 (PR #68): FR3.4, FR3.6, FR5.6, D-05, D-06, D-11 (phương án A), bảng 5.3.4 dòng "Model báo thiếu dữ kiện, hệ thống hỏi lại"; kế hoạch Sprint 12 V1.5, task S12-D5.2.

## 1. Active Clarification (FR3.4)

- `orchestration/clarification.py`: danh mục câu hỏi có phiên bản (`ClarificationCatalog`), nạp từ YAML `{version, generic_message, facts: {<mã>: {question}}}`. Thiếu khóa hoặc giá trị rỗng thì dừng khi khởi động, báo tên khóa (NFR5.1).
- Khi Gate trả `NEEDS_CLARIFICATION`, `AskService` giữ các mã `missing_facts` có trong danh mục (theo thứ tự model trả, bỏ trùng) và dựng câu hỏi từ mẫu cố định. Mã ngoài danh mục bị bỏ, không vào response hay log. Không còn mã nào thì dùng thông báo chung của danh mục; chưa cấu hình danh mục thì dùng thông báo chung FR3.6 (FR3.4-AC4).
- Phản hồi: `status = grounding_status = NEEDS_CLARIFICATION`, `answer = null`, `citations = []`, có disclaimer, HTTP 200 (FR3.4-AC3). Không thêm trường hay mã lỗi.
- Log: sự kiện `response/clarification_built` ghi mã đã giữ, số mã bị bỏ, phiên bản danh mục, cờ `generic_clarification`.
- Cấu hình: `LEGAL_RAG_CLARIFICATION_CATALOG` (runbook). Danh mục và mẫu câu chính thức do Dev 3 làm ở S12-D3.2. Repo chỉ có fixture test `test/fixtures/sprint12/clarification_catalog_test.yaml`, nên tới khi có file của Dev 3, API trả thông báo chung.
- Prompt official `v1.2` không yêu cầu model trả `missing_facts`; prompt nào dùng cho API sau lượt Test 30 do Tech Lead chốt (S12-DEC-01).

## 2. Sinh lại có giới hạn (FR5.6)

- `orchestration/regeneration.py`: Gate FAIL với lý do sửa được thì gọi model thêm đúng một lần, cùng evidence, `as_of_date` và giới hạn chỉ số; Gate quyết định theo lần hai (FR5.6-AC1, AC2).
- Lý do sửa được, theo câu chữ FR5.6, cho tới khi Dev 1 giao tập mã ở S12-D1.2: `LLM_OUTPUT_TRUNCATED`, `LLM_OUTPUT_TRUNCATED_JSON` (đầu ra bị cắt), `ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES` (ký hiệu `[n]` chưa khai báo). Không sinh lại cho citation ngoài ngữ cảnh, sai provenance, JSON lỗi hay câu trả lời không phải tiếng Việt.
- Lần hai không gửi lại y hệt request, vì ở temperature 0 model sẽ trả cùng kết quả. Prompt gốc giữ nguyên và được nối thêm một đoạn sửa lỗi cố định theo lý do (`repair_notes_v1`). Hash của cả hai prompt, lý do và câu trả lời lần đầu nằm trong `retrieval_trace.regeneration`.
- `llm_calls = 2`; token cộng hai lần gọi; `llm_total_ms`, `prompt_eval_ms`, `eval_ms` cộng; `ttft_model_ms` và `load_ms` lấy lần đầu.
- Official: `RAGPipeline` từ chối bật sinh lại với `run_mode = B_controlled_rag`; manifest của `scripts/run_rag_batch.py` ghi `regeneration_enabled: false` (FR5.6-AC3). API bật mặc định, tắt bằng `LEGAL_RAG_REGENERATION=off`.

## 3. Sơ đồ (SRS mục 7, D-11)

`architecture/system_architecture.drawio`: cạnh "Low Confidence / Rỗng" từ Confidence Threshold Filter chuyển đích từ Active Clarification sang Policy Abstention (FR3.3, D-11). Thêm cạnh "Needs clarification" từ Grounding Gate sang Active Clarification. Không đổi khối nào. Hình chưa được xem bằng draw.io trên máy này; đường đi được kiểm không cắt khối khác.

## 4. Test

| Mã | Test |
| --- | --- |
| FR3.4-AC3, AC4, FR3.6-AC1 | `test/orchestration/test_clarification.py`, `test/orchestration/test_ask_service.py::test_model_clarification_uses_catalog_and_logs_only_kept_codes`, `test/api/test_error_mapping.py::test_api_clarification_returns_fixed_questions` |
| NFR5.1 | `test/orchestration/test_clarification.py::test_invalid_catalog_names_key`, `test_configured_missing_file_propagates` |
| FR5.6-AC1, AC2 | `test/orchestration/test_regeneration.py` (bị cắt một lần → SUCCESS, luôn bị cắt → dừng ở 2 lần gọi, ký hiệu chưa khai báo, CITATION_INVALID không sinh lại, tắt sinh lại, lần hai hỏi lại/từ chối) |
| FR5.6-AC3 | `test_official_mode_rejects_regeneration`, `test/evaluation/test_run_rag_batch.py::test_ollama_preflight_records_runtime_and_generation_provenance` |

FR3.4-AC1, AC2, AC5 (tỷ lệ trên tập câu âm) đo ở S12-D1.2 (Dev 1) sau khi nhánh này lên `testing` và có danh mục của Dev 3.

Full suite: 1.969 passed, 2 skipped; ruff sạch (26/11/2026).
