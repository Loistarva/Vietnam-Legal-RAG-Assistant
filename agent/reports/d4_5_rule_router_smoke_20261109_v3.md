# D4.5 Rule Router smoke

- Thời điểm UTC: 2026-11-09T12:05:42.893767+00:00
- Git commit: `ef72d9dff6f1c9568cfab80634bb458d588a3013`
- Corpus SHA chuẩn hóa: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`
- Official IDs: 30; Dev queries: 270; negative v2: 26

## Gate results

| Gate | Kết quả |
|---|---|
| official30_all_LEGAL_HNGD | PASS |
| dev_legal_retrieval_at_least_95_percent | PASS |
| negative_non_legal_6_of_6 | PASS |
| no_legal_negative_to_GENERAL_CHAT | PASS |

- Dev queries routed to LEGAL_RETRIEVAL: 269/270 (99.6%)

## Negative-set confusion matrix

| Expected route | Predicted route | Count |
|---|---|---:|
| LEGAL_IN_SCOPE | LEGAL_HNGD | 12 |
| LEGAL_OUT_OF_SCOPE | LEGAL_OUT_OF_SCOPE | 7 |
| LEGAL_OUT_OF_SCOPE | MIXED_LEGAL_SCOPE | 1 |
| NON_LEGAL | NON_LEGAL | 6 |
