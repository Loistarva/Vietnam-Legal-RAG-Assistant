# Báo cáo kiểm thử hồi quy Prompt & xây dựng Prompt `v1.3` (D3.3)

**Ngày thực hiện:** 23/11/2026  
**Nhánh:** `feature/week11-dev3-contracts-gateway`  
**Module:** `generation/prompt_builder.py`, `generation/prompts/legal_rag_prompt_v1_3.md`  
**Kiểm thử:** `test/generation/test_prompt_builder.py`  
**Mã SRS phủ:** `FR4.2`, `FR4.3`, `FR4.4`, `FR4.5`, `FR4.6`

---

## 1. Bảo toàn bất biến Prompt Official `v1.2`

- `OFFICIAL_PROMPT_A_VERSION = "v1.2_zero_shot"` và `OFFICIAL_PROMPT_B_VERSION = "v1.2_controlled_rag"` tiếp tục là mặc định khi không chỉ định phiên bản khác, chưa bật `v1.3` làm official cho tới khi Tech Lead chốt dùng cho Test 30.
- Mã băm SHA-256 trên fixture chuẩn được kiểm tra bất biến trước và sau khi nâng cấp:
  - `v1.2_zero_shot`: `c5c45e90894e9d58984f4c2b71a2fdaad75cf090a0323be1cde16bf2f918893b`
  - `v1.2_controlled_rag`: `5a19fe70f42efbb101945888d1f4cec8548f78a9a8b704bd31b68acfb4b75940`
  - `generation/prompts/legal_rag_prompt_v1_0.md` (chuẩn hóa LF): `4e8e9bae20447b5b01caebeb7be0dbe994f137b52f4f4f5620b4fa6f83997669`

---

## 2. Thiết kế Prompt phiên bản mới `v1.3_controlled_rag`

- **Template vật lý:** `generation/prompts/legal_rag_prompt_v1_3.md` (SHA-256 chuẩn hóa LF: `fca5e25399b63c8734e7d5a5be8a30d4dd18a80c9240679bbc776c82e881a211`).
- **Nhãn hiệu lực tại `as_of_date` (`FR4.3`):** `format_effectivity_at_as_of_date(item, as_of_date)` tính rõ trạng thái nửa mở `[effective_from, effective_to)` tại `as_of_date` (`Còn hiệu lực tại ...`, `Chưa có hiệu lực tại ...`, `Hết hiệu lực tại ...`, hoặc `Chưa đủ mốc ngày hiệu lực` nếu thiếu cả hai mốc) và kèm `point_ref` khi có.
- **Danh mục đóng `missing_facts` (`FR4.4`, `D-11`):** Khai báo trong `MISSING_FACTS_TAXONOMY` (10 mã chuẩn hóa: `ngay_su_kien`, `tinh_trang_dang_ky_ket_hon`, `tuoi_cac_ben`, `quan_he_giua_cac_ben`, `tinh_trang_hon_nhan`, `nguon_goc_thoi_diem_tai_san`, `thoa_thuan_che_do_tai_san`, `dieu_kien_nuoi_con`, `yeu_to_nuoc_ngoai`, `giay_to_xac_nhan_chuyen_mon`), kèm `validate_missing_facts()` chặn mọi nhãn tự do ngoài danh mục.

---

## 3. Khóa toàn vẹn Template (`FR4.6-AC2`)

- `verify_prompt_template_integrity()` kiểm tra SHA-256 của cả file template (`legal_rag_prompt_v1_0.md`, `legal_rag_prompt_v1_3.md`) lẫn output chuẩn của `v1.2`.
- Test `test_prompt_template_modification_without_version_bump_fails_integrity_check` xác nhận mọi chỉnh sửa lên template mà không tăng phiên bản/hash đều làm test thất bại với thông báo lỗi rõ ràng.
