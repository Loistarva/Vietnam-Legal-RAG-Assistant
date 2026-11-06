# Chọn văn bản đưa vào Cross-Encoder (`reranker.candidate_text`) trên Dev

- Ngày: 2026-11-02. Chọn: **`reranker.candidate_text: document_breadcrumb_chunk_text`** (G5).
- Dev: `data/benchmark/queries_dev.json`; chỉ chạy và chấm 75 câu có Gold đã duyệt (`gold_context_ids_confirmed`) trong `ground_truth.json`.
- Corpus: `data/chunking_output/chunks.jsonl`, 2.164 chunk, SHA-256 bắt đầu `9a72a35e532f`.
- Candidate: Hybrid Top-50 (`retrieval.retrieval_top_k`), index `bm25-e6-verified-20261101`, BGE-M3, collection `vietnam_legal_chunks`, `rrf_k` 60, `as_of_date` của từng câu. Cả ba lượt rerank dùng cùng một file candidate, chỉ khác `candidate_text`. Với `rrf_k` 10, Top-50 là cùng tập chunk ở 270/270 câu ([`rrf_k_comparison_dev_75.md`](../../retrieval/evaluation/rrf_k_comparison_dev_75.md)), nên kết quả rerank không đổi.
- Reranker: `BAAI/bge-reranker-v2-m3`, `max_candidates` 50, `max_length` 512, CPU float32. Số đo ở Top-5 và Top-10 sau rerank; chấm bằng `evaluation.metrics.evaluate` (Recall theo tỉ lệ Gold, MRR, NDCG nhị phân).
- Kết quả từng câu: [`candidate_text_dev_75.csv`](candidate_text_dev_75.csv).

## Ba cách ghép văn bản

| `candidate_text` | Văn bản đưa vào Cross-Encoder |
| --- | --- |
| `chunk_text` | Chỉ nội dung chunk, ví dụ `2. Chính phủ quy định chi tiết khoản 1 Điều này.` |
| `breadcrumb_chunk_text` | Breadcrumb (Chương > Điều N. Tên Điều > Khoản), xuống dòng, rồi `chunk_text` |
| `document_breadcrumb_chunk_text` | Tên và số hiệu văn bản (`Luật Hôn nhân và gia đình 2014 (52/2014/QH13)`, `Nghị định 126/2014/NĐ-CP: Quy định chi tiết…`), breadcrumb, rồi `chunk_text` |

## Quy tắc chọn

So ghép cặp trên 75 câu (bootstrap 10.000 lần, CI95). Chọn cách có Recall@10 và MRR@10 không kém Hybrid không rerank và hơn các cách còn lại; nếu không phân biệt được thì giữ cách ngắn hơn.

## Kết quả (75 câu Dev đã duyệt)

| Metric | Hybrid (không rerank) | `chunk_text` | `breadcrumb_chunk_text` | **`document_breadcrumb_chunk_text`** |
| --- | ---: | ---: | ---: | ---: |
| Recall@5 | 0.6769 | 0.5623 | 0.7058 | **0.7335** |
| MRR@5 | 0.6938 | 0.5498 | 0.6987 | **0.7482** |
| NDCG@5 | 0.6315 | 0.4982 | 0.6544 | **0.6981** |
| Recall@10 | 0.7395 | 0.6499 | 0.7837 | **0.7921** |
| MRR@10 | 0.6973 | 0.5604 | 0.7009 | **0.7482** |
| NDCG@10 | 0.6600 | 0.5382 | 0.6891 | **0.7240** |

So ghép cặp (chênh lệch trung bình, CI95, số câu hơn / kém):

