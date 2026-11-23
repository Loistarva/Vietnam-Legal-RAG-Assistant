# Negative Set Dev v2

## Trạng thái

`dev_negative_queries_v2.jsonl` là Negative Set đang dùng; manifest là `dev_negative_manifest_v2.json`. Bộ có 26 câu và đã được Dev2 review độc lập cùng Tech Lead sign-off ngày 2026-11-17 theo SHA canonical `5584795887e876f15febc05e7f04107b67862492d8a3d027840c01514d75223f`. Trạng thái manifest: `peer_reviewed`.

Sign-off này áp dụng cho bộ Negative Set v2; không tự động freeze Router hay chứng minh hiệu năng độc lập trên holdout. V1 đã được supersede và artifact data/report v1 được dọn khỏi thư mục; holdout Router v1 nằm ngoài thư mục này và được giữ làm kết quả đã tiêu thụ/regression.

## Phân bố

| Nhãn | Số câu |
| --- | ---: |
| `non_legal` | 6 |
| `legal_out_of_scope` | 8 |
| `missing_corpus_evidence` | 6 |
| `insufficient_facts` | 6 |

## Xác minh

```powershell
.\.venv\Scripts\python.exe scripts/validate_negative_set.py
.\.venv\Scripts\python.exe -m pytest test/test_negative_set.py -q
```

SHA canonical được tính bằng cách parse các dòng JSONL thành danh sách record, serialize thành JSON UTF-8 với `ensure_ascii=false`, `sort_keys=true`, separators compact `(',', ':')`, thêm một LF cuối rồi SHA-256. Reviewer dùng SHA canonical trong manifest để xác định artifact đã review.