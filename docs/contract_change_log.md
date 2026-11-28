# Contract Change Log (`schemas/`, `configs/`, `test/fixtures/sprint12/`)

Tài liệu theo dõi thay đổi canonical contracts (`week10_v1.0` -> `week10_v1.1`), cấu hình danh mục đóng `missing_facts`, khóa hash prompt và bộ fixture bàn giao Sprint 12 theo SRS mục 5.6 & Sprint 12 V1.5 (`S12-D3.1`, `S12-D3.2`).

---

## 1. Lịch sử phiên bản Contract Schema (`schemas/models.py`)

| Phiên bản | Nguồn / PR | Trạng thái trên `testing` | Nội dung thay đổi | Tương thích ngược |
| --- | --- | --- | --- | --- |
| `week10_v1.0` | Sprint 10 Baseline | Đã hợp nhất | 10 Pydantic models gốc (`AskRequest`, `AskResponse`, `RouteDecision`, `CandidateChunk`, `RetrievalBundle`, `EvidenceItem`, `ContextPayload`, `LLMResponse`, `GroundingResult`, `LogEvent`) | Nền |
| `week10_v1.1` | PR #56 + PR #63 (D-11 A, SRS 5.6) | Đã hợp nhất (`origin/testing`) | 1) `ErrorCode` thêm `LLM_UNAVAILABLE` (HTTP 503).<br>2) `EventStage` thêm `confidence`.<br>3) `EvidenceItem.point_ref` (optional) + `source_map` giữ tương thích ngược nếu thiếu `point_ref`.<br>4) `RetrievalBundle.metadata_filters` (`MetadataFilters \| None`) và `RetrievalBundle.latency_breakdown` (`RetrievalLatencyBreakdown \| None`).<br>5) `RAGOutputRecord.route: RouteType \| None = None`.<br>6) `StructuredRAGOutput.missing_facts` và `LLMResponse.missing_facts: list[str] = []`.<br>7) `RouteDecision.action: RouteAction \| None = None`. | Có (`SchemaVersionType` chấp nhận cả `week10_v1.0` và `week10_v1.1`; các trường mới đều optional) |

Ghi chú về `RouteDecision.router_route` (SRS mục 5.6 & 9): hiện giữ `str | None = None` trên `testing` (chưa thu hẹp thành `Literal` để giữ tương thích); toàn bộ thay đổi trên đã đồng bộ vào `schemas/generated/*.schema.json` và `api/openapi.json`.

---

## 2. Cấu hình danh mục `missing_facts` (`configs/missing_facts_taxonomy.yaml`)

| Thuộc tính | Giá trị |
| --- | --- |
| Đường dẫn | `configs/missing_facts_taxonomy.yaml` |
| `taxonomy_version` | `missing_facts_v1.0` |
| SHA-256 (LF normalized) | `4bd94364cf1f6d5e7b7e0a36143d7286583f184eeb2c9487d6f66ee9832bebf8` |
| Số nhóm hợp lệ | 10 nhóm đóng (`ngay_su_kien`, `tinh_trang_dang_ky_ket_hon`, `tuoi_cac_ben`, `quan_he_giua_cac_ben`, `tinh_trang_hon_nhan`, `nguon_goc_thoi_diem_tai_san`, `thoa_thuan_che_do_tai_san`, `dieu_kien_nuoi_con`, `yeu_to_nuoc_ngoai`, `giay_to_xac_nhan_chuyen_mon`) |
| Yêu cầu SRS áp dụng | `FR3.4`, `FR3.6`, `FR4.4`, `NFR4.3`, `NFR5.1` (`D-11` phương án A) |

### Quy ước Active Clarification & Fail-fast

- `generation/prompt_builder.py` nạp cấu hình từ `configs/missing_facts_taxonomy.yaml` qua `load_missing_facts_config()`; nếu thiếu file, lỗi UTF-8/YAML hoặc thiếu một trong các khóa bắt buộc (`taxonomy_version`, `categories`, `generic_clarification_message`, `description`, `clarification_template`), hệ thống ném `MissingFactsConfigError` (`ValueError`, `NFR5.1`) và dừng ngay, không fallback âm thầm.
- Helper `filter_missing_facts()` lọc danh sách `missing_facts` thô từ model: giữ nguyên thứ tự, khử trùng lặp các mã thuộc danh mục đóng, loại bỏ giá trị ngoài danh mục (`FR3.4-AC4`).
- Helper `build_clarification_message()` dựng câu hỏi làm rõ từ `clarification_template` cố định trong YAML; nếu danh sách sau lọc rỗng, trả về `generic_clarification_message` (`FR3.6`).
- Nội dung prompt `v1.2_zero_shot`, `v1.2_controlled_rag` và `v1.3_controlled_rag` không thay đổi từng byte sau khi chuyển danh mục sang YAML.

---

## 3. Bộ fixture bàn giao Sprint 12 (`test/fixtures/sprint12/`)

| Tệp fixture | Model / Schema | `status` / `grounding_status` / `error_code` | Đối tượng nhận bàn giao |
| --- | --- | --- | --- |
| `test/fixtures/sprint12/ask_response_success_v1.1.json` | `AskResponse` (`week10_v1.1`) | `SUCCESS` / `PASS` / `null` | Dev 2, Dev 5 |
| `test/fixtures/sprint12/ask_response_needs_clarification_v1.1.json` | `AskResponse` (`week10_v1.1`) | `NEEDS_CLARIFICATION` / `NEEDS_CLARIFICATION` / `null` | Dev 2, Dev 5 |
| `test/fixtures/sprint12/ask_response_abstain_v1.1.json` | `AskResponse` (`week10_v1.1`) | `ABSTAIN` / `NOT_RUN` / `LOW_CONFIDENCE` | Dev 2, Dev 5 |
| `test/fixtures/sprint12/api_error_llm_unavailable_v1.1.json` | `ApiError` (`week10_v1.1`) | Error payload chuẩn / `LLM_UNAVAILABLE` (HTTP 503) | Dev 2, Dev 5 |
| `test/fixtures/sprint12/ask_response_error_llm_unavailable_v1.1.json` | `AskResponse` (`week10_v1.1`) | `ERROR` / `NOT_RUN` / `LLM_UNAVAILABLE` (`retryable=true`, HTTP 503) | Dev 2, Dev 5 |
