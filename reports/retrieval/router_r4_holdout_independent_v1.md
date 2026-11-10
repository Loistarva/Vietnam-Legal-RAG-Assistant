# D4.5 Rule Router smoke

- Thời điểm UTC: 2026-11-10T12:26:01.605251+00:00
- Git commit: `cdca079ba63b5e3d48da690df269ff51bb47c887`
- Classifier version: `rule_router_v2`
- Corpus SHA chuẩn hóa: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`
- Official IDs: 30; Dev queries: 270; negative v2: 26
- Router holdout candidate: 36 cases; label review: completed by Dev2 (peer reviewer; per maintainer confirmation); source: `test/agent/data/router_holdout_independent_v1.jsonl`
- Holdout validation error: `none`
- Holdout expected route distribution: `{"LEGAL_HNGD": 10, "LEGAL_OUT_OF_SCOPE": 8, "LEGAL_SCOPE_UNCERTAIN": 4, "MIXED_LEGAL_SCOPE": 6, "NON_LEGAL": 8}`
- Holdout category distribution: `{"administrative_penalty": 1, "business_registration": 1, "consumer_protection": 1, "cooking": 1, "criminal_gambling": 1, "entertainment_humor": 1, "gardening": 1, "general_science": 1, "general_weather": 1, "hngd_adoption_relationship": 1, "hngd_change_custody": 1, "hngd_child_visitation": 1, "hngd_parenting_arrangement": 1, "hngd_residence": 1, "hngd_spousal_obligations": 1, "hngd_step_parent": 1, "hngd_support_adult_child": 1, "hngd_support_parents": 1, "hngd_unlawful_marriage": 1, "land_use": 1, "math": 1, "mixed_gardening_hngd": 1, "mixed_hngd_business": 1, "mixed_hngd_employment": 1, "mixed_hngd_tax": 1, "mixed_math_hngd": 1, "mixed_translation_hngd": 1, "rental_tax": 1, "social_goodbye": 1, "social_insurance": 1, "technology_product_advice": 1, "traffic_overload": 1, "uncertain_generic_right": 1, "uncertain_legal_basis": 1, "uncertain_procedural_record": 1, "uncertain_scope_unspecified_dispute": 1}`
- Holdout legal-to-GENERAL_CHAT: 0; exact route/action mismatches: 3

## Gate results

| Gate | Kết quả |
|---|---|
| official30_all_LEGAL_HNGD | PASS |
| dev_legal_retrieval_at_least_95_percent | PASS |
| negative_non_legal_6_of_6 | PASS |
| no_legal_negative_to_GENERAL_CHAT | PASS |
| holdout_candidate_safety_no_legal_to_GENERAL_CHAT | PASS |
| holdout_candidate_route_action_match | FAIL |

- Dev queries routed to LEGAL_RETRIEVAL: 268/270 (99.3%)

## Negative-set confusion matrix

| Expected route | Predicted route | Count |
|---|---|---:|
| LEGAL_IN_SCOPE | LEGAL_HNGD | 12 |
| LEGAL_OUT_OF_SCOPE | LEGAL_OUT_OF_SCOPE | 7 |
| LEGAL_OUT_OF_SCOPE | MIXED_LEGAL_SCOPE | 1 |
| NON_LEGAL | NON_LEGAL | 6 |

## Holdout candidate detail (Dev2 peer review completed; no external legal validation claimed)

| ID | Expected route/action | Actual route/action | Result |
|---|---|---|---|
| R4IH_001 | LEGAL_HNGD / LEGAL_RETRIEVAL | LEGAL_HNGD / LEGAL_RETRIEVAL | PASS |
| R4IH_002 | LEGAL_HNGD / LEGAL_RETRIEVAL | LEGAL_HNGD / LEGAL_RETRIEVAL | PASS |
| R4IH_003 | LEGAL_HNGD / LEGAL_RETRIEVAL | LEGAL_HNGD / LEGAL_RETRIEVAL | PASS |
| R4IH_004 | LEGAL_HNGD / LEGAL_RETRIEVAL | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | FAIL |
| R4IH_005 | LEGAL_HNGD / LEGAL_RETRIEVAL | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | FAIL |
| R4IH_006 | LEGAL_HNGD / LEGAL_RETRIEVAL | LEGAL_HNGD / LEGAL_RETRIEVAL | PASS |
| R4IH_007 | LEGAL_HNGD / LEGAL_RETRIEVAL | LEGAL_HNGD / LEGAL_RETRIEVAL | PASS |
| R4IH_008 | LEGAL_HNGD / LEGAL_RETRIEVAL | LEGAL_HNGD / LEGAL_RETRIEVAL | PASS |
| R4IH_009 | LEGAL_HNGD / LEGAL_RETRIEVAL | LEGAL_HNGD / LEGAL_RETRIEVAL | PASS |
| R4IH_010 | LEGAL_HNGD / LEGAL_RETRIEVAL | LEGAL_HNGD / LEGAL_RETRIEVAL | PASS |
| R4IH_011 | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_012 | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_013 | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_014 | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_015 | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_016 | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_017 | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_018 | LEGAL_OUT_OF_SCOPE / POLICY_ABSTENTION | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | FAIL |
| R4IH_019 | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_020 | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_021 | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_022 | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_023 | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_024 | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | MIXED_LEGAL_SCOPE / POLICY_ABSTENTION | PASS |
| R4IH_025 | NON_LEGAL / GENERAL_CHAT | NON_LEGAL / GENERAL_CHAT | PASS |
| R4IH_026 | NON_LEGAL / GENERAL_CHAT | NON_LEGAL / GENERAL_CHAT | PASS |
| R4IH_027 | NON_LEGAL / GENERAL_CHAT | NON_LEGAL / GENERAL_CHAT | PASS |
| R4IH_028 | NON_LEGAL / GENERAL_CHAT | NON_LEGAL / GENERAL_CHAT | PASS |
| R4IH_029 | NON_LEGAL / GENERAL_CHAT | NON_LEGAL / GENERAL_CHAT | PASS |
| R4IH_030 | NON_LEGAL / GENERAL_CHAT | NON_LEGAL / GENERAL_CHAT | PASS |
| R4IH_031 | NON_LEGAL / GENERAL_CHAT | NON_LEGAL / GENERAL_CHAT | PASS |
| R4IH_032 | NON_LEGAL / GENERAL_CHAT | NON_LEGAL / GENERAL_CHAT | PASS |
| R4IH_033 | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | PASS |
| R4IH_034 | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | PASS |
| R4IH_035 | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | PASS |
| R4IH_036 | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL | PASS |
