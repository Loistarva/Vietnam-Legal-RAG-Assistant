# 30 câu Dev đề xuất — kiểm tra trước bàn giao

Status: proposed_pending_user_and_dev2_review. Không phải bảng điểm hoặc xác nhận pháp lý mới.

File gửi chạy zero-shot: `../datasets/dev_gold_30_queries_v1.json` (chỉ query; không có đáp án).

Đã loại đúng 195 ID người dùng chỉ định; dùng corpus cũ, không dùng 9 chunk thêm của PR #25.

Đã đọc đối chiếu câu hỏi/đáp án với chunk source cho các ID dưới đây. Đây là rà soát nội dung trong repo, không thay review pháp lý độc lập hoặc xác minh hiệu lực mới ngoài corpus.

## Phân bố

```json
{
  "category": {
    "ket_hon": 7,
    "vo_chong": 2,
    "tai_san": 5,
    "ly_hon": 3,
    "con_cai": 3,
    "cap_duong": 5,
    "nguyen_tac_quy_dinh": 3,
    "mang_thai_ho": 2
  },
  "question_type": {
    "fact": 13,
    "situation": 14,
    "multi_hop": 3
  },
  "difficulty": {
    "easy": 13,
    "medium": 12,
    "hard": 5
  },
  "test_type": {
    "current_law": 29,
    "outdated_law_trap": 1
  }
}
```

Giới hạn: tất cả Gold được chọn lấy từ Luật 52/2014 trong corpus cũ; không đại diện đầy đủ 75 Dev Gold hoặc toàn bộ văn bản/test_type. Không dùng chỉ số trên mẫu này để tuyên bố chất lượng toàn benchmark. Một số câu dùng chung Khoản; không coi chúng là 30 đơn vị chứng cứ độc lập.

## 01. HN_001

Theo Luật Hôn nhân và gia đình 2014, nam phải đủ bao nhiêu tuổi để kết hôn?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Nam từ đủ 20 tuổi trở lên.

Chứng cứ corpus:

`l_52_2014_qh13_art_8_clause_1_chunk_1`

1. Nam, nữ kết hôn với nhau phải tuân theo các điều kiện sau đây: a) Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên; b) Việc kết hôn do nam và nữ tự nguyện quyết định; c) Không bị mất năng lực hành vi dân sự; d) Việc kết hôn không thuộc một trong các trường hợp cấm kết hôn theo quy định tại các điểm a, b, c và d khoản 2 Điều 5 của Luật này.

## 02. HN_002

Theo Luật Hôn nhân và gia đình 2014, nữ phải đủ bao nhiêu tuổi để kết hôn?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Nữ từ đủ 18 tuổi trở lên.

Chứng cứ corpus:

`l_52_2014_qh13_art_8_clause_1_chunk_1`

1. Nam, nữ kết hôn với nhau phải tuân theo các điều kiện sau đây: a) Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên; b) Việc kết hôn do nam và nữ tự nguyện quyết định; c) Không bị mất năng lực hành vi dân sự; d) Việc kết hôn không thuộc một trong các trường hợp cấm kết hôn theo quy định tại các điểm a, b, c và d khoản 2 Điều 5 của Luật này.

## 03. HN_004

Người bị mất năng lực hành vi dân sự có đáp ứng điều kiện kết hôn theo Luật 2014 không?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Không. Người kết hôn phải không bị mất năng lực hành vi dân sự.

Chứng cứ corpus:

`l_52_2014_qh13_art_8_clause_1_chunk_1`

1. Nam, nữ kết hôn với nhau phải tuân theo các điều kiện sau đây: a) Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên; b) Việc kết hôn do nam và nữ tự nguyện quyết định; c) Không bị mất năng lực hành vi dân sự; d) Việc kết hôn không thuộc một trong các trường hợp cấm kết hôn theo quy định tại các điểm a, b, c và d khoản 2 Điều 5 của Luật này.

## 04. HN_007

Pháp luật hôn nhân và gia đình có cho phép người đang có vợ hoặc chồng kết hôn với người khác không?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Không. Hành vi kết hôn hoặc chung sống như vợ chồng với người khác khi đang có vợ hoặc chồng thuộc trường hợp bị cấm.

Chứng cứ corpus:

`l_52_2014_qh13_art_5_clause_2_chunk_1`

2. Cấm các hành vi sau đây: a) Kết hôn giả tạo, ly hôn giả tạo; b) Tảo hôn, cưỡng ép kết hôn, lừa dối kết hôn, cản trở kết hôn; c) Người đang có vợ, có chồng mà kết hôn hoặc chung sống như vợ chồng với người khác hoặc chưa có vợ, chưa có chồng mà kết hôn hoặc chung sống như vợ chồng với người đang có chồng, có vợ; d) Kết hôn hoặc chung sống như vợ chồng giữa những người cùng dòng máu về trực hệ; giữa những người có họ trong phạm vi ba đời; giữa cha, mẹ nuôi với con nuôi; giữa người đã từng là cha, mẹ nuôi với con nuôi, cha chồng với con dâu, mẹ vợ với con rể, cha dượng với con riêng của vợ, mẹ kế với con riêng của chồng; đ) Yêu sách của cải trong kết hôn; e) Cưỡng ép ly hôn, lừa dối ly hôn, cản trở ly hôn;

