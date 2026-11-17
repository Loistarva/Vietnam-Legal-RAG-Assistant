# DATA - Legal RAG Assistant

## 1. Giới thiệu

Thư mục `data/` lưu trữ và quản lý dữ liệu pháp luật đầu vào cho dự án Legal RAG Assistant.

Dữ liệu được sử dụng để xây dựng Knowledge Base (KB), phục vụ quá trình truy xuất thông tin và trả lời câu hỏi pháp luật bằng Retrieval-Augmented Generation (RAG).

## 2. Cấu trúc thư mục

```text
data/
├── raw_data/
│   ├── laws_and_decrees/
│   └── circulars/
├── legal_documents_master.xlsx
├── data_quality_report.docx
└── README.md
```

### Mô tả

| Thành phần | Chức năng |
|---|---|
| `raw_data/` | Lưu trữ các văn bản pháp luật gốc. |
| `laws_and_decrees/` | Chứa các file Luật và Nghị định. |
| `circulars/` | Chứa các file Thông tư. |
| `legal_documents_master.xlsx` | Danh mục tổng hợp và metadata của văn bản pháp luật. |
| `data_quality_report.docx` | Báo cáo kết quả kiểm tra chất lượng dữ liệu. |
| `README.md` | Hướng dẫn tổ chức, đặt tên và quản lý dữ liệu. |

## 3. Quy tắc đặt tên file
### 3.1. Quy tắc quản lý tên file văn bản gốc

Các văn bản pháp luật được lưu dưới dạng file PDF/DOCX , bao gồm đầy đủ các Chương, Điều, Khoản. 

- Giữ nguyên tên file gốc nếu đã lấy trên thư viện pháp luật.
- Đường dẫn file phải được ghi chính xác trong bảng kiểm kê.

Ví dụ:

```text
raw_data/
├── laws_and_decrees/
│   ├── [các file Luật và Nghị định gốc]
│   └── ...
└── circulars/
    ├── [các file Thông tư gốc]
    └── ...
```

### 3.2. Quy tắc định danh Điều và chunk

Khi xử lý dữ liệu để xây dựng Knowledge Base, hệ thống sẽ trích xuất nội dung từ file gốc và tạo mã định danh cho từng Điều hoặc chunk.

Hệ thống sử dụng bảng ánh xạ chuẩn hóa chính thức giữa mã file quản lý (`file_code`), định danh hệ thống slug (`document_id`), và số hiệu văn bản:

