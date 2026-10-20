# Vietnam Legal RAG Assistant

Dự án RAG hỗ trợ truy xuất và hỏi đáp trên văn bản pháp luật Việt Nam.

- Kiến trúc, parser và chunking hiện có được giữ nguyên.
- Hướng dẫn bố cục repo: `docs/sprint6_integration.md`.
- Hướng dẫn triển khai và chạy Retrieval của Dev 4: `retrieval/retrieval.md`.
- Báo cáo Task 4: `docs/retrieval_report.md`.

Task 4 đã được chạy lại trên 285 câu Dev với corpus hiện tại gồm 1.159 chunk và `gold_id_proposals_300.json` làm nhãn tạm. Hybrid dẫn đầu ở metric chunk-level (Recall@10 0.7407); Dense dẫn đầu ở metric article-level (Recall@10 0.7846). Kết quả vẫn mang tính thử nghiệm vì phần lớn nhãn proposal chưa được xác minh. Xem [báo cáo Task 4](docs/retrieval_report.md).


