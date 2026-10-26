# Retrieval

## Phạm vi

Dev 4 xây dựng lớp truy xuất cho RAG: BM25-only, Dense-only, Hybrid Retrieval dùng Reciprocal Rank Fusion (RRF), khử trùng lặp theo `chunk_id`, xử lý nhánh rỗng và so sánh ba phương pháp trên cùng bộ Dev.

## Thành phần và công nghệ

| Thành phần | Công nghệ / tệp | Vai trò |
| --- | --- | --- |
| Sparse/BM25 | Elasticsearch BM25; `retrieval/hybrid_retriever.py` | Tìm bằng `multi_match` trên `content_segmented` và `breadcrumb^1.5`; loại tài liệu có `metadata.validity_status = "Hết hiệu lực"`. Elasticsearch tự chấm điểm BM25. |
| Dense | Sentence Transformers, Qdrant; `embedding/dense_retriever.py`, `embedding/vector_store.py` | Tạo embedding câu hỏi và tìm chunk gần nhau theo vector; mặc định loại tài liệu hết hiệu lực. |
| Hợp nhất | RRF; `retrieval/rrf.py`, `retrieval/hybrid_retriever.py` | Kết hợp thứ hạng BM25 và Dense, không cộng trực tiếp điểm BM25 với cosine similarity. |
| Build index | `retrieval/build_bm25_index.py` | Đọc corpus chunk JSON/JSONL, chuyển từng chunk thành tài liệu Elasticsearch và nạp index BM25. |
| Chạy benchmark | `retrieval/run_dev_retrieval.py` | Chạy BM25-only, Dense-only và Hybrid trên cùng truy vấn/corpus, ghi ba tệp JSON kết quả; mỗi tệp là mảng `RetrievalEnvelope` (một envelope mỗi câu, `query_id` lấy từ `id` của benchmark), theo mục 5.4 của `docs/data_contract.md`. |
| Đánh giá | `scripts/evaluate_task4.py` | So sánh các JSON đầu ra với candidate/gold labels; ghi `metrics.csv` và `article_metrics.csv`. |

`retrieval/config.yaml` mô tả một bộ cấu hình mặc định khác; `retrieval.run_dev_retrieval` hiện lấy thiết lập từ đối số CLI, không đọc file YAML đó. Lần chạy mới nhất dùng Elasticsearch index `legal-child-chunks-current`, Dense model `bkai-foundation-models/vietnamese-bi-encoder`, collection `vietnam_legal_chunks_current`, candidate depth 50, Top-10 và RRF k=60. Reranker không được bật trong phép so sánh này.

## Cách RRF và khử trùng lặp hoạt động

Mỗi nhánh trả về danh sách chunk có thứ hạng riêng. Với mỗi `chunk_id`, RRF cộng đóng góp từ từng nhánh có chứa chunk đó:

```text
RRF(d) = Σ 1 / (k + rank_r(d))
```

`rank_r(d)` là thứ hạng bắt đầu từ 1 trong nhánh `r`; mặc định `k = 60`. Các kết quả được gom theo `chunk_id`, nên một chunk chỉ xuất hiện một lần trong đầu ra. Nếu chunk xuất hiện trong cả BM25 và Dense, điểm RRF của hai nhánh được cộng lại. Kết quả cuối được sắp theo điểm RRF giảm dần.

## Xử lý kết quả rỗng và lỗi

| Kết quả BM25 | Kết quả Dense | Xử lý |
| --- | --- | --- |
| Có | Có | Hợp nhất thứ hạng bằng RRF, khử trùng theo `chunk_id`. |
| Có | Rỗng | RRF trả các chunk BM25 với đóng góp của nhánh BM25. |
| Rỗng | Có | RRF trả các chunk Dense với đóng góp của nhánh Dense. |
| Rỗng | Rỗng | Trả danh sách rỗng. |

Danh sách rỗng hợp lệ được phân biệt với lỗi kết nối hoặc lỗi truy xuất. Nếu một nhánh phát sinh lỗi, lỗi được ghi log và truyền lên; hệ thống không giả lỗi thành danh sách rỗng và không tự fallback sang nhánh còn lại.

## Chuẩn bị môi trường và chạy

Các lệnh dưới đây dành cho Windows PowerShell, chạy từ thư mục gốc repo. Cần Docker Desktop, Python 3.12, Elasticsearch và Qdrant collection chứa đúng corpus/model. Trong các lệnh bên dưới, `.venv312` là môi trường đã tạo ở bước đầu.

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
$env:ELASTICSEARCH_INDEX = "legal-child-chunks-current"
.\.venv312\Scripts\python.exe -c "from retrieval.build_bm25_index import build_bm25_index; print(build_bm25_index(chunks_file=r'.\data\chunking_output\chunks.jsonl', index_name='legal-child-chunks-current'))"
```

File chunk phải tồn tại trên máy thành viên và phải là corpus nhóm muốn nạp. Nếu index đã có, hàm upsert theo `chunk_id`; truyền `recreate=True` khi muốn thay toàn bộ index và xóa các chunk không còn trong file. Thành viên không có SSH access cần được cấp kết nối qua VPN riêng của nhóm hoặc endpoint Elasticsearch có xác thực; chỉ gửi URL `localhost` sẽ không tạo kết nối tới máy người khác.

### 1. Cài dependencies và khởi chạy Elasticsearch

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r .\requirements.txt
docker compose up -d elasticsearch
```