| So sánh | Recall@10 | MRR@10 | NDCG@10 |
| --- | --- | --- | --- |
| `breadcrumb_chunk_text` − `chunk_text` | +0.134 [+0.078, +0.198], 20 / 0 | +0.141 [+0.069, +0.217], 23 / 9 | +0.151 [+0.089, +0.216], 31 / 10 |
| `breadcrumb_chunk_text` − Hybrid | +0.044 [0.000, +0.093], 10 / 6 | +0.004 [−0.084, +0.091], 16 / 15 | +0.029 [−0.035, +0.096], 26 / 19 |
| `document_breadcrumb_chunk_text` − `breadcrumb_chunk_text` | +0.008 [−0.010, +0.030], 4 / 2 | +0.047 [+0.006, +0.096], 9 / 3 | +0.035 [+0.008, +0.066], 20 / 9 |
| `document_breadcrumb_chunk_text` − Hybrid | +0.053 [+0.007, +0.103], 11 / 4 | +0.051 [−0.021, +0.127], 16 / 12 | +0.064 [+0.007, +0.124], 26 / 18 |

`chunk_text` (giá trị khởi đầu) làm Hybrid kém đi rõ rệt. Ở 24 câu có MRR@10 thấp hơn Hybrid, chunk đứng đầu sau rerank thuộc văn bản khác ở 11 câu và thuộc Điều khác của đúng văn bản ở 12 câu: câu hỏi thường nêu tên văn bản ("theo Nghị định 126/2014/NĐ-CP", "Luật Hôn nhân và gia đình 2000") và tên Điều ("điều kiện mang thai hộ", "hòa giải tại Tòa án"), còn chunk con thường chỉ là một Khoản bắt đầu bằng "2. …". Breadcrumb thêm tên Điều: số câu có MRR@10 thấp hơn Hybrid còn 15 (9 câu top-1 sai văn bản, 5 câu sai Điều); thêm tên văn bản: còn 12 (6 sai văn bản, 5 sai Điều). Với `document_breadcrumb_chunk_text`, Hybrid + Reranker hơn Hybrid ở Recall@10 và NDCG@10 (CI95 không chứa 0); MRR@10 tăng nhưng chưa phân biệt được.

Latency rerank (trung vị mỗi câu, 50 candidate, CPU 20 luồng, float32): 29,1 s (`chunk_text`), 27,0 s (`breadcrumb_chunk_text`), 30,0 s (`document_breadcrumb_chunk_text`). Trên GPU float16, 50 candidate mất khoảng 0,4 s (đo ngày 27/10). Văn bản dài thêm không làm đổi bậc latency, nên không dùng latency để chọn.

## Tái lập

```powershell
# 1. Hybrid Top-50 (một lần), ghi dev_hybrid.json
python -m retrieval.run_dev_retrieval --elasticsearch-url http://localhost:9200 --top-k 50 --output-dir <top50>
# 2. 75 câu Dev đã duyệt
python -c "import json; from pathlib import Path; from retrieval.retrieval_evaluation import gold_dev_records; r, _ = gold_dev_records(Path('data/benchmark/queries_dev.json'), Path('data/benchmark/ground_truth.json')); Path('<dir>/dev_reviewed_queries.json').write_text(json.dumps([{'id': x['id'], 'question': x['question'], 'as_of_date': x['as_of_date']} for x in r], ensure_ascii=False), encoding='utf-8')"
# 3. Mỗi giá trị candidate_text: chép reranking/config.yaml thành <cfg>, đổi candidate_text, rồi
python scripts/run_retrieval.py --queries <dir>/dev_reviewed_queries.json --retriever precomputed `
  --candidates <top50>/dev_hybrid.json --config <cfg> --no-parent-context --top-k 10 `
  --output <dir>/rerank.json --eval-output <dir>/rerank_eval.json
python -c "from evaluation.metrics import evaluate; evaluate('<dir>/rerank_eval.json', 'data/benchmark/ground_truth.json', ks=(5, 10))"
```

File candidate và output rerank (khoảng 33 MB và 2 MB mỗi lượt) không commit. Lượt `chunk_text` chạy trước 1bc3f07 nên output mang nhãn `precomputed_reranker` thay cho `hybrid_reranker`; thứ hạng không bị ảnh hưởng.

Giới hạn: chỉ 75 câu Dev có Gold đã duyệt; nhãn chưa được chuyên gia pháp lý thẩm định; một model reranker, một `max_length`. Đánh giá lại khi duyệt thêm câu Dev. Không dùng kết quả Dev để tuyên bố hiệu năng trên Test.
