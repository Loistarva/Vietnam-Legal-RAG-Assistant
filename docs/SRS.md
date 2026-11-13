# TÀI LIỆU ĐẶC TẢ YÊU CẦU PHẦN MỀM (SOFTWARE REQUIREMENTS SPECIFICATION - SRS)

## DỰ ÁN: HỆ THỐNG TRỢ LÝ PHÁP LÝ THÔNG MINH VIỆT NAM (VIETNAM LEGAL RAG ASSISTANT)

| Thuộc tính Tài liệu | Chi tiết |
| :--- | :--- |
| **Mã tài liệu** | `VN-LEGAL-RAG-SRS-2026` |
| **Phiên bản** | `v2.0 (Codebase-Aligned Baseline: Sprint 9 / Run B Post-fix & Tuần 10 Roadmap)` |
| **Ngày cập nhật** | `13/11/2026` |
| **Chuẩn áp dụng** | `ISO/IEC/IEEE 29148 & IEEE Std 830` |
| **Tham chiếu mã nguồn** | `origin/docs` (`cdca079`) & `results/run-b-20261110` (`d7b0d1b` / `9c77dd8`) |
| **Ngôn ngữ & Nền tảng** | `Python 3.11+ / Qdrant / Elasticsearch 9.5.3 / Ollama (Qwen2.5:7b) / FastAPI & Streamlit (Tuần 10)` |
| **Đội ngũ phát triển** | `05 Kỹ sư AI & Hệ thống (Dev 1 – Dev 5) & Tech Lead` |

---

## 1. Giới thiệu & Kiến trúc Tổng thể Hệ thống (Introduction & System Architecture)

### 1.1. Mục đích Tài liệu
Tài liệu **SRS (Software Requirements Specification)** này đặc tả chính xác kiến trúc phần mềm, cấu trúc dữ liệu kho ngữ liệu (`28 văn bản / 2.322 chunks / 1.079 parents`), hợp đồng dữ liệu runtime (`schemas/models.py`), đặc tả kỹ thuật của từng mô-đun chức năng (`FR-01` đến `FR-09`), các ràng buộc phi chức năng (`NFR-01` đến `NFR-05`) và ma trận truy vết kiểm thử của hệ thống **Vietnam Legal RAG Assistant**.

### 1.2. Kiến trúc Phân tầng (Layered Architecture)
Hệ thống được thiết kế theo kiến trúc phân tầng mô-đun hóa, giao tiếp hoàn toàn qua các hợp đồng dữ liệu nghiêm ngặt (**Canonical Pydantic Schemas**):

1. **Tầng Giao tiếp & Thực thi Lô (Execution & Presentation Layer):**
   * *Đã triển khai (`Implemented`):* `scripts/run_rag_batch.py` (Batch Runner chạy thực nghiệm hàng loạt, hỗ trợ `--require-clean-checkout` và `--resume`).
   * *Kế hoạch Tuần 10 (`Planned`):* `scripts/run_rag_cli.py` (CLI hỏi đáp đơn lẻ), `api/main.py` & `api/routes/ask.py` (REST API FastAPI + SSE), và `frontend/streamlit_app.py` (Web UI Streamlit kèm Evidence Panel).
2. **Tầng Định tuyến & Điều phối Nghiệp vụ (Orchestration & Routing Layer):**
   * `agent/router/rule_router.py`: Bộ phân luồng truy vấn nhanh (Fast-path Rule Router) dựa trên từ khóa/quy tắc thành 5 trạng thái `Route` mà không cần gọi LLM *(hiện hoạt động độc lập, việc nối vào `rag_pipeline.py` nằm trong kế hoạch tích hợp Tuần 10)*.
   * `orchestration/rag_pipeline.py`: Bộ điều phối trung tâm kết nối xuyên suốt từ khâu nhận truy vấn đến khâu kiểm duyệt đầu ra và đóng gói `RAGOutputRecord`.
3. **Tầng Truy xuất, Lọc Thời điểm & Xếp hạng (Retrieval & Reranking Layer):**
   * `retrieval/temporal.py`: Module chuẩn hóa và kiểm tra khoảng hiệu lực thời gian (`is_effective_at`, `normalize_as_of_date`).
   * `retrieval/hybrid_retriever.py`: Kết hợp `ElasticsearchBM25Retriever` (tìm kiếm từ khóa tách từ) và `DenseRetriever` (tìm kiếm ngữ nghĩa trên Qdrant) qua thuật toán hợp nhất RRF.
   * `reranking/pipeline.py`, `reranking/parent_context.py` & `reranking/confidence.yaml`: Xếp hạng lại bằng Cross-Encoder, lọc theo ngưỡng tin cậy độc lập (`conf_v1_20261109`) và khôi phục ngữ cảnh Khoản cha.
4. **Tầng Sinh Văn bản & Kiểm duyệt Căn cứ (Generation & Grounding Layer):**
   * `generation/prompt_builder.py` & `generation/prompts/legal_rag_prompt_v1_0.md`: Xây dựng Prompt A/B, đánh số bằng chứng `[1]..[5]` và ánh xạ ngược chỉ số trích dẫn.
   * `model_gateway/llm_gateway.py` & `model_gateway/config/local_qwen.yaml`: Cổng giao tiếp với mô hình `qwen2.5:7b` qua Ollama, ép kiểu đầu ra JSON Schema và ghi nhận siêu dữ liệu thực thi (Runtime Provenance).
   * `grounding/citation_validator.py`: Bộ kiểm tra trích dẫn xác định thông qua hàm mức module `validate_citations(...)` đóng vai trò chốt chặn tại Grounding Gate.
