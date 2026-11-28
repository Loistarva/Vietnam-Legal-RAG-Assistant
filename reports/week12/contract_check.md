# Week 12 Contract, Prompt Hash & Metadata Check (`S12-D3.1`, `S12-D3.2`)

- **Nhánh làm việc:** `feature/sprint12-dev3-config-and-fixtures` (tách từ `origin/testing` tại commit `2f9ff16`).
- **Phạm vi kiểm tra:** Canonical schema `week10_v1.1`, `api/openapi.json`, khóa SHA-256 prompt Test 30 (`S12-DEC-01` / `S12-D5.3`), kiểm chứng `model_gateway/run_metadata.py` (`D3.4` / `NFR4.2`), trạng thái `S12-DEC-04` (`SRS 5.6`) và `S12-DEC-05` (`origin/main` vs `origin/testing`).

---

## 1. Trạng thái Contract `week10_v1.1` & `api/openapi.json`

- `schemas/models.py`: `SCHEMA_VERSION == "week10_v1.1"`, `len(CANONICAL_SCHEMA_MODELS) == 10`.
- Lệnh `python -m schemas.models`: tái sinh 4 JSON Schema gốc và 10 JSON Schema trong `schemas/generated/` thành công, không phát sinh diff ngoài ý muốn trên `schemas/`.
- Lệnh `python -m api.export_openapi --check`: thoát mã `0` (`api/openapi.json` khớp 100% với FastAPI app và `schemas/models.py`).
- Bộ fixture bàn giao trong `test/fixtures/sprint12/` (`ask_response_success_v1.1.json`, `ask_response_needs_clarification_v1.1.json`, `ask_response_abstain_v1.1.json`, `api_error_llm_unavailable_v1.1.json`, `ask_response_error_llm_unavailable_v1.1.json`) đều đạt kiểm tra Pydantic (`AskResponse`, `ApiError`) và JSON Schema (`schemas/generated/ask_response.schema.json`) tại `test/schemas/test_sprint12_fixtures.py`.

---

## 2. Khóa SHA-256 Prompt Test 30 (`S12-DEC-01` & `S12-D5.3`)

So sánh hai bộ prompt để Tech Lead duyệt cho lượt chạy A/B Test 30 (`S12-DEC-01`) và Dev 5 khóa hash vào `run_manifest.json` (`S12-D5.3`):

| Thành phần | Phiên bản / Đường dẫn | Canonical / File SHA-256 | Ghi chú cho Test 30 |
| --- | --- | --- | --- |
| Prompt A (Zero-Shot) | `v1.2_zero_shot` | `c5c45e90894e9d58984f4c2b71a2fdaad75cf090a0323be1cde16bf2f918893b` | Bản official Run A bất biến trên input chuẩn `CANONICAL_V12`; không đổi từng byte |
| Prompt B (`v1.2`) | `v1.2_controlled_rag` | `5a19fe70f42efbb101945888d1f4cec8548f78a9a8b704bd31b68acfb4b75940` | Bản official mặc định (`OFFICIAL_PROMPT_B_VERSION`); không chứa `missing_facts`; giữ nguyên 100% từ Dev30 |
| Prompt B (`v1.3` template) | `generation/prompts/legal_rag_prompt_v1_3.md` | `fca5e25399b63c8734e7d5a5be8a30d4dd18a80c9240679bbc776c82e881a211` | File template Markdown `v1.3_controlled_rag` (LF normalized) |
| Prompt B (`v1.3` rendered canonical) | `v1.3_controlled_rag` | `f301d91b716354abbbf49cb95a8a2d493f648f524ae2f18dc34b18f5a49a1efb` | Render trên `CANONICAL_V12` sau khi đọc `configs/missing_facts_taxonomy.yaml`; khớp từng byte trước & sau refactor |
| Spec Prompt `v1.0_spec` | `generation/prompts/legal_rag_prompt_v1_0.md` | `4e8e9bae20447b5b01caebeb7be0dbe994f137b52f4f4f5620b4fa6f83997669` | Tham chiếu gốc Sprint 9 |
| Taxonomy `missing_facts` | `configs/missing_facts_taxonomy.yaml` (`missing_facts_v1.0`) | `4bd94364cf1f6d5e7b7e0a36143d7286583f184eeb2c9487d6f66ee9832bebf8` | Chứa 10 nhóm đóng, `clarification_template` tiếng Việt và `generic_clarification_message` (`FR3.6`) |

### Hash các tệp cấu hình / dữ liệu Test freeze liên quan (`NFR4.2`, `NFR4.3`)

