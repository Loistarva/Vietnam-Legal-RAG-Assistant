# Sprint 6 – Tích hợp Hybrid Retrieval + Reranker (Dev 5)

Owner: Dev 5 (Reranker & Packaging Lead). Tài liệu mô tả interface, contract đầu ra, cấu hình, cách chạy standalone và các điểm cần phối hợp.

## 1. Trạng thái: phần chạy thật và phần giả lập

| Thành phần | Trạng thái | Kiểm chứng |
| --- | --- | --- |
| `Reranker` (cắt candidate, khử trùng lặp, xếp hạng, bảo toàn trường) | Chạy thật | `test/test_reranker.py` |
| `MockScorer` (điểm cố định theo `chunk_id` hoặc tỉ lệ token câu hỏi xuất hiện trong chunk) | Stub, không phải mô hình liên quan | Unit test |
| `CrossEncoderScorer` (`BAAI/bge-reranker-v2-m3`) | Chạy thật (sentence-transformers 5.7.0, GPU) | Unit test bằng model giả; chạy tay trên fixture và 10 câu Dev (mục 5.1) |
| `RetrievalPipeline` + `HybridRetriever` của Dev 4 | Chạy thật với nhánh BM25/Dense giả lập đúng dạng output adapter | `test/test_integration.py` |
| CLI `--retriever fixture` / `--retriever mock` | Chạy offline | Integration test; chạy tay 285 câu Dev |
| CLI `--retriever hybrid` (Elasticsearch + Qdrant thật) | Đã nối dây; **chưa chạy** vì máy phát triển không có Elasticsearch/Qdrant index | Chỉ test nhánh lỗi cấu hình |

Đã đo latency của reranker thật (mục 5.1), nhưng chưa có số đo chất lượng: candidate pool thật cần Elasticsearch và Qdrant. Bước tiếp theo là chạy `--retriever hybrid --reranker cross_encoder` trên Dev set (mục 7).

## 2. Luồng xử lý

```text
query
  └─► Retriever.search(query, retrieval_top_k)          # HybridRetriever (Dev 4): BM25 ∥ Dense → RRF
        └─► to_contract_result()                         # map về Retrieval result (mục 4.3)
              └─► Reranker.rerank(query, candidates, top_k)
                    ├─ khử trùng lặp theo chunk_id (giữ bản xếp hạng cao nhất, bù trường còn trống)
                    ├─ cắt còn max_candidates theo thứ hạng retrieval
                    ├─ Scorer.score(query, pool)         # mock | cross_encoder
                    └─ sắp theo score giảm dần → rank 1..top_k
                          └─► {query_id, retriever, results, config, stats}
```

Reranking do pipeline đảm nhận. `build_hybrid_retriever` tạo `HybridRetriever` không gắn reranker; khi đó Hybrid trả nguyên top `retrieval_top_k` candidate sau RRF. `Reranker` cũng tuân theo protocol `Reranker` trong `retrieval/hybrid_retriever.py`, nên có thể truyền trực tiếp `HybridRetriever(..., reranker=Reranker(...))`. Integration test kiểm tra cả hai cách nối.

## 3. Interface

| Đối tượng | Chữ ký | Ghi chú |
| --- | --- | --- |
| `reranking.reranker.Reranker` | `rerank(query: str, hits: list[dict], top_k: int \| None = None) -> list[dict]` | `top_k=None` dùng `rerank_top_k`. Hàm không sửa input. |
| `reranking.reranker.Scorer` | `score(query: str, candidates: list[dict]) -> list[float]` | Trả một điểm cho mỗi candidate, theo thứ tự đầu vào. Điểm phải hữu hạn. |
| `reranking.reranker.build_reranker` | `(RerankerConfig) -> Reranker \| None` | Trả `None` khi `enabled: false`. |
| `reranking.pipeline.RetrievalPipeline` | `run(query, top_k=None, *, query_id) -> dict` | Retriever là bất kỳ đối tượng nào có `search(query, top_k)`. |
| `scripts/run_retrieval.py` | CLI | Xem mục 6. |

