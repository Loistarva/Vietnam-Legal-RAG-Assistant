# Dev 1 - review dữ liệu còn lại của PR #35

Ngày đối chiếu: 08/11/2026. Nền nội dung PR #35: `e0cea35`; cây mã của
`testing` tại merge `7643231` giống nền này. Kiểm trên nhánh sửa F1-F4 của PR #38.
Đây là kết quả hỗ trợ đối chiếu; không ghi `verified_by` hoặc ký duyệt pháp lý
thay người phụ trách. Không khẳng định rà soát toàn bộ văn bản sửa đổi tới hôm nay.

## 1. Phạm vi corpus

| Văn bản | Điều giữ | Kết quả |
|---|---|---|
| NĐ 07/2025 | 2, 3, 5 | Khớp phần sửa NĐ123/2015, NĐ87/2020 và thi hành. Điều 1/4 về chứng thực/quốc tịch được loại theo phạm vi đã công bố. |
| NĐ 18/2026 | 13, 17 | Khớp hộ tịch và thi hành. Đã đọc Điều 16: khoản 1 liệt kê Điều 1-10, 12; khoản 2 về Điều 11, không áp dụng Điều 13 nên không phát hiện thiếu điều khoản chuyển tiếp cho phần hộ tịch. |
| TT 04/2024 | 2, 3, 4 | Giữ cả sửa TT04/2020, chuyển tiếp và hiệu lực; Điều 1 về biểu mẫu quốc tịch ngoài phạm vi. |
| NĐ 87/2020 | Toàn văn | Không có giới hạn trong corpus_scope; exporter đưa toàn bộ vào như mô tả cấu hình. |

Đối chiếu tên và nội dung Điều trong parsed JSON với các PDF nguồn đã dùng khi
review 28 override. Test corpus_scope kiểm tập Điều xuất đúng cấu hình. Việc loại
các lĩnh vực như nuôi con nuôi là lựa chọn phạm vi sản phẩm, không phải kết luận
chúng không có quan hệ với Luật Hôn nhân và gia đình.

## 2. Metadata bốn văn bản mới

| ID / file_code | Ban hành | Hiệu lực | Cơ quan | Kết quả đối chiếu |
|---|---|---|---|---|
| nd_87_2020_nd_cp / ND12 | 28/07/2020 | 15/09/2020 | Chính phủ | Khớp Công báo |
| nd_07_2025_nd_cp / ND11 | 09/01/2025 | 09/01/2025 | Chính phủ | Khớp trang Chính phủ và Điều 5 |
| nd_18_2026_nd_cp / ND13 | 14/01/2026 | 15/01/2026 | Chính phủ | Khớp trang Chính phủ và Điều 17 |
| tt_04_2024_tt_btp / TT13 | 06/06/2024 | 06/06/2024 | Bộ Tư pháp | Khớp trang Chính phủ và Điều 4 |

Nguồn:

- [NĐ87/2020 - Công báo](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-87-2020-nd-cp-31814.htm)
- [NĐ07/2025 - Chính phủ](https://vanban.chinhphu.vn/?pageid=27160&docid=212416)
- [NĐ18/2026 - Chính phủ](https://vanban.chinhphu.vn/?pageid=27160&docid=216651)
- [TT04/2024 - Chính phủ](https://vanban.chinhphu.vn/?pageid=27160&docid=210403)

Không phát hiện lỗi số hiệu, ngày hoặc cơ quan trong bốn dòng registry. File_code
là mã nội bộ, được kiểm nhất quán với corpus, không có ý nghĩa pháp lý.

## 3. HN_078 / HN_207

- Cả hai đã sửa chữ “chồn” thành “chồng”, phù hợp diff PR #35.
- **HN_078:** căn cứ là Điều 18 Luật 52/2014 về tôn trọng/bảo vệ quyền nhân thân.
  Câu hỏi còn yêu cầu phân định chủ thể và thời điểm phát sinh trách nhiệm, vượt
  quá điều khoản đang dẫn. Đề nghị biên tập thành: “Theo Điều 18 Luật Hôn nhân và
  gia đình 2014, quyền và nghĩa vụ về nhân thân của vợ, chồng được tôn trọng và
  bảo vệ như thế nào?” Không tự sửa câu đã source_checked trong đợt này: cần
  người phụ trách duyệt lại và chạy lại kết quả Dev nếu đổi câu.
- **HN_207:** draft answer có phần đầu “của vợ chồng” và tiêu đề chương tiếp theo
  rơi vào đoạn trích. Hai candidate hiện có chứa đủ khoản 1-2 Điều 18 NĐ126/2014.
  Đã làm sạch đáp án từ hai chunk này trên nhánh `fix/dev1-nd126-draft-review`
  (nền PR #36), giữ draft và candidate, không đổi thành gold.

## 4. scripts/check_split.py

Đã đọc mã và kiểm thử: Test chưa duyệt bị báo lỗi; Khoản gold Dev/Test trùng bị
báo lỗi; candidate draft trùng Test bị cảnh báo; câu gần trùng cùng Điều bị báo
lỗi; cùng mẫu khác Điều không bị coi là trùng. `--strict` biến cảnh báo thành lỗi.

Trên nền PR #35: 0 lỗi, 19 cảnh báo draft đã biết. Trên nhánh PR #36 sau sửa 26
câu lịch sử: strict PASS, 0 lỗi, 0 cảnh báo. Không đồng nhất hai mốc dữ liệu này.
Độ giống dùng SequenceMatcher theo token: đây là kiểm cấu trúc/lexical, không
chứng minh không có trùng nghĩa hoặc xác nhận hiệu lực pháp lý của gold.

## 5. Ghi chú mới của lead

- **Luật 81/2025:** ngày ban hành 24/06/2025, hiệu lực 01/07/2025 khớp
  [Công báo](https://congbao.chinhphu.vn/van-ban/luat-so-81-2025-qh15-45513.htm).
  Khoản 13 Điều 2 trong PDF/corpus thay tên cấp Tòa án tại k3 Đ123 Luật52/2014;
  nguồn CSDL quốc gia được tìm thấy cũng mô tả cùng thay đổi. Giữ cách ghi
  `not_applied` cho thay cụm từ; không kết thúc cả Khoản còn nội dung khác.
  Nguồn [CSDL quốc gia](https://vbpl.moj.gov.vn/Toaannhandantoicao/Pages/vbpq-toanvan.aspx?ItemID=179416)
  trả 502 khi mở toàn văn; không coi lượt tìm kiếm này là xác thực tải lại bản gốc.
- **NĐ 120/2025:** đã tải và xem ảnh scan [PDF Chính phủ](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/6/120-cp.signed.pdf).
  Trang 2-3 (Điều 4), trang 9 (Điều 23) và trang 12 (Phụ lục I) xác nhận nội dung
  ghi chú về phân định thẩm quyền và thời hạn kết hôn. Mốc hết hiệu lực 01/03/2027
  có ngoại lệ kéo dài hoặc kết thúc sớm quy định tương ứng; không dùng như mốc
  tuyệt đối. Văn bản chưa có trong corpus: đây vẫn là khoảng trống đối với câu
  hỏi thẩm quyền hiện hành, cần nhóm quyết định cách nhập và xử lý khoảng áp dụng.
- Chưa có đủ căn cứ để chốt tình trạng hiện hành của TT32/2016 và TTLT01/2016;
  giữ ghi nhận chưa xác minh, không tự điền trạng thái.

## Kết quả và việc còn mở

- 16 test corpus_scope, check_split, source_pdfs, registry_periods: PASS.
- Không thay corpus/registry chỉ để đánh dấu đã review.
- Việc cần quyết định: biên tập HN_078, bổ sung NĐ120/2025, xác minh hai văn bản
  còn mở. Phần sửa thời điểm 26 câu và đáp án HN_207 ở nhánh benchmark riêng.
