# Hướng dẫn xác minh freeze Router và holdout

Tài liệu này quy định cách kiểm tra Router trước khi freeze và cách đánh giá holdout mà không dùng holdout để tinh chỉnh. Tình trạng cập nhật ngày 2026-11-17: `rule_router_v3` đã được freeze theo ủy quyền của project owner sau khi các pre-freeze gates đạt và policy/consumer contract được xác nhận. Negative Set v2 đã được Dev2 review độc lập và Tech Lead sign-off theo SHA canonical `5584795887e876f15febc05e7f04107b67862492d8a3d027840c01514d75223f`; manifest hiện ghi `review_status=peer_reviewed`. Kết quả 26/26 là smoke evidence theo phần route/action thuộc Router, không phải đánh giá độc lập trên holdout. `router_holdout_week10_v1.jsonl` đạt 22/36 với 14 mismatch, nhưng record lần chạy không lưu Git SHA/classifier version nên không thể gán chắc chắn điểm này cho v3; đây là kết quả lịch sử đã tiêu thụ, không dùng để chỉnh Router hay tuyên bố holdout mới.

## 1. Phân biệt hai việc cần xác minh

- **Freeze Router:** khóa phiên bản mã, cấu hình/policy và corpus liên quan sau khi regression đã đạt; ghi lại phiên bản và SHA để các nhóm dùng cùng một implementation.
- **Đánh giá holdout độc lập:** đo Router đã freeze trên dữ liệu có nhãn được reviewer xác nhận độc lập, chưa dùng để chỉnh Router. Validator tự động chỉ kiểm tra cấu trúc và trùng văn bản; tính đúng pháp lý, trùng chủ đề và độc lập của nhãn vẫn cần con người.

Một holdout đã chạy mà sau đó dùng mismatch để sửa Router trở thành regression data. Không chạy lại nó để tuyên bố điểm holdout sau sửa. Hãy tạo holdout mới với ID/version mới.

## 2. Trách nhiệm và đầu vào cần chốt

| Người/nhóm | Việc cần xác nhận |
|---|---|
| Dev4 (owner) | Chuẩn bị phiên bản Router, test regression, dataset và manifest; không tự ghi nhận review độc lập. |
| Reviewer độc lập (ví dụ Dev2 hoặc thành viên không soạn nhãn) | Rà câu hỏi, expected route/action, reason, phạm vi pháp lý và semantic overlap; ghi tên/ID reviewer, ngày, bất đồng và cách giải quyết. Nên review khi chưa xem dự đoán Router. |
| Tech Lead | Chốt policy còn mở, đặc biệt nhãn `NEG_DEV_026`; xác nhận tiêu chí freeze và ký nhận code/config/schema version. |
| Dev5/consumer Orchestrator | Xác nhận interface route/action và contract canonical mà consumer sẽ import. |

Đầu vào trước khi bắt đầu: mã nguồn Router và test; policy/route contract; corpus/version dùng trong smoke; Dev Gold, Dev benchmark, Negative Set; holdout candidate JSONL và metadata; tiêu chí pass đã được Tech Lead chốt.

## 3. Xác minh dataset holdout

### Kiểm tra tự động

Chạy từ thư mục gốc repo trên Windows:

```powershell
.\.venv\Scripts\python.exe scripts/validate_router_holdout.py --holdout evaluation/router_holdout/router_holdout_week10_v1.jsonl
```

Lệnh phải báo `VALIDATION PASSED`, số bản ghi, phân bố route và đã so khớp với sáu nguồn. Validator kiểm tra JSONL/field bắt buộc, ID và câu hỏi trùng, đủ năm route, mapping route/action và trùng văn bản đã chuẩn hóa với sáu nguồn đối chiếu. Nếu đường dẫn virtualenv khác, dùng Python của môi trường repo tương ứng.

Kết quả pass không chứng minh nhãn đúng, không phát hiện paraphrase/semantic overlap và không tự chứng nhận reviewer độc lập.

### Review thủ công độc lập

Reviewer không phải người soạn/chỉnh holdout cần:

1. Đọc từng query và `reason`; xác nhận vấn đề pháp lý thực sự được hỏi, không gán route chỉ theo từ khóa như “vợ/chồng”.
2. Đối chiếu expected route/action với policy và corpus scope; ghi lại căn cứ và nguồn nếu câu pháp lý.
3. So sánh chủ đề với holdout cũ, Dev, Negative Set và regression; ghi nhận câu diễn đạt khác nhưng kiểm tra cùng một khái niệm.
4. Kiểm tra nhóm `LEGAL_SCOPE_UNCERTAIN`, `MIXED_LEGAL_SCOPE` và `LEGAL_OUT_OF_SCOPE` có lý do phân biệt rõ.
5. Ghi reviewer identity, ngày, phiên bản/SHA file đã review, số câu đồng ý, bất đồng và quyết định xử lý. Không đổi `reviewer_status` thành reviewed nếu chưa có bằng chứng này.

Nên ẩn expected route/action và dự đoán Router trong vòng chấm đầu tiên để giảm thiên lệch. Bất đồng phải được giải quyết và lưu vết trước khi mở nhãn cho người chạy evaluation.

## 4. Xác minh và freeze Router

### Trước freeze

1. Chốt policy còn mở với Tech Lead hoặc project owner có thẩm quyền, lưu quyết định trong manifest, rồi cập nhật test. Policy `NEG_DEV_026` được xác nhận ngày 2026-11-17; Negative Set v2 đã được Dev2 review và Tech Lead sign-off theo SHA canonical nêu trên.
2. Sửa Router chỉ dựa trên regression/Dev hoặc lỗi đã xác định. Không dùng 14 mismatch của holdout v1 để tối ưu Router.
3. Chạy test Router và holdout validator:

```powershell
.\.venv\Scripts\python.exe -m pytest -q test/agent/test_rule_router.py test/test_validate_router_holdout.py
.\.venv\Scripts\ruff.exe check agent/router/rule_router.py scripts/validate_router_holdout.py scripts/smoke_rule_router.py test/agent/test_rule_router.py test/test_validate_router_holdout.py
```

4. Trước freeze, chạy riêng các tập Dev/Negative Set, không mở holdout chưa tiêu thụ:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_rule_router.py --skip-holdout
.\.venv\Scripts\python.exe -m pytest -q test/agent/test_rule_router.py test/test_smoke_rule_router.py
```

   Áp dụng các gate: (a) 0 câu hỏi pháp lý thành `NON_LEGAL`/`GENERAL_CHAT`; (b) Dev Gold route/action đạt 30/30; (c) Dev benchmark action `LEGAL_RETRIEVAL` ít nhất 95% (270 câu); (d) Negative Set 26/26 route và action thuộc sở hữu Router khớp; (e) non-legal 6/6 đi `NON_LEGAL`/`GENERAL_CHAT` và không vào RAG; (f) regression đã định danh đạt ít nhất 90%. Với Negative Set, các action `INSUFFICIENT_EVIDENCE_ABSTENTION` và `CLARIFICATION` là hành vi downstream của Orchestrator, không phải action do Router phát; ở lớp Router, các câu đó phải route `LEGAL_HNGD` và action `LEGAL_RETRIEVAL`. Báo riêng route/action Router-owned, số đếm, mẫu số và mismatch IDs. Không dùng holdout v1 (đã tiêu thụ) để chỉnh rule; 14 mismatch cũ không phải căn cứ tối ưu.
5. Chỉ freeze khi tất cả tiêu chí do Tech Lead chốt đều đạt, policy không còn pending, test pass, và reviewer/consumer đã xác nhận contract. Nếu gate holdout được đặt là exact route/action match, 14/36 mismatch hiện tại là **không đạt** gate đó.

### Ghi nhận freeze

Sau khi các thay đổi được commit, ghi vào manifest/báo cáo freeze:

- `CLASSIFIER_VERSION` (hiện là `rule_router_v3`), Git commit SHA và SHA-256 của file Router.
- SHA-256 corpus/config/policy snapshot có ảnh hưởng đến route.
- Phiên bản canonical schema và mapping route/action.
- Phiên bản test, lệnh chạy, ngày chạy, tổng pass/fail và kết quả từng gate.
- Người review, Tech Lead sign-off, ngày freeze và mọi quyết định policy còn liên quan.

Không ghi freeze bằng SHA của working tree chưa commit. Sau freeze, mọi thay đổi rule/policy làm thay đổi hành vi cần version bump hoặc freeze record mới.

## 5. Đánh giá trên holdout chưa tiêu thụ

Holdout Week 10 v1 đã có dự đoán và 14 mismatch. Có thể giữ v1 làm regression, nhưng để đo độc lập sau freeze cần tạo một holdout mới (ví dụ v2) và bảo vệ nhãn:

1. Tạo câu hỏi mới, không lấy từ official 30, Dev, Negative Set, regression hoặc các holdout đã dùng; chạy exact-overlap validator và semantic review độc lập.
2. Reviewer xác nhận nhãn/reason và ghi identity/date/SHA; lưu nhãn ở nơi người chạy Router không xem trước nếu quy trình cho phép.
3. Freeze Router trước khi mở nhãn evaluation. Ghi commit/version/SHA và xác nhận môi trường đang chạy đúng artifact đó.
4. Chạy đúng một lần trên holdout v2, lưu prediction JSONL và manifest riêng, gồm input SHA, Router SHA, command, timestamp, phân bố route/action, confusion matrix, mismatch IDs và safety violations.
5. Báo cáo kết quả đúng phạm vi. Không sửa Router dựa vào mismatch rồi giữ v2 làm holdout độc lập; sau sửa, v2 trở thành regression và cần holdout mới cho lần đánh giá độc lập tiếp theo.

Ví dụ lệnh chạy sau khi đã có holdout mới và freeze được phê duyệt:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_rule_router.py --holdout evaluation/router_holdout/router_holdout_week10_v2.jsonl
```