5. **Tầng Lưu trữ & Tiền xử lý Dữ liệu (Data & Storage Layer):**
   * `parser/` & `chunking/`: Bóc tách văn bản pháp luật từ PDF/HTML và phân mảnh theo cấu trúc cây 4 tầng (`Document` $\rightarrow$ `Article` $\rightarrow$ `Clause` $\rightarrow$ `Chunk`).
   * Kho ngữ liệu chuẩn hóa: `data/reference/document_versions.json` (**28 văn bản**), `data/chunking_output/chunks.jsonl` (**2.322 chunks**), và `data/chunking_output/parents.json` (**1.079 parent records**).
   * Cơ sở dữ liệu tìm kiếm: **Qdrant Vector Database** (Collection: `vietnam_legal_chunks`) & **Elasticsearch 9.5.3** (Index cấu hình trong `retrieval/config.yaml`: `bm25-e6-verified-20261101`).

---

## 2. Đặc tả Dữ liệu & Hợp đồng Giao tiếp (Data Contract & Canonical Schemas)

### 2.1. Kiến trúc Cây Dữ liệu Pháp lý 4 Tầng (4-Tier Legal Hierarchy)
Mọi văn bản quy phạm pháp luật trong hệ thống bắt buộc tuân thủ cấu trúc phân cấp 4 tầng và quy ước định danh chữ thường không dấu cho các thực thể pháp lý (`^[a-z0-9_]+$`):
* **Tầng 1 – Document (Văn bản):** Định danh chuẩn từ `data/reference/document_versions.json` (28 văn bản; ví dụ: `l_52_2014_qh13`, `nd_123_2015_nd_cp`, `nq_01_2024_nq_hdtp`).
* **Tầng 2 – Article (Điều luật):** Định danh `[document_id]_art_[số_điều]` (Ví dụ: `l_52_2014_qh13_art_8`).
* **Tầng 3 – Clause (Khoản luật / Parent Context):** Định danh `[article_id]_clause_[số_khoản]` (Ví dụ: `l_52_2014_qh13_art_8_clause_1`). Toàn bộ kho ngữ liệu hiện có **1.079 bản ghi cha** tại `data/chunking_output/parents.json`.
* **Tầng 4 – Chunk (Phân mảnh con / Điểm):** Định danh `[clause_id]_chunk_[idx]` (Ví dụ: `l_52_2014_qh13_art_8_clause_1_chunk_1`), với độ dài tối thiểu `minLength: 10` ký tự theo `schemas/chunk_payload_schema.json` và tối đa $\le 256$ tokens. Toàn bộ kho ngữ liệu hiện có **2.322 phân mảnh** tại `data/chunking_output/chunks.jsonl`.

### 2.2. Đặc tả Các Thực thể Runtime Cốt lõi (`schemas/models.py`)
Tệp `schemas/models.py` là nguồn sự thật duy nhất (Single Source of Truth) định nghĩa các Pydantic v2 Models và tự động xuất ra các tệp JSON Schema tương ứng trong thư mục `schemas/`:

#### A. Thực thể `CandidateChunk` (`schemas/candidate.schema.json`)
Đại diện cho một ứng viên phân mảnh thu được từ tầng Retrieval/Reranking:

| Trường dữ liệu | Kiểu dữ liệu | Bắt buộc | Ràng buộc & Mô tả kỹ thuật trong `schemas/models.py` |
| :--- | :--- | :---: | :--- |
| `query_id` | `str` | Có | Mã định danh truy vấn không rỗng (chấp nhận cả chữ hoa/thường như `"HN_001"`). |
| `chunk_id` | `str` | Có | Định danh duy nhất của Child Chunk (`min_length=1`). |
| `chunk_text` | `str` | Có | Nội dung nguyên gốc của phân mảnh dùng để hiển thị (`min_length=1` ở Pydantic; `minLength: 10` ở corpus JSON Schema). |
| `candidate_text` | `str \| None` | Không | Chuỗi kết hợp tên văn bản, breadcrumb và nội dung (`document_breadcrumb_chunk_text`). |
| `document_id` | `str` | Có | Mã văn bản pháp luật chứa phân mảnh. |
| `article_id` | `str` | Có | Mã Điều luật chứa phân mảnh. |
| `clause_id` | `str` | Có | Mã Khoản luật chứa phân mảnh. |
| `parent_clause_id` | `str \| None` | Không | Khóa ngoại trỏ về Khoản cha. |
| `parent_id` | `str \| None` | Không | Khóa ngoại trỏ về bản ghi Parent trong `parents.json`. |
| `parent_text` | `str \| None` | Không | Toàn văn nội dung Khoản cha sau khi qua `ParentContextResolver`. |
| `score` | `float` | Có | Điểm số xếp hạng cuối cùng của ứng viên. |
| `rank` | `int` | Có | Thứ hạng của ứng viên ($\ge 1$). |
| `retrieval_source` | `str` | Có | Nguồn truy xuất chính của ứng viên (ví dụ: `"hybrid"`, `"bm25"`, `"dense"`, `"precomputed"`). |
| `retrieval_sources` | `list[str]` | Không | Danh sách chi tiết các nhánh đóng góp (ví dụ: `["bm25", "dense"]`). |
| `rrf_score` | `float \| None` | Không | Điểm hợp nhất Reciprocal Rank Fusion. |
| `reranker_score` | `float \| None` | Không | Điểm của mô hình Cross-Encoder Reranker. |
| `validity_status` | `str` | Có | Enum: `["Còn hiệu lực", "Hết hiệu lực", "Sắp có hiệu lực", "Sửa đổi bổ sung", "Không xác định"]`. |
| `effective_from` | `str \| None` | Không | Ngày bắt đầu có hiệu lực (Định dạng chuẩn ISO `YYYY-MM-DD`). |
| `effective_to` | `str \| None` | Không | Ngày hết hiệu lực (Định dạng chuẩn ISO `YYYY-MM-DD` hoặc `None`). |
| `as_of_date` | `str` | Có | Mốc thời gian thực hiện truy vấn (Định dạng chuẩn ISO `YYYY-MM-DD`). |
| `evidence_index` | `int \| None` | Không | Chỉ số bằng chứng được gán trong khoảng `[1, 5]` khi đưa vào Prompt. |

