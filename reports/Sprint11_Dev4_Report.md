# Báo cáo Sprint 11 Dev4

Cập nhật **23/11/2026** · Nhánh `week11_dev4` · Phạm vi **D4.1–D4.5**.

Router v5 đã freeze; holdout v6 được project owner chốt chính thức. Retrieval Adapter đã hoàn tất phần độc lập, còn chờ wiring và logging của consumer. Audit Dev30 có verdict `VERIFIED`. Top-50 input vẫn chờ quyết định D-13, chưa triển khai.

| Task | Trạng thái | Kết quả chính |
|---|---|---|
| D4.1 Router | **FROZEN** | Snapshot khóa; Dev3 và Tech Lead sign-off theo xác nhận project owner |
| D4.2 Holdout | **CHỐT CHÍNH THỨC** | V6 đạt 34/36; legal → chat 0/30 |
| D4.3 Adapter | **XONG PHẦN ĐỘC LẬP** | Trace và kiểm thử ba nhánh đã có; còn wiring/logging |
| D4.4 Provenance Dev30 | **VERIFIED** | Bốn run khớp 30/30; chênh SHA do LF/CRLF |
| D4.5 Top-50 input | **BLOCKED** | Chờ Tech Lead chốt D-13 |

## D4.1 — Router v5 và freeze

**Đầu vào:** Router v5, Negative Set v2 đã duyệt, Dev Gold 30, Dev benchmark 270 và contract `week10_v1.1`.

**Đầu ra:** adapter công khai `agent.router.RuleRouterAdapter`, cấu hình xã giao `agent/config.py` và [hồ sơ freeze](../docs/router_freeze.md).

- Đã thống nhất mapping canonical; explanation ghi route gốc/action; đưa kịch bản xã giao ra khỏi AskService.
- Snapshot source/config/tests: `d76244d8b454aedec7518bd37fecda3d419790cc`. Classifier giữ `rule_router_v5`, không đổi luật phân loại; trước/sau refactor có **552/552** quyết định route/action/reason/version khớp baseline.
- Gate khóa: Gold **30/30**, Dev **270/270**, Negative **26/26**, legal negative → chat **0/20**.
- Kiểm chứng snapshot: Router/AskService/smoke **139 tests, 395 subtests**; API/E2E giả lập **100 tests**.
- Dev3 và Tech Lead đã sign-off theo xác nhận project owner. Ngày ghi hồ sơ 23/11 không được hồi tố thành ngày ký thực tế khi chưa được cung cấp.

**Công nghệ:** Python rule router, Pydantic canonical contract, cấu hình Python cố định, pytest, fake pipeline, SHA-256.

## D4.2 — Holdout v6 chính thức

**Đầu vào:** 36 câu `W16RH_001`–`W16RH_036`; Dev3 review nhãn theo xác nhận project owner.

**Đầu ra:** [JSONL v6](../evaluation/router_holdout/router_holdout_week10_v6.jsonl), [metadata](../evaluation/router_holdout/router_holdout_week10_v6.md) và [hồ sơ chốt holdout](../evaluation/router_holdout/router_holdout_report.md) trong cùng thư mục dữ liệu.

- Project owner chấp thuận v6 làm holdout độc lập chính thức ngày **23/11/2026**. Đây là quyết định nghiệm thu, không phải lần kiểm chứng bổ sung về zero semantic overlap hoặc thời điểm chưa xác định.
- Chốt **34/36 = 94,44%**, vượt ngưỡng classifier 90%; legal → `NON_LEGAL/GENERAL_CHAT` **0/30**.
- Hai mismatch giữ nguyên: `W16RH_012` ngoài phạm vi và `W16RH_029` non-legal đều bị route sang `LEGAL_SCOPE_UNCERTAIN/LEGAL_RETRIEVAL`.
- Kết quả thuộc run **17/11/2026**, source lịch sử `4895649`; không gán cho snapshot refactor `d76244d8`.
- Bộ đã `CONSUMED`: không tune hoặc chạy lại để thay điểm chính thức. `review_date` và `review_before_prediction` vẫn `null` khi chưa có mốc gốc. SHA và confusion matrix giữ trong hồ sơ holdout.

**Công nghệ:** JSONL, Python validator, Unicode NFC, exact-text đối chiếu 10 nguồn, Git/SHA-256.

## D4.3 — Retrieval Adapter

**Đầu vào:** pipeline retrieval, corpus SHA đã xác minh, phiên bản cấu hình, ngày hiệu lực và nguồn ngày do caller giải quyết.

**Đầu ra:** `RetrievalBundle` canonical; API mới `retrieve_with_trace()` trả `(bundle, trace)` trong một lần retrieval. Không sửa schema canonical hoặc wiring orchestration trong đợt này.

