# So sánh model Dense trên Dev (E2)

- Ngày: 2026-11-07. Chọn: **`dense.model: BAAI/bge-m3`** (giữ giá trị trong `retrieval/config.yaml`).
- Dev: `data/benchmark/queries_dev.json`, 270 câu đã chạy retrieval; chỉ chấm 75 câu có Gold đã duyệt (`gold_context_ids_confirmed`) trong `ground_truth.json`.
- Corpus: `data/chunking_output/chunks.jsonl`, 2.164 chunk, SHA-256 (CRLF → LF) bắt đầu `080f1607e5c9`, có `effective_to` cấp Điều/Khoản theo `data/reference/provision_periods.json` (D1). Sau đó corpus thêm các văn bản sửa đổi Nghị định 123/2015, Thông tư 04/2020 (2.322 chunk, `c18239351424`); Dense BGE-M3 trên corpus mới giữ Recall@10 0.7685, MRR@10 0.6607 nên không chọn lại.
- Ba model trong `dense.supported_models`, mỗi model một collection Qdrant dựng bằng `scripts/build_index.py` từ cùng corpus, cùng `embed_text_raw`:
  - `BAAI/bge-m3` (1024 chiều, không tách từ), collection `vietnam_legal_chunks`;
  - `bkai-foundation-models/vietnamese-bi-encoder` (768 chiều, tách từ underthesea 9.5.0 cả câu hỏi và chunk), collection `e2_bkai`;
  - `AITeamVN/Vietnamese_Embedding` (1024 chiều, không tách từ), collection `e2_aiteamvn`.
- Cùng Elasticsearch index `bm25-e6-verified-20261101`, mỗi nhánh 50 candidate, RRF k = 60, Top-10, `as_of_date` của từng câu. Kết quả BGE-M3 là bộ chính: [`../results/`](../results/), [`retrieval_report.md`](retrieval_report.md).

## Quy tắc chọn

Theo đề xuất E2: so ghép cặp trên 75 câu (bootstrap 10.000 lần theo câu, seed 20261107; sign test hai phía). Chỉ đổi model khi model khác hơn BGE-M3 có ý nghĩa thống kê trên Hybrid, vì Hybrid là đầu vào của reranker. Nếu không phân biệt được thì giữ BGE-M3.

## Kết quả (75 câu Dev đã duyệt)

| Nhánh | Model | Recall@5 | Recall@10 | MRR@10 | nDCG@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| Dense | BGE-M3 | 0.6508 | 0.7685 | 0.6607 | 0.6570 |
| Dense | bkai | 0.5648 | 0.7179 | 0.6067 | 0.5967 |
| Dense | AITeamVN | 0.7086 | 0.7858 | 0.7122 | 0.6947 |
| Hybrid | BGE-M3 | 0.6769 | 0.7528 | 0.7136 | 0.6723 |
| Hybrid | bkai | 0.6621 | 0.7551 | 0.6949 | 0.6680 |
| Hybrid | AITeamVN | 0.6876 | 0.7764 | 0.7053 | 0.6898 |

Chênh lệch so với BGE-M3 (model − BGE-M3; CI95 bootstrap; số câu hơn / kém; p của sign test):

| Nhánh | Model | Recall@10 | MRR@10 | nDCG@10 |
| --- | --- | --- | --- | --- |
| Dense | bkai | −0.051 [−0.111; +0.007], 5/14, p = 0,064 | −0.054 [−0.147; +0.036], 13/20, p = 0,30 | −0.060 [−0.134; +0.009], 18/29, p = 0,14 |
| Dense | AITeamVN | +0.017 [−0.035; +0.070], 7/3, p = 0,34 | +0.052 [−0.023; +0.127], 16/10, p = 0,33 | +0.038 [−0.022; +0.098], 23/14, p = 0,19 |
| Hybrid | bkai | +0.002 [−0.042; +0.042], 9/5, p = 0,42 | −0.019 [−0.089; +0.048], 13/13, p = 1,0 | −0.004 [−0.060; +0.047], 23/18, p = 0,53 |
| Hybrid | AITeamVN | +0.024 [−0.018; +0.060], 8/1, p = 0,039 | −0.008 [−0.059; +0.039], 8/6, p = 0,79 | +0.018 [−0.024; +0.055], 21/12, p = 0,16 |

Mọi CI95 đều chứa 0. Sign test của Hybrid AITeamVN ở Recall@10 (8 câu hơn, 1 câu kém) có p = 0,039, nhưng đây là 1 trong 16 phép so (Holm/Bonferroni: không còn ý nghĩa) và CI95 bootstrap vẫn chứa 0; MRR@10 của Hybrid AITeamVN thấp hơn BGE-M3. Vì vậy **giữ BGE-M3**. AITeamVN là bản tinh chỉnh từ BGE-M3, cùng kích thước, nên đổi sang cũng không giảm chi phí. bkai nhanh hơn (dựng index 82 giây so với 116 giây trên RTX 3050 Ti) nhưng Dense kém hơn ở cả bốn metric.

Latency ghi trong file kết quả (`latency_ms`, trung vị 270 câu: BGE-M3 1.618 ms, AITeamVN 1.620 ms, bkai 624 ms) gồm cả bước tìm kiếm của Qdrant chạy local mode có lọc theo thời điểm, nên không dùng để so model.

## Tái lập

```powershell
$env:HF_HUB_OFFLINE = "1"   # model đã có trong cache
python scripts/build_index.py --recreate
python scripts/build_index.py --recreate --model bkai-foundation-models/vietnamese-bi-encoder --collection e2_bkai
python scripts/build_index.py --recreate --model AITeamVN/Vietnamese_Embedding --collection e2_aiteamvn
python -m retrieval.run_dev_retrieval --queries data/benchmark/queries_dev.json
python -m retrieval.run_dev_retrieval --queries data/benchmark/queries_dev.json --model bkai-foundation-models/vietnamese-bi-encoder --collection e2_bkai --output-dir <thư mục bkai>
python -m retrieval.run_dev_retrieval --queries data/benchmark/queries_dev.json --model AITeamVN/Vietnamese_Embedding --collection e2_aiteamvn --output-dir <thư mục aiteamvn>
```

Chỉ commit kết quả BGE-M3; hai bộ kết quả còn lại (khoảng 18 MB mỗi model) không commit. Các metric từng câu tính bằng `evaluation.metrics.score_question` trên `gold_context_ids` đã xác nhận.

Giới hạn: chỉ 75 câu Dev có Gold đã duyệt, nên chênh lệch cỡ 0,02–0,05 khó phân biệt; nhãn chưa được chuyên gia pháp lý thẩm định. Chưa so Hybrid + Reranker theo từng model. Đánh giá lại khi duyệt thêm câu Dev. Không dùng Test để chọn model.
