# D4.1 H? s? freeze Router v5

## Ph?m vi v? k?t lu?n

Router `rule_router_v5` ???c kh?a cho b?n giao D4.1 tr?n nh?nh `week11_dev4`. H? s? ghi ng?y 23/11/2026, theo y?u c?u c?a project owner v? x?c nh?n Dev3 c?ng Tech Lead ?? sign-off. M? SRS: FR1.1, FR1.2, FR1.3, FR1.4, FR1.6; b?ng 5.3.3.

- Snapshot source/config/tests ?? commit: `d76244d8b454aedec7518bd37fecda3d419790cc`.
- N?n tr??c thay ??i boundary: `bd96d0d0e0dbabf877c4e2f508f50df9f303fa8b`.
- Tr?ng th?i t?i smoke sau commit: **clean**, UTC `2026-11-23T14:21:55.267878+00:00`.
- Tr?ng th?i: **FROZEN** cho snapshot source/config v? policy n?u trong h? s?. Commit th?m h? s? kh?ng thay source/config ?? kh?a.
- Phi?n b?n classifier gi? `rule_router_v5`: ch? ??i c?ch tr?nh b?y explanation, chuy?n adapter v? c?u h?nh x? giao; 552/552 quy?t ??nh route/action/reason/version kh?p baseline. Kh?ng ??i keyword, precedence, threshold ho?c prompt.

## ??u v?o v? ??u ra

??u v?o: Router v5, Negative Set v2 ?? duy?t, Dev Gold 30, Dev benchmark 270, c?c b? regression ?? ti?u th? v? contract `week10_v1.1` hi?n h?nh.

??u ra: adapter c?ng khai `agent.router.RuleRouterAdapter`, c?u h?nh `agent/config.py`, tests v? h? s? n?y. Dev5 wiring import adapter t? `agent/router/adapter.py`; import c? `orchestration.ask_service.RuleRouterAdapter` v? `GENERAL_CHAT_MESSAGE` ti?p t?c t??ng th?ch. T?t c? chuy?n ??i canonical ?i qua `RouteDecision.to_canonical()`; kh?ng c?n implementation mapping th? hai trong AskService. Explanation ghi `Route g?c -> Action (Reason): di?n gi?i`.

C?u h?nh x? giao `general_chat_v1` ch?a m?t k?ch b?n c? ??nh, gi? nguy?n n?i dung tr??c chuy?n, kh?ng ch?a ch? ??i?u? ho?c s? hi?u v?n b?n. Nh?nh n?y tr? SUCCESS/NOT_RUN, kh?ng retrieval/LLM; disclaimer do AskResponse cung c?p.

## Sign off v? policy

| Vai tr? | X?c nh?n ???c ghi nh?n | Ngu?n |
|---|---|---|
| Dev3 | Sign-off Router v5 v? boundary canonical | Project owner x?c nh?n trong phi?n l?m vi?c |
| Tech Lead | Sign-off Router v5 v? policy | Project owner x?c nh?n trong phi?n l?m vi?c |
| Project owner | Y?u c?u ghi freeze, th?ng nh?t adapter v? chuy?n c?u h?nh x? giao | Ch? ??o th?c hi?n D4.1 trong phi?n l?m vi?c |

Ng?y 23/11/2026 l? ng?y ghi h? s?; ng?y k? th?c t? c?a Dev3/Tech Lead v? URL review kh?ng ???c cung c?p n?n kh?ng t? ?i?n. ??y l? ghi nh?n x?c nh?n c?a project owner, kh?ng ph?i ch? k? GitHub ???c agent t?o thay ng??i review.

Policy NEG_DEV_025: ch? h?i h?ng th?a k? d?n s? ? LEGAL_OUT_OF_SCOPE/POLICY_ABSTENTION. Policy NEG_DEV_026: h?i ??nh t?i/khung h?nh ph?t ? ngo?i ph?m vi; h?i quy?n/ngh?a v?/b?o v? thu?c HNG? ? trong ph?m vi; k?t h?p hai ph?m vi ? MIXED_LEGAL_SCOPE/POLICY_ABSTENTION. Negative Set v2 ?? c? Dev2 review v? Tech Lead sign-off trong manifest.

