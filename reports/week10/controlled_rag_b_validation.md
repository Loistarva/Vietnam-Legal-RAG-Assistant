# Controlled RAG B – kiểm tra artifact hiện có

## Đầu vào
- Run 30 câu: `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2/`.
- Benchmark IDs/ngày trong `queries_dev.json`, retrieval precompute và manifest chạy.

## Đầu ra
- Kết quả JSONL, lỗi và manifest của run gốc.
- JSONL/manifest bàn giao Dev4 có route hậu kỳ tại `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2_dev4_handoff/`.

## Kết quả
- 30/30 ID đúng và duy nhất; ngày benchmark khớp; 29 PASS, 1 ABSTAIN; không có output bị cắt.
- SHA precompute được đối chiếu và hiệu chỉnh trong manifest; kết quả mô hình/JSONL gốc không đổi.
- Route được tính hậu kỳ và đối chiếu 30/30 với Router ở commit nguồn; không phải trace route tại thời điểm generation.
- Không chạy lại Ollama.

## Công nghệ đã dùng
Shared RAG batch pipeline, Qwen2.5 qua Ollama (run đã lưu), JSONL, canonical Pydantic validation, Rule Router, SHA-256 manifests.

**Trạng thái:** Đã kiểm tra lần chạy 30 câu hiện có; không chạy lại mô hình.

- Lần chạy: `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2/`
- Trạng thái manifest: `SUCCESS`
- Có 30 bản ghi, 30 ID duy nhất và khớp chính xác với `dev_gold_30_ids_v1.txt`.
- `as_of_date` trong mọi kết quả khớp `queries_dev.json`; toàn bộ `as_of_date_source` là `benchmark`.
- Kết quả nghiệp vụ: 29 `PASS`, 1 `ABSTAIN`; không ghi nhận output bị cắt.
- Mỗi kết quả đều có `ContextPayload`/candidate trace tương ứng với 30 query ID; ngày benchmark khớp nguồn.

## Hiệu chỉnh nguồn gốc

SHA-256 thô hiện tại của artifact precompute là `6eb200f3803dfe341299f092ae1be9723ec9236f501f7bb53ef47dc098dd1353`. Giá trị cũ trong bốn manifest là `576065abe250393ee56130555a175345d5827628802df83f14bbe7aae38574a3`; sai lệch metadata đã được sửa. Đã đối chiếu bốn bộ kết quả với artifact hiện tại: query ID, `chunk_id` và `reranker_score` khớp 30/30 câu ở mỗi run. Cả bốn manifest hiện trỏ đến SHA hiện tại; chữ ký được tính lại và kiểm tra lại theo đúng các trường đầu vào của batch runner. Không thay đổi JSONL kết quả hay output mô hình; không chạy lại mô hình.

**Kết luận provenance:** SHA hiện tại và SHA trong manifest đã khớp; kết quả Controlled RAG B được giữ nguyên và có thể truy vết theo các manifest đã hiệu chỉnh. Đây là sửa metadata kèm đối chiếu artifact, không phải một lần chạy mô hình mới.

Chi tiết hiệu chỉnh bốn lần chạy:

| Lần chạy | Chữ ký cũ | Chữ ký sau hiệu chỉnh | Số câu khớp |
|---|---|---|---:|
| `20261110_controlled_rag_qwen25_dev30` | `8e557ae17bb077a4ced421dd53983884e003decfec46e92e5e44b83d93b72635` | `9392382a6c50da4a2c68c4ad7cdbbcdd82076c716e66ebb2b41f4a43483efa6c` | 30/30 |
| `20261113_controlled_rag_qwen25_dev30` | `1aade80583b0511bdd23891c3e36d06aeedfaa6ea7138047408df9a414a8beab` | `47865e633112ef5dc114a806d4651579dc17e9282b785baef95a9de5948f5c04` | 30/30 |
| `20261113_controlled_rag_qwen25_dev30_post_fix` | `16000b8ab44bffa4c64b5e5794c7526a95f0e254a5e3b74124e56b9f3150ca10` | `c2a506a799dc674a719f2e0058c923a604df7c24780def91a143cc72651714cd` | 30/30 |
| `20261114_controlled_rag_qwen25_dev30_prompt_v1_2` | `03a44ca71e01aedfc05d46553dd4e83add10ae42398775c872671c2211343516` | `dc0e8366caecc05895bfcc1adbeb1c80f1923191758203a66d7534a7357b4ea0` | 30/30 |

Việc hiệu chỉnh chỉ cập nhật metadata nguồn gốc; không thay JSONL kết quả hoặc output mô hình.

## Bản bàn giao có route

JSONL gốc không ghi trường `route`. Đã tạo bản bàn giao dẫn xuất riêng tại `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2_dev4_handoff/`; không sửa JSONL gốc và không chạy lại retrieval hay Ollama. Script định tuyến lại 30 query bằng `rule_router_v3` trên đúng câu hỏi và `as_of_date` trong từng record, sau đó validate `result` theo `RAGOutputRecord`.

- Kết quả: 30 record, 30 query ID duy nhất; route canonical: `LEGAL_IN_SCOPE` 30/30.
- Manifest dẫn xuất lưu SHA của JSONL/manifest nguồn, SHA Router và SHA script. Output SHA-256: `d492c08d29b45009758ef2d9a703310b36d72b205ed77bcea6db6095ce5872f4`.
- Đây là **route được tính hậu kỳ**, không phải route trace đã được ghi tại thời điểm generation. Đã chạy đối chiếu cùng 30 câu bằng code Router ở source-run commit `02b0a803` (SHA file `0807b542c2046a8e7e6f4038a9d421bcdba73300c45364702218a5f77153e01f`): kết quả route khớp 30/30 với Router hiện tại (SHA `41b25945b8111ca38bbc3fa2aef302e3c924f23eb4d952eaf37e526073dd107d`). Manifest đánh dấu rõ cách tạo để Dev2 không nhầm provenance.