Reranker chỉ đổi thứ tự. Mọi trường đầu vào được giữ nguyên, gồm `chunk_id`, `chunk_text`, `parent_clause_id`, `document_id` và `metadata.validity_status`. Chỉ `rank` và `score` được thay bằng kết quả rerank. Thứ hạng và điểm trước rerank được lưu ở `retrieval_rank` và `retrieval_score` để đo tác động của reranking. Khi hai candidate bằng điểm, candidate có thứ hạng retrieval cao hơn đứng trước.

## 4. Contract đầu ra

Mỗi phần tử trong `results` có đủ các trường của mục 4.3 và qua được `schemas/retrieval_schema.json`. Ví dụ dưới đây chỉ minh họa cấu trúc; giá trị score và latency không phải số đo thật:

```json
{
  "query_id": "Q_CLI_001",
  "query": "Điều kiện kết hôn theo quy định pháp luật là gì?",
  "retriever": "hybrid_reranker",
  "results": [{
    "chunk_id": "l_52_2014_qh13_art_8_chunk_1",
    "document_id": "l_52_2014_qh13",
    "article_id": "l_52_2014_qh13_art_8",
    "clause_id": null,
    "parent_clause_id": null,
    "rank": 1,
    "score": 0.97,
    "chunk_text": "1. Nam, nữ kết hôn với nhau phải tuân theo các điều kiện sau đây: ...",
    "metadata": {"article_number": "8", "validity_status": "Không xác định", "doc_id": "l_52_2014_qh13"},
    "rrf_score": 0.015873,
    "retrieval_sources": ["dense"],
    "retrieval_rank": 4,
    "retrieval_score": 0.015873
  }],
  "config": {
    "retriever": {"backend": "hybrid", "retrieval_top_k": 50, "rrf_k": 60},
    "reranker": {"backend": "cross_encoder", "model": "BAAI/bge-reranker-v2-m3", "rerank_top_k": 5, "max_candidates": 50},
    "top_k": 5
  },
  "stats": {"retrieved_candidates": 50, "input_candidates": 50, "duplicates_removed": 0, "truncated_candidates": 0,
            "scored_candidates": 50, "output_candidates": 5, "returned": 5,
            "retrieval_latency_ms": 0.0, "rerank_latency_ms": 0.0, "total_latency_ms": 0.0}
}
```

Quy tắc ánh xạ trong `to_contract_result`:

- Chỉ dùng alias đã ghi trong `docs/data_contract.md` mục 5: `doc_id` → `document_id` và `text` → `chunk_text`. Đầu ra chỉ có một trường nội dung là `chunk_text`; trường `text` bị bỏ.
- `article_id`, `clause_id` và `parent_clause_id` được chép khi upstream cung cấp, nếu không có thì để `null`. Pipeline **không suy ra** các trường này từ `parent_id` hay từ chuỗi ID, để evaluation ghi nhận thiếu metadata thay vì tính Parent Match sai (mục 13.4).
- `validity_status` nằm trong `metadata`. Nếu upstream không có giá trị này, pipeline gán `"Không xác định"` theo quy ước Data Audit.
- `score` là điểm của bước cuối cùng: điểm reranker, hoặc điểm RRF khi tắt reranker. Không so sánh điểm giữa các bước.
- `rank` bắt đầu từ 1. Nếu không có kết quả, pipeline trả `results: []`.
- `config` và `stats` ghi model, candidate pool, top_k và latency theo quy định benchmark (mục 7).

## 5. Cấu hình