Kiểm tra Elasticsearch:

```powershell
Invoke-RestMethod http://localhost:9200
$env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:ELASTICSEARCH_INDEX = "legal-child-chunks-current"
```

### 2. Build index từ corpus hiện tại

```powershell
.\.venv312\Scripts\python.exe -c "from retrieval.build_bm25_index import build_bm25_index; print(build_bm25_index(chunks_file=r'.\data\chunking_output\chunks.jsonl', index_name='legal-child-chunks-current', recreate=True))"
```

Lệnh trên **xóa rồi thay** BM25 index `legal-child-chunks-current` bằng toàn bộ `data/chunking_output/chunks.jsonl`; không dùng `recreate=True` nếu index đó cần giữ lại.

Dense collection của lần chạy mới nhất là `vietnam_legal_chunks_current`, được lưu tại `data/indexes/qdrant_storage`. Việc build Dense dùng upsert và không xóa point cũ không còn trong corpus. Với đúng corpus hiện tại, dùng lại tên collection này; khi corpus hoặc model thay đổi, hãy dùng tên collection mới và dùng đúng tên đó ở bước chạy benchmark, tránh point cũ bị giữ lại.

```powershell
.\.venv312\Scripts\python.exe scripts\build_index.py `
  --input .\data\chunking_output\chunks.jsonl `
  --index-dir .\data\indexes `
  --collection vietnam_legal_chunks_current `
  --model bkai-foundation-models/vietnamese-bi-encoder
```

### 3. Chạy BM25-only, Dense-only và Hybrid trên Dev

```powershell
.\.venv312\Scripts\python.exe -m retrieval.run_dev_retrieval `
  --queries .\data\benchmark\queries_dev.json `
  --chunks .\data\chunking_output\chunks.jsonl `
  --model bkai-foundation-models/vietnamese-bi-encoder `
  --collection vietnam_legal_chunks_current `
  --elasticsearch-url http://localhost:9200 `
  --elasticsearch-index legal-child-chunks-current `
  --output-dir .\retrieval\results `
  --top-k 10 `
  --candidate-k 50 `
  --rrf-k 60
```

Runner ghi đè ba tệp JSON trong `retrieval/results/` để thư mục luôn phản ánh lần chạy gần nhất. Lệnh đánh giá sau đây ghi hai CSV metric; nó **không tự tạo/cập nhật** file Markdown:

```powershell
.\.venv312\Scripts\python.exe scripts\evaluate_task4.py `
  --dev .\data\benchmark\queries_dev.json `
  --ground-truth .\data\benchmark\ground_truth.json `
  --chunks .\data\chunking_output\chunks.jsonl `
  --results .\retrieval\results `
  --output .\retrieval\results\metrics.csv `
  --article-index .\data\reference\production_chunk_index.json `
  --article-output .\retrieval\results\article_metrics.csv
```

`retrieval/results/retrieval_report.md` và `docs/retrieval_report.md` là báo cáo Markdown được cập nhật riêng sau lần chạy; cần cập nhật số liệu trong đó nếu benchmark được chạy lại.

## Kết quả Task 4 hiện tại

Kết quả thực tế mới nhất dùng 285 câu Dev và corpus 2.011 chunks. Hybrid RRF đạt Recall@10 0.8209 ở chunk-level và 0.9120 ở article-level, cao nhất trong lần chạy này. Có 267 câu dùng nhãn candidate chưa xác minh và 18 câu không có nhãn, nên các metric chỉ mang tính thử nghiệm. Bảng metric và các JSON đầu ra nằm trong `retrieval/results/`; báo cáo tại [docs/retrieval_report.md](../docs/retrieval_report.md).

## Kiểm thử

Kiểm thử hiện có bao phủ cấu trúc kết quả BM25, thứ hạng, ID trùng, kết hợp RRF, các trường hợp một/hai nhánh rỗng và lỗi retriever. Chạy bằng:

```powershell
python -m unittest discover -s test -v
python -m unittest discover -s retrieval/test -v
```

Lần kiểm tra tài liệu này: 7 kiểm thử trong `retrieval/test/` đạt. Bộ `test/` chạy 138 test nhưng có 9 lỗi: một lỗi `NameError` trong test BM25 và các lỗi do thiếu dependency `underthesea`; cần xử lý các vấn đề đó trước khi mô tả toàn bộ test suite là đạt.

## Giới hạn và việc cần tiếp tục

- Bộ Dev hiện tại nhỏ, chỉ có một văn bản; cần bổ sung corpus và truy vấn đại diện nhiều lĩnh vực pháp luật.
- Nhãn liên quan cần được rà soát bởi người có chuyên môn pháp lý.
- Chưa có Test set độc lập; không dùng Dev để khẳng định chất lượng tổng quát.
- Metadata/time filter trong sơ đồ kiến trúc cần được đặt đúng vị trí pre-filter trước hai nhánh nếu đó là yêu cầu bắt buộc của pipeline production.
- Reranker có adapter nhưng không bật trong benchmark này, để so sánh riêng BM25, Dense và RRF.