`l_52_2014_qh13_art_5_clause_2_chunk_2`

g) Thực hiện sinh con bằng kỹ thuật hỗ trợ sinh sản vì mục đích thương mại, mang thai hộ vì mục đích thương mại, lựa chọn giới tính thai nhi, sinh sản vô tính; h) Bạo lực gia đình; i) Lợi dụng việc thực hiện quyền về hôn nhân và gia đình để mua bán người, bóc lột sức lao động, xâm phạm tình dục hoặc có hành vi khác nhằm mục đích trục lợi.

## 05. HN_009

Nam nữ đủ điều kiện nhưng chung sống như vợ chồng mà không đăng ký kết hôn thì có phát sinh quyền nghĩa vụ giữa vợ chồng không?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Không làm phát sinh quyền, nghĩa vụ giữa vợ và chồng theo Luật Hôn nhân và gia đình; quyền con cái, tài sản được giải quyết theo quy định riêng.

Chứng cứ corpus:

`l_52_2014_qh13_art_14_clause_1_chunk_1`

1. Nam, nữ có đủ điều kiện kết hôn theo quy định của Luật này chung sống với nhau như vợ chồng mà không đăng ký kết hôn thì không làm phát sinh quyền, nghĩa vụ giữa vợ và chồng. Quyền, nghĩa vụ đối với con, tài sản, nghĩa vụ và hợp đồng giữa các bên được giải quyết theo quy định tại Điều 15 và Điều 16 của Luật này.

## 06. HN_010

Nếu cặp đôi chung sống không đăng ký kết hôn sau đó mới đăng ký thì hôn nhân được xác lập từ thời điểm nào?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Từ thời điểm đăng ký kết hôn theo quy định pháp luật.

Chứng cứ corpus:

`l_52_2014_qh13_art_14_clause_2_chunk_1`

2. Trong trường hợp nam, nữ chung sống với nhau như vợ chồng theo quy định tại khoản 1 Điều này nhưng sau đó thực hiện việc đăng ký kết hôn theo quy định của pháp luật thì quan hệ hôn nhân được xác lập từ thời điểm đăng ký kết hôn.

## 07. HN_013

Vợ chồng có bình đẳng về quyền và nghĩa vụ trong gia đình không?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Có. Vợ chồng bình đẳng và có quyền, nghĩa vụ ngang nhau trong gia đình.

Chứng cứ corpus:

`l_52_2014_qh13_art_17_clause_1_chunk_1`

Vợ, chồng bình đẳng với nhau, có quyền, nghĩa vụ ngang nhau về mọi mặt trong gia đình, trong việc thực hiện các quyền, nghĩa vụ của công dân được quy định trong Hiến pháp, Luật này và các luật khác có liên quan.

## 08. HN_016

Thu nhập do lao động trong thời kỳ hôn nhân thường là tài sản chung hay riêng?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Về nguyên tắc là tài sản chung của vợ chồng, trừ trường hợp pháp luật có quy định khác.

Chứng cứ corpus:

`l_52_2014_qh13_art_33_clause_1_chunk_1`

1. Tài sản chung của vợ chồng gồm tài sản do vợ, chồng tạo ra, thu nhập do lao động, hoạt động sản xuất, kinh doanh, hoa lợi, lợi tức phát sinh từ tài sản riêng và thu nhập hợp pháp khác trong thời kỳ hôn nhân, trừ trường hợp được quy định tại khoản 1 Điều 40 của Luật này; tài sản mà vợ chồng được thừa kế chung hoặc được tặng cho chung và tài sản khác mà vợ chồng thỏa thuận là tài sản chung. Quyền sử dụng đất mà vợ, chồng có được sau khi kết hôn là tài sản chung của vợ chồng, trừ trường hợp vợ hoặc chồng được thừa kế riêng, được tặng cho riêng hoặc có được thông qua giao dịch bằng tài sản riêng.

## 09. HN_017

Tài sản vợ chồng được tặng cho chung trong thời kỳ hôn nhân là loại tài sản gì?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Là tài sản chung của vợ chồng.

Chứng cứ corpus:

`l_52_2014_qh13_art_33_clause_1_chunk_1`

1. Tài sản chung của vợ chồng gồm tài sản do vợ, chồng tạo ra, thu nhập do lao động, hoạt động sản xuất, kinh doanh, hoa lợi, lợi tức phát sinh từ tài sản riêng và thu nhập hợp pháp khác trong thời kỳ hôn nhân, trừ trường hợp được quy định tại khoản 1 Điều 40 của Luật này; tài sản mà vợ chồng được thừa kế chung hoặc được tặng cho chung và tài sản khác mà vợ chồng thỏa thuận là tài sản chung. Quyền sử dụng đất mà vợ, chồng có được sau khi kết hôn là tài sản chung của vợ chồng, trừ trường hợp vợ hoặc chồng được thừa kế riêng, được tặng cho riêng hoặc có được thông qua giao dịch bằng tài sản riêng.