| Phần đã làm | Nội dung |
|---|---|
| Trace nhận diện/provenance | Query ID, ngày/nguồn ngày, schema, corpus hash/version, retrieval config version, retriever và precomputed flag |
| Trace ứng viên | Chunk/document/article/clause/parent ID, rank/score, nguồn, điểm/hạng từng nhánh, RRF/reranker score và khoảng hiệu lực |
| Trace bộ lọc/thời gian | Metadata filters, output Top-k, số candidate trả về, latency tổng/từng chặng; chưa đo giữ `null` |
| Outcome | `RETRIEVED` hoặc `EMPTY`; lỗi backend vẫn phát lỗi, không tự quyết định `LOW_CONFIDENCE` |
| Precomputed reader | Lọc ngày/metadata trên pool đã lưu **trước Top-k**; giữ guard query ID/query/ngày/độ sâu pool, không tạo candidate ngoài artifact |

`corpus_version` được truyền riêng, không suy từ SHA. Nguồn ngày theo enum `benchmark/query_text/user_input/system_today`; adapter không trích lại năm từ query. Trace không chứa query/chunk/parent text, không dùng `last_trace` chung giữa request.

**Code thay đổi:** `retrieval/adapter.py`, reader `PrecomputedRetriever` trong `reranking/pipeline.py`, test adapter và `test/test_retrieval_filter_conformance.py`. Sửa reader dùng chung nhằm đồng nhất hành vi lọc với BM25/Dense; cần Dev5 review khi mở PR.

**Kiểm chứng:** cùng fixture/ngày/filter qua Elasticsearch adapter thật với fake transport, Qdrant local `:memory:` và precomputed. Có ngày lịch sử, biên đầu/cuối hiệu lực, tương lai, khoảng mở, filter kết hợp, empty và lọc trước Top-1. So tập chunk hợp lệ, không yêu cầu cùng thứ tự/score.

| Bộ kiểm tra | Kết quả |
|---|---|
| Adapter, filter conformance, pipeline context, Hybrid | **60 passed, 21 subtests passed** |
| CLI precomputed và two-stage | **3 passed, 2 subtests passed** |
| Ruff bốn file Python thay đổi | **PASS** |

**Công nghệ:** Python/Pydantic, Elasticsearch filter DSL/fake transport, Qdrant local, temporal filtering nửa mở, precomputed reader, pytest/Ruff. Không chạy server Elasticsearch/Qdrant, embedding, Cross-Encoder hoặc Ollama thật.

### Phần cần phối hợp để đóng D4.3

| Owner | Việc còn lại |
|---|---|
| Dev5 | Nối adapter vào `Protocol.fetch`/consumer; chuyển bundle tới Context Builder, đưa trace vào record; kiểm tra API/batch sau wiring |
| Dev5 | Review reader precomputed và các guard hash corpus/candidate text/reranker config khi tích hợp |
| Dev1 + Dev5 | Gắn latency BM25/Dense/RRF vào LogEvent stage retrieval, giữ `null` khi chưa đo |
| Dev3 + Tech Lead | Duyệt nếu cần đưa corpus version/nguồn ngày/trace vào canonical bundle; hiện trace riêng không cần đổi schema |

Test nguồn ngày chỉ xác minh adapter giữ thông tin đã được giải quyết, không thay test phân giải ngày UI/API. Kiểm thử offline không thay live integration smoke. **D4.3 toàn luồng chưa đóng.**

## D4.4 — Audit provenance Dev30

**Verdict: VERIFIED** trong phạm vi nguồn gốc artifact precompute và bốn run đã lưu. **Không replay Dev30 theo D-12**; không thay manifest, chữ ký hoặc output gốc. Verdict không xác minh lại chất lượng pháp lý hoặc toàn bộ raw pool 50.

**Đầu vào:** [precompute JSONL](../evaluation/results/precompute/20261110_dev30_retrieval.jsonl), [precompute manifest](retrieval/precompute_manifest.json), benchmark/IDs, corpus/config và Git blobs lịch sử, bốn run trong `evaluation/results/dev/`.

**Đầu ra:** audit/verdict tại mục này và đính chính [báo cáo Week 10](week10/controlled_rag_b_validation.md).

| Dạng artifact | SHA-256 đã tái lập |
|---|---|
| LF, cũng là bytes working tree lúc audit | `6eb200f3803dfe341299f092ae1be9723ec9236f501f7bb53ef47dc098dd1353` |
| Cùng bytes chuyển sang CRLF | `576065abe250393ee56130555a175345d5827628802df83f14bbe7aae38574a3` |

