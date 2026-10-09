# Bộ kiểm kê dữ liệu pháp luật – 261 dòng

## File bàn giao

- data_audit.xlsx: Tong quan gồm thống kê và 9 văn bản; Kiem ke Dieu gồm 261 dòng chuẩn hóa; Danh sach loi gồm mục đã sửa và còn chờ; Nhat ky sua ghi giá trị trước/sau và bằng chứng; Du lieu goc giữ 261 dòng đầu vào.
- normalized_metadata.json: đối tượng audit, 9 documents và tổng 261 articles.
- data_quality_report.md: kết quả và nguồn đối chiếu.
- README.md: quy tắc sử dụng và cập nhật.

## Cấu trúc JSON đề xuất

Đây là schema đề xuất cho audit vì chưa nhận metadata_schema.json của nhóm. documents[].document_id là prefix ID dòng nguồn (L01, ND01, ND02, ND03, TT01..TT05). ND03 được giữ làm ID kế thừa dù văn bản là Nghị quyết; phải thống nhất ánh xạ nếu đổi prefix. documents[].articles[].article_id giữ nguyên ID đầu vào, bao gồm các dạng D4 và D04, để bảo toàn liên kết. Không tạo chunk_id, nội dung Điều hoặc Khoản từ metadata.

document_number là khóa số hiệu. title cấp document là trích yếu nguồn chính thức; title cấp article là tiêu đề Điều nguồn. legal_type có Luật, Nghị định, Nghị quyết, Thông tư, Thông tư liên tịch. Ngày là chuỗi ISO YYYY-MM-DD. legal_sectors là mảng nhãn. source_url cấp document là trang chính thức; URL đầu vào của từng Điều vẫn giữ ở articles[].source_url. Mỗi Điều có source_record để truy về Excel. related_documents và notes giữ nguyên chuỗi hoặc null, chưa phân tích quan hệ. Không dùng null như bằng chứng không có quan hệ.

file_paths cấp document là danh sách đường dẫn đã ghi trong metadata, chưa xác nhận tồn tại. Các Điều Nghị quyết có file_path=null vì trỏ nhầm file Nghị định; source_file_path giữ giá trị trước sửa. Các đường dẫn còn lại giữ nguyên, không tự thêm raw_data/ hoặc đổi tên dấu tiếng Việt. Thư mục gốc khi kiểm tra file phải là thư mục chứa laws_decrees/ và circulars/; không giả định tên thư mục laws_and_decrees/ tương đương.

status=unknown vì chưa xác minh hiệu lực hiện hành; source_status giữ khai báo Còn hiệu lực. verification phân biệt thuộc tính đã tra nguồn và file/nội dung chưa kiểm tra. Không dùng basic_properties=checked_official_page như xác nhận tất cả thông tin đúng hoặc đã đọc PDF ký.

## Cập nhật và bàn giao

1. Mở Danh sach loi, lọc Chưa xử lý, phân công owner và bổ sung bằng chứng. Kiểm tra raw_data trước khi đổi lỗi file thành Đã sửa.
2. Đối chiếu số Điều và URL anchor bằng toàn văn; không tự sửa 66 anchor dựa trên tiêu đề vì tiêu đề có thể sai.
3. Điền đường dẫn Nghị quyết đúng; xác minh tên người ký thông tư liên tịch từ PDF ký.
4. Kiểm tra hiệu lực hiện hành, lịch sử sửa đổi/bãi bỏ. Giữ thông tin nguồn và ngày xác minh.
5. Thống nhất schema nhóm rồi validate JSON. Nếu chỉ nhận flat array, flatten articles kết hợp document metadata, giữ cả document_id và article_id.
6. Khi nguồn thay đổi, chạy lại kiểm kê. Workbook hiện là ảnh chụp audit, không tự sinh JSON hay báo cáo từ các ô được sửa.

## Đọc JSON với Python

```python
import json
with open("normalized_metadata.json", encoding="utf-8") as f:
    data = json.load(f)
assert len(data["documents"]) == 9
assert sum(len(d["articles"]) for d in data["documents"]) == 261
for document in data["documents"]:
    for article in document["articles"]:
        print(document["document_number"], article["article_id"])
```

Chưa có raw_data nên chưa thể kết luận file gốc tồn tại, mở được hoặc đủ cấu trúc Chương/Điều/Khoản cho pipeline.
