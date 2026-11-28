# Ma trận truy vết và trạng thái

**Ảnh chụp nền tại `origin/testing` (`03a4989`, cập nhật phần Dev 3 Sprint 11 ngày 23/11/2026 trên nhánh `feature/week11-dev3-contracts-gateway`; tích hợp đặc tả phân hệ Tóm tắt bản án `2.2.0` ngày 25/11/2026). Contract hiện hành: `schema_version = week10_v1.1` (`schemas/models.py`, tương thích ngược `week10_v1.0`); lộ trình Sprint 12 dự kiến `week12_v1.0`.** File này ghi đã làm tới đâu so với [SRS 2.2.0](SRS.md) và số đo hiện tại của KPI trong [BRD 2.2.0](BRD.md). Nó được cập nhật theo từng PR hoặc lượt chạy; SRS và BRD thì không. Khi có marker `@pytest.mark.req` (SRS NFR6.2), bảng yêu cầu sẽ được sinh tự động.

Trạng thái: **Có** = đã hiện thực và có bằng chứng · **Một phần** = thiếu phần ghi ở cột Ghi chú · **Chưa** = chưa có trên `testing`.

Trạng thái được đánh giá theo câu yêu cầu và tiêu chí chấp nhận của SRS 2.2.0 (trong đó khối Legal Q&A kế thừa baseline 2.1.1/2.1.2 và khối Tóm tắt bản án ở trạng thái `Proposed`), đối chiếu với code và test hiện có. Test chưa gắn marker theo mã tiêu chí (`-ACk`), nên một vài tiêu chí của yêu cầu ghi *Có* có thể chưa có test riêng; việc gắn marker (NFR6.2) sẽ làm lộ các chỗ này.

## Tóm tắt theo giai đoạn

| Giai đoạn | Có | Một phần | Chưa | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| GĐ1 | 39 | 21 | 1 | Lõi RAG, Gate cấu trúc, kho văn bản, đánh giá lô đã có. Còn chấm mù A/B (NFR1.1, FR9.3–FR9.6), máy tham chiếu latency, Top-10 sau reranker, vài tiêu chí truy vết (FR2.4-AC4, FR2.11, FR4.1-AC2). |
| GĐ2 | 1 | 8 | 25 | Contract API có (`week10_v1.0`); router chưa nối (FR1.9); chưa có API, UI trên `testing`, log, che PII, hỏi lại. |
| GĐ3 | 0 | 0 | 18 | Chưa bắt đầu; mỗi khối cần feature spec trước (SRS mục 11). |
| Sprint 12 (Tóm tắt bản án) | 0 | 0 | 12 | Đã đặc tả `FR10.1`–`FR10.8` và `NFR10.1`–`NFR10.4` trong SRS 2.2.0 (`Proposed`); chờ triển khai contract `week12_v1.0` và pipeline `summarization/`. |

Tổng 125 yêu cầu (113 yêu cầu Q&A đếm theo cột GĐ của SRS + 12 yêu cầu `FR10.1`–`FR10.8`, `NFR10.1`–`NFR10.4` cho Sprint 12). Năm yêu cầu có hai giai đoạn (FR3.1, FR6.1, FR8.9, IR1.7, IR2.4) được đếm ở giai đoạn đầu; "Một phần" ở đó có thể là phần của giai đoạn sau chưa có.

## KPI

