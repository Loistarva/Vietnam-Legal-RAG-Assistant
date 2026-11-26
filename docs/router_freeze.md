# D4.1 — Hồ sơ freeze Router v5

## Phạm vi và kết luận

Router `rule_router_v5` được khóa cho bàn giao D4.1 trên nhánh `week11_dev4`. Hồ sơ ghi ngày 23/11/2026, theo yêu cầu của project owner và xác nhận Dev3 cùng Tech Lead đã sign-off. Mã SRS: FR1.1, FR1.2, FR1.3, FR1.4, FR1.6; bảng 5.3.3.

- Snapshot source/config/tests: `d76244d8b454aedec7518bd37fecda3d419790cc`.
- Nền trước thay đổi boundary: `bd96d0d0e0dbabf877c4e2f508f50df9f303fa8b`.
- Trạng thái tại smoke sau commit: **clean**, UTC `2026-11-23T14:21:55.267878+00:00`.
- Trạng thái: **FROZEN** cho snapshot source/config và policy trong hồ sơ này. Thay đổi tài liệu không thay snapshot đã khóa.
- Giữ phiên bản classifier `rule_router_v5`: chỉ đổi cách trình bày explanation, chuyển adapter và cấu hình xã giao; 552/552 quyết định route/action/reason/version khớp baseline. Không đổi keyword, precedence, threshold hoặc prompt.

## Đầu vào và đầu ra

Đầu vào: Router v5, Negative Set v2 đã duyệt, Dev Gold 30, Dev benchmark 270, các bộ regression đã tiêu thụ và contract `week10_v1.1`.

Đầu ra: adapter công khai `agent.router.RuleRouterAdapter`, cấu hình `agent/config.py`, tests và hồ sơ này. Dev5 wiring import adapter từ `agent/router/adapter.py`; import cũ `orchestration.ask_service.RuleRouterAdapter` và `GENERAL_CHAT_MESSAGE` tiếp tục tương thích. Tất cả chuyển đổi canonical đi qua `RouteDecision.to_canonical()`; AskService không còn implementation mapping thứ hai. Explanation ghi `Route gốc -> Action (Reason): diễn giải`.

Cấu hình xã giao `general_chat_v1` chứa một kịch bản cố định, giữ nguyên nội dung trước khi chuyển, không chứa chỉ dẫn điều luật hoặc số hiệu văn bản. Nhánh này trả SUCCESS/NOT_RUN, không retrieval/LLM; disclaimer do AskResponse cung cấp.

## Sign-off và policy

| Vai trò | Xác nhận được ghi nhận | Nguồn |
|---|---|---|
| Dev3 | Sign-off Router v5 và boundary canonical | Project owner xác nhận trong phiên làm việc |
| Tech Lead | Sign-off Router v5 và policy | Project owner xác nhận trong phiên làm việc |
| Project owner | Yêu cầu ghi freeze, thống nhất adapter và chuyển cấu hình xã giao | Chỉ đạo thực hiện D4.1 trong phiên làm việc |

Ngày 23/11/2026 là ngày ghi hồ sơ. Ngày ký thực tế của Dev3/Tech Lead và URL review chưa được cung cấp nên không tự điền. Đây là ghi nhận xác nhận của project owner, không phải chữ ký GitHub được tạo thay người review.

Policy NEG_DEV_025: chỉ hỏi hàng thừa kế dân sự → LEGAL_OUT_OF_SCOPE/POLICY_ABSTENTION. Policy NEG_DEV_026: hỏi định tội/khung hình phạt → ngoài phạm vi; hỏi quyền/nghĩa vụ/bảo vệ thuộc HNGĐ → trong phạm vi; kết hợp hai phạm vi → MIXED_LEGAL_SCOPE/POLICY_ABSTENTION. Negative Set v2 có Dev2 review và Tech Lead sign-off trong manifest.

- Negative Set canonical SHA-256: `5584795887e876f15febc05e7f04107b67862492d8a3d027840c01514d75223f`.
- Corpus SHA-256 chuẩn hóa LF: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.
- Fast-path mặc định: danh sách rỗng; thêm rule/policy mới cần kiểm thử và snapshot freeze mới.

