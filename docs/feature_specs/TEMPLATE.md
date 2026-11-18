# Feature spec: <tên khối>

> Mẫu cho yêu cầu GĐ3 (SRS mục 11). Chép file này thành `docs/feature_specs/<mã-khối>-<tên-ngắn>.md`, ví dụ `FR2.9-semantic-cache.md`. Xóa các dòng hướng dẫn trong dấu `>` khi viết xong.

| Thuộc tính | Giá trị |
| --- | --- |
| Yêu cầu SRS | <mã, ví dụ FR2.9, NFR2.2> |
| Khối trên sơ đồ | <tên khối trong `architecture/system_architecture.drawio`> |
| Người viết | |
| Người duyệt | Tech Lead |
| Trạng thái | Draft · Approved · Done |
| Sprint dự kiến | |

## 1. Mục tiêu

> Một đoạn: khối này giải quyết vấn đề gì cho người dùng hoặc hệ thống, gắn với mục tiêu nào của BRD (BO-xx).

## 2. Phạm vi

- **Làm:** …
- **Không làm:** …

## 3. Thiết kế ngắn

> Luồng dữ liệu vào/ra, thành phần mới, chỗ nối với pipeline hiện có. Ghi rõ interface (SRS mục 5.5) và contract (SRS mục 5.2) bị ảnh hưởng. Nếu cần sửa contract thì ghi `schema_version` mới.

## 4. Tham số

| Tham số | Giá trị mặc định | File cấu hình | Lý do chọn |
| --- | --- | --- | --- |
| | | | |

## 5. Tiêu chí chấp nhận

> Mỗi yêu cầu SRS ở bảng đầu cần ít nhất một tiêu chí. Viết dạng Given/When/Then, có số cụ thể, test được.

- **<mã>-AC1** Given …, When …, Then …
- **<mã>-AC2** …

## 6. Cách đo

| Chỉ số | Tập dữ liệu | Cách tính | Ngưỡng đạt |
| --- | --- | --- | --- |
| | | | |

> Không dùng tập Test để chỉnh tham số. Ghi máy chạy nếu đo latency.

## 7. Ảnh hưởng tới phần đã có

- KPI có thể bị ảnh hưởng: …
- Yêu cầu GĐ1–GĐ2 cần chạy lại kiểm tra: …
- Cần xóa cache hoặc đánh chỉ mục lại: có / không

## 8. Rủi ro

| Rủi ro | Biện pháp |
| --- | --- |
| | |

## 9. Quyết định cần chốt

| Câu hỏi | Phương án đề xuất | Kết quả |
| --- | --- | --- |
| | | |

## 10. Bằng chứng khi xong

> Điền khi khối hoàn thành: file test, artifact, commit. Ma trận truy vết trỏ tới mục này.
