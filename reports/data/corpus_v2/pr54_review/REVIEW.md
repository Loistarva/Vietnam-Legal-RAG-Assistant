# Đối chiếu PR #54 với testing mới nhất

Ngày kiểm tra: 17/11/2026. PR: https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/54

Đã fetch origin và fast-forward nhánh làm việc `feat/corpus-v2` từ `c1e9f12` lên `01fe249` (PR #49 đã merge). Dữ liệu và các sửa đổi test chưa commit được giữ nguyên. PR #54 tại `417e3f3` vẫn là nhánh riêng; chưa merge tài liệu SRS vào nhánh data. Các thay đổi runtime/schema vừa nhận là commit upstream, không phải chỉnh sửa mới của phần data.

## Kết quả đối chiếu nhận xét

| Nhận xét | Kết luận kiểm chứng | Phần cần xử lý |
| --- | --- | --- |
| SRS §5.3.3 / D-01 dùng 5 route, API dùng 4 | Đúng. `schemas/models.py` có RouteType = LEGAL_IN_SCOPE, NON_LEGAL, LEGAL_OUT_OF_SCOPE, MIXED_REVIEW; có hàm ánh xạ route nội bộ. `LEGAL_HNGD` gửi trực tiếp vào AskResponse bị từ chối. | Tác giả SRS và người phụ trách contract chốt ranh giới route nội bộ/API. |
| AskResponse lệch tên trường | Đúng. SRS dùng message/reason_code/error.code; code dùng abstention_message/abstention_reason/error_code và ErrorDetail(message, retryable). | Đồng bộ tài liệu hoặc thực hiện PR contract có kiểm soát tương thích. |
| Thiếu session_id, versions, cache; citation và timings khác | Đúng. Các trường thêm theo SRS bị `extra_forbidden`; MappedCitation và AskTimings khác danh sách trong SRS. | Không thể sửa bằng metadata PDF. Không tự bổ sung field vào schema trong nhánh data. |
| request_id được dùng làm query_id | SRS §5.3.1 và FR7.1-AC2 quy định như vậy; docs/contracts.md §4.1 phân biệt mã client và mã xuyên pipeline, còn AskRequest nhận cả hai. | Cần một quyết định thống nhất contract/ID trước khi nối API và log. |
| Mã lỗi và HTTP lệch | Đúng. ErrorCode thiếu RATE_LIMITED, LLM_UNAVAILABLE, MODEL_ABSTAINED, MODEL_NEEDS_CLARIFICATION. Nhánh API `29d3b70` công bố 403 khi key sai, trong khi SRS chỉ ghi 401. API chưa thuộc testing tại thời điểm đối chiếu. | Người phụ trách API/contract và tác giả SRS. Một số mã thuộc GĐ3, cần ghi rõ phiên bản/phạm vi triển khai. |
| LogEvent 11 stage / session_id | Đúng. Code có 9 stage, chưa có session/confidence và không có session_id. | Đồng bộ contract log với SRS. |
| Traceability cũ | Đúng. Ma trận tại PR #54 lấy mốc c1e9f12, còn testing đã lên 01fe249; FR6.4 vẫn ghi PR #49 chưa merge. | Cập nhật ma trận theo từng tiêu chí. Timeout đã có không đồng nghĩa toàn bộ FR6.4 (503, cảnh báo, log, SSE) đã hoàn tất. |
| Schema path | Đúng. Schema chuẩn mới ở schemas/generated/*.schema.json; vẫn có schema legacy ở schemas/*.schema.json. | Làm rõ §5.2 để tránh dùng nhầm schema legacy. |
| Bản week10_v1.1 | Chưa xác nhận được. Code và schema hiện tại ghi week10_v1.0. | Không ghi v1.1 là phiên bản đã tồn tại nếu chưa có commit tương ứng. |

`comparison.json` lưu field/enum thực tế và 6 phép thử payload SRS bị model hiện tại từ chối. Đây là bằng chứng lệch yêu cầu/contract, không phải lỗi dữ liệu corpus.

## Đối chiếu phần data của người dùng

- FR8.1: 57 văn bản có nguồn; các trường metadata bắt buộc đã kiểm tra không rỗng.
- FR8.5: 2.051 parent, 4.716 child; không có parent > 1.500 ký tự, child > 256 từ đã tách, child thiếu parent hoặc clause_id.
- FR8.7: chưa thể kết luận hoàn tất rà soát pháp lý. Có 2.800 chunk `requires_review`, 1.753 `document_level_only`, 136 `repealed`, 27 `amended`. Giá trị đúng enum/schema không chứng minh các khoảng hiệu lực đã được đối chiếu đầy đủ.
- FR8.8–8.9: đã có corpus sinh ra cục bộ; chưa kiểm tra/re-index Elasticsearch và Qdrant trên dịch vụ thật, chưa chạy lại A/B trên corpus mới. Test qua không thay thế các bước này.
- Bộ negative lịch sử: NEG_DEV_013–018 cần duyệt lại vì nguồn đã có. Nhánh trial13 mới nhất `d9503c8` đã có bộ negative theo corpus41, nhưng không thể áp nguyên cho corpus57: trial41 còn chứa 3 văn bản bị loại và ND17 đang hoãn. Không merge trộn corpus41 vào nhánh hiện tại.
- Các số 28 văn bản / 2.322 chunk trong PR #54 là snapshot baseline, không phải số liệu của nhánh corpus57. Cần ghi mốc corpus khi cập nhật ma trận.

## Giới hạn và hành động

Giữ nguyên parser/cleaner/chunker, runtime contract, manifest Test và kết quả A/B lịch sử. Chưa đăng nhận xét lên GitHub. Các khác biệt thuộc contract/API/SRS cần bàn giao cho người phụ trách tương ứng; phần data vẫn cần hoàn tất kiểm duyệt hiệu lực trước khi công bố sử dụng corpus mới.

Kết quả regression trên testing mới nhất được lưu tại `../pr54_latest_suite.log` và `../pr54_latest_suite.xml`.

K?t qu? cu?i: **1844 passed, 1 skipped, 206 subtests passed in 164.94s (0:02:44)**. Kh?ng c? l?i regression; ?i?u n?y kh?ng ch?ng minh SRS v? contract ?? ??ng b?.
