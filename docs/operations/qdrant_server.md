# Qdrant Server – Hướng dẫn vận hành

## 1. Kiến trúc Embedded và Server

Project có hai chế độ Qdrant:

| Chế độ | Cách kết nối | Dữ liệu nằm ở đâu | Dùng khi |
| --- | --- | --- | --- |
| Embedded/local | `QdrantClient(path=...)` | `data/indexes/qdrant_storage` trên máy ứng dụng | `scripts/build_index.py`, rollback hoặc chạy local tuần tự |
| Server | `QdrantClient(url=...)` | Docker named volume `vietnam-legal-qdrant-storage` | Retrieval, API và batch dùng chung collection |

Qdrant Server được publish trên `127.0.0.1:6333`, chỉ truy cập từ máy Windows này. Hai chế độ dùng hai kho dữ liệu độc lập. Chuyển sang server không tự đồng bộ những lần build index sau này.

Metadata sidecar nằm ngoài cả hai collection tại `data/indexes/vietnam_legal_chunks_metadata.json`. `QDRANT_PATH` giữ đường dẫn tham chiếu để `DenseRetriever.verify_index()` đọc sidecar; khi có `QDRANT_URL`, adapter không mở embedded database ở đường dẫn này. Không copy sidecar vào Docker volume.

## 2. Baseline collection

- Collection: `vietnam_legal_chunks`
- Số points: 2.322
- Vector dimension: 1.024
- Distance: COSINE
- Embedding model: `BAAI/bge-m3`
- Text field: `embed_text_raw`
- Corpus SHA-256: `c18239351424f62d65c4a146ef2a73ed023b1bf5330e0a3fdadb828872b91264`
- Qdrant server image: `qdrant/qdrant:v1.19.1`
- Python client: `qdrant-client==1.19.1`

`corpus_sha256` nhận diện corpus nguồn. Báo cáo migration có thêm SHA chính xác của point ID/payload và so sánh vector theo sai số tuyệt đối mặc định `1e-7`; đây là các phép kiểm tra khác nhau.

## 3. Khởi chạy và kiểm tra Docker

Từ thư mục gốc repository:

```powershell
docker compose -f .\deployment\qdrant\docker-compose.qdrant.yml config
docker compose -f .\deployment\qdrant\docker-compose.qdrant.yml up -d
docker ps --filter "name=vietnam-legal-qdrant"

$health = Invoke-RestMethod http://127.0.0.1:6333/
$health | Format-List *
$health.version

$collections = Invoke-RestMethod http://127.0.0.1:6333/collections
$collections.result.collections | Format-Table name
```

Kỳ vọng container ở trạng thái `Up`, version `1.19.1`, và collection `vietnam_legal_chunks` hiện diện sau migration. Server mới trước migration chưa có collection này.

Kiểm tra collection qua Python:

```powershell
python -c "from qdrant_client import QdrantClient; c=QdrantClient(url='http://127.0.0.1:6333'); i=c.get_collection('vietnam_legal_chunks'); print('Status:',i.status); print('Points:',i.points_count); print('Vectors:',i.config.params.vectors); c.close()"
```

## 4. Cấu hình ứng dụng

Trong PowerShell dùng server mode:

```powershell
$env:QDRANT_URL = 'http://127.0.0.1:6333'
$env:QDRANT_PATH = 'data/indexes/qdrant_storage'
```

- `QDRANT_URL` chọn Qdrant Server.
- `QDRANT_PATH` chỉ định đường dẫn local/metadata sidecar. Giữ giá trị này để DenseRetriever xác minh sidecar.
- CLI `scripts/run_retrieval.py` hỗ trợ cả `--qdrant-url` và `--qdrant-path`.
- `retrieval.run_dev_retrieval` lấy server URL từ biến môi trường `QDRANT_URL`.

Để quay về local mode, gỡ URL trong phiên hiện tại:

```powershell
Remove-Item Env:\QDRANT_URL -ErrorAction SilentlyContinue
```

`scripts/build_index.py` hiện vẫn ghi vào embedded collection. Chỉ đổi `QDRANT_URL` không chuyển hoặc cập nhật index khi chạy build-index; cần chạy migration/sync riêng sau một lần rebuild.

## 5. Migration và xác minh fingerprint

Migration chuyển point ID, vector và payload từ embedded collection hiện có; không tạo lại embedding. Sidecar được giữ nguyên trên máy ứng dụng.

