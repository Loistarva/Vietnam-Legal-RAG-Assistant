# Đồng bộ dữ liệu phụ cho corpus 41 văn bản — 14/11/2026

Lần chạy full pytest sau commit bbac363 chỉ ra các dữ liệu dẫn xuất chưa được đồng bộ, ngoài lỗi negative set: PDF manifest, article index, production chunk index, alias map và corpus hash của cấu hình Test. Đã sinh lại bằng các công cụ sẵn có, không sửa code công cụ.

- `source_pdfs.json`: 41 PDF đầu vào; 13 bản gốc tải về vẫn được giữ riêng.
- `article_index.json`: thêm 521 Điều của 13 văn bản, tổng 1.372 Điều; phạm vi Điều trong retrieval vẫn theo corpus_scope hiện có.
- `production_chunk_index.json`: đủ 3.998 chunk, không có chunk chưa ánh xạ Điều, không đổi Gold.
- `document_aliases.json`: sinh từ registry 41 văn bản, 1.077 alias; alias mơ hồ vẫn không được tự chọn một văn bản.
- `source_status` của 13 văn bản mới dùng vocabulary sẵn có `Cần kiểm tra trạng thái mới nhất`, ánh xạ `Không xác định`. Không nâng trạng thái hiệu lực; ghi chú yêu cầu rà pháp lý và `trial_only` vẫn giữ.
- Đồng bộ metadata cấp văn bản trong 13 parsed JSON và payload mới; ID và nội dung Điều/Khoản không đổi. Audit xác nhận 1.079 parent và 2.322 child thuộc bộ 28 văn bản cũ giữ nguyên toàn bộ payload.

## Cấu hình Test theo phiên bản corpus

Snapshot corpus28 của `docs/test_run_config_freeze.json` được giữ nguyên byte tại [history/test_run_config_freeze_corpus28.json](history/test_run_config_freeze_corpus28.json). File cấu hình hiện tại cập nhật riêng hash corpus41, có `artifact_version=trial13_corpus41_input_snapshot` và `review_status=pending_peer_review`.

Đây là chuẩn bị cấu hình đầu vào mới, **không phải xác nhận đã review hoặc đã chạy Test chính thức**. Câu hỏi Test, Gold, hai manifest khóa câu hỏi/Gold, các phương pháp, top_k, cấu hình retrieval/reranking và hash tương ứng đều giữ nguyên. Kết quả đánh giá cũ vẫn thuộc corpus28; chưa cập nhật threshold hoặc diễn giải kết quả cũ như kết quả corpus41.

## Kiểm chứng

- Full suite trên Python 3.13.9: **1.481 passed, 1 skipped**.
- Nhóm integration liên quan: **204 passed**.
- Ruff E9/F63/F7/F82: PASS; compileall theo các thư mục CI: PASS.
- Manifest PDF: PASS; audit metadata: errors=0, warnings là các mục dữ liệu/hiệu lực còn chờ review.
- Không sửa parser, cleaner, chunker, negative-set validator, code kiểm tra freeze hoặc workflow CI gốc.
- Chỉ cập nhật fixture trong hai test: nguồn thiếu được lấy theo dataset đang kiểm, mẫu alias năm duy nhất dùng 1986, số lượng snapshot đổi từ 28/2.322 thành 41/3.998. Không bỏ test hoặc nới điều kiện để chấp nhận kết quả sai.

Các script `trial13_*` mô tả các bước ingest/chuẩn hóa trước đó. Metadata vẫn cần đi qua bước chuẩn hóa vocabulary và đồng bộ dữ liệu phụ nêu trên sau khi tái sinh; không chạy lại rồi coi kết quả tự động đã được duyệt pháp lý.
