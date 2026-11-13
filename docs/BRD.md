# TÀI LIỆU ĐẶC TẢ YÊU CẦU NGHIỆP VỤ (BUSINESS REQUIREMENTS DOCUMENT - BRD)

## DỰ ÁN: HỆ THỐNG TRỢ LÝ PHÁP LÝ THÔNG MINH VIỆT NAM (VIETNAM LEGAL RAG ASSISTANT)

| Thuộc tính Tài liệu | Chi tiết |
| :--- | :--- |
| **Mã tài liệu** | `VN-LEGAL-RAG-BRD-2026` |
| **Phiên bản** | `v2.0 (Codebase-Aligned Baseline: Sprint 9 / Run B Post-fix & Tuần 10 Roadmap)` |
| **Ngày cập nhật** | `13/11/2026` |
| **Chuẩn áp dụng** | `BABOK v3 (Business Analysis Body of Knowledge)` |
| **Tham chiếu mã nguồn** | `origin/docs` (`cdca079`) & `results/run-b-20261110` (`d7b0d1b` / `9c77dd8`) |
| **Lĩnh vực pháp lý trọng tâm** | `Pháp luật Hôn nhân và Gia đình Việt Nam (1986 – 2026)` |
| **Đội ngũ thực hiện** | `05 Kỹ sư AI & Hệ thống (Dev 1 – Dev 5), Tech Lead & 02 Chuyên gia Đánh giá Độc lập` |

---

## 1. Tóm tắt Điều hành (Executive Summary)

**Vietnam Legal RAG Assistant** là hệ thống trợ lý hỏi - đáp pháp luật chuyên sâu về lĩnh vực **Hôn nhân và Gia đình Việt Nam**, được xây dựng dựa trên kiến trúc **Retrieval-Augmented Generation (RAG)** kết hợp với cơ chế kiểm duyệt căn cứ xác định (**Deterministic Grounding Gate**).

Hệ thống giải quyết bài toán cốt lõi của các mô hình ngôn ngữ lớn (LLM) truyền thống khi áp dụng vào lĩnh vực pháp lý Việt Nam: **hiện tượng ảo giác pháp lý (Legal Hallucination)**, rò rỉ tri thức tiền huấn luyện từ luật nước ngoài (đặc biệt là luật Trung Quốc trên mô hình nền Qwen2.5), trích dẫn sai điều khoản, hoặc áp dụng nhầm các văn bản quy phạm pháp luật đã hết hiệu lực tại thời điểm xảy ra sự kiện pháp lý.

Tài liệu này phân định rạch ròi hai giai đoạn thực thi:
1. **Giai đoạn 1 – Lát cắt dọc Cốt lõi (Implemented Baseline – Sprint 9 / Run B):** Toàn bộ đường ống xử lý dữ liệu, truy xuất lai, reranking, khôi phục ngữ cảnh cha, mô hình Qwen2.5:7b, bộ kiểm duyệt trích dẫn xác định và công cụ chạy lô đánh giá tự động (`scripts/run_rag_batch.py`) đã hoàn thiện và kiểm chứng thực tế trên 30 câu Dev official.
2. **Giai đoạn 2 – Tích hợp Đầu cuối, Đánh giá Mù & Giao diện (Planned Roadmap – Tuần 10):** Nối `rule_router.py` vào `rag_pipeline.py`, tổ chức chấm mù đối chuẩn A/B 60 câu giữa Run A và Run B, đóng gói dịch vụ REST API (FastAPI), giao diện Web UI (Streamlit), CLI hỏi đáp đơn lẻ (`scripts/run_rag_cli.py`) và mô-đun giám sát/ẩn danh dữ liệu cá nhân (`monitoring/`).

---

## 2. Bối cảnh & Vấn đề Nghiệp vụ (Business Background & Problem Statement)

