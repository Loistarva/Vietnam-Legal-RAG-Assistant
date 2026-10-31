# Retrieval

## Phạm vi

Dev 4 xây dựng lớp truy xuất cho RAG: BM25-only, Dense-only, Hybrid Retrieval dùng Reciprocal Rank Fusion (RRF), khử trùng lặp theo `chunk_id`, xử lý nhánh rỗng và so sánh ba phương pháp trên cùng bộ Dev.

## Thành phần và công nghệ

| Thành phần | Công nghệ / tệp | Vai trò |
| --- | --- | --- |
| Sparse/BM25 | Elasticsearch BM25; `retrieval/hybrid_retriever.py` | Tìm theo từ khóa bằng hai nhánh `multi_match`: câu hỏi gốc trên `content` và `breadcrumb`, câu hỏi tách từ trên `content_segmented`. Elasticsearch tự chấm điểm BM25. |
| Dense | BGE-M3, Sentence Transformers, Qdrant; `embedding/vector_store.py` | Tạo embedding câu hỏi và tìm các chunk gần nhau theo vector/ngữ nghĩa. |
| Hợp nhất | RRF; `retrieval/rrf.py`, `retrieval/hybrid_retriever.py` | Kết hợp thứ hạng BM25 và Dense, không cộng trực tiếp điểm BM25 với cosine similarity. |
| Build index | `retrieval/build_bm25_index.py` | Đọc file chunk Hôn nhân và Gia đình, chuyển từng chunk thành tài liệu Elasticsearch và nạp index BM25. |
| Chạy benchmark | `retrieval/run_dev_retrieval.py` | Chạy BM25-only, Dense-only và Hybrid trên cùng truy vấn/corpus, ghi ba tệp JSON kết quả; mỗi tệp là mảng `RetrievalEnvelope` (một envelope mỗi câu, `query_id` lấy từ `id` của benchmark), theo mục 5.4 của `docs/data_contract.md`. |
| Đánh giá | `retrieval/retrieval_evaluation.py` | Tính Recall@10, MRR@10, nDCG@10, Precision@10; xuất báo cáo Markdown và CSV tiếng Việt. |

Cấu hình dùng chung nằm trong `retrieval/config.yaml`: Elasticsearch index `legal-child-chunks-dev`, Dense model `BAAI/bge-m3` (1024 chiều), candidate depth 50, Top-10 và `rrf_k=60`. Runner Hybrid + Reranker đọc shared config qua `retrieval.settings.load_settings()`; collection, storage path, corpus, model và dimension phải khớp metadata index đã build. BM25/Dense/Hybrid benchmark không bật reranker hoặc cache để latency benchmark không bị cache hit làm sai lệch.

## Đồng bộ tách từ BM25

`chunking/export_legal_chunks.py` ghi `content_segmented` từ `seg_text`; `chunking/chunking_rules.py` tạo `seg_text` bằng `underthesea.word_tokenize(..., format="text")`. Phiên bản corpus hiện tại được ghi trong `data/chunking_output/chunking_report.json` là `underthesea==9.5.0`, trùng với pin trong `requirements.txt`. Khi truy vấn, BM25 tách câu hỏi bằng cùng phiên bản và gửi cả câu hỏi gốc lẫn câu hỏi đã tách từ trong hai nhánh `should` của Elasticsearch. Nếu thiếu tokenizer hoặc phiên bản không khớp, truy xuất dừng với lỗi rõ ràng thay vì âm thầm dùng câu hỏi thô cho trường đã tách từ.

## Kiểm tra contract, corpus và thời điểm

Trước khi build BM25 hoặc Dense, mỗi ChildChunk phải có `document_id`, `article_id`, `clause_id`, `parent_clause_id` và `parent_id`. `parent_id` phải khớp một ParentChunk trong `parents.json`, và `child_ids` của ParentChunk phải chứa đúng `chunk_id`. BM25 khai báo ID root-level và metadata ID ở kiểu `keyword`; Dense chuẩn hóa cùng contract trước khi ghi payload, và đầu ra Dense giữ riêng `parent_id` (không thay bằng `parent_clause_id`).

Runner benchmark kiểm tra SHA-256 corpus với metadata của cả Elasticsearch và Qdrant trước khi chạy. Kết quả lưu `as_of_date` từng query. Temporal filtering được áp dụng trong từng backend trước Top-K; RRF bảo toàn `effective_from`/`effective_to` và khử trùng theo `chunk_id`. Ngày kết thúc là biên loại trừ: `effective_from <= as_of_date < effective_to`; thiếu ngày được xem là không giới hạn theo quy ước hiện tại, trừ văn bản đánh dấu hết hiệu lực nhưng thiếu `effective_to` thì corpus validation từ chối.

## Cách RRF và khử trùng lặp hoạt động

Mỗi nhánh trả về danh sách chunk có thứ hạng riêng. Với mỗi `chunk_id`, RRF cộng đóng góp từ từng nhánh có chứa chunk đó:

```text
RRF(d) = Σ 1 / (k + rank_r(d))
```

