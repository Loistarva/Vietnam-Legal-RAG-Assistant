# Bản bàn giao hiện tại: v2

Dùng `dev_negative_queries_v2.jsonl` và `dev_negative_manifest_v2.json`. Có 26 câu, đã rà coverage trên testing fc66642 (28 văn bản, 2.322 chunk); nhãn ranh giới NEG_DEV_025/026 chờ Tech Lead chốt. Xem [validation_report_v2.md](validation_report_v2.md). Các mô tả v1 dưới đây giữ để truy vết lịch sử.

# D1.5 — Tập câu âm Dev v1

24 tình huống mới, mỗi nhóm 6 câu, phục vụ router Dev 4 và abstention/clarification Dev 5. Tạo ngày **06/11/2026**; hạn 04/11 trong kế hoạch đã qua, không ghi lùi ngày. Trạng thái **pending_peer_review**: cần Dev 2 + Tech Lead duyệt nhãn/phạm vi trước khi chốt calibration. Không phải 30 câu official A/B hoặc Test holdout.

## Files và input

- `dev_negative_queries_v1.jsonl`: mỗi dòng một query, UTF-8; ID `NEG_DEV_001`–`NEG_DEV_024`, `split=dev`.
- `dev_negative_manifest_v1.json`: version, hash canonical, phân bố nhãn, baseline corpus/registry, nguồn câu hỏi chỉ dùng kiểm tra trùng và nguồn xác minh tên/số hiệu văn bản.
- Mốc `as_of_date=2026-10-15` giữ thống nhất với Dev Gold kế thừa. Ngày tạo artifact là 06/11; hai ngày có ý nghĩa khác nhau. Không lấy ngày chạy máy để tự thay mốc.

Các câu được soạn mới cho D1.5, không chọn/lấy đáp án/paraphrase từ benchmark. Validator so sánh ID và câu hỏi chuẩn hóa với cả Dev/Test baseline và Test của nhánh D1 mới đã push, theo SHA pin trong manifest và cả Dev/Test đang checkout; không dùng đáp án Test để viết nhãn hay chọn threshold. So khớp máy không chứng minh hết mọi dạng gần nghĩa; reviewer cần kiểm tra trùng ngữ nghĩa.

## Nhãn và hành vi mong đợi

| label | expected_route | expected_action | Dùng đánh giá |
| --- | --- | --- | --- |
| `non_legal` | `non_legal` | `general_chat` | Router, không phát kết luận pháp lý; không ép abstain |
| `legal_out_of_scope` | `legal_out_of_scope` | `policy_abstention` | Router, nói rõ giới hạn HNGĐ |
| `missing_corpus_evidence` | `legal_in_scope` | `insufficient_evidence_abstention` | Coverage/grounding với yêu cầu trích đúng nguồn sơ cấp |
| `insufficient_facts` | `legal_in_scope` | `clarification` | Hỏi dữ kiện còn thiếu, chưa kết luận tình huống cụ thể |

Đây là vocabulary của dataset; Dev 4/5 ánh xạ sang enum/runtime contract mà nhóm thống nhất. Không tạo canonical schema song song với `schemas/models.py` của Dev 3. `clarification` là hành động xử lý sau route `legal_in_scope`, không phải route thứ tư.

Trường chung: `id`, `question`, `split`, `as_of_date`, `label`, `reason`, `expected_route`, `expected_action`. Thiếu nguồn thêm `required_document_number` và `require_primary_source=true`; thiếu dữ kiện thêm `clarification_fields` (những thông tin cần hỏi, không phải đáp án phải khớp nguyên văn).

## Lưu ý cho router và threshold

