# D1.0 — Baseline repo Tuần 9

Ngày: 06/11/2026 (Asia/Saigon). Thời điểm audit UTC: 2026-11-06T11:57:28.944Z; GitHub snapshot UTC: 2026-11-06T11:56:05.4605034Z. Nguồn: Kế hoạch Tuần 9 V3; Git blobs sau fetch; GitHub REST API PR metadata và Actions. Không dùng nguyên trạng các nhận định cũ trong kế hoạch.

## Kết luận

Baseline code đã tích hợp: origin/testing tại **f89ef8372a06102802349bb9ea0cf04fcc0a4646**. PR #26 đã squash-merge chính tại SHA này; candidate_text/rerank fixes đã có, không còn task chờ merge #26. PR #25 đã sửa mapping nhưng vẫn mở; PR #27 có sửa Gold và xác nhận mới, vẫn mở; metrics hiện theo PR #32, không tiếp tục coi #28 là PR cần merge.

Đã hoàn thành phần điều tra và báo cáo D1.0; chờ reviewer Tech Lead + Dev 4. **M0 chưa đóng**: cần quyết định nhận/hoãn các PR đang mở, xác nhận G3, Dev30/rubric guide và M1. Không cần chờ tất cả nhánh hết lỗi để làm các task độc lập. Báo cáo không tự quyết merge, defer hay cho phép official A/B.

## 1. PR và CI xác minh trực tiếp