| Tham số | File | Mặc định | Ý nghĩa |
| --- | --- | ---: | --- |
| `retrieval_top_k` | `retrieval/config.yaml` (Dev 4) | 50 | Số candidate thô lấy từ Hybrid trước rerank. Đọc từ `retrieval.retrieval_top_k`; nếu thiếu thì dùng `hybrid.candidate_k`. CLI: `--retrieval-top-k`. |
| `rrf_k` | `retrieval/config.yaml` (Dev 4) | 60 | Hằng số RRF. |
| `reranker.rerank_top_k` | `reranking/config.yaml` | 5 | Số chunk giữ lại sau rerank, cũng là giá trị mặc định của `--top-k`. |
| `reranker.max_candidates` | `reranking/config.yaml` | 50 | Số candidate tối đa đưa vào Cross-Encoder (mục 13.2). CLI: `--max-candidates`. |
| `reranker.backend` | `reranking/config.yaml` | `mock` | `mock` hoặc `cross_encoder`. CLI: `--reranker` (`none` để tắt). |
| `reranker.model` | `reranking/config.yaml` | `BAAI/bge-reranker-v2-m3` | Model Cross-Encoder. CLI: `--model`. |
| `reranker.batch_size` / `max_length` / `device` | `reranking/config.yaml` | 16 / 512 / null | Tham số suy luận của Cross-Encoder. |

Các giá trị trên chỉ là giá trị khởi đầu. Khóa lạ trong `reranker` bị từ chối để bắt lỗi gõ sai tên khóa. Điều kiện ràng buộc: `top_k ≤ min(retrieval_top_k, max_candidates)`, nếu vi phạm CLI trả exit code 2. Mỗi lần rerank ghi log số candidate vào, số candidate được chấm, số trùng, số bị cắt, số trả ra và latency, ví dụ:

```text
INFO reranking.reranker: Reranker[cross_encoder] input=50 scored=50 (dup=0, cut=0) output=5 latency=2003.8ms model_load=15488.6ms
```

Thời gian tải model được tách thành `model_load_ms`. Model chỉ tải một lần cho mỗi tiến trình, ở lần rerank đầu tiên có candidate, nên `rerank_latency_ms` chỉ gồm thời gian khử trùng lặp, chấm điểm và sắp xếp.

### 5.1. Latency đo được của `bge-reranker-v2-m3`

Môi trường đo: NVIDIA RTX 3050 Ti Laptop (4 GB VRAM), torch 2.12 + CUDA 12.6, fp32, `batch_size: 16`, `max_length: 512`. Candidate lấy từ chế độ `mock`, nên số này chỉ phản ánh tốc độ, không phản ánh chất lượng.

| Trường hợp | `max_candidates` | `rerank_latency_ms` |
| --- | ---: | ---: |
| Tải model, một lần mỗi tiến trình (đọc từ ổ D:) | — | 14.400–16.800 |
| Một câu hỏi, lần gọi đầu (gồm warm-up CUDA) | 20 | 1.823 |
| Một câu hỏi, lần gọi đầu (gồm warm-up CUDA) | 50 | 2.004 |
| Batch 10 câu Dev, trung vị câu 2–10 | 50 | 1.298 |

Trên fixture, reranker đưa chunk đúng (Điều 8 khoản 1 Luật HN&GĐ 2014) từ thứ hạng retrieval 4 lên thứ hạng 1, và đẩy chunk lạc đề ("không thừa nhận hôn nhân cùng giới") xuống cuối. Có thể giảm latency bằng fp16 hoặc giảm `max_candidates`; cần đo cả chất lượng trên Dev set trước khi chọn.

## 6. Chạy standalone

Cài môi trường (Python 3.12, xem `README.md`), sau đó chạy từ thư mục gốc repo:

```powershell
# 1) Offline, không cần dịch vụ: Dense mock (Dev 3) trên corpus thật + mock reranker
python scripts/run_retrieval.py --query "Điều kiện kết hôn là gì?" --top-k 5

# 2) Stub thuần: candidate list cố định trong test/fixtures/reranker_candidates.json
python scripts/run_retrieval.py --query "Điều kiện kết hôn là gì?" --retriever fixture

# 3) Pipeline thật: Elasticsearch BM25 + Qdrant + RRF + bge-reranker-v2-m3
$env:ELASTICSEARCH_URL = "http://localhost:9200"
$env:QDRANT_PATH = (Resolve-Path .\data\indexes\qdrant_storage).Path
python scripts/run_retrieval.py --query "Điều kiện kết hôn là gì?" --top-k 5 `
  --retriever hybrid --reranker cross_encoder `
  --elasticsearch-index legal-child-chunks-dev --collection vietnam_legal_chunks `
  --dense-model bkai-foundation-models/vietnamese-bi-encoder
