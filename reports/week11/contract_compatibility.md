# Báo cáo nâng cấp Canonical Contract `week10_v1.0` → `week10_v1.1` (D3.1 — Bản thống nhất PR #56 + PR #60)

**Ngày thực hiện:** 23/11/2026
**Nhánh:** `feature/week11-dev3-contracts-gateway` (nền `origin/testing` tại `03a4989`, đã gộp phần contract của Dev 4 từ PR #56 `fe279f1`)
**Nguồn sự thật:** `schemas/models.py`
**Đặc tả tham chiếu:** `docs/SRS.md` (SRS 2.1.2, mục 5.2, 5.3, 5.4, 5.6), `docs/contracts.md`

---

## 1. Các thay đổi đã phê duyệt đưa vào bản `week10_v1.1` thống nhất

Toàn bộ các thay đổi dưới đây đều giữ tương thích ngược trong dòng `week10_v1.x` (SRS 5.6): chỉ bổ sung giá trị enum/literal hoặc trường tùy chọn có giá trị mặc định an toàn, giữ `SchemaVersionType = Literal["week10_v1.0", "week10_v1.1"]`, và đặt `SCHEMA_VERSION = "week10_v1.1"`.

### 1.1. Nhóm thay đổi lõi của Dev 3 (5 hạng mục)

| Thành phần | Thay đổi từ `week10_v1.0` → `week10_v1.1` | Mã SRS | Ghi chú |
| --- | --- | --- | --- |
| `SchemaVersionType`, `SCHEMA_VERSION` | Chấp nhận `{"week10_v1.0", "week10_v1.1"}`, mặc định mới `"week10_v1.1"` | SRS 5.2, 5.6 | Bản ghi cũ gắn `"week10_v1.0"` vẫn parse hợp lệ |
| `ErrorCode` | Thêm `"LLM_UNAVAILABLE"` (HTTP 503, `retryable=True`) | `FR6.4`, D-02 | Dùng khi không kết nối được Ollama/provider sau retry |
| `EventStage` | Thêm `"confidence"` | `FR9.9`, `FR3.1` | Tách stage đánh giá ngưỡng tin cậy khỏi `"rerank"` |
| `EvidenceItem` | Thêm `point_ref: str | None = None` (chặn chuỗi chỉ khoảng trắng; đồng bộ vào `ContextPayload.source_map`) | `FR4.7`, `IR1.4` | Giữ `None` khi chunk không thuộc cấp Điểm |
| `StructuredRAGOutput`, `LLMResponse` | Thêm `missing_facts: list[str] = Field(default_factory=list)` | `FR4.4`, `FR3.4` | Mặc định `[]` nên tương thích hoàn toàn với prompt `v1.2` |
| `RouteDecision` | Thêm `router_route: str | None = None`; khóa `action` sang `RouteAction = Literal["LEGAL_RETRIEVAL", "FAST_PATH", "POLICY_ABSTENTION", "GENERAL_CHAT"] \| None` | `FR1.3`, SRS 5.3.3 | Khớp bảng SRS 5.3.3; `schemas/examples/route_decision_out_of_scope.json` đã đổi `"ABSTAIN_OUT_OF_SCOPE"` → `"POLICY_ABSTENTION"` |

### 1.2. Nhóm thay đổi gộp từ PR #56 của Dev 4 (3 hạng mục)

| Thành phần | Thay đổi hợp nhất vào `week10_v1.1` | Mã SRS | Ghi chú |
| --- | --- | --- | --- |
| `MetadataFilters`, `RetrievalBundle.metadata_filters` | Thêm `MetadataFilters` (`document_type`, `document_number`, `document_id`, `article_id`, `clause_id`, `validity_status` đều optional, chặn chuỗi rỗng/extra) và `RetrievalBundle.metadata_filters: MetadataFilters \| None = None` | `FR2.11`, `FR2.2` | Khớp `retrieval/adapter.py` trên PR #56; bản ghi `v1.0` thiếu trường vẫn hợp lệ |
| `RetrievalLatencyBreakdown`, `RetrievalBundle.latency_breakdown` | Thêm `RetrievalLatencyBreakdown` (`bm25_ms`, `dense_ms`, `rrf_ms`, `reranking_ms`, `parent_context_ms`, `total_retrieval_ms`, mỗi field `>= 0.0` hoặc `None`) và `RetrievalBundle.latency_breakdown` | `FR9.4`, `FR2.11` | Khớp `reranking/pipeline.py` và `retrieval/adapter.py` trên PR #56 |
| `RAGOutputRecord.route` | Thêm `route: RouteType \| None = None` trên `RAGOutputRecord` | `FR1.9`, `FR9.8` | Khớp `scripts/enrich_batch_routes.py`; bản ghi `v1.0` thiếu `route` vẫn hợp lệ |

---

## 2. Tái sinh JSON Schemas & Examples

- Đã chạy `python -m schemas.models` để tái sinh toàn bộ 4 schema gốc (`schemas/*.schema.json`) và 10 schema chuẩn trong `schemas/generated/*.schema.json` theo JSON Schema Draft 2020-12 với `"schema_version": "week10_v1.1"`.
- Đã cập nhật 8 tệp mẫu trong `schemas/examples/*.json` lên `"week10_v1.1"`, gồm `point_ref` trong `ask_response_ok.json`, `router_route` / `"POLICY_ABSTENTION"` trong `route_decision_out_of_scope.json`, và `metadata_filters` / `latency_breakdown` trong `retrieval_bundle_valid.json`.

---

## 3. Kiểm chứng tương thích ngược & rà soát tích hợp

- **Test tương thích ngược `week10_v1.0`:** Test `test_week10_v1_0_backward_compatibility` và `test_retrieval_bundle_filters_latency_and_rag_record_route` trong `test/schemas/test_contracts.py` xác nhận toàn bộ các payload `week10_v1.0` (`AskRequest`, `RouteDecision`, `RetrievalBundle` không có `metadata_filters`/`latency_breakdown`, `AskResponse`, `LLMResponse`, `LogEvent`, `RAGOutputRecord` không có `route`) vẫn validate hợp lệ.
- **Lưu ý tích hợp với PR #56 (Dev 4) và PR #55 / `feature/sprint11-dev5` (Dev 5):**
  - Sau khi merge PR #60 của Dev 3 vào `testing`, PR #56 chỉ cần đồng bộ lại `schemas/` theo `testing` (hoặc loại bỏ phần sửa `schemas/` khỏi PR #56) để không xảy ra xung đột trên `schemas/models.py` và `test/schemas/test_contracts.py`.
  - Dev 5 chạy `python -m api.export_openapi` để cập nhật `api/openapi.json`, điều chỉnh 2 test truyền `action="SOMETHING_NEW"` vào `RouteDecision(...)` trong `test/orchestration/test_ask_service.py`, và bật ánh xạ `LLM_UNAVAILABLE` (503) + `stage="confidence"`.

---

## 4. Hạng mục để lại cho GĐ3 (SRS 5.6)

- `AskResponse.session_id`, `LogEvent.session_id`, stage `session` (`FR7.1`, `FR7.2` — Dự kiến).
- `ErrorCode.RATE_LIMITED` (HTTP 429, `NFR3.2` — Dự kiến).
