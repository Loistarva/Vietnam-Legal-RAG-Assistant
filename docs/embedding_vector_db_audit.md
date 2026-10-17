# Audit Embedding và Vector DB

**Ngày audit:** 2026-10-11  
**Phạm vi:** Embedding, Qdrant, chunk fixture, metadata/truy xuất và mức sẵn sàng Week 6–7.  
**Kết luận tổng quát:** Dense embedding → Qdrant → Top-K đã chạy end-to-end trên ba model trong môi trường hiện có. Chưa có bằng chứng đánh giá retrieval bằng ground truth; dữ liệu nguồn và một số điều kiện tái lập chưa đủ tin cậy để chuyển thẳng sang production hoặc kết luận model tốt nhất.

Audit không sửa code, fixture, JSON kết quả hiện có hoặc Qdrant database hiện hữu. Ba lượt chạy lại dùng cache model ở chế độ offline và một Qdrant local mới nằm ngoài repository.

## A. Executive summary

### Đã kiểm chứng

- Môi trường `.venv312` dùng Python 3.12.10; `sentence-transformers 5.7.0`, `qdrant-client 1.19.1`, `underthesea 8.3.0`, `torch 2.14.1+cpu`, `transformers 5.19.0`. CUDA không khả dụng.
- Ba model `AITeamVN/Vietnamese_Embedding`, `bkai-foundation-models/vietnamese-bi-encoder` và `BAAI/bge-m3` đều tải được từ cache khi bật chế độ offline, tạo vector và ghi Qdrant thành công.
- Mỗi lượt dùng cùng fixture 321 child chunks, SHA-256 `f1d9af4423dd337072d467cf6fad31aa1436859eb77035ba6eb14d22796cce0b`, query mặc định, Top-K 5, batch size 32.
- Mỗi collection mới có đúng 321 point, đúng dimension/cosine; vector lưu có L2 norm xấp xỉ 1; kết quả có chunk ID, text và 17 trường metadata. Cả ba lượt trả `l01_art_8_chunk_1` ở Top-1.
- Mã nguồn embedding/vector-store và chunker đã qua parse cú pháp; `load_chunks` đọc được đủ 321 chunk. Công thức Recall@K đã được kiểm tra với ví dụ có relevant/missing IDs và từ chối ground truth rỗng.

### Chưa được chứng minh

- Không có `retrieval_ground_truth.json`; vì vậy Recall@5, MRR@10 và chất lượng tổng quát của retrieval là **N/A**, không phải 0% hay đã đạt ngưỡng 85%.
- Fixture chỉ có một truy vấn smoke test và dữ liệu từ L01, không phải benchmark 50–100 câu hỏi.
- Không có triển khai BM25 retrieval, hybrid/RRF, reranker hay zero-shot LLM baseline trong mã Python hiện được rà soát.
- Không thể xác nhận Git working tree sạch: lệnh `git status --short` không chạy được vì `git` không có trong PATH và không tìm thấy executable ở các vị trí cài Git phổ biến đã kiểm tra.
- Không chạy được pytest trong Python 3.12 vì môi trường báo `No module named pytest`; không cài thêm dependency theo phạm vi audit.

### Rủi ro ưu tiên

1. Metadata parser của L01 mâu thuẫn với metadata chuẩn hóa: cùng văn bản được ghi là `Quyết định`/`Không xác định`/không có ngày hiệu lực trong parser, trong khi nguồn metadata tổng hợp ghi là `Luật` và `Còn hiệu lực`. Fixture còn thiếu ngày hiệu lực, source URL và đường dẫn file.
2. Có 47/47 đường dẫn nguồn được ghi trong `data/normalized_metadata.json` không phân giải được thành file trong các thư mục dự án đã kiểm tra.
3. Sinh lại fixture trong môi trường có `underthesea` tạo 320 thay vì 321 chunk; 320 `embed_text` thay đổi so với fixture đang lưu. Kết quả benchmark hiện hành do đó không được tái tạo chỉ bằng lệnh chuẩn bị dữ liệu trong mọi môi trường.
4. 4/321 `embed_text` vượt giới hạn 256 token của BKAI; mã đặt `max_seq_length=256`, nên đầu vào bị truncation mà không được báo trong kết quả.

## B. Inventory

