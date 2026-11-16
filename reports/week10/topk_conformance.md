# D4.5 – Thí nghiệm cutoff Top-5 và Top-10

## Đầu vào
- Ranking Hybrid/Reranker Top-10 đã lưu (`retrieval/results/dev_hybrid_reranker.json`).
- 45 câu Dev source-checked, ngoài 30 ID official; config baseline Top-5 và metric evaluator của dự án.

## Đầu ra
- So sánh metric cutoff Top-5/Top-10, manifest thí nghiệm và change note đề xuất trong báo cáo này.
- Metric từng câu: `evaluation/results/dev/topk_cutoff_20261116_metrics.json`.

## Kết quả
- Top-10 tăng Recall/NDCG/parent recall, MRR giữ nguyên và Precision giảm; chi tiết số liệu ở phần dưới.
- Đây là cutoff analysis trên ranking đã lưu; chưa xác minh raw candidate pool 50 và chưa đo grounding/citation downstream.
- Official A/B và cấu hình baseline không thay đổi.

## Công nghệ đã dùng
Hybrid BM25 + Dense + RRF, Cross-Encoder ranking artifact, Python metric evaluator, paired bootstrap, JSON manifest, SHA-256.

**Trạng thái:** Đã tính so sánh cutoff đầu ra Top-5 và Top-10 trên ranking Top-10 đã lưu; không thay đổi kết quả A/B official và không gọi Ollama. Đây là phân tích cutoff trên artifact Dev, chưa phải lần chạy retrieval/reranking mới. Việc reranker đã chấm toàn bộ pool 50 candidate chưa thể xác minh độc lập từ artifact hiện có.

## Thiết kế và kiểm tra đầu vào

Thí nghiệm chỉ thay đổi cutoff đầu ra sau reranking. Cùng một danh sách xếp hạng, cùng điểm Cross-Encoder và cùng 50 candidate đã được chấm được tính metric tại Top-5 và Top-10. Script `scripts/evaluate_topk_cutoff.py` kiểm tra SHA-256 của artifact, corpus, cấu hình và từng query trước khi tính điểm.

Nguồn là `retrieval/results/dev_hybrid_reranker.json`: 270 query Dev; artifact SHA-256 `738a07c63bb4812bd3a2f9a5e6bb3a57fc5358515057def63d87fc6c2d764dc7`, khớp SHA trong precompute manifest. Trong từng record, `retrieval_top_k=50`, `stats.scored_candidates=50`, `stats.output_candidates=10`, `top_k=10`, và có 10 kết quả đã xếp hạng. Cấu hình repo hiện ghi `retrieval.result_top_k=10` và `reranker.rerank_top_k=5`; vì vậy ba giá trị không cùng một khái niệm: 50 là pool đầu vào; 5 là mặc định output của reranker; 10 là output cutoff cấu hình/quan sát trong artifact. `top_k=10` thực tế được lưu nhưng chưa có log CLI gốc để xác định cơ chế override `rerank_top_k=5`. Artifact chỉ giữ Top-10; file pool 50 được tham chiếu tại đường dẫn Temp bên ngoài repo và không có ở workspace. Do đó không xác minh độc lập được số 50 ứng với danh sách đã rerank nào. Manifest ghi riêng rõ phần đã quan sát và phần chưa thể kiểm chứng.

| Tham số | Baseline đã khóa | Artifact/experiment quan sát được | Diễn giải |
|---|---:|---:|---|
| `retrieval_top_k` | 50 | 50 | Cấu hình/pipeline record chỉ định số candidate thô trước reranking; artifact ghi đã chấm 50, nhưng raw pool không còn để đối chiếu. |
| `rerank_top_k` | 5 | 5 trong `reranking/config.yaml` | Giá trị mặc định đã khóa; không sửa config. |
| `result_top_k` | 10 trong `retrieval/config.yaml` | 10 trong record/artifact | Output cutoff quan sát được. Top-5 được tính bằng prefix 5 của cùng ranking Top-10 đã lưu. |

Tập chấm gồm 45 câu Dev có `review_status=source_checked`, Gold context đã xác nhận và không thuộc 30 ID official A/B. Đây là tập đã dùng trong hiệu chỉnh confidence trước đó, nên kết quả là phân tích retrieval trên Dev, không phải holdout độc lập. Không dùng Test. Metric dùng evaluator chung của repo và bootstrap cặp 10.000 lần, seed 42.

## Kết quả

| Metric | Top-5 | Top-10 | Chênh lệch Top-10 trừ Top-5 | Khoảng tin cậy 95% của chênh lệch |
|---|---:|---:|---:|---:|
| Strict Match Recall | 0.6359 | 0.7105 | +0.0747 | [+0.0389, +0.1158] |
| MRR | 0.7000 | 0.7000 | 0.0000 | [0.0000, 0.0000] |
| NDCG | 0.6244 | 0.6560 | +0.0316 | [+0.0120, +0.0533] |
| Precision | 0.3378 | 0.2067 | -0.1311 | [-0.1733, -0.0911] |
| Parent Match Recall* | 0.8845 | 0.9524 | +0.0679 | [+0.0280, +0.1149] |

`*` Parent Match Recall có metadata đủ điều kiện ở 28/45 câu. Các metric chunk được tính trên đủ 45 câu.

Top-10 tăng khả năng bao phủ gold chunk và parent; vị trí gold đầu tiên không đổi theo MRR. Precision giảm vì Top-10 thêm các candidate không liên quan. Chưa có hai lần generation ghép cặp chỉ khác output cutoff Top-5/Top-10 trên cùng câu hỏi và prompt, nên downstream grounding/citation, answer quality, kích thước context và latency đầu-cuối **chưa được đo**. Không gọi Ollama và không thay đổi official A/B.