#### B. Thực thể `ContextPayload` (`schemas/context_payload.schema.json`)
Đầu vào chuẩn hóa chuyển từ tầng Orchestration sang Prompt Builder và Citation Validator:
* `query_id: str`, `query: str`, `as_of_date: str` (chuẩn ISO `YYYY-MM-DD`).
* `as_of_date_source: Literal["benchmark", "query_text", "user_input", "system_today"]` (Bắt buộc khai báo tường minh, không dùng giá trị mặc định giả).
* `evidence_items: list[EvidenceItem]`: Danh sách từ 1 đến 5 mảnh bằng chứng đã khôi phục ngữ cảnh cha. Các chỉ số `evidence_index` bắt buộc phải là **duy nhất và liên tục từ $1..n$ ($1 \le n \le 5$)**. Mỗi `EvidenceItem` chứa đầy đủ nhãn đọc được: `document_title`, `document_number`, `breadcrumb`, `validity_status`, `effective_from`, `effective_to`, `content`.
* `source_map: dict[int, dict[str, Any]]`: Từ điển ánh xạ 1-1 từ `evidence_index` ($1..n$) sang bộ khóa định danh (`chunk_id`, `document_id`, `article_id`, `clause_id`).
* `max_context_chars: int = 6000` và `total_chars: int`: Tổng số ký tự của toàn bộ `evidence_items`. Validator bắt buộc kiểm tra `total_chars <= max_context_chars`.

#### C. Thực thể `StructuredRAGOutput`, `LLMResponse`, `LatencyBreakdown` & `RAGOutputRecord`
* **`StructuredRAGOutput` (Schema ép kiểu JSON của Ollama trong Run B – `schemas/llm_response.schema.json`):**
  ```json
  {
    "answer": "Chuỗi nội dung câu trả lời pháp lý hoặc thông báo từ chối...",
    "evidence_indices": [1, 3],
    "abstained": false,
    "abstention_reason": null,
    "needs_clarification": false
  }
  ```
* **`LLMResponse` (Đối tượng phản hồi kèm Runtime Provenance ở tầng Model Gateway):**
  Lưu giữ toàn bộ thông tin truy vết thời gian chạy: `query_id`, `run_mode`, `answer`, `evidence_indices`, `model` (`"qwen2.5:7b"`), `model_digest`, `ollama_version`, `prompt_version`, `prompt_hash`, `num_ctx` (`8192`), `num_predict` (`1024`), `temperature` (`0.0`), `repeat_penalty` (`1.0` trên `results/run-b-20261110`; `1.15` trên mốc Freeze `cdca079`), `done_reason`, `truncated` (`bool`), `context_truncated` (`bool` — chỉ nằm trên `LLMResponse`), `parse_status`, `latency_ms`, `token_usage`.
* **`LatencyBreakdown` (Đối tượng phân rã độ trễ 6 trường chuẩn trong `schemas/models.py`):**
  * `retrieval_ms: float | None` (bằng `null` khi chạy chế độ `precomputed`).
  * `llm_total_ms: float | None`
  * `ttft_model_ms: float | None`
  * `load_ms: float | None`
  * `prompt_eval_ms: float | None`
  * `eval_ms: float | None`
* **`RAGOutputRecord` (Bản ghi đầu ra chính thức của `orchestration/rag_pipeline.py`):**
  Bao gồm toàn bộ trường kết quả cuối cùng, thông tin trạng thái từ chối (`abstained: bool`, `abstention_reason: str | None`, `abstention_source: str | None`, `needs_clarification: bool`), số lượng cuộc gọi mô hình **`llm_calls: int`** (`1` khi gọi LLM, `0` khi ngắt sớm) và đối tượng **`latency_breakdown: LatencyBreakdown`**. Khi xuất ra tệp `results.jsonl` qua `scripts/run_rag_batch.py`, mỗi dòng được bọc trong envelope:
  `{"status": "SUCCESS", "query_id": "...", "as_of_date": "...", "result": <RAGOutputRecord>}`.

---

## 3. Đặc tả Yêu cầu Chức năng Chi tiết (Detailed Functional Requirements)

### FR-01: Tiền xử lý Truy vấn & Che giấu Thông tin Cá nhân (Input Validation & PII Masking)
* **Trạng thái triển khai:** Kiểm tra đầu vào rỗng đã triển khai; bộ che giấu PII (`monitoring/pii_masker.py`, Task D1.3) nằm trong lộ trình Tuần 10 trước khi mở API công cộng.
* **Module thực thi:** `retrieval/hybrid_retriever.py`, `reranking/pipeline.py`, `monitoring/pii_masker.py` *(Planned - Tuần 10)*.
* **Quy tắc xử lý (Processing Rules):**
  1. **Kiểm tra truy vấn rỗng (Issue E14):** Nếu `query` là `None`, chuỗi rỗng `""` hoặc chỉ chứa khoảng trắng (`query.strip() == ""`), hệ thống lập tức dừng xử lý (Fail-fast) và ném ngoại lệ `ValueError`.
  2. **Che giấu PII *(Planned - Tuần 10)*:** Phát hiện và thay thế số điện thoại, Email, số CMND/CCCD bằng nhãn `[REDACTED_*]` trước khi ghi xuống `monitoring/structured_logger.py` hoặc gửi tới dịch vụ bên ngoài.

