# Retrieval configuration

`config.yaml` là nguồn cấu hình chung cho bước dựng BM25, bước dựng Dense, runner và evaluator. `dense.index_dir` đặt thư mục lưu trữ Qdrant; mặc định là `data/indexes`.

Quy ước đường dẫn: mọi đường dẫn tương đối khai báo trong config, bao gồm `retrieval.corpus_path`, được tính từ thư mục gốc repository, không phụ thuộc thư mục hiện tại khi gọi lệnh. Các đường dẫn truyền trực tiếp qua CLI được phân giải theo quy ước của từng script; các đường dẫn corpus override tương đối cũng tính từ repository root.

CLI arguments chỉ ghi đè cấu hình khi được truyền rõ ràng. Khi dùng override cho một lần chạy benchmark, hãy truyền cùng giá trị cho evaluator để evaluator xác nhận cấu hình trong RetrievalEnvelope.