| PR | Head SHA | Trạng thái GitHub | CI đúng head |
| --- | --- | --- | --- |
| [#25](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/25) | 54c0e37f5f913f179628d152297b126c1fda2189 | Đang mở, chưa merge | [tests #107](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/actions/runs/41475573144) success |
| [#26](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/26) | 49aea00121adacd8e6caff0bd6cff153cab616c5 | MERGED f89ef8372a06102802349bb9ea0cf04fcc0a4646 | [tests #112](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/actions/runs/41528008030) success |
| [#27](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/27) | 6288e8c7868c198d4c12c9b8e0f7a49d445facd2 | Đang mở, chưa merge | [tests #134](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/actions/runs/42209553954) success |
| [#28](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/28) | 6e69d0451212f2941feb4717a15329515f5cfb98 | Đóng, chưa merge | [tests #120](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/actions/runs/41633425007) failure |
| [#29](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/29) | 89906f80961c74ee85791247373dcd7e8237488b | Đang mở, chưa merge | [tests #118](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/actions/runs/41570032622) success |
| [#32](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/pull/32) | 1700f912aa02084f26ba27df0de9f53e8e72ee7c | Đang mở, chưa merge | [tests #130](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/actions/runs/41865914023) success |

PR #28, #30, #31 đã đóng chưa merge; nhánh fix/metrics tiếp tục qua #32. PR #26 merged_at=2026-11-02T21:28:10Z; merge_commit_sha=f89ef8372a06102802349bb9ea0cf04fcc0a4646. Không suy ra “chưa merge” bằng merge-base --is-ancestor của head, vì squash làm thay đổi SHA. CI xanh không đồng nghĩa đã review/merge hay hoàn tất yêu cầu Tuần 9.

## 2. Những phần mọi người đã sửa

| Phần | Sửa đổi đã kiểm tra | Trạng thái đối với baseline |
| --- | --- | --- |
| PR #25, 07d365d / 08bcb52 / 54c0e37 | Thay 6 placeholder bằng 9 chunk có nguồn; cập nhật validator/tests; chỉnh draft Dev tránh clause overlap Test. 195 draft confirmed chỉ là xác nhận mapping, vẫn chưa duyệt pháp lý. | Đã sửa trên PR, chưa merge. Chi tiết ở corpus_change_impact.md. |
| PR #26 → f89ef83 | E8/G5, candidate_text=document_breadcrumb_chunk_text; kết quả Dev và context pipeline. | Đã squash-merge; cấu hình này có sẵn trong baseline. |
| PR #27, e39a372 / e8b5bd9 / 4171b5e / 6288e8c | Sửa đáp án Dev HN_256/HN_298; sửa Test HN_156/HN_181/HN_246/HN_268 và re-freeze; ghi xác nhận 24 câu Dev 5; đồng bộ testing. Giữ xác nhận 20 câu Dev 3 tại 18d3325. | Đã push/CI xanh, chưa merge; hash phải lấy theo phiên bản thực được nhận. |
| PR #29, 89906f8 | Contract tài liệu: canonical IDs, temporal fields, chữ ký retriever, query rỗng, precomputed date checks, benchmark dates và candidate flow. | Đang mở; không coi tài liệu là code runtime mới. |
| PR #32, 06d0784 → 94cc911 → 1700f91 | Metrics Strict/Parent dùng cùng Top-K chunk; provenance kiểm corpus/query/date/config; baseline/final-test metric runners; freeze guard retrieval Test; config đồng bộ testing. Xóa baseline cũ/zero-shot artifacts cũ, thêm run_zero_shot_dev/test. | CI xanh tại head 1700f91, chưa merge. Zero-shot entry points vẫn cần điều chỉnh cho Tuần 9 (xem validation report). |

## 3. Danh tính dữ liệu và hash

- Corpus: 2164 chunks; Dev 270; Test 30; source_checked 105; draft/other 195.
- Corpus Git-byte SHA-256: **710350f1d0f9b66cb419d89fe7eabd655eba3330c8416534d475e43ce5048d9d**.
- Baseline Test questions canonical SHA-256: d3eb903c5e65e18acd5f4ff9e07876a1cc84ad5755b03c0df2469dec73b2f517.
- Baseline Test Gold canonical SHA-256: f3b4e856a6fdab500d055c97a0329973edfc037a4065918e3c356eded31c1c87.
- PR #27 Test questions canonical SHA-256: 9dd472f569726d67951afb20bb059ea7cc282f8b7d6102cc44807769bfbc3876.
- PR #27 Test Gold canonical SHA-256: **59a9cdf02f76aec81fc2416059f92ef758f0bdbaaad9c6aa2d24d81eb3068811**.
- Mỗi phiên bản khớp hai manifest riêng. PR #27 khác baseline là thay đổi đã re-freeze có ghi trong PR, không phải freeze lỗi. Commit notes-only 18d3325 không đổi Test, nhưng không thể suy rộng điều đó cho các commit sửa đáp án sau này.

Canonical freeze: sorted keys, ensure_ascii=false, separators=(',', ':'), CRLF normalize, thêm newline; kiểm lại bằng Python freeze scripts. Corpus/config hash tính từ raw Git blob để tránh nhầm CRLF checkout Windows. Runtime dùng hash file thực phải được Dev 4 đối chiếu; không tráo hai loại hash.

## 4. Config baseline

- retrieval/config.yaml: SHA-256 cbbd08528fec137833f98fc0587a8cec224905d1a9f9939daac39478d7960daa

~~~yaml
retrieval:
  # Số ứng viên đầu vào mỗi nhánh retrieval.
  retrieval_top_k: 50
  # Số kết quả cuối cùng sau fusion/reranking.
  result_top_k: 10
  # Đường dẫn tương đối trong config luôn tính từ thư mục gốc repository.
  corpus_path: data/chunking_output/chunks.jsonl

bm25:
  backend: elasticsearch
  index: bm25-e6-verified-20261101
  text_field: content_segmented
  tokenizer: underthesea
  tokenizer_version: 9.5.0

dense:
  backend: qdrant
  model: BAAI/bge-m3
  collection: vietnam_legal_chunks
  index_dir: data/indexes
  supported_models:
    BAAI/bge-m3:
      dimension: 1024
      use_word_segmentation: false
      text_field: embed_text_raw
    bkai-foundation-models/vietnamese-bi-encoder:
      dimension: 768
      use_word_segmentation: true
      text_field: embed_text_raw
    AITeamVN/Vietnamese_Embedding:
      dimension: 1024
      use_word_segmentation: false
      text_field: embed_text_raw

hybrid:
  fusion: rrf
  # Chọn trên 75 câu Dev đã duyệt (retrieval/evaluation/rrf_k_comparison_dev_75.md): Top-50 vào reranker giống hệt với k = 10.
  rrf_k: 60
~~~

- reranking/config.yaml: SHA-256 b99cf7319ec93eeb49c241904eb89b5e3e6b41fbbc05b56e63347b25693c6471

~~~yaml
# Cấu hình Reranker (Owner: Dev 5). Đọc bởi reranking/reranker.py::load_reranker_config.
# Đây là giá trị khởi đầu (Sprint 6 mục 14.3), chưa phải cấu hình tối ưu.
# Chỉ tuning trên Dev set; không dùng Test set để chọn tham số.
reranker:
  enabled: true
  # cross_encoder: sentence-transformers CrossEncoder với `model` bên dưới (Cross-Encoder Neural
  # Reranker của sơ đồ kiến trúc).
  # mock: tỉ lệ token trùng, không phải mô hình liên quan; chỉ dùng cho test và chạy offline
  # (--reranker mock), output mang nhãn <retriever>_mock_reranker.
  backend: cross_encoder
  model: BAAI/bge-reranker-v2-m3
  # Số chunk giữ lại sau reranking để đưa sang bước sinh câu trả lời.
  rerank_top_k: 5
  # Trần số candidate đưa vào Cross-Encoder (mục 13.2); phần dư bị cắt theo thứ hạng retrieval.
  # Số candidate thô lấy từ Hybrid là `retrieval_top_k` trong retrieval/config.yaml (Dev 4).
  max_candidates: 50
  batch_size: 16
  max_length: 512
  # null: để sentence-transformers tự chọn (cuda nếu có, ngược lại cpu).
  device: null
  # auto: float16 khi chạy CUDA (model khoảng 1,1 GB thay vì 2,2 GB, vừa GPU 4 GB cùng model dense),
  # float32 khi chạy CPU. Giá trị khác: float32, float16, bfloat16.
  dtype: auto
  # Văn bản đưa vào scorer: chunk_text; breadcrumb_chunk_text (breadcrumb Chương > Điều > Khoản rồi
  # chunk_text); document_breadcrumb_chunk_text (tên, số hiệu văn bản, breadcrumb rồi chunk_text).
  # Chọn trên 75 câu Dev đã duyệt (G5): reranking/evaluation/candidate_text_comparison_dev_75.md.
  candidate_text: document_breadcrumb_chunk_text

# Parent-Context Resolver: chạy sau reranker, gắn parent_id và parent_text cho từng kết quả.
# Con cùng parent chỉ kết quả hạng cao nhất mang parent_text; dừng gắn khi tổng ngữ cảnh vượt
# max_context_chars (top-5 Hybrid trên Dev: trung vị khoảng 2.850, p90 khoảng 4.200 ký tự).
parent_context:
  enabled: true
  parents_file: data/chunking_output/parents.json
  max_context_chars: 6000
~~~

Top-50 fused → rerank → Top-5; result_top_k=10 là cutoff retrieval result, không được dùng làm giới hạn 10 candidate trước rerank. Không retune Retrieval cho official A/B. Runtime/index identity chưa được kiểm tra live.

## 5. Kiểm tra thực chạy

| Checkout riêng | SHA | Validator + 2 freeze checks | Full pytest theo pytest.ini |
| --- | --- | --- | --- |
| testing | f89ef83 | PASS cả 3 | 642 passed, 1 skipped in 29.74s |
| pr25 | 54c0e37 | PASS cả 3 | 644 passed, 1 skipped in 30.03s |
| pr27 | 6288e8c | PASS cả 3 | 642 passed, 1 skipped in 29.20s |
| pr32 | 1700f91 | PASS cả 3 | 658 passed, 1 skipped in 29.64s |

Raw stdout/stderr và command ở checks_testing.json, checks_pr25.json, checks_pr27.json, checks_pr32.json. Full suite có 1 skipped ở mỗi checkout; không coi skipped là pass. Môi trường offline và fixtures/mocks; không chạy official Test retrieval hoặc generation. CI từ GitHub là bằng chứng bổ sung trên môi trường workflow riêng.

## 6. Điều kiện còn chờ

- Tech Lead: quyết định PR #25/#27/#29/#32; #26 đã merge; #28 đóng và không phải merge target nữa.
- Dev 5/4: G3 handoff artifact đã push + SHA và replay provenance. Không có origin/results/rerank trong refs hiện tại chưa chứng minh không có artifact ở nhánh/path khác; cần owner chỉ đúng artifact. PR #26 branch bị xóa là bình thường sau squash merge.
- Dev 2: 30-ID manifest và rubric guide (chưa phải score sheet). Không thấy evaluation/manifests hoặc evaluation/rubrics ở testing và các head được audit; cần bàn giao trước official run.
- Dev 3/2: prompt A/M1, benchmark as_of_date, num_predict đồng nhất, structured output và immutable run manifest.
- Dev 4: corpus/index/version agreement; nếu nhận #25 thì rebuild/migration ES/Qdrant, precompute lại hoặc chứng minh tương thích.

## 7. Tái lập và working tree

Cập nhật refs bằng git fetch và snapshot GitHub bằng scripts/fetch_week09_github_state.ps1 (lưu riêng artifact theo ngày; script audit này dùng snapshot 20261106). Chạy node scripts/audit_week09_baseline.cjs sau khi cập nhật refs và snapshot. Script từ chối nếu SHA API/ref hoặc SHA kết quả test không khớp. Chạy Python scripts/check_week09_ref.py <checkout> <result.json> để kiểm lại từng phiên bản, dùng môi trường Python có dependency repo. Snapshot API/checks có thời điểm riêng; script không tự coi dữ liệu lưu cũ là GitHub live.

Working tree trước sinh báo cáo:

~~~text
?? docs/sprint/
?? reports/
?? scripts/audit_week09_baseline.cjs
?? scripts/check_week09_ref.py
?? scripts/fetch_week09_github_state.ps1
?? scripts/probe_week09_zero_shot.py
?? scripts/week09_evidence_guard.cjs
?? test/test_week09_evidence_guard.cjs
~~~

Các thay đổi local là tài liệu/audit; không sửa benchmark, corpus, runtime config hoặc manifest Test. Chưa commit/push. Đây là snapshot kỹ thuật, không phải biên bản quyết định của Tech Lead.