### 2.1. Hiện trạng (As-Is Situation)
1. **Tra cứu thủ công phức tạp và phân mảnh:** Người dân, sinh viên luật và chuyên viên pháp lý khi tra cứu quy định về Hôn nhân & Gia đình phải đối chiếu chéo giữa Luật gốc (Luật HNGĐ 1986, 2000, 2014), Luật sửa đổi (Luật Tổ chức TAND sửa đổi 2025), cùng hàng chục Nghị định (NĐ 126/2014, NĐ 123/2015, NĐ 207/2025...), Thông tư và Nghị quyết hướng dẫn (NQ 01/2024/NQ-HĐTP).
2. **Bẫy hiệu lực thời gian (Temporal Validity Trap):** Một văn bản hoặc điều khoản có thể đã hết hiệu lực ở hiện tại (ví dụ: Luật HNGĐ 2000 hoặc Điều 19–50 Nghị định 126/2014/NĐ-CP bị bãi bỏ bởi Nghị định 123/2015/NĐ-CP từ ngày `01/01/2016`), nhưng vẫn là căn cứ pháp lý đúng đắn duy nhất để giải quyết các tranh chấp/sự kiện xảy ra trong quá khứ trước ngày hết hiệu lực.
3. **Rủi ro từ các mô hình AI sinh văn bản tự do (Zero-shot LLM):** Các mô hình LLM đa dụng thường xuyên bịa đặt số hiệu điều khoản, nhầm lẫn quy định giữa luật cũ và luật mới (ví dụ: nhầm độ tuổi kết hôn của nam là *"bước sang tuổi 20"* theo Luật 2000 thay vì *"từ đủ 20 tuổi trở lên"* theo Luật 2014), hoặc trượt sang ngôn ngữ/luật Trung Quốc khi thiếu ràng buộc ngữ cảnh đóng.

### 2.2. Giải pháp kỳ vọng (To-Be Solution)
Xây dựng một hệ thống hỏi - đáp pháp luật có kiểm soát chặt chẽ theo nguyên tắc:
* **Strict Grounding (Không căn cứ – Không trả lời):** Mọi câu trả lời pháp lý phát ra bắt buộc phải dựa trên các phân mảnh văn bản luật có thật trong kho dữ liệu đã được kiểm định.
* **Temporal Accuracy (Chính xác theo dòng thời gian):** Tự động lọc các văn bản/điều khoản có hiệu lực tại đúng mốc thời gian (`as_of_date`) của câu hỏi.
* **Traceability (Khả năng truy nguyên toàn diện):** Lưu vết toàn bộ đường đi của bằng chứng từ `chunk_id`, `article_id`, `clause_id`, `parent_clause_id` đến câu trả lời cuối cùng.

---

## 3. Mục tiêu Kinh doanh & Chỉ số Đo lường Thành công (Business Objectives & KPIs)