### FR-02: Phân luồng Truy vấn 5 Trạng thái (Fast-Path Rule Router)
* **Trạng thái triển khai:** **Đã triển khai độc lập** tại `agent/router/rule_router.py` *(việc tích hợp nối vào luồng chính `orchestration/rag_pipeline.py` là bước tiếp theo ở Tuần 10)*.
* **Quy tắc xử lý:** Bộ định tuyến phân loại truy vấn dựa trên quy tắc/từ khóa (không gọi LLM) theo enum **`Route`** gồm 5 giá trị chính thức và ánh xạ sang `Action` tương ứng:
  1. **`Route.LEGAL_HNGD` $\rightarrow$ `Action.LEGAL_RETRIEVAL`:** Câu hỏi pháp lý thuộc phạm vi Hôn nhân và Gia đình $\rightarrow$ Đi tiếp vào bước lọc thời gian và truy xuất Hybrid RAG.
  2. **`Route.LEGAL_SCOPE_UNCERTAIN` $\rightarrow$ `Action.LEGAL_RETRIEVAL`:** Câu hỏi có yếu tố pháp lý nhưng chưa đủ dấu hiệu khẳng định chắc chắn ngoài phạm vi $\rightarrow$ Vẫn cho đi tiếp vào bước retrieval (để ngưỡng tin cậy `confidence_filter` quyết định tiếp theo thay vì từ chối sớm).
  3. **`Route.LEGAL_OUT_OF_SCOPE` $\rightarrow$ `Action.POLICY_ABSTENTION`:** Câu hỏi pháp lý thuộc lĩnh vực khác (Hình sự, Đất đai, Thuế, Doanh nghiệp...) $\rightarrow$ Từ chối theo chính sách (`ABSTAIN`).
  4. **`Route.MIXED_LEGAL_SCOPE` $\rightarrow$ `Action.POLICY_ABSTENTION`:** Câu hỏi giao thoa giữa Hôn nhân & Gia đình và lĩnh vực pháp lý ngoài phạm vi $\rightarrow$ Áp dụng từ chối theo chính sách (`ABSTAIN`).
  5. **`Route.NON_LEGAL` $\rightarrow$ `Action.GENERAL_CHAT`:** Câu hỏi giao tiếp thông thường, chào hỏi $\rightarrow$ Phản hồi giao tiếp chung, không đưa ra kết luận pháp lý và luôn đính kèm Disclaimer.

### FR-03: Xác định Mốc Thời gian & Bộ lọc Hiệu lực Thời điểm (Temporal Pre-filtering)
* **Trạng thái triển khai:** **Đã triển khai** tại `retrieval/temporal.py`, `retrieval/hybrid_retriever.py`, `embedding/vector_store.py`.
* **Quy tắc xử lý (Issue E1):**
  1. **Thứ tự ưu tiên xác định `as_of_date`:**
     * *Trong chế độ Benchmark A/B chính thức:* Lấy trực tiếp trường `as_of_date` từ `data/benchmark/queries_dev.json` theo `query_id` và gắn nhãn `as_of_date_source = "benchmark"`.
     * *Trong chế độ tương tác:* (1) Mốc thời gian nêu rõ trong câu hỏi (`query_text`) $>$ (2) Ngày người dùng chọn (`user_input`) $>$ (3) Ngày hiện tại qua `normalize_as_of_date(None)` (`system_today`).
  2. **Công thức toán học kiểm tra khoảng hiệu lực nửa mở:**
     Một phân mảnh được xác định là có hiệu lực tại thời điểm `as_of_date` khi và chỉ khi:
     $$\text{effective\_from} \le \text{as\_of\_date} < \text{effective\_to}$$
  3. **Đồng bộ đa tầng:** Cùng một ngữ nghĩa kiểm tra của `retrieval.temporal.is_effective_at` được thực thi trước khi lấy Top-K tại Elasticsearch DSL, Qdrant DatetimeRange Filter DSL và `PrecomputedRetriever`.

### FR-04: Truy xuất Lai (Hybrid Retrieval: BM25 + Dense Vector Search)
* **Trạng thái triển khai:** **Đã triển khai** tại `retrieval/hybrid_retriever.py`, `embedding/dense_retriever.py`, `embedding/model_registry.py`.
* **Quy tắc xử lý:**
  1. **Nhánh Sparse (Elasticsearch BM25):**
     * Kết nối tới index chính thức khai báo trong `retrieval/config.yaml`: **`bm25-e6-verified-20261101`** *(lưu ý: `legal-child-chunks-dev` chỉ là tên mock dùng trong unit test)*.
     * Tách từ tiếng Việt câu truy vấn bằng `underthesea` (`version == 9.5.0`, `format="text"`), fail-fast nếu thiếu thư viện. Truy vấn kết hợp `content`, `breadcrumb^1.5` và `content_segmented`.
  2. **Nhánh Dense (Qdrant Vector Search):**
     * Sử dụng mô hình chuẩn đã khóa trong `retrieval/config.yaml`: `BAAI/bge-m3` (`dimension = 1024`, `use_word_segmentation = False`, `text_field = "embed_text_raw"`, `collection = "vietnam_legal_chunks"`).
     * Khi mở collection, `_ensure_collection` và `read_index_metadata()` đối chiếu tên mô hình, số chiều (`1024`) và mã băm `corpus_sha256` của tệp `chunks.jsonl` (`2.322 chunks`).
  3. **Hợp nhất Reciprocal Rank Fusion (RRF):**
     * Hợp nhất kết quả BM25 và Dense theo công thức RRF với hằng số $k = 60$ (`rrf_k = 60`), kết xuất `retrieval_top_k = 50` ứng viên.
  4. **Xử lý kết quả rỗng (Issue E14):** Trả về `results: []`, không gọi LLM sinh văn bản (`llm_calls = 0`).

