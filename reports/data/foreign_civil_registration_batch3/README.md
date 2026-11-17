# Lượt 3 — Hộ tịch có yếu tố nước ngoài

Ngày chuẩn bị: 18/11/2026. Nhánh `data/trial-13-documents`, baseline `b858e7b`.

## Kết quả

- **2 văn bản mới được nạp vào bộ dữ liệu trial**: TTLT 06/2012/TTLT-BTP-BNG và TT 08/2025/TT-BTP. Có PDF ingest, metadata, nguồn gốc, SHA-256, extracted/cleaned text và parsed JSON.
- **2 văn bản giữ chờ**: TTLT 11/2008/TTLT-BTP-BNG (mới) và TTLT 02/2016/TTLT-BNG-BTP (đã chờ ở lượt trung ương). Đã tải PDF Chính phủ/Công báo; lớp chữ chỉ có tiêu đề hoặc gần như rỗng. Không nạp OCR chưa kiểm chứng hay tự tạo Điều.
- Kho từ **77 lên 79 văn bản**. Hai văn bản mới bổ sung **25 parent, 39 child**; đồng thời cách ly 26 child thuộc khối Điều23 lỗi của TT07/2023. Số lượng sau cách ly xem `independent_audit.json`. 77 metadata cũ và các parent/child ngoài khối cách ly giữ nguyên.
- Không thêm lại các văn bản đã có như Luật Hộ tịch, NĐ123/2015, NĐ87/2020, TT04/2020, TT07/2023/TT-BNG, TT07/2025/TT-BNG. Không coi VBHN4449/2025 là một văn bản luật độc lập mới. Không thêm văn bản tương trợ tư pháp vào đợt hộ tịch.

## Phạm vi và chuẩn hóa

- **TTLT06/2012**: sửa quy định đăng ký hộ tịch tại cơ quan đại diện Việt Nam ở nước ngoài; có nội dung đăng ký kết hôn. Parse đủ 2 Điều. Giữ các việc hộ tịch liên quan trong cùng Điều sửa đổi, không cắt vụn hay đổi số Khoản.
- **TT08/2025**: văn bản nhiều lĩnh vực. Parse đủ 24 Điều; chỉ tạo chunk cho Điều **1–6, 23–24** bằng `corpus_scope.json` sẵn có. Điều 5 quy định ghi sổ nhận cha mẹ con và ghi chú ly hôn/hủy kết hôn đã giải quyết ở nước ngoài. Loại các Điều về chứng thực, bồi thường, luật sư, quốc tịch và nhiệm vụ ngoài phạm vi.
- Giữ nguyên PDF nguồn Công báo và Word chính thức; PDF ingest là bản dẫn xuất không có chữ ký số, khổ Letter 612×792, Times New Roman 12pt. Phụ lục/mẫu biểu và chữ ký vẫn trong nguồn gốc và sidecar, không giả làm Điều luật.
- Word field chỉ giữ chữ hiển thị, bỏ mã HYPERLINK không hiển thị. Chỉ điều chỉnh khoảng trắng/xuống dòng tiêu đề để parser hiện tại nhận đủ tiêu đề; kiểm tra từng tiêu đề với Word nguồn. Bổ sung fixture kỳ vọng tiêu đề dài Điều18 và Điều20, không sửa logic kiểm tra hay ngưỡng.
- Word có footnote story 54 ký tự: “Mẫu lời chứng được đánh máy hoặc khắc trên mẫu dấu”, thuộc phụ lục mẫu chứng thực. Đã trích riêng vào sidecar `.footnotes.txt` và giữ trong nguồn gốc; không có chú thích chính văn bị bỏ để nạp vào bộ Điều.
- Không sửa mã cleaner, parser, chunker, schema hoặc workflow.

## Hiệu lực và giới hạn

- Ngày hiệu lực ban đầu đối chiếu metadata Công báo và Điều thi hành: TTLT06/2012 là 03/08/2012; TT08/2025 là 01/07/2025.
- Chưa xác minh đầy đủ chuỗi sửa đổi/bãi bỏ hiện tại: metadata để `Không xác định`, `requires_review`; không gán là còn hiệu lực toàn bộ.
- Điều23 TT08/2025 có ngày kết thúc dự kiến 01/03/2027 kèm ngoại lệ và khả năng thay thế sớm từng quy định. Không ghi ngày này thành ngày hết hiệu lực vô điều kiện.
- **Đã cách ly lỗi có sẵn ở TT07/2023/TT-BNG**: cả trang53 Công báo (PDF trang13) và bản ký chính thức (PDF trang12–13) đi từ Điều23 sang Điều25. Parser chỉ tạo 23 Điều và gộp phần sau vào Điều23. Dùng `corpus_scope.json` sẵn có để chỉ truy xuất Điều1–22; 26 child của khối lỗi đã loại khỏi chunk export và production chunk index. Giữ nguyên nguồn, extracted/cleaned text và parsed archive. Khôi phục phần cách ly khi có đính chính chính thức hoặc parser hỗ trợ khoảng trống số Điều; không tự tạo Điều24. Có ảnh đối chiếu, băm bản ký và danh sách chunk cách ly.
- Đây là bộ dữ liệu trial, chưa reindex Elasticsearch/Qdrant và chưa chạy đánh giá Run A/B mới. `production_ingest_allowed` ở staging chỉ biểu thị qua cổng kỹ thuật dữ liệu của lượt này; vẫn cần rà soát pháp lý/hiệu lực trước triển khai production.

## Kiểm tra

- Parse/schema và số Điều độc lập: PASS (2 và 24 Điều).
- Đối chiếu toàn bộ từ trong chính văn với nội dung parsed: PASS; PDF token roundtrip, khổ/font/biên trang: PASS. Đã render và xem trang đầu/cuối.
- Replay parser bằng registry hiện tại: PASS. Metadata staging và active tương ứng, băm nguồn/ingest/parsed đúng.
- Metadata audit: 0 lỗi; 79 cảnh báo và 137 alias mơ hồ cần peer review, không tuyên bố đã xử lý hết.
- Ruff, source PDF manifest và negative-set validator: PASS. Negative set có 2 cảnh báo dự kiến vì corpus khác baseline đã ghim.
- Pytest: 2389 test cases trong JUnit, 0 failures, 0 errors, 1 skipped. Xem `tests_final.log` để biết số test/subtest của pytest.
- Kết quả pytest: 2160 passed, 1 skipped, 228 subtests passed in 177.79s (0:02:57)
- Sau cách ly: **79 văn bản, 2516 parent, 5797 child**; giữ nguyên 5758 child cũ ngoài khối lỗi.

## Tệp bàn giao và lệnh kiểm tra

- `catalog.csv`: danh mục nhận/giữ chờ, nguồn và metadata.
- `normalization.json`, `content_layout_checks.json`, `parser_replay.json`, `independent_audit.json`: bằng chứng kiểm tra.
- `acquisition.json`, `extra_sources.json`: URL chính thức và băm nguồn.
- ZIP đi kèm chứa dữ liệu của lượt này và registry/scope hiện tại; không chứa bộ dữ liệu production.

```powershell
python scripts/source_pdf_manifest.py --check
python scripts/audit_document_metadata.py
python scripts/validate_negative_set.py --fetch-sources
ruff check --select E9,F63,F7,F82 .
python -m pytest -q --basetemp=D:/GitHubProjects/.tmp-foreign-tests-final --junitxml=reports/data/foreign_civil_registration_batch3/tests_final.xml
```