| Mã Mục tiêu | Mô tả Mục tiêu Nghiệp vụ | Chỉ số Đo lường (KPI / Target Metric) | Trạng thái & Phương pháp Kiểm chứng |
| :--- | :--- | :--- | :--- |
| **BO-01** | Đảm bảo chất lượng tìm kiếm và xếp hạng đúng điều khoản pháp luật liên quan trong Top-5 kết quả đầu ra. | - **Recall@5 (Dev Hybrid+Rerank):** $\ge 0.7335$ (hướng tới $\ge 0.85$ ở giai đoạn tối ưu tiếp theo)<br>- **MRR@10 (Breadcrumb text):** $\ge 0.7480$ | **Đã đạt:** Đo lường tự động trên tập Dev Gold (75 câu) từ kho **28 văn bản / 2.322 chunks**. |
| **BO-02** | Nâng cao độ chính xác pháp lý (Legal Correctness) và độ bám sát ngữ cảnh (Context Faithfulness) vượt trội so với Zero-shot LLM. | - **Legal Correctness:** Điểm trung bình $\ge 4.2 / 5.0$<br>- Cải thiện có ý nghĩa thống kê ($B - A > 0$) so với Baseline Zero-shot. | **Kế hoạch chấm mù (Tuần 10):** Đánh giá mù (Blind Scoring) 60 câu (30 Run A + 30 Run B) bởi 02 chuyên gia độc lập, mở rộng từ khung `evaluation/rubrics/zero_shot_rubric_guide_v1.md`. |
| **BO-03** | Triệt tiêu hoàn toàn hiện tượng trích dẫn khống (Citation Hallucination) và rò rỉ ngôn ngữ nước ngoài sau cổng kiểm duyệt. | - **Post-Gate Invalid Citation Rate:** $0\%$<br>- **CJK / Chinese Law Leakage:** $0$ ký tự CJK trên toàn bộ tập đánh giá. | **Đã đạt (Run B Post-fix):** Kiểm chứng qua `validate_citations()` và Grounding Gate (`PASS: 28, ABSTAIN: 1, NEEDS_CLARIFICATION: 1, FAIL: 0`). |
| **BO-04** | Ngăn chặn việc tư vấn sai lĩnh vực hoặc trả lời khi câu hỏi thiếu căn cứ trong kho dữ liệu. | - **Out-of-Scope / Negative Rejection Rate:** $\ge 90\%$ trên tập câu hỏi âm (`dev_negative_queries_v2.jsonl` – 26 câu). | **Đã đạt:** Hiệu chỉnh ngưỡng tin cậy tại `reranking/confidence.yaml` (`conf_v1_20261109`) trên tập câu âm v2 (`26 câu`). |
| **BO-05** | Đảm bảo khả năng vận hành ổn định trên GPU cục bộ và minh bạch trách nhiệm pháp lý. | - **100% phản hồi** hiển thị câu khuyến cáo pháp lý (Legal Disclaimer).<br>- **Latency p50 (Precomputed, RTX 4060):** $\le 10\text{s}$/câu (thực tế đạt `4.70s`/câu). | **Đã đạt (Batch):** Kiểm thử thực tế 30/30 câu qua `scripts/run_rag_batch.py`. Giao diện Web/API mở rộng ở Tuần 10. |

---

## 4. Các Bên Liên Quan & Chân Dung Người Dùng (Stakeholders & User Personas)

### 4.1. Các bên liên quan (Stakeholders)
* **Ban Quản lý Dự án / Hội đồng Nghiệm thu (Project Sponsors / Evaluators):** Giám sát chất lượng học thuật, tính toàn vẹn của dữ liệu kiểm thử và độ tin cậy của báo cáo so sánh A/B.
* **Chuyên gia Kiểm định Pháp lý (Legal Reviewers / Raters):** Đối chiếu toàn văn từng Khoản luật trong bộ 105 câu Gold và thực hiện chấm điểm mù (Blind Scoring) theo Rubric.
* **Đội ngũ Kỹ sư Phát triển (Dev 1 – Dev 5 & Tech Lead):** Chịu trách nhiệm thiết kế kiến trúc, xử lý dữ liệu, tích hợp mô hình và vận hành hệ thống.

### 4.2. Chân dung người dùng mục tiêu (User Personas)
1. **Người dân tra cứu pháp luật (End-User / Citizen – Mục tiêu Web UI Tuần 10):**
   * *Nhu cầu:* Hỏi các tình huống thực tế (độ tuổi kết hôn, chia tài sản chung/riêng khi ly hôn, quyền nuôi con dưới 36 tháng tuổi...) bằng ngôn ngữ đời thường.
   * *Điểm đau (Pain point):* Không biết tên văn bản hay số điều luật; dễ bị nhầm lẫn bởi các bài viết hết hiệu lực trên mạng.
2. **Chuyên viên Pháp lý / Sinh viên Luật (Legal Researcher):**
   * *Nhu cầu:* Tra cứu nhanh quy định pháp luật gắn với một mốc thời gian lịch sử cụ thể (ví dụ: sự kiện kết hôn năm 2010 áp dụng Luật HNGĐ 2000 hay Luật 2014) và cần trích dẫn chính xác đến cấp Điều, Khoản, Điểm.
