# Review 28 bản ghi hiệu lực - PR #35

Ngày kiểm: 07/11/2026 (Asia/Saigon). Mốc review cập nhật: `e0cea3535ac17dda9e67513c70f8a55fe2bb8448` trên `origin/fix/leftover-after-0211`. Kiểm chi tiết 28 bản ghi và các artifact nguồn ban đầu thực hiện tại `032fe844a2676947484986acb93fb8270693060f`; đã đối chiếu diff tới mốc mới: chỉ thay ghi chú, 28 override và corpus giữ nguyên, nên kết quả kiểm bên dưới vẫn áp dụng.

## Kết luận

Đã đối chiếu 28/28 sự kiện trong provision_periods.json với văn bản nguồn, ngày hiệu lực, phạm vi và evidence_chunk_id. 28/28 có chunk dẫn đúng văn bản sửa đổi; 162 chunk bị tác động có metadata đúng theo cấu hình. 7/7 PDF trong repo khớp SHA-256 manifest. Đây là kiểm nhất quán với manifest, không phải xác thực chữ ký số hay bằng chứng mọi PDF byte-for-byte giống file tải hôm nay.

21 bản ghi chưa thấy vấn đề trong phạm vi sự kiện đã đối chiếu; 7 bản ghi cần theo dõi thêm. Không nên đánh dấu toàn bộ D1 đã duyệt xong. Các ngày và phạm vi được đối chiếu là của sự kiện sửa/bãi bỏ ghi trong file; kết quả này không xác nhận mọi nội dung vẫn còn hiệu lực tới 07/11/2026. Lead đã rà soát bổ sung và ghi nhận tại commit `e0cea35`, gồm ghi chú về Luật 81/2025 và NĐ 120/2025. Theo scope_note mới, phần rà soát dùng trang tổng hợp chưa đối chiếu Công báo và chưa có Dev 1 xác nhận duyệt pháp lý; vì vậy chưa coi đây là xác nhận đầy đủ tình trạng hiệu lực hiện hành. Báo cáo này ghi nhận phần bổ sung của lead, chưa độc lập xác minh các kết luận mới đó.

Không sửa corpus, không thay review_status/verified_by trong repo và không thay mặt Nqh1126 xác nhận duyệt pháp lý. Không chạy pytest vì Python không sẵn trong môi trường shell; đã chạy kiểm dữ liệu độc lập bằng JavaScript và đọc mã bộ lọc temporal.

## Việc cần xử lý trước khi xác nhận hoàn tất

### F1 - Cao: một chunk gộp hai phiên bản có thời hạn khác nhau

Bản ghi số 8: `nd_123_2015_art_2_clauses_1_2_amended`.