| Mã File (`file_code`) | Định danh hệ thống (`document_id`) | Số hiệu văn bản (`document_number`) | Trạng thái hiệu lực (`validity_status`) | Tên văn bản |
| :--- | :--- | :--- | :--- | :--- |
| **L01** | `l_52_2014_qh13` | 52/2014/QH13 | Còn hiệu lực | Luật Hôn nhân và gia đình 2014 |
| **ND01** | `nd_126_2014_nd_cp` | 126/2014/NĐ-CP | Sửa đổi bổ sung | Quy định chi tiết một số điều và biện pháp thi hành Luật Hôn nhân và gia đình |
| **ND02** | `nd_207_2025_nd_cp` | 207/2025/NĐ-CP | Còn hiệu lực | Quy định về sinh con bằng kỹ thuật hỗ trợ sinh sản và điều kiện mang thai hộ vì mục đích nhân đạo |
| **ND03** | `nq_01_2024_nq_hdtp` | 01/2024/NQ-HĐTP | Còn hiệu lực | Hướng dẫn áp dụng một số quy định của pháp luật trong giải quyết vụ việc về hôn nhân và gia đình |
| **TT01** | `ttlt_01_2016_ttlt_tandtc` | 01/2016/TTLT-TANDTC-VKSNDTC-BTP | Còn hiệu lực | Hướng dẫn thi hành một số quy định của Luật Hôn nhân và gia đình |
| **TT02** | `tt_02a_2015_tt_btp` | 02a/2015/TT-BTP | Hết hiệu lực | Hướng dẫn thi hành một số điều của Nghị định số 126/2014/NĐ-CP ngày 31 tháng 12 năm 2014 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **TT03** | `tt_32_2016_tt_byt` | 32/2016/TT-BYT | Còn hiệu lực | Quy định việc chi trả các chi phí thực tế để bảo đảm chăm sóc sức khỏe sinh sản của bên nhờ mang thai hộ vì mục đích nhân đạo |
| **TT04** | `tt_34_2017_tt_byt` | 34/2017/TT-BYT | Sửa đổi bổ sung | Hướng dẫn tư vấn, sàng lọc, chẩn đoán, điều trị trước sinh và sơ sinh |
| **TT05** | `tt_30_2019_tt_byt` | 30/2019/TT-BYT | Không xác định | Sửa đổi, bổ sung một số điều của Thông tư số 34/2017/TT-BYT ngày 18 tháng 8 năm 2017 của Bộ trưởng Bộ Y tế hướng dẫn tư vấn, sàng lọc, chẩn đoán, điều trị trước sinh và sơ sinh |
| **L02** | `l_22_2000_qh10` | 22/2000/QH10 | Hết hiệu lực | Luật Hôn nhân và gia đình 2000 |
| **L03** | `l_21_lct_hdnn7` | 21-LCT/HĐNN7 | Hết hiệu lực | Luật Hôn nhân và gia đình 1986 |
| **ND05** | `nd_70_2001_nd_cp` | 70/2001/NĐ-CP | Hết hiệu lực | Quy định chi tiết thi hành Luật Hôn nhân và gia đình |
| **ND06** | `nd_32_2002_nd_cp` | 32/2002/NĐ-CP | Hết hiệu lực | Quy định việc áp dụng Luật Hôn nhân và gia đình đối với các dân tộc thiểu số |
| **ND07** | `nd_68_2002_nd_cp` | 68/2002/NĐ-CP | Hết hiệu lực | Quy định chi tiết thi hành một số điều của Luật Hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **ND08** | `nd_77_2001_nd_cp` | 77/2001/NĐ-CP | Hết hiệu lực | Quy định chi tiết về đăng ký kết hôn theo Nghị quyết số 35/2000/QH10 của Quốc hội về việc thi hành Luật Hôn nhân và gia đình |
| **TT06** | `tt_07_2001_tt_btp` | 07/2001/TT-BTP | Hết hiệu lực | Hướng dẫn thi hành một số quy định của Nghị định số 77/2001/NĐ-CP ngày 22 tháng 10 năm 2001 của Chính phủ quy định chi tiết về đăng ký kết hôn theo Nghị quyết số 35/2000/QH10 của Quốc hội |
| **TT07** | `tt_07_2002_tt_btp` | 07/2002/TT-BTP | Hết hiệu lực | Hướng dẫn thi hành một số điều của Nghị định số 68/2002/NĐ-CP ngày 10 tháng 7 năm 2002 của Chính phủ quy định chi tiết thi hành một số điều của Luật Hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **TT08** | `tt_15_2015_tt_btp` | 15/2015/TT-BTP | Hết hiệu lực | Quy định chi tiết thi hành một số điều của Luật Hộ tịch và Nghị định số 123/2015/NĐ-CP ngày 15 tháng 11 năm 2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch |
| **ND04** | `nd_10_2015_nd_cp` | 10/2015/NĐ-CP | Hết hiệu lực | Quy định về sinh con bằng kỹ thuật thụ tinh trong ống nghiệm và điều kiện mang thai hộ vì mục đích nhân đạo |
| **TT09** | `tt_04_2020_tt_btp` | 04/2020/TT-BTP | Sửa đổi bổ sung | Quy định chi tiết thi hành một số điều của Luật Hộ tịch và Nghị định số 123/2015/NĐ-CP ngày 15 tháng 11 năm 2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch |
| **TT10** | `tt_57_2015_tt_byt` | 57/2015/TT-BYT | Sửa đổi bổ sung | Quy định chi tiết một số điều của Nghị định số 10/2015/NĐ-CP ngày 28 tháng 01 năm 2015 của Chính phủ quy định về sinh con bằng kỹ thuật thụ tinh trong ống nghiệm và điều kiện mang thai hộ vì mục đích nhân đạo |
| **TT11** | `tt_38_2025_tt_byt` | 38/2025/TT-BYT | Còn hiệu lực | Quy định chi tiết một số điều của Nghị định số 207/2025/NĐ-CP ngày 15 tháng 7 năm 2025 của Chính phủ quy định về sinh con bằng kỹ thuật hỗ trợ sinh sản và điều kiện mang thai hộ vì mục đích nhân đạo |
| **ND09** | `nd_123_2015_nd_cp` | 123/2015/NĐ-CP | Sửa đổi bổ sung | Quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch |
| **L04** | `l_81_2025_qh15` | 81/2025/QH15 | Còn hiệu lực | Luật sửa đổi, bổ sung một số điều của Luật Tổ chức Tòa án nhân dân |
| **ND12** | `nd_87_2020_nd_cp` | 87/2020/NĐ-CP | Sửa đổi bổ sung | Quy định về Cơ sở dữ liệu hộ tịch điện tử, đăng ký hộ tịch trực tuyến |
| **ND11** | `nd_07_2025_nd_cp` | 07/2025/NĐ-CP | Sửa đổi bổ sung | Sửa đổi, bổ sung một số điều của các Nghị định trong lĩnh vực hộ tịch, quốc tịch, chứng thực |
| **ND13** | `nd_18_2026_nd_cp` | 18/2026/NĐ-CP | Còn hiệu lực | Sửa đổi, bổ sung một số nghị định để cắt giảm, đơn giản hóa thủ tục hành chính, điều kiện kinh doanh thuộc phạm vi quản lý của Bộ Tư pháp |
| **TT13** | `tt_04_2024_tt_btp` | 04/2024/TT-BTP | Còn hiệu lực | Sửa đổi, bổ sung một số điều của Thông tư số 02/2020/TT-BTP ngày 08/4/2020 của Bộ trưởng Bộ Tư pháp ban hành, hướng dẫn sử dụng, quản lý mẫu sổ quốc tịch và mẫu giấy tờ về quốc tịch và Thông tư số 04/2020/TT-BTP ngày 28/5/2020 của Bộ trưởng Bộ Tư pháp quy định chi tiết thi hành một số điều của Luật Hộ tịch và Nghị định số 123/2015/NĐ-CP ngày 15/11/2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch |
| **L10** | `l_102_2016_qh13` | 102/2016/QH13 | Sửa đổi bổ sung | Luật Trẻ em |
| **BL02** | `bl_92_2015_qh13` | 92/2015/QH13 | Sửa đổi bổ sung | Bộ Luật Tố tụng dân sự |
| **L11** | `l_34_2024_qh15` | 34/2024/QH15 | Sửa đổi bổ sung | Luật Tổ chức Tòa án nhân dân |
| **ND21** | `nd_24_2019_nd_cp` | 24/2019/NĐ-CP | Sửa đổi bổ sung | Sửa đổi, bổ sung một số điều của Nghị định số 19/2011/NĐ-CP ngày 21 tháng 3 năm 2011 của Chính phủ quy định chi tiết thi hành một số điều của Luật nuôi con nuôi |
| **ND22** | `nd_06_2025_nd_cp` | 06/2025/NĐ-CP | Không xác định | Sửa đổi, bổ sung một số điều của các Nghị định về nuôi con nuôi |
| **TT15** | `tt_07_2023_tt_btp` | 07/2023/TT-BTP | Sửa đổi bổ sung | Sửa đổi Thông tư 10/2020 về nuôi con nuôi |
| **ND23** | `nd_104_2022_nd_cp` | 104/2022/NĐ-CP | Không xác định | Sửa đổi, bổ sung một số điều của các nghị định liên quan đến việc nộp, xuất trình sổ hộ khẩu, sổ tạm trú giấy khi thực hiện thủ tục hành chính, cung cấp dịch vụ công |
| **ND24** | `nd_120_2025_nd_cp` | 120/2025/NĐ-CP | Không xác định | Quy định về phân định thẩm quyền của chính quyền địa phương 02 cấp trong lĩnh vực quản lý nhà nước của Bộ Tư pháp |
| **L12** | `l_85_2025_qh15` | 85/2025/QH15 | Không xác định | Luật sửa đổi, bổ sung một số điều của Bộ Luật tố tụng dân sự, Luật Tố tụng hành chính, Luật Tư pháp người chưa thành niên, Luật Phá sản và Luật Hòa giải, đối thoại tại Tòa án |
| **TT17** | `tt_10_2025_tt_btp` | 10/2025/TT-BTP | Không xác định | Sửa đổi, bổ sung một số điều của Thông tư số 10/2020/TT-BTP ngày 28 tháng 12 năm 2020 của Bộ trưởng Bộ Tư pháp ban hành, hướng dẫn việc ghi chép, sử dụng, quản lý và lưu trữ Sổ, mẫu giấy tờ, hồ sơ nuôi con nuôi được sửa đổi, bô sung một số điều theo Thông tư số 07/2023/TT-BTP |
| **ND25** | `nd_63_2024_nd_cp` | 63/2024/NĐ-CP | Sửa đổi bổ sung | Quy định việc thực hiện liên thông điện tử 02 nhóm thủ tục hành chính: Đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi; đăng ký khai tử, xóa đăng ký thường trú, giải quyết mai táng phí, tử tuất |
| **L13** | `l_58_2020_qh14` | 58/2020/QH14 | Sửa đổi bổ sung | Luật Hòa giải, đối thoại tại tòa án |
| **TT18** | `tt_01_2022_tt_btp` | 01/2022/TT-BTP | Sửa đổi bổ sung | Quy định chi tiết một số điều và biện pháp thi hành Nghị định số 87/2020/NĐ-CP ngày 28 tháng 7 năm 2020 của Chính phủ quy định về Cơ sở dữ liệu hộ tịch điện tử, đăng ký hộ tịch trực tuyến |
| **TT19** | `tt_03_2023_tt_btp` | 03/2023/TT-BTP | Không xác định | Sửa đổi Thông tư 01/2022 về hộ tịch điện tử |
| **TT20** | `tt_07_2023_tt_bng` | 07/2023/TT-BNG | Sửa đổi bổ sung | Hướng dẫn việc đăng ký và quản lý hộ tịch tại Cơ quan đại diện ngoại giao, Cơ quan đại diện lãnh sự của Việt Nam ở nước ngoài |
| **TT21** | `tt_07_2025_tt_bng` | 07/2025/TT-BNG | Không xác định | Sửa đổi, bổ sung một số điều của Thông tư số 07/2023/TT-BNG ngày 29 tháng 12 năm 2023 của Bộ trưởng Bộ Ngoại giao hướng dẫn việc đăng ký và quản lý hộ tịch tại Cơ quan đại diện ngoại giao, Cơ quan đại diện lãnh sự của Việt Nam ở nước ngoài |
| **L05** | `l_60_2014_qh13` | 60/2014/QH13 | Không xác định | LUẬT HỘ TỊCH |
| **L06** | `l_52_2010_qh12` | 52/2010/QH12 | Không xác định | LUẬT NUÔI CON NUÔI |
| **L07** | `l_13_2022_qh15` | 13/2022/QH15 | Không xác định | Luật phòng, chống bạo lực gia đình |
| **TT14** | `tt_10_2020_tt_btp` | 10/2020/TT-BTP | Không xác định | ban hành, hướng dẫn việc ghi chép, sử dụng, quản lý và lưu trữ Sổ, mẫu giấy tờ, hồ sơ nuôi con nuôi |
| **L08** | `l_35_2013_qh13` | 35/2013/QH13 | Không xác định | Luật Hòa giải ở cơ sở |
| **ND16** | `nd_19_2011_nd_cp` | 19/2011/NĐ-CP | Không xác định | Quy định chi tiết thi hành một số điều của Luật Nuôi con nuôi |
| **ND18** | `nd_76_2023_nd_cp` | 76/2023/NĐ-CP | Không xác định | Quy định chi tiết một số điều của Luật Phòng, chống bạo lực gia đình |
| **ND19** | `nd_114_2016_nd_cp` | 114/2016/NĐ-CP | Không xác định | Quy định lệ phí đăng ký nuôi con nuôi, lệ phí cấp giấy phép hoạt động của tổ chức con nuôi nước ngoài |
| **ND20** | `nd_15_2014_nd_cp` | 15/2014/NĐ-CP | Không xác định | Quy định chi tiết một số điều và biện pháp thi hành Luật hòa giải ở cơ sở |
| **NQ02** | `nq_326_2016_ubtvqh14` | 326/2016/UBTVQH14 | Không xác định | Án phí và lệ phí Tòa án |
| **BL01** | `bl_91_2015_qh13` | 91/2015/QH13 | Không xác định | Bộ Luật Dân sự |
| **TT16** | `tt_09_2022_tt_btp` | 09/2022/TT-BTP | Không xác định | Bãi bỏ một số nội dung tại các Thông tư trong lĩnh vực trợ giúp pháp lý, hộ tịch do Bộ trưởng Bộ Tư pháp ban hành |
| **ND26** | `nd_301_2026_nd_cp` | 301/2026/NĐ-CP | Không xác định | Sửa đổi, bổ sung một số điều của Nghị định số 63/2024/NĐ-CP ngày 10 tháng 6 năm 2024 của Chính phủ quy định việc thực hiện liên thông điện tử 02 nhóm thủ tục hành chính: đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi; đăng ký khai tử, xóa đăng ký thường trú, giải quyết mai táng phí, tử tuất |
| **ND28** | `nd_24_2013_nd_cp` | 24/2013/NĐ-CP | Hết hiệu lực | quy định chi tiết thi hành một số điều của Luật hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **TT22** | `tt_22_2013_tt_btp` | 22/2013/TT-BTP | Hết hiệu lực | quy định chi tiết và hướng dẫn thi hành một số điều của Nghị định số 24/2013/NĐ-CP ngày 28 tháng 3 năm 2013 của Chính phủ quy định chi tiết thi hành một số điều của Luật Hôn nhân và gia đình về quan hệ hôn nhân và gia đình có yếu tố nước ngoài |
| **TT23** | `tt_16_2010_tt_btp` | 16/2010/TT-BTP | Hết hiệu lực | hướng dẫn việc ghi vào sổ hộ tịch việc ly hôn đã tiến hành ở nước ngoài |
| **TTLT01** | `ttlt_03_2016_ttlt_btp_bng_bca_bldtbxh` | 03/2016/TTLT-BTP-BNG-BCA-BLĐTBXH | Không xác định | hướng dẫn việc theo dõi tình hình phát triển của trẻ em Việt Nam được cho làm con nuôi nước ngoài và bảo vệ trẻ em trong trường hợp cần thiết |
| **ND29** | `nd_110_2013_nd_cp` | 110/2013/NĐ-CP | Hết hiệu lực | quy định xử phạt vi phạm hành chính trong lĩnh vực bổ trợ tư pháp, hành chính tư pháp, hôn nhân và gia đình, thi hành án dân sự, phá sản doanh nghiệp, hợp tác xã |
| **TT24** | `tt_66_2025_tt_bca` | 66/2025/TT-BCA | Không xác định | quy định công tác giám sát việc thực hiện quyết định cấm tiếp xúc theo quy định của Luật Phòng, chống bạo lực gia đình |
| **ND30** | `nd_110_2025_nd_cp` | 110/2025/NĐ-CP | Không xác định | quy định Cơ sở dữ liệu về phòng, chống bạo lực gia đình |
| **TT25** | `tt_24_2011_tt_bvhttdl` | 24/2011/TT-BVHTTDL | Không xác định | quy định về tiêu chuẩn, điều kiện khen thưởng cá nhân, tập thể tham gia phòng, chống bạo lực gia đình; đối tượng, điều kiện, cơ quan hoàn trả thiệt hại về giá trị tài sản cho người trực tiếp tham gia phòng, chống bạo lực gia đình |
| **TT26** | `tt_11_2021_tt_btp` | 11/2021/TT-BTP | Không xác định | sửa đổi, bổ sung một số điều của Thông tư số 21/2011/TT-BTP ngày 21 tháng 11 năm 2011 của Bộ trưởng Bộ Tư pháp về việc quản lý Văn phòng con nuôi nước ngoài tại Việt Nam |
| **TT27** | `tt_01_2025_tt_btp` | 01/2025/TT-BTP | Không xác định | sửa đổi, bổ sung một số điều của Thông tư số 21/2011/TT-BTP ngày 21 tháng 11 năm 2011 của Bộ trưởng Bộ Tư pháp về việc quản lý Văn phòng con nuôi nước ngoài tại Việt Nam đã được sửa đổi, bổ sung một số điều theo Thông tư số 11/2021/TT-BTP ngày 28 tháng 12 năm 2021 của Bộ trưởng Bộ Tư pháp |
| **TT28** | `tt_24_2014_tt_btp` | 24/2014/TT-BTP | Hết hiệu lực | sửa đổi, bổ sung một số điều của Thông tư số 12/2011/TT-BTP ngày 27 tháng 6 năm 2011 của Bộ Tư pháp về việc ban hành và hướng dẫn việc ghi chép, lưu trữ, sử dụng biểu mẫu nuôi con nuôi |
| **ND31** | `nd_06_2012_nd_cp` | 06/2012/NĐ-CP | Không xác định | sửa đổi, bổ sung một số điều của các Nghị định về hộ tịch, hôn nhân và gia đình và chứng thực |
| **TT32** | `tt_12_2011_tt_btp` | 12/2011/TT-BTP | Hết hiệu lực | về việc ban hành và hướng dẫn việc ghi chép, lưu trữ, sử dụng biểu mẫu nuôi con nuôi |
| **TT34** | `tt_15_2014_tt_btp` | 15/2014/TT-BTP | Không xác định | hướng dẫn tìm gia đình thay thế ở nước ngoài cho trẻ em khuyết tật, trẻ em mắc bệnh hiểm nghèo, trẻ em từ 5 tuổi trở lên, hai trẻ em trở lên là anh chị em ruột cần tìm gia đình thay thế |
| **TT35** | `tt_21_2011_tt_btp` | 21/2011/TT-BTP | Không xác định | về việc quản lý Văn phòng con nuôi nước ngoài tại Việt Nam |