3. **Kỹ sư Đánh giá & Vận hành Hệ thống (AI Engineer / QA – Đối tượng chính của Release hiện tại):**
   * *Nhu cầu:* Chạy thực nghiệm hàng loạt (Batch Evaluation) qua `scripts/run_rag_batch.py`, truy vết `run_manifest.json` và `results.jsonl`, kiểm tra độ trễ, lượng token tiêu thụ và trạng thái từ chối (`ABSTAIN`).

---

## 5. Phạm vi Dự án & Lộ trình Phân kỳ (Project Scope & Phased Delivery)

Phạm vi dự án được phân tách rạch ròi giữa **Phần đã hoàn thiện trên Baseline hiện tại** và **Phần kế hoạch triển khai ở Tuần 10**:

| Phân loại | Đã Triển Khai & Kiểm Chứng (Implemented Baseline) | Kế Hoạch Triển Khai Tiếp Theo (Planned – Tuần 10+) |
| :--- | :--- | :--- |
| **Dữ liệu & Lĩnh vực** | - Kho ngữ liệu chuẩn hóa gồm **28 văn bản pháp luật** chuyên ngành Hôn nhân & Gia đình và Hộ tịch liên quan (**2.322 Child Chunks** và **1.079 Parent Records**).<br>- Bộ Benchmark **105 câu Gold** đã duyệt toàn văn (`75 Dev Gold`, `30 Test Gold` đóng băng SHA-256).<br>- Tập câu hỏi âm **26 câu** (`dev_negative_queries_v2.jsonl` kèm `dev_negative_manifest_v2.json`). | - Mở rộng sang các lĩnh vực pháp luật khác ngoài Hôn nhân & Gia đình (Hình sự, Đất đai, Thuế, Doanh nghiệp...).<br>- Bổ sung quy trình tự động cập nhật văn bản hợp nhất/sửa đổi mới. |
| **Xử lý Truy vấn & Truy xuất** | - **Rule Router (`agent/router/rule_router.py`):** Đã phát triển độc lập phân loại 5 trạng thái `Route` (`LEGAL_HNGD`, `LEGAL_OUT_OF_SCOPE`, `NON_LEGAL`, `MIXED_LEGAL_SCOPE`, `LEGAL_SCOPE_UNCERTAIN`).<br>- **Temporal Pre-filter (`retrieval/temporal.py`):** Lọc theo khoảng hiệu lực $[\text{effective\_from}, \text{effective\_to})$ tại `as_of_date`.<br>- **Hybrid Search:** Elasticsearch BM25 (`bm25-e6-verified-20261101`) + Qdrant Dense (`BAAI/bge-m3`) hợp nhất qua RRF ($k=60$) lấy Top-50.<br>- **Reranking & Context:** Cross-Encoder (`bge-reranker-v2-m3`) lấy Top-5 + Confidence Threshold (`reranking/confidence.yaml`) + Parent-Context Resolver (tối đa 6.000 ký tự). | - **Tích hợp Router vào Pipeline:** Nối trực tiếp `rule_router.py` vào luồng chính `orchestration/rag_pipeline.py` (hiện đang chạy độc lập).<br>- Mở rộng truy vấn bằng LLM (HyDE) và đa dạng hóa bằng MMR. |
| **Sinh văn bản & Kiểm duyệt** | - **Prompt Builder (`generation/prompt_builder.py`):** Đánh số bằng chứng `[1]..[5]`, khóa phiên bản (`v1.0_*_m1` trên `cdca079` và `v1.1_*` chống rò rỉ luật Trung Quốc trên `results/run-b-20261110`).<br>- **Model Gateway (`model_gateway/llm_gateway.py`):** Tích hợp `qwen2.5:7b` qua Ollama (`num_ctx=8192`, `num_predict=1024`, Structured JSON Output).<br>- **Deterministic Grounding Gate (`grounding/citation_validator.py`):** Kiểm tra trích dẫn qua `validate_citations()` và chặn ký tự CJK (`count_cjk_chars()`). | - **Đánh giá mù A/B (Blind Scoring):** Tổ chức chấm mù 60 câu trả lời giữa Run A (Zero-shot) và Run B (Controlled RAG) bởi 2 chuyên gia độc lập.<br>- Ma trận chuyển đổi dự phòng 3 tầng (Multi-tier LLM Fallback) và NLI/LLM-Judge. |
| **Giao diện & Hạ tầng** | - Công cụ chạy thực nghiệm hàng loạt **Batch Runner (`scripts/run_rag_batch.py`)** xuất `results.jsonl`, `errors.jsonl`, `run_manifest.json` kèm cơ chế `--require-clean-checkout` và `--resume`.<br>- Bộ kiểm thử tự động toàn diện (**1.352 tests** thu thập bởi pytest; `1.351 passed, 1 skipped`). | - **CLI hỏi đáp đơn lẻ:** `scripts/run_rag_cli.py` (kèm `test/e2e/test_rag_cli.py`).<br>- **Backend API FastAPI:** `api/main.py` & `api/routes/ask.py` (`POST /ask`, xác thực `X-API-Key`, SSE, OpenAPI `/docs`).<br>- **Web UI Streamlit:** `frontend/streamlit_app.py` (kèm Evidence Panel & Date Picker).<br>- **Giám sát & PII Masking:** `monitoring/pii_masker.py` & `monitoring/structured_logger.py` (Task D1.3). |

