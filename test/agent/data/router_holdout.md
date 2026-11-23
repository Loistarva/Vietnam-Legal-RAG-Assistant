# Rule Router holdout set

`router_holdout.jsonl` contains 40 cases that are separate from the Dev benchmark and the negative set used by the smoke script. The reviewer examples from the PR review are included as regression anchors; additional cases broaden the set across family law, independent legal domains, mixed scope, and clearly nonlegal requests.

The exact route/action labels are executable expectations, not legal advice. A reviewer who did not tune the router should confirm the cases and labels before treating the holdout gate as an independent acceptance result. The smoke command reports both legal-to-General-Chat safety and exact classification agreement.
