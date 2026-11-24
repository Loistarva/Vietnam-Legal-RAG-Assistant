# Bàn giao 3 đề xuất liên kết bằng chứng — 24/11/2026

Trạng thái: **sẵn sàng cho người phụ trách code review, chưa triển khai**. Gói bàn giao lưu trong repository; chưa có xác nhận tiếp nhận của người phụ trách. Cả ba đề xuất vẫn pending, không áp dụng vào `provision_periods.json`.

| Mã | Đề xuất chờ | Ngày kết thúc đề xuất | Vướng mắc đã tái hiện |
|---|---|---|---|
| EVIDENCE-LINK-01 | TT 11/2021 bãi bỏ Điều 7 TT 21/2011 | 11/02/2022 | Số hiệu có ở `articles[1].intro`, không ở action chunk hoặc tên Điều 2 |
| EVIDENCE-LINK-02 | Luật 85/2025 thay Điều 35, 37 BLTTDS 92/2015 | 01/07/2025 | Số hiệu có ở nguồn text/PDF; tên Điều 1 chỉ nêu tên Bộ luật; parsed chưa lưu anchor số hiệu |
| EVIDENCE-LINK-03 | Luật 81/2025 thay Điều 4 Luật 34/2024 | 01/07/2025 | Số hiệu có trong PDF; parsed chưa lưu anchor, kho chưa có extracted/cleaned text riêng |

Đây là phạm vi đề xuất cũ, chưa phải chứng nhận pháp lý hoặc override được hệ thống áp dụng. Không mở rộng sang Điều khác, thay cụm từ hoặc mọi hồ sơ chuyển tiếp.

`tickets.json` giữ nguyên đề xuất, action/context, lỗi assertion, URL/PDF/SHA-256, JSON pointer hoặc trang PDF và đoạn trích định danh. `reproduction.json` lưu fingerprint code/dữ liệu cùng 3 lỗi contract đã tái hiện.

## Việc giao người phụ trách code

1. Parser/ingest bảo toàn anchor định danh trong lời dẫn, tên Chương hoặc phần mở đầu; lưu vị trí cấu trúc/trang/offset và hash nguồn. Trường hợp 02–03 cần giữ anchor từ nguồn vào artifact truy vết được. Không thêm số hiệu vào chunk quy phạm.
2. Chủ evidence/provision validator thống nhất liên kết có kiểu giữa action chunk và anchor. Kiểm cùng `changed_by`, nguồn/hash, selector tồn tại, đúng mục tiêu và phạm vi bao chứa/tham chiếu. Không nhận chỉ vì số hiệu xuất hiện ở nơi bất kỳ trong văn bản.
3. Giữ action chunk và thứ tự context. Luật sửa nhiều luật phải có quan hệ phạm vi rõ để không gán chéo Điều. Không đổi evidence ID sang chunk chỉ tình cờ nhắc số hiệu.
4. Sau khi contract được duyệt, triển khai và test, Dev1 rà căn cứ, phạm vi, ngày rồi mới cân nhắc đưa override vào active/export. Tài liệu này không tự phê duyệt ingest.

## Tiêu chí nghiệm thu thay đổi code sau này

- Ba trường hợp xác minh được bằng anchor thật; override hiện hữu vẫn tương thích.
- Test âm phải bắt anchor sai nguồn/`changed_by`/hash/selector, anchor không tồn tại, số hiệu gần giống, target hoặc phạm vi sai.
- Số hiệu chỉ có trong trích dẫn không liên quan phải bị từ chối; luật sửa nhiều luật không gán chéo mục tiêu.
- Action phải thể hiện đúng sửa/bãi bỏ và Điều/Khoản; không đóng toàn văn bản từ một thay đổi cục bộ.
- Giữ kiểm tra ngày hiệu lực từ nguồn sửa đổi, kiểm tra trước ngày/đúng ngày kết thúc, thứ tự context và Gold.
- Chủ code bổ sung test dương/âm cho contract mới. Dev1 không sửa test, chữ nguồn hoặc tạo evidence chunk giả để vượt kiểm tra.

## Tái hiện read-only

Chạy đoạn Python từ thư mục repository với dependencies dự án:

```python
import json
from pathlib import Path
from chunking.provision_periods import _parse_override
from test.test_provision_periods import test_override_has_evidence_in_corpus

path = Path("reports/data/evidence_link_handoff_20261124/tickets.json")
for ticket in json.loads(path.read_text(encoding="utf-8")):
    try:
        test_override_has_evidence_in_corpus(
            _parse_override(ticket["original_proposal"])
        )
    except AssertionError as error:
        assert str(error) == ticket["current_contract"]["failure"]
        print(ticket["ticket_id"], "EXPECTED CONTRACT BLOCK:", error)
    else:
        raise AssertionError("Contract đã thay đổi; cần review lại gói bàn giao")
```

Đoạn trên chỉ đọc đề xuất vào bộ nhớ. Ba lỗi mong đợi không phải suite regression thất bại: các đề xuất chưa được nạp vào override production.

```powershell
python -m pytest test/test_provision_periods.py test/test_document_aliases.py -q
python scripts/audit_document_metadata.py
```

Kết quả: **132 test pass**, metadata audit **0 lỗi** (giữ 85 cảnh báo và 131 alias nhập nhằng); 3 lỗi contract được tái hiện đúng kỳ vọng. Đã kiểm tra trực quan PDF Luật 81/2025 trang 1: lời dẫn nêu số 34/2024/QH15, ngay trước Điều 1. Fingerprint các đầu vào không đổi. Chi tiết trong `validation.json`. Những nhóm việc khác của [bàn giao trước](../provision_review_20261123/technical_handoff.json) vẫn giữ riêng.
