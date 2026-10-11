# Báo cáo kiểm kê và kiểm soát chất lượng dữ liệu

**Dự án:** Vietnam Legal RAG Assistant. **Ngày kiểm tra:** 2026-10-02.

## 1. Phạm vi

Nguồn: legal_documents_master (1).xlsx. Sheet tổng hợp có 261 dòng; laws_decrees có 217 dòng; circulars có 44 dòng. Tổng hợp khớp chính xác phép nối hai sheet thành phần. Chỉ kiểm kê sheet tổng hợp, tránh đếm thành 522 dòng. Mỗi dòng là metadata cấp Điều, không phải một văn bản riêng. Có 9 số hiệu văn bản. Không nhận raw_data hoặc schema nhóm.

## 2. Thống kê đầu vào

| Tiêu chí | Kết quả |
|---|---|
| Số dòng cấp Điều | 261 |
| Số văn bản theo số hiệu | 9 |
| Luật/Nghị định/Nghị quyết/TT/TTLT | 1 / 2 / 1 / 4 / 1 |
| ID Điều trùng | 0 |
| Đường dẫn đầu vào khác nhau | 47 |
| Thiếu legal_type đầu vào | 1 |
| Ngày có nháy thừa | 2 |
| Hiệu lực trước ban hành (dòng) | 17 |
| URL anchor lệch tiêu đề (dòng) | 66 |
| Thiếu related_documents | 198 |
| Thiếu notes | 217 |
| Sheet tổng hợp khớp thành phần | Có; không đếm thêm 261 dòng thành phần |
| PDF/HTML gốc | Chưa nhận; không kết luận file thiếu |
| Hiệu lực hiện hành | Chưa xác minh |

Không có ID Điều trùng. Cùng số hiệu hoặc cùng PDF ở nhiều Điều là quan hệ bình thường. Không dùng trùng title để xóa bản ghi vì nhiều văn bản có cùng tên Điều. Chưa có hash file để kiểm tra trùng byte.

## 3. Vấn đề đã xác định và xử lý

- L01_D32 thiếu legal_type; L01_D33 ghi Luât. Chuẩn hóa thành Luật dựa trên số hiệu và trang thuộc tính chính thức. Có 131 giá trị Luật kèm khoảng trắng cuối; cắt khoảng trắng. Hai ngày ở L01_D33 có dấu nháy thừa; đã bỏ nháy.
- 12 dòng của 01/2024/NQ-HĐTP ghi sai loại Nghị định, sai ngày ban hành 2024-02-16. Đã sửa loại thành Nghị quyết, ngày thành 2024-05-16 và cơ quan thành Hội đồng Thẩm phán Tòa án nhân dân tối cao. Ngày hiệu lực 2024-07-01 khớp nguồn. Giữ prefix ND03 để tránh phá liên kết cũ; cần nhóm thống nhất chuyển mã.
- 17 dòng 207/2025/NĐ-CP có effective_date=2025-01-10. Nguồn chính thức ghi 2025-10-01; đã sửa trong metadata chuẩn hóa, không suy diễn từ thứ tự ngày/tháng.
- 9 dòng thông tư liên tịch được phân loại chi tiết thành Thông tư liên tịch theo nguồn chính thức; nếu schema nhóm chỉ có Thông tư, cần ánh xạ nhóm loại và giữ subtype riêng.
- 12 dòng Nghị quyết cùng trỏ đến laws_decrees/2072025NĐ-CP.pdf của Nghị định khác. Đây là xung đột ánh xạ metadata, chưa chứng minh nội dung file. Đặt file_path của các Điều Nghị quyết thành null và giữ source_file_path cũ; không tự tạo tên file mới.
- Có 66 URL chứa anchor số Điều khác số trong title: cần đối chiếu toàn văn. Giữ URL gốc ở Điều và cờ url_anchor_match=false, không tự sửa anchor hoặc đánh số lại. URL chính thức cấp văn bản được bổ sung riêng, không dùng anchor sai cho dẫn chứng Điều.
- Dãy Điều của 126/2014/NĐ-CP trong bảng có 2,4..57, thiếu 1 và 3 trong phạm vi dãy. Chưa kết luận văn bản gốc thiếu Điều hoặc khẳng định đánh số đúng; có thể tiêu đề đã lệch. Chưa xác minh tính đầy đủ của các dãy khác.
- 198 related_documents và 217 notes trống. Chưa coi là lỗi bắt buộc vì thiếu schema. Không tự điền quan hệ hoặc đổi null thành “không có”.

## 4. Chuẩn hóa và bằng chứng

