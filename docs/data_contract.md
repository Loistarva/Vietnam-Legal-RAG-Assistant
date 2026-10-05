# Hợp đồng Dữ liệu Hệ thống Legal AI RAG

Tài liệu này quy định cấu trúc dữ liệu bắt buộc (Data Contract) đầu ra từ module Parser và đầu vào cho module Chunking & Embedding.

## 1. Quy ước Định danh (ID Convention)
Hệ thống sử dụng Semantic ID để đảm bảo tính duy nhất và khả năng truy vết:
* **Document ID:** `[loại_văn_bản]_[số_hiệu]_[năm]` (VD: `nd_100_2019_nd_cp`)
* **Article ID:** `[document_id]_art_[số_điều]` (VD: `nd_100_2019_nd_cp_art_6`)
* **Chunk ID:** `[article_id]_chunk_[số_khoản]_[điểm]` (VD: `nd_100_2019_nd_cp_art_6_chunk_2_c`)

## 2. Cấu trúc Đối tượng (Entities)
Tất cả các tệp JSON truyền giữa các module phải tuân thủ hệ thống phân cấp sau:

| Thực thể | Mô tả | Yêu cầu bắt buộc |
| :--- | :--- | :--- |
| **Document** | Đối tượng cao nhất đại diện cho một văn bản luật nguyên bản. | `document_id`, `document_metadata`, `articles` |
| **Metadata** | Siêu dữ liệu để phục vụ bộ lọc (Pre-filter) của Vector DB. | `title`, `document_type`, `issue_date`, `effective_date`, `validity_status` |
| **Article** | Các Điều luật chứa bên trong Document. | `article_id`, `article_number`, `chunks` |
| **Chunk** | Đơn vị nhỏ nhất (Khoản, Điểm) để đưa vào mô hình Embedding. | `chunk_id`, `text`, `parent_id` |

## 3. Quy định xử lý ngoại lệ
* Nếu Khoản/Điểm không thể bóc tách, toàn bộ nội dung Điều luật được lưu ở cấp độ một Chunk duy nhất với `chunk_id` bằng `article_id_chunk_0`.
* Văn bản hết hiệu lực bắt buộc phải có `validity_status = "Hết hiệu lực"` và không được đưa vào Vector DB trừ khi có yêu cầu tra cứu lịch sử đặc biệt.