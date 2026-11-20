# Hướng dẫn cho AI viết code trong repo này

File này dành cho trợ lý AI (Claude Code, Codex, Copilot, Cursor…) và cho người giao việc cho AI. Đọc hết trước khi sửa code.

## 1. Nguồn sự thật

Theo thứ tự ưu tiên:

1. [`docs/SRS.md`](docs/SRS.md): yêu cầu, tiêu chí chấp nhận, contract, quyết định. Là nguồn yêu cầu duy nhất.
2. [`schemas/models.py`](schemas/models.py): contract dữ liệu (Pydantic), phiên bản hiện hành ghi ở `SCHEMA_VERSION`.
3. [`architecture/system_architecture.drawio`](architecture/system_architecture.drawio): phần Retrieval và Knowledge Base là bắt buộc; phần khác là kiến trúc mục tiêu, SRS làm rõ.
4. [`docs/BRD.md`](docs/BRD.md): mục tiêu, KPI, quy tắc nghiệp vụ.
5. [`docs/requirements_traceability.md`](docs/requirements_traceability.md): đã làm tới đâu và số đo hiện tại.

**Không dùng làm căn cứ** (cũ, đã bị SRS thay thế): `docs/architecture_description.docx`, `docs/module_interfaces.docx`, `docs/integration_test.md`, các file `docs/sprint6_*`, các file `*.schema.json` ở gốc `schemas/`. Số liệu trong `README.md` có thể cũ; số hiện tại nằm ở ma trận truy vết.

## 2. Trước khi code

1. Tìm mã yêu cầu trong SRS (`FRn.m`, `IRn.m`, `NFRn.m`) cho việc được giao. Không có mã thì dừng và hỏi người giao việc.
2. Kiểm tra yêu cầu đạt Definition of Ready (SRS mục 10.1). Yêu cầu ở trạng thái `Proposed` hoặc bị một quyết định "Chờ Tech Lead duyệt" chặn (SRS mục 8) thì **chưa được code**.
3. Đọc tiêu chí chấp nhận `<mã>-ACk`. Code xong khi mọi tiêu chí có test pass.
4. Đặt code đúng thư mục theo SRS mục 2.3 (Vị trí code). Không tạo module mới cho một khối đã có chỗ.
5. SRS sai, thiếu hoặc mâu thuẫn với code: dừng phần đó, báo lại cho người giao việc kèm mã yêu cầu. Không tự diễn giải rồi code (SRS mục 12.1).

## 3. Không được làm

- Sửa `schemas/models.py` hoặc `schemas/generated/` khi việc được giao không phải thay đổi contract đã duyệt ở SRS mục 5.6. Chỉ owner contract sửa các file này.
- Đọc hoặc chạy tập Test để chỉnh tham số, prompt, ngưỡng hay router: `data/benchmark/queries_test.json`, phần Test của Gold, `docs/test_questions_freeze.json`, `docs/test_gold_freeze.json`.
- Đổi file cấu hình đã khóa trong `docs/test_run_config_freeze.json` (corpus, `retrieval/config.yaml`, `reranking/config.yaml`) mà không theo quy tắc ở SRS mục 12.1.
- Sửa hoặc ghi đè kết quả lượt chạy cũ trong `evaluation/results/` (FR9.8). Lượt chạy mới ghi vào thư mục mới.
- Đổi nội dung prompt mà không tăng phiên bản prompt (FR4.6).
- Commit secret, API key, `.env`, file model, `__pycache__`, `.pyc`.
- Thêm tính năng ở SRS mục 11.1 (Chưa nhận vào phạm vi) hoặc tính năng không có mã yêu cầu.
- Sửa code thuộc phân hệ khác phân hệ được giao. Lỗi ở phân hệ khác thì báo lại.

## 4. Những chỗ dễ sai

- **Hai lớp `RouteDecision`.** `agent.router.rule_router.RouteDecision` là lớp nội bộ của router; `schemas.models.RouteDecision` là contract. Ngoài `agent/router/` chỉ dùng lớp contract (SRS mục 5.3.3).
- **Mã chi tiết và `error_code`.** Pipeline dùng mã chi tiết (`EMPTY_RETRIEVAL`, `LLM_OUTPUT_TRUNCATED`…); `AskResponse.error_code` dùng mã nhóm (`RETRIEVAL_EMPTY`, `JSON_INVALID`…). Chuyển theo bảng ở SRS mục 5.3.5.
- **`validity_status` là tĩnh.** Đó là tình trạng hiện nay của văn bản, không phải tại `as_of_date`. Hiệu lực tại `as_of_date` tính từ `effective_from` / `effective_to` (`retrieval/temporal.py`, FR4.3).
- **Khoảng hiệu lực nửa mở.** `effective_from ≤ as_of_date < effective_to`; `effective_to` rỗng là chưa hết hiệu lực (FR2.4).
- **Tối đa 5 evidence.** `EvidenceItem.evidence_index` và `StructuredRAGOutput.evidence_indices` có `le=5`; tăng quá 5 là thay đổi contract.
- **Mọi câu trả lời đi qua Gate.** Không trả nội dung model cho người dùng trước khi Grounding Gate kết luận, kể cả khi stream (FR5.1).
- **Disclaimer đúng một lần** ở mọi phản hồi (FR5.8).
- **Hash có chuẩn hóa xuống dòng.** SHA-256 của corpus và cấu hình tính sau khi đổi CRLF thành LF (FR8.9); repo chạy cả trên Windows và Linux.
- **Không tự điền 0** cho thời gian hoặc token mà runtime không trả về; để `null` (FR6.6).

## 5. Test

- Chạy toàn bộ: `python -m pytest` (thư mục trong `pytest.ini`: `parser`, `test`, `retrieval/test`).
- Lint như CI: `python -m ruff check --select E9,F63,F7,F82 .`; quy tắc đầy đủ trong `ruff.toml`.
- Test chạy được khi không có Elasticsearch, Qdrant và model: dùng mock của interface (SRS mục 5.5, NFR6.3). CI đặt `HF_HUB_OFFLINE=1`, không tải model.
- Test mới gắn mã tiêu chí: `@pytest.mark.req("FR5.7-AC1")`. Marker `req` được đăng ký trong `pytest.ini` ở đợt 0 (SRS mục 9); trước đó pytest chỉ cảnh báo.
- Test đặt trong `test/<phân hệ>/`, đặt tên theo hành vi được kiểm.

## 6. Dịch vụ cho lượt chạy thật

- Elasticsearch, Qdrant server: [`docs/operations/qdrant_server.md`](docs/operations/qdrant_server.md), [`deployment/qdrant/`](deployment/qdrant/).
- Ollama và model local: [`docs/operations/ollama.md`](docs/operations/ollama.md).
- Lượt chạy official: working tree sạch, temperature 0, tắt cache, khóa fallback (NFR4.1); manifest ghi đủ khóa ở NFR4.2.

## 7. Khi mở PR

- Mô tả PR ghi các mã yêu cầu được hiện thực và tiêu chí chấp nhận đã có test.
- Hành vi khác SRS thì PR sửa SRS đi trước, Tech Lead duyệt, rồi mới tới PR code (SRS mục 12.2).
- Cập nhật ma trận truy vết khi một yêu cầu đổi trạng thái (Definition of Done, SRS mục 10.2).
