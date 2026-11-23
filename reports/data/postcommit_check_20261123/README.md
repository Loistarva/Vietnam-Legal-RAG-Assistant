# Kiểm tra và sửa mã băm dữ liệu

Kiểm tra commit `63223fb` ngày23/11/2026 phát hiện **25 trường parsed_json_sha256 đã cũ** so với JSON hiện tại. Replay bằng parser nguyên bản cho đủ25 văn bản cho kết quả nội dung Điều/Khoản và metadata giống hoàn toàn tệp active. Lỗi nằm ở thông tin truy vết, không phải mất nội dung luật.

Đã sửa25 mã băm theo byte UTF-8 LF đúng như tệp trong Git và đồng bộ9 tệp registry staging hiện tại. Quy định LF cho parsed JSON được ghi trong `.gitattributes` và data_contract để checkout Windows/Linux không đổi mã băm. Không sửa PDF, nội dung parsed JSON, parser, chunker, schema, test, Gold hoặc các snapshot lịch sử. Nguồn gốc và các bản lưu trước chuẩn hóa giữ nguyên byte.

Kiểm tra độc lập xác nhận **57 trường mã băm parsed hiện có** khớp artifact, cả84 tệp parsed trùng byte với Git sau chuẩn LF,84 PDF khớp manifest,4 bản lưu nguồn khớp mã băm và113 đường dẫn registry hợp lệ. Chunks, parent, scope, provision_periods, article_index, production_chunk_index và source_pdfs không đổi byte. Vẫn84 văn bản active,2.638 parent,6.144 child và32 trạng thái hiệu lực cần xác minh.

## Bằng chứng

- `parsed_hash_corrections.json`: đủ25 mã băm trước/sau và danh sách staging đã đồng bộ.
- `parser_replay.json`:25 kết quả replay, không khác chính văn hoặc metadata.
- `working_integrity.json`: kiểm tra Git/worktree, PDF, bản lưu và đường dẫn.
- `validation_summary.json`, `tests_final.log`: kiểm thử sau sửa; `ci_baseline.json`: kết quả CI cho commit được kiểm tra.

[GitHub Actions của63223fb](https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/actions/runs/45090377504) đã hoàn tất thành công trước lượt sửa này. CI cho commit sửa tiếp theo là một lần chạy riêng, không được suy từ kết quả cũ.

Metadata audit vẫn0 lỗi cấu trúc,84 cảnh báo và127 alias nhập nhằng chờ peer review. Hai script audit hiện có chưa kiểm tra đầy đủ parsed_json_sha256; kiểm tra độc lập ở lượt này bổ sung đối chiếu Git và replay. Đề nghị người phụ trách kiểm thử thêm kiểm tra checksum JSON phái sinh vào pipeline; lượt data này không đổi code hay test để thực hiện việc đó.