| File/đường dẫn | Vai trò và trạng thái | Phụ thuộc / vấn đề |
|---|---|---|
| `embedding/vector_store.py` | Có; chuẩn hóa chunk, tải Sentence-Transformers, encode vector, tạo client/Qdrant collection, upsert và search | Có kiểm tra dimension/giá trị hữu hạn; collection mặc định dùng cosine. Timer embedding bắt đầu sau bước tiền xử lý. |
| `embedding/retrieval_smoke_test.py` | Có; CLI smoke test, tạo collection, Top-K, tùy chọn ground truth/JSON kết quả | Kiểm tra số point nhưng không đối chiếu toàn bộ tập ID/payload đã lưu. Kết quả không ghi query, device, package versions hoặc model revision. |
| `embedding/prepare_chunk_dataset.py` | Có; gọi chunker trên `parser/parsed_jsons/L01.json`, xuất fixture | Gọi fallback whitespace khi `underthesea` không cài; kết quả hiện lưu ghi rõ backend fallback. |
| `embedding/data/han_gia_dinh_smoke_chunks.json` | Có; fixture L01, 321 chunks, hash đã ghi ở trên | Mỗi record có ID/text và các trường metadata phẳng; loader dựng metadata từ các trường này. Fixture không chứa `source_url`/`file_path`; ngày hiệu lực rỗng. |
| `embedding/results/aiteamvn.json`, `bkai.json`, `bge-m3.json` | Có; JSON đo đạc ngày 2026-10-11, cùng hash và 321 chunks | Các số tương ứng với bảng hiện tại trong README/tài liệu thực nghiệm; không có ground-truth metrics. Thời điểm, query, hardware và model revision không được serialize. |
| `embedding/README.md` | Có; có hướng dẫn cài đặt, chuẩn bị fixture, Qdrant, chạy model, kết quả và ground truth | Hướng dẫn có ích cho embedding, nhưng phần ground truth chỉ là ví dụ; file ground truth chưa tồn tại. |
| `docs/embedding_experiment.md` | Có; mô tả lựa chọn model, kết quả, tiêu chí và giới hạn | Ghi cùng bộ số liệu smoke test như README/JSON; chính tài liệu cũng xác nhận chưa có Recall/MRR. |
| `docs/embedding_model_research.md` | Không có | Không thấy file riêng; ghi chú khảo sát model nằm trong `docs/embedding_experiment.md`. |
| `README.md` | Có nhưng chỉ có tiêu đề dự án | Không có quickstart hoặc liên kết tới README module embedding. |
| `embedding/requirements.txt`, `requirements-bkai.txt` | Có | Khai báo dependency dạng range; requirements BKAI tham chiếu requirements nền và thêm `underthesea`. |
| `schemas/metadata_schema.json` | Có; JSON Schema cho document/article/chunk | Yêu cầu `document_metadata`, date hợp lệ và status trong enum; parser thực tế dùng key `metadata`, có `effective_date: null` và `validity_status: "Không xác định"`. |
| `docs/data_contract.md` | Có; quy ước ID và contract document/article/chunk | Mô tả `document_metadata`, không khớp key parser hiện tại. |
| `parser/parsed_jsons/L01.json` | Có; nguồn JSON thực tế của fixture, 131 Điều | Payload `metadata` không khớp JSON Schema; giá trị loại văn bản/ngày/status cần đối chiếu nguồn chuẩn. |
| `data/normalized_metadata.json` | Có; 9 văn bản và 261 bản ghi metadata cấp Điều | Scope ghi `raw_data_received: false`; bản ghi Điều chỉ có metadata/title, không có `text`, `content`, `body` hoặc `chunks`. |
| `data/raw_data/` | Có PDF L01, ND01–ND03 và TT01–TT04 | PDF L01 tồn tại, nhưng chưa được xác minh nội dung PDF có khớp parser JSON. Đường dẫn trong normalized metadata không trỏ đến các file này. |
| `../tests`, `parser/test_parser.py` | Có test nguồn | Không chạy được pytest trong `.venv312`; test schema dùng Pydantic riêng, không chứng minh parser output tuân thủ `schemas/metadata_schema.json`. |
| `.gitignore` | Có | Bỏ qua `.venv*`, bytecode và `/qdrant_data/`; không bao phủ mọi tên local Qdrant/cache nếu đặt chỗ khác trong repo. |
| BM25/hybrid/reranker | Không thấy module thực thi trong các file Python của repository | Chunker chỉ xuất định dạng Elasticsearch; SRS và tài liệu chunking mô tả BM25/RRF/reranker nhưng không có implementation retrieval tương ứng. |

## C. Test evidence