### FR-05: Xếp hạng lại (Cross-Encoder Reranking), Ngưỡng Tin cậy & Khôi phục Khoản Cha
* **Trạng thái triển khai:** **Đã triển khai** tại `reranking/pipeline.py`, `reranking/parent_context.py`, `reranking/confidence.yaml`.
* **Quy tắc xử lý:**
  1. **Cross-Encoder Reranking:**
     * Sử dụng mô hình `BAAI/bge-reranker-v2-m3` (`fp16` trên CUDA) chấm điểm cặp `(query, candidate_text)` với `candidate_text = document_breadcrumb_chunk_text`, chọn ra tối đa `rerank_top_k = 5` ứng viên đứng đầu.
  2. **Chế độ Chạy 2 Bước (`PrecomputedRetriever`):**
     * Hỗ trợ nạp ứng viên tính trước qua biến môi trường `RAG_PRECOMPUTED` (ví dụ `evaluation/results/precompute/20261110_dev30_retrieval.jsonl`), bắt buộc kiểm tra khớp `as_of_date` từng câu. Khi dùng precomputed, trường `retrieval_ms` trong `latency_breakdown` là `null`.
  3. **Lọc theo Ngưỡng Tin cậy (`reranking/confidence.yaml`):**
     * Tham số ngưỡng được tách riêng tại tệp **`reranking/confidence.yaml`** (để không làm thay đổi mã băm của `reranking/config.yaml`) với cấu hình `threshold_config_version: "conf_v1_20261109"`:
       * `min_top1_score: 0.5`
       * `min_evidence_score: 0.1`
     * Ngưỡng này được hiệu chỉnh trên tập Dev còn lại kết hợp với tập câu hỏi âm 26 câu (`evaluation/negative_set/dev_negative_queries_v2.jsonl`, manifest `dev_negative_manifest_v2.json`).
     * Nếu ứng viên đứng đầu không đạt ngưỡng tin cậy (như câu `HN_035` có `top1_score = 0.087 < 0.5`), hệ thống ngắt sớm (`llm_calls = 0`) và trả về `grounding_status = "ABSTAIN"`, `abstained = True`, `abstention_reason = "LOW_CONFIDENCE"`, `abstention_source = "confidence_filter"`.
  4. **Khôi phục Ngữ cảnh Cha (`ParentContextResolver`):**
     * Truy vết từ `parent_id` / `parent_clause_id` sang tệp `data/chunking_output/parents.json` (`1.079 parent records`), giới hạn ngân sách `max_context_chars = 6000` ký tự và đóng gói thành `ContextPayload`.

### FR-06: Xây dựng Prompt & Đánh số Bằng chứng (`[1]..[5]`)
* **Trạng thái triển khai:** **Đã triển khai** tại `generation/prompt_builder.py`, `generation/prompts/legal_rag_prompt_v1_0.md`.
* **Quy tắc xử lý:**
  1. **Quản lý Phiên bản Prompt:**
     * Tại mốc Freeze ban đầu (`origin/docs` / `cdca079`): `PROMPT_A_VERSION = "v1.0_zero_shot_m1"`, `PROMPT_B_VERSION = "v1.0_controlled_rag_m1"`.
     * Tại mốc cập nhật chống rò rỉ luật Trung Quốc (`results/run-b-20261110`, commit `d7b0d1b`): Nâng cấp lên **`PROMPT_A_VERSION = "v1.1_zero_shot"`** và **`PROMPT_B_VERSION = "v1.1_controlled_rag"`**, tự động cập nhật `prompt_hash` (SHA-256).
  2. **Ràng buộc Chống Ảo giác & Luật Nước ngoài (`v1.1`):**
     * Chỉ được phép trả lời dựa trên pháp luật nước Cộng hòa Xã hội Chủ nghĩa Việt Nam được cung cấp trong các đoạn bằng chứng `[1]` đến `[{n}]`.
     * Nghiêm cấm tuyệt đối sử dụng kiến thức tiền huấn luyện về pháp luật Trung Quốc (Bộ luật Dân sự Trung Quốc, Luật Hôn nhân Trung Quốc...) hay bất kỳ quốc gia nào khác.
     * Nguyên tắc đóng ngữ cảnh (*Strict Closed-Context*): Không đủ căn cứ trong `[1]..[{n}]` bắt buộc đặt `"abstained": true`.
  3. **Ánh xạ ngược (`map_evidence_indices_to_citations`):**
     * Mô hình chỉ xuất mảng chỉ số nguyên `evidence_indices` (ví dụ `[1, 2, 3, 5]`), không chép chuỗi `chunk_id`. Hàm ánh xạ tự động khử trùng lặp và tách riêng các chỉ số ngoài khoảng vào `invalid_indices`.

### FR-07: Cổng Giao tiếp Mô hình Qwen2.5:7b & Theo dõi Runtime Provenance
* **Trạng thái triển khai:** **Đã triển khai** tại `model_gateway/llm_gateway.py`, `model_gateway/config/local_qwen.yaml`.
* **Quy tắc xử lý:**
  1. **Siêu tham số cố định:**
     * Mô hình: `qwen2.5:7b` qua Ollama (`http://localhost:11434`).
     * Tham số sinh: `temperature = 0.0`, `num_predict = 1024`, `num_ctx = 8192`, `timeout_seconds = 120`, `max_retries = 1`, `repeat_penalty = 1.0` (trên `results/run-b-20261110`; `1.15` trên `cdca079`).
  2. **Phân loại Trạng thái Phân tích JSON (`parse_status`) & Cắt cụt Ngữ cảnh:**
     * Ép kiểu đầu ra bằng JSON Schema (`StructuredRAGOutput`). Tách biệt `parse_status = "ok"` (kể cả khi `evidence_indices` chứa số ngoài khoảng để chuyển cho Gate xử lý) với `truncated_json` (`done_reason == "length"`) và `invalid_json`.
     * Trường `context_truncated` được ghi nhận trực tiếp trên `LLMResponse` khi `prompt_eval_count >= num_ctx` (`8192`).

