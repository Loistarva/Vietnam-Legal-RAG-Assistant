# Corpus v3 — kết quả chuẩn hóa danh sách đã lọc

Trong 34 ứng viên (đợt đề xuất khoảng 30), 5 văn bản trực tiếp về HNGĐ được chuẩn bị; 29 ứng viên còn lại không được đưa vào pipeline ở lần này. Không nhận toàn văn hỗn hợp hoặc tài liệu thuần quản lý chỉ để đủ số lượng.

PDF của 5 văn bản đã qua cleaner/parser/schema hiện tại, token roundtrip không đổi, không cần OCR. Bốn văn bản đã cập nhật vào raw_data, metadata và các đầu ra parse; tổng registry/parser/raw PDF đang hoạt động là 61. NĐ69/2006 đã chuẩn hóa nhưng ở hold, không xuất hiện trong đầu vào mặc định.

| Văn bản | Điều | Trạng thái |
|---|---:|---|
| NĐ24/2013/NĐ-CP | 45 | Đã thêm; văn bản lịch sử. Các Điều ngoài 3,5,44 hết hiệu lực từ 15/02/2015 theo NĐ126/2014; phần còn lại kết thúc 01/01/2016 theo NĐ123/2015. |
| TT22/2013/TT-BTP | 19 | Đã thêm; hết hiệu lực từ 10/04/2015 theo Điều17 TT02a/2015. |
| TT16/2010/TT-BTP | 10 | Đã thêm; hết hiệu lực từ 10/04/2015 theo Điều17 TT02a/2015. Phụ lục được giữ ở nguồn và sidecar, không khai là đã index biểu mẫu. |
| TTLT03/2016/TTLT-BTP-BNG-BCA-BLĐTBXH | 22 | Đã thêm; không tự khẳng định tình trạng hiệu lực mới nhất. |
| NĐ69/2006/NĐ-CP | 3 | PDF và parse kỹ thuật PASS, đang hold do cần đối chiếu dẫn chiếu/phạm vi bãi bỏ cấp Khoản. |

## Chuẩn đầu vào

- Letter 612×792 pt, Times New Roman 12 pt, chữ native; không thay đổi code cleaner/parser/chunker/schema.
- Bản gốc Công báo/Word/ZIP và HTML metadata được lưu riêng trong data/source_pdfs/corpus_v3 và data/source_documents/corpus_v3, kèm URL và SHA-256.
- NĐ69: chuẩn hóa dấu phân cách nhãn Điều bên trong đoạn trích để parser hiện tại nhận đúng Khoản; không đổi chữ/số. Vì đang hold, bản này không vào mặc định.
- Chữ ký/phụ lục ngoài cấu trúc parser được bảo toàn trong bản gốc và annex_and_terminal_text, không xóa khỏi nguồn.
- Đây là chuẩn bị dữ liệu trên nhánh trial; chưa re-index ES/Qdrant hoặc chạy lại A/B official. Hiệu lực cấp Khoản chưa rà soát đầy đủ không được coi là đã được duyệt pháp lý.

Xem scope_review.json để biết quyết định từng ứng viên và reports/data/corpus_v3 để xem bằng chứng kiểm tra.
