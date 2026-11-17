# D4.2 – Holdout độc lập cho Router

## Đầu vào
- Yêu cầu kiểm thử năm route/action của Router.
- Các nguồn đối chiếu trùng lặp: holdout R4IH v1, Dev270, Negative Set v2, regression data và test Router.
- Bộ câu hỏi ứng viên Week 10.

## Đầu ra
- Dataset: `evaluation/router_holdout/router_holdout_week10_v1.jsonl` (36 câu).
- Metadata, phạm vi và giới hạn review: `evaluation/router_holdout/router_holdout_week10_v1.md`.
- Validator: `scripts/validate_router_holdout.py`.

## Kết quả
- JSONL hợp lệ; 36 ID/câu hỏi duy nhất; đủ 5 route; mapping route/action hợp lệ.
- Validator đối chiếu 5 nguồn và không phát hiện trùng nguyên văn.
- Dev4 đã rà soát nhãn (`reviewer_status=DEV4`); chưa có reviewer độc lập, vì vậy chưa xác nhận độc lập.
- Smoke Router đã chạy trên bộ này: 22/36 khớp, 14 mismatch. Kết quả đã tiêu thụ; không dùng lại để tinh chỉnh. Bộ hiện tại không được gọi là holdout chưa dùng.

## Đánh giá holdout v2 trên Router đã freeze