- Negative Set canonical SHA-256: `5584795887e876f15febc05e7f04107b67862492d8a3d027840c01514d75223f`.
- Corpus SHA-256 chu?n h?a LF: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.
- Fast-path m?c ??nh: danh s?ch r?ng; th?m rule/policy m?i c?n ki?m th? v? snapshot freeze m?i.

## B?ng hash kh?a source v? c?u h?nh

Hash canonical l? SHA-256 c?a bytes UTF-8 sau khi ??i CRLF th?nh LF, gi? nguy?n c?c bytes c?n l?i. Raw SHA c?a `rule_router.py` t?i smoke Windows l? `17af2320286d8db5df26fa78cb10602ab634fbe6dcae1a6e1c8101bf70823a9d`; n? kh?c canonical ch? do line endings.

| Artifact | SHA-256 canonical LF |
|---|---|
| `agent/router/rule_router.py` | `081152e3e71795454b702c57092987703bd281f943cdfc3b740076a393780067` |
| `agent/router/adapter.py` | `1feb5fccbf40ff63eebc46116ee4942fb4e7077cb40bf59feb9c0355014ef2c5` |
| `agent/router/__init__.py` | `3e0c87ad748e7568fd7660e2aef7afd50ac12262e7e7e12d32d82d10ed862aad` |
| `agent/config.py` | `5f043ed3b90bedb0900eb7a653b7f48176f94fea1a4b9f1362e9ccad013e0eb7` |
| `orchestration/ask_service.py` | `563517ced5353ae58f1998b05ad9aabe1997473600fd2201b80197dfdeff69f8` |
| `orchestration/wiring.py` | `698d6eba3ade09ede67c4560b615118f0595812386721368303a9f1c634072e3` |
| `schemas/models.py` | `164f5dd110b10d2d9faf4d86d36e55ef22ba9b95d4eb3bff99fdf47bca002b19` |
| `retrieval/config.yaml` | `08df4180c8c47fe86592bb2a41d8b0e5f88cc0194160a7990990b3c139de8179` |
| `reranking/config.yaml` | `b99cf7319ec93eeb49c241904eb89b5e3e6b41fbbc05b56e63347b25693c6471` |