### FR-08: Cổng Kiểm duyệt Căn cứ Xác định (Deterministic Grounding Gate)
* **Trạng thái triển khai:** **Đã triển khai** tại `grounding/citation_validator.py` và `orchestration/rag_pipeline.py`.
* **Quy tắc xử lý:**
  1. **Hàm kiểm tra xác định (`validate_citations(...)`):** Mô-đun `grounding/citation_validator.py` cung cấp hàm mức module `validate_citations(...)` (không sử dụng class) để đối chiếu danh sách trích dẫn đã ánh xạ với `ContextPayload`.
  2. **Kiểm tra ký tự Hán / CJK (`count_cjk_chars(...)`):** Kiểm tra toàn bộ nội dung `answer` trước khi phát ra; nếu phát hiện ký tự CJK, Gate lập tức chặn với mã lỗi `ANSWER_NOT_VIETNAMESE`.
  3. **Kiểm tra khớp chỉ số dẫn chứng trong văn bản (`ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES`):** Đối chiếu các ký hiệu `[k]` xuất hiện trong nội dung `answer` với mảng `evidence_indices` do mô hình khai báo.
  4. **Điền đầy đủ trạng thái `ABSTAIN` / `FAIL`:** Khi kết quả không đạt `PASS`, `orchestration/rag_pipeline.py` thông qua hàm `abstention_fields()` và `_abstention_reason_detail()` luôn điền đầy đủ giá trị (tuyệt đối không để `null`) cho `abstained`, `abstention_reason`, `abstention_source` ở cấp `RAGOutputRecord` và `reason_detail` trong `retrieval_trace["gate"]`.

### FR-09: Thực thi Lô (Batch Runner) & Giao diện Mở rộng (CLI, REST API, Web UI)
* **Phần đã triển khai (`Implemented`):**
  * **Batch Runner (`scripts/run_rag_batch.py`):** Đọc danh sách ID (như `evaluation/rubrics/dev_gold_30_ids_v1.txt`) và tệp benchmark (`data/benchmark/queries_dev.json`); hỗ trợ `--require-clean-checkout` và `--resume`; xuất ra 3 tệp chuẩn trong thư mục đầu ra: **`results.jsonl`**, **`errors.jsonl`**, và **`run_manifest.json`**.
* **Phần kế hoạch mở rộng (`Planned – Tuần 10`):**
  * **RAG Q&A CLI (`scripts/run_rag_cli.py`):** Entry point dòng lệnh hỏi đáp đơn lẻ tương tác.
  * **Backend API FastAPI (`api/main.py`, `api/routes/ask.py`):** Cung cấp endpoint `POST /ask`, xác thực `X-API-Key`, sự kiện trạng thái SSE và tài liệu OpenAPI `/docs`.
  * **Web UI Streamlit (`frontend/streamlit_app.py`):** Giao diện trò chuyện trực quan tích hợp khung đối chiếu điều luật (**Evidence Panel**) và bộ chọn ngày hiệu lực (**Date Picker**).

---

## 4. Đặc tả Cấu trúc Bản ghi Đầu ra Chuẩn trong `results.jsonl`

Mỗi dòng trong tệp `results.jsonl` do `scripts/run_rag_batch.py` xuất ra là một đối tượng JSON bọc ngoài (**Batch Envelope**) chứa trạng thái thực thi của batch và toàn bộ đối tượng `RAGOutputRecord` nằm trong khóa **`result`**. Dưới đây là cấu trúc chính xác đối chiếu từ kết quả thực tế `20261113_controlled_rag_qwen25_dev30_post_fix/results.jsonl`:

### 4.1. Ví dụ Bản ghi Trạng thái `PASS` (Dòng 14 – Câu `HN_025`)
```json
{
  "status": "SUCCESS",
  "query_id": "HN_025",
  "as_of_date": "2026-10-15",
  "result": {
    "query_id": "HN_025",
    "query": "Một bên có thể được Tòa án giải quyết cho ly hôn khi có bạo lực gia đình nghiêm trọng không?",
    "as_of_date": "2026-10-15",
    "as_of_date_source": "benchmark",
    "answer": "Theo quy định có hiệu lực tại ngày 2026-10-15, khi vợ hoặc chồng có hành vi bạo lực gia đình làm cho hôn nhân lâm vào tình trạng trầm trọng, đời sống chung không thể kéo dài, mục đích của hôn nhân không đạt được thì Tòa án giải quyết cho ly hôn theo yêu cầu của một bên [1], [2], [3], [5].\n\nThông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.",
    "evidence_indices": [1, 2, 3, 5],
    "citations": [
      {
        "evidence_index": 1,
        "chunk_id": "l_52_2014_qh13_art_56_clause_1_chunk_1",
        "document_id": "l_52_2014_qh13",
        "article_id": "l_52_2014_qh13_art_56",
        "clause_id": "l_52_2014_qh13_art_56_clause_1",
        "parent_clause_id": "l_52_2014_qh13_art_56_clause_1"
      }
    ],
    "grounding_status": "PASS",
    "abstained": false,
    "abstention_reason": null,
    "abstention_source": null,
    "needs_clarification": false,
    "retrieval_trace": {
      "candidate_source": "precomputed",
      "rerank_top_k": 5,
      "precomputed": true,
      "candidates": [
        {
          "evidence_index": 1,
          "chunk_id": "l_52_2014_qh13_art_56_clause_1_chunk_1",
          "document_id": "l_52_2014_qh13",
          "article_id": "l_52_2014_qh13_art_56",
          "clause_id": "l_52_2014_qh13_art_56_clause_1",
          "parent_clause_id": "l_52_2014_qh13_art_56_clause_1",
          "score": 0.985
        }
      ],
      "gate": {
        "status": "PASS",
        "reason": "CITATIONS_MATCH_SELECTED_CONTEXT",
        "invalid_indices": [],
        "abstained": false
      }
    },
    "llm_calls": 1,
    "model": "qwen2.5:7b",
    "prompt_version": "v1.1_controlled_rag",
    "num_ctx": 8192,
    "num_predict": 1024,
    "done_reason": "stop",
    "truncated": false,
    "corpus_version": "sha256:7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023",
    "retrieval_config_version": "sha256:a650eac52ec2ba74",
    "threshold_config_version": "conf_v1_20261109",
    "latency_ms": 5392.41,
    "latency_breakdown": {
      "retrieval_ms": null,
      "llm_total_ms": 5388.12,
      "ttft_model_ms": 1140.25,
      "load_ms": 18.4,
      "prompt_eval_ms": 1121.85,
      "eval_ms": 4247.87
    },
    "token_usage": {
      "input": 2590,
      "output": 204
    },
    "fallback_status": "none"
  }
}
```

