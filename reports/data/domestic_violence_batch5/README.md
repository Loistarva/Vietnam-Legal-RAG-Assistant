# Mục 5 — Phòng, chống bạo lực gia đình

Ngày chuẩn bị: 18/11/2026. Nhánh `data/trial-13-documents`, baseline `cdd812b` (79 văn bản, 2.516 parent, 5.797 child).

## Kết quả

- **7 văn bản mới nhận vào bộ dữ liệu trial**, đủ PDF chuẩn hóa, metadata, nguồn chính thức/SHA-256, extracted/cleaned text và parsed JSON.
- **7 văn bản giữ chờ**, gồm 2 văn bản đã chờ từ lượt trung ương và 5 mục mới. Không tính bản scan, tệp dự thảo, trang giới thiệu hoặc văn bản tương lai chưa tương thích registry thành dữ liệu đã nạp.
- Không thêm trùng các văn bản đã có: Luật02/2007, Luật13/2022, NĐ08/2009, NĐ76/2023, NĐ110/2009, TT24/2011, NĐ110/2025 và TT66/2025.
- Chỉ thay đổi dữ liệu, metadata, phạm vi nạp, mapping, fixture tiêu đề đối chiếu nguồn và báo cáo. **Không sửa code cleaner/parser/chunker, schema, test logic hay workflow**. Giữ nguyên phạm vi cách ly TT07/2023 từ lượt trước.

## Danh mục nhận

| Số hiệu | Số Điều parse | Phạm vi chunk | Ghi chú |
|---|---:|---|---|
| 143/2011/TTLT-BTC-BVHTTDL | 11 | Toàn bộ chính văn | Kinh phí PCBLGĐ và hỗ trợ cơ sở ngoài công lập; lịch sử, hết hiệu lực 25/09/2024 theo Điều1 và2.1 TT58/2024. Nguồn Word dùng dấu `/` sau TTLT, chuẩn hóa mã về dạng `-` theo cách dẫn của văn bản bãi bỏ; giữ mã nguồn gốc trong metadata. |
| 58/2024/TT-BTC | 2 | Toàn bộ | Văn bản bãi bỏ TTLT143/2011. |
| 13/2016/TTLT-BGDĐT-BVHTTDL-BLĐTBXH-BCA | 12 | Toàn bộ | Giáo dục chuyển đổi hành vi xây dựng gia đình và PCBLGĐ. Số hiệu đầy đủ theo Công báo chính xác; không dùng bản ghi Công báo bị cắt đuôi mã. |
| 12/2013/TT-BVHTTDL | 7 | Toàn bộ | Hỗ trợ xây dựng gia đình hạnh phúc, phát triển bền vững tại cộng đồng; gồm hỗ trợ người bị BLGĐ và hoạt động PCBLGĐ. |
| 23/2011/TT-BVHTTDL | 10 | Chính văn | Thu thập, xử lý thông tin về gia đình và PCBLGĐ; biểu mẫu lưu nguồn, không giả thành Điều luật. Chưa xác minh đầy đủ hiệu lực hiện tại, metadata để Không xác định. |
| 282/2025/NĐ-CP | 71 | Điều1–2,4–7,37–55,64–65,69–71 | Xử phạt BLGĐ và các quy định chung/thẩm quyền liên quan. Loại các lĩnh vực an ninh, cư trú, ma túy, mại dâm, cờ bạc, hàng không; loại toàn Điều3 bản gốc do khoản6 đã sửa bởi NĐ347/2026, chờ temporal review cấp Khoản. |
| 347/2026/NĐ-CP | 42 | Điều33,41–42 | Điều33 sửa nguyên tắc xử phạt nhiều lần tại khoản6 Điều3 NĐ282/2025; Điều41–42 về thi hành. Loại các sửa đổi về dữ liệu, PCCC và lĩnh vực khác. Không tự hợp nhất hay cập nhật nội dung pháp luật trong bản gốc ND282. |

## Giữ chờ

