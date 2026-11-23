# D1.1 — Metadata audit và document aliases

Ngày thực hiện: **08/11/2026** (Asia/Saigon). Tên file 20261103 giữ theo đường dẫn bàn giao trong kế hoạch; không phải ngày đã thực hiện audit.

Git SHA lúc audit: `790eeaa406e070b4f31f513e0c8d78e6972790da`; registry/corpus đọc từ working tree, fingerprints ở JSON evidence. Không đổi registry, corpus, benchmark hoặc Test.

## Kết quả cấu trúc

- Registry: 84 văn bản; corpus: 6165 chunks / 84 văn bản; article index: 3841 dòng.
- Structural errors: **0**; warnings: 84. Đây không phải xác nhận hiệu lực pháp lý độc lập hoặc xác nhận HTTP của nguồn.
- Alias keys: 2143; ambiguous keys: 127. Mỗi key giữ toàn bộ candidate IDs, không overwrite ứng viên hoặc tự chọn năm mới nhất.

## Kiểm tra đã làm

ID canonical, file_code và số hiệu không trùng; số hiệu/năm khớp issue_date (khi số hiệu có năm); title bắt buộc; ISO date và thứ tự issue/effectivity; canonical/legacy date không xung đột. Đối chiếu document_id, document_number, document_type, issue_date và effective period của chunk với registry; article index nối đúng văn bản/số hiệu.

## Hiệu lực và vấn đề nguồn

Registry hiện dùng effective_date/expiry_date; alias artifact ánh xạ thành effective_from/effective_to sau kiểm tra, không đổi tên field trong registry/consumer cũ. Ngày kết thúc là cận loại trừ. Alias resolver không lọc hiệu lực hoặc kết luận luật áp dụng; năm là năm ban hành, không phải năm hiệu lực.

Cờ requires_review trong nguồn:

- `nd_126_2014_nd_cp`
- `tt_04_2020_tt_btp`
- `tt_57_2015_tt_byt`
- `nd_123_2015_nd_cp`
- `l_102_2016_qh13`
- `bl_92_2015_qh13`
- `l_34_2024_qh15`
- `nd_24_2019_nd_cp`
- `nd_06_2025_nd_cp`
- `tt_07_2023_tt_btp`
- `nd_104_2022_nd_cp`
- `nd_120_2025_nd_cp`
- `l_85_2025_qh15`
- `tt_10_2025_tt_btp`
- `nd_63_2024_nd_cp`
- `l_58_2020_qh14`
- `tt_01_2022_tt_btp`
- `tt_03_2023_tt_btp`
- `tt_07_2025_tt_bng`
- `l_60_2014_qh13`
- `l_52_2010_qh12`
- `l_13_2022_qh15`
- `tt_10_2020_tt_btp`
- `l_35_2013_qh13`
- `nd_19_2011_nd_cp`
- `nd_76_2023_nd_cp`
- `nd_114_2016_nd_cp`
- `nd_15_2014_nd_cp`
- `nq_326_2016_ubtvqh14`
- `bl_91_2015_qh13`
- `tt_09_2022_tt_btp`
- `nd_301_2026_nd_cp`
- `nd_24_2013_nd_cp`
- `tt_22_2013_tt_btp`
- `tt_16_2010_tt_btp`
- `ttlt_03_2016_ttlt_btp_bng_bca_bldtbxh`
- `nd_110_2013_nd_cp`
- `tt_66_2025_tt_bca`
- `nd_110_2025_nd_cp`
- `tt_11_2021_tt_btp`
- `tt_01_2025_tt_btp`
- `tt_24_2014_tt_btp`
- `tt_12_2011_tt_btp`
- `tt_15_2014_tt_btp`
- `tt_21_2011_tt_btp`
- `nd_158_2005_nd_cp`
- `nd_83_1998_nd_cp`
- `l_02_2007_qh12`
- `nd_08_2009_nd_cp`
- `nd_110_2009_nd_cp`
- `tt_08_2025_tt_btp`
- `nd_282_2025_nd_cp`
- `nd_347_2026_nd_cp`
- `ttlt_01_2019_ttlt_tandtc_bng`
- `l_102_2025_qh15`
- `nd_158_2026_nd_cp`
- `l_73_2006_qh11`
- `l_24_2008_qh12`
- `l_68_2020_qh14`
- `l_11_2017_qh14`

