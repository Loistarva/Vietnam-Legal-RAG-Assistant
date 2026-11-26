# Bàn giao kiểm thử Retrieval Sprint 12

Ngày kiểm tra: 25/11/2026, múi giờ Asia/Saigon. Nhánh `feature/sprint12-dev4-Router-Retrieval-and-Knowledge-Base`, baseline `c266983c9a5b6d802f8ff87f5036c9637fd3a9ac`; thay đổi trong báo cáo đang ở working tree, chưa commit.

Phần producer của Retrieval Adapter đã được rà soát theo FR2.11-AC1; test temporal ba nhánh được bổ sung theo FR2.4-AC4. Bản sửa parent thiếu từ commit `5fd05f42` được đưa vào các vị trí tương ứng của baseline hiện tại và kiểm theo FR4.1-AC2. Gói này cung cấp fixture giả lập để Dev 5 viết test consumer; chưa xác nhận luồng API live hoặc nghiệm thu cuối trên `testing`.

## Nội dung đã kiểm tra

| Trường hợp | Bằng chứng |
| --- | --- |
| Có metadata filter | Filter truyền xuống pipeline, có trong bundle và trace; test không có raw query/chunk text trong trace |
| Không có filter | Kiểm cả `None` và `{}`: pipeline nhận `None`, bundle có `metadata_filters = null`, trace có `{}` |
| Ngày đã resolve | Giữ nguyên ngày và nguồn `query_text`, `user_input`, `system_today`, `benchmark`; adapter không tự lấy năm khác từ câu hỏi |
| Không có kết quả | Candidates rỗng, outcome `EMPTY`, không dựng evidence giả |
| Stage latency chưa đo | Giữ `null`; stage đã báo số 0 được giữ là 0 |
| Backend lỗi | Ngoại lệ truyền lên, không đổi thành `EMPTY` |
| Điểm từng nhánh | Giữ `source_scores`, `source_ranks`, `rrf_score`, `reranker_score` |
| Parent thiếu | Giữ child chunk làm evidence, ghi cảnh báo, số lượng và `missing_chunk_ids` vào trace |

### Tổng latency và giới hạn contract

`RetrievalBundle.latency_ms` hiện là trường số bắt buộc; `RetrievalLatencyBreakdown` cho phép các stage là `null`. Adapter trước đây tự gán tổng không biết thành 0. Bản sửa dùng tổng đã đo trong `stats.total_latency_ms`, hoặc `latency_ms` của envelope nếu tổng trong stats không có; nếu cả hai không có thì báo `ValueError`, không tạo số đo giả. Giá trị 0 do nguồn cung cấp vẫn được giữ. Không thay đổi `schemas/models.py`.

Nếu cần biểu diễn tổng thời gian chưa biết bằng `null` trong canonical bundle, Dev 3 cần quyết định thay đổi contract và test tương thích trước khi áp dụng. Trường hợp precomputed phải phân biệt thời gian tra artifact hiện tại với thời gian retrieval/rerank gốc; fixture không chứng minh tốc độ hệ thống thật.

## Temporal ba nhánh

`test/test_retrieval_filter_conformance.py` kiểm bộ lọc của Elasticsearch qua một trình giả lập DSL độc lập, bộ lọc Qdrant local thật trong memory và precomputed. Test yêu cầu Qdrant local hoạt động, không âm thầm fallback sang backend giả khác.

Các ngày được bổ sung: `1999-12-31`, `2000-01-01`, `2020-01-02`, `2029-12-31`, bên cạnh các mốc ngày biên đang có. Test kiểm khoảng hiệu lực nửa mở, văn bản tương lai, filter metadata, tập rỗng, filter trước Top-k và precomputed sai ngày/filter không hỗ trợ. Bằng chứng chỉ xác nhận cùng tập chunk đủ điều kiện; không khẳng định thứ hạng giống nhau hoặc Elasticsearch live đã pass.

## Parent thiếu

`ParentContextResolver.resolve_with_stats()` trả kết quả và thống kê riêng của lần gọi, gồm danh sách `missing_chunk_ids`. API `resolve()` và `last_stats` cũ vẫn được giữ để tương thích.

