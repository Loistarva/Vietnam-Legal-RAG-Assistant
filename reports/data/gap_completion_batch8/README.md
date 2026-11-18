# Phần 8 — Rà soát và bổ sung khoảng trống

Ngày chuẩn bị:18/11/2026. Nhánh `data/trial-13-documents`, baseline `8d0af49`:94 văn bản,2.760 parent,6.406 child.

## Kết quả

Nhận **5 văn bản**, giữ chờ **4 ứng viên** có nguồn chính thức. Có5 PDF ingest chuẩn hóa:3 dựa trên PDF Công báo có lớp chữ và2 dựa trên Word gốc Chính phủ (Luật Bình đẳng giới và Luật Quốc tịch2008). Hai PDF từ Word là bản phái sinh không chữ ký, không mô tả thành PDF ký gốc.

Kiểm kê toàn kho theo văn bản duy nhất:132 văn bản đã có tệp, gồm99 pass kỹ thuật trong corpus,20 chờ xử lý kỹ thuật/xác minh nguồn,10 chờ phạm vi/hiệu lực và3 trial13 đã loại khỏi HNGĐ nhưng còn lưu nguồn. Thêm3 mục chưa tải được tệp:135 mục theo dõi. Không cộng bản gốc/chuẩn hóa/staging thành nhiều văn bản; pass kỹ thuật không đồng nghĩa hoàn tất duyệt pháp lý. Xem `all_data_inventory.json`.

Tổng: **99 văn bản,2.814 parent,6.549 child**; thêm54 parent và143 child.195 Điều parsed toàn văn; chỉ50 Điều được chunk theo whitelist. Metadata vẫn `Không xác định`/`requires_review` cho hiệu lực hiện tại chưa kiểm đủ chuỗi sửa đổi. Chỉ ngày hiệu lực ban đầu đã đối chiếu; không gọi bản gốc là bản hợp nhất hiện hành.

| Văn bản | Điều toàn văn | Điều đưa vào chunk |
|---|---:|---|
|73/2006/QH11 — Bình đẳng giới|44|1–6,18,33,43,44: nguyên tắc, bình đẳng/trách nhiệm gia đình, thi hành|
|24/2008/QH12 — Quốc tịch Việt Nam|44|9,10,15,17,18: vợ chồng và quốc tịch trẻ em; tạm loại16,35–37 chờ sửa đổi|
|05/2015/TTLT-BTP-BCA-BYT|21|21 Điều về liên thông khai sinh, cư trú, BHYT cho trẻ dưới6 tuổi; **nguồn lịch sử**, không coi là thủ tục hiện hành mặc định|
|68/2020/QH14 — Cư trú|38|13,14,18,38: người được giám hộ, vợ chồng, người được chăm sóc/nuôi dưỡng/trợ giúp, hiệu lực|
|11/2017/QH14 — Trợ giúp pháp lý|48|1,2,8,9,27,31,32,33,47,48: khái niệm, quyền/nghĩa vụ, hình thức trợ giúp và thi hành|

Các Điều chung chỉ có vai trò hỗ trợ vụ việc HNGĐ; không coi mọi vụ việc cư trú, quốc tịch hoặc trợ giúp pháp lý là HNGĐ. Không đổi scope của văn bản cũ để nhận thêm Điều chưa được duyệt. Chưa reindex Elasticsearch/Qdrant hoặc chạy RunA/B.

## Giữ chờ và hiệu lực

- **79/2025/QH15**: giữ PDF/Word chính thức; Điều1 trộn sửa đổi quốc tịch trong nhiều lĩnh vực. Cơ chế whitelist hiện tại chỉ theo Điều, chưa tách sửa đổi HNGĐ cấp khoản để index. Không áp dụng lại nguyên bản Điều16 và35–37 Luật2008 như chưa sửa.
- **56/2014/QH13**: PDF ký thiếu lớp chữ đầy đủ, không tự OCR chưa kiểm chứng.
- **118/2025/QH15**: giữ PDF/DOCX chính thức để đối chiếu sửa Luật Cư trú tại Điều4. Tạm cách ly Điều12 và20–22 bản gốc, đặc biệt quy định nơi cư trú của con và đăng ký về với cha mẹ. Không nhận10 luật an ninh/trật tự vào corpus HNGĐ.
- **05/2026/QH16**: ngày ban hành23/04/2026; **hiệu lực01/01/2027** tại Điều3 và Công báo. Giữ ở hold, không áp dụng sớm điều kiện TGPL mở rộng. Điều7 Luật2017 cũng bị tạm loại để chờ đối chiếu53/2024 và59/2024.
- TTLT05/2015 là bản gốc thời kỳ thủ tục giấy; ND63/2024 và ND301/2026 về quy trình điện tử đã có. Chưa xác minh đủ mốc hết hiệu lực toàn bộ của TTLT trong lượt này, không suy ngày từ trang liệt kê hay nhãn tìm kiếm. Không dùng nguồn này làm quy trình mặc định hiện tại.