## 10. HN_018

Tài sản có trước khi kết hôn mặc nhiên là tài sản chung không?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Không. Tài sản mỗi người có trước khi kết hôn về nguyên tắc là tài sản riêng, trừ khi nhập vào tài sản chung.

Chứng cứ corpus:

`l_52_2014_qh13_art_43_clause_1_chunk_1`

1. Tài sản riêng của vợ, chồng gồm tài sản mà mỗi người có trước khi kết hôn; tài sản được thừa kế riêng, được tặng cho riêng trong thời kỳ hôn nhân; tài sản được chia riêng cho vợ, chồng theo quy định tại các điều 38, 39 và 40 của Luật này; tài sản phục vụ nhu cầu thiết yếu của vợ, chồng và tài sản khác mà theo quy định của pháp luật thuộc sở hữu riêng của vợ, chồng.

`l_52_2014_qh13_art_46_clause_1_chunk_1`

1. Việc nhập tài sản riêng của vợ, chồng vào tài sản chung được thực hiện theo thỏa thuận của vợ chồng.

## 11. HN_020

Vợ chồng có thể thỏa thuận chia tài sản chung ngay trong thời kỳ hôn nhân không?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Có. Vợ chồng có quyền thỏa thuận chia một phần hoặc toàn bộ tài sản chung trong thời kỳ hôn nhân, trừ trường hợp luật hạn chế.

Chứng cứ corpus:

`l_52_2014_qh13_art_38_clause_1_chunk_1`

1. Trong thời kỳ hôn nhân, vợ chồng có quyền thỏa thuận chia một phần hoặc toàn bộ tài sản chung, trừ trường hợp quy định tại Điều 42 của Luật này; nếu không thỏa thuận được thì có quyền yêu cầu Tòa án giải quyết.

## 12. HN_021

Chồng có quyền tự yêu cầu ly hôn khi vợ đang mang thai không?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Không. Khoản 3 Điều 51 hạn chế quyền yêu cầu ly hôn của chồng khi vợ đang mang thai.

Chứng cứ corpus:

`l_52_2014_qh13_art_51_clause_3_chunk_1`

3. Chồng không có quyền yêu cầu ly hôn trong trường hợp vợ đang có thai, sinh con hoặc đang nuôi con dưới 12 tháng tuổi.

## 13. HN_023

Hai vợ chồng có thể cùng yêu cầu Tòa án giải quyết ly hôn không?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Có. Vợ, chồng hoặc cả hai đều có quyền yêu cầu Tòa án giải quyết ly hôn.

Chứng cứ corpus:

`l_52_2014_qh13_art_51_clause_1_chunk_1`

1. Vợ, chồng hoặc cả hai người có quyền yêu cầu Tòa án giải quyết ly hôn.

## 14. HN_025

Một bên có thể được Tòa án giải quyết cho ly hôn khi có bạo lực gia đình nghiêm trọng không?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Có thể, nếu đáp ứng căn cứ tại khoản 1 Điều 56 và hòa giải tại Tòa án không thành.

Chứng cứ corpus:

`l_52_2014_qh13_art_56_clause_1_chunk_1`

1. Khi vợ hoặc chồng yêu cầu ly hôn mà hòa giải tại Tòa án không thành thì Tòa án giải quyết cho ly hôn nếu có căn cứ về việc vợ, chồng có hành vi bạo lực gia đình hoặc vi phạm nghiêm trọng quyền, nghĩa vụ của vợ, chồng làm cho hôn nhân lâm vào tình trạng trầm trọng, đời sống chung không thể kéo dài, mục đích của hôn nhân không đạt được.

## 15. HN_028

Con từ đủ 7 tuổi trở lên thì Tòa án có phải xem xét nguyện vọng của con khi quyết định người trực tiếp nuôi không?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Có. Tòa án phải xem xét nguyện vọng của con từ đủ 7 tuổi trở lên.

Chứng cứ corpus:

`l_52_2014_qh13_art_81_clause_2_chunk_1`

2. Vợ, chồng thỏa thuận về người trực tiếp nuôi con, nghĩa vụ, quyền của mỗi bên sau khi ly hôn đối với con; trường hợp không thỏa thuận được thì Tòa án quyết định giao con cho một bên trực tiếp nuôi căn cứ vào quyền lợi về mọi mặt của con; nếu con từ đủ 07 tuổi trở lên thì phải xem xét nguyện vọng của con.

## 16. HN_029

Sau ly hôn, con dưới 36 tháng tuổi có đương nhiên luôn phải giao mẹ nuôi không?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Không tuyệt đối. Nguyên tắc giao mẹ trực tiếp nuôi, trừ khi mẹ không đủ điều kiện hoặc cha mẹ có thỏa thuận khác phù hợp lợi ích của con.

Chứng cứ corpus:

`l_52_2014_qh13_art_81_clause_3_chunk_1`

3. Con dưới 36 tháng tuổi được giao cho mẹ trực tiếp nuôi, trừ trường hợp người mẹ không đủ điều kiện để trực tiếp trông nom, chăm sóc, nuôi dưỡng, giáo dục con hoặc cha mẹ có thỏa thuận khác phù hợp với lợi ích của con.