## Quyết định và change note

- Giữ nguyên baseline official: `retrieval_top_k=50`, `rerank_top_k=5`; không sửa cấu hình đang freeze.
- Số Dev hiện có cho thấy Top-10 tăng strict recall (+0,0747), NDCG (+0,0316) và parent recall (+0,0679), giữ nguyên MRR, nhưng giảm precision (−0,1311). Đây là lợi ích/chi phí retrieval, chưa chứng minh cải thiện câu trả lời.
- Đề xuất cập nhật SRS và sơ đồ kiến trúc bằng change note để ghi rõ Top-10 là yêu cầu/nhánh experiment của output, còn Top-5 là baseline đang khóa. Không đổi cấu hình mặc định cho đến khi có run Top-10 tái lập được với candidate pool lưu trong repo và kiểm tra downstream grounding/citation.

### Change note đề xuất cho SRS, sơ đồ và config

**Trạng thái:** Đề xuất; chưa áp dụng vào official run hoặc cấu hình baseline đang khóa.

SRS và sơ đồ kiến trúc mô tả Reranker trả Top-10, trong khi baseline Sprint 6 khóa `reranker.rerank_top_k=5`. `retrieval/config.yaml` đồng thời đặt `retrieval.result_top_k=10`; `retrieval.retrieval_top_k=50` là kích thước candidate pool trước rerank. Các tên này cần được dùng theo nghĩa riêng để tránh nhầm:

- `retrieval_top_k`: số candidate lấy vào pool trước reranking.
- `rerank_top_k`: cutoff mặc định của baseline sau reranking.
- `result_top_k`: số kết quả trả ra sau reranking; có thể override riêng trong experiment.

Đề xuất giữ nguyên official A/B và baseline hiện tại (`retrieval_top_k=50`, `rerank_top_k=5`). Cập nhật SRS để nêu Top-10 là mục tiêu/nhánh experiment, còn Top-5 là baseline vận hành cho đến khi có quyết định mới. Cập nhật sơ đồ thành `Hybrid retrieval Top-50 → Cross-Encoder scores up to 50 → result cutoff K (baseline 5; experiment 10)`. Chỉ đồng bộ cấu hình, CLI/run manifest và tài liệu API sau khi có Top-10 run tái lập được, lưu raw candidate pool cùng lệnh/config hiệu lực, và đánh giá downstream grounding/citation. Nếu chốt thay đổi, phát hành version bump và change log.

Số liệu cutoff hiện có ủng hộ recall cao hơn ở Top-10 nhưng cho thấy precision giảm; vì vậy chưa đủ căn cứ để đổi baseline. Cụ thể, strict recall tăng 0,0747, NDCG tăng 0,0316, parent recall tăng 0,0679, MRR không đổi và precision giảm 0,1311. Đây là trade-off ở retrieval, chưa phải bằng chứng cải thiện câu trả lời.

## Artifact và giới hạn

- Manifest thí nghiệm: `reports/week10/topk_experiment_20261116_manifest.json`.
- Metric đầy đủ theo từng câu và bootstrap: `evaluation/results/dev/topk_cutoff_20261116_metrics.json`.
- Có thể tái lập phép tính metric Top-5/Top-10 từ Top-10 đã lưu bằng `.venv/Scripts/python.exe scripts/evaluate_topk_cutoff.py`; không thể tái lập việc tạo pool 50 và rerank nếu thiếu artifact candidate 50 cùng lệnh/config hiệu lực.
- Phép so sánh tái sử dụng ranking Top-10 đã lưu; không chạy lại Elasticsearch, Qdrant, Cross-Encoder hoặc Ollama. Do vậy đây là so sánh cutoff đầu ra có kiểm soát, không phải đo lại latency hay benchmark end-to-end mới.
- Provenance SHA của Controlled RAG B đã được hiệu chỉnh và đối chiếu; xem `controlled_rag_b_validation.md`.

## Xác minh khả năng tái chạy candidate pool và downstream

Đã kiểm tra lại trực tiếp trước khi kết luận về mức độ tái lập:

- Artifact hiện có 270 query; cả 270 record chỉ lưu 10 kết quả đầu ra. Trường `stats.scored_candidates=50` xuất hiện ở 270 record, nhưng đây là số đếm/metadata, không chứa đủ ID và điểm của 50 candidate để kiểm tra lại.
- Tất cả record tham chiếu cùng một candidate-pool file trong thư mục Temp của máy tạo artifact; file đó không tồn tại trong workspace hiện tại. Vì vậy không thể xác nhận độc lập pool 50 hay chạy lại reranker trên đúng pool.
- Môi trường hiện tại không có `ELASTICSEARCH_URL`/`QDRANT_URL`; kết nối localhost Elasticsearch `9200` và Qdrant `6333` đều thất bại. Có thư mục Qdrant local, nhưng thiếu Elasticsearch nên không thể tái lập Hybrid BM25 + Dense + RRF end-to-end.
- Không chạy Ollama theo chỉ dẫn trước đó. Vì vậy không tạo hai nhánh generation ghép cặp Top-5/Top-10; grounding, citation và answer quality downstream chưa được đo.

Kết luận sau xác minh: kết quả metric trong báo cáo vẫn là **cutoff analysis trên ranking Top-10 đã lưu**. Nó đáp ứng phần so sánh retrieval metrics và change note của D4.5; không được mô tả thành lần tái chạy candidate pool 50 hoặc bằng chứng cải thiện downstream. Bằng chứng môi trường được ghi thêm trong `topk_experiment_20261116_manifest.json`.