Lệnh không truyền `--report` in kết quả ra stdout; khi cần artifact chính thức, dùng report/manifest có tên versioned mới, không ghi đè kết quả đánh giá cũ.

## 6. Checklist sign-off

- [x] Policy `NEG_DEV_026` được project owner xác nhận ngày 2026-11-17 và ghi vào manifest/nhãn; Negative Set v2 được Dev2 review và Tech Lead sign-off theo SHA canonical `5584795887e876f15febc05e7f04107b67862492d8a3d027840c01514d75223f` (`peer_reviewed`).
- [x] Project owner đã ủy quyền freeze `rule_router_v3` ngày 2026-11-17 sau khi chốt policy. Không ghi nhận danh tính Tech Lead riêng biệt trong artifact này.
- [x] Regression/Dev pre-freeze gates đã pass tại working tree hiện tại: Official 30/30; Dev 270/270 retrieval; Negative Set 26/26 theo route và action Router-owned; 6/6 non-legal; không có legal negative sang `NON_LEGAL`/`GENERAL_CHAT`; test Router/holdout 127 passed, 84 subtests.
- [x] Reviewer độc lập hoàn tất semantic/legal label review; identity, ngày và SHA được ghi (`Dev3`, `2026-11-17`, LF SHA-256 `d2cd4087b8d81048e63074b2fdb31aceadd3d18dedc678b956b801693c815e49`).
- [x] Holdout v2 qua validator và semantic overlap review độc lập (`Dev3`, giữ nguyên 36/36 câu & nhãn kèm ghi chú overlap/ranh giới); không dùng v1 đã tiêu thụ để tuyên bố điểm mới.
- [x] Router/config/policy được commit; ghi nhận classifier source commit `f0c7c295f4804dc4a8e37f7a03b60c1519578af7`, evidence commit `10daaad7`, `rule_router_v3`, Router SHA-256 `41b25945b8111ca38bbc3fa2aef302e3c924f23eb4d952eaf37e526073dd107d`, corpus SHA-256 `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`, schema `week10_v1.1`.
- [x] Project owner báo Dev5 đã xác nhận contract route/action ngày 2026-11-17; lưu bằng chứng xác nhận vào handoff/PR trước freeze.
- [x] Project owner báo Dev2 đã review độc lập Negative Set v2.
- [x] Dev2 review độc lập và Tech Lead sign-off Negative Set v2 theo SHA canonical trong manifest; sign-off áp dụng cho artifact SHA `5584795887e876f15febc05e7f04107b67862492d8a3d027840c01514d75223f`.
- [ ] Dev2 xác nhận format bàn giao nếu holdout v2 được dùng cho evaluation.
- [x] Holdout v2 được chạy đúng một lần sau freeze; SHA đầu vào, Router SHA, kết quả và gate outcomes được ghi trong [router_holdout_report.md](../reports/week10/router_holdout_report.md). V2 đã consumed.

