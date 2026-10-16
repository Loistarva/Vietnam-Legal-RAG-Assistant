# Dữ liệu đánh giá truy xuất

`queries_dev.json` chứa 14 câu hỏi Dev hiện có cùng nhãn `relevant_chunk_ids`.
`ground_truth.json` là bản tách riêng các nhãn từ chính bộ Dev đó.
Hiện chưa có `queries_test.json` độc lập; không dùng số đo Dev làm kết quả kiểm thử cuối.
Corpus fixture hiện vẫn nằm tại `embedding/data/han_gia_dinh_smoke_chunks.json` để các pipeline hiện tại tiếp tục hoạt động.
