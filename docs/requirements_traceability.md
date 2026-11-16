# Ma trận truy vết và trạng thái

**Ảnh chụp tại `origin/testing` `c1e9f12` (16/11/2026).** File này ghi đã làm tới đâu so với [SRS 2.1](SRS.md) và số đo hiện tại của KPI trong [BRD](BRD.md). Nó được cập nhật theo từng PR hoặc lượt chạy; SRS và BRD thì không. Khi có marker `@pytest.mark.req` (SRS NFR6.2), bảng yêu cầu sẽ được sinh tự động.

Trạng thái: **Có** = đã hiện thực và có bằng chứng · **Một phần** = thiếu phần ghi ở cột Ghi chú · **Chưa** = chưa có trên `testing`.

## Tóm tắt theo giai đoạn

| Giai đoạn | Có | Một phần | Chưa | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| GĐ1 | 42 | 18 | 1 | Lõi RAG, Gate cấu trúc, kho văn bản, đánh giá lô đã có. Còn chấm mù A/B (NFR1.1, FR9.3–FR9.6), máy tham chiếu latency, Top-10 sau reranker. |
| GĐ2 | 1 | 7 | 25 | Router có nhưng chưa nối; chưa có API, UI trên `testing`, log, che PII, hỏi lại. |
| GĐ3 | 0 | 0 | 18 | Chưa bắt đầu. |

Tổng 112 yêu cầu, đếm theo cột GĐ của SRS. Năm yêu cầu có hai giai đoạn (FR3.1, FR6.1, FR8.9, IR1.7, IR2.4) được đếm ở giai đoạn đầu; "Một phần" ở đó có thể là phần của giai đoạn sau chưa có.

## KPI

| KPI (BRD) | Tập | Số đo | Nguồn | So với mục tiêu đề xuất |
| --- | --- | --- | --- | --- |
| BO-01 Recall@5 sau rerank | Test (30) | 0,8978 | [baseline_report.md](baseline_report.md) (08/11) | Đạt ≥ 0,85 |
| BO-01 Recall@5 sau rerank (theo dõi) | Dev (75) | 0,7335 | như trên | — |
| BO-01 MRR@5 sau rerank | Test | 0,8694 | như trên | Đạt ≥ 0,80 |
| BO-01 Temporal Violation | Dev + Test | 0/750, 0/300 | như trên | Đạt |
| BO-02 Legal Correctness, Hallucination, Faithfulness | Dev30 A/B | Chưa có | Chấm mù chưa xong (`evaluation/results/dev/blinded_ab_scoring_v1.csv` chưa có điểm) | — |
| BO-03 Citation Precision / Recall (Run B) | Dev30 | 0,7056 / 0,7356 | `evaluation/results/metrics_A_B_results/results_metrics.json` (prompt v1.2) | Chưa đạt 0,80 |
| BO-03 Citation Validity trước Gate | Dev30 | 52/52 | như trên | Đạt |
| BO-03 Câu không phải tiếng Việt | Dev30 A / B | 0/30 / 0/30 | `…/20261115_zero_shot_qwen25_dev30_metrics.json`, `results_metrics.json` | Đạt |
| BO-04 Tập câu âm, toàn hệ thống | 26 câu | Chưa đo | Router chưa nối vào pipeline | — |
| BO-04 Riêng ngưỡng tin cậy 0,5 | 26 câu | Chặn 15/26: non_legal 6/6, ngoài phạm vi 7/8, kho không có 1/6, thiếu dữ kiện 1/6 | [calibration](../reports/retrieval/confidence_threshold_dev_calibration.md) | Chỉ là một tầng |
| BO-04 Từ chối nhầm | Dev30 | 1/30 (HN_035) | `results_metrics.json` | Đạt ≤ 5% |
| BO-05 Thời gian tới câu trả lời, p50 / p95 (Run B v1.2) | Dev30 | 31,8 s / 50,3 s | `results_metrics.json` | Chưa có máy tham chiếu; Run A chạy máy khác (manifest `platform` khác) |
| BO-06 Câu khuyến cáo | Dev30 A / B | 30/30 / 30/30 | file kết quả | Đạt |
| BO-07 Chi phí / câu | Dev30 | 0 USD (local) | `results_metrics.json` | Đạt |

## FR1. Định tuyến

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR1.1 | Một phần | `test/agent/test_rule_router.py`, `test/test_smoke_rule_router.py` | Router chạy độc lập; v3 đang ở PR #46. |
| FR1.2 | Một phần | `test/agent/test_rule_router.py` | Router trả `GENERAL_CHAT`; chưa có General Chat Responder. |
| FR1.3 | Một phần | như trên | Chưa nối vào pipeline (kế hoạch Tuần 10 D5.1). |
| FR1.4 | Một phần | như trên | Như trên. |
| FR1.5 | Một phần | như trên | Như trên. |
| FR1.6 | Một phần | như trên | Như trên. |
| FR1.7 | Một phần | `test/agent/test_rule_router.py`, `test/evaluation/test_run_rag_batch.py` | Chưa có giới hạn độ dài. |
| FR1.8 | Một phần | `test/agent/data/router_holdout.jsonl` | Chưa xác nhận tính độc lập. |

