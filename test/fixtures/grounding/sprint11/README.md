# Grounding fixture usage

`base_context.json` contains invented IDs and text, not a legal document. The canonical 18 case descriptions are `evaluation/quality/grounding_cases_sprint11.jsonl`; `test/grounding/test_sprint11_regression.py` applies their mutations and verifies expected status/code.

Fixtures test structural citation mapping and explicit date bounds. They are not corpus additions, benchmark Gold or semantic hallucination labels. Exact normalized query/ID overlap is audited against benchmark/negative/remote holdout inputs; this does not certify independent holdout labels or tune the router.
