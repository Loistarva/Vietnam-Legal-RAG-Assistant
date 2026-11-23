# Rà chuỗi hiệu lực nuôi con nuôi

Lượt tiếp sau commit `45b012c`, ngày23/11/2026. Active giữ **84 văn bản**, tăng từ6.135 lên **6.144 child** và từ2.632 lên **2.638 parent**. Thêm9 child của Điều14 NĐ18/2026 về nuôi con nuôi. Mọi child cũ giữ nguyên ID, nội dung và liên kết parent; chỉ41 child cũ đổi metadata có chủ đích. Không sửa parser, cleaner, chunker, schema, workflow hoặc test.

## Các lỗi dữ liệu đã sửa

**NĐ19/2011:** khoản2 Điều10 NĐ114/2016 bãi bỏ khoản1 Điều38 và Điều39–46 từ01/01/2017. Thêm override cho đúng9 phạm vi này. Đối chiếu cả NĐ114 gốc trong corpus và VBHN410/VBHN-BTP; các thay đổi chỉ bỏ cụm từ tại Điều1.1,38.3 được giữ riêng, không ghi hết hiệu lực toàn Khoản.

**NĐ18/2026:** bổ sung Điều14 vào whitelist cùng Điều13 và17. Điều14 trực tiếp sửa NĐ19/2011 và thuộc nhóm nuôi con nuôi đã có trong corpus. Parsed cũ nhầm số Khoản bên trong đoạn trích thành ranh giới Khoản sửa đổi, khiến nội dung Khoản2,3 lẫn vào Khoản1. Chuẩn hóa bằng cách thêm khoảng trắng trước dấu chấm của số đánh mục bên trong ngoặc kép; bảo toàn toàn bộ ký tự ngoài khoảng trắng. Không đổi số, từ, dấu hoặc quy phạm. Parser hiện tại đọc đúng5 Khoản sửa đổi bên ngoài, mọi Điều khác cho kết quả parsed giống hệt trước.

PDF active mới là **bản phái sinh chuẩn hóa không chữ ký**, không mô tả là PDF Công báo ký gốc. Giữ basename cũ `nd_18_2026_nd_cp_congbao_61` để tương thích danh sách tiêu đề đã duyệt sẵn; loại bản phái sinh được ghi rõ trong metadata và thuộc tính PDF. Giữ PDF ký gốc và SHA-256 tại `data/source_documents/adoption_effectivity_20261123/nd_18_2026_nd_cp_original.pdf`, cùng4 tệp trước chuẩn hóa trong staging/archive. `archive_manifest.json` lưu đường dẫn và SHA-256. PDF, cleaned/extracted text, parsed JSON và PDF manifest được thay đồng bộ; `candidate_normalization.json` và các trang render24–26 là bằng chứng kiểm tra.

**Mốc15/01/2026:** thêm override cho toàn Điều7 và khoản2 Điều31 NĐ19/2011 theo khoản1,3 Điều14 NĐ18/2026. `evidence_context_ids` giữ đủ phần sửa đổi bị chia nhiều chunks theo thứ tự. Không áp mốc này cho toàn Điều35 bản gốc đã được sửa từ2025.

**TT11/2021:** chuyển từ `Không xác định` sang `Sửa đổi bổ sung`, dựa trên khoản5,6 Điều1 và khoản2 Điều2 TT01/2025 đã có nguồn trong corpus. Chỉ xác nhận có sửa đổi, chưa xác nhận hiện hành toàn văn. Số văn bản active chưa xác định hiệu lực giảm từ33 xuống **32**.

## Đồng bộ và giới hạn còn lại

Đồng bộ registry, metadata trong parsed/staging hiện tại, PDF manifest, alias map, production_chunk_index và bảng ánh xạ. Giữ báo cáo đợt trước như snapshot. `all_data_inventory.json` vẫn133 văn bản có tệp và136 mục theo dõi: VBHN410 và các bản gốc/phái sinh không tính thành văn bản corpus mới. Chưa reindex production, chưa thay Gold/Test hoặc tự duyệt alias.

Vẫn còn thay đổi cấp Điểm/cụm từ và bản trung gian cần mô hình hóa: điểm g khoản1 Điều31; khoản2 Điều35 trong phần thay thế NĐ06/2025; các thời hạn tại khoản5 Điều14 NĐ18/2026. Ghi ở `provision_periods.not_applied`, không coi việc thêm hai override là hoàn tất toàn chuỗi. Ba đề xuất vướng hợp đồng bằng chứng từ lượt trước vẫn chờ người phụ trách code; không sửa code để vượt kiểm tra.

`legal_review_queue.json` ghi32 trạng thái chưa xác định cùng các yêu cầu peer review còn lại. `validation_summary.json`, `tests_final.log`, `integrity_checks.json` và `temporal_boundary_checks.json` ghi kết quả kiểm tra cuối.

Nguồn đối chiếu bổ sung: [VBHN410/VBHN-BTP](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/01/410-vbhn-btp.pdf). Văn bản hợp nhất dùng để đối chiếu, không thay bản gốc trong parser hoặc tự trở thành một văn bản active mới.
