# Vietnam Legal RAG Assistant

Dự án RAG hỗ trợ truy xuất và hỏi đáp trên văn bản pháp luật Việt Nam.

- Kiến trúc, parser và chunking hiện có được giữ nguyên.
- Hướng dẫn bố cục repo: `docs/sprint6_integration.md`.
- Hướng dẫn chạy BM25 Elasticsearch, Dense Qdrant và Hybrid RRF: `retrieval/retrieval.md`.
- Báo cáo đánh giá gần nhất: `retrieval/results/retrieval_report.md`.

Lưu ý: số liệu retrieval hiện tại được đo trên bộ smoke test 321 chunk, 14 câu hỏi Dev và một văn bản; chưa phải đánh giá trên corpus lớn hoặc bộ Test độc lập.
