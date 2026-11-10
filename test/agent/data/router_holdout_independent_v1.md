# Router Regression Set R4 — Original Holdout v1

## 1. Purpose and Status

This 36-query dataset was prepared as an R4.6 evaluation candidate. It has since been evaluated, and its mismatches are now being used to guide Router changes.

**Review status: Maintainer self-review and Dev2 peer review completed; external legal validation not performed.**

The repository maintainer states that Dev2 has reviewed the dataset and its labels. This records a peer review within the project; it does not claim external legal validation.

The dataset review covers:

- Dataset structure and schema.
- Query distribution across five routing categories.
- Expected route/action combinations.
- Query wording and labeling consistency.
- Evaluation methodology and documented limitations.

**Current status: CONSUMED FOR REGRESSION/TUNING; no longer an untouched holdout.**

Preserve the original labels and first-run report. Do not use this set to claim independent post-fix performance; create a new, unseen holdout for that purpose.

## 2. Metadata

- Dataset file: `router_holdout_independent_v1.jsonl`
- Number of queries: 36
- Target classifier version: To be filled after Router freeze.
- Frozen Git commit: `<FILL_IN_AFTER_ROUTER_FREEZE>`
- Actual CLASSIFIER_VERSION: `<FILL_IN_AFTER_ROUTER_FREEZE>`
- Dataset preparation date: `2026-11-10`
- Label review: COMPLETED.
- Maintainer self-review: COMPLETED.
- Dev2 peer review of dataset and labels: COMPLETED (per maintainer confirmation).
- External legal validation: NOT PERFORMED.
- Initial Router evaluation: COMPLETED on `rule_router_v2`, commit `cdca079ba63b5e3d48da690df269ff51bb47c887`.
- Initial exact route/action: 33/36; legal-to-`GENERAL_CHAT`: 0.
- Initial mismatches: `R4IH_004`, `R4IH_005`, `R4IH_018`.
- Current use: regression/tuning set; not independent evaluation data.

## 3. Dataset Distribution

| Group | Count | Expected Route | Expected Action |
|---|---:|---|---|
| HNGĐ | 10 | `LEGAL_HNGD` | `LEGAL_RETRIEVAL` |
| Legal outside project scope | 8 | `LEGAL_OUT_OF_SCOPE` | `POLICY_ABSTENTION` |
| Mixed | 6 | `MIXED_LEGAL_SCOPE` | `POLICY_ABSTENTION` |
| Non-legal | 8 | `NON_LEGAL` | `GENERAL_CHAT` |
| Legal scope uncertain | 4 | `LEGAL_SCOPE_UNCERTAIN` | `LEGAL_RETRIEVAL` |
| **Total** | **36** | | |

Three queries are written without Vietnamese diacritics:

- `R4IH_004`
- `R4IH_014`
- `R4IH_030`

These queries exercise the Router's accent-normalization path.

## 4. Labeling Convention

Expected route/action pairs follow the Router enums and intended routing contract:

- `LEGAL_HNGD` → `LEGAL_RETRIEVAL`
- `LEGAL_OUT_OF_SCOPE` → `POLICY_ABSTENTION`
- `MIXED_LEGAL_SCOPE` → `POLICY_ABSTENTION`
- `NON_LEGAL` → `GENERAL_CHAT`
- `LEGAL_SCOPE_UNCERTAIN` → `LEGAL_RETRIEVAL`

These labels describe routing expectations. They are not legal advice or adjudications of the underlying facts.

## 5. Revision Notes

- `R4IH_026` was changed from another capital-city question to a general-science question about the boiling point of pure water at standard atmospheric pressure.
- `R4IH_004`, `R4IH_014`, and `R4IH_030` were converted to unaccented Vietnamese to provide accent-normalization cases.
- `R4IH_034` was replaced with a question about adding a dissenting statement to an inaccurate working record before signing. This removes the earlier generic right-to-sue scenario, which was semantically close to a reviewer example.
- The expected labels were assigned before Router evaluation.
- Router predictions were not used during dataset preparation.

## 6. Review, Duplicate Screening, and Limitations

**Maintainer self-review and Dev2 peer review: COMPLETED**, according to the maintainer. No external legal validation is claimed.

The original candidate was screened lexically against the repository datasets available during preparation:

- Dev270.
- Existing `router_holdout.jsonl`.
- Negative Set v2.
- Existing Router test cases.
- Reviewer examples reproduced in the supplied R4 review note.

The similarity audit is a lexical comparison, not proof of semantic independence.

The complete 53-query reviewer evaluation set was not present in the materials available during the original preparation. Therefore, the available lexical screening alone cannot establish that no query is semantically equivalent to any of all 53 reviewer queries.

Dev2 peer review is recorded above. The maintainer authored the questions, so peer review does not satisfy an independent-author requirement. The complete 53-query reviewer set was unavailable for full screening. Because this dataset has informed Router changes, use it only for regression from this point onward.

## 7. Evaluation Protocol and Current Use

The original evaluation protocol below records how the first run was performed. This dataset is now consumed, so do not rerun it as an independent holdout or overwrite its first-run report.

For any future independent evaluation:

1. Use a newly authored, unseen dataset whose queries have not guided Router changes.
2. Freeze the Router commit and record its full Git SHA and classifier version.
3. Validate JSONL structure, IDs, category distribution, enum values, route/action pairs, and exact-text overlap against repository comparison sources.
4. Preserve reviewed expected labels before running predictions.
5. Run `scripts/smoke_rule_router.py` with the new dataset path and a new report path. The smoke script now uses `DEFAULT_COMPARISON_PATHS` during validation.
6. Preserve the first evaluation result. Do not change labels to match predictions.
7. Move any case used to modify Router logic into a regression set; it is no longer untouched holdout data.

## 8. Evaluation Results

The first evaluation is recorded in `reports/retrieval/router_r4_holdout_independent_v1.md`: 33/36 exact route/action matches, zero legal-to-`GENERAL_CHAT` cases, and three mismatches. The report describes the original `rule_router_v2` run. The current code changes require fresh regression tests; preserve the first-run report unchanged.
