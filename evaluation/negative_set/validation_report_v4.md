# Negative v4 — corpus57

Mốc corpus: `4106ff0bd9d57e2436534b5fa7ab18c32d2db4aa`, 57 văn bản / 4.716 child chunk. Ngày chuẩn bị: 17/11/2026.

## Sửa nguyên nhân CI đỏ

CI chạy `python scripts/validate_negative_set.py --fetch-sources` trước pytest. Bộ v2 cũ còn NEG_DEV_013–018 yêu cầu nguồn sơ cấp 52/2010/QH12, 60/2014/QH13, 326/2016/UBTVQH14 dù cả ba nguồn đã có trong corpus57, nên validator đúng khi trả exit code 1. Lần kiểm tra trước chỉ chạy pytest nên không phát hiện việc entrypoint mặc định của CI còn dùng bộ dữ liệu cũ.

Không bỏ bước CI, không nới validator và không sửa code parser/chunker/schema. Thay đổi lần này là bộ dữ liệu và test hồi quy cho entrypoint CI.

- Lưu nguyên bản v2 trước sửa tại `history/dev_negative_v2_corpus28_4106ff0/`; giữ các snapshot v2/v3 đã có.
- Retire NEG_DEV_013–018, lưu nguyên câu/nhãn/lý do trong `review/retired_missing_sources_corpus57.json`.
- Thêm NEG_DEV_027–032: yêu cầu chính văn NĐ 56/2017/NĐ-CP (đang hold ngoài corpus) hoặc TTLT 05/2015/TTLT-BTP-BCA-BYT (chưa có trong registry/chunks). Chủ đề bảo vệ trẻ trong gia đình và thủ tục liên thông sau sinh. Không coi bản PDF ở vùng hold hay dẫn chiếu ở văn bản khác là chunk của nguồn sơ cấp được yêu cầu. Không suy luận hiệu lực pháp luật từ việc nguồn có/không có trong corpus.
- Giữ 26 câu và bốn nhóm nhãn: 6 non_legal, 8 legal_out_of_scope, 6 missing_corpus_evidence, 6 insufficient_facts. Các câu không bị thay thế giữ nguyên nội dung và ID.
- Manifest pin corpus57 và hash Git của dữ liệu; tiếp tục chống trùng Dev/Test bằng các snapshot đã khóa.
- `dev_negative_*_v4` là bản phát hành mới. `dev_negative_*_v2` là entrypoint tương thích mà script hiện có đang đọc, chứa cùng dữ liệu v4. `dataset_version=dev_negative_v2` là phiên bản schema được validator hỗ trợ; `artifact_version=dev_negative_v4_corpus57` phân biệt bản dữ liệu.
- Test mới chạy validator mặc định với corpus thực và kiểm tra hai entrypoint giống nhau; test lịch sử tiếp tục xác nhận cả 6 câu cũ bị phát hiện khi nguồn đã có. Các test giả lập thêm nguồn lấy số hiệu từ case đang thử thay vì gắn cứng nguồn của corpus28.

## Trạng thái duyệt

`pending_peer_review`: Dev 2 và Tech Lead cần duyệt phạm vi, câu thay thế và hiệu chỉnh. Kiểm tra cấu trúc/coverage thành công không phải tuyên bố đã hoàn tất duyệt nghiệp vụ. Bộ này dùng cho phát triển; không thay đổi ground truth Test hay kết quả A/B official.

Kết quả kiểm tra lần này nằm tại `reports/data/corpus_v2/ci_negative57_*`.

K?t qu? local: validator `--fetch-sources` exit 0, issues/warnings r?ng; 1845 passed, 1 skipped, 206 subtests passed; Ruff 0.17.4 E9,F63,F7,F82 v? compileall ??u qua.