## FR2. Lọc trước và truy xuất

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR2.1 | Một phần | `retrieval/temporal.py`, `test/test_pipeline_context.py` | Hàm có; pipeline chưa có chế độ tương tác; nhãn `question/ui/today` chưa ánh xạ sang `query_text/user_input/system_today`. |
| FR2.2 | Chưa | — | Metadata có sẵn trong chunk (`document_number`, `document_type`, `issuing_body`, `issue_date`). |
| FR2.3 | Chưa | — | |
| FR2.4 | Có | `test/test_e1_temporal_retrieval.py`, `test/test_provision_periods.py` | |
| FR2.5 | Có | `test/test_bm25_retrieval.py` | |
| FR2.6 | Có | `test/test_dense_retriever.py` | |
| FR2.7 | Có | `test/test_hybrid_retriever.py` | `retrieval_top_k = 50`, `rrf_k = 60`. |
| FR2.8 | Một phần | `test/test_reranker.py` | Reranker đang giữ Top-5 (`rerank_top_k = 5`), sơ đồ là Top-10 (D-04). |
| FR2.9 | Chưa | — | |
| FR2.10 | Có | `test/orchestration/test_evidence_index_mapping.py` | |
| FR2.11 | Có | như trên | |

## FR3. Ngưỡng tin cậy và làm rõ

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR3.1 | Một phần | `test/test_confidence.py`, `test/orchestration/test_grounding_gate.py` | Phần ngưỡng (GĐ1) có; LLM Judge (GĐ3) chưa. |
| FR3.2 | Chưa | — | Chưa có MMR. |
| FR3.3 | Có | `test/orchestration/test_record_abstention_latency.py` | Mã trong code là `EMPTY_RETRIEVAL`. |
| FR3.4 | Chưa | — | Hiện luôn từ chối, không hỏi lại. |
| FR3.5 | Chưa | — | |
| FR3.6 | Có | `test/orchestration/test_grounding_gate.py` | Thông báo làm rõ cố định. |
| FR3.7 | Có | `test/test_calibrate_confidence_threshold.py`; báo cáo calibration | |

## FR4. Sinh câu trả lời có trích dẫn

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR4.1 | Có | `test/test_pipeline_context.py` | 1.079 parent, đều cấp Điều, ≤ 1.498 ký tự. |
| FR4.2 | Có | `test/orchestration/test_evidence_index_mapping.py`, `test/schema_test.py` | |
| FR4.3 | Có | `test/schema_test.py` | |
| FR4.4 | Có | `test/test_p45_prompt_gateway.py`, `test/test_dev3_sprint9_contracts_prompt_gateway.py` | Prompt v1.2. |
| FR4.5 | Có | `test/orchestration/test_evidence_index_mapping.py`, `test/orchestration/test_grounding_gate.py` | |
| FR4.6 | Có | `test/test_p45_prompt_gateway.py` | Hash ở `retrieval_trace.prompt_sha256`. |
| FR4.7 | Có | `test/orchestration/test_evidence_index_mapping.py` | Hiển thị trên UI chờ IR1.4. |

## FR5. Grounding Gate và từ chối

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR5.1 | Có | `test/orchestration/test_grounding_gate.py` | Gateway gọi không stream; bản nháp chỉ phát sau Gate. |
| FR5.2 | Có | `test/grounding/test_citation_validator.py`, `test/orchestration/test_grounding_gate.py`, `test/orchestration/test_record_abstention_latency.py` | |
| FR5.3 | Chưa | — | |
| FR5.4 | Một phần | `test/orchestration/test_grounding_gate.py` | Citations Map có; Evidence Panel chưa. |
| FR5.5 | Có | `test/orchestration/test_grounding_gate.py` | |
| FR5.6 | Chưa | — | |
| FR5.7 | Một phần | `test/orchestration/test_record_abstention_latency.py` | Nguồn `router` và `clarification` chưa dùng. |
| FR5.8 | Một phần | `test/orchestration/test_grounding_gate.py` | Nhánh xã giao và API chưa có. |

## FR6. Model Gateway

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR6.1 | Một phần | `model_gateway/llm_gateway.py` | Một gateway, một provider (Ollama); chưa có giao diện tương thích OpenAI. |
| FR6.2 | Có | `model_gateway/config/local_qwen.yaml` | |
| FR6.3 | Chưa | — | `fallback_locked = true`. |
| FR6.4 | Chưa | — | Lỗi kiểu `LLM_TIMEOUT` đang ở PR #49. |
| FR6.5 | Chưa | — | |
| FR6.6 | Có | `test/test_p45_prompt_gateway.py` | |
| FR6.7 | Có | Manifest các lượt official | |
| FR6.8 | Có | Manifest (`provider: ollama`) | |

