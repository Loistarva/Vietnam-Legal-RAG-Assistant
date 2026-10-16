# Hướng dẫn chạy Retrieval

Tài liệu này mô tả cả runner đánh giá offline và pipeline production theo `RAG Assistant Architecture.drawio`: sparse search (Elasticsearch/BM25) + dense search (BGE-M3/Qdrant) song song, RRF Top-50, cross-encoder rerank rồi trả Top-10. Hai phần dùng chung schema chunk.

## 1. Phân biệt corpus và bộ Dev

- `embedding/data/han_gia_dinh_smoke_chunks.json` là **corpus**: các chunk mà retriever tìm kiếm, kèm `chunk_id`, nội dung và metadata.
- `data/benchmark/queries_dev.json` là **bộ Dev**: câu hỏi và `relevant_chunk_ids` dùng để đối chiếu kết quả truy xuất. `data/benchmark/ground_truth.json` lưu riêng phần nhãn.

`relevant_chunk_ids` trong bộ Dev phải tồn tại trong corpus. Bộ hiện tại có 14 câu hỏi, dùng để kiểm tra pipeline trên fixture 321 chunk của một văn bản; đây không phải corpus lớn. Nhãn chưa được chuyên gia pháp lý thẩm định nên chưa phải benchmark chính thức.

## 2. Môi trường và dependencies

Các lệnh dưới đây dùng Windows PowerShell, chạy từ thư mục gốc repo. Dùng Python 3.12:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\embedding\requirements.txt
```

`embedding/requirements.txt` cài Sentence Transformers, Qdrant client và Elasticsearch client. Cần có Elasticsearch đang chạy, cùng child-chunk corpus được lập chỉ mục trước khi chạy hybrid retrieval. Nếu dùng model BKAI, cài thêm tokenizer tiếng Việt:

```powershell
python -m pip install -r .\embedding\requirements-bkai.txt
```

Khi PowerShell chặn kích hoạt virtual environment, cho phép trong terminal hiện tại rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv312\Scripts\Activate.ps1
```

Có thể bỏ qua Activate và thay `python` trong các lệnh bên dưới bằng `\.venv312\Scripts\python.exe`. Lần chạy model đầu tiên có thể cần Internet để tải model từ Hugging Face.

## 3. Chạy Elasticsearch local bằng Docker Desktop

Mở `Docker Desktop Installer.exe`, hoàn tất cài đặt (chọn WSL 2 backend nếu trình cài đặt hỏi), khởi động Docker Desktop và chờ trạng thái Engine chạy. Từ PowerShell ở thư mục gốc repo, khởi chạy Elasticsearch single-node; cấu hình này chỉ bind cổng vào loopback của máy local:

```powershell
docker compose up -d
Invoke-RestMethod http://localhost:9200
```

`docker-compose.yml` dùng image Elasticsearch chính thức và volume Docker để giữ dữ liệu index qua các lần restart. Sau khi dịch vụ trả về thông tin cluster, cài Python client nếu chưa cài:

```powershell
python -m pip install -r .\embedding\requirements.txt
```

## 4. Chuẩn bị dữ liệu và Qdrant

Corpus smoke test đã có sẵn tại `embedding/data/han_gia_dinh_smoke_chunks.json`. Nếu cần tạo lại từ parser/chunker, xem hướng dẫn trong `embedding/README.md` và chạy `embedding/prepare_chunk_dataset.py`.

Dense và Hybrid cần một Qdrant collection đã được nạp bằng **cùng corpus và cùng model**. Dùng Qdrant embedded local trong repo:

```powershell
$env:QDRANT_PATH = "$PWD\qdrant_data"
```

Tạo/nạp collection BKAI nếu chưa có:

```powershell
python .\embedding\retrieval_smoke_test.py --chunks .\embedding\data\han_gia_dinh_smoke_chunks.json --model bkai-foundation-models/vietnamese-bi-encoder --top-k 5
```

Collection mặc định dựa trên model và hash corpus. Runner Dev set sẽ tự dùng collection theo quy ước này. Nếu collection được tạo với tên tùy chỉnh, truyền cùng tên qua `--collection` khi chạy Dev set. Không xóa Qdrant data chỉ để xử lý lỗi collection; hãy xác nhận đúng `QDRANT_PATH`, model và collection trước.

## 5. Nạp chunks và chạy BM25-only bằng Elasticsearch

BM25-only gọi Elasticsearch trực tiếp, không cần model embedding hoặc Qdrant. Index cần được nạp trước bằng child chunks từ `ChildChunk.to_elasticsearch_doc()`:

```powershell
$env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:ELASTICSEARCH_INDEX = "legal-child-chunks-dev"
python -m retrieval.index_elasticsearch
python -m retrieval.bm25_retriever --query "Điều kiện ly hôn đơn phương theo Điều 56" --top-k 10
```

Elasticsearch dùng BM25 mặc định cho `match` trên `content_segmented`; đầu ra gồm `rank`, `score`, `chunk_id`, `text`, `parent_id` và `metadata`. `BM25Index` in-memory còn là baseline/offline tiện cho test; chỉ bật rõ ràng bằng `--backend local`.