```

Model Cross-Encoder (~2,2 GB) được tải về thư mục cache Hugging Face, mặc định nằm trên ổ C:. Để cache ở ổ khác, đặt biến môi trường `HF_HOME` (ví dụ `setx HF_HOME D:\cache\huggingface`). Khi model đã có sẵn trong cache, đặt `HF_HUB_OFFLINE=1` để không kết nối mạng.

Chế độ `mock` dùng vector giả lập tất định, nên thứ hạng **không mang ý nghĩa ngữ nghĩa**. Chế độ này chỉ dùng để kiểm tra luồng và contract. Ở chế độ `hybrid`, Elasticsearch index và Qdrant collection phải được nạp từ cùng corpus và cùng dense model (xem `retrieval/retrieval.md`).

Các tùy chọn khác:

- `--output FILE`: ghi JSON ra file thay vì stdout.
- `--queries FILE`: chạy batch trên một file câu hỏi.
- `--eval-output FILE`: ghi thêm file `[{question_id, retrieved_chunk_ids}]` cho `evaluation.metrics.evaluate` (Dev 2).
- `--log-level`: chọn mức log. Log được ghi ra stderr, nên stdout chỉ chứa JSON.

Mã thoát:

| Exit code | Ý nghĩa |
| ---: | --- |
| 0 | Thành công, kể cả khi `results: []`. |
| 1 | Lỗi retriever, reranker, dịch vụ hoặc model (`PipelineError`, `ConnectionError`, thiếu package). Lỗi không bị đổi thành kết quả rỗng và pipeline không tự fallback. |
| 2 | Đầu vào hoặc cấu hình sai: query rỗng, `top_k` không hợp lệ, file thiếu, thiếu URL Elasticsearch, hoặc chạy trên Test set khi chưa thêm `--allow-test-split`. |

## 7. Tuning trên Dev set

Chỉ tuning `retrieval_top_k`, `max_candidates` và `rerank_top_k` trên Dev set. CLI từ chối file câu hỏi có tên chứa `test` hoặc có bản ghi `split: "test"`, trừ khi thêm `--allow-test-split` cho lần đánh giá chính thức sau khi đã khóa cấu hình.

```powershell
python scripts/run_retrieval.py --queries data/benchmark/queries_dev.json --retriever hybrid --reranker cross_encoder `
  --retrieval-top-k 50 --max-candidates 50 --top-k 10 `
  --output retrieval/results/dev_hybrid_reranker.json --eval-output retrieval/results/dev_hybrid_reranker_eval.json
