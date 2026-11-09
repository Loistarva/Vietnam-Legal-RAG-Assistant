# Hiệu chỉnh ngưỡng tin cậy (D5.2) — `conf_v1_20261109`

Owner: Dev 5. Reviewer theo kế hoạch: Dev 2 + Tech Lead. Ngày chạy: 09/11/2026 (hạn 05/11 trong kế hoạch V3 đã qua).

Kết quả chốt, ghi trong [reranking/confidence.yaml](../../reranking/confidence.yaml):

| Khoá | Giá trị |
| --- | --- |
| `min_top1_score` | 0.5: điểm reranker hạng 1 thấp hơn mức này thì từ chối, không gọi LLM |
| `min_evidence_score` | 0.1: kết quả trong Top-5 thấp hơn mức này bị bỏ khỏi ngữ cảnh |
| `threshold_config_version` | `conf_v1_20261109` |

Bộ lọc chạy trong [orchestration/rag_pipeline.py](../../orchestration/rag_pipeline.py), sau Cross-Encoder và trước Parent-Context Resolver, đúng vị trí "Confidence Threshold Filter" trong sơ đồ kiến trúc. LLM Judge và MMR đang tắt theo kế hoạch V3.

## Dữ liệu (chỉ Dev, không đọc Test)

| Nhóm | Số câu | Nguồn | SHA-256 |
| --- | --- | --- | --- |
| Câu Dev trả lời được | 45 | Các câu `source_checked` trong [data/benchmark/queries_dev.json](../../data/benchmark/queries_dev.json), trừ 30 ID official trong [evaluation/manifests/dev_gold_30_manifest.json](../../evaluation/manifests/dev_gold_30_manifest.json) | Danh sách ID `4d7169b7…`; artifact G3 [retrieval/results/dev_hybrid_reranker.json](../../retrieval/results/dev_hybrid_reranker.json) `738a07c6…` |
| Câu âm v2 của Dev 1 | 26 | [evaluation/negative_set/dev_negative_queries_v2.jsonl](../../evaluation/negative_set/dev_negative_queries_v2.jsonl) | `e571c583…`; artifact rerank [confidence_calibration/neg_v2_hybrid_reranker.json](confidence_calibration/neg_v2_hybrid_reranker.json) `f308d29a…` |

Corpus của cả hai artifact là `7105c484…`, cùng index ES `bm25-e6-verified-20261101` và Qdrant `vietnam_legal_chunks` (BGE-M3). Cấu hình: `rrf_k` 60, Top-50 vào `BAAI/bge-reranker-v2-m3`, `candidate_text=document_breadcrumb_chunk_text`, `rerank_top_k` 5. Câu âm chạy hai bước như G3: Hybrid Top-50 với `--reranker none --no-parent-context`, sau đó `--retriever precomputed --reranker cross_encoder`. Toàn bộ hash và điểm từng câu nằm trong [confidence_calibration/sweep.json](confidence_calibration/sweep.json).

## Cách đo

Với mỗi cặp `min_top1_score` × `min_evidence_score`:

- **Từ chối sai**: câu trả lời được bị từ chối dù chunk gold có trong Top-5 (mất thật).
- **Từ chối khi retrieval đã trượt**: câu trả lời được bị từ chối, nhưng không có gold trong Top-5. Trường hợp này từ chối là có lợi, vì LLM chỉ còn ngữ cảnh sai.
- **Đúng bị loại**: chunk gold trong Top-5 bị ngưỡng bằng chứng loại khỏi ngữ cảnh.
- **Câu âm lọt**: câu âm vẫn đi tới LLM, tính theo từng nhãn.

## Kết quả quét (trích, `min_evidence_score` = 0.1)