Quy tắc định danh cấu trúc phân cấp:
- **Article ID**: `[document_id]_art_[số_điều]` (Ví dụ: `l_52_2014_qh13_art_8`). Mã quản lý tương ứng: `L01_D08`.
- **Clause ID**: `[article_id]_clause_[số_khoản]` (Ví dụ: `l_52_2014_qh13_art_8_clause_1`).
- **Chunk ID**: `[clause_id]_chunk_[chỉ_số]` (Ví dụ: `l_52_2014_qh13_art_8_clause_1_chunk_1`).

Các mã này được tạo tự động trong quá trình xử lý dữ liệu, không yêu cầu phải đổi tên file PDF gốc.
Không sử dụng cùng một document_id cho hai văn bản khác nhau.

## 4. Bảng kiểm kê văn bản

File `legal_documents_master.xlsx` là danh mục quản lý tập trung cho các văn bản trong hệ thống.

Bảng cần thống nhất mã định danh, loại văn bản, thông tin ban hành, hiệu lực, nguồn và đường dẫn file gốc theo các trường metadata mà nhóm đã thống nhất.

Mỗi văn bản cần có bản ghi tương ứng trong bảng kiểm kê. Không xem mỗi dòng metadata ở cấp Điều hoặc Khoản là một văn bản pháp luật độc lập.