| KPI (BRD) | Tập | Số đo | Nguồn | So với mục tiêu |
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
| BO-JS-01 Tóm tắt bản án API & Streamlit UI không hồi quy Q&A | Sprint 12 | Chưa có | Chưa triển khai (`FR10.8`) | Mục tiêu vận hành ổn định; 100% test hồi quy Q&A PASS |
| BO-JS-02 Thời gian trích xuất 5 nhóm thông tin cốt lõi | Usability Test | Chưa có | Chưa đo (`FR10.5`, `FR10.8`) | Mục tiêu giảm ≥ 40% so với đọc toàn văn |
| BO-JS-03 Factual Accuracy & Acceptance Rate | Test (20 bản án freeze) | Chưa có | Chưa triển khai (`NFR10.1`) | Mục tiêu $FA \ge 90\%$ (micro-average + macro-average) kèm $AR$; $AR = 0\% \Rightarrow \text{FAIL}$ |
| BO-JS-04 Critical-fact Omission Rate | Test (20 bản án freeze) | Chưa có | Chưa triển khai (`FR10.4`, `NFR10.1`) | Mục tiêu $CFO < 10\%$ trên toàn bộ $N_{\text{total}}$ bản án (tách thêm trên Accepted) |
| BO-JS-05 Expert Quality Score | Test (20 bản án freeze) | Chưa có | Chưa chấm (`FR10.6`, `NFR10.1`) | Mục tiêu $\ge 4,0 / 5,0$ theo rubric 5 tiêu chí + Hard Gate ($\le 2,0$ nếu sai/thiếu quyết định) |
| BO-JS-06 Decision Accuracy & Decision Coverage | Dev (10) + Test (20) | Chưa có | Chưa triển khai (`FR10.2`, `FR10.7`, `NFR10.1`) | Mục tiêu $DA = 100\%$ (theo doc phát hành) / $DC = 100\%$ (theo mục quyết định) |
| BO-JS-07 Tỷ lệ mục `PRESENT` có `source_refs` đúng tới `Pxxx_yyy` | Dev (10) + Test (20) | Chưa có | Chưa triển khai (`FR10.1`, `FR10.5`) | Mục tiêu 100% |
| BO-JS-08 Rò rỉ PII bản án trong log & hồi quy Q&A | Bộ test PII & CI Q&A | Chưa có | Chưa triển khai (`NFR10.3`, `FR10.8`) | Mục tiêu 0 rò rỉ; 100% test Q&A PASS |

## Contract so với SRS mục 5

