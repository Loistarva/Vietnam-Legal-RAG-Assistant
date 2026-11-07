# Sửa F1 và bổ sung dẫn chứng F2/F3 của PR #35

Base: `e0cea35` (`fix/leftover-after-0211`). Báo cáo gốc ở PR #37.

## Thay đổi

- Tách khoản 2 Điều 2 NĐ 07/2025 theo hai Khoản được trích dẫn. Khoản nguồn vẫn là
  `clause_number = 2`; metadata mới `quoted_clause_number` phân biệt nội dung k1/k2.
- Bổ sung override kết thúc phần k1 bản 2025 từ 15/01/2026 theo khoản 1 Điều 13
  NĐ 18/2026. Phần k2, bao gồm miễn nộp giấy khi có dữ liệu điện tử, giữ nguyên.
- Tách parent để child còn hiệu lực không mở rộng sang phần k1 đã bị sửa lại.
- Bổ sung `evidence_context_ids` cho hai dẫn chứng thiếu câu dẫn bãi bỏ và bốn
  dẫn chứng có nội dung tiếp ở chunk sau. Exporter kiểm tồn tại và văn bản nguồn.
  Đây là nhóm dẫn chứng để review/truy vết, không phải thay đổi top-k retrieval.
- Không đổi trạng thái TT 30/2019 (F4); vẫn cần người phụ trách làm rõ biểu diễn
  phiên bản và xác nhận pháp lý.

## Ảnh hưởng dữ liệu

- Giữ nguyên tập ID của 2.322 child chunk. Hai chunk của khoản sửa đổi có nội dung
  phân bố lại; cùng ID không có nghĩa cùng nội dung. Không thay gold/candidate.
- Parent tăng từ 1.078 lên 1.079; parent_id của một số child trong NĐ 07/2025 đổi.
- `production_chunk_index.json` được nhập lại; hầu hết diff là hash nguồn thay đổi,
  chỉ hai dòng có nội dung luật đổi. Corpus hash mới phải dùng cho index mới.
- 29 override thay cho 28; bỏ ghi chú `not_applied` về chunk gộp đã xử lý.

## Sau khi lấy bản sửa

Dựng lại index trước khi dùng corpus mới:

```powershell
python -m retrieval.build_bm25_index --recreate
python scripts/build_index.py --recreate
```

Các kết quả retrieval và metrics đã lưu thuộc corpus cũ, không được coi là số đo
của bản sửa này. Chưa chạy Dev/Test retrieval; hash corpus trong manifest cấu hình
Test được cập nhật để chuẩn bị lần chạy mới, giữ nguyên câu hỏi/gold/cấu hình.
Cần phối hợp nhóm cho đợt đánh giá corpus mới. Không sửa các hash kết quả cũ để làm
chúng có vẻ tương thích.

`check_split.py` trên nền PR #35 có 0 lỗi, 19 cảnh báo draft sẵn có; phần xử lý
20 câu draft nằm ở PR #36, không được gộp vào thay đổi này.

## Kiểm tra

- Exporter chạy thành công, bảo toàn token nguồn, 0 ID trùng.
- 84 kiểm thử chunking, schema, hiệu lực, corpus scope, registry, reference sync
  và temporal retrieval đã qua.
- `scripts/validate_benchmark.py`: PASS, 0 lỗi.
- Kiểm biên 14/01/2026 và 15/01/2026 cho phần cũ, phần còn hiệu lực, parent và
  nội dung thay thế; kiểm nhóm evidence và fail closed khi đoạn trích không hợp lệ.
- `python -m pytest -q` toàn repo: 815 pass, 1 skip.
- Ruff trên bốn file Python thay đổi: không lỗi. `git diff --check`: không lỗi.