python -c "from evaluation.metrics import evaluate; evaluate('retrieval/results/dev_hybrid_reranker_eval.json', 'data/benchmark/ground_truth.json')"
```

Lặp lại với các tổ hợp `retrieval_top_k`/`max_candidates` ∈ {20, 50, 100}. So sánh Recall@K, MRR@K, NDCG@K với `stats.rerank_latency_ms` ở cùng điều kiện, rồi mới chốt giá trị trong `reranking/config.yaml`. Luồng chạy batch và chấm điểm đã được kiểm chứng ở chế độ `mock` trên 285 câu Dev. Kết quả `mock` không được dùng làm số đo chất lượng.

## 8. Khảo sát model reranker

| Model | Kích thước | Ghi chú |
| --- | --- | --- |
| `BAAI/bge-reranker-v2-m3` (**mặc định**) | ~568M | Cross-encoder đa ngôn ngữ dựa trên bge-m3, giấy phép Apache-2.0, chạy trực tiếp bằng `sentence_transformers.CrossEncoder`. Cùng họ với embedding bge-m3 trong `retrieval/config.yaml`. |
| `Alibaba-NLP/gte-multilingual-reranker-base` | ~306M | Nhẹ hơn, đa ngôn ngữ, Apache-2.0. Cần `trust_remote_code`. |
| `jinaai/jina-reranker-v2-base-multilingual` | ~278M | Nhanh, nhưng giấy phép CC-BY-NC (phi thương mại). |
| `itdainb/PhoRanker` | PhoBERT-base | Cross-encoder cho tiếng Việt. Yêu cầu input đã tách từ, phải đồng bộ với quy tắc word-segmentation của dự án. |

Chưa model nào được đo trên Dev set của dự án. Lựa chọn mặc định dựa trên khả năng đa ngôn ngữ, giấy phép và tính tương thích với stack hiện có. Có thể đổi model bằng `reranker.model` hoặc `--model` mà không phải sửa code, với điều kiện model chạy được qua `CrossEncoder`.

## 9. Kiểm thử

```powershell
python -m pytest test/test_reranker.py test/test_integration.py -v
python -m pytest test/                          # toàn bộ thư mục test; chạy từ thư mục gốc repo
python -m unittest discover -s test -v          # tương đương, không cần pytest
```

Các bài test bao phủ: đọc và validate config, giới hạn `max_candidates`, kết quả rỗng (một nhánh hoặc cả hai nhánh), lỗi adapter BM25/Dense/reranker, output adapter sai dạng, `chunk_id` trùng, bảo toàn metadata và ID, không suy đoán `parent_clause_id`, validate `schemas/retrieval_schema.json`, chế độ batch, chặn Test set và mã thoát của CLI.

## 10. Vấn đề contract phát hiện, cần phối hợp

1. **Corpus chưa có `parent_clause_id`/`clause_id`/`article_id` (Dev 1, Dev 3).** `data/chunking_output/chunks.jsonl` chỉ có `parent_id` ở cấp Điều, ví dụ `l_52_2014_qh13_art_8`. `scripts/build_index.py::_adapt_chunk_for_vector_store` điền `parent_clause_id` bằng `parent_id` hoặc `{article_id}_clause_1`, nghĩa là giá trị trong Qdrant là giá trị suy đoán, trái với mục 13.4. Pipeline Dev 5 giữ nguyên giá trị upstream trả về, nên ở chế độ `mock`/`hybrid`, hit từ nhánh Dense mang giá trị suy đoán này, còn hit chỉ có từ BM25 nhận `null`. Cần bổ sung `parent_clause_id` thật ở bước chunking trước khi báo cáo Parent Match.
2. **Output của `ElasticsearchBM25Retriever` (Dev 4)** dùng `text`/`parent_id` và không có `chunk_text`/`document_id`/`parent_clause_id` ở cấp gốc. Pipeline đang ánh xạ alias. Nên chuẩn hóa ngay tại adapter.
3. **`retrieval/config.yaml` (Dev 4)** chưa có khóa `retrieval.retrieval_top_k` theo mục 14.3. Pipeline hiện đọc `hybrid.candidate_k` làm fallback.
4. **`schemas/retrieval_schema.json` (Dev 1)** vẫn khai báo `text` và chưa yêu cầu `chunk_text`, `document_id`, `parent_clause_id`. Integration test đang kiểm tra cả schema hiện tại lẫn các trường của mục 4.3. Đề nghị Dev 1 cập nhật schema.
5. **`retrieval.hybrid_retriever.CrossEncoderReranker` (Dev 4)** trùng chức năng với `reranking/reranker.py`, chấm `text` thay vì `chunk_text`, không giới hạn candidate và không cập nhật `rank`/`score`. Đề nghị Dev 4 bỏ class này hoặc trỏ về `reranking.reranker`.
6. **Test đang lỗi không thuộc phạm vi Dev 5** (tình trạng khi bàn giao):
   - `test/test_bm25_retrieval.py` cần package `elasticsearch`, và cùng `test/test_retrieval_evaluation.py` import `embedding.vector_store.load_chunks`, hàm không còn tồn tại.
   - `tests/test_benchmark.py` có 7 test lỗi (manifest đóng băng Test set, số lượng mapping).
7. **Benchmark dùng `id` (`HN_001`)** thay cho `query_id`. CLI chấp nhận cả hai tên trường, và `query_id` của đầu ra lấy theo giá trị đó.