## Hash khóa source và cấu hình

Hash canonical LF là SHA-256 của bytes UTF-8 sau khi đổi CRLF thành LF, giữ nguyên các bytes còn lại. Raw SHA của `rule_router.py` tại smoke Windows là `17af2320286d8db5df26fa78cb10602ab634fbe6dcae1a6e1c8101bf70823a9d`. Canonical LF của source khác cách canonical JSON của Negative Set.

Các hash từng file nằm trong `files_sha256_lf` bên dưới. Hash snapshot tổng hợp: `14acb337f0d8af87ba746418c435d8e8569e569b95bdce4888d57841eb290c8a`. Cách tái lập: parse khối JSON, serialize với `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, thêm một LF cuối rồi SHA-256 UTF-8.

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

SHA Router v5 trước thay đổi explanation là `996bd6a0894aeaf964f188f032961329ec6cdecfe1575bcf80df685aa068f2f7`, source commit `48956492b63238b4d1df323cad06d8547e1cc4b7`. SHA cũ được giữ để truy vết kết quả lịch sử; không dùng thay SHA snapshot bàn giao mới.

## Kết quả kiểm chứng

| Gate | Kết quả |
|---|---|
| Official Gold route/action | 30/30 PASS |
| Dev action LEGAL_RETRIEVAL | 270/270 PASS, vượt ngưỡng 95% |
| Negative v2 route/action thuộc Router | 26/26 PASS |
| Non-legal Negative Set | 6/6 SUCCESS/NOT_RUN; Retrieval=0, LLM=0 |
| Out-of-scope Negative Set | 8/8 ABSTAIN/NOT_RUN/ROUTE_POLICY; Retrieval=0, LLM=0 |
| Legal negative sang NON_LEGAL/GENERAL_CHAT | 0/20 |
| Regression Week10 v1 | 36/36, safety PASS |
| Regression R4IH v1 | 36/36, safety PASS |
| Regression router_holdout.jsonl | 40/40, safety PASS |
| Route/action/reason/version trước và sau sửa boundary | 552/552 khớp, không đọc v6 |
| Router, AskService và smoke tests | 139 passed, 395 subtests passed |
| API và CLI/E2E giả lập | 100 passed |
| Ruff và git diff --check | PASS |

Các bộ v1–v5/R4IH đã tiêu thụ chỉ là regression. Không chạy lại holdout v6 trong đợt bàn giao này. Kết quả 34/36 của v6 thuộc source SHA lịch sử, không phải lần đánh giá độc lập mới trên snapshot `d76244d8`. Xác nhận Dev3 review v6 và giới hạn bằng chứng thời điểm được ghi tại [báo cáo D4.2](../evaluation/router_holdout/router_holdout_report.md).

## Lệnh kiểm chứng

Chạy trong checkout snapshot source đã nêu, bằng Python môi trường repo có dependency requirements:

```powershell
.\.venv\Scripts\python.exe -m pytest -q test/agent/test_rule_router.py test/orchestration/test_ask_service.py test/test_smoke_rule_router.py
.\.venv\Scripts\python.exe -m pytest -q test/api test/e2e
.\.venv\Scripts\python.exe scripts/smoke_rule_router.py --skip-holdout
.\.venv\Scripts\python.exe -m ruff check agent/config.py agent/router orchestration/ask_service.py orchestration/wiring.py test/agent/test_rule_router.py test/orchestration/test_ask_service.py
git diff --check
```

Trong đợt kiểm chứng snapshot, pytest dùng `--basetemp` riêng trong `.pytest-cache-local` và `-p no:cacheprovider`; dependency FastAPI/Starlette/Uvicorn được nạp từ thư mục tạm vì venv gốc chưa cài API. Không đổi requirements hoặc môi trường venv. Không gọi Ollama hay dịch vụ retrieval thật.

## Công nghệ và giới hạn

Python rule-based Router, canonical Pydantic contract, cấu hình Python cố định, pytest/subtests, fake pipeline, Ruff và SHA-256. D4.1 khóa boundary/routing/config; không nghiệm thu thay D4.2 holdout, D4.3 Retrieval Adapter hoặc live UI/API.
