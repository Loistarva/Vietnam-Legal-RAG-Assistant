# QA frontend Sprint 11

**Ngày kiểm tra:** 26/11/2026  
**Task:** D2.5  
**Môi trường:** Streamlit Demo (mock) gọi HTTP POST đến `http://127.0.0.1:8001/api/v1/ask`.

## Kết quả kiểm tra

| Ca kiểm thử | Mã HTTP | Kết quả và bằng chứng |
|---|---:|---|
| `[mock:http401]` | 401 | **PASS.** UI hiển thị thông báo lỗi gọi API và disclaimer. [Ảnh 401/422](screenshots/401_422_error.png) |
| `[mock:http422]` | 422 | **PASS.** UI hiển thị thông báo lỗi và đoạn hội thoại trước đó vẫn còn. [Ảnh 401/422](screenshots/401_422_error.png) |
| `[mock:error]` | 500 | **PASS.** UI báo hệ thống đang bận, hiển thị disclaimer và Evidence Panel báo không có căn cứ. [Ảnh HTTP 500](screenshots/error.png) |
| `[mock:http503]` | 503 | **PASS.** UI hiển thị “API gặp lỗi” và thông báo “Mô phỏng Qwen không kết nối được.”, kèm disclaimer và Evidence Panel báo không có căn cứ. [Ảnh HTTP 503](screenshots/http503.png) |
| `[mock:timeout]` | 504 | **PASS.** UI hiển thị “Mô phỏng Qwen timeout.”, disclaimer và Evidence Panel báo không có căn cứ. [Ảnh HTTP 504](screenshots/timeout.png) |
| `[mock:network_timeout]` | — | **PASS.** UI báo API phản hồi quá chậm. Người kiểm thử xác nhận lịch sử chat vẫn còn trong cùng phiên Streamlit. [Ảnh client timeout](screenshots/network_timeout.png) |
| `[mock:gate_fail]` | 200 | **PASS với mock.** Phản hồi có `status=ABSTAIN`, `grounding_status=FAIL` và `answer` rỗng. UI hiển thị thông báo từ chối và Evidence Panel báo không có căn cứ. Việc backend thật loại bỏ bản nháp sẽ được kiểm tra trong live E2E. [Ảnh Gate FAIL](screenshots/gatefail.png) |

UI hiện dùng cùng một thông báo chung cho 401 và 422. Mã HTTP trong bảng được kiểm tra riêng tại endpoint mock.

Các ảnh bằng chứng không hiển thị giá trị API key. Chế độ Demo không gửi API key, nên kiểm tra UI và log với key thử trong chế độ API vẫn chưa thực hiện.

## Kiểm tra điểm trích dẫn trên UI

Hai ca dưới đây được chạy ở chế độ **Demo (mock)** nội bộ.

| Ca kiểm thử | Kết quả | Bằng chứng |
|---|---|---|
| `[mock:success]` với `point_ref` | **PASS.** Evidence Panel hiển thị **Điểm a** sau điều và khoản, đồng thời hiển thị điểm trong đường dẫn căn cứ. | [Ảnh có điểm](screenshots/success-point-ref.png) |
| `[mock:long_evidence]` với `point_ref: null` | **PASS.** Evidence Panel hiển thị điều và khoản, không có nhãn điểm rỗng. Nội dung dài hiển thị trong vùng cuộn. | [Ảnh căn cứ dài](screenshots/long-evidence-no-point-ref.png) |

## Cách chạy lại

Khởi động mock server từ thư mục gốc repo.

```powershell
.\.venv\Scripts\python.exe -m frontend.mock_server
```

Trong PowerShell khác, cấu hình Mock URL và chạy Streamlit.

```powershell
$env:LEGAL_RAG_MOCK_URL = "http://127.0.0.1:8001/api/v1/ask"
.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

Chọn **Demo (mock)**. Gửi từng marker trong bảng và đối chiếu mã HTTP ở terminal mock. Với client timeout, gửi `[mock:success]` trước, sau đó gửi `[mock:network_timeout]` trong cùng phiên và kiểm tra câu trả lời trước đó vẫn hiển thị.

## Test tự động và live E2E

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider test/frontend
```

**Kết quả test frontend:** 19 passed.

**Live E2E:** Chờ endpoint Sprint 11 từ Dev 5. Khi có endpoint, xác nhận ít nhất một ca pháp lý có Grounding Gate PASS và một ca `ABSTAIN` hoặc `NEEDS_CLARIFICATION`. Lưu ảnh và `query_id` cho từng ca.
