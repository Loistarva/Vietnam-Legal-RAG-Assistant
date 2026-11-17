# Corpus v2 test review ? 2026-11-17

Runtime parser, cleaner, chunker and schemas are unchanged. Only four test modules and a source-reviewed title fixture change.

- Official long titles: 31 exact title exceptions verified against original source files and SHA-256, with the general 40-word guard retained.
- Alias tests: isolate the one-candidate fixture; accommodate additional laws issued in 2014/2015; audit counts against actual input sizes.
- Negative-set tests: run BOM and unrelated-change checks against the dataset's pinned baseline. Added coverage verifies that current corpus coverage invalidates historical missing-source cases.
- Frozen Test: validate the historical manifest against the preserved baseline chunks; independently require expanded corpus to fail the historical freeze guard. Historical manifests, ground truth and A/B outputs are unchanged.

The standalone historical negative validator is expected to reject NEG_DEV_013?018 on corpus v2: Laws 52/2010/QH12, 60/2014/QH13 and Resolution 326/2016/UBTVQH14 are now present. This is an evaluation data review requirement, not a parser failure. The evaluation owner must version/review the affected negative labels before using them to score corpus v2. No historical labels were rewritten just to get a passing suite.

Full suite results: see full_suite_final.log and full_suite_final.xml. Passing unit tests do not imply a new live index or a completed legal effectivity review.
