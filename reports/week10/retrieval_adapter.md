# D4.3 – Retrieval Adapter và contract Week 10

## Đầu vào
- `AskRequest`/ngày `as_of_date`, tùy chọn metadata filters, cấu hình retrieval và kết quả Hybrid/Reranker hiện có.
- Canonical `RetrievalBundle`/`CandidateChunk` từ `schemas.models`.

## Đầu ra
- `retrieval/adapter.py` tạo `RetrievalBundle` canonical cho consumer.
- Bundle serialize metadata filters, provenance và latency breakdown theo contract.

## Kết quả
- Ngày hiệu lực được truyền rõ ràng; retrieval rỗng trả `candidates=[]`, không dựng context/evidence giả.
- BM25 và Dense nhận cùng metadata filters; các stage latency được ghi riêng, stage không đo có giá trị null.
- Kiểm thử adapter, pipeline và contract đã pass trong đợt kiểm tra toàn repo: 1.455 passed, 1 skipped, 197 subtests.
- Giới hạn: chưa xác minh lại candidate pool 50 của thí nghiệm Top-k.

## Công nghệ đã dùng
Python, Pydantic canonical models, BM25, Dense retrieval, Qdrant, RRF, Cross-Encoder reranking, metadata filtering, latency instrumentation, pytest, Ruff.

**Trạng thái:** Adapter dùng contract mở rộng `week10_v1.1`, giữ khả năng đọc payload `week10_v1.0`, và serialize metadata filters cùng latency breakdown trong `RetrievalBundle`.

## Adapter và ranh giới module

`retrieval/adapter.py` chuyển kết quả của retrieval pipeline thành `schemas.models.RetrievalBundle` và `CandidateChunk`. Adapter yêu cầu `as_of_date` rõ ràng, truyền ngày đó xuống pipeline và candidate; không tự lấy ngày hiện tại. Nếu retrieval rỗng, adapter trả bundle với `candidates=[]`, không tạo evidence hoặc context giả.

`ContextPayload` do Context Builder của Dev5 tạo theo interface đã thống nhất. Retrieval Adapter chỉ cung cấp candidates; không tự ghép context.

## Provenance

- `corpus_hash` là SHA-256 của corpus, không dùng như phiên bản. Factory `from_corpus_artifact()` gọi helper `chunk_file_sha256()` để có cùng quy tắc chuẩn hóa newline của dự án.
- `retrieval_config_version` là nhãn cấu hình riêng, được truyền tường minh; không suy ra từ corpus hash.
- SHA-256 cấu hình đầy đủ tiếp tục được lưu ở manifest thí nghiệm. Contract `RetrievalBundle` v1.0 hiện chỉ có `retrieval_config_version` và `corpus_hash`, chưa có `retrieval_config_hash` hoặc `corpus_version` riêng.

## Bộ lọc và latency

Retrieval nhận cùng mapping `metadata_filters` ở BM25 và Dense. Bộ lọc hỗ trợ exact match trên `document_type`, `document_number`, `document_id`, `article_id`, `clause_id`, `validity_status`; giá trị được chuẩn hóa và kiểm tra lại sau khi truy vấn. BM25 chuyển filter thành điều kiện term của backend; Dense truyền filter đến vector store và áp dụng cùng điều kiện ở chế độ in-memory. Cache key bao gồm filter đã chuẩn hóa. Backend không hỗ trợ filter sẽ báo lỗi thay vì âm thầm bỏ lọc.

Pipeline ghi `bm25_ms`, `dense_ms`, `rrf_ms`, `reranking_ms`, `parent_context_ms` và `total_retrieval_ms` vào `stats.latency_breakdown`; stage không đo được có giá trị `null`. Adapter đưa breakdown đó vào `RetrievalBundle.latency_breakdown`, đồng thời serialize filter đầu vào thành `RetrievalBundle.metadata_filters`. `RetrievalBundle.latency_ms` tiếp tục giữ latency tổng.

## Kiểm chứng sau merge

- `schemas.models.SCHEMA_VERSION`: `week10_v1.1`; model tiếp tục chấp nhận các payload `week10_v1.0` cũ.
- Sinh schema canonical từ Pydantic cho ra cùng 10 schema và cấu trúc JSON tương đương các tệp trong `schemas/generated/`. Ba tệp có khác biệt thứ tự key khi so byte; nội dung JSON parse ra giống nhau.
- Kiểm thử toàn repo sau các thay đổi contract/adaptor/handoff: **1.455 passed, 1 skipped, 197 subtests passed**. Kiểm thử tập trung adapter, pipeline, BM25, Dense, Hybrid, router, holdout và canonical schema trước đó đạt **181 passed, 111 subtests passed**.
- `ruff check .` và `git diff --check`: đều pass.
- Phân tích cutoff D4.5 được tính lại từ artifact Dev đã lưu; xem [topk_conformance.md](topk_conformance.md) và manifest [topk_experiment_20261116_manifest.json](topk_experiment_20261116_manifest.json). Không chạy lại retrieval/reranker hoặc Ollama.
- Smoke Router trên holdout Week 10: **14/36 route/action mismatch**; kết quả tổng hợp trong [router_regression.md](router_regression.md). Holdout đã được chạy, không dùng để chỉnh Router.

## Giới hạn còn lại

Contract `week10_v1.1` bổ sung hai trường serialization này. Cần thông báo consumer Dev3/Dev5/Dev2 đồng bộ contract mới trước khi merge. Báo cáo này không xác nhận độc lập raw candidate pool 50 của thí nghiệm Top-k; xem giới hạn trong báo cáo D4.5.