### 4.2. Ví dụ Bản ghi Trạng thái `ABSTAIN` (Dòng 21 – Câu `HN_035` ngắt sớm tại Confidence Filter)
```json
{
  "status": "SUCCESS",
  "query_id": "HN_035",
  "as_of_date": "2026-10-15",
  "result": {
    "query_id": "HN_035",
    "query": "...",
    "as_of_date": "2026-10-15",
    "as_of_date_source": "benchmark",
    "answer": "Không tìm thấy đủ căn cứ trong cơ sở dữ liệu pháp luật Hôn nhân và gia đình hiện có để trả lời câu hỏi này tại thời điểm 2026-10-15.\n\nThông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.",
    "evidence_indices": [],
    "citations": [],
    "grounding_status": "ABSTAIN",
    "abstained": true,
    "abstention_reason": "LOW_CONFIDENCE",
    "abstention_source": "confidence_filter",
    "needs_clarification": false,
    "retrieval_trace": {
      "candidate_source": "precomputed",
      "rerank_top_k": 5,
      "precomputed": true,
      "candidates": [
        {
          "evidence_index": 1,
          "chunk_id": "...",
          "score": 0.0867919921875
        }
      ],
      "gate": {
        "status": "ABSTAIN",
        "reason": "LOW_CONFIDENCE",
        "reason_detail": "LOW_CONFIDENCE: top1_score=0.087 < 0.50",
        "invalid_indices": [],
        "abstained": true,
        "abstention_source": "confidence_filter"
      }
    },
    "llm_calls": 0,
    "model": "qwen2.5:7b",
    "prompt_version": "v1.1_controlled_rag",
    "num_ctx": 8192,
    "num_predict": 1024,
    "done_reason": "not_generated",
    "truncated": false,
    "corpus_version": "sha256:7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023",
    "retrieval_config_version": "sha256:a650eac52ec2ba74",
    "threshold_config_version": "conf_v1_20261109",
    "latency_ms": 0.14,
    "latency_breakdown": {
      "retrieval_ms": null,
      "llm_total_ms": null,
      "ttft_model_ms": null,
      "load_ms": null,
      "prompt_eval_ms": null,
      "eval_ms": null
    },
    "token_usage": {
      "input": 0,
      "output": 0
    },
    "fallback_status": "none"
  }
}
```

---

## 5. Yêu cầu Phi Chức năng (Non-Functional Requirements - NFRs)

| Mã NFR | Nhóm Yêu cầu | Đặc tả Kỹ thuật & Ngưỡng Chấp nhận Thực tế |
| :--- | :--- | :--- |
| **NFR-01** | **Hiệu năng & Tài nguyên (Performance & Resource Limits)** | - Vận hành ổn định trên phần cứng cục bộ: **RTX 3050 Ti (4 GB VRAM)** và **RTX 4060 (8 GB VRAM)**.<br>- Kết quả thực nghiệm thực tế trên 30 câu Dev official (Run B `post-fix`, RTX 4060, precomputed): độ trễ trung vị **`p50 = 4.698,81 ms`**, **`p95 = 6.552,61 ms`**, **`max = 7.950,23 ms`**.<br>- **TTFT streaming:** `N/A` (do chạy chế độ `stream=False` theo cơ chế *Buffer-then-stream* qua Grounding Gate trước khi phát câu trả lời; hệ thống ghi nhận thời gian xử lý prompt phía engine qua `latency_breakdown.ttft_model_ms`).<br>- **Cost/request:** `$0.00` (suy luận cục bộ qua Ollama `0.40.16`). |
| **NFR-02** | **Tính Tất định & Khả năng Tái lập (Determinism & Reproducibility)** | - Mọi lượt chạy đánh giá chính thức đặt `temperature = 0.0`, tắt bộ nhớ đệm (`cache_enabled = False`), khóa fallback (`fallback_locked = True`) và kiểm tra sạch cây thư mục (`--require-clean-checkout`).<br>- Mọi lượt chạy xuất tệp **`run_manifest.json`** lưu vết đầy đủ `git_sha`, `corpus_sha256`, `dataset_ids_hash`, `prompt_version`, `prompt_hash`, `ollama_version`, `model_digest` và `threshold_config_version`. |
| **NFR-03** | **Độ Tin cậy & Lập trình Phòng thủ (Reliability & Defensive Programming)** | - Áp dụng nguyên tắc **Schema-First** và **Fail-Fast**: Mọi sai lệch về số chiều vector (`1024`), thiếu thư viện tách từ `underthesea 9.5.0`, thiếu khóa cấu hình, hoặc lệch ngày `as_of_date` trong tệp precompute đều ném ngoại lệ tường minh.<br>- Không tạo các thư mục nguồn sự thật trùng lặp (duy trì duy nhất `schemas/`, `test/`, `reranking/parent_context.py`). |
| **NFR-04** | **Đồng thời & Quản lý Kết nối (Concurrency Control)** | - Khi sử dụng Qdrant nhúng cục bộ (`QdrantClient(path=...)`), Batch Runner thực thi tuần tự (`serial mode`) để tránh lỗi khóa tệp. Hỗ trợ chuyển đổi sang Qdrant Server qua Docker (`deployment/qdrant/docker-compose.qdrant.yml`) cho môi trường đa tiến trình ở Tuần 10. |
| **NFR-05** | **Khả năng Kiểm thử & Bảo vệ Nhánh (Testability & CI Gate)** | - Kho mã nguồn duy trì bộ kiểm thử tự động quy mô lớn với **1.352 tests** thu thập bởi `python -m pytest --collect-only -q` (**1.351 passed, 1 skipped**), `0` lỗi linting (`python -m ruff check .`).<br>- GitHub Actions CI tự động kiểm tra trên mỗi commit/PR và chặn gộp nhánh nếu có bài test thất bại hoặc xuất hiện tệp rác `.pyc`. |

