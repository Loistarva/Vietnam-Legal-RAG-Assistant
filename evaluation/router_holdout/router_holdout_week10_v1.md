# Router Week 10 Holdout v1 - review record

## Status

- Dev4 has read and confirmed all 36 questions, expected routes/actions, rationales, and the reviewer corrections (2026-11-16).
- Every JSONL row records `reviewer_status: DEV4`.
- This records Dev4 owner review; it does not claim review by an independent third party.
- Router smoke evaluation was run on 2026-11-16 using `scripts/smoke_rule_router.py --holdout evaluation/router_holdout/router_holdout_week10_v1.jsonl`; result is summarized in [router_regression.md](../../reports/week10/router_regression.md).
- This run is an evaluation snapshot, not an independent legal review. Do not tune Router on these 36 cases and continue to treat the set as consumed for this evaluation.
- Corrections applied: W10RH_005 no longer asks about adoption eligibility; W10RH_004 and W10RH_008 were replaced; W10RH_010 no longer tests child custody; W10RH_031 and W10RH_034 avoid administrative-law framing.

## Dataset

- File: `router_holdout_week10_v1.jsonl`
- SHA-256: `8e1253d9d1e38635a9a63c6647e7996b91035bb59bfdb94ab9e0baf71f905308`
- Exact duplicate IDs/questions within file: none (checked by validator).
- Route distribution: `LEGAL_HNGD` 10, `LEGAL_OUT_OF_SCOPE` 8, `LEGAL_SCOPE_UNCERTAIN` 6, `MIXED_LEGAL_SCOPE` 6, `NON_LEGAL` 6.
- Route/action mapping is validated against `agent/router/rule_router.py`.
- Per-row rationale explains the routing signal; it does not certify legal merits.

## Overlap screening

Exact/normalized-text screening is run against:

- `test/agent/data/router_holdout.jsonl` (Router regression set)
- `test/agent/data/router_holdout_independent_v1.jsonl` (R4IH v1; consumed for tuning)
- `data/benchmark/queries_dev.json`
- `evaluation/negative_set/dev_negative_queries_v2.jsonl`
- string literals in `test/agent/test_rule_router.py`

The prior review's three named near-topic overlaps were replaced. Manual topic screening is documented, but cannot prove semantic independence from every Dev query or test phrase.

## Freeze and evaluation

The labels and rationales are confirmed by Dev4. Before reporting an independent holdout score, freeze Router code/config, record the full SHA and `CLASSIFIER_VERSION`, then run the Router once and save predictions separately. Do not tune using the holdout results. If a mismatch changes Router logic, this set becomes consumed regression data and a new unseen holdout is needed.

No holdout performance score is claimed in this file.
