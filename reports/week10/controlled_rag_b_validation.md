# Controlled RAG B – kiểm tra artifact hiện có

**Đính chính ngày 23/11/2026:** Provenance **VERIFIED** theo [audit/verdict Sprint 11](../Sprint11_Dev4_Report.md). Hai SHA khác nhau do LF/CRLF của cùng Git blob; bốn run manifest vẫn giữ SHA CRLF và chữ ký gốc. Phần từng ghi đã sửa bốn manifest/tính lại chữ ký không đúng trạng thái artifact hiện tại và được rút lại. Không sửa manifest/output, không replay Dev30 theo D-12.

## Đầu vào
- Run 30 câu: `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2/`.
- Benchmark IDs/ngày trong `queries_dev.json`, retrieval precompute và manifest chạy.

## Đầu ra
- Kết quả JSONL, lỗi và manifest của run gốc.
- JSONL/manifest bàn giao Dev4 có route hậu kỳ tại `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2_dev4_handoff/`.

## Kết quả
- 30/30 ID đúng và duy nhất; ngày benchmark khớp; 29 PASS, 1 ABSTAIN; không có output bị cắt.
- SHA precompute được đối chiếu: LF khớp precompute manifest/Git blob, CRLF khớp cả bốn run manifest; không hiệu chỉnh manifest hoặc chữ ký gốc.
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

## Đính chính provenance

- Artifact/Git blob dạng LF có SHA-256 `6eb200f3803dfe341299f092ae1be9723ec9236f501f7bb53ef47dc098dd1353`, khớp precompute manifest.
- Chuyển cùng bytes sang CRLF cho SHA-256 `576065abe250393ee56130555a175345d5827628802df83f14bbe7aae38574a3`, khớp SHA precompute trong cả bốn run manifest.
- Git commit chứa artifact: `cdca079ba63b5e3d48da690df269ff51bb47c887`; blob ID `d652635b70a6ff04d09cdbbdd6af7c611a60c460`.
- Đối chiếu bốn run: query ID, query/ngày, chunk ID và reranker score khớp 30/30 ở mỗi run. Chữ ký gốc tái tính khớp 4/4; corpus/retrieval/rerank config và benchmark đối chiếu được theo Git SHA ghi trong từng manifest.
- Không đổi manifest hoặc output gốc. Bảng “chữ ký sau hiệu chỉnh” trước đây được rút lại vì không phản ánh bốn manifest hiện có.

**Verdict: VERIFIED** trong phạm vi provenance của precompute và kết quả đã lưu; không xác minh mới toàn bộ raw pool 50 hoặc chất lượng câu trả lời. Bằng chứng chi tiết và quyết định không replay nằm trong [báo cáo D4.4 Sprint 11](../Sprint11_Dev4_Report.md).

## Bản bàn giao có route

JSONL gốc không ghi trường `route`. Đã tạo bản bàn giao dẫn xuất riêng tại `evaluation/results/dev/20261114_controlled_rag_qwen25_dev30_prompt_v1_2_dev4_handoff/`; không sửa JSONL gốc và không chạy lại retrieval hay Ollama. Script định tuyến lại 30 query bằng `rule_router_v3` trên đúng câu hỏi và `as_of_date` trong từng record, sau đó validate `result` theo `RAGOutputRecord`.

- Kết quả: 30 record, 30 query ID duy nhất; route canonical: `LEGAL_IN_SCOPE` 30/30.
- Manifest dẫn xuất lưu SHA của JSONL/manifest nguồn, SHA Router và SHA script. Output SHA-256: `d492c08d29b45009758ef2d9a703310b36d72b205ed77bcea6db6095ce5872f4`.
- Đây là **route được tính hậu kỳ**, không phải route trace đã được ghi tại thời điểm generation. Theo kiểm tra lịch sử, đã đối chiếu cùng 30 câu bằng code Router ở source-run commit `02b0a803` (SHA file `0807b542c2046a8e7e6f4038a9d421bcdba73300c45364702218a5f77153e01f`): kết quả route khớp 30/30 với snapshot Router v3 khi tạo handoff (SHA `41b25945b8111ca38bbc3fa2aef302e3c924f23eb4d952eaf37e526073dd107d`), không phải Router v5 hiện tại. Manifest đánh dấu rõ cách tạo để Dev2 không nhầm provenance.