---

## 6. Quy trình Nghiệp vụ Cốt lõi (Core Business Workflows)

```
+---------------------------------------------------------------------------------------------------+
|                        LUỒNG NGHIỆP VỤ XỬ LÝ TRUY VẤN PHÁP LÝ (IMPLEMENTED PIPELINE)              |
+---------------------------------------------------------------------------------------------------+

[Batch Runner (run_rag_batch.py) / CLI & API (Tuần 10)]
       |
       v  (1) Nhập câu hỏi + Mốc thời gian tra cứu (as_of_date)
[Input Validator] ---> (Nếu câu hỏi rỗng "") ---> [Báo lỗi ValueError]
       |
       v  (2) Câu hỏi hợp lệ (Ghi chú: rule_router.py hiện độc lập, sẽ nối vào pipeline ở Tuần 10)
[Xác định as_of_date (Benchmark > Câu hỏi > UI > Hôm nay)]
       |
       v  (3) Lọc hiệu lực thời gian: effective_from <= as_of_date < effective_to
[Truy xuất lai (BM25 + Qdrant BGE-M3) & Hợp nhất RRF (Top-50) / Precomputed Retrieval]
       |
       v  (4) Xếp hạng lại (bge-reranker-v2-m3 -> Top-5) & Kiểm tra ngưỡng (reranking/confidence.yaml)
       |
       +---> (Nếu Rỗng hoặc top1_score < 0.5) ------> [ABSTAIN (LOW_CONFIDENCE / EMPTY_RETRIEVAL)]
       |                                                                     |
       v  (5) Đạt ngưỡng tin cậy                                             |
[Parent-Context Resolver & Context Aggregator]                               |
(Mở rộng Khoản cha <= 6.000 ký tự, đánh số bằng chứng [1]..[5])              |
       |                                                                     |
       v  (6) Đóng gói ContextPayload + Prompt (v1.1_controlled_rag)         |
[Qwen2.5:7b Model Gateway (Structured JSON Output)]                          |
(Sinh câu trả lời vào bộ đệm Buffer + mảng evidence_indices)                 |
       |                                                                     |
       v  (7) Ánh xạ ngược [1]..[5] -> chunk_id, Điều, Khoản, Parent         |
[Deterministic Grounding Gate (validate_citations & count_cjk_chars)]        |
       |                                                                     |
       +---> (Nếu FAIL: Trích dẫn ngoài context / dính CJK) -> [Chặn & Chuyển sang FAIL/ABSTAIN]
       |                                                                     |
       v  (Nếu PASS: 100% trích dẫn hợp lệ)                                  |
[Đóng gói Envelope results.jsonl (status, query_id, as_of_date, result) + Disclaimer] <---+
```

---

## 7. Ràng buộc Kinh doanh, Pháp lý & Quản trị Rủi ro (Constraints, Compliance & Risk Management)

