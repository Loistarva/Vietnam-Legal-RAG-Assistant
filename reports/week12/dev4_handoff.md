# Bàn giao Dev 4 — Sprint 12

Cập nhật ngày 26/11/2026 (Asia/Saigon). Producer Test 30: `9144dfddbc6a3610dab17271f1290216e30dbb8d`; checker đã sửa: `626d3705c9e9e9e2e9449e451066f7edf742746f`. Các commit hiện có ở local; chưa xác nhận push, CI remote hoặc merge PR.

## Kết quả bàn giao

Hybrid BM25 + BGE-M3 + RRF đã lấy 50 ứng viên cho mỗi câu trong Test 30. Cross-Encoder BGE reranker đã chấm đủ cùng 1.500 ứng viên. Kiểm lại ngày 26/11/2026: **VERIFY PASSED**. Không gọi Qwen, chưa chạy A/B và chưa chấm mù.

Artifact gốc: `evaluation/results/precompute/test30_s12_001/`.

Gói chuyển giao local: `evaluation/results/handoff/dev4_s12_test30_001.zip`; SHA-256 của ZIP ở file cùng tên có đuôi `.sha256`. ZIP giữ nguyên đường dẫn tương đối trong repo, gồm tám file của lượt chạy, các báo cáo week12, fixture consumer và `SHA256SUMS.json`. Không kèm secret, môi trường `.venv` hoặc bản ghi phê duyệt local riêng; thông tin phê duyệt cần đối chiếu đã nằm trong manifest. Code được tham chiếu bằng commit, không nhúng toàn bộ repo vào ZIP.

| File trong thư mục artifact | Vai trò |
| --- | --- |
| `candidates.json` | Pool trước rerank |
| `reranked.json` | Đầu vào chính cho Dev 5 |
| `candidates_manifest.json`, `reranked_manifest.json` | Hash, ngày, cấu hình, model revision, môi trường và provenance |
| `run_receipt.json` | Kết quả tổng hợp đã kiểm |
| `rerank_checker_failure_receipt.json` | Bằng chứng phục hồi sau lỗi checker; không chạy lại model |
| `candidates.lock.json`, `reranked.lock.json` | Mốc bắt đầu các giai đoạn; giữ làm bằng chứng, không phải tiến trình còn chạy |

Lỗi checker ban đầu liên quan khóa `retrieval` được serializer thêm vào source rank/score. Checker sửa chỉ chấp nhận đúng rank/score gốc và giữ mọi trường evidence/nhánh cũ. Artifact không bị sửa; manifest ghi riêng SHA producer và verifier. Người nhận cần đọc receipt phục hồi, không hiểu đây là một lượt model chạy lại.

## Dev 5 kiểm nhận