Trước migration, đóng tiến trình retrieval/API/batch đang mở embedded storage. Chạy từ repository root với virtual environment đã kích hoạt:

```powershell
python .\deployment\qdrant\migrate_local_to_server.py `
  --source-path data/indexes/qdrant_storage `
  --url http://127.0.0.1:6333 `
  --collection vietnam_legal_chunks `
  --expected-count 2322 `
  --batch-size 128
```

Script xác minh sidecar, dimension và distance; tạo collection nếu thiếu; upsert point còn thiếu theo batches; không ghi đè point đích xung đột; rồi đọc lại đích và kiểm tra:

- ID và payload khớp chính xác.
- Vector khớp trong `vector_atol` (mặc định `1e-7`).
- Số points là 2.322.
- SHA payload khớp; ghi `max_abs_vector_diff` và `min_cosine_similarity`.

Kết quả được lưu tại `reports/retrieval/d4_3_qdrant_migration.json`. PASS cần `status=PASS`, `point_count=2322`, `payload_hash_match=true`, `vectors_within_tolerance=true` và `max_abs_vector_diff <= vector_atol`. Có thể chạy lại để xác minh hoặc tiếp tục point còn thiếu; point tương đương đã có sẽ không được upsert lại.

## 6. Chạy Retrieval và Batch Retrieval

Đảm bảo Elasticsearch đang chạy và cấu hình endpoint/index:

```powershell
$env:ELASTICSEARCH_URL = 'http://127.0.0.1:9200'
$env:QDRANT_URL = 'http://127.0.0.1:6333'
$env:QDRANT_PATH = 'data/indexes/qdrant_storage'
```

Batch runner lấy tên index từ `retrieval/config.yaml` hoặc `--elasticsearch-index`; không cấu hình `ELASTICSEARCH_INDEX` trong môi trường cho batch này. Chỉ bật chế độ Hugging Face offline nếu model đã được cache đầy đủ trên máy:

```powershell
$env:HF_HUB_OFFLINE = '1'
```

### Một truy vấn qua Hybrid Retrieval và Cross-Encoder

```powershell
python scripts/run_retrieval.py `
  --query 'Năm 2010, Luật Hôn nhân và gia đình 2000 có cấm kết hôn cùng giới không?' `
  --query-id D43_SERVER_HISTORICAL `
  --retriever hybrid `
  --reranker cross_encoder `
  --retrieval-top-k 50 `
  --top-k 5 `
  --qdrant-url $env:QDRANT_URL `
  --qdrant-path $env:QDRANT_PATH `
  --no-parent-context `
  --output reports\retrieval\d4_3_qdrant_server_smoke.json
```

Kiểm tra `config.as_of_date` là `2010-01-01`, `config.retriever.qdrant_url` là server URL, `retriever` là `hybrid_reranker`, và có tối đa 5 kết quả:

```powershell
$result = Get-Content .\reports\retrieval\d4_3_qdrant_server_smoke.json -Raw | ConvertFrom-Json
$result | Format-List query_id, retriever, top_k
$result.config | Format-List as_of_date, retrieval_top_k, rerank_top_k
$result.config.retriever | Format-List qdrant_url, qdrant_storage_path, collection
$result.results[0] | ConvertTo-Json -Depth 12

if ($result.config.retriever.qdrant_url -ne $env:QDRANT_URL) {
    throw "Retrieval smoke test không dùng Qdrant Server theo QDRANT_URL."
}
if ($result.config.as_of_date -ne '2010-01-01') {
    throw "Ngày lịch sử không đúng: $($result.config.as_of_date)"
}
Write-Host 'PASS: one-query Hybrid Retrieval used Qdrant Server and the historical as_of_date.'
```

### Batch Retrieval trên Dev

Trước khi chạy toàn bộ Dev set, có thể kiểm tra Batch Retrieval bằng một query. Lệnh dùng `QDRANT_URL` từ môi trường và output envelope phải ghi URL tại `config.qdrant_url`:

```powershell
$smokeQueries = Join-Path $PWD 'reports\retrieval\d4_3_batch_smoke_query.json'
@([PSCustomObject]@{
    id = 'D43_BATCH_SMOKE'
    question = 'Năm 2010, Luật Hôn nhân và gia đình 2000 có cấm kết hôn cùng giới không?'
    as_of_date = '2010-01-01'
}) | ConvertTo-Json -Depth 5 | Set-Content -Path $smokeQueries -Encoding utf8

