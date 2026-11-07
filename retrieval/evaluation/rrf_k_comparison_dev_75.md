# So sánh rrf_k = 10 và rrf_k = 60 trên Dev

- Ngày: 2026-11-02. Chọn: **`hybrid.rrf_k: 60`** (giữ giá trị khởi đầu).
- Dev: `data/benchmark/queries_dev.json`, 270 câu đã chạy retrieval; chỉ chấm 75 câu có Gold đã duyệt (`gold_context_ids_confirmed`) trong `ground_truth.json`.
- Corpus: `data/chunking_output/chunks.jsonl`, 2.164 chunk, SHA-256 bắt đầu `9a72a35e532f`.
- Cùng Elasticsearch index `bm25-e6-verified-20261101`, BGE-M3 1024 chiều, Qdrant collection `vietnam_legal_chunks`, mỗi nhánh 50 candidate, `as_of_date` của từng câu. Hai lượt chỉ khác `rrf_k`; nhánh BM25 và Dense cho cùng thứ hạng ở 270/270 câu.
- Kết quả chính (rrf_k = 60): [`retrieval_report.md`](retrieval_report.md), [`../results/`](../results/).

## Quy tắc chọn

Trong pipeline, RRF đưa Top-50 (`retrieval.retrieval_top_k`) vào Cross-Encoder Reranker, nên `rrf_k` được chọn theo các candidate vào reranker (Recall@50), có xem thêm Top-5/10/20. So ghép cặp trên 75 câu (bootstrap 10.000 lần, sign test). Nếu không phân biệt được hai giá trị thì giữ 60.

## Kết quả Hybrid (75 câu Dev đã duyệt)

| Metric | rrf_k = 10 | rrf_k = 60 | Chênh lệch 10 − 60 | CI95 | Câu 10 hơn / 60 hơn |
| --- | ---: | ---: | ---: | --- | ---: |
| Recall@5 | 0.6725 | 0.6769 | −0.0044 | −0.017 đến +0.005 | 1 / 2 |
| Recall@10 | 0.7617 | 0.7395 | +0.0222 | −0.002 đến +0.058 | 3 / 1 |
| MRR@10 | 0.7033 | 0.6973 | +0.0059 | −0.005 đến +0.018 | 6 / 2 |
| Recall@20 | 0.8432 | 0.8263 | +0.0169 | −0.005 đến +0.044 | 3 / 2 |
| **Recall@50** | **0.8753** | **0.8753** | **0** | 0 đến 0 | **0 / 0** |

Không chênh lệch nào có ý nghĩa thống kê (sign test p ≥ 0,11). Top-50 của hai giá trị là **cùng một tập chunk ở 270/270 câu Dev**; chỉ thứ tự bên trong khác. Reranker chấm từng candidate độc lập, nên với Hybrid + Reranker hai giá trị cho cùng kết quả. Chênh lệch R@10 gần như chỉ do HN_035: Dense xếp gold ở hạng 1, BM25 không có; gold đứng hạng 7 với rrf_k = 10 và hạng 15 với rrf_k = 60, vẫn trong Top-50 ở cả hai.

Latency Hybrid (trung vị trên 270 câu, CPU) phụ thuộc chủ yếu vào bước mã hoá câu hỏi của BGE-M3; RRF trên tối đa 100 phần tử không đáng kể, nên không dùng latency để chọn `rrf_k`.

## Tái lập

```powershell
python -m retrieval.run_dev_retrieval --elasticsearch-url http://localhost:9200 --rrf-k 10 --top-k 50 --output-dir <thư mục k10>
python -m retrieval.run_dev_retrieval --elasticsearch-url http://localhost:9200 --rrf-k 60 --top-k 50 --output-dir <thư mục k60>
```

Hai lượt Top-10 ban đầu (7653709) chạy lại trên máy khác, với index dựng mới từ `retrieval/config.yaml`, cho cùng thứ hạng ở 270/270 câu cho cả ba phương pháp. File Top-50 không commit (khoảng 33 MB mỗi lượt); chạy lại bằng lệnh trên khi cần làm candidate cho reranker hai bước.

Giới hạn: chỉ 75 câu Dev có Gold đã duyệt; nhãn chưa được chuyên gia pháp lý thẩm định. Đánh giá lại khi duyệt thêm câu Dev. Không dùng kết quả Dev để tuyên bố hiệu năng trên Test.
