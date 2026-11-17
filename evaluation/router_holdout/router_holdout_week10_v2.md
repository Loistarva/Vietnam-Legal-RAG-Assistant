# Holdout Router Week 10 v2 — đã hoàn tất review độc lập (Dev3)

## Trạng thái

- Candidate holdout gồm 36 câu mới; **chưa chạy Router và chưa dùng để tinh chỉnh**.
- Reviewer độc lập (**Dev3**) đã hoàn tất rà soát tất cả 36/36 bản ghi vào ngày **2026-11-17** và quyết định **giữ nguyên bộ câu hỏi, `expected_route`, `expected_action` và `reason`**, chuyển `reviewer_status` từ `PENDING_INDEPENDENT_REVIEW` sang `INDEPENDENT_REVIEW_COMPLETE`.
- Week 10 v1 đã được chạy (22/36 khớp; 14 mismatch), nên chỉ giữ làm regression; không dùng lại để báo cáo kết quả holdout độc lập.
- Chỉ chạy v2 đúng 1 lần sau khi Router đã được cập nhật đạt toàn bộ Freeze Gate trên Regression/Dev/Negative Set v2 và freeze theo SHA cụ thể.

## Hồ sơ review độc lập (Dev3 — 2026-11-17)

- **Reviewer identity:** `Dev3` (độc lập, không phải tác giả soạn bộ câu hỏi).
- **Ngày review:** `2026-11-17 (Asia/Saigon)`.
- **SHA-256 JSONL trước review (bản `PENDING_INDEPENDENT_REVIEW`):** `cd3568b554b9be7c7a602d8a3f903f47587b3f108ff4098271e45df1289b65ac`.
- **SHA-256 JSONL sau review (bản `INDEPENDENT_REVIEW_COMPLETE`, LF):** `d2cd4087b8d81048e63074b2fdb31aceadd3d18dedc678b956b801693c815e49`.
- **Tổng hợp kết quả:** `36/36` câu đã kiểm tra đối chiếu phạm vi corpus 28 văn bản và so khớp 6 nguồn đối chiếu:
  - **Đồng ý hoàn toàn:** `30/36` câu (`W11RH_001`–`003`, `005`–`006`, `008`–`015`, `017`–`022`, `024`–`033`, `035`). Ghi nhận `W11RH_003` giao thoa nhẹ dân sự ở đại diện cha mẹ–con (Điều 73 Luật HNGĐ 2014) và `W11RH_008` hỏi ngược chiều nghĩa vụ so với `R4IH_005` (Điều 110 vs Điều 111 Luật HNGĐ 2014).
  - **Ghi chú chấp nhận giữ nguyên đối với 6 điểm ranh giới/overlap:** `W11RH_004` (chủ đề gần `dev_270::HN_009`), `W11RH_007` (lưu ý ranh giới thuật ngữ giám hộ BLDS vs đại diện theo pháp luật HNGĐ), `W11RH_016` (gần kịch bản bảo hành `R4IH_018`), `W11RH_023` (gần chủ đề ly hôn + thuế chuyển nhượng `W10RH_020`), `W11RH_034` (gần `W10RH_035`), `W11RH_036` (khung gần `W10RH_034`, giữ để kiểm tra bẫy từ khóa gia đình). Reviewer quyết định **giữ nguyên toàn bộ 36 câu & nhãn** để chốt mốc đánh giá holdout.

## Phạm vi và phân bố dự kiến

| Route | Số câu |
|---|---:|
| `LEGAL_HNGD` | 10 |
| `LEGAL_OUT_OF_SCOPE` | 8 |
| `MIXED_LEGAL_SCOPE` | 6 |
| `NON_LEGAL` | 6 |
| `LEGAL_SCOPE_UNCERTAIN` | 6 |

Các câu thay thế tránh chủ đề bị nêu là gần/trùng với holdout cũ. Reviewer cần kiểm tra semantic overlap, phạm vi luật áp dụng, lý do route/action và đặc biệt các trường hợp ranh giới giữa HNGĐ với thừa kế, hình sự, nghĩa vụ cấp dưỡng, quyền cha mẹ và đại diện/giám hộ.

## Kiểm tra trước review

Đã chạy kiểm tra cấu trúc và exact-text overlap:

```powershell
.\.venv\Scripts\python.exe scripts/validate_router_holdout.py --holdout evaluation/router_holdout/router_holdout_week10_v2.jsonl
```

Validator kiểm tra JSONL, trường bắt buộc, ID/query duy nhất, mapping route/action và exact-text overlap với sáu nguồn trong script: regression holdout, R4IH v1, Week 10 v1, Dev benchmark, Negative Set v2 và test Router. Kết quả pass chỉ chứng minh các kiểm tra tự động này; không chứng minh nhãn pháp lý đúng hay semantic independence.

**Không chạy** `scripts/smoke_rule_router.py` trên v2 trước khi hoàn tất review độc lập và freeze Router.

## Provenance

- Tạo ngày: 2026-11-17 (Asia/Saigon).
- SHA-256 JSONL trước review (LF): `cd3568b554b9be7c7a602d8a3f903f47587b3f108ff4098271e45df1289b65ac`.
- SHA-256 JSONL hiện tại (`INDEPENDENT_REVIEW_COMPLETE`, LF): `d2cd4087b8d81048e63074b2fdb31aceadd3d18dedc678b956b801693c815e49`.
- Nếu sửa JSONL, phải tính lại SHA và cập nhật metadata/review record.