| ID | Mục tiêu/lệnh | Kết quả thực tế | Trạng thái | Giới hạn |
|---|---|---|---|---|
| T-01 | Kiểm tra package bằng `.venv312\Scripts\python.exe` | Python 3.12.10; torch 2.14.1+cpu; sentence-transformers 5.7.0; qdrant-client 1.19.1; underthesea 8.3.0; transformers 5.19.0; CUDA false | PASS | Chỉ xác nhận environment hiện tại, không phải tương thích mọi Python/OS. |
| T-02 | `python -m pytest --version` trong `.venv312` | Thất bại: `No module named pytest` | BLOCKED | Không cài package trong audit; unit tests chưa chạy. |
| T-03 | `git status --short` | PowerShell báo `git` không nhận diện là command; không tìm thấy executable tại các vị trí cài Git phổ biến đã kiểm tra | NOT VERIFIED | Không xác nhận được trạng thái thay đổi của repository trước/sau audit. |
| T-04 | `ast.parse` với `embedding/vector_store.py`, `embedding/retrieval_smoke_test.py`, `embedding/prepare_chunk_dataset.py`, `chunking/chunking_rules.py`; import loader/metric; đọc fixture | Tất cả parse được; loader trả 321 chunk với 17 metadata keys; Recall mẫu là 0.5 và 0.0; ground truth rỗng ném `ValueError` | PASS | Không thay thế unit/integration tests đầy đủ. |
| T-05 | Chạy lần lượt `retrieval_smoke_test.py --model <ID> --results <file>` cho cả ba model; bật `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, dùng Qdrant local mới ngoài repo | Cả ba exit code 0; mỗi lượt nạp 321 point, trả Top-5 có payload; kết quả chi tiết nằm tại `C:\Users\Thy\.copilot\session-state\23e9c32d-d09c-4a47-bb16-0eb258189efd\files\embedding-vector-audit\` | PASS | Một query và một lượt mỗi model; số đo CPU biến thiên; không có relevance labels. |
| T-06 | Mở Qdrant local cô lập, đọc collection info/count/point/vector | Ba collection có count 321; dimension lần lượt 1024/768/1024; distance cosine; text và metadata tồn tại; dimension vector khớp; L2 norm xấp xỉ 1.000000 | PASS | Không kiểm toán lại toàn bộ database Qdrant hiện hữu trong `qdrant_data`; database đó được giữ nguyên. |
| T-07 | Tokenize fixture bằng tokenizer cache cục bộ và so với `max_seq_length` trong code | AITeamVN: max 301/2048, 0 vượt; BKAI: max 307/256, 4 vượt; BGE-M3: max 301/8192, 0 vượt | PARTIAL | Đo token count trên `embed_text` hiện lưu; BKAI tự truncation do giới hạn Sentence-Transformers, chưa đánh giá ảnh hưởng retrieval của 4 chunk. |
| T-08 | Tạo lại L01 chunks trong bộ nhớ bằng cùng config, với `underthesea 8.3.0`; không ghi file | Fixture hiện có 321; generator hiện tại cho 320; 1 ID bị loại; 320 ID chung có `embed_text` khác; 4 chunk có `text` khác | FAIL (tái lập fixture) | Chỉ đối chiếu L01 và cấu hình đã lưu; không thay đổi fixture hay parser. |
| T-09 | `retrieval_smoke_test.py --help` | Exit code 0; CLI hiển thị các tham số `--chunks`, `--model`, `--query`, `--top-k`, `--batch-size`, `--device`, `--collection`, `--ground-truth`, `--results` | PASS | Help không xác nhận các nhánh lỗi runtime khác. |

**Lệnh smoke test tương đương đã chạy** (đường dẫn Qdrant/results thực tế được đặt trong session scratch để tránh đụng dữ liệu repo):

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:QDRANT_PATH = "<session-scratch>\qdrant-local"
.\.venv312\Scripts\python.exe .\embedding\retrieval_smoke_test.py --model AITeamVN/Vietnamese_Embedding --results <session-scratch>\aiteamvn.json
.\.venv312\Scripts\python.exe .\embedding\retrieval_smoke_test.py --model bkai-foundation-models/vietnamese-bi-encoder --results <session-scratch>\bkai.json
.\.venv312\Scripts\python.exe .\embedding\retrieval_smoke_test.py --model BAAI/bge-m3 --results <session-scratch>\bge-m3.json
```

## D. So sánh embedding model

Cấu hình ba lượt audit: cùng fixture/hash, query mặc định `Điều kiện về độ tuổi kết hôn được quy định như thế nào?`, Top-K 5, batch 32, CPU, cache model offline, Qdrant local cosine.

| Model | Tiền xử lý / max tokens | Dimension | Nạp model (s) | Embed 321 (s) | chunks/s | Query encode (ms) | Qdrant search (ms) | Tổng query (ms) | Top-1 / cosine | Recall@5 / MRR@10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `AITeamVN/Vietnamese_Embedding` | identity / 2048 | 1024 | 12.764 | 185.306 | 1.73 | 208.66 | 28.11 | 236.77 | `l01_art_8_chunk_1` / 0.60566 | N/A / N/A |
| `bkai-foundation-models/vietnamese-bi-encoder` | underthesea / 256 | 768 | 1.310 | 48.072 | 6.68 | 46.61 | 8.39 | 55.00 | `l01_art_8_chunk_1` / 0.65203 | N/A / N/A |
| `BAAI/bge-m3` | identity / 8192 | 1024 | 2.818 | 207.595 | 1.55 | 237.16 | 28.21 | 265.37 | `l01_art_8_chunk_1` / 0.73843 | N/A / N/A |