---

## 6. Khung Đánh giá Thực nghiệm & Ma trận Truy vết Nghiệm thu (Evaluation & RTM)

### 6.1. Thiết kế Thực nghiệm Đối chuẩn (Controlled A/B Experiment)
* **Tập dữ liệu đánh giá chính thức:** Đúng **30 câu hỏi** thuộc tập `Dev Gold` (`evaluation/rubrics/dev_gold_30_ids_v1.txt`, `review_status = "source_checked"`), được bảo vệ bởi bài kiểm tra chống rò rỉ **`test/evaluation/test_dev30_no_test_leakage.py`**.
* **Hai cấu hình đối chuẩn:**
  * **Run A (Zero-shot Baseline):** Mô hình `qwen2.5:7b` + Prompt Zero-shot + `as_of_date` từ benchmark + không có ngữ cảnh RAG.
  * **Run B (Controlled RAG):** Cùng mô hình `qwen2.5:7b` + Precomputed Hybrid Retrieval (`bm25-e6-verified-20261101` + Qdrant `BAAI/bge-m3`) & Rerank Top-5 + Parent Context + Structured JSON Output + Deterministic Grounding Gate (`validate_citations`).
* **Quy trình Chấm mù A/B (Planned – Bước đánh giá tiếp theo):**
  * Kế thừa và mở rộng khung tiêu chí chấm điểm từ **`evaluation/rubrics/zero_shot_rubric_guide_v1.md`** (hiện dùng để chấm baseline zero-shot) sang biểu mẫu chấm mù A/B 60 câu (30 câu Run A + 30 câu Run B).
  * Chuẩn hóa hiển thị trích dẫn, ẩn nhãn nguồn (`A` hay `B`) và trộn ngẫu nhiên thứ tự 60 câu trả lời trước khi chuyển cho 02 người chấm độc lập đánh giá (kèm double-score tập con 10 câu để tính hệ số đồng thuận **Weighted Cohen's Kappa ($\kappa$)**).

### 6.2. Ma trận Truy vết Yêu cầu & Nghiệm thu (Requirements Traceability Matrix - RTM)

| Mã Yêu cầu | Hạng mục Đặc tả | Module / Tệp Nguồn Chính | Bài Kiểm thử / Bằng chứng Nghiệm thu | Trạng thái |
| :--- | :--- | :--- | :--- | :---: |
| **BO-01 / FR-03 / FR-04** | Lọc hiệu lực thời gian `as_of_date` & Hybrid Retrieval Top-50 (`28 văn bản / 2.322 chunks`) | `retrieval/temporal.py`<br>`retrieval/hybrid_retriever.py`<br>`embedding/vector_store.py` | `test/test_e1_temporal_retrieval.py`<br>`docs/data_contract.md` (Mục 5.5) | **Đã đạt** |
| **BO-02 / FR-05** | Cross-Encoder Reranking Top-5, Ngưỡng tin cậy (`conf_v1_20261109`) & Parent Context (`1.079 parents`) | `reranking/pipeline.py`<br>`reranking/parent_context.py`<br>`reranking/confidence.yaml` | `test/test_reranker.py`<br>`reports/retrieval/confidence_threshold_dev_calibration.md` | **Đã đạt** |
| **FR-02 / BO-04** | Rule Router 5 trạng thái `Route` (độc lập) & Tập câu hỏi âm 26 câu (`v2`) | `agent/router/rule_router.py`<br>`evaluation/negative_set/dev_negative_queries_v2.jsonl` | `test/agent/test_rule_router.py`<br>`evaluation/negative_set/dev_negative_manifest_v2.json` | **Đã đạt** |
| **FR-06 / FR-07** | Canonical Pydantic Schemas, Prompt `v1.1` chống luật Trung Quốc & Qwen Gateway | `schemas/models.py`<br>`generation/prompt_builder.py`<br>`model_gateway/llm_gateway.py` | `test/schema_test.py`<br>`test/test_p45_prompt_gateway.py`<br>`reports/dev3_live_qwen_verification.json` | **Đã đạt** |
| **BO-03 / FR-08** | Deterministic Citation Validator (`validate_citations`) & Grounding Gate (không để `null` khi `ABSTAIN`) | `grounding/citation_validator.py`<br>`orchestration/rag_pipeline.py` | `test/grounding/test_citation_validator.py`<br>`test/orchestration/test_grounding_gate.py`<br>`test/orchestration/test_record_abstention_latency.py` | **Đã đạt** |
| **BO-05 / FR-09 (Batch)** | Batch Runner xuất `results.jsonl`, `errors.jsonl`, `run_manifest.json` & Leakage Guard | `scripts/run_rag_batch.py`<br>`evaluation/metric_definitions_v1.md` | `test/evaluation/test_run_rag_batch.py`<br>`test/evaluation/test_dev30_no_test_leakage.py` | **Đã đạt** |
| **FR-01 (PII) / FR-02 (Link) / FR-09 (UI/API)** | Nối `rule_router` vào pipeline, Chấm mù A/B 60 câu, CLI (`run_rag_cli.py`), FastAPI, Streamlit & PII Masking | `orchestration/rag_pipeline.py`<br>`scripts/run_rag_cli.py`<br>`api/main.py`<br>`frontend/streamlit_app.py`<br>`monitoring/pii_masker.py` | Kế hoạch kiểm thử E2E, chấm mù A/B & triển khai Tuần 10 (`test/e2e/test_rag_cli.py`) | **Kế hoạch Tuần 10** |