- Câu có từ “gia đình”, “đám cưới”, “anh em” vẫn có thể là non-legal. Câu đất đai trong tập này đã loại trừ việc chia tài sản vợ chồng.
- 6 câu thiếu nguồn đòi **trích trực tiếp chính văn bản chỉ định**; corpus/registry baseline chưa có Luật Nuôi con nuôi 52/2010/QH12, Luật Hộ tịch 60/2014/QH13 và Nghị quyết 326/2016/UBTVQH14. Việc văn bản khác có dẫn tên hoặc tóm tắt quy định không đáp ứng yêu cầu nguồn sơ cấp này. Không kết luận cả chủ đề đều không thể trả lời.
- Việc nhận con nuôi, hộ tịch gia đình và án phí ly hôn được đề xuất là tình huống liên quan HNGĐ cho **source-coverage test**. Tech Lead/Dev 4 phải xác nhận biên phạm vi này; nếu router chủ động loại một nhóm, sửa nhãn/version trước calibration thay vì tính nhầm đó là retrieval false negative.
- 6 câu thiếu dữ kiện vẫn có thể nhận được giải thích quy định chung có điều kiện; không yêu cầu im lặng hoàn toàn. Cần hỏi lại, không tự bịa dữ kiện hoặc kết luận chắc chắn vụ việc. Ngày khảo sát không thay cho ngày xảy ra sự kiện.
- Không tính “mọi câu âm đều phải abstain”. Báo riêng router correctness, policy abstention, thiếu chứng cứ và clarification. Giữ disclaimer cố định của pipeline cả với general chat.
- Không dùng toàn bộ 24 câu làm nhãn relevance=0 cho reranker. Sau route guard, Dev 5 dùng nhóm thiếu nguồn để xem false acceptance/coverage; nhóm thiếu dữ kiện cần policy riêng, có thể vẫn retrieve đúng điều luật với score cao. Threshold đơn lẻ không giải quyết đủ cả bốn nhóm.
- Tập Dev Gold calibration phải tính bằng phép loại **30 ID official thực tế** do Dev 2 bàn giao, không mặc định luôn 75−30. Chưa chạy model, retrieval hoặc chọn threshold trong D1.5.

## Kiểm tra và chạy

Từ root repository, dùng Python môi trường dự án:

```powershell
# Chay mot lan sau clone moi/shallow de tai cac Git SHA da pin
python scripts/validate_negative_set.py --fetch-sources
# Cac lan kiem tra offline:
python scripts/validate_negative_set.py
python -m pytest test/test_negative_set.py -q
```

Validator mặc định chỉ đọc dữ liệu; từ chối JSON trùng khóa/NaN/Infinity, JSONL hỏng hoặc có dòng trống và input sai kiểu. UTF-8 BOM/CRLF hợp lệ được hỗ trợ. Manifest không được bỏ các snapshot Dev/Test bắt buộc, giả trạng thái đã duyệt hoặc lệch ngày khảo sát. Các kiểm tra nội dung gồm: kiểm 20–30 câu, đủ bốn nhãn, ID/câu hỏi duy nhất, policy nhất quán, ngày hợp lệ, không trùng benchmark, source được khai báo đúng trong câu hỏi và thật sự vắng trong registry, cả root lẫn metadata của chunk, hash/count/inputs đúng manifest. Cần các commit pin trong manifest có ở local; nếu thiếu, fetch `testing` và `fix/d1-draft-check`. Mặc định không fetch mạng. Cờ --fetch-sources là bước opt-in tải Git commit thiếu, không checkout/merge, không sửa input, không tải luật mới và không gọi model. CI chạy bước này trước pytest để tránh thiếu lịch sử do checkout shallow.

Khi baseline/corpus đổi, validator dừng để review coverage/version; không sửa hash cho qua kiểm tra. Nếu một nguồn được thêm vào corpus, câu “thiếu nguồn” tương ứng phải gỡ/đổi nhãn qua review và tạo v2. Hash dataset dùng sorted-key UTF-8 JSON của mảng query, compact separators, thêm newline để ổn định qua checkout CRLF. Hash corpus/registry là byte từ Git blob ở SHA baseline, không tráo với hash file runtime.

## Nguồn và bàn giao

Yêu cầu: Kế hoạch Tuần 9 V3, mục 4.4, D1.5, D.6 và G.2. Link nguồn chính thức trong manifest chỉ xác minh danh tính văn bản, không thêm đáp án pháp lý hay khẳng định hiệu lực hiện hành: [Luật Nuôi con nuôi](https://vanban.chinhphu.vn/?docid=96052&pageid=27160), [Luật Hộ tịch](https://vbpl.moj.gov.vn/bonoivu/Pages/vbpq-thuoctinh.aspx?ItemID=46746), [Nghị quyết án phí](https://baochinhphu.vn/uy-ban-thuong-vu-quoc-hoi-ra-nghi-quyet-ve-an-phi-le-phi-toa-an-102215425.htm).

Handoff: Dev 4 nhận JSONL cho router; Dev 5 nhận để phân tích hành vi abstention/clarification và calibration; Dev 2 + Tech Lead duyệt. Kèm nhánh/PR, manifest version/hash, sample payload ở dòng đầu JSONL, hai lệnh trên và báo cáo `validation_report_v1.md`. Không ghi “đã được duyệt” hoặc “threshold đạt” chỉ từ dataset validation PASS.