**Chưa lấp toàn bộ khoảng trống.** `gap_inventory.json` ghi riêng việc đã bổ sung một phần và việc còn mở: thi hành án cấp dưỡng/giao con, chuỗi quốc tịch, y tế hỗ trợ sinh sản, HNGĐ trong hình sự/đất đai/nhà ở và các nguồn chờ parser. `remaining_held_inventory.json` tổng hợp hold từ các lượt trước, không tính nguồn chờ thành văn bản đã nạp.

## Chuẩn hóa và sửa lỗi dữ liệu

- PDF Letter612×792pt, Times New Roman12pt; kiểm tọa độ/font mọi trang, token roundtrip và render đầu/cuối. Giữ nguyên byte nguồn, URL và SHA-256; loại bản sao nguồn trùng byte.
- Word2008 dùng TAB giữa tiêu đề Điều15 và câu quy phạm; chuyển ranh giới TAB thành xuống dòng, giữ toàn bộ từ và dấu. Không đưa câu quy phạm vào tiêu đề hay thêm Khoản giả.
- Tiêu đề Điều18 TTLT05/2015 tiếp nối bằng “Trung ương…” bị parser dừng sớm khi dòng mới viết hoa. Chỉ đổi chỗ xuống dòng tại điểm ngữ pháp, bảo toàn từ; cập nhật cùng tiêu đề đầy đủ vào article_index. Không sửa code parser.
- Nguồn Word của Luật Cư trú/TGPL có đánh số tự động không nằm trong phần text trích; chọn **PDF Công báo** làm nguồn chữ chính để giữ số Khoản thật. Không tự điền số dự đoán.
- Ngày trang metadata Chính phủ của Luật73/2006 và24/2008 khác ngày thông qua ghi trong bản gốc. Dùng29/11/2006 và13/11/2008, hiệu lực01/07/2007 và01/07/2009; lưu cả HTML và ghi rõ khác biệt.
- Kiểm đủ số Điều, schema, bảo toàn từ chính văn vào parsed, replay parser, SHA nguồn/PDF/parsed/text, staging-active và baseline audit:PASS. Không sửa cleaner/parser/chunker/alias, schema, test logic hoặc workflow.

## Negative set

TTLT05/2015 đã có chunk nên nghỉ3 ca NEG_DEV_030–032; chuyển vào danh sách chờ review, **không tự tạo Gold**. Thay bằng033–035 yêu cầu chunk sơ cấp của các bản còn hold79/2025,118/2025 và56/2017. Bộ v5 vẫn26 ca, nhãn chờ Dev2/Tech Lead duyệt. Snapshot v4 được giữ nguyên byte. Tênv2/v4 là alias tương thích vì pipeline hiện yêu cầu; không sửa code hay Test freeze.

## Kiểm tra cuối

- Pytest: **2452 passed, 1 skipped, 248 subtests passed in 120.89s (0:02:00)**.
- Metadata audit:0 lỗi,98 cảnh báo và169 alias mơ hồ chờ peer review.
- Ruff, PDF manifest, negative-set validator, whitespace diff:PASS. Negative-set có2 cảnh báo dự kiến vì corpus khác baseline ghim.
- Giữ nguyên94 metadata cũ,2.760 parent và6.406 child cũ. ZIP là gói data bàn giao, không phải phê duyệt triển khai production.

`catalog.csv` liệt kê nguồn nhận/giữ chờ. Các báo cáo normalization, content_layout_checks, parser_replay, independent_audit và validation_summary là bằng chứng kiểm tra. Nguồn gốc lưu ở source_documents/source_pdfs; PDF chuẩn hóa đã nhận nằm ở raw_data.
