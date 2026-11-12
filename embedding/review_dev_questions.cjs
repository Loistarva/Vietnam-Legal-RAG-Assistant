/** Freeze assistant-reviewed supporting-evidence labels before inspecting rankings.
 * This is a corpus support review, not a human legal review or exhaustive qrels.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const folder = path.join(__dirname, 'data');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fixture = fs.readFileSync(path.join(folder, 'priority_bkai_chunks.json'));
const chunks = new Map(JSON.parse(fixture).chunks.map(c => [c.id,c]));
const input = fs.readFileSync(path.join(folder, 'priority_bkai_dev.draft.json'));
const questions = JSON.parse(input);
const decisions = {
 priority_001: {summary:'Điều kiện gồm độ tuổi, tự nguyện, năng lực hành vi và không thuộc các trường hợp cấm được dẫn chiếu.', note:'Khoản 1 Điều 8 trực tiếp liệt kê điều kiện cho nam và nữ; không gán các Điều được dẫn chiếu như nhãn liên quan đầy đủ.'},
 priority_006: {query:'Nam, nữ có đủ điều kiện kết hôn nhưng sống chung không đăng ký kết hôn có làm phát sinh quyền và nghĩa vụ giữa vợ chồng không?', summary:'Không làm phát sinh quyền, nghĩa vụ giữa vợ và chồng; quyền với con và tài sản được xử lý theo quy định riêng.', note:'Bổ sung điều kiện nam, nữ đủ điều kiện kết hôn để câu hỏi khớp phạm vi khoản 1 Điều 14.'},
 priority_011: {summary:'Nơi cư trú do vợ chồng thỏa thuận.', note:'Đoạn nguồn trả lời trực tiếp; tiêu đề Điều đang bị gộp vào nội dung nhưng không mất mệnh đề trả lời.'},
 priority_016: {summary:'Có thể chọn chế độ tài sản theo luật định hoặc theo thỏa thuận.', note:'Khoản 1 Điều 28 nêu đúng hai lựa chọn; không hỏi chi tiết thủ tục lập thỏa thuận.'},
 priority_021: {summary:'Việc chiếm hữu, sử dụng, định đoạt tài sản chung do vợ chồng thỏa thuận.', note:'Câu hỏi chỉ hỏi chủ thể quyết định, không hỏi hình thức hay điều kiện giao dịch tại các khoản khác.'},
 priority_026: {query:'Nghĩa vụ về tài sản của mỗi bên có trước khi kết hôn là nghĩa vụ riêng hay nghĩa vụ chung của vợ chồng?', summary:'Là nghĩa vụ riêng về tài sản của mỗi bên.', note:'Thêm phạm vi tài sản. Phải đọc tiêu đề Điều 45 trong chunk vì phần thân khoản 1 là một mục liệt kê.'},
 priority_031: {summary:'Theo quy định của pháp luật về tố tụng dân sự.', note:'Khoản 1 Điều 53 trả lời đúng câu hỏi về hệ thống quy định, không đủ để giải thích toàn bộ thủ tục nộp đơn.'},
 priority_036: {summary:'Con có quyền được cha mẹ thương yêu, tôn trọng.', note:'Khoản 1 Điều 70 hỗ trợ trực tiếp.'},
 priority_041: {query:'Sau ly hôn, cha mẹ còn quyền và nghĩa vụ chăm sóc, nuôi dưỡng, giáo dục con chưa thành niên không?', summary:'Có, cha mẹ vẫn có quyền và nghĩa vụ đối với con chưa thành niên sau ly hôn.', note:'Thu hẹp tới con chưa thành niên, tránh suy rộng nghĩa vụ cho mọi người con đã thành niên.'},
 priority_046: {summary:'Con có quyền nhận cha, mẹ kể cả khi cha, mẹ đã chết.', note:'Khoản 1 Điều 90 hỗ trợ trực tiếp.'},
};
const source = JSON.parse(fs.readFileSync(path.join(root,'data/chunking_output/documents/L01.json'),'utf8'));
const reviewed = questions.map(q => {
 const decision = decisions[q.question_id];
 if (!decision || q.split !== 'dev') throw new Error('Unexpected question');
 const clause = source.articles.flatMap(a=>a.clauses).find(c=>c.clause_id===q.source_clause_id);
 if (!clause || clause.clause_text !== q.reference_answer_excerpt) throw new Error('Source excerpt drift');
 for(const id of q.relevant_chunk_ids) {
   const chunk = chunks.get(id);
   if(!chunk || chunk.clause_id !== q.source_clause_id || chunk.document_number !== '52/2014/QH13') throw new Error('Invalid supporting evidence');
 }
 return {...q, original_query:q.query, query:decision.query || q.query,
   reference_answer_summary:decision.summary, review_note:decision.note,
   review_status:'assistant_support_reviewed_human_pending', reviewer_type:'assistant',
   relevance_scope:'supporting_clause_only_not_exhaustive', dataset_sha256:hash(fixture)};
});
const output = path.join(folder,'priority_bkai_dev.support_reviewed.json');
fs.writeFileSync(output,JSON.stringify(reviewed,null,2)+'\n');
fs.writeFileSync(path.join(folder,'priority_bkai_dev.review_manifest.json'),JSON.stringify({
 reviewer_type:'assistant', human_review_complete:false, query_count:reviewed.length,
 changed_queries:reviewed.filter(q=>q.query!==q.original_query).map(q=>q.question_id),
 dataset_sha256:hash(fixture), input_labels_sha256:hash(input), output_labels_sha256:hash(fs.readFileSync(output)),
 review_basis:'Read all ten queries, supporting chunk text, article context and parser clause excerpts before running retrieval. No Test labels edited.',
 limitations:['Not an independent human legal review.','Not exhaustive relevance judgments; other valid supporting chunks may be unlabelled.','Small development set with wording close to source; unsuitable for production quality claims.','Corpus still contains partially expired/unknown documents and parser structure errors.']
},null,2)+'\n');
console.log('Reviewed 10 Dev questions; clarified 3 queries; all supporting IDs valid. Human review pending.');
