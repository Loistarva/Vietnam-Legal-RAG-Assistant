# Chuẩn bị precompute Test 30 Sprint 12

Ngày đối chiếu: **26/11/2026**, múi giờ Asia/Saigon. Baseline: `c266983c9a5b6d802f8ff87f5036c9637fd3a9ac`, nhánh `feature/sprint12-dev4-Router-Retrieval-and-Knowledge-Base`. Wrapper, checker và test mới đang ở working tree, chưa thuộc baseline này.

**Trạng thái: hoàn tất phần chuẩn bị code và kiểm thử bằng dữ liệu giả; chưa chạy retrieval/rerank thật trên Test 30.** Đầu vào local khớp freeze. Chưa có xác nhận cấu hình của Tech Lead; working tree còn thay đổi chưa commit. Không tạo thư mục official `evaluation/results/precompute/test30_s12_001` trong lần chuẩn bị này.

**Cập nhật trước lượt chạy ngày 26/11/2026:** người giao việc đã xác nhận trong cuộc hội thoại: “Nếu tất cả đã khớp thì hãy phê duyệt các điều kiện kia và chạy retrieval đi.” Quyết định này cho phép ghi nhận cấu hình đã đối chiếu và thực hiện hai giai đoạn precompute. Người xác nhận được ghi là `project_user`, không tự gán tên hoặc chức danh Tech Lead. Kiểm tra dịch vụ lại sau xác nhận đã pass: ES/Qdrant cùng hash corpus `7105c484…6b023`; Qdrant đúng BGE-M3, 1024 chiều, 2.322 chunk. Chưa gửi câu hỏi trong bước kiểm metadata. Code sẽ được commit trước khi tạo bản ghi xác nhận gắn với SHA và chạy thật; kết quả thực thi nằm trong output mới, không thay số liệu chuẩn bị bên dưới.

## Các mức Top k

| Giá trị | Nguồn điều khiển | Cách dùng |
| --- | --- | --- |
| 50 ứng viên retrieval | `retrieval.retrieval_top_k = 50` và CLI `--top-k 50` | Pool duy nhất đầu vào reranker |
| Tối đa 50 ứng viên đã rerank | `reranker.max_candidates = 50`, CLI `--top-k 50` | Lưu đủ pool để Dev 5 chọn evidence sau; không phải 50 evidence đưa vào prompt |
| 5 evidence runtime | `reranker.rerank_top_k = 5` trong YAML không đổi | RAG Pipeline giữ tối đa 5 evidence |
| 10 kết quả mặc định retrieval | `retrieval.result_top_k = 10` | Giá trị mặc định của config, khác pool xuất ra qua CLI |
| `top_k = 10` trong freeze | `docs/test_run_config_freeze.json` | Tham số đánh giá retrieval cũ; wrapper ghi lại, không sửa thành 5 hoặc 50 |

Hai giai đoạn đều tắt Parent Context Resolver. Parent được xử lý sau khi chọn evidence trong pipeline sinh. Wrapper không gọi Qwen, không dùng Gold để chọn tham số và không thay đổi YAML/manifest đã khóa.

## Kiểm đầu vào local

`check-inputs` xác nhận đủ 30 ID duy nhất, đúng thứ tự và hash JSON chuẩn hóa của `test_questions_freeze.json`; tất cả câu thuộc split Test và có `as_of_date` hợp lệ. Không in nội dung câu hỏi.

| Đối tượng | SHA-256 đã kiểm |
| --- | --- |
| Corpus, chuẩn hóa CRLF thành LF | `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023` |
| Retrieval config, chuẩn hóa CRLF thành LF | `08df4180c8c47fe86592bb2a41d8b0e5f88cc0194160a7990990b3c139de8179` |
| Reranking config, chuẩn hóa CRLF thành LF | `b99cf7319ec93eeb49c241904eb89b5e3e6b41fbbc05b56e63347b25693c6471` |
| Payload questions, JSON canonical theo helper freeze của repo | `9dd472f569726d67951afb20bb059ea7cc282f8b7d6102cc44807769bfbc3876` |

Hash raw file questions sau chuẩn hóa LF được ghi riêng trong snapshot; không dùng nó thay hash JSON canonical trong questions freeze.

Model config đã có trong cache local tại mốc kiểm tra:

| Model | Revision cache |
| --- | --- |
| `BAAI/bge-m3` | `5617a9f61b028005a4858fdac845db406aefb181` |
| `BAAI/bge-reranker-v2-m3` | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` |

Wrapper ghi tên model, revision snapshot và SHA-256 `config.json`; đây không phải hash toàn bộ weights. Việc tìm thấy config cache chưa chứng minh mọi file weights đều sẵn. Hai subprocess chạy với `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1`, kiểm revision trước/sau; cache thiếu thì lượt chạy thất bại, không chuyển sang mock hoặc tự tải bản mới.

## Wrapper và các bước thực hiện

Lần kiểm dịch vụ ngày 26/11/2026 tại `127.0.0.1:9200` bị từ chối kết nối (`ConnectionRefusedError`). Chưa xác minh được ES metadata; bước Qdrant chưa được thực hiện do preflight dừng tại ES. Cần khởi chạy dịch vụ đúng cấu hình hoặc cung cấp endpoint máy nghiệm thu. Không suy ra trạng thái Qdrant từ lỗi ES này.

Code: [precompute_test30_retrieval.py](../../scripts/precompute_test30_retrieval.py). Test: [test_precompute_test30_retrieval.py](../../test/test_precompute_test30_retrieval.py).

### Kiểm đầu vào và dịch vụ

```powershell
python scripts/precompute_test30_retrieval.py check-inputs
python scripts/precompute_test30_retrieval.py check-models
python scripts/precompute_test30_retrieval.py check-services --elasticsearch-url http://127.0.0.1:9200
```

`check-inputs` và `check-models` không kết nối ES/Qdrant. `check-services` kiểm metadata/index/count, không embed hoặc search câu hỏi: dùng verifier ES hiện có cho corpus/tokenizer/text field và verifier Qdrant hiện có cho corpus/model/dimension/collection metadata. Cần đúng endpoint hoặc local storage của máy chạy; có thể truyền `--qdrant-url` hoặc `--qdrant-path`, cũng hỗ trợ các biến môi trường tương ứng. Endpoint trên chỉ là địa chỉ mặc định để kiểm tra, chưa được coi là môi trường nghiệm thu đã xác nhận.

### Chuẩn bị bản ghi xác nhận

Sau khi code/input đã review và commit, tạo bản nháp mới:

```powershell
python scripts/precompute_test30_retrieval.py prepare-approval --approval-file .venv/test30_precompute_approval.v2.json
```

Lệnh chỉ tạo JSON `approved = false`, chứa SHA commit, toàn bộ snapshot input/config và revision model; không chạy retrieval. Một bản nháp local ban đầu đã được tạo ở `.venv/test30_precompute_approval.pending.json` trong lần chuẩn bị này. Bản đó tham chiếu baseline cũ, phải tạo lại sau khi commit code; không dùng nó như bằng chứng đã duyệt.

Tech Lead kiểm nội dung rồi ghi `approved = true`, `approved_by`, `approved_at` có múi giờ và `reference` tới bằng chứng xác nhận. Dev 3 xác nhận manifest/contract; Dev 5 xác nhận đường nạp artifact. File xác nhận nên giữ tại vị trí local được phép, không chứa secret. Không tự ghi tên reviewer hoặc trạng thái duyệt thay người có trách nhiệm.

Thay đổi SHA, hash input/config hoặc revision cache sau khi xác nhận khiến wrapper từ chối chạy. Working tree phải sạch; khi chạy giai đoạn 2, chỉ thư mục output của lượt này được loại khỏi kiểm tra thay đổi. Các thay đổi khác trong kết quả cũ cũng không được bỏ qua.

### Giai đoạn 1 lấy pool ứng viên

Chỉ chạy sau khi các xác nhận đã có và dịch vụ đúng cấu hình. Chọn output chưa tồn tại:

```powershell
python scripts/precompute_test30_retrieval.py retrieve `
  --approval-file .venv/test30_precompute_approval.v2.json `
  --output-dir evaluation/results/precompute/test30_s12_001 `
  --elasticsearch-url http://127.0.0.1:9200
```

Wrapper gọi CLI hiện có với Hybrid, `--reranker none`, `--no-parent-context`, `--top-k 50`, `--retrieval-top-k 50` và tạo `candidates.json` cùng `candidates_manifest.json`. Metadata dịch vụ phải pass trước khi gửi câu hỏi. Không cho ghi đè thư mục output đã tồn tại.

### Giai đoạn 2 rerank và kiểm nhận

Chạy sau khi tiến trình giai đoạn 1 đã kết thúc để hai model không phải cùng chiếm GPU:

```powershell
python scripts/precompute_test30_retrieval.py rerank `
  --approval-file .venv/test30_precompute_approval.v2.json `
  --output-dir evaluation/results/precompute/test30_s12_001

python scripts/precompute_test30_retrieval.py verify `
  --output-dir evaluation/results/precompute/test30_s12_001
