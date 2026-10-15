# Hướng dẫn chạy Retrieval

Tài liệu này mô tả cách chạy ba phương pháp retrieval trong repo: BM25, Dense Search bằng Sentence Transformers + Qdrant, và Hybrid Search kết hợp hai nhánh bằng Reciprocal Rank Fusion (RRF).

## 1. Phân biệt corpus và Dev set

- `embedding/data/han_gia_dinh_smoke_chunks.json` là **corpus**: các chunk mà retriever tìm kiếm, kèm `chunk_id`, nội dung và metadata.
- `embedding/data/dev_queries.json` là **Dev set**: câu hỏi và `relevant_chunk_ids` dùng để đối chiếu kết quả retrieval.

`relevant_chunk_ids` trong Dev set phải tồn tại trong corpus. Dev set hiện tại có 14 câu hỏi, dùng để kiểm tra pipeline; nhãn chưa được chuyên gia pháp lý thẩm định nên chưa phải benchmark chính thức.

## 2. Môi trường và dependencies

Các lệnh dưới đây dùng Windows PowerShell, chạy từ thư mục gốc repo. Dùng Python 3.12:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\embedding\requirements.txt
```

`embedding/requirements.txt` cài Sentence Transformers và Qdrant client. Nếu dùng model BKAI, cài thêm tokenizer tiếng Việt:

```powershell
python -m pip install -r .\embedding\requirements-bkai.txt
```

Khi PowerShell chặn kích hoạt virtual environment, cho phép trong terminal hiện tại rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv312\Scripts\Activate.ps1
```

Có thể bỏ qua Activate và thay `python` trong các lệnh bên dưới bằng `\.venv312\Scripts\python.exe`. Lần chạy model đầu tiên có thể cần Internet để tải model từ Hugging Face.

## 3. Chuẩn bị dữ liệu và Qdrant

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

## 4. Chạy BM25 độc lập

BM25 không cần model embedding hoặc Qdrant:

```powershell
python -m retrieval.bm25_retriever --chunks .\embedding\data\han_gia_dinh_smoke_chunks.json --query "Điều kiện ly hôn đơn phương theo Điều 56" --top-k 10
```

Tuỳ chọn `--output` lưu kết quả ra JSON:

```powershell
python -m retrieval.bm25_retriever --query "ly hôn đơn phương" --top-k 20 --output .\retrieval\results\bm25.json
```

BM25 trả các trường `rank`, `score`, `chunk_id`, `text`, `metadata`. Điểm BM25 dùng để xếp hạng trong nhánh BM25; không so sánh trực tiếp với cosine score của Dense Search.

## 5. Chạy Dense, BM25 và Hybrid trên cùng Dev set

Sau khi cài model dependencies và chuẩn bị Qdrant collection, chạy từ thư mục gốc:

```powershell
$env:QDRANT_PATH = "$PWD\qdrant_data"
python -m retrieval.run_dev_retrieval `
  --queries .\embedding\data\dev_queries.json `
  --chunks .\embedding\data\han_gia_dinh_smoke_chunks.json `
  --model bkai-foundation-models/vietnamese-bi-encoder `
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

Trong mã ứng dụng, Hybrid được cấu hình và gọi qua interface `DenseRetriever`:

```python
from retrieval.hybrid_retriever import (
    EmbeddingQdrantAdapter,
    HybridRetriever,
    HybridSearchConfig,
)

config = HybridSearchConfig(top_k=10, candidate_k=50, rrf_k=60)
dense = EmbeddingQdrantAdapter(embedding_service, vector_store)
retriever = HybridRetriever(bm25_index, dense, config)
hits = retriever.search("Câu hỏi cần truy vấn", top_k=10)
```

Chọn/tinh chỉnh `candidate_k`, `top_k` và `rrf_k` chỉ trên Dev set. Không dùng tập Test để tinh chỉnh; hiện repo chưa có tập Test tách biệt. Các kết quả đang lưu là một lượt với cấu hình Top-10, candidate depth 50, RRF k=60, không phải báo cáo sweep/tối ưu tham số.

## 6. Tạo CSV và báo cáo chỉ số

Sau khi có đủ ba file kết quả, chạy:

```powershell
python -m retrieval.retrieval_evaluation
```

Lệnh kiểm tra schema, query và ID trùng, sau đó tạo:

- `retrieval/results/retrieval_results.csv`: kết quả chi tiết với `method`, `query`, `chunk_id`, `score`, `rank`, `is_relevant`, `chunk_text`, `relevant_chunk_ids`, `relevant_chunk_text`. Hai cột văn bản cho phép xem trực tiếp chunk được truy xuất và chunk chuẩn từ Dev set.
- `retrieval/results/retrieval_report.md`: macro Recall@10 và MRR@10 cùng cấu hình và giới hạn đánh giá.

### So sánh BM25, Dense và Hybrid

Các phương pháp dùng cùng 14 câu hỏi, cùng corpus và cùng Top-10. Kết quả hiện tại với BKAI Dense, candidate depth 50 và RRF k=60:

| Phương pháp | Cách tìm | Recall@10 | MRR@10 | Đọc kết quả |
| --- | --- | ---: | ---: | --- |
| BM25 | Khớp từ khóa, số Điều và thuật ngữ trong chunk/metadata | 0.7857 | 0.7381 | Baseline lexical; có thể bỏ sót câu hỏi diễn đạt khác từ trong luật. |
| Dense | Tương đồng ngữ nghĩa qua embedding | 0.9643 | **0.8595** | Chunk đúng thường xuất hiện sớm hơn; có thể không ưu tiên số hiệu chính xác như BM25. |
| Hybrid (RRF) | Hợp nhất thứ hạng BM25 và Dense | **1.0000** | 0.8333 | Bao phủ toàn bộ chunk relevant trong Top-10 ở Dev set này, nhưng hạng relevant đầu tiên trung bình thấp hơn Dense một chút. |

**Kết luận cho lượt chạy này:** Hybrid có Recall@10 cao nhất, Dense có MRR@10 cao nhất. Vì vậy Hybrid tìm được toàn bộ chunk đã gán nhãn trong Top-10 trên Dev set nhỏ này, còn Dense thường đưa chunk relevant lên vị trí sớm hơn. Đây là hai khía cạnh khác nhau; không thể kết luận một phương pháp thắng tuyệt đối chỉ từ một chỉ số.

Điểm `score` trong CSV **không so sánh trực tiếp giữa các phương pháp**: BM25 là điểm lexical, Dense là cosine similarity, còn Hybrid là điểm RRF từ thứ hạng. So sánh chất lượng bằng Recall/MRR trên cùng Dev set và xem `is_relevant`, `chunk_text`, `relevant_chunk_text` để kiểm tra từng truy vấn. Các con số trên là kết quả của một cấu hình cố định, không phải kết quả tuning; nhãn Dev chưa được chuyên gia pháp lý thẩm định.

Muốn dùng Dev set, thư mục kết quả hoặc output khác, truyền `--dev-set`, `--results-dir`, `--output-dir`. Ví dụ:

```powershell
python -m retrieval.retrieval_evaluation --dev-set .\embedding\data\dev_queries.json --results-dir .\retrieval\results --output-dir .\retrieval\results
```

Recall/MRR chỉ có ý nghĩa tương ứng với nhãn `relevant_chunk_ids` đã cung cấp. Cần rà soát nhãn độc lập và mở rộng câu hỏi/văn bản trước khi dùng để chọn model hay kết luận chất lượng tổng quát.

## 7. Kiểm thử và lỗi thường gặp

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
