# Phần 6 — Giải quyết tranh chấp hôn nhân và gia đình

Ngày chuẩn bị:18/11/2026. Nhánh `data/trial-13-documents`; baseline `7eec902` gồm86 văn bản,2.616 parent,6.043 child.

## Kết quả lượt này

- **7 văn bản mới** có PDF ingest chuẩn hóa, metadata, URL/băm nguồn chính thức, extracted/cleaned text và parsed JSON. Đây là nhóm thủ tục dân sự hỗ trợ giải quyết tranh chấp HNGĐ, không phải7 văn bản chỉ điều chỉnh riêng HNGĐ.
- **3 văn bản đã tải nguồn nhưng giữ chờ** vì chưa tương thích đầy đủ với pipeline. Ngoài ra6 mục nguồn chưa phục hồi được bản gốc được liệt kê riêng ở `deferred_sources.json`, không tính là đã tải/đã nạp.
- Không thêm trùng BLTTDS92/2015, BLDS91/2015, Luật58/2020 về hòa giải/đối thoại tại Tòa án, NQ01/2024, TTLT01/2016/TANDTC-VKSNDTC-BTP hoặc NQ326/2016 đã có.
- **Không sửa code cleaner/parser/chunker, schema, test logic hoặc workflow.** Chỉ cập nhật data, metadata, phạm vi nạp, bảng ánh xạ, fixture tiêu đề đối chiếu nguồn và báo cáo. Giữ nguyên phạm vi cách ly và vùng chờ của các lượt trước.

## Danh mục được nhận

| Số hiệu | Số Điều parse | Phạm vi chunk |
|---|---:|---|
| 102/2025/QH15 — Luật Tương trợ tư pháp về dân sự | 38 | Điều1–35,37–38; loại Điều36 sửa tố tụng hành chính |
| 158/2026/NĐ-CP — hướng dẫn Luật TTTP dân sự | 24 | Chính văn; áp dụng như căn cứ thủ tục TTTP cho vụ việc HNGĐ có yếu tố nước ngoài |
| 13/2025/TTLT-BTP-BNG-TANDTC | 3 | Chính văn sửa đổi và chuyển tiếp của TTLT12/2016 |
| 12/2016/TTLT-BTP-BNG-TANDTC | 27 | Loại7,8,10,17 do đã có sửa đổi tại Điều1 TTLT13/2025; giữ phần còn lại làm nguồn lịch sử/chuyển tiếp chờ temporal review |
| 01/2019/TTLT-TANDTC-BNG | 23 | Tống đạt/thông báo và chi phí ở nước ngoài; tạm loại18,21 về tổ chức/trách nhiệm hệ thống Tòa án |
| 02/2020/TT-TANDTC | 8 | Chỉ1,6,8: phạm vi chung, cơ sở vật chất và thi hành; tạm giữ các Điều tổ chức/trách nhiệm/biểu mẫu chờ nguồn sửa đổi TT05/2025 |
| 03/2020/TT-TANDTC | 10 | Chỉ1,2,8,9,10: quy định chung nhận đơn, thời điểm hòa giải, chuyển đơn sang tố tụng và thi hành |

Tổng133 Điều trong parsed JSON; chunk chỉ theo whitelist hiện có. Nguồn có quy định dân sự chung (có thể dùng cho cả lao động/kinh doanh) hoặc phối hợp cả tố tụng hành chính; chỉ được bổ sung với vai trò thủ tục hỗ trợ HNGĐ. Không đưa luật hình sự, dẫn độ, phá sản, tài sản dòng họ hay trọng tài thương mại thành một nhóm HNGĐ mới. Biểu mẫu/phụ lục vẫn nằm trong nguồn gốc và sidecar, không được giả thành Điều luật.

## Hiệu lực và giới hạn pháp lý

- Ngày ban hành, hiệu lực ban đầu theo nguồn chính thức. Luật102/2025 Điều37.1 và NĐ158/2026 Điều24 xác nhận hiệu lực01/07/2026.
- Điều37–38 Luật102/2025 và Điều24 NĐ158/2026 có ngoại lệ chuyển tiếp cho yêu cầu cũ. TTLT13/2025 Điều3.2 cũng quy định tiếp tục áp dụng TTLT12/2016 cho hồ sơ trước01/09/2025. **Không gán ngày hết hiệu lực vô điều kiện hoặc tự hợp nhất** từ các quy định này.
- Toàn bộ7 bản ghi để `Không xác định`/`requires_review` cho trạng thái hiện tại chưa được đối chiếu đầy đủ. Cần rà soát pháp lý/hiệu lực cấp Điều/Khoản trước khi dùng trong production, nhất là các nguồn2016–2020 và thay đổi tổ chức Tòa án2025. Các bản gốc này không phải bản hợp nhất hiện hành.
- `production_ingest_allowed` ở staging chỉ biểu thị đã qua cổng kỹ thuật dữ liệu của lượt này, không phải xác nhận đủ điều kiện triển khai production.
- Giữ nguyên data_contract/schema và các quy tắc temporal hiện có. Chưa reindex Elasticsearch/Qdrant, chưa chạy đánh giá RunA/B mới.