### 7.1. Ràng buộc Pháp lý & Tuân thủ (Legal & Regulatory Compliance)
1. **Giới hạn trách nhiệm tư vấn (Legal Disclaimer):** Mọi đầu ra của hệ thống, bất kể thuộc nhánh trả lời nào, đều bắt buộc đính kèm thông điệp cố định:
   > *"Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."*
2. **Bảo vệ dữ liệu cá nhân (Privacy & Data Protection):** Tuân thủ nguyên tắc bảo mật theo **Nghị định 13/2023/NĐ-CP** và **Luật Bảo vệ dữ liệu cá nhân 2025**:
   * Các lượt đánh giá hiện tại sử dụng tập dữ liệu chuẩn hóa ẩn danh (`queries_dev.json`).
   * Trước khi mở cổng API/Web UI cho người dùng thật ở Tuần 10, bắt buộc hoàn thiện và kích hoạt mô-đun `monitoring/pii_masker.py` (Task D1.3) để che giấu thông tin định danh cá nhân (Số điện thoại, Email, CCCD/CMND) trước khi ghi log hoặc gửi ra dịch vụ bên ngoài.

### 7.2. Ràng buộc Vận hành & Phần cứng (Operational Constraints)
* **Giới hạn phần cứng cục bộ:** Hệ thống được kiểm chứng vận hành ổn định trên máy trạm có **GPU 4 GB – 8 GB VRAM (RTX 3050 Ti / RTX 4060)** và 16 GB RAM, hỗ trợ cơ chế chạy hai bước (`PrecomputedRetriever`) để tách biệt tài nguyên giữa bước truy xuất và bước sinh văn bản.
* **Chế độ Buffer-then-stream:** Toàn bộ câu trả lời của LLM được giữ trong bộ đệm cho đến khi `validate_citations()` kiểm duyệt đạt chuẩn (`PASS`) mới được phát ra.

### 7.3. Ma trận Quản trị Rủi ro Nghiệp vụ (Business Risk Register)

| Mã Rủi ro | Mô tả Rủi ro Nghiệp vụ | Mức độ Ảnh hưởng | Biện pháp Kiểm soát & Giảm thiểu |
| :--- | :--- | :---: | :--- |
| **BR-01** | Người dùng hỏi về các điều khoản đã bị sửa đổi/bãi bỏ một phần (như Điều 19–50 NĐ 126/2014). | Cao | Áp dụng bộ lọc thời điểm `as_of_date`, cập nhật trạng thái hiệu lực cấp Điều/Khoản (`provision_status`) và chuyển hướng sang văn bản thay thế (Điều 45 NĐ 123/2015). |
| **BR-02** | Mô hình nền `qwen2.5:7b` rò rỉ kiến thức luật Trung Quốc hoặc sinh ký tự Hán khi thiếu ngữ cảnh. | Rất cao | Nâng cấp Prompt `v1.1_controlled_rag` cấm tuyệt đối luật nước ngoài, kết hợp kiểm tra ký tự CJK (`count_cjk_chars()`) tại Grounding Gate (đã giảm lỗi CJK về `0` trên toàn bộ 30 câu). |
| **BR-03** | Rò rỉ dữ liệu kiểm thử (Data Leakage) giữa tập phát triển (Dev) và tập kiểm thử độc lập (Test Holdout). | Cao | Đóng băng kép bằng mã băm SHA-256 (`freeze_test.py`, `freeze_gold.py`) và kiểm tra tự động qua `test/evaluation/test_dev30_no_test_leakage.py`. |
| **BR-04** | Thiên kiến chủ quan của người chấm trong quá trình đánh giá chất lượng câu trả lời giữa Zero-shot và RAG. | Trung bình | Áp dụng quy trình Chấm mù (Blind Scoring) 60 câu giữa Run A và Run B ở Tuần 10 (mở rộng từ hướng dẫn `evaluation/rubrics/zero_shot_rubric_guide_v1.md`): ẩn nhãn nguồn `A/B`, trộn ngẫu nhiên thứ tự và đo độ đồng thuận Cohen's Kappa ($\kappa$). |
