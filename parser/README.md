A.Các thư viện cần cài đặt trên máy để có thể chạy praser
1.pdfplumber: mở terminal ,gõ lệnh pip install pdfplumber
2.pip install pytest
3.pip install pydantic
B.Luồng dữ liệu
1.Chạy parser: chạy từ file test_parser.py
2.luồng xử lý của test_parser

    -Gọi các hàm trong cleaner.py để trích xuất từ file PDF thành file txt, lưu vào thư mục cleanned_texts
    -Gọi các hàm trong parser.py để xử lý các file txt trong cleanned_texts thành các file json, luu vào thư mục parsed_json
C.Lưu ý và cải tiến code trong tương lai
- Để tránh việc sửa schema trong thư mục test ảnh hưởng đến code file praser.py nên trong file parser vẫn có phần viết định nghĩa 4 schema của document, article,chunk, metadata(dựa trên bản schema_test ngày 5/10). Khi nào thống nhất schema sẽ tối ưu lại để lấy schema trực tiếp từ thư mục lưu schema nếu muốn