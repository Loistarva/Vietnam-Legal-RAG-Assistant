# Kiểm tra negative set v3 — 14/11/2026

## Thay đổi dữ liệu

Giữ 26 câu và phân bố 6 non_legal / 8 legal_out_of_scope / 6 missing_corpus_evidence / 6 insufficient_facts. So sánh object JSON với snapshot v2: **22 câu nguyên vẹn**, chỉ thay `NEG_DEV_013`–`NEG_DEV_016`.

| ID | Nguồn yêu cầu ở v2 | Nguồn sơ cấp yêu cầu ở v3 |
|---|---|---|
| NEG_DEV_013 | Luật 52/2010/QH12 | NĐ 24/2019/NĐ-CP |
| NEG_DEV_014 | Luật 52/2010/QH12 | NĐ 06/2025/NĐ-CP |
| NEG_DEV_015 | Luật 60/2014/QH13 | TT 07/2023/TT-BTP |
| NEG_DEV_016 | Luật 60/2014/QH13 | TTLT 05/2015/TTLT-BTP-BCA-BYT |

Danh tính văn bản được đối chiếu với nguồn cơ quan nhà nước ghi trong manifest. Kiểm tra thiếu nguồn dùng cả registry, trường số hiệu ở root chunk và metadata chunk. Một văn bản khác có dẫn chiếu đến số hiệu không đáp ứng yêu cầu trích trực tiếp nguồn sơ cấp trong bốn câu này. Không đưa đáp án pháp luật vào dataset hoặc khẳng định hiệu lực hiện hành từ bước này.

V2 corpus28 được giữ nguyên byte tại `history/dev_negative_v2_corpus28/`. Bốn câu cũ được đưa vào thư mục `review/`, chưa tự gán nhãn relevance hoặc đáp án dương.

## Tương thích mà không sửa code gốc

`dev_negative_queries_v2.jsonl` và manifest v2 ở đường dẫn mặc định của CI là bản sao byte-exact của bộ v3 hiện tại. Bản v2 cũ có snapshot riêng. Manifest phân biệt `artifact_version=dev_negative_v3` với `dataset_version=dev_negative_v2` là schema được code hiện tại chấp nhận. Không giả lập code đã hỗ trợ một schema v3 mới.

Các snapshot Dev/Test bắt buộc vẫn được pin bằng full Git SHA; baseline hiện tại trỏ đến commit dữ liệu corpus41 đứng ngay trước commit này. Snapshot Test bổ sung `6288e8c` tiếp tục được kiểm tra. Không đọc đáp án Test để soạn các câu thay thế.

## Fixture được cập nhật theo chấp thuận của người dùng

- `test/test_negative_set.py`: các fixture thử tình huống “nguồn thiếu vừa được nạp” lấy đúng số hiệu đang khai báo trong dòng dataset thay vì ghi cứng hai luật đã có. Giữ các assertion phát hiện lỗi, kiểm metadata/root và kiểm hash.
- `test/test_document_aliases.py`: fixture một Luật theo năm dùng 1986 thay cho 2014 (nay có hai luật); số lượng corpus mong đợi đổi từ 28/2.322 sang 41/3.998. Không thay đổi code resolver.

## Kết quả

- Validator ở đường dẫn CI mặc định với `--fetch-sources`: **26 câu, issues=[], warnings=[]**.
- Bản v3 chỉ định rõ qua `--dataset`/`--manifest`: PASS.
- Full pytest: **1.481 passed, 1 skipped**, xem [validation_tests_v3.log](validation_tests_v3.log).
- Nhóm integration liên quan: 204 passed; Ruff E9/F63/F7/F82 và compileall theo thư mục CI: PASS.
- Snapshot v2 nguyên byte và hai cặp file compatibility v2/v3 đã đối chiếu hash.
- Không sửa parser, cleaner, chunker, validator, schema model hoặc workflow CI gốc. Test questions, Gold và retrieval/reranking config giữ nguyên.

Việc đồng bộ các chỉ mục, vocabulary trạng thái chưa xác minh và phiên bản corpus input snapshot được giải thích riêng ở [corpus41_integration.md](../../reports/data/trial13/corpus41_integration.md). Không gọi bộ dữ liệu đã được duyệt hoặc chạy official Test chỉ vì kiểm tra kỹ thuật PASS.

## Review và sử dụng

Trạng thái: **pending_peer_review**, cần Dev 2 + Tech Lead duyệt bốn nhãn mới và hai case ranh giới `NEG_DEV_025/026`. Chưa chạy model/retrieval, chưa chọn threshold, chưa thay kết quả calibration cũ. File kết quả v2 cũ không được dùng cho v3 chỉ vì cùng tên đường dẫn hay cùng query ID; phải kiểm cả dataset/corpus hash.
