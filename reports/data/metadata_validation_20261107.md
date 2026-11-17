# D1.1 — Ket qua kiem tra ngay 07/11/2026

Technical handoff: pending_peer_review (Dev 2 + Dev 3).

| Command | Result |
| --- | --- |
| `python scripts/audit_document_metadata.py` | PASS: errors=0; warnings=24; ambiguous_aliases=24 |
| `python -m pytest test/test_document_aliases.py -q` | 58 passed in 2.46s |
| `python scripts/validate_benchmark.py` | PASS. Handoff check chỉ chứng minh cấu trúc, chưa phải xác nhận gold pháp lý/production. |
| `python scripts/freeze_test.py --verify` | PASS: 30 câu Test chưa bị thay đổi |
| `python scripts/freeze_gold.py --verify` | PASS: Test Gold (30 câu) không đổi |
| `python -m pytest -q` | 761 passed, 1 skipped in 58.17s |

Additional data checks: 72 canonical ID/number/file_code round trips PASS; every declared raw alias form normalizes to its own key.

Raw stdout/stderr, exit codes and before/after hashes: metadata_validation_20261107.json. Protected registry, corpus, Dev/Test/Gold and freeze manifests unchanged. Full pytest runs offline fixtures; one inherited skipped test is not counted as PASS.

Alias map: 24 documents; 562 keys; 24 multi-candidate keys; 62 weak year/type-year keys require identity context.

Regression coverage: number/title/type/year variants, diacritics/Unicode punctuation, short known numbers, shared titles, conflicting hints, weak singleton years, unknown full authority, stale/tampered maps, wrong registry identity/dates, missing corpus/index, metadata mismatch and shallow/single-branch audit without origin/testing ref.

Structural errors: 0. The 24 warnings preserve existing document-level/provision effectivity limitations; they are not newly established legal errors. requires_review flags remain for ND126, TT04/2020, TT57/2015, ND123. No automatic correction or new source verification was inferred.

Canonical plan report: metadata_audit_20261103.md; actual audit date in that report is 07/11/2026. Source-code implementation is local/uncommitted at this handoff. No external model, live index, HTTP URL sweep or official evaluation was invoked.