Dung lượng vector float32 ước tính: 1,314,816 byte cho dimension 1024 và 986,112 byte cho dimension 768, chưa gồm payload/index/overhead. Đây là ước lượng từ số chunk × dimension × 4 byte.

Các số đo là một lần chạy CPU; thời gian tải model trong lần này chỉ đo từ cache offline. `EmbeddingService._embed` thực hiện preprocessing trước khi bắt đầu timer encode, nên thời gian và throughput ở bảng **không tính thời gian word segmentation của BKAI**. Không dùng các cosine score giữa các model để xếp hạng chất lượng. Bảng README/JSON lần chạy 2026-10-11 trước audit ghi số thời gian khác; cùng kết luận Top-1, dimension và cùng fixture. Sai khác thời gian là phù hợp với các lượt đơn trên CPU, không phải bằng chứng ranking.

Không có prompt/prefix riêng cho query hoặc document trong wrapper: query và document đều đi qua `model.encode`; BKAI áp dụng cùng word segmentation cho cả hai. Đây là tính nhất quán của implementation, nhưng smoke test chưa chứng minh chất lượng trên bộ truy vấn/domain đủ rộng.

## E. Vector DB audit

- **Client:** hỗ trợ Qdrant embedded qua `QDRANT_PATH`; nếu không có path thì dùng `QDRANT_URL` (mặc định localhost) và `QDRANT_API_KEY`.
- **Collection:** cosine distance; kích thước vector được kiểm tra lúc mở collection. Tên mặc định gồm slug model và 12 ký tự đầu SHA-256 fixture. Ba lượt audit tạo collection riêng, không ghi vào `qdrant_data` đã có.
- **Upsert/ID:** Qdrant point ID là UUIDv5 chỉ từ `chunk_id`; `upload_points` upsert. ID ổn định khi chunk ID giữ nguyên, nhưng có thể va chạm/ngầm ghi đè nếu dùng lại collection cho dữ liệu khác có cùng chunk ID. Collection mặc định có hash dataset giảm rủi ro này.
- **Payload/retrieval:** lưu `chunk_id`, `text`, `metadata`; kiểm tra trực tiếp point trong DB cho thấy 17 metadata fields được giữ lại. Top-K trả về đủ `chunk_id`, score, text, metadata.
- **Tính nhất quán:** script xác nhận `count == len(chunks)` sau nạp. Đây là kiểm tra hữu ích nhưng chưa so sánh tập point IDs/payload thực tế với dataset; count bằng nhau không phát hiện trường hợp tập IDs cũ/sai có cùng cardinality.
- **Cập nhật dữ liệu:** chạy lại dùng cùng ID sẽ ghi đè point tương ứng. Khi dataset đổi mà dùng lại `--collection`, point cũ không có ID trong lượt mới không tự bị xóa. Không có thao tác xóa tự động trong smoke test; audit không xóa collection/cache.
- **Khả năng khôi phục:** có thể dựng lại collection từ fixture và model, nhưng kết quả phụ thuộc phiên bản model/tokenizer và backend chunking; model revision, config/version của dependency và backend tokenizer chưa được khóa đủ để tái tạo chính xác.
- **Git ignore:** `.gitignore` loại `/qdrant_data/`, `.venv*/` và `__pycache__/`; vị trí local Qdrant khác nằm trong repo có thể không được ignore. Model cache đang ở ngoài repo.

## F. Retrieval và evaluation

- **Luồng thực tế:** parser JSON L01 → `chunk_legal_document` → fixture child chunks → `embed_text` → Sentence-Transformers → Qdrant → query embedding → `query_points` Top-5.
- **Nguồn nội dung:** fixture có nội dung text thực tế, không chỉ 261 metadata cấp Điều. Fixture hiện dùng 321 chunks từ 131 articles của L01; `text` dài nhất 897 ký tự, `embed_text` dài nhất 1060 ký tự. Tập 261 bản ghi trong `data/normalized_metadata.json` là article metadata/title, không có trường nội dung Điều đầy đủ; đó không phải nguồn text mà smoke test embedding.
- **Top-K:** cả ba model trả đúng cấu trúc payload và Top-1 là Điều 8, Khoản 1 cho một query phù hợp. Đây chỉ là một kiểm tra smoke, không chứng minh recall trên câu hỏi khác.
- **Metric:** code tính macro-average Recall@5 theo từng query với mẫu số là số relevant IDs và MRR@10 theo thứ hạng relevant đầu tiên. Ground truth rỗng bị từ chối; ID ngoài fixture bị báo lỗi; query/list relevant IDs thiếu bị báo lỗi.
- **Ground truth:** không tìm thấy `embedding/data/retrieval_ground_truth.json` hay benchmark QA đã gán nhãn. Không có Recall@5/MRR@10 hoặc Recall@1/10 thực đo; mục tiêu Recall@5 ≥85% chưa được xác minh.
- **Giới hạn đánh giá:** chưa có tách Dev/Test, nhãn do chuyên gia pháp lý rà soát, số query 50–100, báo cáo theo query, hit rate/precision, percentile latency, hay so sánh BM25 → hybrid → reranker. Để benchmark có ý nghĩa, cần bộ QA–relevant chunk được gán nhãn độc lập, split cố định và cùng một tập Test cho mọi model.