## 17. HN_030

Cha hoặc mẹ không trực tiếp nuôi con sau ly hôn có nghĩa vụ cấp dưỡng không?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Có. Cha hoặc mẹ không trực tiếp nuôi con có nghĩa vụ cấp dưỡng cho con.

Chứng cứ corpus:

`l_52_2014_qh13_art_82_clause_2_chunk_1`

2. Cha, mẹ không trực tiếp nuôi con có nghĩa vụ cấp dưỡng cho con.

## 18. HN_031

Cha mẹ không trực tiếp nuôi con có quyền thăm nom con sau ly hôn không?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Có quyền và nghĩa vụ thăm nom con, không ai được cản trở; việc thăm nom bị hạn chế nếu lạm dụng gây ảnh hưởng xấu theo quy định.

Chứng cứ corpus:

`l_52_2014_qh13_art_82_clause_3_chunk_1`

3. Sau khi ly hôn, người không trực tiếp nuôi con có quyền, nghĩa vụ thăm nom con mà không ai được cản trở. Cha, mẹ không trực tiếp nuôi con lạm dụng việc thăm nom để cản trở hoặc gây ảnh hưởng xấu đến việc trông nom, chăm sóc, nuôi dưỡng, giáo dục con thì người trực tiếp nuôi con có quyền yêu cầu Tòa án hạn chế quyền thăm nom con của người đó.

## 19. HN_032

Mức cấp dưỡng cho con có bắt buộc là một số tiền cố định do luật ấn định không?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Không. Mức cấp dưỡng do các bên thỏa thuận theo thu nhập, khả năng thực tế và nhu cầu thiết yếu; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

Chứng cứ corpus:

`l_52_2014_qh13_art_116_clause_1_chunk_1`

1. Mức cấp dưỡng do người có nghĩa vụ cấp dưỡng và người được cấp dưỡng hoặc người giám hộ của người đó thỏa thuận căn cứ vào thu nhập, khả năng thực tế của người có nghĩa vụ cấp dưỡng và nhu cầu thiết yếu của người được cấp dưỡng; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

## 20. HN_033

Cấp dưỡng có thể thực hiện một lần thay vì hằng tháng không?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Có. Phương thức cấp dưỡng có thể theo tháng, quý, nửa năm, năm hoặc một lần.

Chứng cứ corpus:

`l_52_2014_qh13_art_117_clause_1_chunk_1`

Việc cấp dưỡng có thể được thực hiện định kỳ hàng tháng, hàng quý, nửa năm, hàng năm hoặc một lần. Các bên có thể thỏa thuận thay đổi phương thức cấp dưỡng, tạm ngừng cấp dưỡng trong trường hợp người có nghĩa vụ cấp dưỡng lâm vào tình trạng khó khăn về kinh tế mà không có khả năng thực hiện nghĩa vụ cấp dưỡng; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

## 21. HN_035

Theo quy định HNGĐ hiện hành năm 2026, kết hôn cùng giới vẫn là hành vi bị cấm theo Luật 2000 đúng không?

- Ngày áp dụng: 2026-10-15; situation; hard.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Không. Luật 2000 đã hết hiệu lực; Luật 2014 quy định Nhà nước không thừa nhận hôn nhân giữa những người cùng giới tính, không liệt kê đây là một trường hợp cấm kết hôn như Luật 2000.

Chứng cứ corpus:

`l_52_2014_qh13_art_8_clause_2_chunk_1`

2. Nhà nước không thừa nhận hôn nhân giữa những người cùng giới tính.

## 22. HN_061

Phạm vi điều chỉnh của Luật Hôn nhân và gia đình 2014 bao gồm những nhóm quan hệ và vấn đề nào?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Luật Hôn nhân và gia đình năm 2014 điều chỉnh chế độ hôn nhân và gia đình, quy định chuẩn mực pháp lý cho cách ứng xử giữa các thành viên gia đình, đồng thời xác định trách nhiệm của cá nhân, tổ chức, Nhà nước và xã hội trong việc xây dựng, củng cố chế độ hôn nhân và gia đình.

Chứng cứ corpus:

`l_52_2014_qh13_art_1_clause_1_chunk_1`

Luật này quy định chế độ hôn nhân và gia đình; chuẩn mực pháp lý cho cách ứng xử giữa các thành viên gia đình; trách nhiệm của cá nhân, tổ chức, Nhà nước và xã hội trong việc xây dựng, củng cố chế độ hôn nhân và gia đình.

## 23. HN_062

Luật Hôn nhân và gia đình 2014 đặt ra những nguyên tắc nào đối với vấn đề chế độ hôn nhân và gia đình?