python retrieval/run_dev_retrieval.py `
  --queries $smokeQueries `
  --elasticsearch-url $env:ELASTICSEARCH_URL `
  --output-dir .\reports\retrieval\d4_3_batch_smoke `
  --output-prefix dev

$batchSmoke = Get-Content .\reports\retrieval\d4_3_batch_smoke\dev_hybrid.json -Raw | ConvertFrom-Json
$batchSmoke = $batchSmoke[0]
$batchSmoke.config | Format-List qdrant_url, as_of_date, collection
if ($batchSmoke.config.qdrant_url -ne $env:QDRANT_URL) {
    throw 'Batch smoke test không dùng Qdrant Server theo QDRANT_URL.'
}
Write-Host 'PASS: one-query batch used Qdrant Server.'
```

Khi smoke test pass, chạy toàn bộ Dev set. Runner đọc từng query theo ID/ngày trong benchmark và ghi riêng kết quả BM25, Dense và Hybrid:

```powershell
python retrieval/run_dev_retrieval.py `
  --queries .\data\benchmark\queries_dev.json `
  --elasticsearch-url $env:ELASTICSEARCH_URL `
  --output-dir .\retrieval\results `
  --output-prefix dev
```

Các file đầu ra là `retrieval/results/dev_bm25.json`, `dev_dense.json` và `dev_hybrid.json`. Kiểm tra `config.qdrant_url` trong envelope để xác nhận batch dùng server. Corpus SHA và metadata index vẫn được xác minh trước khi truy vấn.

## 7. Restart, backup và truy cập đồng thời

### Restart và kiểm tra persistence

```powershell
docker compose -f .\deployment\qdrant\docker-compose.qdrant.yml restart
Start-Sleep -Seconds 5
Invoke-RestMethod http://127.0.0.1:6333/collections
```

Xác nhận `vietnam_legal_chunks` vẫn có 2.322 points. Dữ liệu server ở Docker named volume `vietnam-legal-qdrant-storage`; restart container không xóa volume. Không dùng `docker compose down -v` khi vận hành thường ngày.

### Backup volume và sidecar

Để có bản backup nhất quán, dừng các app/job dùng server rồi dừng Qdrant trước khi archive volume:

```powershell
$backupDir = Join-Path $PWD 'backups\qdrant'
New-Item -ItemType Directory -Force $backupDir | Out-Null
$backupDir = (Resolve-Path $backupDir).Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

docker compose -f .\deployment\qdrant\docker-compose.qdrant.yml stop
docker run --rm `
  --mount 'type=volume,source=vietnam-legal-qdrant-storage,target=/data,readonly' `
  --mount "type=bind,source=$backupDir,target=/backup" `
  busybox:1.36 sh -c "tar czf /backup/qdrant-storage-$stamp.tar.gz -C /data ."

Copy-Item .\data\indexes\vietnam_legal_chunks_metadata.json `
  (Join-Path $backupDir "vietnam_legal_chunks_metadata-$stamp.json")

docker compose -f .\deployment\qdrant\docker-compose.qdrant.yml start
```

Backup volume chứa collection và backup riêng sidecar. Giữ thêm corpus tương ứng với `corpus_sha256` đã ghi nhận. Không xóa embedded source cho đến khi bản backup và server retrieval đã được xác minh.

### Tránh truy cập đồng thời embedded storage

Embedded Qdrant dùng file local và không phải dịch vụ chia sẻ cho nhiều tiến trình. Không chạy đồng thời các retrieval/API/batch local và thao tác build/migration mở cùng `data/indexes/qdrant_storage`. Qdrant Server mode không mở file embedded; có thể dùng cho các tiến trình chia sẻ qua URL.

`scripts/build_index.py` vẫn ghi embedded storage, không ghi server. Nếu rebuild local index, dừng những tiến trình local đang dùng file đó; sau khi build cần migration/sync có kiểm tra trước khi ứng dụng server dùng corpus mới.

## Rollback và giới hạn triển khai

Giữ nguyên Docker volume, sidecar và embedded source. Dừng app/job, bỏ `QDRANT_URL` để quay lại local mode, rồi chạy các tiến trình local theo thứ tự để tránh cùng mở embedded storage.

Đây là Docker Desktop trên máy phát triển, bind loopback và không có HA. Nếu ứng dụng chạy trong container khác, cần chung Docker network và dùng service name thay cho `127.0.0.1`.