`rank_r(d)` là thứ hạng bắt đầu từ 1 trong nhánh `r`; `k` lấy từ `hybrid.rrf_k` trong shared config trừ khi CLI override tường minh. Các kết quả được gom theo `chunk_id`, nên một chunk chỉ xuất hiện một lần trong đầu ra. Nếu chunk xuất hiện trong cả BM25 và Dense, điểm RRF của hai nhánh được cộng lại. Kết quả cuối được sắp theo điểm RRF giảm dần.

## Redis cache cho luồng truy xuất tương tác

`scripts/run_retrieval.py` bật Redis cache khi có `REDIS_URL` hoặc `--redis-url`; để trống thì cache tắt. Redis được khai báo trong `docker-compose.yml`, bind vào localhost và dùng volume riêng. Chạy `docker compose up -d redis` để khởi động riêng Redis.

Cache kết quả Hybrid trước bước Parent Context, có TTL mặc định 3600 giây. Cache key gồm query chuẩn hóa, `as_of_date`, Top-K, candidate depth, `rrf_k`, filter, reranker và context của model/dimension, corpus SHA-256, Elasticsearch index, Qdrant collection. Vì vậy đổi ngày, filter, cấu hình rerank, model hoặc corpus sẽ tạo key mới thay vì lấy kết quả cũ. Nếu Redis mất kết nối, truy xuất tiếp tục không cache và ghi cảnh báo; lỗi này không biến thành kết quả rỗng. JSON hỏng được bỏ qua và xóa best-effort.

Ví dụ PowerShell:

```powershell
docker compose up -d redis
$env:REDIS_URL = "redis://localhost:6379/0"
python .\scripts\run_retrieval.py --query "Điều kiện kết hôn là gì?" --reranker none
```

## Xử lý kết quả rỗng và lỗi

| Kết quả BM25 | Kết quả Dense | Xử lý |
| --- | --- | --- |
| Có | Có | Hợp nhất thứ hạng bằng RRF, khử trùng theo `chunk_id`. |
| Có | Rỗng | RRF trả các chunk BM25 với đóng góp của nhánh BM25. |
| Rỗng | Có | RRF trả các chunk Dense với đóng góp của nhánh Dense. |
| Rỗng | Rỗng | Trả danh sách rỗng. |

Danh sách rỗng hợp lệ được phân biệt với lỗi kết nối hoặc lỗi truy xuất. Nếu một nhánh phát sinh lỗi, lỗi được ghi log và truyền lên; hệ thống không giả lỗi thành danh sách rỗng và không tự fallback sang nhánh còn lại.

## Chuẩn bị môi trường và chạy

Các lệnh dưới đây dành cho Windows PowerShell, chạy từ thư mục gốc repo. Cần Docker Desktop đang chạy, Python 3.12, Elasticsearch và Qdrant collection chứa cùng corpus/model.

### Máy thành viên mới: tạo môi trường Python

Mỗi thành viên cần tự tạo môi trường ảo tại máy mình; thư mục `.venv312` bị loại khỏi Git nên không được chia sẻ cùng repo. Mở PowerShell tại thư mục repo và chạy:

```powershell
py -3.12 --version
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r .\requirements.txt
```

Nếu `py -3.12 --version` không chạy, hãy cài Python 3.12 kèm Python Launcher rồi mở lại PowerShell. Không cần kích hoạt môi trường ảo; chạy trực tiếp `python.exe` bên trong `.venv312` như lệnh ở trên sẽ tránh lỗi PowerShell không tìm thấy `python`.

### Thành viên build index Elasticsearch dùng chung

Elasticsearch local trong `docker-compose.yml` chỉ bind vào máy chủ (`localhost:9200`). Không mở trực tiếp cổng Elasticsearch chưa bật xác thực ra mạng. Nếu thành viên có SSH access tới máy chủ, họ mở SSH tunnel trong một PowerShell và để cửa sổ đó chạy:

```powershell
ssh -N -L 9200:127.0.0.1:9200 <user>@<ip-máy-chủ>
```

Thay `<user>` và `<ip-máy-chủ>` bằng tài khoản và địa chỉ do người quản lý máy chủ cung cấp. Trong PowerShell thứ hai, tại thư mục repo của thành viên, trỏ client vào đầu tunnel và nạp dữ liệu:

```powershell
$env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:ELASTICSEARCH_INDEX = "legal-child-chunks-dev"
python -c "from retrieval.build_bm25_index import build_bm25_index; print(build_bm25_index(chunks_file=r'.\embedding\data\han_gia_dinh_smoke_chunks.json'))"
```

Không dùng lệnh smoke corpus cũ ở trên để dựng index production. Build BM25 hiện yêu cầu `chunks.jsonl`, `chunking_report.json` và `parents.json` cùng thư mục; báo cáo phải xác nhận `underthesea==9.5.0`, mọi ChildChunk phải có đủ ID theo contract và parent-child links phải khớp. Nếu index đã có, hàm upsert theo `chunk_id`; truyền `recreate=True` khi muốn thay toàn bộ index. Thành viên không có SSH access cần được cấp kết nối qua VPN riêng của nhóm hoặc endpoint Elasticsearch có xác thực.