## G. Documentation, schema và dependency audit

### Tài liệu

- `embedding/README.md` hướng dẫn tương đối đủ cho smoke test: tạo environment Python 3.12, cài dependencies, tạo fixture, chọn Qdrant local, chạy ba model, lưu JSON và cấu trúc ground truth. Cần bổ sung cảnh báo fixture phụ thuộc `underthesea`, truncation BKAI và thực tế preprocessing time đang bị loại khỏi timing.
- `docs/embedding_experiment.md` và JSON kết quả cùng ghi một query, 321 chunks, dimension, timing và không có ground truth; kết luận chưa chọn model là phù hợp. Nội dung này không phải benchmark chất lượng.
- README gốc chỉ có tiêu đề; chưa dẫn người mới tới module embedding. `docs/embedding_model_research.md` không tồn tại riêng; phần nghiên cứu nằm trong experiment doc.
- `docs/data_contract.md`/`schemas/metadata_schema.json` yêu cầu key `document_metadata`, trong khi parser tạo key `metadata`. Schema còn yêu cầu ngày hiệu lực dạng date và status trong enum; dữ liệu parser có `null`/`"Không xác định"`. `../tests` khai báo Pydantic schema khác và không tự áp dụng JSON Schema file nói trên.
- Hướng dẫn chạy ghi đúng CLI và vị trí JSON kết quả, nhưng các tên JSON mặc định được ghi đè nếu chạy đúng ví dụ trên repository. Dùng tên file khác khi cần giữ kết quả cũ.

### Dependencies

- `requirements.txt`: `sentence-transformers>=3.4,<6`, `qdrant-client>=1.13,<2`; `requirements-bkai.txt` tham chiếu file nền và thêm `underthesea>=8.3,<9`.
- Đây là range tương thích được khai báo, không phải lockfile. Phiên bản được xác nhận chạy trong audit chỉ là các phiên bản đã ghi ở T-01.
- Torch/Transformers là dependency gián tiếp của Sentence-Transformers trong cấu hình đã chạy; không có manifest khóa đầy đủ toàn bộ dependency graph/model revision.
- README chọn Python 3.12 trên Windows; audit xác nhận Python 3.12.10 hiện tại. Chưa xác nhận các phiên bản Python/OS khác.

## H. Mức sẵn sàng Week 6–7

| Yêu cầu | Trạng thái | Bằng chứng/thiếu sót |
|---|---|---|
| BM25-only baseline | FAIL | Không thấy BM25 retriever/index thực thi; chunker chỉ có serializer tài liệu cho Elasticsearch. |
| Zero-shot LLM baseline không RAG | FAIL | Không thấy pipeline/model evaluation cho baseline này. |
| Dense retrieval baseline chạy được | PARTIAL | Ba model đã encode/search thành công trên Qdrant, nhưng chỉ một query smoke, chưa có ground-truth score. |
| Hybrid retrieval BM25 + dense | FAIL | SRS/chunk docs mô tả nhưng không có retriever/hợp nhất RRF trong code hiện rà soát. |
| Reranker tích hợp và đánh giá | FAIL | Không tìm thấy integration/test kết quả reranker. |
| Benchmark 50–100 legal QA pairs | FAIL | Không có ground-truth file; mới có query mặc định và ví dụ README. |
| Dev/Test split | FAIL | Chưa có bộ nhãn hoặc split. |
| Đo Recall@5, mục tiêu ≥85% | PARTIAL | Hàm/script có thể tính Recall@5 khi có ground truth; chưa có số đo nên chưa đạt/không đạt ngưỡng. |
| So sánh BM25-only → tuned Hybrid → Hybrid + Reranker | FAIL | Chưa có các hệ thống/baseline và tập đánh giá tương ứng. |

## I. Findings

### F-01 — HIGH: Metadata pháp lý của L01 sai lệch/không đầy đủ

