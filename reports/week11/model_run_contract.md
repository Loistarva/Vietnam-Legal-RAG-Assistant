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
