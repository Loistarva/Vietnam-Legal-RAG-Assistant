# Báo cáo nâng cấp Canonical Contract `week10_v1.0` → `week10_v1.1` (D3.1)

**Ngày thực hiện:** 23/11/2026  
**Nhánh:** `feature/week11-dev3-contracts-gateway` (nền `origin/testing` tại `03a4989`)  
**Nguồn sự thật:** `schemas/models.py`  
**Đặc tả tham chiếu:** `docs/SRS.md` (SRS 2.1.2, mục 5.2, 5.3, 5.4, 5.6)

---

## 1. Các thay đổi đã phê duyệt đưa vào `week10_v1.1`

Tất cả thay đổi dưới đây đều tuân thủ nguyên tắc mở rộng tương thích ngược trong cùng dòng `week10_v1.x` (SRS 5.6): chỉ bổ sung giá trị enum/literal hoặc trường tùy chọn có giá trị mặc định an toàn, giữ `SchemaVersionType = Literal["week10_v1.0", "week10_v1.1"]`, và đặt `SCHEMA_VERSION = "week10_v1.1"`.

| Thành phần | Thay đổi từ `week10_v1.0` → `week10_v1.1` | Mã SRS | Ghi chú |
| --- | --- | --- | --- |
| `SchemaVersionType`, `SCHEMA_VERSION` | Chấp nhận `{"week10_v1.0", "week10_v1.1"}`, mặc định mới `"week10_v1.1"` | SRS 5.2, 5.6 | Bản ghi cũ gắn `"week10_v1.0"` vẫn parse hợp lệ |
| `ErrorCode` | Thêm `"LLM_UNAVAILABLE"` (HTTP 503, `retryable=True`) | `FR6.4`, D-02 | Dùng khi không kết nối được Ollama/provider sau retry |
| `EventStage` | Thêm `"confidence"` | `FR9.9`, `FR3.1` | Tách stage đánh giá ngưỡng tin cậy khỏi `"rerank"` |
| `EvidenceItem` | Thêm `point_ref: str | None = None` (chặn chuỗi chỉ khoảng trắng; đồng bộ vào `ContextPayload.source_map`) | `FR4.7`, `IR1.4` | Giữ `None` khi chunk không thuộc cấp Điểm |
| `StructuredRAGOutput`, `LLMResponse` | Thêm `missing_facts: list[str] = Field(default_factory=list)` | `FR4.4`, `FR3.4` | Mặc định `[]` nên tương thích hoàn toàn với prompt `v1.2` |
| `RouteDecision` | Thêm `router_route: str | None = None`; khóa `action` sang `RouteAction = Literal["LEGAL_RETRIEVAL", "FAST_PATH", "POLICY_ABSTENTION", "GENERAL_CHAT"] \| None` | `FR1.3`, SRS 5.3.3 | Khớp bảng SRS 5.3.3; `schemas/examples/route_decision_out_of_scope.json` đã đổi `"ABSTAIN_OUT_OF_SCOPE"` → `"POLICY_ABSTENTION"` |

---

## 2. Tái sinh JSON Schemas & Examples

- Đã chạy `python -m schemas.models` để tái sinh toàn bộ 4 schema gốc (`schemas/*.schema.json`) và 10 schema chuẩn trong `schemas/generated/*.schema.json` theo JSON Schema Draft 2020-12 với `"schema_version": "week10_v1.1"`.
- Đã cập nhật 8 tệp mẫu trong `schemas/examples/*.json` lên `"week10_v1.1"` (minh họa `point_ref` trong `ask_response_ok.json` và `router_route` / `POLICY_ABSTENTION` trong `route_decision_out_of_scope.json`).

---

## 3. Kiểm chứng tương thích ngược & rà soát repo

- **Rà soát `RouteDecision.action` trên toàn repo (`git grep`):** Không có bản ghi lưu trữ hay kết quả đánh giá nào trên `testing` sử dụng giá trị `action` ngoài 4 giá trị chuẩn. Chỉ có ví dụ `schemas/examples/route_decision_out_of_scope.json` dùng nhãn cũ `"ABSTAIN_OUT_OF_SCOPE"` và đã được cập nhật. *(Lưu ý khi ghép với nhánh API `feature/week10-fastapi-integration`: `test/orchestration/test_ask_service.py` có test truyền `"SOMETHING_NEW"` vào `RouteDecision` để thử `next_action`; sau khi khóa `RouteAction`, trường hợp đó sẽ bị Pydantic chặn ngay tại bước tạo `RouteDecision`.)*
- **Test tương thích ngược `week10_v1.0`:** Test `test_week10_v1_0_backward_compatibility` trong `test/schemas/test_contracts.py` xác nhận toàn bộ các payload `week10_v1.0` (`AskRequest`, `RouteDecision`, `RetrievalBundle`, `AskResponse`, `LLMResponse`, `LogEvent`) không có các trường mới vẫn validate thành công.

---

## 4. Danh sách hạng mục CHƯA đưa vào code (đang chờ Tech Lead duyệt ở SRS 5.6)

Theo quy tắc SRS 12.1, Dev 3 **không tự ý thêm** các mục sau vào `schemas/models.py` khi chưa có phê duyệt chính thức từ Tech Lead:

1. `RetrievalBundle.metadata_filters` và `RetrievalBundle.latency_breakdown` (`FR2.11`, `FR9.4` — trạng thái SRS 5.6: *Owner Contract đồng ý 17/11/2026; chờ Tech Lead duyệt và owner contract chốt bản thống nhất*).
2. `RAGOutputRecord.route: RouteType | None = None` (`FR1.9`, `FR9.8` — trạng thái SRS 5.6: *Owner Contract đồng ý 17/11/2026; chờ Tech Lead duyệt và owner contract chốt bản thống nhất*).
3. `corpus_version` / `retrieval_config_hash` trên các model API nếu có đề xuất bổ sung thêm vào contract (chưa nằm trong phần đã duyệt của SRS 5.6).
4. Các hạng mục dự kiến cho GĐ3 (`AskResponse.session_id`, `LogEvent.session_id`, stage `session`, `ErrorCode.RATE_LIMITED`).
