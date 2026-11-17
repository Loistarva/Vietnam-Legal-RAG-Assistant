# Holdout Router Week 10 v2 — bản nháp chờ review độc lập

## Trạng thái

- Candidate holdout gồm 36 câu mới; **chưa chạy Router và chưa dùng để tinh chỉnh**.
- Cả 36 bản ghi đang có `reviewer_status=PENDING_INDEPENDENT_REVIEW`. Nhãn và lý do là đề xuất của Dev4, chưa được reviewer độc lập xác nhận.
- Week 10 v1 đã được chạy (22/36 khớp; 14 mismatch), nên chỉ giữ làm regression; không dùng lại để báo cáo kết quả holdout độc lập.
- Chỉ chạy v2 sau khi reviewer độc lập xác nhận nhãn/reason, policy được Tech Lead chốt và Router đã freeze theo SHA cụ thể.

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
- SHA-256 JSONL: `cd3568b554b9be7c7a602d8a3f903f47587b3f108ff4098271e45df1289b65ac`.
- Nếu sửa JSONL, phải tính lại SHA và cập nhật metadata/review record.
