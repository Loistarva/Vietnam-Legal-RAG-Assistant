# Phần7 — Văn bản địa phương, lượt đầu TP.HCM

Ngày chuẩn bị18/11/2026; nhánh `data/trial-13-documents`, baseline `6616d74`.

## Kết quả

- Tải6 PDF gốc từ Công báo TP.HCM, lưu URL, trang thuộc tính và SHA-256. Nhận **1 văn bản**, giữ chờ **5 văn bản**. Các nguồn tỉnh khác không tải được được ghi riêng trong `unavailable_sources.json`, không tính đã có PDF.
- **38/2026/NQ-HĐND**, ngày27/08/2026, hiệu lực01/10/2026: chế độ bồi dưỡng hàng tháng cho cộng tác viên dân số tham gia công tác gia đình, phòng chống bạo lực gia đình ở cộng đồng TP.HCM. Đủ5 Điều. Metadata nguồn ghi “Đang hiệu lực” tại thời điểm tải; đối chiếu hiệu lực ban đầu tại Điều5.
- Đã thêm PDF chuẩn hóa vào raw_data, metadata, alias, extracted/cleaned text, parsed JSON, article_index và chunk output. Tổng **94 văn bản, 2760 parent, 6406 child**; thêm5 parent và8 child.
- Không sửa code cleaner/parser/chunker/alias, schema, test logic hoặc workflow. Toàn bộ93 metadata cũ,2.755 parent và6.398 child cũ giữ nguyên.

## Phạm vi địa phương

Nghị quyết này áp dụng tại **TP.HCM**, không phải mức bồi dưỡng toàn quốc. Tên địa phương giữ trong title/issuing_body và reference metadata `territorial_scope`, `jurisdiction_review_required`. ID có hậu tố địa phương. Pipeline hiện chưa có bộ lọc địa bàn tự động; phải rà soát địa bàn trước khi triển khai retrieval production. `production_ingest_allowed` chỉ là cổng kỹ thuật data hiện có, không phải phê duyệt production. Chưa reindex dịch vụ tìm kiếm và chưa chạy RunA/B mới.

Không thêm văn bản trùng số hiệu của hai tỉnh: registry/alias hiện yêu cầu duy nhất document_number. Không sửa code để vượt giới hạn đó. Không tự mở rộng phạm vi văn bản cũ theo địa giới sau sáp nhập.

## Nguồn giữ chờ

| Số hiệu | Lý do |
|---|---|
|17/2026/QĐ-UBND TP.HCM|PDF chuẩn hóa và parser qua đủ13 Điều, nhưng alias registry chưa hỗ trợ loại Quyết định. Giữ full normalized PDF và parsed candidate ở staging; không đổi nhãn thành Nghị quyết hoặc sửa code. Điều12.4 có điều kiện chấm dứt một số mức chi, cần temporal review cấp khoản.|
|18/2026/NQ-HĐND TP.HCM|Phụ lục chứa bảng mức lệ phí hộ tịch. Không nạp chỉ5 Điều rồi coi đã có đủ mức thu. Giữ nguyên toàn bộ PDF, chờ hỗ trợ bảng.|
|1990/QĐ-UBND TP.HCM|Quyết định bãi bỏ thủ tục hộ tịch; số hiệu không có năm. Không tự thêm năm vào số hiệu; loại Quyết định cũng chưa được alias hỗ trợ.|
|72/2011/QĐ-UBND TP.HCM|Phần quyết định có Điều1–3, quy định đính kèm đánh lại Điều1–12. Parser hiện không phân biệt được hai phạm vi Điều. Metadata nguồn hết hiệu lực11/02/2016.|
|93/2006/QĐ-UBND TP.HCM|Chi phí hòa giải cơ sở nói chung, không giới hạn riêng HNGĐ; giữ tham khảo, không mở rộng lượt HNGĐ bằng văn bản chung. Metadata nguồn hết hiệu lực20/11/2011.|

Các nguồn giữ chờ không xuất hiện trong active registry, active raw PDFs, parser output hay chunks. Parsed candidate của QĐ17 chỉ nằm trong staging.

## Chuẩn hóa và kiểm tra

PDF dẫn xuất không có chữ ký số: Letter612×792pt, Times New Roman12pt, có kiểm font/biên trang và ảnh trang đầu/cuối. Giữ nguyên byte nguồn. Ánh xạ lớp chữ font cũ `ð→Đ`, `ñ→đ`, `Ð→Đ` cho QĐ17 đã đối chiếu ảnh bản gốc; không sửa câu chữ pháp luật. Bỏ header Công báo và thông tin ký khỏi đầu vào ingest, toàn bộ bản gốc/source_text vẫn được giữ. Các lỗi dấu sẵn có trong lớp chữ nguồn không được tự suy đoán sửa.

PDF token roundtrip, đủ số Điều, schema, bảo toàn từ chính văn, replay parser, SHA nguồn/ingest/parsed, staging-active và audit baseline:PASS. Báo cáo `content_layout_checks.json` gồm cả QĐ17 qua parser nhưng giữ chờ ở bước alias.

- Pytest: **2377 passed, 1 skipped, 243 subtests passed in 124.98s (0:02:04)**.
- Metadata audit:0 lỗi,93 cảnh báo có sẵn và165 alias mơ hồ chờ peer review.
- Ruff, PDF manifest, negative-set validator, git diff whitespace:PASS. Negative set có2 cảnh báo dự kiến do khác baseline ghim.

`catalog.csv` liệt kê nhận/giữ chờ; `independent_audit.json`, `parser_replay.json`, `validation_summary.json` là bằng chứng kiểm tra. ZIP chỉ là bộ dữ liệu bàn giao, không phải chỉ mục production.
