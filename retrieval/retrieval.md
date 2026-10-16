# Retrieval

## Phạm vi

Dev 4 xây dựng lớp truy xuất cho RAG: BM25-only, Dense-only, Hybrid Retrieval dùng Reciprocal Rank Fusion (RRF), khử trùng lặp theo `chunk_id`, xử lý nhánh rỗng và so sánh ba phương pháp trên cùng bộ Dev.

## Thành phần và công nghệ

| Thành phần | Công nghệ / tệp | Vai trò |
| --- | --- | --- |
| Sparse/BM25 | Elasticsearch BM25; `retrieval/hybrid_retriever.py` | Tìm theo từ khóa. Dùng `multi_match` trên `content_segmented`, breadcrumb và metadata Điều/Khoản. Elasticsearch tự chấm điểm BM25. |
| Dense | BGE-M3, Sentence Transformers, Qdrant; `embedding/vector_store.py` | Tạo embedding câu hỏi và tìm các chunk gần nhau theo vector/ngữ nghĩa. |
| Hợp nhất | RRF; `retrieval/rrf.py`, `retrieval/hybrid_retriever.py` | Kết hợp thứ hạng BM25 và Dense, không cộng trực tiếp điểm BM25 với cosine similarity. |
| Build index | `retrieval/build_bm25_index.py` | Đọc file chunk Hôn nhân và Gia đình, chuyển từng chunk thành tài liệu Elasticsearch và nạp index BM25. |
| Chạy benchmark | `retrieval/run_dev_retrieval.py` | Chạy BM25-only, Dense-only và Hybrid trên cùng truy vấn/corpus, ghi ba tệp JSON kết quả. |
| Đánh giá | `retrieval/retrieval_evaluation.py` | Tính Recall@10, MRR@10, nDCG@10, Precision@10; xuất báo cáo Markdown và CSV tiếng Việt. |

Cấu hình mặc định nằm trong `retrieval/config.yaml`: Elasticsearch index `legal-child-chunks-dev`, Dense model `BAAI/bge-m3`, candidate depth 50, Top-10 và RRF k=60. Đây là cấu hình chạy Dev; reranker không được bật trong phép so sánh BM25/Dense/Hybrid.

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
.\.venv312\Scripts\python.exe -m retrieval.build_bm25_index `
  --chunks .\embedding\data\han_gia_dinh_smoke_chunks.json
```

File chunk phải tồn tại trên máy thành viên và phải là corpus nhóm muốn nạp. Nếu dùng file khác, thay đường dẫn sau `--chunks`. Không thêm `--recreate` trừ khi được thống nhất xóa và tạo lại index. Thành viên không có SSH access cần được cấp kết nối qua VPN riêng của nhóm hoặc endpoint Elasticsearch có xác thực; chỉ gửi URL `localhost` sẽ không tạo kết nối tới máy người khác.

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

### 2. Nạp child chunks vào Elasticsearch

```powershell
python -m retrieval.build_bm25_index `
  --chunks .\embedding\data\han_gia_dinh_smoke_chunks.json
```

Lệnh trên tạo hoặc cập nhật index mặc định. Chỉ truyền `--recreate` khi chủ động muốn xóa và tạo lại index.

### 3. Chạy BM25-only, Dense-only và Hybrid trên cùng bộ Dev

```powershell
$env:QDRANT_PATH = (Resolve-Path .\qdrant_data).Path
python -m retrieval.run_dev_retrieval `
  --queries .\data\benchmark\queries_dev.json `
  --chunks .\embedding\data\han_gia_dinh_smoke_chunks.json `
  --model BAAI/bge-m3 `
  --top-k 10 `
  --candidate-k 50 `
  --rrf-k 60
```

Runner yêu cầu Elasticsearch index và Qdrant collection khớp cùng corpus. Collection mặc định được xác định từ tên model và hash của file chunk. Kết quả được lưu tại:

- `retrieval/results/dev_bm25.json`
- `retrieval/results/dev_dense.json`
- `retrieval/results/dev_hybrid.json`

### 5. Tính metric và tạo báo cáo

```powershell
python -m retrieval.retrieval_evaluation
```

Lệnh đọc bộ Dev cùng ba tệp JSON kết quả, sau đó ghi:

- `retrieval/results/retrieval_report.md`: cấu hình, metric, diễn giải và giới hạn.
- `retrieval/results/retrieval_results.csv`: kết quả từng truy vấn/chunk, với tên cột và cờ liên quan bằng tiếng Việt.

## Kết quả Dev hiện có

Các số dưới đây được tính từ kết quả lưu gần nhất: 14 câu hỏi, 321 chunk từ một văn bản, Top-10 mỗi phương pháp. Đây là bộ smoke test phát triển, không phải benchmark trên corpus lớn. Nhãn chưa được chuyên gia pháp lý thẩm định.

| Phương pháp | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: |
| BM25 Elasticsearch | 0,8929 | 0,5620 | 0,6415 | 0,0929 |
| Dense BGE-M3 | 1,0000 | 0,9524 | 0,9586 | 0,1071 |
| Hybrid RRF | 1,0000 | 0,8197 | 0,8684 | 0,1071 |

Trong Dev set này, Dense và Hybrid cùng thu hồi đủ chunk được gán nhãn trong Top-10; Dense xếp chunk liên quan sớm hơn theo MRR và nDCG. Chưa có căn cứ từ kết quả này để khẳng định Hybrid tốt hơn Dense.

## Kiểm thử

Kiểm thử hiện có bao phủ cấu trúc kết quả BM25, thứ hạng, ID trùng, kết hợp RRF, các trường hợp một/hai nhánh rỗng và lỗi retriever. Chạy bằng:

```powershell
python -m unittest discover -s test -v
python -m unittest discover -s retrieval/test -v
```

Ở lần kiểm tra gần nhất, 22 kiểm thử trong `test/` và 8 kiểm thử trong `retrieval/test/` đều đạt.

## Giới hạn và việc cần tiếp tục

- Bộ Dev hiện tại nhỏ, chỉ có một văn bản; cần bổ sung corpus và truy vấn đại diện nhiều lĩnh vực pháp luật.
- Nhãn liên quan cần được rà soát bởi người có chuyên môn pháp lý.
- Chưa có Test set độc lập; không dùng Dev để khẳng định chất lượng tổng quát.
- Metadata/time filter trong sơ đồ kiến trúc cần được đặt đúng vị trí pre-filter trước hai nhánh nếu đó là yêu cầu bắt buộc của pipeline production.
- Reranker có adapter nhưng không bật trong benchmark này, để so sánh riêng BM25, Dense và RRF.
