# Thử nghiệm Embedding và Qdrant

## BM25 lexical retrieval

BM25 dùng thuật toán của Elasticsearch. Để nạp bộ corpus chunks chuẩn (`data/chunking_output/chunks.jsonl`) vào index, chạy từ thư mục gốc repo. Tên index, corpus và tokenizer lấy từ `bm25` và `retrieval.corpus_path` trong `retrieval/config.yaml`:

```powershell
$env:ELASTICSEARCH_URL = "http://localhost:9200"
python -m retrieval.build_bm25_index            # thêm --recreate để thay index cũ
```

Lệnh này đọc trực tiếp file chunk làm dữ liệu đầu vào; không tự parse PDF hay
chạy chunking lại. Có thể truyền file khác qua `--chunks`, index khác qua `--index`.
Mặc định không xóa index đang có; khi corpus đổi, chạy với `--recreate` sau khi đã
xác nhận có thể thay index đích. Index ghi SHA-256 của corpus; retriever báo lỗi
nếu hash này lệch corpus đang dùng. Index dùng trường `content_segmented` cùng các
trường tham chiếu điều/khoản.

## Hybrid retrieval với RRF

Hybrid gọi BM25 và Dense retrieval với cùng `candidate_k` (`retrieval.retrieval_top_k`),
sau đó hợp nhất theo thứ hạng (RRF, `hybrid.rrf_k`).
Dense search yêu cầu collection Qdrant đã được nạp bằng cùng bộ chunk và
embedding model. Ví dụ gọi từ Python:

```python
import os
from reranking.pipeline import build_hybrid_retriever, load_retrieval_settings

# Index BM25, collection Qdrant, model, candidate_k, rrf_k đều lấy từ retrieval/config.yaml;
# trả về Top-retrieval_top_k ứng viên sau RRF (chưa rerank).
settings = load_retrieval_settings("retrieval/config.yaml")
hybrid = build_hybrid_retriever(settings, elasticsearch_url=os.environ["ELASTICSEARCH_URL"])
for hit in hybrid.search("Điều kiện ly hôn đơn phương theo Điều 56"):
    print(hit["rank"], hit["chunk_id"], hit["rrf_score"], hit["source_ranks"])
```

`DenseRetriever` truyền thẳng vào `HybridRetriever`; `hybrid_search` chỉ dành cho
embedding service có `embed_query`, không nhận `DenseRetriever`.
Kết quả có `rrf_score`, `source_ranks`, `source_scores`, `retrieval_sources`,
cùng `chunk_id`, `chunk_text` và `metadata`. Có thể kiểm thử gộp mà không cần model
hay Qdrant bằng `pytest test/test_hybrid_retriever.py -v`.

## Dev set retrieval

Chạy BM25, Dense và Hybrid trên tập Dev queries. Model, index, collection, `--top-k`,
`--candidate-k`, `--rrf-k` mặc định lấy từ `retrieval/config.yaml`; chỉ truyền khi cần thử
giá trị khác:

```powershell
python -m retrieval.run_dev_retrieval --queries data/benchmark/queries_dev.json
```

## Tạo và quản lý Vector Index (`scripts/build_index.py`)

Chạy lệnh sau từ thư mục gốc của repository để lập chỉ mục từ `data/chunking_output/chunks.jsonl` vào Qdrant:

```powershell
# Model mặc định là dense.model trong retrieval/config.yaml (BAAI/bge-m3)
python scripts/build_index.py

# Hoặc chạy kiểm thử nhanh bằng chế độ Mock
python scripts/build_index.py --mock
```

Collection đã có điểm thì script dừng, trừ khi truyền `--recreate` (xóa và dựng lại toàn bộ
collection, cần khi corpus hoặc model đổi). Vector lưu tại `data/indexes/qdrant_storage/`,
metadata của collection (model, số chiều, cờ tách từ, SHA-256 corpus) tại
`data/indexes/{collection}_metadata.json`; khi mở collection để truy vấn, `DenseRetriever`
kiểm file này và báo lỗi nếu lệch cấu hình.

## Kiểm thử khói Dense Retrieval (`embedding/retrieval_smoke_test.py`)

Kiểm tra nhanh luồng truy vấn Dense vector search:

```powershell
# Xem trợ giúp CLI
python embedding/retrieval_smoke_test.py --help

# Chạy thử nghiệm khói ở chế độ Mock
python embedding/retrieval_smoke_test.py --mock
```