JSON gồm 9 documents với tổng 261 articles. document_id là prefix cấp văn bản lấy từ ID nguồn; article_id giữ nguyên ID dòng cũ. Mỗi Điều có source_record để truy về sheet và dòng gốc. Tên văn bản cấp document được bổ sung từ trích yếu nguồn, còn title cấp article giữ tiêu đề Điều. Không thêm nội dung Điều/Khoản vì Excel chỉ có metadata.

Đã đối chiếu số hiệu, loại, ngày ban hành, ngày hiệu lực bắt đầu và cơ quan từ trang thuộc tính chính thức cho 9 văn bản. Người ký được đối chiếu khi nguồn rõ; riêng thông tư liên tịch có khác cách ghi tên trên trang so với Excel nên giữ dữ liệu nguồn và yêu cầu PDF ký gốc. Các thay đổi từng trường được ghi trong Nhat ky sua. Ngày hiệu lực bắt đầu không chứng minh còn hiệu lực tại ngày kiểm tra. Toàn bộ status=unknown, giữ source_status=Còn hiệu lực.

URL nguồn đầu vào có 74 chuỗi khác nhau, gồm nhiều anchor. Kiểm tra cú pháp và tên miền trên mọi dòng; đã tra được trang chính thức tương ứng 9 số hiệu. Không thực hiện 74 phép HTTP trực tiếp để xác minh từng anchor. Các trang được truy xuất qua công cụ tra cứu; không có bằng chứng về mọi mã HTTP/redirect ở máy người dùng.

## 5. Kết quả còn chờ

Chưa nhận 47 file được tham chiếu nên chưa kiểm tra tồn tại, mở được, chữ ký, SHA-256, PDF scan, OCR, dấu tiếng Việt, header/footer hoặc Chương/Điều/Khoản. Ghi Chưa kiểm tra, không ghi 0 lỗi file thiếu. Chưa xác minh lịch sử sửa đổi, thay thế, bãi bỏ hoặc hiệu lực từng phần. Chưa validate theo schema nhóm vì chưa có hợp đồng dữ liệu. Bảng Excel là kết quả audit tại ngày ghi trên báo cáo, không tự kiểm tra lại khi sửa dữ liệu.

## 6. Quy trình khắc phục

1. Nhận raw_data và schema nhóm, chốt ID cấp văn bản/Điều và loại Nghị quyết/Thông tư liên tịch.
2. Đối chiếu đúng PDF cho Nghị quyết; cập nhật file_path còn null.
3. Đối chiếu 66 anchor lệch và dãy Điều Nghị định 126; kiểm tra cả tên, số Điều và nội dung thực tế, tránh chỉ sửa số trên tiêu đề.
4. Kiểm tra hiệu lực hiện hành và quan hệ sửa đổi/bãi bỏ; ghi bằng chứng, người xử lý và ngày.
5. Kiểm tra mọi file, trích xuất và cấu trúc; sau đó validate schema và bàn giao parser/chunking.

## 7. Kết luận

Hoàn thành kiểm kê và chuẩn hóa metadata cho toàn bộ 261 dòng đã nhận. Các lỗi có bằng chứng đã được sửa ở bản chuẩn hóa, nguồn Excel gốc được giữ để đối chiếu. Chưa đủ điều kiện xác nhận dữ liệu sẵn sàng indexing vì còn xung đột file Nghị quyết, anchor lệch, cấu trúc Điều và hiệu lực hiện hành chưa xác minh. Danh sách lỗi phân biệt Đã sửa, Chưa xử lý và trường tùy chọn, không cộng mọi mục thành số lỗi pháp lý.

## Nguồn đối chiếu

Các nguồn được tra ngày 2026-10-02. Chỉ hỗ trợ các trường thuộc tính nêu trên, không phải xác nhận hiệu lực hiện hành.

- 52/2014/QH13: https://vanban.chinhphu.vn/?docid=175351&pageid=27160
- 126/2014/NĐ-CP: https://vanban.chinhphu.vn/?docid=178372&pageid=27160
- 207/2025/NĐ-CP: https://vanban.chinhphu.vn/?docid=214619&pageid=27160
- 01/2024/NQ-HĐTP: https://congbao.chinhphu.vn/van-ban/nghi-quyet-so-01-2024-nq-hdtp-41972.htm
- 01/2016/TTLT-TANDTC-VKSNDTC-BTP: https://vanban.chinhphu.vn/?docid=183824&pageid=27160
- 02a/2015/TT-BTP: https://vanban.chinhphu.vn/?docid=179845&pageid=27160
- 32/2016/TT-BYT: https://vanban.chinhphu.vn/?docid=186859&pageid=27160
- 34/2017/TT-BYT: https://vanban.chinhphu.vn/?docid=191754&pageid=27160
- 30/2019/TT-BYT: https://vanban.chinhphu.vn/?docid=199571&pageid=27160
