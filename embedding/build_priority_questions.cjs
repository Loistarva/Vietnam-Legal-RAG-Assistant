/** Draft labels from explicit source clauses, never from model retrieval. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const specs = [
 [8,'Nam và nữ cần đáp ứng những điều kiện nào để kết hôn?'],
 [9,'Chung sống mà không đăng ký kết hôn có giá trị pháp lý của hôn nhân không?'],
 [10,'Người bị cưỡng ép kết hôn có quyền yêu cầu hủy kết hôn không?'],
 [11,'Cơ quan nào xử lý việc kết hôn trái pháp luật?'],
 [12,'Khi bị hủy việc kết hôn trái pháp luật, hai bên có phải chấm dứt quan hệ vợ chồng không?'],
 [14,'Sống chung không đăng ký kết hôn có làm phát sinh quyền và nghĩa vụ vợ chồng không?'],
 [15,'Quyền của con khi cha mẹ sống chung không đăng ký kết hôn được giải quyết thế nào?'],
 [16,'Tài sản của hai người sống chung không đăng ký kết hôn được giải quyết theo cơ sở nào?'],
 [17,'Vợ chồng có quyền và nghĩa vụ ngang nhau trong gia đình không?'],
 [19,'Vợ chồng có những nghĩa vụ gì trong việc chăm sóc và giúp đỡ nhau?'],
 [20,'Ai quyết định nơi cư trú của vợ chồng?'],
 [21,'Vợ chồng phải tôn trọng danh dự và nhân phẩm của nhau như thế nào?'],
 [22,'Vợ chồng có phải tôn trọng quyền tự do tôn giáo của nhau không?'],
 [24,'Việc đại diện giữa vợ chồng trong giao dịch được xác định theo cơ sở nào?'],
 [26,'Tài sản chung chỉ đứng tên một người thì việc đại diện giữa vợ chồng được thực hiện theo quy định nào?'],
 [28,'Vợ chồng được lựa chọn những chế độ tài sản nào?'],
 [29,'Lao động trong gia đình có bị phân biệt với lao động có thu nhập khi xác định quyền với tài sản chung không?'],
 [30,'Vợ chồng có quyền thực hiện giao dịch đáp ứng nhu cầu thiết yếu của gia đình không?'],
 [31,'Giao dịch về căn nhà là nơi ở duy nhất có cần sự thỏa thuận của vợ chồng không?'],
 [33,'Những tài sản nào được coi là tài sản chung của vợ chồng?'],
 [35,'Ai quyết định việc chiếm hữu, sử dụng và định đoạt tài sản chung?'],
 [37,'Nghĩa vụ từ giao dịch do cả hai vợ chồng cùng xác lập thuộc loại nghĩa vụ nào?'],
 [39,'Thời điểm có hiệu lực của việc chia tài sản chung trong thời kỳ hôn nhân được xác định ra sao?'],
 [43,'Tài sản có trước khi kết hôn hoặc được tặng cho riêng có phải tài sản riêng không?'],
 [44,'Một người có quyền quyết định nhập tài sản riêng vào tài sản chung không?'],
 [45,'Nghĩa vụ có trước khi kết hôn thuộc trách nhiệm riêng hay chung?'],
 [46,'Nhập tài sản riêng vào tài sản chung được thực hiện trên cơ sở nào?'],
 [47,'Thỏa thuận chế độ tài sản trước khi kết hôn cần có hình thức gì?'],
 [51,'Những ai có quyền yêu cầu Tòa án giải quyết ly hôn?'],
 [52,'Nhà nước có khuyến khích hòa giải ở cơ sở khi vợ chồng yêu cầu ly hôn không?'],
 [53,'Tòa án thụ lý đơn yêu cầu ly hôn theo quy định nào?'],
 [55,'Khi nào Tòa án công nhận thuận tình ly hôn?'],
 [56,'Khi một bên yêu cầu ly hôn và hòa giải không thành, Tòa án căn cứ vào đâu để giải quyết?'],
 [57,'Quan hệ hôn nhân chấm dứt từ thời điểm nào sau khi Tòa án cho ly hôn?'],
 [69,'Cha mẹ có nghĩa vụ gì trong việc tôn trọng và chăm sóc con?'],
 [70,'Con có quyền được cha mẹ yêu thương và tôn trọng không?'],
 [71,'Cha và mẹ có quyền và nghĩa vụ ngang nhau trong việc chăm sóc con không?'],
 [72,'Cha mẹ có trách nhiệm gì đối với việc học tập của con?'],
 [73,'Trong trường hợp nào cha mẹ là người đại diện theo pháp luật của con?'],
 [75,'Con có quyền có tài sản riêng không?'],
 [81,'Sau ly hôn cha mẹ còn nghĩa vụ chăm sóc và giáo dục con không?'],
 [82,'Người không trực tiếp nuôi con phải tôn trọng quyền sống chung của con với ai?'],
 [83,'Người trực tiếp nuôi con có quyền yêu cầu bên kia thực hiện nghĩa vụ đối với con không?'],
 [84,'Ai có thể yêu cầu thay đổi người trực tiếp nuôi con sau ly hôn?'],
 [88,'Con sinh trong thời kỳ hôn nhân được xác định là con chung thế nào?'],
 [90,'Con có quyền nhận cha mẹ khi cha mẹ đã chết không?'],
 [91,'Cha mẹ có quyền nhận con khi con đã chết không?'],
 [94,'Con sinh ra từ mang thai hộ vì mục đích nhân đạo được xác định là con của ai?'],
 [110,'Cha mẹ phải cấp dưỡng cho con trong những trường hợp nào?'],
 [116,'Mức cấp dưỡng được xác định dựa vào những yếu tố nào?'],
];
const fixture = fs.readFileSync(path.join(root, 'embedding/data/priority_chunks.json'));
const chunks = JSON.parse(fixture).chunks;
const doc = JSON.parse(fs.readFileSync(path.join(root, 'data/chunking_output/documents/L01.json'), 'utf8'));
const questions = specs.map(([number, query], index) => {
 const article = doc.articles.find(a => +a.article_number === number);
 const clause = article.clauses[0];
 const relevant = chunks.filter(c => c.clause_id === clause.clause_id);
 if (!relevant.length) throw new Error(`No evidence: ${number}`);
 return {question_id: `priority_${String(index + 1).padStart(3,'0')}`, split: index % 5 === 0 ? 'dev' : 'test', query, relevant_chunk_ids: relevant.map(c => c.id), reference_answer_excerpt: clause.clause_text, source_clause_id: clause.clause_id, review_status: 'draft_requires_human_review'};
});
const out = path.join(root, 'embedding/data');
fs.writeFileSync(path.join(out, 'priority_questions.draft.json'), JSON.stringify({status:'draft_requires_human_review', scope:'L01 only; all seven documents are retrieval distractors. Labels identify supporting clauses and are not exhaustive relevance judgments.', dataset_sha256:crypto.createHash('sha256').update(fixture).digest('hex'), questions}, null, 2) + '\n');
for (const split of ['dev','test']) fs.writeFileSync(path.join(out, `priority_${split}.draft.json`), JSON.stringify(questions.filter(q => q.split === split), null, 2) + '\n');
console.log(`Created ${questions.length} draft questions (10 dev / 40 test).`);