Retrieval Pipeline đưa thống kê vào `envelope.stats.parent_context`. RAG Pipeline nhận lại thống kê này nếu parent đã được xử lý phía trước; nếu resolve trong RAG thì lấy thống kê của lần resolve đó. Test `test_missing_parent_uses_chunk_and_records_trace` chạy cả hai đường, kiểm child text trong evidence, cảnh báo và trace. Test producer của Retrieval Pipeline cũng có ca parent không tồn tại.

## Fixture bàn giao Dev 5

File: [retrieval_handoff_samples.json](../../test/fixtures/sprint12/retrieval_handoff_samples.json).

Mọi câu hỏi, evidence, ID, hash đại diện, điểm và thời gian trong file đều giả lập; không lấy dữ liệu từ lượt Dev/Test official. File chứa 5 trường hợp:

| `case_id` | Mục đích |
| --- | --- |
| `filtered` | Candidates có filter, có điểm/hạng từng nhánh |
| `unfiltered` | Candidates không áp dụng filter |
| `empty` | Retrieval trả rỗng |
| `precomputed_unknown_stages` | Precomputed với latency từng stage chưa biết |
| `partial_stages` | Một stage có số đo 0, các stage chưa đo là null |

Mỗi trường hợp có `bundle` theo canonical schema và `trace` sidecar của Dev 4. Đây không phải `AskResponse`. Full bundle chứa query/chunk text giả lập để consumer test, không đưa full bundle vào production log.

```python
import json
from pathlib import Path
from schemas.models import RetrievalBundle

fixture = json.loads(Path(
    "test/fixtures/sprint12/retrieval_handoff_samples.json"
).read_text(encoding="utf-8"))
for case in fixture["cases"]:
    bundle = RetrievalBundle.model_validate(case["bundle"])
    trace = case["trace"]
    # Dev 5 injects the bundle/trace through the approved consumer interface.
    # Assert that final RAG trace preserves filters, versions, scores and dates.
```

## Kiểm thử và bàn giao còn lại

Bộ tập trung sau thay đổi: **79 passed, 6 subtests passed**. Baseline cùng nhóm trước thay đổi: **67 passed, 6 subtests passed**. Ruff theo rule CI trên 8 file Python thay đổi đạt; `git diff --check` đạt tại lúc kiểm tra.

Regression mở rộng offline: **284 passed, 38 subtests passed** trong 58,25 giây, gồm `test/orchestration`, các test adapter/temporal/context/reranker/hybrid/confidence và `retrieval/test`.

```powershell
python -m pytest test/test_retrieval_adapter.py test/test_retrieval_filter_conformance.py test/test_pipeline_context.py test/orchestration/test_evidence_index_mapping.py -q -p no:cacheprovider --basetemp .venv/pytest_s12_dev4_review

python -m pytest test/orchestration test/test_pipeline_context.py test/test_reranker.py test/test_retrieval_adapter.py test/test_retrieval_filter_conformance.py test/test_hybrid_retriever.py test/test_confidence.py retrieval/test -q -p no:cacheprovider --basetemp .venv/pytest_s12_dev4_regression_review
```

Các `tmp_path` ban đầu lỗi quyền truy cập thư mục Temp mặc định của máy; dùng `--basetemp` trong workspace đã giải quyết và không sửa test để bỏ qua lỗi. Lượt regression có API/E2E chưa collect được vì môi trường `.venv` thiếu `fastapi`; không coi API/E2E đã pass.

- [x] Rà soát producer và bổ sung test FR2.11-AC1, FR2.4-AC4, FR4.1-AC2.
- [x] Tạo fixture giả lập và test validate/roundtrip canonical bundle cùng trace.
- [x] Kiểm hai đường parent thiếu và giữ kết quả fallback.
- [ ] Dev 5 review phần thay đổi trong reranking/orchestration và dùng fixture cho consumer integration tests.
- [ ] Dev 5 nối bộ lọc/điểm/provenance của adapter vào trace cuối của RAG; thay đổi này chưa thực hiện trong gói hiện tại.
- [ ] Chạy API/E2E trên môi trường đủ dependencies và dịch vụ thật khi nghiệm thu.
- [ ] Review, commit, CI và tích hợp lên `testing`; cập nhật ma trận truy vết bằng SHA nghiệm thu.

Không đánh dấu toàn bộ FR2.11 hoàn tất chỉ từ test adapter. Không thay đổi corpus, benchmark hoặc cấu hình đã khóa; không chạy A/B Test 30.