- **TT24/2017/TT-BYT** (đã chờ trước): cả bản ký trang8–9 và Công báo đều lặp Điều16. Word chứa số Điều ghép và dấu vết sửa đổi (56,67,910…). Giữ nguồn và ảnh đối chiếu; không tự đánh lại số Điều.
- **NĐ144/2021/NĐ-CP** (đã chờ trước): bản ký hiện có là scan, chưa phục hồi được nguồn chữ đầy đủ đã kiểm chứng. Điều69.4 NĐ282/2025 có quy định thay thế và Điều70 chuyển tiếp; chưa thay đổi metadata cũ vì cần rà soát toàn bộ lịch sử.
- **TT23/2014/TT-BVHTTDL**: tệp Word trên cổng TTHC Huế có dòng “Dự thảo11(09/2/3/2010)”; chưa xác minh bản ban hành cuối cùng, không nạp.
- **TT27/2026/TT-BVHTTDL**: đã có nguồn Công báo/DOCX, PDF chuẩn hóa, đủ12 Điều, parse/schema/nội dung qua. Hiệu lực **01/01/2027**, chưa có hiệu lực tại ngày chuẩn bị. Registry/test mapping hiện không hỗ trợ trạng thái `Sắp có hiệu lực`; giữ staging và phạm vi đề xuất Điều1–3,12. Không đổi sang trạng thái hiện hành/không xác định để ép qua test, không sửa code ánh xạ. Chỉ nhận sau khi đến ngày hiệu lực hoặc chủ sở hữu hỗ trợ trạng thái đúng.
- **TT02/2010/TT-BVHTTDL**: URL Bộ hiện trả trang không tìm thấy văn bản, chưa lấy được bản gốc cuối cùng phù hợp.
- **TT07/2017/TT-BVHTTDL**: host nguồn Hà Nội không phân giải DNS sau lần thử được cấp quyền; trang Bộ chỉ là bài giới thiệu, chưa lấy được bản gốc toàn văn.
- **TT16/2009/TT-BYT**: trang giới thiệu chính thức có, chưa thu được tệp toàn văn chính thức.

## Chuẩn hóa và kiểm tra

- PDF dẫn xuất không có chữ ký số, Letter612×792, Times New Roman12pt; giữ nguyên byte nguồn, URL và SHA-256. Bản gốc Word/DOCX được lưu khi có; không gọi bản dẫn xuất là PDF ký gốc.
- Chỉ đổi khoảng trắng/xuống dòng, nối số hiệu `NĐ- CP` thành `NĐ-CP`, đưa số hiệu liên bộ bị ngắt ở bảng hai cột về một dòng. Giữ thứ tự từ/dấu câu trong chính văn; bảo vệ dẫn chiếu khỏi bị nhận nhầm là nhãn Điều bằng khoảng trắng.
- DOCX chỉ có footnote separator, không có nội dung chú thích chính văn. Word nguồn được kiểm tra footnote story bằng0. Bản Word TT24 và tệp có nhãn dự thảo không được dùng để nạp.
- Kiểm tra số Điều độc lập với nguồn: tổng **155 Điều** trong7 văn bản được nhận. Đối chiếu mọi từ trong chính văn với parsed, tiêu đề dài với Word nguồn; PDF token roundtrip, khổ/font/biên trang, render trang đầu/cuối: PASS.
- NĐ282: nội dung chính văn trong Word chính thức và Công báo **khớp hoàn toàn theo bộ đếm từ**, không có từ thừa/thiếu giữa hai bản nguồn. Báo cáo `nd282_word_gazette_comparison.json`.
- Lượt test đầu phát hiện số hiệu bị tách sau dấu gạch và ánh xạ trạng thái TTLT143; đã sửa dữ liệu, giữ TT27 ở staging và chạy lại toàn bộ test. Không miễn test hoặc nới ngưỡng. Log trước sửa được lưu riêng.
- Các trạng thái hiện tại chưa đối chiếu đầy đủ vẫn là `Không xác định`/`requires_review`; không tuyên bố toàn bộ văn bản còn hiệu lực. `production_ingest_allowed` ở staging chỉ biểu thị qua cổng kỹ thuật dữ liệu; vẫn cần peer review pháp lý/hiệu lực trước production.
- Chưa reindex Elasticsearch/Qdrant và chưa chạy đánh giá Run A/B mới.

- Kết quả sau cùng: **86 văn bản, 2616 parent, 6043 child**; thêm 100 parent, 246 child. Giữ nguyên toàn bộ79 metadata, 2516 parent và 5797 child cũ.
- Pytest: **2260 passed, 1 skipped, 235 subtests passed in 115.47s (0:01:55)**. Metadata audit:0 lỗi,86 cảnh báo và145 alias mơ hồ chờ peer review. Ruff, source PDF manifest, negative-set validator:PASS (2 cảnh báo dự kiến vì khác baseline đã ghim).

## Bàn giao

- `catalog.csv`: danh sách nhận/giữ chờ và nguồn.
- `selected_acquisition.json`, các tệp acquisition, `source_inspection.json`: truy vết tải nguồn và lựa chọn bản chữ.
- `normalization.json`, `content_layout_checks.json`, `parser_replay.json`, `independent_audit.json`: bằng chứng kiểm tra.
- `held_source_findings.json`, ảnh nguồn: lỗi cần xử lý tiếp; `data/staging/domestic_violence_batch5/proposed_future_scope.json` dành riêng TT27 tương lai.
- ZIP chứa dữ liệu của lượt này, bản nguồn, staging và registry/scope hiện tại; không phải chỉ mục production.

```powershell
python scripts/source_pdf_manifest.py --check
python scripts/audit_document_metadata.py
python scripts/validate_negative_set.py --fetch-sources
ruff check --select E9,F63,F7,F82 .
python -m pytest -q --basetemp=D:/GitHubProjects/.tmp-dv-tests-fixed --junitxml=reports/data/domestic_violence_batch5/tests_final.xml
```
