# Hướng dẫn xác minh freeze Router và holdout

Tài liệu này quy định cách kiểm tra Router trước khi freeze và cách đánh giá holdout mà không dùng holdout để tinh chỉnh. Tình trạng hiện tại của Week 10: Router `rule_router_v3` chưa freeze; `router_holdout_week10_v1.jsonl` đã được chạy, đạt 22/36 route/action và có 14 mismatch. Vì vậy v1 là dữ liệu đã tiêu thụ cho lần đánh giá này, không được dùng làm holdout chưa thấy để công bố kết quả tổng quát hóa.

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

1. Tech Lead chốt policy còn mở, bao gồm `NEG_DEV_026`; cập nhật test theo quyết định được duyệt.
2. Sửa Router chỉ dựa trên regression/Dev hoặc lỗi đã xác định. Không dùng 14 mismatch của holdout v1 để tối ưu Router.
3. Chạy test Router và holdout validator:

```powershell
.\.venv\Scripts\python.exe -m pytest -q test/agent/test_rule_router.py test/test_validate_router_holdout.py
.\.venv\Scripts\ruff.exe check agent/router/rule_router.py scripts/validate_router_holdout.py scripts/smoke_rule_router.py test/agent/test_rule_router.py test/test_validate_router_holdout.py
```

4. Chạy smoke trên Dev Gold, toàn bộ Dev benchmark và Negative Set theo script `scripts/smoke_rule_router.py`; áp dụng đầy đủ các gate trước khi freeze: (a) 0 câu hỏi pháp lý bị route thành `NON_LEGAL`/`GENERAL_CHAT`; (b) Dev Gold đạt 30/30; (c) Dev benchmark tối thiểu 270 câu đạt route/action retrieval kỳ vọng (>=95%); (d) Negative Set đạt 26/26 nhãn route/action đã chốt, gồm NEG_DEV_025 và NEG_DEV_026; (e) non-legal không đi vào RAG; và (f) regression đạt ít nhất 90%. Lưu số đếm, mẫu số, mismatch IDs và lệnh chạy cho từng gate. Nếu gate/định nghĩa nhãn chưa được Tech Lead chốt, chưa freeze.
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

- [x] Policy route/action được Tech Lead chốt: `NEG_DEV_025`/`NEG_DEV_026` là `legal_out_of_scope` + `policy_abstention`; bạo lực gia đình chỉ hỏi biện pháp/quyền/nghĩa vụ HNGĐ thì in-scope, chỉ hỏi xử lý hình sự thì out-of-scope, hỏi cả hai thì mixed.
- [ ] Regression/Dev gates đã pass và có lệnh + kết quả.
- [x] Reviewer độc lập hoàn tất semantic/legal label review; identity, ngày và SHA được ghi (`Dev3`, `2026-11-17`, LF SHA-256 `d2cd4087b8d81048e63074b2fdb31aceadd3d18dedc678b956b801693c815e49`).
- [x] Holdout v2 qua validator và semantic overlap review độc lập (`Dev3`, giữ nguyên 36/36 câu & nhãn kèm ghi chú overlap/ranh giới); không dùng v1 đã tiêu thụ để tuyên bố điểm mới.
- [ ] Router/config/policy được commit; version, commit SHA, source SHA và corpus SHA đã ghi.
- [ ] Consumer (Dev5) xác nhận contract; Dev2 xác nhận format bàn giao nếu dùng cho evaluation.
- [ ] Holdout mới được chạy đúng một lần sau freeze; predictions/manifest được lưu và không bị ghi đè.

## 7. Trạng thái tại thời điểm viết

- `router_holdout_week10_v1.jsonl`: 36 câu, `reviewer_status=DEV4`; owner đã rà soát nhưng chưa có xác nhận reviewer độc lập. Đã tiêu thụ khi chạy (22/36 khớp, 14 mismatch), vì vậy chỉ dùng làm regression.
- `router_holdout_week10_v2.jsonl`: 36 câu mới, đã hoàn tất review độc lập bởi `Dev3` (`2026-11-17`, `reviewer_status=INDEPENDENT_REVIEW_COMPLETE`, giữ nguyên 36/36 câu & nhãn); validator exact-text pass trên sáu nguồn. Chưa chạy Router trên v2.
- Smoke v1: 22/36 route/action khớp, 14 mismatch; đã tiêu thụ.
- Router freeze: chưa đạt; cần Dev 4 xử lý regression để pass toàn bộ Freeze Gate và ghi nhận freeze SHA trước khi chạy holdout v2.