- **Bằng chứng:** `parser/parsed_jsons/L01.json` ghi `document_type="Quyết định"`, `effective_date=null`, `validity_status="Không xác định"`; `data/normalized_metadata.json` ghi văn bản L01 là `Luật`, số hiệu `52/2014/QH13`, trạng thái nguồn `Còn hiệu lực`. Fixture đưa `document_type="Quyết định"`, ngày hiệu lực rỗng, status `"Không xác định"` vào cả 321 payload.
- **Ảnh hưởng:** filter theo loại văn bản/hiệu lực và citation có thể sai hoặc không đáng tin. Smoke test không lọc theo validity status.
- **Cách khắc phục:** xác định nguồn metadata có thẩm quyền, sửa mapping parser/metadata và kiểm tra chéo tất cả văn bản trước khi tạo collection production.
- **File cần sửa:** `parser/parser.py`, dữ liệu parser L01, `schemas/metadata_schema.json`, `docs/data_contract.md`, pipeline tạo fixture.
- **Điều kiện nghiệm thu:** metadata từng văn bản khớp nguồn pháp lý đã xác minh; không đưa record `null/unknown` vào corpus production khi chưa có chính sách rõ; test schema áp dụng trên parser output thật.

### F-02 — HIGH: Không truy vết được payload về file nguồn qua metadata hiện tại

- **Bằng chứng:** 47/47 đường dẫn file duy nhất trong `data/normalized_metadata.json` không tồn tại dưới project root, `data/` hoặc `data/raw_data/` theo kiểm tra filesystem. L01 PDF thực có tại `data/raw_data/laws_and_decrees/L01.pdf`, còn metadata tham chiếu `laws_decrees/522014QH13.pdf`. Fixture không có `source_url` hoặc `file_path`; payload chỉ giữ doc ID/title/Điều.
- **Ảnh hưởng:** không thể dùng các path đã lưu để mở/đối chiếu nguồn; citation UI và kiểm chứng pháp lý thiếu liên kết nguồn.
- **Cách khắc phục:** chuẩn hóa đường dẫn tương đối theo một root được định nghĩa, xác minh file tồn tại, lưu nguồn URL/file và phiên bản/hiệu lực vào payload.
- **File cần sửa:** `data/normalized_metadata.json`, tài liệu/data mapping, `chunking/chunking_rules.py`, `embedding/prepare_chunk_dataset.py`.
- **Điều kiện nghiệm thu:** mọi path được dùng cho retrieval resolve được; test kiểm tra 100% link nguồn; Top-K trả về source reference truy xuất được.

### F-03 — MEDIUM: BKAI truncation không được phát hiện trong benchmark

- **Bằng chứng:** tokenizer cục bộ đếm được 4/321 `embed_text` dài hơn 256 tokens, tối đa 307 tokens; `MODEL_CONFIGS` đặt BKAI `max_seq_length=256`. Model wrapper không ghi nhận/chặn các sample bị cắt.
- **Ảnh hưởng:** tối đa 51 token cuối của một số chunk có thể không đi vào vector; điều khoản có nội dung trọng yếu cuối chunk có thể bị mất.
- **Cách khắc phục:** chọn chunk/tokenizer limits khớp model, chia nhỏ chunk vượt ngưỡng hoặc báo truncation; đánh giá retrieval trước/sau thay đổi.
- **File cần sửa:** `chunking/chunking_rules.py`, `embedding/prepare_chunk_dataset.py`, `embedding/vector_store.py`, test embedding.
- **Điều kiện nghiệm thu:** không chunk nào vượt giới hạn tokenizer hoặc mọi lần cắt được báo/kiểm tra; regression test cho các chunk dài và query dài.

### F-04 — MEDIUM: Fixture không tái tạo ổn định theo môi trường tokenization

- **Bằng chứng:** fixture ghi backend `fallback whitespace segmentation (underthesea is not installed)` và có 321 chunk. Gọi cùng chunker/config trong Python hiện tại có `underthesea 8.3.0` cho 320 chunk; một ID biến mất, 320 `embed_text` khác nhau và 4 `text` khác nhau.
- **Ảnh hưởng:** chạy lại bước tạo dataset có thể đổi chunk IDs/nội dung/hash và làm benchmark/collection không so sánh cùng corpus.
- **Cách khắc phục:** quy định một backend chuẩn bắt buộc hoặc fallback có chủ ý và ổn định; ghi version/backend/config vào manifest và dùng fixture bất biến khi so sánh.
- **File cần sửa:** `embedding/prepare_chunk_dataset.py`, `chunking/chunking_rules.py`, `embedding/README.md`.
- **Điều kiện nghiệm thu:** hai lần build trong môi trường sạch theo lock tương đương cho cùng số chunk, IDs, nội dung và SHA-256; thay đổi backend phải tạo version dataset mới.

### F-05 — MEDIUM: Timing bỏ qua preprocessing BKAI