Các cờ này đã có trong registry; không trình bày thành lỗi mới và không tự điền ngày hết hiệu lực cho điều khoản chỉ dựa vào trạng thái cấp văn bản. End=null có thể chưa mô hình hóa đầy đủ sửa đổi/bãi bỏ; không phải chứng minh mọi điều còn hiệu lực.

Warning counts:

- provision_effectivity_not_independently_verified: 84

## Alias mơ hồ tiêu biểu

```json
{
  "2014": [
    "l_52_2014_qh13",
    "l_60_2014_qh13",
    "nd_126_2014_nd_cp",
    "nd_15_2014_nd_cp",
    "tt_15_2014_tt_btp",
    "tt_24_2014_tt_btp"
  ],
  "2025": [
    "l_102_2025_qh15",
    "l_81_2025_qh15",
    "l_85_2025_qh15",
    "nd_06_2025_nd_cp",
    "nd_07_2025_nd_cp",
    "nd_110_2025_nd_cp",
    "nd_120_2025_nd_cp",
    "nd_207_2025_nd_cp",
    "nd_282_2025_nd_cp",
    "tt_01_2025_tt_btp",
    "tt_07_2025_tt_bng",
    "tt_08_2025_tt_btp",
    "tt_10_2025_tt_btp",
    "tt_38_2025_tt_byt",
    "tt_66_2025_tt_bca"
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

Registry canonical SHA-256: `b231f27c52c48f4a5f4b9dfa814410e5009447912a48762599e82e3021b2298d`.
- data/reference/document_versions.json: raw file SHA-256 `382b8b6198ab5f5b8821d953b79b1f189021bbfc54ad48381bf175cacb4a880e`
- data/chunking_output/chunks.jsonl: raw file SHA-256 `90bb120257352e46fe4e6d440c50e0288b4123494cbbae9522b7d71012491073`
- data/reference/article_index.json: raw file SHA-256 `0cd361c4c01e46115941ffce59d7082feaa24ec263b6416ebd8392ce17aa834e`
- data/reference/provision_periods.json: raw file SHA-256 `bf1f71e62bc3f7efc44bc6d5f5f12338b2ad1fd290af4b0acee5a72c740444e2`

Không kiểm HTTP/redirect hay tự sửa source_url. Không suy diễn thêm văn bản mới, điều khoản đang còn hiệu lực hoặc tình trạng pháp lý từ alias. Nếu metadata đổi phải rebuild/review artifact; load_alias_map từ chối bản stale/tampered. Reviewer: Dev 2 + Dev 3; tình trạng pending_peer_review.

Remote context:

origin/testing snapshot 03a498924d0d134d2abc861599db94920f7291db; differing tracked input paths vs HEAD: ['data/chunking_output/chunks.jsonl', 'data/reference/article_index.json', 'data/reference/document_versions.json']. No automatic merge. Registry/corpus unchanged relative to this snapshot when absent from the list; article/source URL changes need integration review.

## Cách tái lập và bàn giao

```powershell
python scripts/audit_document_metadata.py
python -m pytest test/test_document_aliases.py -q
```

Dùng --write để sinh alias map/evidence/report sau audit. Citation consumer đọc data/reference/document_aliases.json qua evaluation.document_aliases.load_alias_map; resolver nhận exact span và optional year/document_type. Sample/API chi tiết ở docs/document_aliases.md. Chưa sửa citation parser hoặc schema canonical của Dev 3.