## 5. Quy trình bổ sung dữ liệu

1. Nhận file văn bản pháp luật từ thành viên phụ trách.
2. Xác định loại văn bản: Luật, Nghị định hoặc Thông tư.
3. Đặt tên file theo document_id đã thống nhất.
4. Lưu file vào đúng thư mục trong `raw_data/`.
5. Kiểm tra file có mở được và nội dung có đầy đủ hay không.
6. Đối chiếu thông tin với `legal_documents_master.xlsx`.
7. Ghi nhận lỗi hoặc metadata còn thiếu trong `data_quality_report.docx`.

## 6. Kiểm tra chất lượng dữ liệu

Các tiêu chí kiểm tra:

- File tồn tại và mở được.
- Định dạng file phù hợp với quy trình xử lý.
- Không có file trùng lặp ngoài ý muốn.
- document_id không bị trùng.
- Metadata bắt buộc được điền đầy đủ.
- Tên file và đường dẫn khớp với bảng kiểm kê.
- Văn bản có thông tin nguồn và tình trạng hiệu lực để đối chiếu.

Các lỗi phát hiện cần được ghi lại, kèm document_id, mô tả lỗi và trạng thái xử lý.

## 7. Sử dụng dữ liệu trong pipeline RAG

Dữ liệu trong `raw_data/` là nguồn đầu vào cho pipeline xử lý văn bản.

Quy trình dự kiến:

1. Đọc file văn bản pháp luật.
2. Trích xuất nội dung.
3. Phân tích cấu trúc văn bản như Chương, Điều, Khoản và Điểm.
4. Chia nội dung thành các đoạn (chunks).
5. Gắn metadata và mã định danh nguồn.
6. Tạo embedding và lập chỉ mục để phục vụ truy xuất trong Knowledge Base.

Bảng kiểm kê hỗ trợ quản lý và liên kết metadata; nội dung dùng để truy xuất được lấy từ văn bản gốc sau khi xử lý.

## 8. Nguyên tắc quản lý

- Giữ nguyên file gốc, không chỉnh sửa trực tiếp nội dung pháp luật.
- Không tự ý thay đổi document_id sau khi đã được sử dụng trong pipeline.
- Khi bổ sung hoặc thay thế văn bản, cập nhật bảng kiểm kê và báo cáo chất lượng.
- Kiểm tra nguồn và tình trạng hiệu lực của văn bản trước khi sử dụng làm căn cứ trả lời.
- Không đưa file chưa kiểm tra vào bộ dữ liệu chính thức.

---
**Project:** Vietnam Legal RAG Assistant  
**Directory:** data/  
**Purpose:** Legal document storage and metadata management