| Tệp | SHA-256 (raw file) |
| --- | --- |
| `docs/test_run_config_freeze.json` | `fa3583dedf3ee4ce9a60835cbd8bda35e3c0646959b10eec39ede950e57a4d37` |
| `docs/test_questions_freeze.json` | `7da1a5e1864bc17c2838b1332890d741367be5fea34d589d59b589f364ec0f9e` |
| `docs/test_gold_freeze.json` | `40a3cd468469aa554ed8d53f60150eb1b6e69d5b8eb22cd44b14a14eefbbbe77` |
| `model_gateway/config/local_qwen.yaml` | `f9dbe5c6bb823368b74da7a0cfd329b355c00a9aa46fd554cee2dcc91a2880bf` |

### Đối chiếu nhanh `v1.2_controlled_rag` vs `v1.3_controlled_rag` cho `S12-DEC-01`

1. **`v1.2_controlled_rag` (`OFFICIAL_PROMPT_B_VERSION`):** ổn định trên Dev30, không có `missing_facts`, chỉ định dạng `Hiệu lực: <validity_status> (<from> -> <to>)`. Phù hợp nếu muốn đối sánh trực tiếp với lịch sử Dev30 của Sprint 10–11.
2. **`v1.3_controlled_rag` (`PROMPT_B_V1_3_VERSION`):** bổ sung nhãn hiệu lực tại `as_of_date` theo khoảng `[effective_from, effective_to)` (`FR4.3-AC2`) và danh mục đóng 10 mã `missing_facts` đọc từ `configs/missing_facts_taxonomy.yaml` (`FR3.4`, `FR4.4`). Nếu Tech Lead chọn `v1.2` cho Test 30, `v1.3` chỉ bật ở API sau khi kết thúc lượt chạy Test 30; nếu chọn `v1.3`, giữ nguyên đúng hash đã khóa ở bảng trên.

---

## 3. Kiểm chứng `model_gateway/run_metadata.py` (`D3.4` / `NFR4.2`)

- `validate_runtime_config(DEFAULT_CONFIG_PATH, official=True)` trả về `[]` (hợp lệ tuyệt đối) với cấu hình:
  - `config_version`: `"local_qwen_v1.1"`
  - `provider`: `"ollama"`
  - `model`: `"qwen2.5:7b"`
  - `temperature`: `0.0`
  - `repeat_penalty`: `1.0`
  - `num_predict`: `1024`
  - `num_ctx`: `8192`
  - `timeout_seconds`: `120.0`
  - `max_retries`: `1` (chính sách official `0 <= max_retries <= 1`, chặn `> 1`)
  - `cache_enabled`: `false`
  - `fallback_locked`: `true`
- Toàn bộ `56` test trong `test/model_gateway/test_run_metadata.py` pass (kiểm tra snapshot cấu hình đủ khóa khi đọc standalone, đối chiếu `base_model_config_hash`, `effective_model_config_hash`, hardware fields `os`/`cpu`/`gpu`/`vram`, từ chối NaN/Inf và số nguyên vượt biên 64-bit).

---

## 4. Trạng thái quyết định kiến trúc liên quan (`S12-DEC-04`, `S12-DEC-05`)

- **`S12-DEC-04` (`SRS 5.6` — `RetrievalBundle.metadata_filters` & `latency_breakdown`):**
  - Trong `docs/SRS.md` mục 5.6 trên `origin/testing`, dòng `RetrievalBundle.metadata_filters` và `RetrievalBundle.latency_breakdown` đã ở trạng thái **"Đã duyệt và gộp vào bản `week10_v1.1` thống nhất (PR #56 + PR #63)"**.
  - `schemas/models.py` đã định nghĩa sẵn `metadata_filters: MetadataFilters | None = None` và `latency_breakdown: RetrievalLatencyBreakdown | None = None` cùng `RetrievalLatencyBreakdown` và `MetadataFilters`. Không cần thay đổi phá vỡ contract hiện hành.

- **`S12-DEC-05` (Lệch `origin/main` so với `origin/testing` từ PR #60):**
  - `origin/main` hiện đang ở commit `b1a25e6` (`Merge pull request #60 from Loistarva/feature/week11-dev3-contracts-gateway`), đi trước/lệch nhánh `testing` ở các commit PR #60 cũ (`5e77065`, `0a5c232`) trong khi `origin/testing` đã ở commit `2f9ff16` (gồm PR #53, #59, #61, #63, #64, #66, #68).
  - Kết quả `git diff --stat origin/testing..origin/main`: **`155 files changed, 647 insertions(+), 16293 deletions(-)`**.
  - Khuyến nghị trình Tech Lead xác nhận: đồng bộ `main <- testing` sau khi nghiệm thu Sprint 12 (hoặc revert PR #60 trên `main` trước khi merge phát hành chính thức) — Dev 3 không tự ý sửa `main`.