## 7. Trạng thái tại thời điểm viết

- `router_holdout_week10_v1.jsonl`: 36 câu, `reviewer_status=DEV4`; owner đã rà soát nhưng chưa có xác nhận reviewer độc lập. Đã tiêu thụ khi chạy (22/36 khớp, 14 mismatch), vì vậy chỉ dùng làm regression.
- `router_holdout_week10_v2.jsonl`: 36 câu, Dev3 review độc lập, validator pass; đã chạy một lần trên frozen `rule_router_v3`: 17/36 exact match, 19 mismatch, 1 legal-to-GENERAL_CHAT safety violation. V2 đã consumed; kết quả ghi trong `reports/week10/router_holdout_report.md`.
- Smoke trên holdout v1: 22/36 route/action khớp, 14 mismatch; run provenance không lưu classifier version/Git SHA, nên không xác nhận được đây là kết quả của v3; đã tiêu thụ.
- Router freeze: `rule_router_v3` đã freeze theo owner authorization, evidence commit `10daaad7`. Holdout v2 không đạt acceptance gates, nhưng kết quả không tự hủy freeze record; không chỉnh v3 theo v2. Muốn sửa cần version mới và holdout mới nếu cần đánh giá độc lập.

## 8. Ứng viên Router v4 sau review

- Ngày 2026-11-17, Router được phát triển tiếp dưới phiên bản mới `rule_router_v4`; freeze record và kết quả `rule_router_v3` ở trên được giữ nguyên như lịch sử.
- V4 sửa va chạm greeting/corporate sale do bỏ dấu, bổ sung nhận diện theo nhóm ngữ cảnh HNGĐ/ngoài phạm vi/mixed và một số intent non-legal. Có regression paraphrase mới, không dùng lại holdout v2 để chỉnh.
- Kiểm tra không dùng holdout: `python scripts/smoke_rule_router.py --skip-holdout` đạt 5/5 gate — Official 30/30, Dev 270/270, Negative Set v2 26/26, non-legal 6/6, legal-to-chat 0. Test tập trung: 130 passed, 105 subtests; Ruff pass.
- Router file SHA-256 tại lần kiểm tra: `44466e654e4536b840707003040d7b668ea726db1e6199e123d2144616fffc94`.
- **V4 chưa freeze và chưa được đánh giá độc lập.** Holdout v2 đã consumed; nếu muốn kết luận chất lượng holdout cho v4, reviewer cần chuẩn bị một holdout mới độc lập sau khi phiên bản này được review/freeze. Không chạy lại v2.
- Chi tiết code, paraphrase tests và gate report: [router_regression.md](../reports/week10/router_regression.md).

## 9. Freeze Router v4.1

- `rule_router_v4_1` đã được freeze ngày 2026-11-17 tại commit `48a9c051dfd14ea0f78e4a708f6aec0526cf3175`.
- SHA-256 `agent/router/rule_router.py`: `2d0ae791e2476afa33a49fc5207496a83faa17c2f22784b33ea3bb0dc8d26a5a`.
- Pre-freeze gates đạt 5/5; smoke bỏ qua holdout. Router tests 53 passed/239 subtests, Negative Set tests 65 passed, Ruff pass.
- Holdout Week 10 v3 chưa chạy; SHA code, SHA holdout và run status được liên kết trong [manifest](../evaluation/router_holdout/router_holdout_week10_v3_manifest.json).
- Freeze chỉ gồm Router source và Router tests trong commit đã nêu; các thay đổi khác trong working tree không thuộc snapshot Router.
- Manifest ghi SHA-256 source theo nội dung LF ổn định và lưu thêm raw working-tree SHA; khi khác line endings, ưu tiên giá trị canonical trong manifest cùng Git commit đã đóng băng.