Tuỳ chọn `--output` lưu kết quả Elasticsearch ra JSON:

```powershell
python -m retrieval.bm25_retriever --query "ly hôn đơn phương" --top-k 20 --output .\retrieval\results\bm25.json
```

Điểm Elasticsearch BM25 dùng để xếp hạng trong nhánh lexical; không so sánh trực tiếp với cosine score của Dense Search.

## 6. Chạy Dense, Elasticsearch BM25 và Hybrid trên cùng Dev set

Sau khi cài dependencies, nạp cùng corpus vào Elasticsearch và chuẩn bị Qdrant collection, cấu hình URL/index Elasticsearch rồi chạy từ thư mục gốc:

```powershell
$env:QDRANT_PATH = "$PWD\qdrant_data"
$env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:ELASTICSEARCH_INDEX = "legal-child-chunks-dev"
python -m retrieval.index_elasticsearch
python -m retrieval.run_dev_retrieval `
  --queries .\data\benchmark\queries_dev.json `
  --chunks .\embedding\data\han_gia_dinh_smoke_chunks.json `
  --model BAAI/bge-m3 `
  --top-k 10 `
  --candidate-k 50 `
  --rrf-k 60
```

Runner dùng cùng query và corpus cho cả ba nhánh, sau đó ghi:

- `retrieval/results/dev_bm25.json`
- `retrieval/results/dev_dense.json`
- `retrieval/results/dev_hybrid.json`

Mỗi dòng có `query`, `chunk_id`, `score`, `rank`. Với Hybrid, `score` là điểm RRF. RRF cộng đóng góp theo hạng (`1 / (rrf_k + rank)`), không cộng trực tiếp điểm BM25 và cosine. `candidate-k` là số kết quả đầu vào cho phép hợp nhất; `top-k` là số kết quả cuối cùng được lưu.

Có thể chọn một trong ba model đã cấu hình: `AITeamVN/Vietnamese_Embedding`, `bkai-foundation-models/vietnamese-bi-encoder`, hoặc `BAAI/bge-m3`. Collection Qdrant phải được nạp bằng model đã chọn. Xem toàn bộ tham số bằng:

```powershell
python -m retrieval.run_dev_retrieval --help
```

Runner bộ Dev gọi Elasticsearch `_search` với truy vấn `multi_match`; Elasticsearch dùng BM25 mặc định để chấm điểm nhánh sparse. Index phải chứa cùng child-chunk corpus dùng để nạp Qdrant, nếu không so sánh hybrid sẽ lệch dữ liệu. Runner chưa bật reranker để giữ riêng phép đo BM25/Dense/RRF; ứng dụng bật cross-encoder như ví dụ dưới để hoàn tất luồng production:

```python
from retrieval.hybrid_retriever import (
    CrossEncoderReranker,
    ElasticsearchBM25Retriever,
    EmbeddingQdrantAdapter,
    filter_legal_metadata,
    HybridRetriever,
    HybridSearchConfig,
)

config = HybridSearchConfig(top_k=10, candidate_k=50, rrf_k=60)
dense = EmbeddingQdrantAdapter(bge_m3_embedding_service, qdrant_vector_store)
sparse = ElasticsearchBM25Retriever(elasticsearch_client, "legal-child-chunks-dev")
retriever = HybridRetriever(
    sparse, dense, config, reranker=CrossEncoderReranker("BAAI/bge-reranker-v2-m3"),
    metadata_filter=lambda hits: filter_legal_metadata(hits, filters=extracted_filters),
)
detailed = retriever.retrieve("Câu hỏi cần truy vấn")
top10 = detailed["hybrid"]  # fused Top-50 is available at detailed["fused"]

# Metadata/temporal gate này chạy sau RRF, trước rerank. Qdrant và Elasticsearch
# loại văn bản hết hiệu lực ngay ở nhánh tìm kiếm.
```

Elasticsearch phải được nạp từ `ChildChunk.to_elasticsearch_doc()` cùng metadata; adapter mặc định BM25 `multi_match` trên `content_segmented` (tương ứng `seg_text`), breadcrumb và metadata Điều/Khoản, đồng thời lọc `metadata.validity_status`. Nếu index dùng trường hoặc mapping khác, cấu hình `text_field` hay sửa truy vấn term tương ứng. `CrossEncoderReranker` tải model lần đầu khi truy vấn; có thể truyền model đã khởi tạo để quản lý vòng đời/thiết bị trong ứng dụng.

`HybridRetriever` chạy hai nhánh song song, giữ Top-50 RRF trong `fused`, rerank thành Top-10 rồi gọi tùy chọn `confidence_filter(query, hits)` và `parent_resolver.resolve(hits)`. `filter_legal_metadata` cung cấp lọc hiệu lực và metadata cho các adapter không hỗ trợ pre-filter. `RedisJSONCache` là adapter lưu JSON có TTL; cần cấu hình riêng cho namespace và cache key. Các thành phần LLM Judge, MMR, cache ngữ nghĩa theo độ tương đồng, router/HyDE, và Parent Store phụ thuộc vào dịch vụ/model cụ thể nên chưa được giả lập trong runner offline; tích hợp qua `confidence_filter`, `parent_resolver` và cache của ứng dụng.