- SHA LF khớp precompute manifest; SHA CRLF khớp cả bốn run manifest. Chênh lệch là biểu diễn newline, không phải nội dung candidate/ranking.
- Git commit chứa precompute: `cdca079ba63b5e3d48da690df269ff51bb47c887`; blob ID `d652635b70a6ff04d09cdbbdd6af7c611a60c460`. Git blob LF bằng nội dung LF hiện tại.
- Ranking nguồn: `retrieval/results/dev_hybrid_reranker.json` tại commit `defee7e45f7b7310ff41379f42728a76f86cb465`; SHA-256 `738a07c63bb4812bd3a2f9a5e6bb3a57fc5358515057def63d87fc6c2d764dc7`, khớp precompute manifest.
- Top-5 precompute khớp prefix ranking nguồn về ID/rank/score/reranker score và chunk/parent text ở **30/30 query**. `candidate_text` do builder bổ sung theo `document_breadcrumb_chunk_text`, dựng lại khớp **150/150 candidate**.
- Benchmark/input IDs, corpus/retrieval/rerank config đối chiếu được tại `git_sha` từng run; SHA config/benchmark khớp bản CRLF, corpus khớp LF. Chữ ký gốc tái tính từ stable fields của batch runner khớp **4/4**.

| Run | Đối chiếu query/ngày/chunk ID/reranker score | Chữ ký gốc |
|---|---|---|
| `20261110_controlled_rag_qwen25_dev30` | 30/30 | Hợp lệ |
| `20261113_controlled_rag_qwen25_dev30` | 30/30 | Hợp lệ |
| `20261113_controlled_rag_qwen25_dev30_post_fix` | 30/30 | Hợp lệ |
| `20261114_controlled_rag_qwen25_dev30_prompt_v1_2` | 30/30 | Hợp lệ |

**Đính chính:** rút phát biểu Week 10 “đã sửa bốn manifest/tính lại chữ ký”. Thực tế manifest vẫn giữ SHA CRLF và chữ ký gốc hợp lệ. Route trong handoff là tính hậu kỳ. Git diff xác nhận 10 file precompute/precompute manifest và manifest/results bốn run không thay đổi so với HEAD trong đợt audit.

**Bàn giao:** Dev2 dùng verdict cho D2.7 và ghi Dev30 là dữ liệu theo dõi theo D-12. D4.4 hoàn tất phần hồ sơ; không mở khóa D4.5.

**Công nghệ:** Python JSON, SHA-256 bytes/LF/CRLF, Git blob comparison, đối chiếu trace và manifest signature; không chạy model.

## D4.5 — Top-50 input

**BLOCKED — chờ Tech Lead chốt D-13, chưa triển khai.** D-04 khóa `max_evidence=5`; contract evidence index tối đa 5. Thiết kế 5 so với 10 evidence cần quyết định trước; khi chưa có MMR, lấy Top-10 rồi cắt 5 không tạo nhóm evidence khác Top-5.

**Đầu vào cần chốt:** quyết định D-13, Dev/validation IDs được duyệt, adapter đã tích hợp, corpus/config snapshot, candidate text policy và `as_of_date`.

**Đầu ra dự kiến sau mở khóa:** `evaluation/experiments/topk_sprint11/input/top50_candidates.jsonl` và `input_manifest.json`, cùng pool cho các nhánh experiment; chưa tạo trong đợt này.

| Owner | Trách nhiệm sau quyết định |
|---|---|
| Tech Lead | Chọn phương án D-13, IDs, giới hạn evidence và tiêu chí nghiệm thu |
| Dev3 | Chốt contract nếu phương án được duyệt cần thay đổi |
| Dev4 | Chuẩn bị pool Top-50 có provenance/SHA; validate schema, duplicate và temporal |
| Dev5 | Nhận input, thực thi các nhánh experiment |
| Dev2 | Đánh giá offline output |

Nếu chọn phương án B, chỉ dùng Dev IDs được duyệt, không dùng Test30. Tên tham số theo kế hoạch: `retrieval_top_k`, `rerank_output_k`, `max_evidence`. [Phân tích cutoff Week 10](week10/topk_conformance.md) là lịch sử, không nghiệm thu thay Top-50 input Sprint 11. Chưa chạy retrieval/reranking/generation hoặc thay baseline đang khóa.

## Lệnh xác minh phần độc lập

```powershell
.\.venv\Scripts\python.exe scripts/validate_router_holdout.py --holdout evaluation/router_holdout/router_holdout_week10_v6.jsonl
.\.venv\Scripts\python.exe -m pytest -q test/test_retrieval_adapter.py test/test_retrieval_filter_conformance.py test/test_pipeline_context.py test/test_hybrid_retriever.py
.\.venv\Scripts\python.exe -m pytest -q test/test_integration.py -k "precomputed or two_stage"
.\.venv\Scripts\python.exe -m ruff check retrieval/adapter.py reranking/pipeline.py test/test_retrieval_adapter.py test/test_retrieval_filter_conformance.py
```

Validator holdout chỉ kiểm tra dữ liệu/exact-text, không chạy prediction. Báo cáo này là bản tổng hợp duy nhất cho Sprint 11 Dev4; hồ sơ freeze trong `docs/`, hồ sơ holdout trong thư mục dữ liệu và báo cáo lịch sử Week 10 được giữ để truy vết. Không tạo PR, commit hoặc push trong đợt tổng hợp.