- Ngày áp dụng: 2026-10-15; fact; easy.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Chế độ hôn nhân và gia đình theo Luật năm 2014 dựa trên 5 nguyên tắc cơ bản: (1) hôn nhân tự nguyện, tiến bộ, một vợ một chồng, vợ chồng bình đẳng; (2) tôn trọng và bảo vệ hôn nhân không phân biệt dân tộc, tôn giáo, tín ngưỡng hoặc giữa công dân Việt Nam với người nước ngoài; (3) xây dựng gia đình ấm no, tiến bộ, hạnh phúc, các thành viên tôn trọng, chăm sóc nhau và không phân biệt đối xử giữa các con; (4) Nhà nước, xã hội và gia đình bảo vệ trẻ em, người cao tuổi, người khuyết tật, hỗ trợ người mẹ và kế hoạch hóa gia đình; (5) kế thừa, phát huy truyền thống văn hóa, đạo đức tốt đẹp của dân tộc.

Chứng cứ corpus:

`l_52_2014_qh13_art_2_clause_1_chunk_1`

1. Hôn nhân tự nguyện, tiến bộ, một vợ một chồng, vợ chồng bình đẳng.

`l_52_2014_qh13_art_2_clause_2_chunk_1`

2. Hôn nhân giữa công dân Việt Nam thuộc các dân tộc, tôn giáo, giữa người theo tôn giáo với người không theo tôn giáo, giữa người có tín ngưỡng với người không có tín ngưỡng, giữa công dân Việt Nam với người nước ngoài được tôn trọng và được pháp luật bảo vệ.

`l_52_2014_qh13_art_2_clause_3_chunk_1`

3. Xây dựng gia đình ấm no, tiến bộ, hạnh phúc; các thành viên gia đình có nghĩa vụ tôn trọng, quan tâm, chăm sóc, giúp đỡ nhau; không phân biệt đối xử giữa các con.

`l_52_2014_qh13_art_2_clause_4_chunk_1`

4. Nhà nước, xã hội và gia đình có trách nhiệm bảo vệ, hỗ trợ trẻ em, người cao tuổi, người khuyết tật thực hiện các quyền về hôn nhân và gia đình; giúp đỡ các bà mẹ thực hiện tốt chức năng cao quý của người mẹ; thực hiện kế hoạch hóa gia đình.

`l_52_2014_qh13_art_2_clause_5_chunk_1`

5. Kế thừa, phát huy truyền thống văn hóa, đạo đức tốt đẹp của dân tộc Việt Nam về hôn nhân và gia đình.

## 24. HN_067

Khi gặp tình huống liên quan đến tập quán về hôn nhân và gia đình, phải chọn căn cứ pháp luật như thế nào theo Luật Hôn nhân và gia đình 2014?

- Ngày áp dụng: 2026-10-15; situation; hard.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Tập quán về hôn nhân và gia đình chỉ được áp dụng khi pháp luật không có quy định và các bên không có thỏa thuận, với điều kiện đó là tập quán tốt đẹp thể hiện bản sắc của mỗi dân tộc, không trái với các nguyên tắc cơ bản tại Điều 2 và không vi phạm điều cấm của Luật Hôn nhân và gia đình năm 2014; việc áp dụng thực hiện theo quy định chi tiết của Chính phủ.

Chứng cứ corpus:

`l_52_2014_qh13_art_7_clause_1_chunk_1`

1. Trong trường hợp pháp luật không quy định và các bên không có thỏa thuận thì tập quán tốt đẹp thể hiện bản sắc của mỗi dân tộc, không trái với nguyên tắc quy định tại Điều 2 và không vi phạm điều cấm của Luật này được áp dụng.

`l_52_2014_qh13_art_7_clause_2_chunk_1`

2. Chính phủ quy định chi tiết khoản 1 Điều này.

## 25. HN_087

Đối với trách nhiệm liên đới của vợ, chồng, Luật Hôn nhân và gia đình 2014 quy định ai phải thực hiện nghĩa vụ hoặc trách nhiệm tương ứng?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Vợ, chồng phải chịu trách nhiệm liên đới đối với giao dịch do một bên thực hiện nhằm đáp ứng nhu cầu thiết yếu của gia đình theo khoản 1 Điều 30 hoặc giao dịch khác phù hợp với quy định về đại diện giữa vợ chồng tại các Điều 24, 25 và 26, đồng thời chịu trách nhiệm liên đới đối với các nghĩa vụ chung về tài sản quy định tại Điều 37 Luật Hôn nhân và gia đình năm 2014.

Chứng cứ corpus:

`l_52_2014_qh13_art_27_clause_1_chunk_1`

1. Vợ, chồng chịu trách nhiệm liên đới đối với giao dịch do một bên thực hiện quy định tại khoản 1 Điều 30 hoặc giao dịch khác phù hợp với quy định về đại diện tại các điều 24, 25 và 26 của Luật này.

`l_52_2014_qh13_art_27_clause_2_chunk_1`

2. Vợ, chồng chịu trách nhiệm liên đới về các nghĩa vụ quy định tại Điều 37 của Luật này.

## 26. HN_104

