# Sprint 11 grounding test data

Dev 1 tạo18 case synthetic phục vụ regression cấu trúc citation và khoảng ngày. Canonical dataset: `evaluation/quality/grounding_cases_sprint11.jsonl`; base context: `test/fixtures/grounding/sprint11/base_context.json`; test runner: `test/grounding/test_sprint11_regression.py`.

Mỗi record có ID riêng, query synthetic, category, mutation, expected_status, expected_code, origin và mục đích. Các ID/content của evidence đều được sáng tác cho test, không giả làm căn cứ pháp luật thật. `semantic_assessment=not_performed`; expected codes chỉ là kết quả kỹ thuật, không phải nhãn human hallucination.

Các nhóm gồm mapping hợp lệ, đầu/cuối khoảng ngày, ngày lịch sử, nguồn chưa/hết hiệu lực, evidence/citation rỗng, index sai/trùng/ngoài context/không liên tục, provenance sai, metadata ngày không khớp và input ngày lỗi. Bộ test logging riêng dùng metadata và secret giả để kiểm tra redaction, không thêm tình huống pháp luật thật.

`grounding_fixture_overlap.json` ghi commit/path/SHA và số record của13 input snapshots benchmark, negative set và Router holdout từ `origin/testing` và nhánh Dev 4. Không có trùng ID hoặc query sau chuẩn hóa. Đây là kiểm tra trùng chính xác, không phải chứng nhận độc lập ngữ nghĩa, duyệt nhãn holdout hoặc kết quả Router. Không dự đoán hoặc tuning trên holdout.

Reviewer có thể kiểm tra mẫu theo expected code và chạy pytest. Nhãn fixture vẫn cần peer review khi nhận PR; không sửa Dev Gold, negative set, official A/B outputs hoặc corpus.