- **Bằng chứng:** `_embed` gọi `_prepare(texts)` trước khi bắt đầu `perf_counter`; `_prepare` chạy `underthesea.word_tokenize` cho BKAI. Vì vậy `embedding_seconds` và `query_embedding_seconds` không bao gồm thời gian này.
- **Ảnh hưởng:** thời gian/latency BKAI bị thấp giả tạo và throughput bị cao giả tạo so với pipeline end-to-end; so sánh tốc độ giữa các model chưa công bằng.
- **Cách khắc phục:** đo riêng preprocess, encode và tổng end-to-end; báo rõ timing scope trong JSON/README.
- **File cần sửa:** `embedding/vector_store.py`, `embedding/retrieval_smoke_test.py`, `embedding/README.md`.
- **Điều kiện nghiệm thu:** JSON lưu đủ preprocessing, encode và end-to-end time; test timing xác nhận preprocess được tính vào metric tổng.

### F-06 — MEDIUM: Kiểm tra collection dựa vào count, chưa xác minh toàn bộ dataset

- **Bằng chứng:** smoke test chỉ so `store.count()` với số chunks. Point ID được tạo từ UUIDv5 của `chunk_id`; `upload_points` upsert, không xóa points cũ không còn trong dataset. Tên collection mặc định có hash dataset 12 ký tự nhưng `--collection` cho phép tái sử dụng tên tùy ý.
- **Ảnh hưởng:** collection dùng lại có thể chứa tập IDs/payload cũ nhưng count vẫn bằng dataset; index sai corpus mà smoke test vẫn qua.
- **Cách khắc phục:** kiểm tra toàn bộ ID set/payload/version sau ingestion; tiếp tục dùng collection versioned, không tự xóa dữ liệu hiện hữu.
- **File cần sửa:** `embedding/vector_store.py`, `embedding/retrieval_smoke_test.py`.
- **Điều kiện nghiệm thu:** test phát hiện cùng-count nhưng khác-ID fixture và từ chối collection sai; collection manifest ghi model/dataset/version.

### F-07 — MEDIUM: Data contract, JSON Schema và parser output lệch nhau

- **Bằng chứng:** contract/JSON Schema yêu cầu `document_metadata`; parser dùng `metadata`. Schema bắt ngày hiệu lực dạng date và enum status giới hạn, trong khi parser có null/`Không xác định`. Test Pydantic lại định nghĩa biến thể schema khác và chưa chạy được do pytest thiếu.
- **Ảnh hưởng:** validation hiện tại không thể bảo đảm dữ liệu pháp luật đầu vào phù hợp contract/metadata filter.
- **Cách khắc phục:** chọn một schema chuẩn, cập nhật parser/chunker/test cùng một contract; thêm test schema trên JSON đã parse.
- **File cần sửa:** `schemas/metadata_schema.json`, `docs/data_contract.md`, `parser/parser.py`, `../tests`.
- **Điều kiện nghiệm thu:** bộ parser fixtures thật validate qua schema duy nhất; các trường bắt buộc/null/unknown có policy được kiểm tra bằng unit tests.

### F-08 — LOW: Thiếu test runner trong môi trường xác nhận và trạng thái Git không biết

- **Bằng chứng:** `python -m pytest --version` trả `No module named pytest`; `git status --short` không chạy vì không tìm thấy Git executable.
- **Ảnh hưởng:** không thể báo cáo unit-test result hoặc chắc chắn trạng thái thay đổi trước/sau audit.
- **Cách khắc phục:** dùng environment dự án đã cài test dependencies và có Git CLI; chạy tests trước khi merge.
- **File cần sửa:** dependency/test setup hoặc hướng dẫn developer nếu team muốn yêu cầu pytest/Git trong environment chuẩn.
- **Điều kiện nghiệm thu:** test suite chạy và lưu exit code; Git status/diff kiểm tra được trước/sau thay đổi.

## J. Action plan

| Ưu tiên | Hành động | Tiêu chí nghiệm thu |
|---|---|---|
| P1 | Xác minh và sửa metadata pháp lý L01/corpus cùng source paths; xác định policy với effective date/status chưa biết | Schema hợp lệ; loại văn bản, hiệu lực, số hiệu và URL/file path đối chiếu được với nguồn có thẩm quyền; 100% path dùng được. |
| P1 | Chuẩn hóa fixture generator và tokenizer backend; khóa/ghi rõ version model/dependencies/dataset | Build hai lần cùng môi trường cho cùng hash/ID; không có drift âm thầm khi `underthesea` có/không cài. |
| P1 | Tạo benchmark 50–100 QA pairs, relevance IDs đã được người đánh giá kiểm tra; chia Dev/Test | Test set cố định không dùng tuning; mọi ID tồn tại trong fixture; có Recall@5/MRR@10 theo query và macro. |
| P2 | Giải quyết chunk vượt 256 token BKAI và đo truncation cho mọi model | Báo cáo số chunk vượt ngưỡng bằng tokenizer từng model; không mất nội dung âm thầm. |
| P2 | Sửa phép đo preprocessing/encode/end-to-end latency | JSON có đủ metric phân tách; so sánh cùng hardware, cache state, query/batch và nhiều lượt. |
| P2 | Tăng kiểm tra ingestion Qdrant từ count sang tập ID/version/payload | Test bắt được collection có cùng count nhưng IDs sai; model/dataset được version hóa. |
| P2 | Đồng bộ data contract/schema/parser và bổ sung unit tests | Pytest chạy trong môi trường chuẩn; parser output thật qua schema, test metadata filtering. |
| P3 | Cập nhật README gốc, chỉ dẫn đọc audit/embedding docs; chuẩn hóa `.gitignore` cho Qdrant local tùy vị trí | Người mới có quickstart và không thể vô tình đưa DB/cache vào Git. |
| P3 | Sau khi dense benchmark ổn định, triển khai và đánh giá BM25-only → Hybrid/RRF → reranker | So sánh trên cùng Dev/Test, latency và Recall/MRR; chỉ chuyển bước khi đạt tiêu chí dự án. |

