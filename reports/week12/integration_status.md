# Sprint 12 — Bàn giao tích hợp cục bộ

Mốc đối chiếu là `origin/testing` tại `9821816`. Nhánh `integration/sprint12-local` được tạo trong worktree riêng. Các commit tích hợp là bằng chứng cục bộ, còn trạng thái CI, review và nghiệm thu trên GitHub cần được xác nhận theo SRS mục 10.2.

| Hạng mục | Trạng thái và bằng chứng | Owner / phần việc còn lại |
| --- | --- | --- |
| M0 — SRS/BRD | Đã tích hợp cục bộ SRS 2.1.2 và BRD 2.1.1 tại `7c9c1ac`. `origin/spec/srs-2.1.3` tại `32d09eb` có D-14 Proposed và hai sửa đổi đang chờ xác nhận. Ref công khai cho D-15 và nội dung D-13 đã duyệt chưa tìm thấy trong các nhánh spec đã đối chiếu. | Tech Lead xác nhận mục 5.5, 5.3.4, cung cấp bản ghi D-13 và quyết định D-15. |
| #59 → #63 → #61 | Đã tích hợp cục bộ tại `44d510c`, `0ccc6a1`, `9d5923a`. Giữ adapter Router của #64, đưa phần thay đổi riêng của #61 lên sau #63 và giữ trạng thái phê duyệt của SRS mục 5.6. | Dev 3/Dev 5 review và xác nhận CI trên GitHub. Xử lý #60 trên `main` theo S12-DEC-05. |
| #53 — Chấm Dev30 | Cần đối chiếu FR9.8. Commit `f4fa6c6` sửa hai tệp hiện hữu trong `evaluation/results/dev/`. | Dev 4 xác nhận các tệp thuộc lượt nào và chuyển kết quả mới sang thư mục mới nếu cần, hoặc ghi lý do đóng PR. |
| Live E2E, BO-04, BO-05 | BLOCKED. Các cổng FastAPI, Streamlit, Elasticsearch, Qdrant và Ollama mặc định không có dịch vụ lắng nghe trong môi trường kiểm tra. BO-04 và BO-05 còn phụ thuộc triển khai đợt 2 trên `testing`. | Dev 5 cung cấp môi trường và SHA `testing`; Dev 1 đo BO-04 đủ bốn nhóm; Dev 5 đo BO-05/NFR2.1 trên máy tham chiếu. |
| Test 30 và chấm mù | BLOCKED. Chưa có xác nhận S12-DEC-01 và Top-50 kèm manifest đối chiếu freeze. Lượt official còn nguyên để chạy khi đủ điều kiện. | Tech Lead khóa cấu hình; Dev 4 bàn giao Top-50; Dev 5 chạy một lượt A/B. Reviewer độc lập giữ khóa, Dev 2/4 chỉ nhận phiếu không nhãn. |
| FR3.4 / FR5.6 | Chưa nghiệm thu. FR3.4 cần xác nhận S12-DEC-03. Với FR5.6, kế hoạch liệt kê `ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES` là sửa được trong khi mapper hiện tại phân loại mã này là `CITATION_INVALID`, nhóm kế hoạch yêu cầu loại khỏi sinh lại. | Dev 1/Dev 5 đối chiếu phân loại với Tech Lead trước khi hiện thực nhánh sinh lại cho mã này. |
| FR2.11 / NFR7.3 | BLOCKED theo S12-DEC-04 và S12-DEC-05. | Dev 3/Dev 4 chờ xác nhận mục 5.6 cho FR2.11; Tech Lead chỉ định người duyệt pháp lý cho NFR7.3. |

FR4.3-AC2 đã có bản sửa Evidence Panel và bốn ca kiểm thử cục bộ tại `cfe08b7`, gồm ngày tra cứu 01/06/1995 và hai biên của khoảng hiệu lực. Bộ kiểm thử tập trung API, contract, orchestration, gateway, grounding, frontend và E2E bằng mock có 650 ca đạt, một ca bỏ qua. Bộ pytest toàn repo chạy cục bộ có 1.933 ca đạt, hai ca bỏ qua. Ruff theo cấu hình CI đạt.

NFR3.4 và NFR7.2 có marker và ghi rõ các trường hợp che nhầm, bỏ sót tại `7010363`. Kiểm tra logger và API có 15 ca đạt, gồm lỗi ghi log không làm đổi phản hồi (FR9.10-AC1). Đối chiếu sự kiện của API/CLI trên dịch vụ thật vẫn thuộc live E2E.

FR2.8 Top-10/MMR chuyển sang GĐ3 theo D-13 được ghi trong kế hoạch Sprint 12. `rerank_top_k` giữ ở 5. Ma trận truy vết chưa chuyển yêu cầu sang Done khi thiếu CI, bằng chứng live hoặc sign-off. Các mục đợt 3 còn lại chờ cổng đợt 2 theo SRS mục 9.