Ví dụ khởi tạo embedder cũ của smoke test (chỉ để tham khảo; không thay cho BGE-M3 production):

```python
config = HybridSearchConfig(top_k=10, candidate_k=50, rrf_k=60)
dense = EmbeddingQdrantAdapter(embedding_service, vector_store)
retriever = HybridRetriever(bm25_index, dense, config)
hits = retriever.search("Câu hỏi cần truy vấn", top_k=10)
```

Chọn/tinh chỉnh `candidate_k`, `top_k` và `rrf_k` chỉ trên Dev set. Không dùng tập Test để tinh chỉnh; hiện repo chưa có tập Test tách biệt. Các kết quả đang lưu là một lượt với cấu hình Top-10, candidate depth 50, RRF k=60, không phải báo cáo sweep/tối ưu tham số.

## 7. Tạo CSV và báo cáo chỉ số

Sau khi có đủ ba file kết quả, chạy:

```powershell
python -m retrieval.retrieval_evaluation
```

Lệnh kiểm tra schema, query và ID trùng, sau đó tạo:

- `retrieval/results/retrieval_results.csv`: kết quả chi tiết với tiêu đề cột tiếng Việt; hai cột nội dung cho phép xem chunk được truy xuất và chunk chuẩn của bộ Dev.
- `retrieval/results/retrieval_report.md`: macro Recall@10, MRR@10, nDCG@10 và Precision@10 cùng cấu hình và giới hạn đánh giá.

### Kết quả Dev set hiện tại

Ba phương pháp được chạy trên cùng 14 câu hỏi, cùng 321 chunks và Top-10; BM25 dùng Elasticsearch index `legal-child-chunks-dev`, Dense dùng BGE-M3/Qdrant, Hybrid dùng candidate depth 50 và RRF k=60.

| Phương pháp | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: |
| BM25 (Elasticsearch) | 0.8929 | 0.5620 | 0.6415 | 0.0929 |
| Dense (BGE-M3) | 1.0000 | **0.9524** | **0.9586** | 0.1071 |
| Hybrid (RRF) | 1.0000 | 0.8197 | 0.8684 | 0.1071 |

Trên bộ Dev nhỏ này, Dense và Hybrid cùng đạt Recall@10=1,0; Dense xếp chunk liên quan sớm hơn theo MRR và nDCG. Kết quả này không cho thấy Hybrid tốt hơn Dense trong cấu hình hiện tại.

Điểm `score` trong CSV **không so sánh trực tiếp giữa các phương pháp**: BM25 là điểm Elasticsearch lexical, Dense là cosine similarity, còn Hybrid là điểm RRF từ thứ hạng. Nhãn Dev chưa được chuyên gia pháp lý thẩm định; kết quả chỉ mang tính smoke/development cho một văn bản.

Muốn dùng bộ Dev, thư mục kết quả hoặc thư mục xuất khác, truyền `--dev-set`, `--results-dir`, `--output-dir`. Ví dụ:

```powershell
  python -m retrieval.retrieval_evaluation --dev-set .\data\benchmark\queries_dev.json --results-dir .\retrieval\results --output-dir .\retrieval\results
```

Recall/MRR chỉ có ý nghĩa tương ứng với nhãn `relevant_chunk_ids` đã cung cấp. Cần rà soát nhãn độc lập và mở rộng câu hỏi/văn bản trước khi dùng để chọn model hay kết luận chất lượng tổng quát.

## 8. Kiểm thử và lỗi thường gặp

Chạy các kiểm thử nhánh BM25/Hybrid, gồm nhánh rỗng, chunk ID trùng và lỗi retriever:

```powershell
python -m unittest discover -s retrieval/test -v
python -m unittest test.test_bm25_retrieval test.test_hybrid_retriever -v
```

- **Không mở được Qdrant / collection không tồn tại:** đặt `QDRANT_PATH` đúng trước khi nạp và chạy; xác nhận collection đã được tạo với model và corpus đang dùng.
- **Sai số point:** dùng collection riêng cho fixture/model; không dùng collection được tạo từ corpus khác.
- **Không tải được model:** kiểm tra mạng ở lần tải đầu. Khi model đã cache, có thể thử lại trong cùng môi trường Python.
- **Thiếu `underthesea`:** cài `embedding/requirements-bkai.txt` nếu dùng BKAI.
- **Dev set tham chiếu chunk không tồn tại:** kiểm tra `relevant_chunk_ids` với `chunk_id` trong corpus trước khi đánh giá.
- **Dense lỗi:** runner báo lỗi và dừng; không tự coi lỗi kết nối là nhánh rỗng hoặc âm thầm fallback BM25.
