# D1.1 — Metadata audit và document aliases

Ngày thực hiện: **07/11/2026** (Asia/Saigon). Tên file 20261103 giữ theo đường dẫn bàn giao trong kế hoạch; không phải ngày đã thực hiện audit.

Git SHA lúc audit: `6eff7c2a6db34202b5b3ffad6c5ee14ef5902366`; registry/corpus đọc từ working tree, fingerprints ở JSON evidence. Không đổi registry, corpus, benchmark hoặc Test.

## Kết quả cấu trúc

- Registry: 24 văn bản; corpus: 2164 chunks / 24 văn bản; article index: 799 dòng.
- Structural errors: **0**; warnings: 24. Đây không phải xác nhận hiệu lực pháp lý độc lập hoặc xác nhận HTTP của nguồn.
- Alias keys: 562; ambiguous keys: 24. Mỗi key giữ toàn bộ candidate IDs, không overwrite ứng viên hoặc tự chọn năm mới nhất.

## Kiểm tra đã làm

ID canonical, file_code và số hiệu không trùng; số hiệu/năm khớp issue_date (khi số hiệu có năm); title bắt buộc; ISO date và thứ tự issue/effectivity; canonical/legacy date không xung đột. Đối chiếu document_id, document_number, document_type, issue_date và effective period của chunk với registry; article index nối đúng văn bản/số hiệu.

## Hiệu lực và vấn đề nguồn

Registry hiện dùng effective_date/expiry_date; alias artifact ánh xạ thành effective_from/effective_to sau kiểm tra, không đổi tên field trong registry/consumer cũ. Ngày kết thúc là cận loại trừ. Alias resolver không lọc hiệu lực hoặc kết luận luật áp dụng; năm là năm ban hành, không phải năm hiệu lực.

Cờ requires_review trong nguồn:

- `nd_126_2014_nd_cp`
- `tt_04_2020_tt_btp`
- `tt_57_2015_tt_byt`
- `nd_123_2015_nd_cp`

Các cờ này đã có trong registry; không trình bày thành lỗi mới và không tự điền ngày hết hiệu lực cho điều khoản chỉ dựa vào trạng thái cấp văn bản. End=null có thể chưa mô hình hóa đầy đủ sửa đổi/bãi bỏ; không phải chứng minh mọi điều còn hiệu lực.

Warning counts:

- provision_effectivity_not_independently_verified: 24

## Alias mơ hồ tiêu biểu

```json
{
  "2014": [
    "l_52_2014_qh13",
    "nd_126_2014_nd_cp"
  ],
  "2025": [
    "l_81_2025_qh15",
    "nd_207_2025_nd_cp",
    "tt_38_2025_tt_byt"
  ],
  "luat hngd": [
    "l_21_lct_hdnn7",
    "l_22_2000_qh10",
    "l_52_2014_qh13"
  ],
  "luat hon nhan va gia dinh": [
    "l_21_lct_hdnn7",
    "l_22_2000_qh10",
    "l_52_2014_qh13"
  ],
  "nghi dinh 2015": [
    "nd_10_2015_nd_cp",
    "nd_123_2015_nd_cp"
  ]
}
```

## Nguồn và giới hạn

Registry canonical SHA-256: `19d8f6b3ab8c47c3363ee08fa0d77afc0f9f2d1c9196692de5a36b638df9cd64`.
- data/reference/document_versions.json: raw file SHA-256 `af7fcf530b53907250840fc06fbd19e2eba25170e4757a7103d77df01092c283`
- data/chunking_output/chunks.jsonl: raw file SHA-256 `9a72a35e532f03447b348afe11e4d718ba7f3697f8f6b4d2108f1d28747c01bb`
- data/reference/article_index.json: raw file SHA-256 `d62154c08c40a29de5063cd7d333b02f4028a619232ba545224134ee2769f4c0`

Không kiểm HTTP/redirect hay tự sửa source_url. Không suy diễn thêm văn bản mới, điều khoản đang còn hiệu lực hoặc tình trạng pháp lý từ alias. Nếu metadata đổi phải rebuild/review artifact; load_alias_map từ chối bản stale/tampered. Reviewer: Dev 2 + Dev 3; tình trạng pending_peer_review.

Remote context:

origin/testing snapshot d203ed5b4e8925d63742d897bd8a9879b1a04c34; differing tracked input paths vs HEAD: ['data/normalized_metadata.json', 'data/reference/article_index.json']. No automatic merge. Registry/corpus unchanged relative to this snapshot when absent from the list; article/source URL changes need integration review.

## Cách tái lập và bàn giao

```powershell
python scripts/audit_document_metadata.py
python -m pytest test/test_document_aliases.py -q
```

Dùng --write để sinh alias map/evidence/report sau audit. Citation consumer đọc data/reference/document_aliases.json qua evaluation.document_aliases.load_alias_map; resolver nhận exact span và optional year/document_type. Sample/API chi tiết ở docs/document_aliases.md. Chưa sửa citation parser hoặc schema canonical của Dev 3.
