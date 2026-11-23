# Hợp đồng kiểm tra cấu hình Runtime & Model-Run Manifest (D3.4)

**Ngày thực hiện:** 23/11/2026  
**Nhánh:** `feature/week11-dev3-contracts-gateway`  
**Module triển khai:** `model_gateway/run_metadata.py`  
**Kiểm thử:** `test/model_gateway/test_run_metadata.py`  
**Mã SRS phủ:** `NFR4.1`, `NFR4.2`, `NFR4.3`, `NFR2.3`, `FR6.6`, `FR6.7`

---

## 1. Mục đích

Cung cấp bộ kiểm tra độc lập cho Dev 5 (`scripts/run_rag_batch.py`, API/evaluation runners) trước và sau mỗi lượt chạy model để bảo đảm tái lập kết quả và kiểm toán phần cứng theo `NFR4.1`–`NFR4.3` và `NFR2.3`, không tạo canonical schema song song với `schemas/models.py`.

---

## 2. Nhóm trường bắt buộc trong `run_manifest.json`

| Nhóm | Trường bắt buộc | Quy tắc kiểm tra |
| --- | --- | --- |
| Git & checkout | `git_branch`, `git_sha`, `working_tree_clean` | `git_sha` khớp hex SHA 7–40 ký tự; `working_tree_clean` là `bool` |
| Dữ liệu & corpus | `benchmark_sha256`, `dataset_ids_hash`, `corpus_hash` | Chuỗi SHA-256 64 hex (hoặc tiền tố `sha256:` + 64 hex) |
| Hash cấu hình (`NFR4.3`) | `config_hashes.{retrieval, rerank, model, threshold}` | Cả 4 khóa phải có SHA-256 hợp lệ |
| Precomputed | `precomputed_retrieval`, `precomputed_artifact` | Nếu `precomputed_retrieval == True`, `precomputed_artifact` phải có `path`/`status` và `sha256` |
| Runtime & model (`FR6.6`) | `runtime.{model, model_digest, ollama_version, prompt_version, num_ctx, num_predict, temperature, repeat_penalty, cache/cache_enabled, fallback/fallback_locked}` | Đủ provenance thực tế, không tự bịa số liệu thiếu |
| Phần cứng (`NFR2.3`) | `hardware.{os, cpu, gpu, vram}` | Đầy đủ chuỗi mô tả máy chạy; không GPU ghi `"none"` thay vì bỏ trống |
| Thời gian | `started_at`, `finished_at` | ISO-8601 có múi giờ UTC (`Z` hoặc `+00:00`), `finished_at >= started_at` |

---

## 3. Ràng buộc riêng cho lượt chạy Official (`official=True`, `NFR4.1-AC1`)

Khi gọi `validate_run_manifest(manifest, official=True)` hoặc `assert_valid_run_manifest(manifest, official=True)`:

- `working_tree_clean` bắt buộc `True`.
- `runtime.temperature` bắt buộc bằng `0.0`.
- Cache tắt (`cache_enabled == False` hoặc `cache == "OFF"`).
- Fallback khóa (`fallback_locked == True` hoặc `fallback == "LOCKED"`).

Khi vi phạm bất kỳ trường nào, validator trả về danh sách thông báo lỗi nêu rõ tên trường (hoặc ném `ManifestValidationError`).

---

## 4. Khắc phục hậu review Sprint 11 (Post-review fixes)

- **[P2] Chặn `NaN` / `Infinity` / `-Infinity`:** Dùng `_is_finite_number` (`math.isfinite`) kiểm tra toàn bộ tham số số thực ở cả `validate_runtime_config` và `validate_run_manifest` (`runtime.temperature`, `runtime.repeat_penalty`, `runtime.timeout_seconds`) cho cả `official=True` và `official=False`.
- **[P2] Nhất quán hash model config vs runtime hiệu lực (`NFR4.1`–`NFR4.3`):** `build_model_run_manifest` và `validate_run_manifest` đối chiếu các tham số sinh hiệu lực với cấu hình gốc được băm tại `config_hashes.model`. Khi `official=True`, mọi override/lệch trường bị từ chối với lỗi `model_config_hash_mismatch` chỉ rõ trường lệch; khi `official=False`, manifest ghi nhận tường minh `base_model_config`, `base_model_config_hash`, `runtime_overrides` và `effective_model_config_hash` (từ chối nếu ghi đè ngầm thiếu provenance).
- **[P2] Phát hiện mâu thuẫn biểu diễn cache / fallback:** `_read_cache_disabled` và `_read_fallback_locked` kiểm tra chéo toàn bộ biểu diễn hiện diện (`cache_enabled` vs `cache`, `fallback_locked` vs `fallback` / `fallback_enabled`) trong cả `validate_runtime_config` và `validate_run_manifest`, từ chối ngay khi mâu thuẫn ở cả `official=True` và `official=False`.
- **[P2] Xử lý an toàn file YAML lỗi cú pháp / lỗi đọc:** `_load_yaml_mapping` bắt `OSError`, `UnicodeDecodeError`, `yaml.YAMLError` và trả về lỗi có cấu trúc (`YAML_PARSE_ERROR` kèm `file_path` và `line`/`column` nếu có, hoặc `CONFIG_READ_ERROR` kèm `file_path`) thay vì ném exception thô. Đã bổ sung đầy đủ unit test trong `test/model_gateway/test_run_metadata.py`.
- **[P2] Chống `OverflowError`, bắt buộc nguồn đối chiếu `official=True` & tái tính `effective_model_config_hash`:**
  - `_safe_finite_float` và `QwenGatewayConfig.validate_strict_float` / `ollama_durations_ms` bắt `OverflowError` đối với số nguyên cực lớn (`10**1000`, `-10**1000`), trả về lỗi validation có cấu trúc trong cả `validate_runtime_config` lẫn `validate_run_manifest`.
  - Khi `official=True`, `validate_run_manifest` bắt buộc phải có ít nhất một nguồn cấu hình gốc (`model_config_path` hợp lệ hoặc snapshot `base_model_config` đầy đủ 12 khóa bắt buộc); snapshot thiếu khóa (như `{"num_ctx": 4096}`) bị chặn bằng `incomplete_base_model_config` trước khi qua Pydantic (không cho tự điền giá trị mặc định). Khi đọc độc lập không truyền `model_config_path` ở `official=True`, manifest bắt buộc có đủ `base_model_config`, `base_model_config_hash` và `effective_model_config_hash`.
  - Khi có override (`official=False` hoặc có khai báo `runtime_overrides` / `effective_model_config_hash`), validator kiểm tra đầy đủ `base_model_config_hash`, đối chiếu hai chiều từng cặp `{"config": ..., "runtime": ...}` trong `runtime_overrides`, và tái dựng cấu hình hiệu lực để kiểm chứng `effective_model_config_hash` (`effective_model_config_hash_mismatch`).
  - Thống nhất một bảng ánh xạ chuẩn duy nhất `CONFIG_TO_RUNTIME_FIELD_MAP` / `RUNTIME_TO_CONFIG_FIELD_MAP` giữa `build_model_run_manifest` và validator (`_compare_runtime_with_model_config`, `_build_effective_model_config`), phủ toàn bộ 12 trường cấu hình của `QwenGatewayConfig` (bao gồm `base_url` và `config_version` ↔ `model_config_version`).