Với Dense/Qdrant, `scripts/build_index.py` chỉ xóa collection hiện có khi được gọi với `--recreate`. Cờ này phá hủy collection trước khi dựng lại; chỉ dùng khi chủ động rebuild toàn bộ index và đã xác nhận đúng collection. Không truyền cờ sẽ giữ collection và dùng chế độ tạo/cập nhật thông thường.

### 1. Cài dependencies và khởi chạy Elasticsearch

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
docker compose up -d
```

Kiểm tra Elasticsearch:

```powershell
Invoke-RestMethod http://localhost:9200
$env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:ELASTICSEARCH_INDEX = "legal-child-chunks-dev"
```

### 2. Build index theo shared config

```powershell
$env:ELASTICSEARCH_URL = "http://localhost:9200"
.\.venv\Scripts\python.exe -c "from retrieval.build_bm25_index import build_bm25_index; print(build_bm25_index())"
```

Lệnh này đọc corpus, tokenizer, text field và tên index từ `retrieval/config.yaml`. Nó cập nhật index theo ID; không dùng `recreate=True` trừ khi chủ động xác nhận thao tác xóa và dựng lại index. Metadata lưu tokenizer và SHA-256 corpus.

### 3. Lập Dense index và chạy ba nhánh trên cùng bộ Dev

```powershell
.\.venv\Scripts\python.exe scripts\build_index.py
.\.venv\Scripts\python.exe -m retrieval.run_dev_retrieval `
  --queries .\data\benchmark\queries_dev.json `
  --elasticsearch-url http://localhost:9200
```

Runner so SHA-256 corpus với metadata Elasticsearch và Qdrant; hai index phải được build từ cùng một file. Mỗi envelope lưu model, dimension, index, collection, tham số ranking, SHA-256 corpus và `as_of_date`. CLI override chỉ dùng khi cố ý chạy một cấu hình/index đã build tương ứng. Runner ghi `dev_bm25.json`, `dev_dense.json` và `dev_hybrid.json` vào `retrieval/results/` mặc định hoặc thư mục `--output-dir` được chọn. Các file kết quả lịch sử hiện không có trong checkout này.

### 4. Đánh giá và trạng thái nhãn

Evaluator hiện nhận benchmark có `relevant_chunk_ids`; bộ hiện tại không có trường này vì toàn bộ 300 label record đều là draft, `gold_context_ids` rỗng và `candidate_context_ids` chưa được duyệt. Do đó, chưa thể chạy metric gold bằng evaluator hiện tại. Dataset hiện tại có 300 query; 770 proposal IDs đều tồn tại trong corpus, nhưng đây chỉ là kiểm tra ID chứ không xác nhận relevance. Chi tiết SHA-256, nguồn và quy tắc sử dụng nằm trong [benchmark label provenance](../docs/benchmark_label_provenance.md). Không dùng tệp kết quả cũ làm đầu vào đánh giá corpus mới.

## Kết quả Task 4 lịch sử

Các metric ở [báo cáo retrieval](../docs/retrieval_report.md) được tạo trên corpus/index/model cũ (1.159/1.175 chunks, BKAI 768 chiều). Corpus hiện tại có 2.164 chunks và shared config chọn BGE-M3 1024 chiều. Chưa có G3 mới: cần kết nối Elasticsearch có BM25 metadata hợp lệ và dựng Qdrant index đúng shared config. Không dùng số liệu lịch sử để tuyên bố kết quả cấu hình hiện tại.

## Kiểm thử

Kiểm thử hiện có bao phủ cấu trúc kết quả BM25, thứ hạng, ID trùng, kết hợp RRF, các trường hợp một/hai nhánh rỗng và lỗi retriever. Chạy bằng:

```powershell
python -m unittest discover -s test -v
python -m unittest discover -s retrieval/test -v
```

Ở lần kiểm tra gần nhất, 22 kiểm thử trong `test/` và 8 kiểm thử trong `retrieval/test/` đều đạt.

## Giới hạn và việc cần tiếp tục

- Bộ hiện tại có 285 câu Dev và 15 câu Test; corpus có 2.164 chunk. Tỷ lệ Test nhỏ, và các nhãn còn draft nên chưa thể dùng để khẳng định chất lượng retrieval.
- Nhãn liên quan cần được rà soát bởi người có chuyên môn pháp lý.
- Có 15 query trong Test, nhưng chưa chạy trên index/model hiện tại; toàn bộ nhãn đang draft nên chưa thể xác nhận chất lượng độc lập.
- Test temporal hiện tại xác nhận filter của backend trước Top-K ở mức unit/integration test; chưa có bằng chứng chạy end-to-end với Elasticsearch và Qdrant đang hoạt động trong môi trường này.
- Reranker có adapter nhưng không bật trong benchmark này, để so sánh riêng BM25, Dense và RRF.