Theo Luật Hôn nhân và gia đình 2014, việc xác định hoặc xử lý chiếm hữu, sử dụng, định đoạt tài sản riêng dựa trên nguyên tắc nào?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Vợ, chồng có quyền chiếm hữu, sử dụng, định đoạt tài sản riêng và quyết định nhập hoặc không nhập vào tài sản chung. Nếu một bên không thể tự quản lý và không ủy quyền thì bên kia được quản lý vì lợi ích của chủ sở hữu. Nghĩa vụ riêng về tài sản của mỗi người được thanh toán từ tài sản riêng của người đó; riêng trường hợp hoa lợi, lợi tức từ tài sản riêng là nguồn sống duy nhất của gia đình thì việc định đoạt tài sản riêng đó phải có sự đồng ý của chồng, vợ.

Chứng cứ corpus:

`l_52_2014_qh13_art_44_clause_1_chunk_1`

1. Vợ, chồng có quyền chiếm hữu, sử dụng, định đoạt tài sản riêng của mình; nhập hoặc không nhập tài sản riêng vào tài sản chung.

`l_52_2014_qh13_art_44_clause_2_chunk_1`

2. Trong trường hợp vợ hoặc chồng không thể tự mình quản lý tài sản riêng và cũng không ủy quyền cho người khác quản lý thì bên kia có quyền quản lý tài sản đó. Việc quản lý tài sản phải bảo đảm lợi ích của người có tài sản.

`l_52_2014_qh13_art_44_clause_3_chunk_1`

3. Nghĩa vụ riêng về tài sản của mỗi người được thanh toán từ tài sản riêng của người đó.

`l_52_2014_qh13_art_44_clause_4_chunk_1`

4. Trong trường hợp vợ, chồng có tài sản riêng mà hoa lợi, lợi tức từ tài sản riêng đó là nguồn sống duy nhất của gia đình thì việc định đoạt tài sản này phải có sự đồng ý của chồng, vợ.

## 27. HN_155

Theo Luật Hôn nhân và gia đình 2014, cần đáp ứng những yêu cầu cụ thể nào về điều kiện mang thai hộ vì mục đích nhân đạo?

- Ngày áp dụng: 2026-10-15; situation; medium.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Việc mang thai hộ vì mục đích nhân đạo phải tự nguyện, lập thành văn bản và không trái pháp luật về hỗ trợ sinh sản. Vợ chồng nhờ mang thai hộ phải có xác nhận của tổ chức y tế có thẩm quyền về việc người vợ không thể mang thai và sinh con ngay cả khi áp dụng kỹ thuật hỗ trợ sinh sản, đang không có con chung và đã được tư vấn y tế, pháp lý, tâm lý. Người được nhờ mang thai hộ phải là người thân thích cùng hàng của bên vợ hoặc bên chồng, đã từng sinh con và chỉ được mang thai hộ một lần, ở độ tuổi phù hợp có xác nhận y tế, có sự đồng ý bằng văn bản của chồng (nếu có chồng) và đã được tư vấn đầy đủ.

Chứng cứ corpus:

`l_52_2014_qh13_art_95_clause_1_chunk_1`

1. Việc mang thai hộ vì mục đích nhân đạo phải được thực hiện trên cơ sở tự nguyện của các bên và được lập thành văn bản.

`l_52_2014_qh13_art_95_clause_2_chunk_1`

2. Vợ chồng có quyền nhờ người mang thai hộ khi có đủ các điều kiện sau đây: a) Có xác nhận của tổ chức y tế có thẩm quyền về việc người vợ không thể mang thai và sinh con ngay cả khi áp dụng kỹ thuật hỗ trợ sinh sản; b) Vợ chồng đang không có con chung; c) Đã được tư vấn về y tế, pháp lý, tâm lý.

`l_52_2014_qh13_art_95_clause_3_chunk_1`

3. Người được nhờ mang thai hộ phải có đủ các điều kiện sau đây: a) Là người thân thích cùng hàng của bên vợ hoặc bên chồng nhờ mang thai hộ; b) Đã từng sinh con và chỉ được mang thai hộ một lần; c) Ở độ tuổi phù hợp và có xác nhận của tổ chức y tế có thẩm quyền về khả năng mang thai hộ; d) Trường hợp người phụ nữ mang thai hộ có chồng thì phải có sự đồng ý bằng văn bản của người chồng; đ) Đã được tư vấn về y tế, pháp lý, tâm lý.

`l_52_2014_qh13_art_95_clause_4_chunk_1`

4. Việc mang thai hộ vì mục đích nhân đạo không được trái với quy định của pháp luật về sinh con bằng kỹ thuật hỗ trợ sinh sản.

## 28. HN_297

Khi sinh con bằng kỹ thuật hỗ trợ sinh sản, việc xác định cha mẹ có khác trường hợp mang thai hộ như thế nào?

- Ngày áp dụng: 2026-10-15; multi_hop; hard.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Theo Điều 93 Luật Hôn nhân và gia đình năm 2014, khi sinh con bằng kỹ thuật hỗ trợ sinh sản thông thường, việc xác định cha mẹ đối với cặp vợ chồng được áp dụng theo Điều 88 (xác định cha, mẹ trong thời kỳ hôn nhân), đối với phụ nữ độc thân thì người phụ nữ đó là mẹ của con được sinh ra, và không phát sinh quan hệ cha mẹ - con với người cho tinh trùng, noãn, phôi. Ngược lại, trong trường hợp mang thai hộ vì mục đích nhân đạo (khoản 4 Điều 93 và Điều 94), con sinh ra được xác định là con chung của vợ chồng nhờ mang thai hộ kể từ thời điểm con được sinh ra (chứ không phải của người phụ nữ mang thai hộ).

