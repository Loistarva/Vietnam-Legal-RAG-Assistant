# Tái lập benchmark Retrieval Tuần 7

## Dữ liệu và index đã dùng

- Dev: `data/benchmark/queries_dev.json` (285 query). Nhãn duy nhất: `data/benchmark/gold_id_proposals_300.json`; metric chunk-level tính trên 267 query có nhãn khớp, loại 18 query chỉ có `version_*` không có trong corpus.
- Chunking E: `retrieval/results/dev_tuning/chunking_variants/E/chunks.jsonl` (1.923 chunks), parents ở cùng thư mục. Parent 1.500 ký tự, child 256 tokens / 350 units / tối thiểu 30 từ; fallback overlap 40 từ (giữ cố định, chỉ áp dụng khi fallback window).
- Elasticsearch: `legal-child-chunks-dev-cfge`; Qdrant collection: `vietnam_legal_dev_cfge`, storage ở `retrieval/results/dev_tuning/chunking_variants/E/vector_index/qdrant_storage`.
- Embedding: `bkai-foundation-models/vietnamese-bi-encoder`, 768 chiều; Qdrant index metadata ghi nhận 1.792 vector dùng lại từ collection gốc theo `embed_text` giống hệt và chỉ tạo mới 131 vector.
- BM25 và Dense mỗi nhánh lấy Top-50; RRF k=60; trọng số Dev chọn cho E là BM25 0,35 / Dense 0,65.

## Lệnh tái lập

Từ PowerShell ở thư mục gốc dự án, sau khi Elasticsearch và Qdrant chứa đúng các index nêu trên:

```powershell
$env:QDRANT_PATH = "retrieval/results/dev_tuning/chunking_variants/E/vector_index/qdrant_storage"
python -m retrieval.run_dev_retrieval `
  --queries data/benchmark/queries_dev.json `
  --chunks retrieval/results/dev_tuning/chunking_variants/E/chunks.jsonl `
  --model bkai-foundation-models/vietnamese-bi-encoder `
  --collection vietnam_legal_dev_cfge `
  --elasticsearch-url http://localhost:9200 `
  --elasticsearch-index legal-child-chunks-dev-cfge `
  --output-dir retrieval/results/dev_tuning/chunking_variants/E/results `
  --top-k 50 --candidate-k 50 --rrf-k 60 `
  --bm25-weight 0.35 --dense-weight 0.65
```

Quét trọng số và tổng hợp các phương án chunking chỉ trên Dev:

```powershell
python scripts/evaluate_dev_rrf_weights.py `
  --queries data/benchmark/queries_dev.json `
  --labels data/benchmark/gold_id_proposals_300.json `
  --chunks retrieval/results/dev_tuning/chunking_variants/E/chunks.jsonl `
  --bm25 retrieval/results/dev_tuning/chunking_variants/E/results/dev_bm25.json `
  --dense retrieval/results/dev_tuning/chunking_variants/E/results/dev_dense.json `
  --hybrid retrieval/results/dev_tuning/chunking_variants/E/results/dev_hybrid.json `
  --label-mapping retrieval/results/dev_tuning/chunking_variants/label_mapping.json `
  --variant E --output retrieval/results/dev_tuning/chunking_variants/E/rrf_weight_sweep.json `
  --top-k 5 --candidate-k 50 --rrf-k 60 --step 0.05
python scripts/evaluate_dev_chunking_variants.py
python scripts/measure_dev_retrieval_latency.py
python scripts/evaluate_dev_cross_encoder.py --variant E --bm25-weight 0.35 --dense-weight 0.65 --rrf-k 60 --candidate-k 50 --top-k 5
```

Chạy pipeline tích hợp cho truy vấn thủ công (config mặc định trả Top-10 sau Cross-Encoder và parent context):

```powershell
python scripts/run_retrieval.py --query "Điều kiện áp dụng là gì?" --retriever hybrid --elasticsearch-url http://localhost:9200
```

`retrieval/config.yaml` và `reranking/config.yaml` là cấu hình hiện hành. `scripts/measure_dev_retrieval_latency.py` ghi latency BM25/Dense/Hybrid riêng. `scripts/evaluate_dev_cross_encoder.py` có thể tạo `retrieval/results/dev_tuning/chunking_variants/E/dev_cross_encoder.json` khi chạy đủ Dev; báo cáo chính thức hiện chưa có metric Cross-Encoder tổng hợp toàn Dev. Lượt Test đầu dùng Config A trước khi Dev chọn E; sau khi khóa E đã có một lượt đánh giá lại trên cùng Test như ghi dưới đây.

Sau khi khóa Config E trên Dev, đã chạy lượt đánh giá lại một lần trên cùng `queries_test.json` bằng `scripts/evaluate_test_config_e.py`. Đây là Test lặp lại sau lượt Config A trước đó, không phải tập kiểm thử độc lập mới; không dùng kết quả này để tune. Script lưu báo cáo, metric theo query, ánh xạ nhãn sang chunk E và danh sách Top-50/Top-10 tại `retrieval/results/test_run/config_e_final/`; mặc định từ chối ghi đè các file kết quả đã tồn tại.

Lệnh tái lập lượt Config E (chỉ chạy lại khi chủ động chấp nhận dùng lại Test):

```powershell
python scripts/evaluate_test_config_e.py --output-dir retrieval/results/test_run/config_e_repeat
```

## Giới hạn tái lập

`gold_id_proposals_300.json` còn proposal provisional. Việc ánh xạ nhãn sang chunk B/C/E dựa trên span text cùng `clause_id`; không đọc `ground_truth.json`. Latency riêng BM25/Dense/Hybrid của E được đo trên đủ 285 Dev query ở trọng số cuối 0,35/0,65; latency A/B/C là số đo từ lượt truy xuất trước ở 0,65/0,35. Metric Hybrid được tính lại từ cùng Top-50 BM25/Dense theo trọng số Dev đã chọn. Tokenizer embedding có giới hạn 256 token; cấu hình E có 74/1.923 chunks vượt giới hạn và bị truncation khi embed.