## Giữ chờ và nguồn còn thiếu

- **02/2016/TTLT-VKSNDTC-TANDTC**: nguồn đầy đủ38 Điều, nhưng tiêu đề Điều18 dài81 từ vượt MAX_TITLE_WORDS80. Parser cắt tiêu đề thành “Gửi quyết định của”. Giữ bản gốc và PDF chuẩn hóa đầy đủ; output parse sai nằm riêng tại `rejected_parser_output`, không ở corpus. Có ảnh đối chiếu `held_ttlt02_article18.png`. Không đổi số Điều, rút gọn tiêu đề hoặc nới ngưỡng.
- **16/2021/NĐ-CP** và **07/2026/TT-BTP**: tải được PDF ký/ban hành chính thức, nhưng lớp chữ gần như chỉ có thông tin ký; không tự nạp OCR chưa kiểm chứng.
- Chưa lấy được nguồn gốc đáng tin cậy cho NQ02/2020,04/2017,04/2016,01/2017,04/2018 và TT05/2025/TANDTC. Các trang giới thiệu không được nạp thay văn bản gốc. URL TAND363847 được tìm thấy có nội dung hợp nhất về thi đua/khen thưởng, chỉ dẫn chiếu TT05/2025: không coi đó là bản gốc TT05/2025. Cần phục hồi các nguồn này ở lượt tiếp theo.

## Chuẩn hóa và bằng chứng kiểm tra

- PDF ingest là bản dẫn xuất không chữ ký số, Letter612×792, Times New Roman12pt; giữ nguyên byte PDF/Word/DOCX nguồn, URL và SHA-256.
- Điều chỉnh khoảng trắng/xuống dòng để số hiệu/tiêu đề không bị cắt, bảo vệ dẫn chiếu nội dòng khỏi bị nhận nhầm làm nhãn Điều; chuẩn hóa vị trí dấu thanh qua cleaner hiện có. Không sửa nội dung quy phạm.
- DOCX NĐ158 có đúng1 đoạn đánh số tự động OOXML: câu đầu Điều24. Trích `w:t` làm mất nhãn1; đã phục hồi **1.** theo PDF Công báo. Kiểm tra OOXML và đối chiếu toàn bộ chính văn sau phục hồi: khớp PDF.
- Cả6 văn bản lấy chữ từ Word/DOCX khớp Công báo theo bộ đếm từ chính văn, không có từ thừa/thiếu. Hai DOCX không có footnote nội dung; các Word được kiểm tra footnote story bằng0. Các nguồn scan không dùng làm đầu vào nạp.
- Kiểm số Điều độc lập, schema, replay parser với registry hiện tại, bảo toàn từ chính văn, PDF token roundtrip, khổ/font/biên trang và render trang đầu/cuối:PASS.
- Metadata/nguồn/PDF/parsed/normalized text được kiểm SHA-256; các bản PDF nguồn trùng byte đã được loại bản sao, không thay nội dung nguồn.
- Các cảnh báo chunk về trạng thái chưa xác định được giữ để peer review. NĐ158 Điều7 và TTLT12/2016 Điều5,13 có intro bị giới hạn trong `embed_text` theo budget hiện có; nội dung đầy đủ vẫn ở parent/parsed/chunk, không cắt văn bản nguồn để ép qua giới hạn. Các mảnh ngắn dưới20 từ được cảnh báo là dữ liệu cũ.

- Kết quả: **93 văn bản, 2755 parent, 6398 child**; thêm139 parent và355 child. Giữ nguyên86 metadata,2.616 parent và6.043 child cũ.
- Pytest: **2363 passed, 1 skipped, 242 subtests passed in 129.03s (0:02:09)**. Metadata audit:0 lỗi,93 cảnh báo và165 alias mơ hồ chờ peer review. Ruff, PDF manifest, negative-set validator:PASS; negative set có2 cảnh báo dự kiến vì khác baseline đã ghim.

## Tệp bàn giao

`catalog.csv` là danh sách nhận/giữ chờ. `normalization.json`, `content_layout_checks.json`, `word_gazette_comparisons.json`, `parser_replay.json`, `independent_audit.json` chứa bằng chứng kiểm tra. Các tệp acquisition/source_inspection và nguồn gốc phục vụ truy vết. ZIP chứa dữ liệu của lượt này, nguồn, staging và registry/scope hiện tại; không phải chỉ mục production.

```powershell
python scripts/source_pdf_manifest.py --check
python scripts/audit_document_metadata.py
python scripts/validate_negative_set.py --fetch-sources
ruff check --select E9,F63,F7,F82 .
python -m pytest -q --basetemp=D:/GitHubProjects/.tmp-dispute-tests-final --junitxml=reports/data/dispute_resolution_batch6/tests_final.xml
```