- Holdout: `evaluation/router_holdout/router_holdout_week10_v2.jsonl`, Dev3 review độc lập; SHA-256 bytes đầu vào: `cc331e418abf54d7266e944a27f186abe9650e23bf5fa771d33ed1e1a7a79dc4` (SHA LF của reviewer: `d2cd4087b8d81048e63074b2fdb31aceadd3d18dedc678b956b801693c815e49`).
- Router: `rule_router_v3`; source SHA-256 `41b25945b8111ca38bbc3fa2aef302e3c924f23eb4d952eaf37e526073dd107d`, khớp freeze record. Corpus SHA-256: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`; schema `week10_v1.1`.
- Lệnh: `python scripts/smoke_rule_router.py --holdout evaluation/router_holdout/router_holdout_week10_v2.jsonl`.
- Run UTC `2026-11-17T10:55:58.967332+00:00`; Git HEAD `ea0aa40c35bdd9b308f6fb2fa983b14193077be2`; working tree `dirty` (Router source bytes vẫn khớp SHA freeze).
- Validator: PASS, 36 records; 10 `LEGAL_HNGD`, 8 `LEGAL_OUT_OF_SCOPE`, 6 `MIXED_LEGAL_SCOPE`, 6 `NON_LEGAL`, 6 `LEGAL_SCOPE_UNCERTAIN`.
- Kết quả: **17/36 exact route/action (47,2%) — FAIL**; **19 mismatch**. Safety gate **FAIL** do một câu pháp lý route sang `NON_LEGAL`/`GENERAL_CHAT`: `W11RH_017`.
- Holdout mismatch IDs: `W11RH_001`, `W11RH_002`, `W11RH_003`, `W11RH_006`, `W11RH_007`, `W11RH_011`, `W11RH_012`, `W11RH_013`, `W11RH_014`, `W11RH_015`, `W11RH_017`, `W11RH_018`, `W11RH_020`, `W11RH_021`, `W11RH_022`, `W11RH_026`, `W11RH_027`, `W11RH_028`, `W11RH_029`.
- Chi tiết sai route/action:

| ID | Expected | Predicted |
| --- | --- | --- |
| W11RH_001, W11RH_002, W11RH_003, W11RH_006, W11RH_007 | `LEGAL_HNGD / LEGAL_RETRIEVAL` | `LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL` |
| W11RH_011, W11RH_012, W11RH_013, W11RH_014, W11RH_015, W11RH_018 | `LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION` | `LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL` |
| W11RH_017 | `LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION` | `NON_LEGAL / GENERAL_CHAT` — safety violation |
| W11RH_020, W11RH_021, W11RH_022 | `MIXED_LEGAL_SCOPE / POLICY_ABSTENTION` | `LEGAL_HNGD / LEGAL_RETRIEVAL` |
| W11RH_026, W11RH_027, W11RH_028, W11RH_029 | `NON_LEGAL / GENERAL_CHAT` | `LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL` |
- Cùng lượt chạy: Official Dev Gold 30/30 PASS; Dev benchmark retrieval 270/270 PASS; Negative Set v2 Router-owned mapping 26/26 PASS; non-legal 6/6 PASS; các gate holdout tổng thể FAIL. Script exit code `1`.
- Đây là lần chạy duy nhất; v2 đã **consumed**. Không sửa `rule_router_v3` dựa trên 19 mismatch rồi tiếp tục gọi v2 là holdout độc lập. Giữ freeze/result; mọi thay đổi hành vi cần version mới và holdout mới nếu cần đánh giá độc lập.

## Phân tích nguyên nhân gốc (đọc code, không tinh chỉnh theo holdout)

Không sửa Router sau lần chạy này. Phân nhóm mismatch cho thấy đây là vấn đề thiết kế/bao phủ rule, không phải lỗi dữ liệu JSONL hay runtime: validator đã pass, Router version/hash khớp freeze record.

| Nhóm | Mismatch | Nguyên nhân trong code |
| --- | --- | --- |
| HNGĐ bị trả `LEGAL_SCOPE_UNCERTAIN` | `W11RH_001`–`003`, `006`–`007` | `_HNGD_TERMS` thiếu các quan hệ/khái niệm như anh chị em, ông bà–cháu, cha mẹ đại diện cho con, giám hộ và danh dự/nhân phẩm thành viên gia đình. Một số câu có tín hiệu pháp lý chung nhưng không đủ tín hiệu HNGĐ để chọn `LEGAL_HNGD`. Xem `agent/router/rule_router.py` phần `_HNGD_TERMS` và `_classify_normalized_query`.
| Pháp lý ngoài phạm vi bị trả `LEGAL_SCOPE_UNCERTAIN` | `W11RH_011`–`015`, `018` | `_OUT_OF_SCOPE_TERMS` chưa bao phủ nhãn hiệu/sở hữu trí tuệ, thị thực/nhập cảnh, làm thêm giờ, cách hỏi nghĩa vụ thuế chung, lỗi mũ bảo hiểm/xử phạt cụ thể và quy chuẩn tiếng ồn/môi trường. Khi không match domain, fallback trả `LEGAL_SCOPE_UNCERTAIN` + `LEGAL_RETRIEVAL`.
| Lỗi an toàn: pháp lý bị coi là chat | `W11RH_017` | Câu có cụm “chào bán”. Sau khi bỏ dấu, thành `chao ban`, trùng chính xác với nhánh `chào bạn` trong `_CLEAR_NONLEGAL_SIGNAL_UNACCENTED`; bộ dò chat thắng dù đây là hỏi chuyển nhượng vốn công ty. Đây là va chạm do bỏ dấu làm mất phân biệt ngữ nghĩa, không chỉ thiếu keyword doanh nghiệp.
| Mixed bị phân loại thành HNGĐ-only | `W11RH_020`–`022` | HNGĐ được nhận diện từ ly hôn/tài sản/con, nhưng tín hiệu phạm vi thứ hai bị bỏ sót: vốn góp/quyền biểu quyết doanh nghiệp; đưa trẻ ra nước ngoài; và thu hồi đất. `_INDEPENDENT_OUTSIDE_TOPIC`/`_OUT_OF_SCOPE_TERMS` không bao phủ các cách diễn đạt này, nên Router không bật `MIXED_LEGAL_SCOPE`.
| Non-legal bị trả `LEGAL_SCOPE_UNCERTAIN` + retrieval | `W11RH_026`–`029` | `_CLEAR_NONLEGAL_SIGNAL` không có các yêu cầu như viết hàm palindrome, lên lịch tham quan, giải thích hiện tượng tự nhiên và chẩn đoán vấn đề chăm sóc cây. Do câu không match mẫu chat hiện có, fallback mặc định hướng sang legal retrieval.

### Kết luận kỹ thuật

Ba điểm chính cần xử lý nếu mở một phiên bản mới: (1) bỏ kiểu fallback khiến mọi câu không nhận diện thành `LEGAL_SCOPE_UNCERTAIN`/retrieval hoặc phân biệt rõ unknown với non-legal; (2) mô hình hóa tín hiệu domain/legal–HNGĐ–outside theo khái niệm thay vì chỉ thêm từ khóa rời rạc; (3) không dùng phép bỏ dấu để match các cụm có thể nhập nhằng như `chào bạn`/`chào bán`, và thêm test đối kháng cho normalization. Các ca HNGĐ giao thoa dân sự (đặc biệt `W11RH_003`, `W11RH_007`) cũng cần policy precedence rõ trước khi viết test mới.

Đây là phân tích giải thích kết quả đã quan sát, không phải căn cứ để thay nhãn hoặc sửa rule dựa trực tiếp trên holdout v2. V2 vẫn được giữ nguyên làm bằng chứng đã tiêu thụ; mọi sửa đổi tiếp theo phải dùng Dev/regression và muốn có điểm độc lập thì cần holdout mới.

## Công nghệ đã dùng
JSONL, Python validation script, Unicode/text normalization, exact duplicate checks, route/action contract.