## K. Reproducibility

### Môi trường đã xác nhận

- Windows; `.venv312`; Python 3.12.10.
- torch 2.14.1+cpu; CUDA không khả dụng.
- sentence-transformers 5.7.0; qdrant-client 1.19.1; underthesea 8.3.0; transformers 5.19.0.
- Fixture: `embedding/data/han_gia_dinh_smoke_chunks.json`, 321 child chunks; SHA-256 `f1d9af4423dd337072d467cf6fad31aa1436859eb77035ba6eb14d22796cce0b`.
- Model cache có sẵn cho cả ba ID. Lượt audit dùng `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.
- Query: `Điều kiện về độ tuổi kết hôn được quy định như thế nào?`; Top-K 5; batch 32.
- Kết quả/log tạm của ba lượt audit được ghi ngoài repo tại `C:\Users\Thy\.copilot\session-state\23e9c32d-d09c-4a47-bb16-0eb258189efd\files\embedding-vector-audit\`. Qdrant audit được tạo trong `qdrant-local`; Qdrant repository hiện hữu không bị sửa.

### Giới hạn tái lập

- Model IDs không khóa revision/commit; dependency chỉ giới hạn range, không có lock đầy đủ.
- Fixture được tạo trong môi trường thiếu `underthesea`; generator hiện có môi trường tokenization khác và cho kết quả khác.
- JSON kết quả hiện có không lưu query, device, phiên bản package, model revision, preprocessing time riêng hoặc thời điểm đầy đủ; cần bổ sung nếu dùng làm benchmark chính thức.
- Không chạy pytest do thiếu pytest; Git status chưa xác minh do thiếu Git executable.
- Cần tạo ground truth độc lập trước khi tuyên bố đạt Recall@5 ≥85% hoặc chọn model theo chất lượng.

## Kết luận trực tiếp

1. **Đã thực sự thử nghiệm embedding model chưa?** Có. Ba model đều chạy lại thành công offline trên cùng fixture, với JSON/log từ lần audit và kết quả Top-1 nêu ở mục D. Các JSON lưu sẵn cũng ghi cùng fixture/hash và kết quả trước đó.
2. **Vector DB hoạt động đúng chưa?** Với smoke-test scope: có. Ba collection cô lập có đúng count/dimension/cosine, vectors chuẩn hóa và payload hợp lệ. Điều này chưa xác nhận tính nhất quán đầy đủ của database cũ hoặc dữ liệu production.
3. **Top-K có trả cấu trúc và metadata không?** Có, đã kiểm tra trực tiếp kết quả và point Qdrant; mỗi hit có ID, score, text, metadata. Metadata nguồn URL/file còn thiếu.
4. **Đã đánh giá bằng ground truth/Recall@5/MRR@10 chưa?** Chưa. Không có ground-truth file nên metric là N/A.
5. **Tài liệu đủ để thành viên mới chạy lại không?** README embedding có thể hướng dẫn chạy smoke test, nhưng README gốc sơ sài; cần sửa khác biệt backend fixture, truncation, timing và metadata trước khi dùng kết quả cho đánh giá chính thức.
6. **Cần gì trước Hybrid/Reranker?** Xác minh dữ liệu pháp luật và source links; làm fixture tái lập; xử lý truncation; xây benchmark QA có nhãn/split; hoàn thiện baseline dense có metric; sau đó mới tích hợp BM25, RRF và reranker.
7. **Ba việc tiếp theo ưu tiên:** (1) xác minh/sửa metadata và liên kết nguồn, (2) khóa quy trình fixture/model/dependency và xử lý BKAI truncation/timing, (3) xây bộ 50–100 QA pairs có relevance labels cùng Dev/Test để đo Recall@5/MRR@10.
