# F4 - TT 30/2019/TT-BYT: đối chiếu nguồn và biểu diễn phiên bản

Ngày đối chiếu: 08/11/2026. Phạm vi: sự kiện thay đổi có hiệu lực từ 01/02/2020;
không phải rà soát toàn bộ lịch sử sửa đổi về sau hoặc ký duyệt pháp lý thay Dev 1.

## Kết quả

Giữ `provision_status = repealed` và `effective_to = 2020-02-01` cho **nội dung
phiên bản gốc** khoản 2-3 Điều 2 TT 34/2017 trong corpus. Không suy diễn rằng
hai khái niệm không còn được quy định, hoặc loại cả nội dung mới của TT 30/2019.

Đây là quyết định biểu diễn dữ liệu dựa trên các nguồn dưới đây, không phải tự
đính chính câu chữ của văn bản ban hành. F4 đã có căn cứ để giữ cách biểu diễn
hiện tại; không cần đổi trạng thái hoặc sinh lại corpus vì F4.

## Nguồn đối chiếu

1. [TT 30/2019 bản chính thức trên Cổng Chính phủ](https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/03/30-byt.pdf):
   trang PDF 1, Điều 1 khoản 1-2 có nội dung định nghĩa thay thế; trang 2, Điều 2
   khoản 1-2 ghi ngày hiệu lực và bãi bỏ hai Khoản của TT 34/2017.
2. [Văn bản hợp nhất trên CSDL quốc gia, Bộ Y tế](https://vbpl.vn/FileData/TW/Lists/vbpq/Attachments/141540/tvVanBanGoc_S%E1%BB%90%2002.VBHN-BYT.pdf):
   trang in 2, Điều 2 khoản 2-3 và chú thích 2-3 giữ định nghĩa đã sửa theo Điều 1
   TT 30/2019; trang in 5, chú thích 4 cũng dẫn lại điều khoản bãi bỏ. Dùng để
   đối chiếu cách hợp nhất, không thay thế văn bản gốc làm căn cứ ban hành.
3. [Danh mục hết hiệu lực một phần của Bộ Y tế](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/3/phulucso4danhmucvanbanhethieulucmotphanphathanh26.1.2024.signed.pdf):
   mục 53, trang in 25 ghi hai Khoản này bị bãi bỏ bởi TT 30/2019 từ 01/02/2020.
   Danh mục xác nhận sự kiện lịch sử; không đủ để xác nhận tình trạng tới hôm nay.

Không tìm thấy văn bản đính chính trong lượt tìm kiếm này; không coi việc không
tìm thấy là bằng chứng chắc chắn rằng không có đính chính.

## Đối chiếu corpus và bộ lọc

| Phiên bản | Chunk | Kỳ hiệu lực kiểm tra |
|---|---|---|
| Gốc k2 | `tt_34_2017_tt_byt_art_2_clause_2_chunk_1` | Có trước 01/02/2020, bị loại từ ngày này |
| Gốc k3 | `tt_34_2017_tt_byt_art_2_clause_3_chunk_1` | Có trước 01/02/2020, bị loại từ ngày này |
| Thay thế k2 | `tt_30_2019_tt_byt_art_1_clause_1_chunk_1` | Có từ 01/02/2020 |
| Thay thế k3 | `tt_30_2019_tt_byt_art_1_clause_2_chunk_1` | Có từ 01/02/2020 |

Chunk bãi bỏ vẫn là `tt_30_2019_tt_byt_art_2_clause_2_chunk_1`. Ghi chú của
override bổ sung hai ID thay thế và nguồn đối chiếu. Kiểm thử xác nhận biên ngày
31/01/2020 và 01/02/2020; đây là điều kiện qua bộ lọc, không khẳng định thứ hạng
top-k hoặc mức độ đầy đủ của một câu trả lời sinh ra.
