# Vietnam Legal RAG Assistant

Dự án RAG hỗ trợ truy xuất và hỏi đáp trên văn bản pháp luật Hôn nhân và Gia đình Việt Nam. Pipeline gồm: Parser → Chunking → BM25 (Elasticsearch) và Dense (Qdrant) → Hybrid RRF → Reranker.

## Cấu trúc repo

| Thư mục / file | Nội dung | Owner Sprint 6 |
| --- | --- | --- |
| `parser/`, `chunking/` | Bóc tách văn bản và chia chunk cha–con (Sprint 5, giữ nguyên) | — |
| `schemas/`, `data/benchmark/` | Schema dùng chung, câu hỏi Dev/Test, ground truth | Dev 1 |
| `evaluation/` | BM25 baseline, Zero-shot LLM, metric Recall/MRR/NDCG | Dev 2 |
| `embedding/`, `scripts/build_index.py` | Dense retriever, vector store Qdrant, tạo index | Dev 3 |
| `retrieval/` | BM25 Elasticsearch, RRF, `HybridRetriever` | Dev 4 |
| `reranking/`, `scripts/run_retrieval.py` | Reranker, pipeline Hybrid + Reranker, CLI | Dev 5 |
| `test/` | Unit test và integration test | Từng owner |
| `docs/` | Báo cáo và hướng dẫn | Từng owner |

## Cài đặt

Dùng Python 3.12. Mỗi thành viên tự tạo môi trường ảo; thư mục `.venv*` không được đưa lên Git.

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
```

Tất cả dependency được gom vào `requirements.txt`. Các lệnh bên dưới dùng `python`, giả định môi trường ảo đã được kích hoạt bằng `.\.venv312\Scripts\Activate.ps1`.

## Chạy nhanh Hybrid + Reranker

```powershell
# Mặc định theo sơ đồ kiến trúc: Elasticsearch BM25 + Qdrant + RRF, rồi Cross-Encoder bge-reranker-v2-m3
python scripts/run_retrieval.py --query "Điều kiện kết hôn theo quy định pháp luật là gì?" --top-k 5 `
  --elasticsearch-url http://localhost:9200
# Offline, không cần dịch vụ hay model (thứ hạng không có ý nghĩa ngữ nghĩa)
python scripts/run_retrieval.py --query "Điều kiện kết hôn theo quy định pháp luật là gì?" --top-k 5 `
  --retriever mock --reranker mock
```

Lệnh in JSON theo contract Retrieval result (`query_id`, `retriever`, `results` có `chunk_id`, `rank`, `score`, `chunk_text`, `parent_clause_id`, `document_id`, `metadata.validity_status`, …). Lần chạy dùng mock scorer mang nhãn `<retriever>_mock_reranker`. Cách chạy hai bước khi máy không đủ bộ nhớ cho cả model dense và reranker: xem [docs/sprint6_integration.md](docs/sprint6_integration.md).

## Quy trình đầy đủ

| Bước | Lệnh | Hướng dẫn chi tiết |
| --- | --- | --- |
| 1. Khởi chạy Elasticsearch | `docker compose up -d` | [retrieval/retrieval.md](retrieval/retrieval.md) |
| 2. Tạo BM25 index | `python -c "from retrieval.build_bm25_index import build_bm25_index; build_bm25_index(chunks_file='data/chunking_output/chunks.jsonl')"` | [retrieval/retrieval.md](retrieval/retrieval.md) |
| 3. Tạo vector index | `python scripts/build_index.py --input data/chunking_output/chunks.jsonl` | [docs/embedding_experiment.md](docs/embedding_experiment.md) |
| 4. Baseline trên Dev | `python scripts/run_baselines.py` | `evaluation/` |
| 5. So sánh BM25 / Dense / Hybrid trên Dev | `python -m retrieval.run_dev_retrieval --elasticsearch-url http://localhost:9200 ...` | [docs/retrieval_report.md](docs/retrieval_report.md) |
| 6. Hybrid + Reranker | `python scripts/run_retrieval.py --query "..." --elasticsearch-url http://localhost:9200` | [docs/sprint6_integration.md](docs/sprint6_integration.md) |
| 7. Kiểm thử | `python -m pytest test/` (chạy từ thư mục gốc repo) | — |
| 8. Test chính thức (sau khi khóa dữ liệu, model, tham số và commit) | `python scripts/run_final_test.py` | — |

Tham số chỉ được tuning trên Dev set. Test set đã đóng băng và chỉ dùng cho một lần đánh giá chính thức; `scripts/run_retrieval.py` từ chối chạy trên Test set nếu không có `--allow-test-split`.

## Cấu hình

- `retrieval/config.yaml` (Dev 4): `retrieval_top_k`/`candidate_k` (mặc định 50), `rrf_k` (60), index và dense model.
- `reranking/config.yaml` (Dev 5): `rerank_top_k` (5), `max_candidates` (50), `backend` (`cross_encoder` mặc định | `mock` cho test), `model` (`BAAI/bge-reranker-v2-m3`), `dtype` (`auto`: float16 trên GPU).

Đây là giá trị khởi đầu, chưa phải cấu hình tối ưu.

## Kết quả hiện tại

Task 4 đã chạy lại trên 285 câu Dev với corpus 1.159 chunk, dùng `gold_id_proposals_300.json` làm nhãn tạm. Ở cấp chunk, Hybrid dẫn đầu (Recall@10 0.7407); ở cấp Điều, Dense dẫn đầu (Recall@10 0.7846). Phần lớn nhãn proposal chưa được xác minh, nên các số này chỉ mang tính thử nghiệm. Xem [báo cáo Task 4](docs/retrieval_report.md). Hybrid + Reranker chưa có số đo trên Dev set với model thật.
