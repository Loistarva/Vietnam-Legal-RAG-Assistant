# Hướng dẫn chạy Streamlit

Chạy các lệnh PowerShell dưới đây từ thư mục gốc repository. Dự án dùng Python 3.12. Nếu chưa có môi trường ảo, tạo môi trường và cài các gói cần cho frontend.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install 'streamlit>=1.40,<2' 'requests>=2.31' 'pydantic>=2,<3'
```

Nếu repo đã có `.venv` với các gói trên, có thể dùng luôn. Lệnh chạy frontend sẽ in địa chỉ để mở trên trình duyệt, mặc định là `http://localhost:8501`.

## Demo với mock nội bộ

```powershell
Remove-Item Env:LEGAL_RAG_MOCK_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

Trong thanh bên, chọn **Demo (mock)**. Có thể chạy chế độ này khi chưa có API Sprint 11.

## Demo với Mock URL

Trong terminal thứ nhất, khởi động mock server và giữ terminal mở.

```powershell
.\.venv\Scripts\python.exe -m frontend.mock_server
```

Trong terminal thứ hai, đặt Mock URL và chạy Streamlit.

```powershell
$env:LEGAL_RAG_MOCK_URL = "http://127.0.0.1:8001/api/v1/ask"
.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

Chọn **Demo (mock)** và gửi `[mock:success]`. Terminal mock server sẽ ghi `POST /api/v1/ask` với mã HTTP 200.

## Demo với API thật

Lấy endpoint `/api/v1/ask` và key test từ Dev 5. Đặt biến trong terminal dùng để chạy Streamlit. Dùng `LEGAL_RAG_LOCAL_API_URL` cho **API → Local** hoặc `LEGAL_RAG_API_URL` cho **API → Cloud**.

```powershell
$env:LEGAL_RAG_LOCAL_API_URL = "http://127.0.0.1:8000/api/v1/ask"

# Nhập key test nếu endpoint yêu cầu.
$env:LEGAL_RAG_API_KEY = [System.Net.NetworkCredential]::new(
    "", (Read-Host "API key test" -AsSecureString)
).Password

.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

Giữ key trong biến môi trường của terminal. Khi kết thúc, đóng terminal hoặc chạy `Remove-Item Env:LEGAL_RAG_API_KEY -ErrorAction SilentlyContinue`. Khi lưu ảnh demo hoặc chia sẻ log, kiểm tra ảnh và log không chứa key hay dữ liệu cá nhân.

## Kịch bản demo

| Ca | Nội dung gửi trong Demo (mock) | Kết quả cần quan sát |
|---|---|---|
| Có căn cứ | `[mock:success]` | Có câu trả lời và disclaimer. Bấm citation `[1]` để mở căn cứ tương ứng. |
| Cần làm rõ | `[mock:clarify]` | Có thông báo yêu cầu làm rõ. |
| Không đủ căn cứ | `[mock:gate_fail]` | Grounding `FAIL`, UI hiển thị thông báo từ chối và Evidence Panel báo không có căn cứ. |

Để demo ngày hiệu lực, bật **Tự chọn ngày tra cứu**, chọn ngày và gửi lại ca có căn cứ. Kiểm tra ngày và nguồn ngày hiển thị trên phản hồi.

## Phiên chat và lỗi thường gặp

- Lịch sử được giữ trong phiên Streamlit hiện tại. Tải lại trang hoặc khởi động lại app có thể tạo phiên mới.
- Timeout HTTP mặc định là 180 giây và chỉnh được qua `LEGAL_RAG_REQUEST_TIMEOUT_SECONDS`. Trong Mock URL, riêng câu `[mock:network_timeout]` dùng giới hạn 1 giây để kiểm tra thông báo timeout và việc giữ lịch sử.
- Nếu Demo không có request trong terminal mock, kiểm tra `LEGAL_RAG_MOCK_URL` trong terminal đã khởi động Streamlit. Sau khi đổi biến môi trường, khởi động lại Streamlit và gửi lại câu thử.
- Nếu các marker HTTP như `[mock:http401]` trả phản hồi thành công mặc định, kiểm tra chế độ Mock URL và khởi động lại mock server để nạp phiên bản hiện tại.

Xem [báo cáo QA Week 11](../../reports/week11/frontend_qa.md) để chạy thêm các ca HTTP 401/422/500/503/504 và đối chiếu ảnh bằng chứng.