| `min_top1_score` | Từ chối sai (gold trong Top-5) | Từ chối khi đã trượt | Đúng bị loại | non_legal lọt /6 | ngoài phạm vi lọt /8 | thiếu nguồn lọt /6 | thiếu dữ kiện lọt /6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tắt (0, 0) | 0 | 0 | 0 | 6 | 8 | 6 | 6 |
| 0.1 | 0 | 0 | 0 | 0 | 2 | 6 | 6 |
| 0.3 | 0 | 0 | 0 | 0 | 1 | 5 | 5 |
| **0.5** | **0** | **1** (HN_210) | **0** | **0** | **1** | **5** | **5** |
| 0.6 | 0 | 1 | 0 | 0 | 1 | 4 | 5 |
| 0.7 | 0 | 1 | 0 | 0 | 1 | 3 | 4 |
| 0.8 | 2 (HN_008, HN_282) | 2 | 0 | 0 | 1 | 1 | 4 |
| 0.9 | 5 | 3 | 0 | 0 | 1 | 1 | 4 |

Ngưỡng bằng chứng: 0.1 không loại chunk gold nào; 0.2 loại 1 chunk gold (HN_056, điểm 0.165); 0.3 loại 3.

## Lý do chọn

- Điểm top-1 thấp nhất của câu trả lời được có gold trong Top-5 là 0.731 (HN_008). Điểm cao nhất của nhóm câu âm tách rõ là 0.281 (NEG_DEV_013). 0.5 nằm khoảng giữa hai mức, cách mỗi bên khoảng 0.22.
- 0.7 chặn thêm 2 câu thiếu nguồn, nhưng chỉ cách HN_008 0.03. Với 45 câu, khoảng cách đó dễ là khớp riêng mẫu nên không chọn. Từ 0.8 bắt đầu từ chối sai.
- 0.5 còn chặn HN_210: câu này không có gold trong Top-5, top-1 chỉ 0.369.

## Giới hạn

1. **Ngưỡng không giải quyết nhóm thiếu nguồn: 5/6 câu vẫn lọt.** Corpus có văn bản dẫn chiếu gần chủ đề (ví dụ NEG_DEV_016 có top-1 0.953 từ TT 04/2020/TT-BTP). Nhóm này phải dựa vào việc LLM tự từ chối (`abstained`) và Grounding Gate. Đây đúng là điều README tập âm đã cảnh báo.
2. **Nhóm thiếu dữ kiện (5/6 lọt) là đúng ý đồ.** Các câu này cần hỏi lại, không cần từ chối. Gate đã có nhánh `NEEDS_CLARIFICATION`, nhưng cần chạy Qwen thật mới biết model có bật cờ này hay không.
3. **Nhóm non-legal và ngoài phạm vi là việc của router (D4.5).** Ngưỡng chỉ là lớp chặn sau. NEG_DEV_025 (0.903) là case ranh giới đang chờ Tech Lead chốt nhãn.
4. **Kiểm tra sau khi chốt trên 30 câu official** (không dùng để chọn ngưỡng): 1/30 bị từ chối. Đó là HN_035, câu hỏi tiền đề sai ("Luật 2000 vẫn cấm kết hôn cùng giới đúng không?"). Chunk gold `l_52_2014_qh13_art_8_clause_2_chunk_1` đứng hạng 1 nhưng chỉ có điểm 0.087, vì cross-encoder chấm thấp đoạn trái với tiền đề câu hỏi. Mọi ngưỡng trên 0.087 đều từ chối câu này. Không chỉnh ngưỡng theo câu official. Cần báo Dev 2 để phân tích Run B.
5. Mẫu nhỏ: 45 câu dương, 26 câu âm. Nhãn tập âm v2 vẫn ở trạng thái `pending_peer_review`. Khi tập âm, corpus hoặc artifact G3 đổi, phải chạy lại script và tăng `threshold_config_version`.

## Chạy lại

```powershell
python scripts/calibrate_confidence_threshold.py `
  --negatives-artifact reports/retrieval/confidence_calibration/neg_v2_hybrid_reranker.json `
  --output reports/retrieval/confidence_calibration/sweep.json
```

Script chỉ đọc Dev, artifact G3 và tập âm. Nó dừng nếu artifact câu âm khác tập câu âm (về ID, câu hỏi hoặc `as_of_date`).
