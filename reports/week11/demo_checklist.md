# Checklist demo Streamlit Sprint 11

**Task:** D2.6  
**Người chạy thử:** …  
**Ngày kiểm tra:** …  
**Chế độ:** Mock nội bộ / Mock URL / API thật  
**Kết quả buổi chạy thử:** Chưa chạy

Dành 10–15 phút để một thành viên khác chạy theo [runbook](../../docs/frontend/streamlit_runbook.md). Đánh dấu ô khi đã quan sát kết quả và ghi **PASS**, **FAIL** hoặc **Chưa chạy** cho từng ca.

## Khởi động

- [ ] Mở được Streamlit theo runbook và chọn đúng chế độ phản hồi.
- [ ] Nếu dùng Mock URL, gửi `[mock:success]` và xác nhận terminal mock ghi `POST /api/v1/ask` với HTTP 200.

## Ba ca demo

| Ca | Câu nhập khi dùng mock | Kết quả mong đợi | Kết quả và ghi chú |
|---|---|---|---|
| Có căn cứ | `[mock:success]` | Hiện câu trả lời và disclaimer. Bấm `[1]` để mở đúng căn cứ trong Evidence Panel. | Chưa chạy |
| Cần làm rõ | `[mock:clarify]` | Hiện thông báo yêu cầu làm rõ và disclaimer. | Chưa chạy |
| Không đủ căn cứ | `[mock:gate_fail]` | Hiện thông báo từ chối, Grounding `FAIL` và disclaimer. Evidence Panel báo không có căn cứ, bản nháp không xuất hiện. | Chưa chạy |

## Hoàn tất

- [ ] Lưu ảnh ba ca vào [thư mục bằng chứng](screenshots/) và ghi tên ảnh vào bảng.
- [ ] Kiểm tra ảnh và log dùng để bàn giao không chứa API key hoặc dữ liệu cá nhân.
- [ ] Ghi lỗi, bước tái hiện hoặc mục chưa chạy vào cột ghi chú.

## Bằng chứng QA đã có

- [Gate FAIL qua Mock URL](screenshots/gatefail.png) cho thấy UI hiển thị thông báo từ chối.
- [Báo cáo QA Week 11](frontend_qa.md) có ảnh các ca lỗi HTTP và client timeout. Người kiểm thử đã xác nhận lịch sử chat còn sau timeout.
- Live E2E đang chờ endpoint Sprint 11 từ Dev 5.
