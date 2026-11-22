# Xử lý thẩm định corpus

Đối chiếu báo cáo Google Docs với commit `2438a76` trên nhánh `data/trial-13-documents`. Bắt đầu ngày 22/11/2026. Tập active sau rà soát gồm **84 văn bản, 2.632 parent, 6.135 child và 3.841 dòng article_index**. Đây là kết quả chuẩn hóa và thu hẹp phạm vi; chưa phải phê duyệt hiệu lực pháp lý cho toàn bộ corpus.

## Phạm vi đã xử lý

- Chuyển 12 văn bản hoãn và 3 văn bản ngoài phạm vi sang `data/staging/corpus_review_20261122/archive/`. Giữ nguyên byte của 60 tệp PDF, parsed JSON, cleaned text và extracted text; lưu SHA-256 và đường dẫn cũ trong `review_decisions.json`.
- Loại 414 child cùng parent tương ứng khỏi tập active; đồng bộ registry, PDF manifest, corpus_scope, article_index, production_chunk_index, alias map và bảng danh mục. Các bản nguồn chính thức trong source_documents/source_pdfs vẫn được giữ.
- Thêm **9 override** cho các Điều/Khoản bị thay thế toàn bộ hoặc bãi bỏ trong chuỗi NĐ19/2011, TT10/2020, TT21/2011 và TT01/2022. Mỗi bản ghi có ngày kết thúc và nhóm chunk bằng chứng theo thứ tự nguồn. Xem `temporal_changes.json`.
- Chuyển trạng thái chưa xác định của NĐ19/2011, TT10/2020 và TT21/2011 sang `Sửa đổi bổ sung` dựa trên văn bản sửa đổi đã có. Chỉ xác nhận phạm vi đối chiếu; vẫn giữ yêu cầu duyệt đầy đủ chuỗi hiệu lực.
- Sửa thông tin lỗi thời trong `provision_periods.not_applied`: NĐ104/2022, TT09/2022 và NĐ120/2025 đã có trong corpus. Không suy hết hiệu lực toàn Điều/Khoản từ việc đổi một cụm từ hoặc phân định thẩm quyền.
- Nội dung chữ, ID và liên kết parent của mọi chunk còn lại được bảo toàn. Chỉ 228 child đổi metadata có chủ đích. Không sửa code parser, cleaner, chunker, resolver, schema, workflow hoặc test.

## Các mục tiếp tục chờ duyệt

**35 văn bản active còn trạng thái `Không xác định`.** `legal_review_queue.json` liệt kê từng văn bản, nguồn và phạm vi đã có override. Không tự đổi thành còn hiệu lực khi chưa có căn cứ. Các mục chưa có ngày kết thúc không mặc nhiên là quy phạm hiện hành.

Ba đề xuất có căn cứ sửa đổi nhưng chưa áp dụng được bằng hợp đồng bằng chứng hiện tại: TT11/2021 bãi bỏ Điều7 TT21/2011; Luật85/2025 thay thế Điều35,37 BLTTDS; Luật81/2025 thay thế Điều4 Luật34/2024. Số hiệu văn bản gốc ở lời dẫn/tên văn bản thay vì chunk hoặc tên Điều; test hiện tại yêu cầu số hiệu tại chunk/tên Điều. Giữ đề xuất trong `temporal_changes.pending_technical_contract`, không thêm chữ vào nguồn hoặc sửa test để vượt kiểm tra. Đây là yêu cầu gửi người phụ trách code, chưa phải override đã áp dụng.

Các thay đổi theo cụm từ, chuyển tiếp, chuỗi sửa đổi bản trung gian, NĐ63/2024–NĐ301/2026, NĐ282/2025–NĐ347/2026 và phần tố tụng/hòa giải còn lại cần duyệt cấp quy phạm. Không dùng các override đã thêm để tuyên bố toàn bộ chuỗi đã hoàn tất.

Giữ `document_type = Luật` cho BL01/BL02 để tương thích enum và resolver hiện tại. Khi chủ sở hữu contract hỗ trợ `Bộ luật`, mới đổi đồng bộ schema, parser, alias và data; không đổi riêng metadata.

Metadata audit còn **84 cảnh báo và 127 alias nhập nhằng**. Số giảm chủ yếu do thu hẹp tập active, không có nghĩa các mục còn lại đã được duyệt. `alias_review_queue.json` giữ đầy đủ ứng viên để Dev2/Dev3 kiểm tra; không xóa alias hợp lệ hoặc tự chọn văn bản mới nhất. Negative labels, Gold/Test và trạng thái peer review được giữ nguyên.

## Nguồn và bàn giao

- [Báo cáo thẩm định](https://docs.google.com/document/d/1yw8iuBwDsRnMeKb9M6_yijZgUBz4JDy9EqY6rlbF2nI/edit).
- [NĐ06/2025](https://vanban.chinhphu.vn/?pageid=27160&docid=212318), [TT10/2025](https://vanban.chinhphu.vn/?pageid=27160&docid=214348), cùng văn bản gốc và URL trong registry/manifest; các mốc khác dẫn theo nhóm chunk trong `provision_periods.json`.
- `scope_changes.json`: quyết định và lý do cho đủ 15 văn bản; `integrity_checks.json`: kiểm tra bảo toàn; `validation_summary.json`: kết quả kiểm thử cuối.
- `all_data_inventory.json`: kiểm kê mới theo văn bản duy nhất. Các báo cáo và ZIP đợt cũ là snapshot lịch sử, không dùng để ghi đè tập active đã rà soát. Chưa reindex Elasticsearch/Qdrant, chưa thay corpus production hoặc chạy lại Run A/B.

Ưu tiên bàn giao: người duyệt pháp lý xác nhận các mục trong legal_review_queue và điều kiện nhận lại 12 bản hoãn; người phụ trách parser/citation xác nhận hợp đồng bằng chứng cho ba đề xuất chưa áp dụng; Dev2/Dev3 duyệt alias. Không mở rộng corpus trước khi chốt các mục này.
