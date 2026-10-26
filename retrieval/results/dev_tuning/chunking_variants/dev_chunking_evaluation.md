# Dev: đánh giá kích thước chunk

- Ngày chạy: 2026-10-26
- Số query Dev có nhãn chunk đối chiếu được: 267
- Nguồn nhãn: `data\benchmark\gold_id_proposals_300.json`; Test không được dùng.
- Dense model: `bkai-foundation-models/vietnamese-bi-encoder`; RRF k=60; candidate Top-50.
- Với mỗi chunking, trọng số được chọn trên Dev từ cùng lưới 21 tỉ lệ BM25/Dense, bước 5%.
- Fallback overlap 40 từ được giữ cố định trong cả bốn phương án; chỉ áp dụng cho nhánh tách fallback window, không được tune riêng.
- Nhãn B/C/E được chuyển theo đoạn text liên tiếp trong cùng `clause_id`; không sửa file proposal gốc.
- Latency của E được đo lại riêng trên Dev ở đúng trọng số đã chọn 0,35/0,65. Latency A/B/C lấy từ lượt truy xuất trước ở 0,65/0,35. Metric Hybrid từng phương án được tính lại offline trên cùng Top-50 BM25/Dense bằng trọng số Dev đã chọn.

## Kết quả

| Chunking | Parent chars | Child tokens / words | Số chunks | BM25/Dense | BM25 Recall@5 | Dense Recall@5 | Hybrid Recall@5 | Hybrid MRR@5 | Embed >256 | Latency retrieval (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 1500 | 256 / 200 | 2011 | 0.45 / 0.55 | 0.7466 | 0.7591 | 0.8196 | 0.6459 | 40/2011 (1.99%) | 310.6 |
| B | 800 | 128 / 100 | 2655 | 0.45 / 0.55 | 0.7179 | 0.7266 | 0.7959 | 0.6069 | 5/2655 (0.19%) | 381.2 |
| C | 2500 | 512 / 350 | 1906 | 0.30 / 0.70 | 0.7541 | 0.7647 | 0.8227 | 0.6463 | 86/1906 (4.51%) | 284.8 |
| E | 1500 | 256 / 350 | 1923 | 0.35 / 0.65 | 0.7503 | 0.7647 | 0.8246 | 0.6521 | 74/1923 (3.85%) | 172.2 |

Theo tiêu chí Recall@5 (MRR@5 dùng để phân xử khi bằng nhau), cấu hình Dev được chọn là **E** với BM25/Dense=0.35/0.65: Recall@5=0.8246, MRR@5=0.6521.

## Cách đọc kết quả

Config A được sinh lại và khớp toàn bộ ID cùng text với corpus/index hiện hành. Với B/C/E, một nhãn chunk gốc được ánh xạ sang chunk mới nếu text của chunk mới là đoạn liên tiếp nằm trong chunk gốc hoặc chunk mới chứa toàn bộ đoạn của chunk gốc; điều kiện clause_id phải trùng. Các nhãn `version_*` không thuộc corpus chunk nên bị loại khỏi metric.

Tokenizer `bkai-foundation-models/vietnamese-bi-encoder` có giới hạn 256 token. Chunk dài hơn giới hạn sẽ bị cắt khi embed; số lượng bị ảnh hưởng có trong bảng. Nhãn proposal còn provisional; đây là tuning trên Dev, không phải đánh giá pháp lý độc lập. Kích thước danh sách relevant thay đổi khi chunk bị tách hoặc gộp.

Tại thời điểm tuning Dev, kết quả Test có sẵn là Config A cùng RRF 1:1; không dùng điểm đó để chọn cấu hình. Sau khi khóa E, một lượt đánh giá lại đã chạy trên cùng Test. Xem `retrieval/results/test_run/config_e_final/test_config_e_report.md`; lượt sau này không được xem là một Test độc lập mới.

## Tệp tái lập

- Bản JSON đầy đủ: `retrieval\results\dev_tuning\chunking_variants\dev_chunking_evaluation.json`
- Ánh xạ nhãn theo chunking: `retrieval\results\dev_tuning\chunking_variants\label_mapping.json`
- Corpus/index riêng A, B, C, E: thư mục cùng tên trong `chunking_variants/`.