Quyết định contract được cập nhật theo [review của Owner Contract ngày 17/11/2026](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/54#pullrequestreview-5938652304). Trạng thái triển khai vẫn đối chiếu với `testing` `01fe249`: được đồng ý đưa vào lộ trình không đồng nghĩa đã triển khai hoặc đã merge.

| Hạng mục (SRS 5.6) | Phiên bản | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| `ErrorCode.LLM_UNAVAILABLE` (503) | `week10_v1.1` | Có | Đã thêm vào `schemas/models.py`, `model_gateway/llm_gateway.py` và `test/schemas/test_contracts.py` + `test/model_gateway/test_structured_output.py`. |
| `EventStage.confidence` | `week10_v1.1` | Có | Đã thêm vào `schemas/models.py` (`test/schemas/test_contracts.py`); logger/orchestrator dùng theo stage mới. |
| `EvidenceItem.point_ref` | `week10_v1.1` | Có | Đã thêm vào `EvidenceItem` và `ContextPayload.source_map` (`test/schemas/test_contracts.py`); 272/2.322 chunk có `point_ref`. |
| `StructuredRAGOutput.missing_facts` / `LLMResponse.missing_facts` | `week10_v1.1` | Có | Đã thêm vào `schemas/models.py` (mặc định `[]`, tương thích `v1.2`) và prompt `v1.3` (`test/generation/test_prompt_builder.py`). |
| `RouteDecision.router_route` & `RouteAction` | `week10_v1.1` | Có | Khóa 4 giá trị chuẩn theo SRS 5.3.3 (`test/schemas/test_contracts.py`). |
| `RetrievalBundle.metadata_filters`, `latency_breakdown` | `week10_v1.1` | Có | Đã gộp `MetadataFilters` và `RetrievalLatencyBreakdown` từ PR #56 vào bản `week10_v1.1` thống nhất trên nhánh Dev 3 (PR #60); bản ghi cũ không có 2 trường này vẫn hợp lệ. |
| `RAGOutputRecord.route: RouteType \| None = None` | `week10_v1.1` | Có | Đã gộp từ PR #56 vào bản `week10_v1.1` thống nhất trên nhánh Dev 3 (PR #60); bản ghi cũ thiếu `route` vẫn hợp lệ. |
| `AskResponse.session_id`, stage `session` | khi FR7.2 | Dự kiến | |
| `ErrorCode` thêm `RATE_LIMITED` (HTTP 429) | khi NFR3.2 | Dự kiến | |
| Nhóm 1 Summarization: `ParsedDocument`, `SectionedDocument`, `ContextPlan` (`schemas/models.py`) | `week12_v1.0` | Dự kiến | Owner: Dev 3 (`FR10.1`–`FR10.3`); Consumer: `summarization/parser.py`, `section_identifier.py`, `context_planner.py`. |
| Nhóm 2 Summarization: `FactLedger`, `StructuredSummary`, `VerificationReport` (`schemas/models.py`) | `week12_v1.0` | Dự kiến | Owner: Dev 3 (`FR10.4`–`FR10.7`); Consumer: `summarization/structured_summarizer.py`, `checklist_qa.py`, `release_gate.py`. |
| Nhóm 3 Summarization: `SummarizationResponse`, mở rộng `ErrorCode` (`UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `EMPTY_DOCUMENT`, `DOCUMENT_PARSE_FAILED`, `OCR_REQUIRED`, `UNSUPPORTED_DOCUMENT_TYPE`, `DECISION_NOT_FOUND`, `DOCUMENT_LIMIT_EXCEEDED`, `SUMMARY_GENERATION_FAILED`, `SUMMARY_QA_FAILED`) & `EventStage` (`summarization_*`) trong `schemas/models.py` | `week12_v1.0` | Dự kiến | Owner: Dev 3 (`FR10.8`, `NFR10.2`); Consumer: `api/`, `orchestration/summarization_service.py`, `monitoring/`. |

Hành vi của PR #55 cần khớp SRS 5.3.4 trước khi merge: sai API key trả 401 (đang 403); từ chối của Confidence Filter trả `grounding_status = NOT_RUN` (đang `ABSTAIN`). Lớp API cần kiểm tra giới hạn 2.000 ký tự trước pipeline (FR1.7) và trả body `ApiError` cho 401/422, gồm cả lỗi validation của FastAPI (IR2.1-AC2, IR2.2-AC1); các AC này chưa được xác nhận trên ảnh chụp `testing`.

## FR1. Định tuyến

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR1.1 | Một phần | `test/agent/test_rule_router.py`, `test/test_smoke_rule_router.py` | Router chạy độc lập; v3 đang ở PR #46. |
| FR1.2 | Một phần | `test/agent/test_rule_router.py` | Router trả `GENERAL_CHAT`; chưa có General Chat Responder. |
| FR1.3 | Một phần | như trên | Contract `RouteDecision` (`RouteType` + `action`) có; nối vào pipeline ở PR #55, chưa merge. |
| FR1.4 | Một phần | như trên | Như trên. |
| FR1.5 | Một phần | như trên | Như trên. |
| FR1.6 | Một phần | như trên | Như trên. |
| FR1.7 | Một phần | `test/agent/test_rule_router.py`, `test/evaluation/test_run_rag_batch.py` | Chưa có giới hạn độ dài; API cần kiểm tra trước pipeline, kiểm thử biên 2.000/2.001 ký tự và body `ApiError` 422 (AC1–AC2). |
| FR1.8 | Một phần | `test/agent/data/router_holdout.jsonl` | Chưa xác nhận tính độc lập. |
| FR1.9 | Chưa | — | Orchestrator gọi router ở PR #55, chưa merge. |

## FR2. Lọc trước và truy xuất

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR2.1 | Một phần | `retrieval/temporal.py`, `test/test_pipeline_context.py` | Hàm có; pipeline chưa có chế độ tương tác; nhãn `question/ui/today` chưa ánh xạ sang `query_text/user_input/system_today`. |
| FR2.2 | Chưa | — | Metadata có sẵn trong chunk (`document_number`, `document_type`, `issuing_body`, `issue_date`). |
| FR2.3 | Chưa | — | |
| FR2.4 | Một phần | `test/test_e1_temporal_retrieval.py`, `test/test_provision_periods.py` | AC1–AC3 có; AC4 chưa có test so sánh ba nhánh (Elasticsearch, Qdrant, precomputed). |
| FR2.5 | Có | `test/test_bm25_retrieval.py` | |
| FR2.6 | Có | `test/test_dense_retriever.py` | |
| FR2.7 | Có | `test/test_hybrid_retriever.py` | `retrieval_top_k = 50`, `rrf_k = 60`. |
| FR2.8 | Một phần | `test/test_reranker.py` | Reranker đang giữ Top-5 (`rerank_top_k = 5`), sơ đồ là Top-10 (D-04). |
| FR2.9 | Chưa | — | |
| FR2.10 | Có | `test/orchestration/test_evidence_index_mapping.py` | |
| FR2.11 | Một phần | như trên | `retrieval_trace` chưa ghi bộ lọc đã áp dụng (`as_of_date` chỉ ở cấp bản ghi). |

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
| FR4.1 | Một phần | `test/test_pipeline_context.py` | 1.079 parent, đều cấp Điều, ≤ 1.498 ký tự. AC2: thiếu parent mới chỉ ghi cảnh báo vào log, chưa vào `retrieval_trace`. |
| FR4.2 | Có | `test/orchestration/test_evidence_index_mapping.py`, `test/schema_test.py` | |
| FR4.3 | Có | `test/schema_test.py`, `test/generation/test_prompt_builder.py` | Prompt `v1.3` render thêm nhãn hiệu lực tại `as_of_date` (`FR4.3`). |
| FR4.4 | Có | `test/test_p45_prompt_gateway.py`, `test/test_dev3_sprint9_contracts_prompt_gateway.py`, `test/generation/test_prompt_builder.py`, `test/schemas/test_contracts.py` | Prompt official `v1.2`; `v1.3` thêm `missing_facts` danh mục đóng. |
| FR4.5 | Có | `test/orchestration/test_evidence_index_mapping.py`, `test/orchestration/test_grounding_gate.py`, `test/generation/test_prompt_builder.py` | |
| FR4.6 | Có | `test/test_p45_prompt_gateway.py`, `test/generation/test_prompt_builder.py` | Hash ở `retrieval_trace.prompt_sha256`; thêm `verify_prompt_template_integrity` chặn sửa template không tăng version (`AC2`). |
| FR4.7 | Có | `test/orchestration/test_evidence_index_mapping.py`, `test/schemas/test_contracts.py` | AC1 và `EvidenceItem.point_ref` (`week10_v1.1`, AC2) đã có trong contract; hiển thị trên UI chờ IR1.4. |

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
| FR6.2 | Có | `model_gateway/config/local_qwen.yaml`, `test/model_gateway/test_structured_output.py` | Khóa đủ 12 trường bắt buộc (gồm `config_version`) và kiểm tra kiểu khi khởi tạo Gateway (`AC1`). |
| FR6.3 | Chưa | — | `fallback_locked = true`. |
| FR6.4 | Một phần | `model_gateway/llm_gateway.py`, `test/model_gateway/test_structured_output.py`, `test/schemas/test_contracts.py` | Gateway đã phân tách `LLM_UNAVAILABLE` (503) / `LLM_TIMEOUT` (504) (`retryable=True`) với lỗi parse/citation đi qua Gate; còn chờ API layer (Dev 5) nối HTTP 503/504 trên `testing`. |
| FR6.5 | Chưa | — | |
| FR6.6 | Có | `test/test_p45_prompt_gateway.py`, `test/model_gateway/test_structured_output.py`, `test/model_gateway/test_run_metadata.py` | Giữ `None` khi thiếu token/duration (`AC2`). |
| FR6.7 | Có | Manifest các lượt official | |
| FR6.8 | Có | Manifest (`provider: ollama`) | |

## FR7. Phiên và lịch sử

| Mã | Trạng thái | Ghi chú |
| --- | --- | --- |
| FR7.1–FR7.4 | Chưa | Batch có `query_id`; `AskRequest` nhận `session_id` nhưng chưa có session; `AskResponse.session_id` để sau (SRS mục 5.6). |

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
| FR9.9 | Chưa | — | `LogEvent` có trong contract (9 stage, `confidence` ở `week10_v1.1`); chưa có `monitoring/` trên `testing`. |
| FR9.10 | Chưa | — | |
| FR9.11 | Chưa | — | |

## Ánh xạ BRD → SRS (Phân hệ Tóm tắt bản án)

| Mã BRD | Nội dung ngắn | Mã SRS ánh xạ | Ghi chú kiểm chứng |
| --- | --- | --- | --- |
| BO-JS-01 | Tự động hóa tóm tắt bản án qua API & Streamlit UI, không hồi quy Q&A | FR10.1, FR10.8 | `POST /api/v1/summarize`, tab Streamlit, CI hồi quy Q&A |
| BO-JS-02 | Giảm ≥ 40% thời gian trích xuất 5 nhóm thông tin cốt lõi | FR10.5, FR10.8 | Usability Test so sánh bản tóm tắt 5 trường với toàn văn |
| BO-JS-03 | Factual Accuracy (Atomic Claim Precision) ≥ 90% kèm Acceptance Rate | FR10.4, FR10.5, FR10.6, NFR10.1 | Đo trên Test 20 bản án freeze |
| BO-JS-04 | Critical-fact Omission Rate < 10% | FR10.4, FR10.6, NFR10.1 | Đo trên Test 20 bản án freeze |
| BO-JS-05 | Expert Quality Score ≥ 4,0 / 5,0 (không đạt nếu sai/thiếu quyết định chính) | FR10.5, FR10.6, NFR10.1 | Chấm chuyên môn trên 20 bản án Test |
| BO-JS-06 | Decision Accuracy = 100% và Decision Coverage = 100% | FR10.2, FR10.6, FR10.7, NFR10.1 | Bảo vệ `DECISION`, `Decision Inventory`, `ReleaseGate` |
| BO-JS-07 | 100% mục `PRESENT` có `source_refs` đúng tới `paragraph_id` gốc | FR10.1, FR10.4, FR10.5, FR10.6 | Kiểm tra tất cả `PASS`/`PASS_WITH_WARNINGS` |
| BO-JS-08 | 0 rò rỉ PII/nội dung bản án trong log; 100% test Q&A PASS | FR10.8, NFR10.2, NFR10.3 | Bộ test che PII & CI Q&A |
| BR-JS-09 | Không lưu tệp mặc định, không log PII; ẩn danh hóa PII 30 bản án benchmark | FR10.1, NFR10.3 | Kiểm tra `data/judgment_benchmark/` & log JSONL |
| BR-JS-11 | Khóa ranh giới Dev (10) / Test (20) bằng SHA-256; cấm dùng output LLM thô làm ground truth / tune trên Test | NFR10.1, NFR10.4 | Manifest `dataset_sha256` & test chống rò rỉ |

## FR10. Tóm tắt bản án pháp luật

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| FR10.1 | Chưa | — | Chờ `week12_v1.0` (`ParsedDocument`) và `summarization/parser.py` (tách riêng kiểm tra `%PDF-` cho PDF và UTF-8 BOM/non-BOM cho TXT). |
| FR10.2 | Chưa | — | Chờ `SectionedDocument` (`protected=true` cho `DECISION`) và `summarization/section_identifier.py`. |
| FR10.3 | Chưa | — | Chờ `ContextPlan` và `summarization/context_planner.py`. |
| FR10.4 | Chưa | — | Chờ `FactLedger`, profile `family_judgment_v1` và `summarization/fact_extractor.py`. |
| FR10.5 | Chưa | — | Chờ `StructuredSummary`, prompt `judgment_summary_v1` và `summarization/structured_summarizer.py`. |
| FR10.6 | Chưa | — | Chờ `VerificationReport` và `summarization/checklist_qa.py`. |
| FR10.7 | Chưa | — | Chờ `summarization/release_gate.py`, `summarization/repair.py` và kết quả `SUMMARY_QA_FAILED` (HTTP 200). |
| FR10.8 | Chưa | — | Chờ `SummarizationResponse`, endpoint `POST /api/v1/summarize`, đồng bộ `api/openapi.json` và tab Streamlit UI. |

## IR. Giao diện

| Mã | Trạng thái | Ghi chú |
| --- | --- | --- |
| IR1.1–IR1.7 | Chưa | UI Streamlit ở PR #51 (`sprint10/UI`), chưa merge. |
| IR2.1–IR2.5 | Chưa | `AskRequest`/`AskResponse` có (`test/schemas/test_contracts.py`); `api/` ở PR #55, chưa merge. |
| IR3.1 | Chưa | Chưa có `scripts/run_rag_cli.py`. |
| IR3.2 | Có | `scripts/run_rag_batch.py`, `test/evaluation/test_run_rag_batch.py` |
| IR4.1 | Một phần | `orchestration/rag_pipeline.py` inject nguồn ứng viên và generator; model contract chung ở `schemas/models.py`; router, validator, logger chưa qua interface. |

## NFR

| Mã | Trạng thái | Bằng chứng | Ghi chú |
| --- | --- | --- | --- |
| NFR1.1 | Chưa | — | Chờ chấm mù. |
| NFR1.2 | Có | `docs/baseline_report.md` | |
| NFR1.3 | Có | `test/orchestration/test_record_abstention_latency.py` | |
| NFR2.1 | Chưa | — | Cần SSE. |
| NFR2.2 | Chưa | — | |
| NFR2.3 | Một phần | `results_metrics.json`, `model_gateway/run_metadata.py`, `test/model_gateway/test_run_metadata.py` | Manifest validator đã bắt buộc `hardware.{os,cpu,gpu,vram}`; các manifest lịch sử cũ chỉ có `platform`, chờ lượt đo mới trên máy tham chiếu. |
| NFR3.1 | Chưa | — | |
| NFR3.2 | Chưa | — | |
| NFR3.3 | Một phần | — | Chưa có quét secret tự động. |
| NFR3.4 | Chưa | — | |
| NFR3.5 | Chưa | — | |
| NFR4.1 | Có | `model_gateway/run_metadata.py`, `test/model_gateway/test_run_metadata.py` | Kiểm tra `working_tree_clean`, `temperature == 0`, cache tắt, fallback khóa khi `official=True`. |
| NFR4.2 | Có | `model_gateway/run_metadata.py`, `test/model_gateway/test_run_metadata.py` | Đã có `build_model_run_manifest` và `validate_run_manifest` kiểm đủ git/hashes/runtime/hardware (`os`, `cpu`, `gpu`, `vram`)/timestamps UTC. |
| NFR4.3 | Có | `model_gateway/run_metadata.py`, `test/model_gateway/test_run_metadata.py` | Bắt buộc SHA-256 cho `retrieval`, `rerank`, `model`, `threshold`. |
| NFR5.1 | Có | `test/test_dense_retriever.py`, `test/test_bm25_retrieval.py` | |
| NFR5.2 | Có | `deployment/qdrant/docker-compose.qdrant.yml` | |
| NFR6.1 | Có | `.github/workflows/tests.yml` | |
| NFR6.2 | Chưa | — | |
| NFR6.3 | Một phần | `test/orchestration/conftest.py` | Router, logger chưa có mock interface. |
| NFR7.1–NFR7.3 | Chưa | — | |
| NFR8.1 | Chưa | — | |
| NFR10.1 | Chưa | — | Đo `Factual Accuracy` ($FA \ge 90\%$ micro-average + macro-average, hợp nhất không trùng `Factual Consistency`) kèm `Acceptance Rate` ($AR = 0\% \Rightarrow \text{FAIL}$), `Critical-fact Omission Rate` ($CFO < 10\%$ trên toàn bộ $N_{\text{total}}$), `Decision Accuracy`/`Coverage` (100%) và `Expert Quality` theo rubric 5 tiêu chí + Hard Gate. |
| NFR10.2 | Chưa | — | Chờ giới hạn token budget, `max_llm_calls`, timeout và stage `summarization_*` trong `LogEvent`. |
| NFR10.3 | Chưa | — | Chờ `data/judgment_benchmark/` ẩn danh PII toàn bộ 30 bản án (`BR-JS-09`) và kiểm thử không log PII. |
| NFR10.4 | Chưa | — | Chờ mở rộng `validate_run_manifest()` theo nhánh `task_type = "legal_judgment_summarization"` trong `model_gateway/run_metadata.py` (kiểm tra `official=True`: `temperature == 0.0`, `max_retries <= 1`, `max_repair_attempts <= 1`, `allow_model_fallback: false`, `profile_sha256`, `dataset_sha256` cùng provenance chuẩn `git_*`/`runtime`/`hardware`/`config_hashes`). |