Hash snapshot t?ng h?p: `14acb337f0d8af87ba746418c435d8e8569e569b95bdce4888d57841eb290c8a`. C?ch t?i l?p: parse kh?i JSON sau, serialize v?i `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, th?m m?t LF cu?i r?i SHA-256 UTF-8.

```json
{
  "classifier_version": "rule_router_v5",
  "fast_path_rules": [],
  "general_chat_config_version": "general_chat_v1",
  "schema_version": "week10_v1.1",
  "negative_set_canonical_sha256": "5584795887e876f15febc05e7f04107b67862492d8a3d027840c01514d75223f",
  "files_sha256_lf": {
    "agent/router/rule_router.py": "081152e3e71795454b702c57092987703bd281f943cdfc3b740076a393780067",
    "agent/router/adapter.py": "1feb5fccbf40ff63eebc46116ee4942fb4e7077cb40bf59feb9c0355014ef2c5",
    "agent/router/__init__.py": "3e0c87ad748e7568fd7660e2aef7afd50ac12262e7e7e12d32d82d10ed862aad",
    "agent/config.py": "5f043ed3b90bedb0900eb7a653b7f48176f94fea1a4b9f1362e9ccad013e0eb7",
    "orchestration/ask_service.py": "563517ced5353ae58f1998b05ad9aabe1997473600fd2201b80197dfdeff69f8",
    "orchestration/wiring.py": "698d6eba3ade09ede67c4560b615118f0595812386721368303a9f1c634072e3",
    "schemas/models.py": "164f5dd110b10d2d9faf4d86d36e55ef22ba9b95d4eb3bff99fdf47bca002b19",
    "retrieval/config.yaml": "08df4180c8c47fe86592bb2a41d8b0e5f88cc0194160a7990990b3c139de8179",
    "reranking/config.yaml": "b99cf7319ec93eeb49c241904eb89b5e3e6b41fbbc05b56e63347b25693c6471"
  }
}
```

SHA Router v5 tr??c thay ??i explanation l? `996bd6a0894aeaf964f188f032961329ec6cdecfe1575bcf80df685aa068f2f7`, source commit `48956492b63238b4d1df323cad06d8547e1cc4b7`. SHA ?? ???c gi? ?? truy v?t k?t qu? l?ch s?; kh?ng d?ng thay SHA snapshot b?n giao m?i.

## K?t qu? ki?m ch?ng

| Gate | K?t qu? |
|---|---|
| Official Gold route/action | 30/30 PASS |
| Dev action LEGAL_RETRIEVAL | 270/270 PASS, v??t ng??ng 95% |
| Negative v2 route/action thu?c Router | 26/26 PASS |
| Non-legal Negative Set | 6/6 SUCCESS/NOT_RUN; Retrieval=0, LLM=0 |
| Out-of-scope Negative Set | 8/8 ABSTAIN/NOT_RUN/ROUTE_POLICY; Retrieval=0, LLM=0 |
| Legal negative sang NON_LEGAL/GENERAL_CHAT | 0/20 |
| Regression Week10 v1 | 36/36, safety PASS |
| Regression R4IH v1 | 36/36, safety PASS |
| Regression router_holdout.jsonl | 40/40, safety PASS |
| Route/action/reason/version tr??c v? sau s?a boundary | 552/552 kh?p, kh?ng ??c v6 |
| Router, AskService v? smoke tests | 139 passed, 395 subtests passed |
| API v? CLI/E2E gi? l?p | 100 passed |
| Ruff v? git diff --check | PASS |

C?c b? v1?v5/R4IH ?? ti?u th? ch? l? regression. Holdout v6 kh?ng ???c ch?y l?i. K?t qu? 34/36 c?a v6 thu?c source SHA l?ch s? n?u tr?n, kh?ng ph?i m?t l?n ??nh gi? ??c l?p m?i tr?n snapshot b?n giao. X?c nh?n Dev3 ?? review v6 ???c project owner cung c?p; h? s? review/??nh gi? D4.2 ph?i ghi ri?ng th?i ?i?m v? b?ng ch?ng th?c t?, kh?ng suy ra t? sign-off D4.1.

## L?nh ki?m ch?ng

Ch?y trong checkout c?a snapshot source ?? n?u, d?ng Python m?i tr??ng repo c? dependency requirements:

```powershell
.\.venv\Scripts\python.exe -m pytest -q test/agent/test_rule_router.py test/orchestration/test_ask_service.py test/test_smoke_rule_router.py
.\.venv\Scripts\python.exe -m pytest -q test/api test/e2e
.\.venv\Scripts\python.exe scripts/smoke_rule_router.py --skip-holdout
.\.venv\Scripts\python.exe -m ruff check agent/config.py agent/router orchestration/ask_service.py orchestration/wiring.py test/agent/test_rule_router.py test/orchestration/test_ask_service.py
git diff --check
```

? m?i tr??ng agent, pytest d?ng `--basetemp` ri?ng trong `.pytest-cache-local` v? `-p no:cacheprovider`; dependency FastAPI/Starlette/Uvicorn ???c n?p t? th? m?c t?m v? venv g?c ch?a c?i API. Kh?ng ??i requirements ho?c m?i tr??ng venv. Kh?ng g?i Ollama hay d?ch v? retrieval th?t.

## C?ng ngh? v? gi?i h?n

Python rule-based Router, canonical Pydantic contract, c?u h?nh Python c? ??nh, pytest/subtests, fake pipeline, Ruff v? SHA-256. D4.1 ch? kh?a boundary/routing/config; kh?ng nghi?m thu thay D4.2 holdout, D4.3 Retrieval Adapter ho?c live UI/API.