- Căn cứ: khoản 2 Điều 2 NĐ 07/2025 sửa hai Khoản của NĐ 123/2015. Khoản 1 Điều 13 NĐ 18/2026 tiếp tục sửa khoản 1 Điều 2 từ 15/01/2026. Xem [nguồn NĐ18/2026](https://congbaocdn.chinhphu.vn/180507251028987904/2026/1/29/18signed-1769674108244123996285.pdf#page=29), trang PDF 29-30; mốc hiệu lực ở trang 35.
- Corpus hiện tại: `nd_07_2025_nd_cp_art_2_clause_2_chunk_1` chứa cả khoản 1 và phần đầu khoản 2; `metadata.effective_to = null`. Bộ lọc trong retrieval/temporal.py kiểm thời gian trên toàn chunk nên vẫn cho chunk này qua tại 15/01/2026. Đây là chứng minh chunk đủ điều kiện qua bộ lọc, không phải khẳng định nó chắc chắn xuất hiện trong top-k của mọi truy vấn.
- Đề nghị: tách theo từng quy định được sửa; chỉ phần khoản 1 phiên bản 2025 kết thúc ngày 15/01/2026. Giữ khoản 2 và đoạn miễn nộp bản giấy theo hiệu lực riêng. Không gắn ngày hết hiệu lực cho cả chunk đang gộp. Nếu đổi ID, kiểm candidate/gold và sinh lại corpus/index trong một thay đổi riêng.
- Giới hạn này đã được tác giả ghi ở not_applied; nó vẫn là khoảng trống của việc bảo đảm không trả nội dung cũ.

### F2 - Trung bình: hai evidence_chunk_id thiếu câu dẫn bãi bỏ

Bản ghi số 1 và 2 đều dẫn `nd_123_2015_nd_cp_art_45_clause_2_chunk_2`. Chunk này chỉ chứa danh sách ở điểm đ. Câu dẫn nêu hành vi bãi bỏ nằm ở `..._chunk_1`. Văn bản nguồn xác nhận phạm vi và ngày là đúng (PDF trong repo, trang 22; Công báo trang in 23).

Đề nghị hỗ trợ evidence_context_ids gồm cả chunk_1 và chunk_2, hoặc lấy parent clause khi trình bày chứng cứ. Không đổi sang chỉ chunk_1 vì sẽ mất điểm đ xác định phạm vi. Đây là lỗi thiếu ngữ cảnh khi dùng một chunk độc lập, không phải sai căn cứ trong toàn văn.

### F3 - Trung bình: bốn chunk dẫn không chứa đủ nội dung thay thế

Các bản ghi 7, 8, 15, 22 dẫn chunk_1 của các Khoản sau trong NĐ07/2025: Đ2 k1, Đ2 k2, Đ2 k9, Đ3 k1. Phần tiếp theo nằm ở chunk_2. Chunk_1 đủ nhận diện sự kiện sửa đổi; không đủ để coi là toàn bộ căn cứ trả lời về nội dung mới.

Đề nghị lưu nhóm evidence hoặc mở rộng cùng parent clause khi retrieval lấy chứng cứ. Không xếp đây là bốn ngày hiệu lực sai.

### F4 - Cần làm rõ: TT30/2019 vừa có điều khoản sửa vừa có câu bãi bỏ cùng phạm vi

Bản ghi số 4 đặt repealed cho khoản 2-3 Điều 2 TT34/2017. Điều 2 khoản 2 [PDF chính thức](https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/03/30-byt.pdf#page=2) thực sự có câu bãi bỏ này; ngày 01/02/2020 khớp. Tuy nhiên Điều 1 khoản 1-2 của cùng văn bản cũng ghi định nghĩa thay thế cho hai Khoản. Vì vậy không tự đổi trạng thái chỉ dựa vào suy luận. Cần người duyệt làm rõ cách biểu diễn bản cũ và bản mới, và bảo đảm nội dung thay thế vẫn truy xuất được.

## Bảng từng bản ghi

“Khớp” chỉ áp dụng cho sự kiện và nguồn đã kiểm. Cột số chunk là số chunk mục tiêu nhận override; không phải số chunk dẫn chứng. Trang nguồn được ghi riêng theo văn bản ở cuối báo cáo.

| STT | ID bản ghi | Căn cứ trong văn bản sửa | Ngày kết thúc bản cũ | Chunk mục tiêu | Kết quả |
|---|---|---|---|---:|---|
| 1 | `nd_126_2014_art_19_50_repealed` | nd_123_2015_nd_cp: Đ45 k2 đ | 2016-01-01 | 101 | Cần theo dõi: F2 |
| 2 | `nd_126_2014_art_63_clause_1_point_a_repealed` | nd_123_2015_nd_cp: Đ45 k2 đ | 2016-01-01 | 1 | Cần theo dõi: F2 |
| 3 | `nd_126_2014_art_63_clause_2_amended` | nd_123_2015_nd_cp: Đ45 k3 | 2016-01-01 | 1 | Khớp |
| 4 | `tt_34_2017_art_2_clauses_2_3_repealed` | tt_30_2019_tt_byt: Đ2 k2; đối chiếu thêm Đ1 k1-2 | 2020-02-01 | 2 | Cần theo dõi: F4 |
| 5 | `tt_57_2015_chapters_1_2_5_6_repealed` | tt_38_2025_tt_byt: Đ7 k2 | 2025-10-01 | 27 | Khớp |
| 6 | `nd_123_2015_art_12_clauses_1_2_repealed` | nd_87_2020_nd_cp: Đ25 k2 | 2020-09-15 | 2 | Khớp |
| 7 | `nd_123_2015_art_1_amended` | nd_07_2025_nd_cp: Đ2 k1 | 2025-01-09 | 2 | Cần theo dõi: F3 |
| 8 | `nd_123_2015_art_2_clauses_1_2_amended` | nd_07_2025_nd_cp: Đ2 k2; tiếp nối Đ13 k1 NĐ18/2026 | 2025-01-09 | 2 | Cần theo dõi: F1, F3 |
| 9 | `nd_123_2015_art_3_clause_1_amended` | nd_07_2025_nd_cp: Đ2 k3 b | 2025-01-09 | 1 | Khớp |
| 10 | `nd_123_2015_art_4_clause_1_point_c_amended` | nd_07_2025_nd_cp: Đ2 k4 | 2025-01-09 | 1 | Khớp |
| 11 | `nd_123_2015_art_9_clause_2_amended` | nd_07_2025_nd_cp: Đ2 k5 | 2025-01-09 | 1 | Khớp |
| 12 | `nd_123_2015_art_10_clause_1_repealed` | nd_07_2025_nd_cp: Đ2 k10 | 2025-01-09 | 1 | Khớp |
| 13 | `nd_123_2015_art_22_clause_4_amended` | nd_07_2025_nd_cp: Đ2 k6 | 2025-01-09 | 1 | Khớp |
| 14 | `nd_123_2015_art_23_clause_2_amended` | nd_07_2025_nd_cp: Đ2 k7 | 2025-01-09 | 1 | Khớp |
| 15 | `nd_123_2015_art_30_clause_3_amended` | nd_07_2025_nd_cp: Đ2 k9 | 2025-01-09 | 1 | Cần theo dõi: F3 |
| 16 | `nd_123_2015_art_22_clause_2_amended` | nd_18_2026_nd_cp: Đ13 k2 | 2026-01-15 | 1 | Khớp |
| 17 | `nd_123_2015_art_24_clause_2_amended` | nd_18_2026_nd_cp: Đ13 k3 | 2026-01-15 | 1 | Khớp |
| 18 | `nd_123_2015_art_26_clause_1_point_c_amended` | nd_18_2026_nd_cp: Đ13 k4 a | 2026-01-15 | 1 | Khớp |
| 19 | `nd_123_2015_art_26_clause_2_amended` | nd_18_2026_nd_cp: Đ13 k4 b | 2026-01-15 | 2 | Khớp |
| 20 | `nd_123_2015_art_27_clause_2_amended` | nd_18_2026_nd_cp: Đ13 k5 | 2026-01-15 | 2 | Khớp |
| 21 | `nd_123_2015_art_26_27_clause_3_repealed` | nd_18_2026_nd_cp: Đ13 k6 | 2026-01-15 | 2 | Khớp |
| 22 | `nd_87_2020_art_2_clause_2_amended` | nd_07_2025_nd_cp: Đ3 k1 | 2025-01-09 | 1 | Cần theo dõi: F3 |
| 23 | `nd_87_2020_art_8_clause_2_amended` | nd_07_2025_nd_cp: Đ3 k2 | 2025-01-09 | 1 | Khớp |
| 24 | `nd_87_2020_art_12_clause_3_point_c_amended` | nd_07_2025_nd_cp: Đ3 k3 | 2025-01-09 | 1 | Khớp |
| 25 | `nd_87_2020_art_13_clauses_1_2_amended` | nd_07_2025_nd_cp: Đ3 k4 | 2025-01-09 | 2 | Khớp |
| 26 | `nd_87_2020_art_19_clause_7_amended` | nd_07_2025_nd_cp: Đ3 k5 | 2025-01-09 | 1 | Khớp |
| 27 | `tt_04_2020_art_3_clause_2_amended` | tt_04_2024_tt_btp: Đ2 k1 a | 2024-06-06 | 1 | Khớp |
| 28 | `tt_04_2020_art_18_clause_2_amended` | tt_04_2024_tt_btp: Đ2 k3 | 2024-06-06 | 1 | Khớp |

## Nguồn và vị trí đối chiếu

Trang PDF đánh số từ 1. Với TT30/2019 và TT38/2025, PDF trong repo là bản dàn lại, khác số trang PDF Chính phủ; đã đối chiếu riêng điều khoản trên nguồn chính thức trực tuyến. NĐ123/2015 đối chiếu nội dung bản Công báo trong repo và ngày hiệu lực trên trang Chính phủ; chưa tải lại toàn bộ PDF nguồn của văn bản này.

- [nd_123_2015_nd_cp](https://vanban.chinhphu.vn/?pageid=27160&docid=182158): trang 22-23; căn cứ ngày: Điều 45 khoản 1. PDF repo: `data/raw_data/additional_documents/Nghị định 1232015NĐ-CP.pdf`; SHA-256: `b39a37a54e3aec6431ed5c24dbd1f28275599bbd35c6d8478191d1bec24b7376`.
- [tt_30_2019_tt_byt](https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/03/30-byt.pdf): trang 2 (PDF chính thức); 1 (PDF trong repo); căn cứ ngày: Điều 2 khoản 1. PDF repo: `data/raw_data/additional_documents/TT_30_2019_BYT.pdf`; SHA-256: `30fbf0b68424527f695cca0361644785327bbb540350479c12fad2d8fb7bd808`.
- [tt_38_2025_tt_byt](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/8/38-byt.pdf): trang 5 (PDF chính thức); 3 (PDF trong repo); căn cứ ngày: Điều 7 khoản 1. PDF repo: `data/raw_data/additional_documents/38_2025_TT-BYT_669119.pdf`; SHA-256: `b1e46cb699d0dad5c8e9bf66f9bf0089fe467eae8f1050da5f797f0bd9d97251`.
- [nd_87_2020_nd_cp](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2020/7/31814/32138-1-2020823-82487-2020-nd-cp.pdf): trang 18; căn cứ ngày: Điều 25 khoản 1. PDF repo: `data/raw_data/additional_documents/nd_87_2020_nd_cp_congbao_823_824.pdf`; SHA-256: `7c168f73e39170476d97a6fc51607a56b86b560484a4fb64c63b108206e50a55`.
- [nd_07_2025_nd_cp](https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/1/43907/54364-1-2025191-19207-2025-nd-cp.pdf): trang 2-8; hiệu lực: 12; căn cứ ngày: Điều 5 khoản 1; ký ngày 09/01/2025. PDF repo: `data/raw_data/additional_documents/nd_07_2025_nd_cp_congbao_191_192.pdf`; SHA-256: `0cc9c4f1347dadf93f43022414ffd31f790e4afe8bcd071d1dbf342334cbe0b5`.
- [nd_18_2026_nd_cp](https://congbaocdn.chinhphu.vn/180507251028987904/2026/1/29/18signed-1769674108244123996285.pdf): trang 29-31; hiệu lực: 35; căn cứ ngày: Điều 17 khoản 1. PDF repo: `data/raw_data/additional_documents/nd_18_2026_nd_cp_congbao_61.pdf`; SHA-256: `c75d72ff811a794004f71c7246aa989c335c3522eaa28e91eedfb5538374c134`.
- [tt_04_2024_tt_btp](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/6/04-btp.pdf): trang 4; hiệu lực: 5; căn cứ ngày: Điều 4 khoản 1. PDF repo: `data/raw_data/additional_documents/tt_04_2024_tt_btp.pdf`; SHA-256: `58e05dae781e2032054de6674072e9076248d6e97b1e753ab97a47cc2b335d57`.

## Kết quả kiểm tự động

- 28/28 evidence tồn tại, cùng document_id với changed_by.
- 28/28 effective_to khớp effective_date của văn bản sửa trong registry; ngày được đối chiếu thêm với nguồn như trên.
- 162/162 chunk trong phạm vi khớp effective_to và provision_status ở metadata; không thấy scope nào không có chunk mục tiêu.
- Phạm vi chương của TT57/2015 tương ứng Điều 1-6, 30-33 trong parsed JSON; khớp danh sách override.
- 7/7 SHA-256 PDF khớp manifest trong snapshot.
- Tái hiện F1: effective_from <= 2026-01-15 và effective_to null ở chunk gộp nên is_effective_at sẽ trả true. Chưa chạy truy vấn retrieval top-k hoặc benchmark.

Chi tiết đầy đủ evidence_chunk_id, nguồn, ghi chú từng dòng: [pr35_provision_periods_review.json](pr35_provision_periods_review.json). Kiểm cấu trúc: [pr35_structural_checks.json](pr35_structural_checks.json). Kiểm bổ sung và tái hiện F1: [pr35_additional_checks.json](pr35_additional_checks.json). Các JSON ghi kết quả kiểm tại snapshot ban đầu 032fe84; diff tới e0cea35 chỉ đổi ghi chú.

## Điều kiện đóng phần review này

1. Xử lý hoặc ghi rõ phạm vi chấp nhận F1; không tuyên bố loại hết nội dung cũ khi chunk gộp còn tồn tại.
2. Bổ sung ngữ cảnh evidence cho F2/F3 hoặc chứng minh luồng retrieval đã lấy đủ parent clause.
3. Ghi quyết định có căn cứ cho F4, không tự suy diễn ý chí cơ quan ban hành.
4. Người phụ trách pháp lý đọc và xác nhận kết quả; không gán tên/verified_by của người dùng từ báo cáo hỗ trợ này.