1. Dùng code có commit checker `626d3705` và đúng frozen inputs. Giải nén vào vị trí mới, không đè kết quả hiện có. Đối chiếu hash ZIP với `.sha256` qua kênh bàn giao, rồi hash từng file với `SHA256SUMS.json` trong ZIP. Hash kiểm tính toàn vẹn, không thay thế xác nhận người gửi.
2. Chạy tại repo đã có môi trường dependencies:

   ```powershell
   python scripts/precompute_test30_retrieval.py verify `
     --output-dir evaluation/results/precompute/test30_s12_001
   ```

3. Yêu cầu `VERIFY PASSED`; kiểm đủ 30 ID/ngày và nạp `reranked.json` bằng `PrecomputedRerankedSource` theo [runbook](test30_precompute.md#manifest-và-handoff-dev-5).
4. Phân biệt pool retrieval 50, pool rerank 50, evidence runtime 5 và Top-10 của đánh giá cũ. Không sửa YAML/freeze để đồng nhất chúng.
5. Dùng [fixture giả lập](../../test/fixtures/sprint12/retrieval_handoff_samples.json) kiểm consumer: filter/ngày/provenance, empty, điểm từng nhánh và stage latency null/0. Tổng latency bắt buộc là số theo contract hiện tại; adapter từ chối khi không có số đo tổng.

Phiếu kiểm nhận (Dev 5 điền, hiện chưa có sign-off):

| Mục | Kết quả / người kiểm / thời điểm / bằng chứng |
| --- | --- |
| Nhận đủ gói và hash khớp | Chờ Dev 5 |
| Checker đúng phiên bản, `VERIFY PASSED` | Chờ Dev 5 |
| Nạp đủ 30 ID/ngày bằng consumer | Chờ Dev 5 |
| Chọn Top-5, parent fallback và trace cuối pipeline | Chờ Dev 5 |
| Đọc và chấp nhận provenance phục hồi checker | Chờ Dev 5 |

Không tự chỉnh artifact nếu lỗi; gửi lỗi cụ thể và commit consumer để Dev 4 đối chiếu.

## Các giai đoạn sau

| Người | Điều kiện bắt đầu | Đầu ra cần lưu |
| --- | --- | --- |
| Dev 3 / người phụ trách contract | Có manifest và tài liệu consumer | Kết luận manifest/contract cùng giới hạn còn lại |
| Dev 5 | Kiểm nhận xong; prompt A/B, Qwen, tham số sinh và Gate được xác nhận | Hai nhánh cùng Test 30/artifact, câu trả lời, evidence thực tế, trace, Gate, lỗi và manifest sinh |
| Người chuẩn bị chấm mù độc lập | Có kết quả sinh đầy đủ và rubric thống nhất | Bộ đã ẩn nhãn, xáo thứ tự, phiếu chấm; giữ riêng bảng ánh xạ |
| Dev 2 + Dev 4 | Nhận bộ đã làm mù | Hai phiếu chấm độc lập được khóa trước khi mở nhãn, kèm lý do/dẫn chứng |
| Người tổng hợp | Hai reviewer khóa điểm | Tổng hợp, mức đồng thuận, xử lý bất đồng và kết luận theo quy trình |

Dev 4 không xem kết quả sinh có nhãn A/B trước khi chấm. Không tinh chỉnh trên điểm Test. Mọi lượt chạy lại phải có lý do và lưu kết quả gốc.

## Ma trận bằng chứng và phạm vi nghiệm thu

| Hạng mục | Phần Dev 4 đã làm | Bằng chứng | Còn phụ thuộc |
| --- | --- | --- | --- |
| FR1.8-AC1 | Validator v6, audit exact/near-duplicate, ngưỡng/hash/cặp gắn cờ và phiếu review | [Audit Router](router_holdout_similarity.md), `scripts/audit_router_holdout_similarity.py` | Reviewer độc lập kết luận cặp W16RH_011; Tech Lead quyết định xử lý giới hạn |
| FR2.10 / precompute Test 30 | Retrieval và rerank thật, checker, manifest chain, cùng pool 30 × 50 | [Runbook](test30_precompute.md), artifact/receipt, `test/test_precompute_test30_retrieval.py` | Dev 3 xác nhận contract; Dev 5 kiểm nhận và tích hợp |
| FR2.11-AC1 | Filter, nguồn ngày, empty/error, branch rank/score, stage latency và fixture | [Retrieval trace](retrieval_trace.md), `test/test_retrieval_adapter.py` | Dev 5 truyền trace đến kết quả RAG; API/E2E trong môi trường đủ dependency |
| FR4.1-AC2 | Child fallback và missing-parent trace cho resolve trong RAG và upstream | `test/orchestration/test_evidence_index_mapping.py::test_missing_parent_uses_chunk_and_records_trace`, `test/test_pipeline_context.py` | Consumer review, CI và tích hợp |
| FR2.4-AC4 | Ngày biên, future, empty, filter trước Top-k và precomputed mismatch | `test/test_retrieval_filter_conformance.py` | Chưa chứng minh ES live hoặc cùng thứ hạng: ES giả lập DSL, Qdrant local thật, precomputed |
| PR #53 / tích hợp | Đã rà PR #53: OPEN, merge mô phỏng sạch; phiếu Dev4 đã có trên testing, đề xuất đóng có lý do | [Rà soát PR #53](pr53_review.md), [checks](pr53_review_checks.json) | Chưa đóng PR; code Sprint 12 riêng vẫn cần review/CI/tích hợp |

Không coi toàn bộ Sprint 12 hoặc từng FR đã nghiệm thu chỉ vì test producer pass.

## Nội dung đề xuất cho PR Dev 4

Kiểm lại local ngày 26/11/2026: **153 passed, 6 subtests passed**; validator holdout pass 36 câu, audit có 0 exact match và 1 cặp gắn cờ; checker artifact thật `VERIFY PASSED`. Lệnh tái lập bộ test:

```powershell
python -m pytest test/test_precompute_test30_retrieval.py test/test_precompute_dev30_retrieval.py test/test_retrieval_adapter.py test/test_retrieval_filter_conformance.py test/test_pipeline_context.py test/orchestration/test_evidence_index_mapping.py -q -p no:cacheprovider --basetemp .venv/pytest_s12_dev4_closeout_20261126
```

Lượt kiểm này không chạy lại model, không kiểm API/E2E hoặc CI remote. Không sửa sáu input đã freeze.

**Tiêu đề:** Sprint 12 Dev 4: bàn giao Test 30 precompute, trace retrieval và audit Router.

**Mô tả:** Bổ sung audit gần trùng holdout v6 có phiếu reviewer độc lập; bảo toàn filter/ngày/điểm/latency trong adapter và trace parent thiếu; kiểm temporal trên ba nhánh. Thêm wrapper precompute Test 30, manifest chain và checker chống ghi đè, sai hash/ngày/config/pool. Lượt thật đã tạo 30 × 50 ứng viên và rerank trên cùng pool; không gọi Qwen. Checker sửa để chấp nhận provenance `retrieval` do serializer production thêm, giữ nguyên artifact và ghi rõ phục hồi manifest. Xem bảng bằng chứng và các điều kiện chưa nghiệm thu ở tài liệu này.

Đây là nội dung chuẩn bị local, chưa đăng lên PR hoặc gửi cho người khác.
