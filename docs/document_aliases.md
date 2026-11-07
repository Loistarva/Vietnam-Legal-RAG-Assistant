# D1.1 — Bàn giao document aliases cho citation parser

Ngày thực hiện: **07/11/2026**. Nhánh chung: `feature/week09-dev1-planning`. Trạng thái: **pending_peer_review** bởi Dev 2 + Dev 3.

## Files và nguồn chuẩn

- `data/reference/document_versions.json`: nguồn canonical ID/số hiệu/title/type/date; không sửa trong D1.1 vì audit chưa có bằng chứng cần chỉnh registry.
- `data/reference/document_aliases.json`: artifact `document_aliases_v1`, sinh từ registry; chứa normalization version, hash canonical của registry, metadata văn bản và alias → danh sách ứng viên.
- `evaluation/document_aliases.py`: builder, loader và exact-span resolver cho Dev 2 dùng. Không triển khai citation parser hoặc metrics của Dev 2.
- `scripts/audit_document_metadata.py`: audit doc/corpus/article metadata, sinh alias map và báo cáo bằng cờ `--write`. Mặc định kiểm tra read-only.
- `reports/data/metadata_audit_20261103.md`: giữ tên file theo kế hoạch, header ghi đúng ngày audit 07/11; evidence JSON là `metadata_audit_20261107.json`.

Không tạo schema runtime song song `schemas/models.py` của Dev 3. Đây là định dạng artifact tra cứu, không thay thế ContextPayload/LLMResponse.

## API và sample

```python
from evaluation.document_aliases import load_alias_map, resolve_document_alias

aliases = load_alias_map()

resolve_document_alias("Luật HNGĐ 2014", aliases)
# {"status": "resolved", "normalized_alias": "luat hngd 2014",
#  "document_id": "l_52_2014_qh13", "candidates": ["l_52_2014_qh13"]}

resolve_document_alias("Luật HNGĐ", aliases)
# status="ambiguous", document_id=None, candidates chứa luật 1986/2000/2014

resolve_document_alias("Luật HNGĐ", aliases, year=2000)
# resolved -> l_22_2000_qh10, kể cả văn bản đã hết hiệu lực: đây là tra identity

resolve_document_alias("2019", aliases)
# status="insufficient_context", document_id=None; năm đứng riêng không là citation

resolve_document_alias("52/2014/QH12", aliases)
# status="not_found"; không bỏ authority sai để ép khớp 52/2014/QH13
```

Status gồm `resolved`, `ambiguous`, `not_found`, `insufficient_context`. Chỉ `resolved` có `document_id`; các trạng thái khác giữ candidate IDs để hỏi lại/kiểm ngữ cảnh. Không tự lấy phần tử đầu, luật mới nhất hoặc văn bản đang có hiệu lực.

Resolver nhận **span định danh** mà parser đã tách, không tìm luật trong cả câu văn. `year` là năm ban hành theo issue_date/số hiệu; không lấy năm có hiệu lực làm năm văn bản. `document_type` có thể là Luật/L, Nghị định/NĐ/ND, Nghị quyết/NQ, Thông tư/TT, Thông tư liên tịch/TTLT. Hints sai kiểu hoặc không biết bị ValueError; hint hợp lệ nhưng mâu thuẫn cho `not_found`.

## Định dạng artifact

```json
{
  "version": "document_aliases_v1",
  "normalization": "nfkd_casefold_alnum_v1",
  "registry_canonical_sha256": "<hash>",
  "documents": {"l_52_2014_qh13": {"issue_year": "2014", "effective_from": "2015-01-01", "effective_to": null}},
  "aliases": {
    "luat hngd": {
      "document_ids": ["l_21_lct_hdnn7", "l_22_2000_qh10", "l_52_2014_qh13"],
      "ambiguous": true,
      "requires_identity_context": false,
      "forms": ["Luật HNGĐ", "Luật HNGD"],
      "kinds": ["family_law_short_title"]
    }
  }
}
```

Ví dụ rút gọn, không phải JSON Schema. Consumer nên gọi loader để kiểm artifact thay vì tin mọi JSON cùng hình dạng. Loader so artifact với bản build từ registry hiện tại; stale/tampered mapping bị từ chối.

Normalization: Unicode NFKD, casefold, đ→d, bỏ dấu thanh, chuyển ký tự không phải chữ/số thành khoảng trắng rồi gộp khoảng trắng. Giữ nguyên nhóm chữ/số của số hiệu; không fuzzy-match authority, năm hoặc số văn bản chưa biết. Biến thể bỏ zero đầu chỉ sinh từ số hiệu đã tồn tại (ví dụ 02a/2015 → 2a/2015), không suy ra một văn bản mới.

Alias title, tên viết tắt HNGĐ, type+số hiệu/năm, file_code và canonical ID đều giữ toàn bộ ứng viên khi va chạm. Alias chỉ có năm hoặc loại+năm (ví dụ Luật 2014, NQ 2024) có `requires_identity_context=true`, kể cả nếu chỉ có một ứng viên trong corpus hữu hạn này. Cần tên/số hiệu đủ rõ, không chỉ thêm lại type/year hint cho chính alias yếu đó. Consumer đọc JSON trực tiếp phải tôn trọng flag, không coi singleton year là bằng chứng nhận diện toàn bộ thế giới văn bản.

## Hiệu lực và giới hạn

Registry dùng `effective_date/expiry_date`; metadata trong artifact xuất `effective_from/effective_to`, kèm `source_fields` ghi đúng tên trường gốc. Nếu cả canonical và legacy có giá trị khác nhau, build dừng thay vì tự chọn. Không đổi field trong registry, parser, chunk hoặc index hiện có.

Trạng thái cấp văn bản không đủ quyết định hiệu lực cấp Khoản. `effective_to=null` có thể còn thiếu quan hệ sửa đổi/bãi bỏ. Các cờ `requires_review`/`document_level_only` được giữ lại; alias identity đúng không chứng minh citation thuộc context, citation đúng Gold, claim được hỗ trợ hoặc luật áp dụng đúng tại as_of_date.

Không dùng as_of_date để tự giải alias mơ hồ: câu hỏi lịch sử có thể cần luật cũ. Temporal pre-filter và citation validator là những bước riêng. Không tự sửa source_url hoặc tuyên bố website còn truy cập được từ kiểm tra định dạng URL.

## Chạy và review

```powershell
python scripts/audit_document_metadata.py --write
python scripts/audit_document_metadata.py
python -m pytest test/test_document_aliases.py -q
```

Builder không truy cập mạng hoặc cần lịch sử Git để sinh aliases từ input working tree. Script audit ghi HEAD và snapshot `origin/testing` hiện có để truy nguyên, không fetch/merge tự động. Raw file hashes có thể khác vì CRLF checkout; hash registry canonical dùng JSON sorted keys/compact UTF-8/trailing newline để ổn định. Chỉ regenerate/review khi metadata thay đổi, không sửa artifact bằng tay để vượt check.

Dev 2 review vocabulary/normalization/ambiguous handling và tích hợp parser; Dev 3 review canonical ID và date mapping. Chưa có xác nhận reviewer ở bước bàn giao này.