```

Giai đoạn 2 dùng `--retriever precomputed`, `--reranker cross_encoder`, `--no-parent-context`, `--top-k 50`; không truy vấn lại ES/Qdrant. Nó kiểm manifest giai đoạn 1 trước khi chạy, giữ đúng cùng pool và evidence, chỉ đổi thứ tự/điểm. Ghi `reranked.json`, `reranked_manifest.json` và hash liên kết tới candidate manifest. `verify` chạy lại checker cho cả hai giai đoạn mà không gọi model.

## Pool dưới 50 và lỗi từng giai đoạn

Checker không chấp nhận pool trên 50, chunk trùng, rank đứt quãng, score không hữu hạn hoặc evidence sai ngày. Mỗi pool dưới 50 phải có lý do trong manifest.

Wrapper tự ghi lý do dựa trên số liệu producer khi kiểm chứng được `retrieved_candidates - duplicates_removed = returned`: upstream trả ít ứng viên hơn giới hạn hoặc đã loại ứng viên trùng. Nó không suy diễn nguyên nhân pháp lý hoặc cho rằng văn bản không tồn tại. Giai đoạn 2 thừa kế lý do của pool giai đoạn 1.

Nếu producer không có đủ số liệu để giải thích, cung cấp `--short-pool-reasons <file.json>` với mapping ID sang lý do có bằng chứng, không có câu hỏi thô. Ví dụ bằng dữ liệu giả:

```json
{"SYNTHETIC_001": "Pool source has only two eligible unique chunks; see source trace."}
```

Không dùng ví dụ giả làm lý do cho Test thật. Không nới ngưỡng hoặc sửa câu hỏi để làm đủ 50. Nếu kiểm tra thất bại, giữ lại output và lock để điều tra; không tạo manifest `COMPLETE` và không ghi đè/chạy lại trong cùng thư mục. Wrapper không hỗ trợ resume hoặc tự chọn lượt tốt hơn. Quyết định chạy lại ở output mới cần được ghi nhận trước khi thực hiện.

## Manifest và handoff Dev 5

Manifest precompute chứa git branch/SHA/trạng thái sạch, hash sáu input, danh sách ID/ngày, cấu hình hiệu lực và các mức Top-k, revision/hash config model, metadata dịch vụ, phiên bản Python/package/máy chạy, thời gian bắt đầu/kết thúc, hash output và số ứng viên/lý do từng câu. Đây là manifest **retrieval-only**, không thay thế manifest A/B sinh câu trả lời theo NFR4.2 của Dev 3/Dev 5; không có Qwen model digest, prompt, temperature hoặc trạng thái cache của lượt sinh.

Dev 5 nhận cả bốn file JSON của hai giai đoạn và giữ nguyên kết quả. Artifact chứa câu hỏi/evidence phục vụ pipeline, vì vậy không đưa raw output vào log hoặc commit trước khi thống nhất quy trình lưu trữ. Trước khi nạp, chạy `verify` trên đúng frozen inputs/config, sau đó:

```python
import json
from pathlib import Path
from orchestration.rag_pipeline import PrecomputedRerankedSource

output = Path("evaluation/results/precompute/test30_s12_001")
manifest = json.loads((output / "reranked_manifest.json").read_text(encoding="utf-8"))
snapshot = manifest["inputs"]
source = PrecomputedRerankedSource.from_file(
    output / "reranked.json",
    expected_corpus_sha256=snapshot["hashes"]["corpus"],
    expected_candidate_text=snapshot["reranker"]["candidate_text"],
    expected_settings={"retriever": snapshot["retriever"], "reranker": snapshot["reranker"]},
)
```

Checker đã thử gọi consumer này và `fetch()` từng ID bằng dữ liệu giả, bao gồm kiểm ngày và nội dung câu hỏi. Dev 5 vẫn cần kiểm nhận artifact thật và chọn Top-5 cho RAG theo cấu hình đã khóa.

## Bằng chứng kiểm thử

- **51 test mới pass**, toàn bộ bằng fixture giả sinh trong thư mục tạm; không đọc/sửa Test thật để thử lỗi, không gọi ES/Qdrant/model thật trong test.
- **128 test regression pass**: checker mới, precompute Dev30 cũ, evidence mapping, retrieval adapter và temporal ba nhánh.
- Ruff theo nhóm rule CI đạt; không thay đổi sáu file input đã khóa.
- Ca lỗi gồm hash corpus/config/output sai; ngày/câu hỏi/ID sai; mock hoặc model/candidate text/RRF sai; parent gắn sẵn; quá 50/duplicate/rank/score sai; thiếu lý do pool nhỏ; thiếu xác nhận/dirty checkout; model revision thay đổi; metadata dịch vụ sai; ghi đè; subprocess lỗi; manifest thiếu runtime hoặc thời gian sai.

```powershell
python -m pytest test/test_precompute_test30_retrieval.py test/test_precompute_dev30_retrieval.py test/orchestration/test_evidence_index_mapping.py test/test_retrieval_adapter.py test/test_retrieval_filter_conformance.py -q -p no:cacheprovider --basetemp .venv/pytest_s12_precompute_review
```

## Điều kiện trước khi chạy thật

- [x] Kiểm ID, ngày và hash input local; phân biệt các mức Top-k.
- [x] Wrapper/checker, manifest chain và test bằng fixture giả.
- [x] Kiểm tương thích `PrecomputedRerankedSource` bằng dữ liệu giả.
- [ ] Commit/review code và chạy CI trên SHA sẽ dùng.
- [ ] Dev 3 xác nhận manifest/contract; Tech Lead xác nhận cấu hình và revision model.
- [ ] Xác minh ES/Qdrant thật dùng đúng corpus/model/index trên máy chạy.
- [ ] Chạy hai giai đoạn, checker pass và Dev 5 kiểm nhận artifact thật.

FR2.10 và phần handoff Test 30 chưa được đánh dấu nghiệm thu toàn bộ chỉ từ gói chuẩn bị này.
