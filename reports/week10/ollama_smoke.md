# Báo cáo Smoke & Độ trễ Ollama Qwen Gateway (`week10`)

**Phạm vi:** Task `D3.2` / `D3.3` / `D3.4` (Kế hoạch Tuần 10)  
**Model baseline:** `qwen2.5:7b` qua `Ollama 0.40.16` (`http://localhost:11434`)  
**Model digest (SHA-256):** `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`

---

## 1. Cấu hình thực thi đã xác minh

Từ [model_gateway/config/local_qwen.yaml](../../model_gateway/config/local_qwen.yaml):

- `provider`: `ollama`
- `model`: `qwen2.5:7b`
- `temperature`: `0.0`, `repeat_penalty`: `1.0`, `num_predict`: `1024`, `num_ctx`: `8192`
- `timeout_seconds`: `120.0`, `max_retries`: `1`, `cache_enabled`: `false`, `fallback_locked`: `true`

---

## 2. Kết quả Smoke Test Live 1 câu ([reports/dev3_live_qwen_verification.json](../dev3_live_qwen_verification.json))

**Thời điểm ghi nhận báo cáo live gần nhất:** `2026-11-14T04:56:46.928654+00:00`  
**Truy vấn:** `HN_003` — *"Việc kết hôn có bắt buộc do hai bên tự nguyện quyết định không?"* (`as_of_date=2026-10-15`, `as_of_date_source=benchmark`)  
**Ngữ cảnh:** 5 mảnh bằng chứng từ `retrieval/results/dev_hybrid_reranker.json` (`total_chars=4870 / 6000`).

| Chế độ chạy | Prompt Version | `done_reason` | `parse_status` | `evidence_indices` | `latency_ms` | `ttft_model_ms` | Tokens (in / out) |
| :--- | :--- | :--- | :--- | :--- | ---: | ---: | :---: |
| Run A (Zero-Shot) | `v1.1_zero_shot` | `stop` | `raw_text` | `[]` | `17575.76` | `786.36` | `443 / 118` |
| Run B (Controlled RAG) | `v1.2_controlled_rag` | `stop` | `ok` | `[2, 3]` | `30584.60` | `3615.41` | `2821 / 182` |

**8/8 tiêu chí kiểm tra live đều `PASS`:**
`ollama_version_recorded`, `model_digest_recorded`, `a_done_reason_stop`, `b_done_reason_stop`, `no_output_truncation`, `no_context_truncation`, `b_structured_output_parsed`, `b_evidence_indices_in_context`.

---

## 3. Tham chiếu hiệu năng lô Dev-30 chính thức (`results/run-b-20261110`)

**Run Directory:** `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2/`  
**Git SHA đối chiếu:** `02b0a803237983a20741273a881e18ba4824717d` (`run_manifest.json`)  
**Chế độ retrieval:** `precomputed` (`evaluation/results/precompute/20261110_dev30_retrieval.jsonl`)

- **Tỷ lệ hoàn tất:** `30 / 30` câu hỏi hợp lệ (`failed = 0`, `invalid_records = 0`, `truncated = 0`).
- **Phân bố `grounding_status`:** `29 PASS`, `1 ABSTAIN` (`HN_035` do `confidence_filter` với `LOW_CONFIDENCE`, `llm_calls = 0`), `0 FAIL`, `0 NEEDS_CLARIFICATION`.
- **Độ trễ toàn pipeline `latency_ms` (n=30, precomputed retrieval):**
  - `p50 = 31607.46 ms`
  - `p95 = 52356.99 ms`
- **Độ trễ gọi LLM `llm_total_ms` (n=29 câu hỏi có gọi LLM):**
  - `p50 = 31833.33 ms`
  - `p95 = 52354.76 ms`
- **Độ trễ TTFT xấp xỉ `ttft_model_ms` (n=29):**
  - `p50 = 2914.97 ms`
  - `p95 = 3781.85 ms`
- **Mức tiêu thụ token trung bình (n=29):** `2468.9` input tokens / `188.0` output tokens.

---

## 4. Phần gia cố Tuần 10 & phạm vi kiểm chứng

Các nâng cấp Tuần 10 tại [model_gateway/llm_gateway.py](../../model_gateway/llm_gateway.py) (`D3.3` & `D3.4`) gồm:
- Loại bỏ markdown fence (` ```json ... ``` `) trước khi parse JSON.
- Kiểm tra cấu trúc `StructuredRAGOutput` (`extra="forbid"`, bắt buộc có `"answer"` chuỗi) và gắn `error_code="JSON_INVALID"`.
- Hỗ trợ kiểm tra phạm vi chỉ số trích dẫn qua tham số `max_evidence_index`, ghi nhận chỉ số vượt biên vào `rejected_evidence_values` và gắn `error_code="CITATION_INVALID"`.
- Chuẩn hóa `GatewayExecutionError.error_code` (`LLM_TIMEOUT` vs `INTERNAL_ERROR`).
- Giữ `None` khi Ollama không trả `prompt_eval_count` / `eval_count` và sinh `raw_response_reference`.

- **Cập nhật xác minh live khi review PR (`2026-11-16`, commit `9d57092`):** Reviewer đã chạy lại `scripts/verify_qwen_live.py` trên code mới với `Ollama 0.40.16` và model digest `845dbda0...`: kết quả **8/8 `PASS`**, `error_code = null`, có đầy đủ `raw_response_reference`, và Run B `parse_status = ok` (tệp JSON cục bộ của lượt chạy review không commit vào repo).
- **Phạm vi kiểm chứng tự động:** Các kịch bản lỗi biên của gateway Tuần 10 (bóc markdown fence, JSON thiếu trường/sai cấu trúc, timeout `LLM_TIMEOUT`, và `max_evidence_index` gắn `CITATION_INVALID`) được kiểm thử tự động qua mock transport trong [test_structured_output.py](../../test/model_gateway/test_structured_output.py); các số liệu định lượng chi tiết ở Mục 2 và Mục 3 được giữ nguyên từ lần chạy đã ghi artifact ngày `2026-11-14`.
