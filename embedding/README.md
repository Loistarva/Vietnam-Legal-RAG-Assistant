# Thử nghiệm Embedding và Qdrant

## BM25 lexical retrieval

BM25 dùng thuật toán của Elasticsearch. Để nạp bộ corpus chunks chuẩn (`data/chunking_output/chunks.jsonl`) vào index, đặt URL và tên index (mặc định là `legal-child-chunks-dev`), sau đó chạy từ thư mục gốc repo:

```python
from retrieval.build_bm25_index import build_bm25_index

stats = build_bm25_index(
    chunks_file="data/chunking_output/chunks.jsonl",
    es_url="http://localhost:9200",
    index_name="legal-child-chunks-dev",
)
print(stats)
```

Lời gọi này đọc trực tiếp file chunk làm dữ liệu đầu vào; không tự parse PDF hay
chạy chunking lại. Có thể truyền file khác qua `chunks_file`. Mặc định hàm không
xóa index đang có; nếu cần build lại từ đầu, truyền `recreate=True` sau khi đã
xác nhận có thể thay index đích. Index dùng trường `content_segmented` cùng các
trường tham chiếu điều/khoản.

## Hybrid retrieval với RRF

Hybrid gọi BM25 và Dense retrieval với cùng `candidate_k`, sau đó hợp nhất
theo thứ hạng (RRF). `rrf_k` mặc định là 60.
Dense search yêu cầu collection Qdrant đã được nạp bằng cùng bộ chunk và
embedding model. Ví dụ gọi từ Python:

```python
import os
from elasticsearch import Elasticsearch
from embedding.dense_retriever import DEFAULT_MODEL_NAME, DenseRetriever, get_model_spec
from embedding.vector_store import LegalVectorStore
from retrieval.hybrid_retriever import ElasticsearchBM25Retriever, HybridRetriever, HybridSearchConfig

es = Elasticsearch(os.environ["ELASTICSEARCH_URL"])
bm25 = ElasticsearchBM25Retriever(es, os.getenv("ELASTICSEARCH_INDEX", "legal-child-chunks-dev"))
store = LegalVectorStore(
    collection_name="vietnam_legal_chunks",
    dimension=get_model_spec(DEFAULT_MODEL_NAME)["dimension"],
    storage_path="data/indexes/qdrant_storage",
)
dense = DenseRetriever(vector_store=store, model_name=DEFAULT_MODEL_NAME)

hybrid = HybridRetriever(bm25, dense, HybridSearchConfig(top_k=10, candidate_k=50, rrf_k=60))
for hit in hybrid.search("Điều kiện ly hôn đơn phương theo Điều 56"):
    print(hit["rank"], hit["chunk_id"], hit["rrf_score"], hit["source_ranks"])
```

`DenseRetriever` truyền thẳng vào `HybridRetriever`; `hybrid_search` chỉ dành cho
embedding service có `embed_query`, không nhận `DenseRetriever`.
Kết quả có `rrf_score`, `source_ranks`, `source_scores`, `retrieval_sources`,
cùng `chunk_id`, `chunk_text` và `metadata`. Có thể kiểm thử gộp mà không cần model
hay Qdrant bằng `pytest test/test_hybrid_retriever.py -v`.

## Dev set retrieval

Chạy BM25, Dense và Hybrid trên tập Dev queries:

```powershell
$env:QDRANT_PATH = "$PWD\data\indexes\qdrant_storage"
python -m retrieval.run_dev_retrieval --queries data/benchmark/queries_dev.json --model BAAI/bge-m3 --top-k 10 --candidate-k 50 --rrf-k 60
```

## Tạo và quản lý Vector Index (`scripts/build_index.py`)

Chạy lệnh sau từ thư mục gốc của repository để lập chỉ mục từ `data/chunking_output/chunks.jsonl` vào Qdrant:

```powershell
# Model mặc định là dense.model trong retrieval/config.yaml (BAAI/bge-m3)
python scripts/build_index.py

# Hoặc chạy kiểm thử nhanh bằng chế độ Mock
python scripts/build_index.py --mock
```

Mỗi lần chạy dựng lại toàn bộ collection. Vector lưu tại `data/indexes/qdrant_storage/`,
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
