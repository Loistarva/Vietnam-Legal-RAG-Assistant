# Thử nghiệm Embedding và Qdrant

Thử nghiệm này chuyển các child chunk pháp luật cố định thành vector, lưu
vector cùng payload vào Qdrant local và chạy truy vấn Top-K cho từng model.
Quy trình dùng parser và thuật toán chunking đã có trong repo, không viết
lại parser hoặc chunker.

Ba model ID được cấu hình:

- `AITeamVN/Vietnamese_Embedding`
- `bkai-foundation-models/vietnamese-bi-encoder`
- `BAAI/bge-m3`

`BAAI/bge-vi-base` xuất hiện trong ghi chú nghiên cứu cũ nhưng không nằm
trong danh sách model chạy của thử nghiệm này.

## 1. Chuẩn bị Python và cài dependencies

Trên Windows, dùng Python 3.12. Mở PowerShell tại thư mục gốc repo. Nếu
đã có `.venv312` thì bỏ qua lệnh tạo môi trường:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip install -r .\embedding\requirements.txt
```

Các dependencies cơ bản cài Sentence-Transformers và Qdrant client. Model
BKAI cần thêm bộ phân đoạn từ tiếng Việt:

```powershell
python -m pip install -r .\embedding\requirements-bkai.txt
```

Nếu PowerShell chặn kích hoạt môi trường, chỉ cho phép trong terminal hiện
tại rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv312\Scripts\Activate.ps1
```

Xác nhận dấu nhắc có `(.venv312)` và `python --version` trả về Python
3.12. Nếu không muốn kích hoạt môi trường, thay `python` trong các lệnh
bên dưới bằng `.\.venv312\Scripts\python.exe`.

## 2. Kiểm tra đầu vào parser và chunking

Script tạo fixture cần hai file sau:

- `parser\parsed_jsons\L01.json`
- `chunking\chunking_rules.py`

Script gọi hàm `chunk_legal_document` từ thuật toán chunking hiện có. Nếu
thiếu một trong các file trên sau khi clone, hãy kiểm tra repo đã được clone
đầy đủ và terminal đang ở thư mục gốc:

```powershell
Get-Location
Test-Path .\parser\parsed_jsons\L01.json
Test-Path .\chunking\chunking_rules.py
```

## 3. Tạo tập chunk mẫu cố định

Chạy:

```powershell
python .\embedding\prepare_chunk_dataset.py
```

Script ghi kết quả vào
`embedding\data\han_gia_dinh_smoke_chunks.json`, sử dụng chunker hiện có
với Config A (`parent_max_chars=1500`, `child_max_tokens=256`,
`child_max_units=200`, `child_min_words=20`). Script in ra số lượng chunk
và SHA-256. Fixture của thử nghiệm hiện có 321 child chunk.

Hãy tạo fixture một lần trước khi so sánh, sau đó dùng cùng file cho cả ba
model. Nếu dữ liệu parser, chunker, cấu hình hoặc bộ phân đoạn từ thay đổi,
việc tạo lại fixture có thể làm hash thay đổi. Mỗi kết quả đều ghi hash để
đối chiếu các lượt chạy có dùng cùng dữ liệu hay không.

## 4. Cấu hình Qdrant local

Smoke test dùng Qdrant embedded local nên không cần chạy riêng Qdrant
server hoặc Docker. Chọn một thư mục lưu dữ liệu lâu dài trong repo:

```powershell
$env:QDRANT_PATH = "$PWD\qdrant_data"
```

Giữ biến môi trường này trong terminal cho tất cả các lượt chạy. Qdrant tự
tạo thư mục khi mở cơ sở dữ liệu lần đầu. Script dùng collection riêng cho
từng model và hash fixture; sau khi nạp sẽ kiểm tra số point. Script không
xóa collection hoặc dữ liệu cũ.

## 5. Chạy một model rồi chạy cả ba

Nên chạy một model trước để xác nhận việc tải model, embedding, lưu vector
và truy hồi:

```powershell
python .\embedding\retrieval_smoke_test.py --model AITeamVN/Vietnamese_Embedding --results .\embedding\results\aiteamvn.json
```

Sau đó chạy hai model còn lại với cùng fixture và cùng Qdrant:

```powershell
python .\embedding\retrieval_smoke_test.py --model bkai-foundation-models/vietnamese-bi-encoder --results .\embedding\results\bkai.json
python .\embedding\retrieval_smoke_test.py --model BAAI/bge-m3 --results .\embedding\results\bge-m3.json
```

Mỗi lượt embedding toàn bộ chunk, lưu vector cùng `chunk_id`, nội dung và
metadata vào Qdrant, rồi in Top-5 cho truy vấn mặc định:
“Điều kiện về độ tuổi kết hôn được quy định như thế nào?”

Các tùy chọn khác gồm `--chunks`, `--query`, `--top-k`, `--batch-size`,
`--device`, `--collection`, `--ground-truth` và `--results`. Xem danh sách
tùy chọn hiện hành bằng lệnh:

```powershell
python .\embedding\retrieval_smoke_test.py --help
```