## FR7. Phiên và lịch sử

| Mã | Trạng thái | Ghi chú |
| --- | --- | --- |
| FR7.1–FR7.4 | Chưa | Batch có `query_id`; chưa có session. |

## FR8. Knowledge Base

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR8.1 | Có | `data/reference/document_versions.json` (28/28 có `source_url`) | |
| FR8.2 | Có | `parser/extracted_texts_qwen/` (28 file) | Bóc tách ngoại tuyến. |
| FR8.3 | Có | `parser/test_parser.py`, `test/test_chunking.py` | |
| FR8.4 | Có | `test/test_chunking.py` | `seg_text` cho BM25, `embed_text_raw` cho dense. |
| FR8.5 | Có | `test/test_chunking.py` | 2.322 child chunk. |
| FR8.6 | Có | `test/schema_test.py` | |
| FR8.7 | Có | `test/test_provision_periods.py`; `data/reference/provision_periods.json` | |
| FR8.8 | Có | `test/test_bm25_retrieval.py`, `test/test_dense_retriever.py` | |
| FR8.9 | Một phần | Manifest (`corpus_sha256`) | Cập nhật thủ công; chưa có cache để xóa. |
| FR8.10 | Chưa | — | |

## FR9. Đánh giá và giám sát

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR9.1 | Có | `evaluation/results/*_metrics.json`, `docs/baseline_report.md` | |
| FR9.2 | Có | `evaluation/results/metrics_A_B_results/` | |
| FR9.3 | Một phần | như trên | Faithfulness theo rubric chưa chấm. |
| FR9.4 | Một phần | như trên | Chưa có thời gian tới byte đầu tiên. |
| FR9.5 | Một phần | `evaluation/metric_definitions_v1.md` | Legal Correctness, Hallucination chờ chấm mù. |
| FR9.6 | Một phần | `evaluation/results/dev/blinded_ab_scoring_v1.csv` | Chưa có điểm, chưa có Kappa. |
| FR9.7 | Có | `test/evaluation/test_dev30_no_test_leakage.py`, `test/test_freeze_safety.py` | |
| FR9.8 | Có | `test/evaluation/test_run_rag_batch.py` | |
| FR9.9 | Chưa | — | Chưa có `monitoring/` (kế hoạch Tuần 10 D1.2). |
| FR9.10 | Chưa | — | |
| FR9.11 | Chưa | — | |

## IR. Giao diện

| Mã | Trạng thái | Ghi chú |
| --- | --- | --- |
| IR1.1–IR1.7 | Chưa | UI Streamlit ở PR #51 (`sprint10/UI`), chưa merge. |
| IR2.1–IR2.5 | Chưa | Chưa có `api/` (kế hoạch Tuần 10 D5.3–D5.6). |
| IR3.1 | Chưa | Chưa có `scripts/run_rag_cli.py`. |
| IR3.2 | Có | `scripts/run_rag_batch.py`, `test/evaluation/test_run_rag_batch.py` |
| IR4.1 | Một phần | `orchestration/rag_pipeline.py` inject nguồn ứng viên và generator; router, validator, logger chưa qua interface. |

## NFR

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| NFR1.1 | Chưa | — | Chờ chấm mù. |
| NFR1.2 | Có | `docs/baseline_report.md` | |
| NFR1.3 | Có | `test/orchestration/test_record_abstention_latency.py` | |
| NFR2.1 | Chưa | — | Cần SSE. |
| NFR2.2 | Chưa | — | |
| NFR2.3 | Một phần | `results_metrics.json` | Manifest chỉ có `platform`, không có GPU. |
| NFR3.1 | Chưa | — | |
| NFR3.2 | Chưa | — | |
| NFR3.3 | Một phần | — | Chưa có quét secret tự động. |
| NFR3.4 | Chưa | — | |
| NFR3.5 | Chưa | — | |
| NFR4.1 | Có | Manifest (`cache_enabled`, `fallback_locked`, `working_tree_dirty`) | |
| NFR4.2 | Một phần | Manifest | Thiếu cấu hình máy. |
| NFR4.3 | Có | Manifest (hash cấu hình) | |
| NFR5.1 | Có | `test/test_dense_retriever.py`, `test/test_bm25_retrieval.py` | |
| NFR5.2 | Có | `deployment/qdrant/docker-compose.qdrant.yml` | |
| NFR6.1 | Có | `.github/workflows/tests.yml` | |
| NFR6.2 | Chưa | — | |
| NFR6.3 | Một phần | `test/orchestration/conftest.py` | Router, logger chưa có mock interface. |
| NFR7.1–NFR7.3 | Chưa | — | |
| NFR8.1 | Chưa | — | |