Chứng cứ corpus:

`l_52_2014_qh13_art_93_clause_1_chunk_1`

1. Trong trường hợp người vợ sinh con bằng kỹ thuật hỗ trợ sinh sản thì việc xác định cha, mẹ được áp dụng theo quy định tại Điều 88 của Luật này.

`l_52_2014_qh13_art_93_clause_2_chunk_1`

2. Trong trường hợp người phụ nữ sống độc thân sinh con bằng kỹ thuật hỗ trợ sinh sản thì người phụ nữ đó là mẹ của con được sinh ra.

`l_52_2014_qh13_art_93_clause_3_chunk_1`

3. Việc sinh con bằng kỹ thuật hỗ trợ sinh sản không làm phát sinh quan hệ cha, mẹ và con giữa người cho tinh trùng, cho noãn, cho phôi với người con được sinh ra.

`l_52_2014_qh13_art_93_clause_4_chunk_1`

4. Việc xác định cha, mẹ trong trường hợp mang thai hộ vì mục đích nhân đạo được áp dụng theo quy định tại Điều 94 của Luật này.

`l_52_2014_qh13_art_94_clause_1_chunk_1`

Con sinh ra trong trường hợp mang thai hộ vì mục đích nhân đạo là con chung của vợ chồng nhờ mang thai hộ kể từ thời điểm con được sinh ra.

## 29. HN_299

Nghĩa vụ cấp dưỡng cho con khi cha mẹ ly hôn được xác định về chủ thể và mức cấp dưỡng như thế nào?

- Ngày áp dụng: 2026-10-15; multi_hop; hard.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Theo Điều 110 Luật Hôn nhân và gia đình năm 2014, cha, mẹ có nghĩa vụ cấp dưỡng cho con chưa thành niên hoặc con đã thành niên không có khả năng lao động và không có tài sản để tự nuôi mình khi không sống chung với con (như sau khi ly hôn) hoặc sống chung nhưng vi phạm nghĩa vụ nuôi dưỡng. Theo Điều 116, mức cấp dưỡng do các bên thỏa thuận căn cứ vào thu nhập, khả năng thực tế của người có nghĩa vụ cấp dưỡng và nhu cầu thiết yếu của con; khi có lý do chính đáng, mức cấp dưỡng có thể thay đổi theo thỏa thuận hoặc theo quyết định của Tòa án nếu không thỏa thuận được.

Chứng cứ corpus:

`l_52_2014_qh13_art_110_clause_1_chunk_1`

Cha, mẹ có nghĩa vụ cấp dưỡng cho con chưa thành niên, con đã thành niên không có khả năng lao động và không có tài sản để tự nuôi mình trong trường hợp không sống chung với con hoặc sống chung với con nhưng vi phạm nghĩa vụ nuôi dưỡng con.

`l_52_2014_qh13_art_116_clause_1_chunk_1`

1. Mức cấp dưỡng do người có nghĩa vụ cấp dưỡng và người được cấp dưỡng hoặc người giám hộ của người đó thỏa thuận căn cứ vào thu nhập, khả năng thực tế của người có nghĩa vụ cấp dưỡng và nhu cầu thiết yếu của người được cấp dưỡng; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

`l_52_2014_qh13_art_116_clause_2_chunk_1`

2. Khi có lý do chính đáng, mức cấp dưỡng có thể thay đổi. Việc thay đổi mức cấp dưỡng do các bên thỏa thuận; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

## 30. HN_300

Việc cấp dưỡng cho con được xác định theo mức cấp dưỡng và phương thức thực hiện ra sao?

- Ngày áp dụng: 2026-10-15; multi_hop; hard.
- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.

Đáp án tham chiếu từ repo (không đưa vào file inference):

Theo Điều 116 Luật Hôn nhân và gia đình năm 2014, mức cấp dưỡng do người có nghĩa vụ và người được cấp dưỡng (hoặc người giám hộ) thỏa thuận dựa trên thu nhập, khả năng thực tế của người cấp dưỡng và nhu cầu thiết yếu của người được cấp dưỡng, và có thể thay đổi khi có lý do chính đáng. Theo Điều 117, việc cấp dưỡng có thể thực hiện định kỳ hàng tháng, hàng quý, nửa năm, hàng năm hoặc một lần; các bên có thể thỏa thuận thay đổi phương thức hoặc tạm ngừng cấp dưỡng nếu người có nghĩa vụ lâm vào tình trạng khó khăn về kinh tế không có khả năng thực hiện; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

Chứng cứ corpus:

`l_52_2014_qh13_art_116_clause_1_chunk_1`

1. Mức cấp dưỡng do người có nghĩa vụ cấp dưỡng và người được cấp dưỡng hoặc người giám hộ của người đó thỏa thuận căn cứ vào thu nhập, khả năng thực tế của người có nghĩa vụ cấp dưỡng và nhu cầu thiết yếu của người được cấp dưỡng; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