Lần chạy đầu tải model từ Hugging Face nên có thể mất vài phút, đặc biệt
khi chỉ dùng CPU. Cần Internet cho đến khi model được lưu vào cache. Cảnh
báo về giới hạn tải ẩn danh từ Hugging Face không nhất thiết là lỗi.

## 6. Kiểm tra kết quả và xử lý lỗi thường gặp

File JSON trong `embedding\results` ghi model ID, tên collection, hash và
số lượng chunk, dimension, thời gian tải model và embedding tài liệu,
throughput, thời gian mã hóa query, thời gian tìm kiếm Qdrant, độ trễ truy
vấn, cùng Top-K gồm ID, điểm, nội dung và metadata. Độ trễ truy vấn chỉ là
thời gian query embedding cộng Qdrant vector search; không gồm tải model,
embedding tài liệu, reranking hoặc LLM.

Đối chiếu `chunk_file_sha256` và `chunk_count` giữa kết quả của ba model.
Lượt chạy thành công sẽ báo 321 points và trả Top-K có nội dung cùng
metadata.

Một số lỗi thường gặp:

- **`Could not open requirements file`:** kiểm tra thư mục hiện tại bằng
  `Get-Location` và xác nhận file tồn tại bằng
  `Test-Path .\embedding\requirements.txt`. Chạy lệnh cài từ thư mục gốc
  repo hoặc cung cấp đường dẫn đầy đủ tới file.
- **`Cần cài ... sentence-transformers` hoặc `qdrant-client`:** Python
  đang chạy không phải môi trường đã cài dependencies. Kích hoạt `.venv312`
  hoặc gọi trực tiếp `.\.venv312\Scripts\python.exe`.
- **Thiếu `underthesea` khi chạy BKAI:** cài
  `.\embedding\requirements-bkai.txt` vào cùng môi trường Python. Trên
  Windows nên dùng Python 3.12 vì tokenizer core có wheel dựng sẵn cho
  phiên bản này.
- **Lỗi tải model từ Hugging Face:** kiểm tra kết nối Internet và thử lại;
  lần đầu phải tải trọng số model.
- **Số point trong collection không bằng số chunk:** không xóa collection
  có thể chứa dữ liệu đang dùng. Kiểm tra tên collection, hash fixture và
  tùy chọn `--collection`. Tên mặc định đã bao gồm một phần hash fixture.

## 7. Ground truth cho Recall@5 và MRR@10

Chạy Top-K smoke test không cần ground truth, nhưng muốn tính Recall@5 và
MRR@10 thì cần nhãn. Các ví dụ chunking và bảng đánh giá chunking trong
repo mô tả ID chunk, cấu hình và thống kê chunk; chúng không phải nhãn
đánh giá câu hỏi nào liên quan tới chunk nào.

Tạo file JSON UTF-8 gồm các đánh giá đã được người đọc kiểm tra. Mỗi
`relevant_chunk_ids` phải chứa ID có trong chính fixture dùng cho cả ba
lượt chạy:

```json
[
  {
    "query": "Nam và nữ phải bao nhiêu tuổi mới được kết hôn?",
    "relevant_chunk_ids": ["l01_art_8_chunk_1"]
  },
  {
    "query": "Những hành vi nào bị cấm trong hôn nhân và gia đình?",
    "relevant_chunk_ids": ["l01_art_5_p1_chunk_2_1", "l01_art_5_p1_chunk_2_2"]
  }
]
```

Đây chỉ là ví dụ cấu trúc. Hãy xác minh ID trong
`embedding\data\han_gia_dinh_smoke_chunks.json` và tự đánh giá mức độ liên
quan dựa trên nội dung pháp luật. Không lấy kết quả Top-K do chính model
tạo ra làm ground truth.

Chạy cùng bộ câu hỏi đã gán nhãn cho từng model:

```powershell
python .\embedding\retrieval_smoke_test.py --model AITeamVN/Vietnamese_Embedding --ground-truth .\embedding\data\retrieval_ground_truth.json --results .\embedding\results\aiteamvn.json
python .\embedding\retrieval_smoke_test.py --model bkai-foundation-models/vietnamese-bi-encoder --ground-truth .\embedding\data\retrieval_ground_truth.json --results .\embedding\results\bkai.json
python .\embedding\retrieval_smoke_test.py --model BAAI/bge-m3 --ground-truth .\embedding\data\retrieval_ground_truth.json --results .\embedding\results\bge-m3.json
```

Script tính Recall@5 cho mỗi query bằng số chunk liên quan được tìm thấy
trong Top-5 chia cho tổng số chunk liên quan đã gán nhãn cho query đó, rồi
lấy trung bình trên các query. MRR@10 là trung bình nghịch đảo thứ hạng
của kết quả liên quan đầu tiên trong Top-10 (bằng 0 nếu không tìm thấy).
Nếu ground truth tham chiếu ID không tồn tại trong fixture, script báo
lỗi. Cần dùng đủ câu hỏi đa dạng đã được kiểm tra trước khi kết luận hoặc
chọn model thắng cuộc.