`l_52_2014_qh13_art_116_clause_2_chunk_1`

2. Khi có lý do chính đáng, mức cấp dưỡng có thể thay đổi. Việc thay đổi mức cấp dưỡng do các bên thỏa thuận; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

`l_52_2014_qh13_art_117_clause_1_chunk_1`

Việc cấp dưỡng có thể được thực hiện định kỳ hàng tháng, hàng quý, nửa năm, hàng năm hoặc một lần. Các bên có thể thỏa thuận thay đổi phương thức cấp dưỡng, tạm ngừng cấp dưỡng trong trường hợp người có nghĩa vụ cấp dưỡng lâm vào tình trạng khó khăn về kinh tế mà không có khả năng thực hiện nghĩa vụ cấp dưỡng; nếu không thỏa thuận được thì yêu cầu Tòa án giải quyết.

## Loại và chưa chọn

Không chọn không đồng nghĩa câu đó sai. Danh sách dưới chỉ nêu lý do loại kỹ thuật; các câu hợp lệ còn lại không được chọn nhằm giữ đúng 30 câu và ưu tiên phạm vi đơn giản, nguồn trực tiếp.

- HN_037: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_038: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_039: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_040: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_041: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_042: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_043: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_044: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_045: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_046: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_047: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_048: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_049: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_050: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_051: substantive_gold_changed_in_pending_d1
- HN_053: citation_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_056: invalid_citation_identity_or_url_format
- HN_057: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_058: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_059: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_060: incomplete_review_provenance, invalid_citation_identity_or_url_format, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_context_id_provenance, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_063: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_064: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_065: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_068: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_069: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_070: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_071: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_072: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_073: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_074: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_075: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_076: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_077: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_078: known_query_issue, substantive_gold_changed_in_pending_d1
- HN_079: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_080: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_082: substantive_gold_changed_in_pending_d1
- HN_083: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_084: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_085: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_086: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_089: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_090: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_091: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_092: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_093: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_094: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_095: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_096: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_097: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_098: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_099: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_100: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_101: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_102: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_103: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_105: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_106: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_107: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_108: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_109: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_110: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_111: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_113: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_114: substantive_gold_changed_in_pending_d1
- HN_115: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_116: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_117: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_118: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_119: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_120: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_121: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_122: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_123: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_124: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_125: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_126: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_127: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_129: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_130: substantive_gold_changed_in_pending_d1
- HN_131: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_132: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_133: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_134: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_135: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_136: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_137: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_138: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_139: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_140: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_141: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_142: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_143: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_144: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_145: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_146: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_147: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_148: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_149: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_150: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_151: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_152: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_153: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_154: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_157: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_158: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_159: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_160: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_161: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_162: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_163: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_164: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_165: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_166: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_167: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_168: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_170: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_171: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_172: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_174: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_175: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_178: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_179: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_180: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_182: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_184: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_185: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_186: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_188: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_189: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_190: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_191: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_192: citation_article_mapping_mismatch, gold_clause_or_article_mapping_mismatch
- HN_195: article_not_source_checked, citation_article_mapping_mismatch, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_196: citation_article_mapping_mismatch, gold_clause_or_article_mapping_mismatch, substantive_gold_changed_in_pending_d1
- HN_197: citation_article_mapping_mismatch, gold_clause_or_article_mapping_mismatch
- HN_199: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_200: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_201: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_202: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_203: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_204: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_205: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_206: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_207: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_208: citation_article_mapping_mismatch
- HN_209: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_210: citation_article_mapping_mismatch
- HN_211: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_212: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_213: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_214: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_215: citation_article_mapping_mismatch
- HN_216: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_217: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_218: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_219: citation_article_mapping_mismatch
- HN_220: citation_article_mapping_mismatch
- HN_221: citation_article_mapping_mismatch
- HN_222: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_223: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_224: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_225: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_226: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_227: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_228: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_229: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_230: citation_article_mapping_mismatch
- HN_231: citation_article_mapping_mismatch
- HN_232: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_233: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_234: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_235: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_236: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_237: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_238: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_239: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_241: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_243: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_244: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_245: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_247: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_248: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_249: substantive_gold_changed_in_pending_d1
- HN_253: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_254: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_256: substantive_gold_changed_in_pending_d1
- HN_257: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_258: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_259: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_260: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_262: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_263: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_264: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_265: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_266: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_267: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_269: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_270: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_271: substantive_gold_changed_in_pending_d1
- HN_272: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_273: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_274: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, substantive_gold_changed_in_pending_d1, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_275: substantive_gold_changed_in_pending_d1
- HN_276: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_277: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_279: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_280: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_285: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_286: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_287: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_289: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_291: gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_293: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_295: article_not_source_checked, gold_clause_or_article_mapping_mismatch, incomplete_review_provenance, missing_or_duplicate_gold_ids, unverified_answer_kind, unverified_evidence_level, unverified_mapping_status, unverified_review_status, user_requested_exclusion
- HN_298: substantive_gold_changed_in_pending_d1
