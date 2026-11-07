// Read Git blobs, never mutate datasets or freeze manifests. Node 18+; no dependencies.
const fs = require('node:fs');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const path = require('node:path');
process.chdir(path.resolve(__dirname, '..'));
const git = (...args) => cp.execFileSync('git', args, {maxBuffer: 64*1024*1024});
const { validateEvidence } = require('./week09_evidence_guard.cjs');
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const text = (ref, file) => git('show', `${ref}:${file}`).toString('utf8').replace(/^\uFEFF/, '');
const json = (ref, file) => JSON.parse(text(ref,file));
const sorted = obj => Array.isArray(obj) ? obj.map(sorted) : obj && typeof obj === 'object' ? Object.fromEntries(Object.keys(obj).sort().map(k=>[k,sorted(obj[k])])) : obj;
// Equivalent to canonical_json_sha256 for these JSON datasets (no floats).
const canonical = obj => sha(JSON.stringify(sorted(obj)).replace(/\r\n/g,'\n')+'\n');
const base='origin/testing', pr25='origin/pr/25';
const audit = ref => {
 const corpusFile='data/chunking_output/chunks.jsonl';
 const chunks=text(ref,corpusFile).trim().split(/\r?\n/).map(JSON.parse);
 const dev=json(ref,'data/benchmark/queries_dev.json'), test=json(ref,'data/benchmark/queries_test.json'), gold=json(ref,'data/benchmark/ground_truth.json');
 const byId=new Map(gold.map(g=>[g.id,g])), chunkIds=new Set(chunks.map(c=>c.chunk_id));
 const testIds=new Set(test.map(q=>q.id));
 const clauses=new Set(test.flatMap(q=>byId.get(q.id)?.gold_clause_ids||[]));
 const qhash=canonical(test), ghash=canonical({questions:test,test_ground_truth:test.map(q=>byId.get(q.id))});
 const qm=json(ref,'docs/test_questions_freeze.json'), gm=json(ref,'docs/test_gold_freeze.json');
 const unresolved=gold.flatMap(g=>(g.gold_context_ids||[]).filter(id=>!chunkIds.has(id)).map(id=>({id:g.id,chunk_id:id})));
 const reviewed=gold.filter(g=>g.review_status==='source_checked');
 const draft=gold.filter(g=>g.review_status!=='source_checked');
 const nd126=reviewed.filter(g=>(g.gold_context_ids||[]).some(id=>/^nd_126_2014_nd_cp_art_(\d+)_/.test(id)&&Number(id.match(/_art_(\d+)_/)[1])>=19&&Number(id.match(/_art_(\d+)_/)[1])<=50));
 return {ref,sha:git('rev-parse',ref).toString().trim(),chunks:chunks.length,corpus_git_blob_sha256:sha(git('show',`${ref}:${corpusFile}`)),dev:dev.length,test:test.length,gold:gold.length,reviewed:reviewed.length,draft:draft.length,draft_confirmed:draft.filter(g=>g.gold_context_ids_confirmed===true).map(g=>g.id),duplicate_chunk_ids:chunks.length-chunkIds.size,duplicate_query_ids:dev.length+test.length-new Set([...dev,...test].map(q=>q.id)).size,duplicate_gold_ids:gold.length-byId.size,missing_gold_query_ids:[...dev,...test].filter(q=>!byId.has(q.id)).map(q=>q.id),split_id_overlap:dev.filter(q=>testIds.has(q.id)).map(q=>q.id),reviewed_clause_overlap:dev.filter(q=>byId.get(q.id)?.review_status==='source_checked'&&(byId.get(q.id).gold_clause_ids||[]).some(c=>clauses.has(c))).map(q=>q.id),unresolved_gold_contexts:unresolved,all_nd126_articles_19_50:gold.filter(g=>(g.gold_context_ids||[]).some(id=>/^nd_126_2014_nd_cp_art_(\d+)_/.test(id)&&Number(id.match(/_art_(\d+)_/)[1])>=19&&Number(id.match(/_art_(\d+)_/)[1])<=50)).map(g=>g.id),reviewed_nd126_articles_19_50:nd126.map(g=>g.id),test_questions_canonical_sha256:qhash,test_gold_canonical_sha256:ghash,questions_manifest_sha256:qm.sha256,gold_manifest_sha256:gm.sha256,questions_freeze_match:qhash===qm.sha256,gold_freeze_match:ghash===gm.sha256,configs:Object.fromEntries(['retrieval/config.yaml','reranking/config.yaml'].map(f=>[f,{git_blob_sha256:sha(git('show',`${ref}:${f}`)),content:text(ref,f)}]))};
};
const snapshots=[base,...[25,26,27,28,29,32].map(n=>`origin/pr/${n}`)].map(audit);
const merged=ref=>{try{git('merge-base','--is-ancestor',ref,base);return true;}catch{return false;}};
const refs=snapshots.map(s=>({ref:s.ref,sha:s.sha,head_is_ancestor_of_testing:merged(s.ref)}));
const before=json(base,'data/benchmark/ground_truth.json'), after=json(pr25,'data/benchmark/ground_truth.json');
const old=new Map(before.map(g=>[g.id,g]));
const removedGoldIds=before.filter(g=>!after.some(a=>a.id===g.id)).map(g=>g.id);
const changed=after.filter(g=>JSON.stringify(sorted(g))!==JSON.stringify(sorted(old.get(g.id))));
const corpus=ref=>new Map(text(ref,'data/chunking_output/chunks.jsonl').trim().split(/\r?\n/).map(JSON.parse).map(c=>[c.chunk_id,c]));
const bc=corpus(base),pc=corpus(pr25);
const impact={removed_gold_ids:removedGoldIds,added_chunks:[...pc.keys()].filter(k=>!bc.has(k)),removed_chunks:[...bc.keys()].filter(k=>!pc.has(k)),modified_existing_chunks:[...pc.keys()].filter(k=>bc.has(k)&&JSON.stringify(sorted(pc.get(k)))!==JSON.stringify(sorted(bc.get(k)))),changed_gold_ids:changed.map(g=>g.id),changed_reviewed_gold_ids:changed.filter(g=>old.get(g.id)?.review_status==='source_checked').map(g=>g.id),changed_test_gold_ids:changed.filter(g=>json(base,'data/benchmark/queries_test.json').some(q=>q.id===g.id)).map(g=>g.id),changed_fields:Object.fromEntries([...new Set(changed.flatMap(g=>[...Object.keys(g),...Object.keys(old.get(g.id)||{})]))].map(k=>[k,changed.filter(g=>JSON.stringify(sorted(g[k]))!==JSON.stringify(sorted(old.get(g.id)?.[k]))).length]).filter(([,v])=>v))};
const api=JSON.parse(fs.readFileSync('reports/baseline/github_state_20261106.json','utf8'));
for(const p of api.details){if(snapshots.find(s=>s.ref===`origin/pr/${p.number}`)?.sha!==p.head_sha)throw Error(`API/ref SHA mismatch PR ${p.number}; refresh API and refs`);}
const tests=Object.fromEntries(['testing','pr25','pr27','pr32'].map(n=>[n,JSON.parse(fs.readFileSync(`reports/baseline/checks_${n}.json`,'utf8'))]));
for(const [n,r] of Object.entries(tests)){if(r.sha!==snapshots.find(s=>s.ref===(n==='testing'?base:`origin/pr/${n.slice(2)}`)).sha)throw Error(`Stale tests ${n}`);}
const probe=JSON.parse(fs.readFileSync('reports/baseline/zero_shot_probe_pr32.json','utf8'));
validateEvidence(snapshots,api,tests,probe);
const b=snapshots[0],p=snapshots[1],d1=snapshots.find(s=>s.ref==='origin/pr/27');
const prTable=api.details.map(p=>{
 const run=api.workflow_runs.find(r=>r.head_sha===p.head_sha&&r.event==='pull_request');
 const mergeProof=p.merged?`MERGED ${p.merge_commit_sha}`:p.state==='closed'?'Đóng, chưa merge':'Đang mở, chưa merge';
 return `| [#${p.number}](${p.html_url}) | ${p.head_sha} | ${mergeProof} | ${run?`[tests #${run.run_number}](${run.html_url}) ${run.conclusion}`:'Chưa có run trong snapshot'} |`;
}).join('\n');
const requiredArtifacts=Object.fromEntries(snapshots.map(s=>[s.ref,git('ls-tree','-r','--name-only',s.ref,'evaluation/manifests','evaluation/rubrics').toString().trim().split('\n').filter(Boolean)]));
const pr26TreeMatchesTesting=git('rev-parse','origin/pr/26^{tree}').toString().trim()===git('rev-parse',base+'^{tree}').toString().trim();
const evidence={required_artifacts:requiredArtifacts,pr26_tree_matches_testing:pr26TreeMatchesTesting,observed_at:new Date().toISOString(),github_snapshot_observed_at:api.observed_at,git_status_before_reports:git('status','--porcelain').toString().trim(),refs,snapshots,impact,api_file:'github_state_20261106.json',local_checks:Object.fromEntries(Object.entries(tests).map(([n,t])=>[n,{sha:t.sha,file:`checks_${n}.json`,all_exit_zero:t.results.every(r=>r.exit_code===0)}])),limitations:['GitHub merge metadata is authoritative; ancestry alone misses squash merges.','CI success proves configured tests only, not Sprint 9 completion.','No live ES/Qdrant/model or official evaluation run.','Source-level legal correctness is not established by structural checks.']};
fs.mkdirSync('reports/baseline',{recursive:true});fs.mkdirSync('reports/data',{recursive:true});
fs.writeFileSync('reports/baseline/m0_audit_evidence.json',JSON.stringify(evidence,null,2)+'\n');
const write=(file,body)=>fs.writeFileSync(file,body.trim()+'\n');
const localTable=Object.entries(tests).map(([n,t])=>`| ${n} | ${t.sha.slice(0,7)} | ${t.results.slice(0,3).every(r=>r.exit_code===0)?'PASS cả 3':'Xem log'} | ${t.results[3].stdout.trim().split('\n').at(-1)} |`).join('\n');
write('reports/baseline/m0_repo_snapshot.md',`
# D1.0 — Baseline repo Tuần 9

Ngày: 06/11/2026 (Asia/Saigon). Thời điểm audit UTC: ${evidence.observed_at}; GitHub snapshot UTC: ${api.observed_at}. Nguồn: Kế hoạch Tuần 9 V3; Git blobs sau fetch; GitHub REST API PR metadata và Actions. Không dùng nguyên trạng các nhận định cũ trong kế hoạch.

## Kết luận

Baseline code đã tích hợp: origin/testing tại **${b.sha}**. PR #26 đã squash-merge chính tại SHA này; candidate_text/rerank fixes đã có, không còn task chờ merge #26. PR #25 đã sửa mapping nhưng vẫn mở; PR #27 có sửa Gold và xác nhận mới, vẫn mở; metrics hiện theo PR #32, không tiếp tục coi #28 là PR cần merge.

Đã hoàn thành phần điều tra và báo cáo D1.0; chờ reviewer Tech Lead + Dev 4. **M0 chưa đóng**: cần quyết định nhận/hoãn các PR đang mở, xác nhận G3, Dev30/rubric guide và M1. Không cần chờ tất cả nhánh hết lỗi để làm các task độc lập. Báo cáo không tự quyết merge, defer hay cho phép official A/B.

## 1. PR và CI xác minh trực tiếp

| PR | Head SHA | Trạng thái GitHub | CI đúng head |
| --- | --- | --- | --- |
${prTable}

PR #28, #30, #31 đã đóng chưa merge; nhánh fix/metrics tiếp tục qua #32. PR #26 merged_at=${api.details.find(p=>p.number===26).merged_at}; merge_commit_sha=${api.details.find(p=>p.number===26).merge_commit_sha}. Không suy ra “chưa merge” bằng merge-base --is-ancestor của head, vì squash làm thay đổi SHA. CI xanh không đồng nghĩa đã review/merge hay hoàn tất yêu cầu Tuần 9.

## 2. Những phần mọi người đã sửa

| Phần | Sửa đổi đã kiểm tra | Trạng thái đối với baseline |
| --- | --- | --- |
| PR #25, 07d365d / 08bcb52 / 54c0e37 | Thay 6 placeholder bằng 9 chunk có nguồn; cập nhật validator/tests; chỉnh draft Dev tránh clause overlap Test. 195 draft confirmed chỉ là xác nhận mapping, vẫn chưa duyệt pháp lý. | Đã sửa trên PR, chưa merge. Chi tiết ở corpus_change_impact.md. |
| PR #26 → f89ef83 | E8/G5, candidate_text=document_breadcrumb_chunk_text; kết quả Dev và context pipeline. | Đã squash-merge; cấu hình này có sẵn trong baseline. |
| PR #27, e39a372 / e8b5bd9 / 4171b5e / 6288e8c | Sửa đáp án Dev HN_256/HN_298; sửa Test HN_156/HN_181/HN_246/HN_268 và re-freeze; ghi xác nhận 24 câu Dev 5; đồng bộ testing. Giữ xác nhận 20 câu Dev 3 tại 18d3325. | Đã push/CI xanh, chưa merge; hash phải lấy theo phiên bản thực được nhận. |
| PR #29, 89906f8 | Contract tài liệu: canonical IDs, temporal fields, chữ ký retriever, query rỗng, precomputed date checks, benchmark dates và candidate flow. | Đang mở; không coi tài liệu là code runtime mới. |
| PR #32, 06d0784 → 94cc911 → 1700f91 | Metrics Strict/Parent dùng cùng Top-K chunk; provenance kiểm corpus/query/date/config; baseline/final-test metric runners; freeze guard retrieval Test; config đồng bộ testing. Xóa baseline cũ/zero-shot artifacts cũ, thêm run_zero_shot_dev/test. | CI xanh tại head 1700f91, chưa merge. Zero-shot entry points vẫn cần điều chỉnh cho Tuần 9 (xem validation report). |

## 3. Danh tính dữ liệu và hash

- Corpus: ${b.chunks} chunks; Dev ${b.dev}; Test ${b.test}; source_checked ${b.reviewed}; draft/other ${b.draft}.
- Corpus Git-byte SHA-256: **${b.corpus_git_blob_sha256}**.
- Baseline Test questions canonical SHA-256: ${b.test_questions_canonical_sha256}.
- Baseline Test Gold canonical SHA-256: ${b.test_gold_canonical_sha256}.
- PR #27 Test questions canonical SHA-256: ${d1.test_questions_canonical_sha256}.
- PR #27 Test Gold canonical SHA-256: **${d1.test_gold_canonical_sha256}**.
- Mỗi phiên bản khớp hai manifest riêng. PR #27 khác baseline là thay đổi đã re-freeze có ghi trong PR, không phải freeze lỗi. Commit notes-only 18d3325 không đổi Test, nhưng không thể suy rộng điều đó cho các commit sửa đáp án sau này.

Canonical freeze: sorted keys, ensure_ascii=false, separators=(',', ':'), CRLF normalize, thêm newline; kiểm lại bằng Python freeze scripts. Corpus/config hash tính từ raw Git blob để tránh nhầm CRLF checkout Windows. Runtime dùng hash file thực phải được Dev 4 đối chiếu; không tráo hai loại hash.

## 4. Config baseline

${Object.entries(b.configs).map(([f,v])=>'- '+f+': SHA-256 '+v.git_blob_sha256+'\n\n~~~yaml\n'+v.content.trim()+'\n~~~').join('\n\n')}

Top-50 fused → rerank → Top-5; result_top_k=10 là cutoff retrieval result, không được dùng làm giới hạn 10 candidate trước rerank. Không retune Retrieval cho official A/B. Runtime/index identity chưa được kiểm tra live.

## 5. Kiểm tra thực chạy

| Checkout riêng | SHA | Validator + 2 freeze checks | Full pytest theo pytest.ini |
| --- | --- | --- | --- |
${localTable}

Raw stdout/stderr và command ở checks_testing.json, checks_pr25.json, checks_pr27.json, checks_pr32.json. Full suite có 1 skipped ở mỗi checkout; không coi skipped là pass. Môi trường offline và fixtures/mocks; không chạy official Test retrieval hoặc generation. CI từ GitHub là bằng chứng bổ sung trên môi trường workflow riêng.

## 6. Điều kiện còn chờ

- Tech Lead: quyết định PR #25/#27/#29/#32; #26 đã merge; #28 đóng và không phải merge target nữa.
- Dev 5/4: G3 handoff artifact đã push + SHA và replay provenance. Không có origin/results/rerank trong refs hiện tại chưa chứng minh không có artifact ở nhánh/path khác; cần owner chỉ đúng artifact. PR #26 branch bị xóa là bình thường sau squash merge.
- Dev 2: 30-ID manifest và rubric guide (chưa phải score sheet). Không thấy evaluation/manifests hoặc evaluation/rubrics ở testing và các head được audit; cần bàn giao trước official run.
- Dev 3/2: prompt A/M1, benchmark as_of_date, num_predict đồng nhất, structured output và immutable run manifest.
- Dev 4: corpus/index/version agreement; nếu nhận #25 thì rebuild/migration ES/Qdrant, precompute lại hoặc chứng minh tương thích.

## 7. Tái lập và working tree

Cập nhật refs bằng git fetch và snapshot GitHub bằng scripts/fetch_week09_github_state.ps1 (lưu riêng artifact theo ngày; script audit này dùng snapshot 20261106). Chạy node scripts/audit_week09_baseline.cjs sau khi cập nhật refs và snapshot. Script từ chối nếu SHA API/ref hoặc SHA kết quả test không khớp. Chạy Python scripts/check_week09_ref.py <checkout> <result.json> để kiểm lại từng phiên bản, dùng môi trường Python có dependency repo. Snapshot API/checks có thời điểm riêng; script không tự coi dữ liệu lưu cũ là GitHub live.

Working tree trước sinh báo cáo:

~~~text
${evidence.git_status_before_reports||'(clean)'}
~~~

Các thay đổi local là tài liệu/audit; không sửa benchmark, corpus, runtime config hoặc manifest Test. Chưa commit/push. Đây là snapshot kỹ thuật, không phải biên bản quyết định của Tech Lead.
`);
write('reports/data/corpus_change_impact.md',`
# D1.0 — Tác động PR #25 sau các commit đã sửa

So sánh trực tiếp testing ${b.sha} với PR #25 ${p.sha}. PR đang mở; Trạng thái CI head ghi tại m0_repo_snapshot.md theo GitHub snapshot ${api.observed_at}. Không gộp “đã sửa” với “đã merge”.

## 1. Những gì đã được xử lý

07d365d thay sáu mapping placeholder bằng nguồn/chunk production; 08bcb52 sửa validation/tests cho mapping hoàn chỉnh; 54c0e37 sửa câu Dev draft để tránh giao Khoản Test. Full pytest trên đúng PR head: ${tests.pr25.results[3].stdout.trim().split('\n').at(-1)}; validator và hai freeze checks PASS.

${p.draft} câu vẫn draft/other; gold_context_ids_confirmed=true được docs/benchmark_label_provenance.md giải thích là xác nhận mapping tồn tại/khớp corpus. Không gọi đây là lỗi nâng 195 câu thành Gold pháp lý. Metric official tiếp tục chỉ dùng source_checked.

## 2. Delta định lượng

| Chỉ tiêu | Baseline | PR #25 |
| --- | --- | --- |
| Corpus chunks | ${b.chunks} | ${p.chunks} |
| Gold source_checked | ${b.reviewed} | ${p.reviewed} |
| Draft/other | ${b.draft} | ${p.draft} |
| Draft confirmed mapping | ${b.draft_confirmed.length} | ${p.draft_confirmed.length} |
| Gold context không tồn tại | ${b.unresolved_gold_contexts.length} | ${p.unresolved_gold_contexts.length} |
| Reviewed Dev giao clause với Test (số câu) | ${b.reviewed_clause_overlap.length} | ${p.reviewed_clause_overlap.length} |
| Mọi record dùng ID Điều 19–50 NĐ126 | ${b.all_nd126_articles_19_50.length} | ${p.all_nd126_articles_19_50.length} |
| Source_checked trong nhóm đó | ${b.reviewed_nd126_articles_19_50.length} | ${p.reviewed_nd126_articles_19_50.length} |

26 record trong nhóm NĐ126 là draft; đây là danh sách cần source review khi chuyển Gold, không phải 26 câu đã duyệt mới bị phát hiện sai. Audit ID không kết luận hiệu lực pháp luật; không sửa luật/dữ liệu theo suy đoán.

Corpus thêm ${impact.added_chunks.length}, xóa ${impact.removed_chunks.length}, sửa chunk cũ ${impact.modified_existing_chunks.length}. ${impact.changed_gold_ids.length} record ground_truth thay đổi; xóa record ${impact.removed_gold_ids.length}; source_checked thay đổi ${impact.changed_reviewed_gold_ids.length}; Test thay đổi ${impact.changed_test_gold_ids.length}.

Corpus hash baseline: ${b.corpus_git_blob_sha256}; PR: ${p.corpus_git_blob_sha256}. Test questions/Gold của PR vẫn khớp manifest và bằng baseline.

Các trường Gold thay đổi:

${Object.entries(impact.changed_fields).map(([k,v])=>'- '+k+': '+v).join('\n')}

Chín chunk mới:

${impact.added_chunks.map(id=>'- '+id).join('\n')}

## 3. Việc tích hợp cần làm nếu nhận PR

1. Owner review nguồn/provenance 9 chunk và quyết định accept/defer; report D1.0 không tự quyết.
2. Rebuild hoặc migration có kiểm soát ES/Qdrant cho corpus 2173; ghi hash/index/version mới. Không dùng artifact corpus 2164 như thể là bản 2173.
3. Kiểm tra kết quả tích hợp với #27 và #32: giữ các sửa đáp án/reviewer/freeze mới, bảo đảm evaluator chỉ chấm nhãn được duyệt. Không kết luận có conflict chỉ vì cùng file; cần thử tích hợp trước.
4. Chạy validator, leakage, freeze và tests sau tích hợp. Chỉ re-freeze khi payload Test thực sự đổi và được phép; thay corpus một mình không bắt buộc đổi hash Test.

## 4. Phần còn là giới hạn tài liệu

docs/benchmark_label_provenance.md giải thích phần 294/300 và 6 placeholder là lịch sử, nhưng vẫn có số liệu cũ/mệnh đề cũ về confirmed ở phần sau. Đây là điểm làm rõ tài liệu khi bàn giao, không phủ nhận các commit mapping đã sửa. Bằng chứng machine-readable: ../baseline/m0_audit_evidence.json.
`);
write('reports/baseline/m0_validation_results.md',`
# D1.0 — Kiểm tra bản sửa mới và vấn đề còn lại

Audit 06/11/2026. So sánh code trên từng head riêng; không merge mọi nhánh vào planning. GitHub API và CI được lưu tại github_state_20261106.json; raw local logs tại checks_*.json.

## 1. Kết quả chạy độc lập

| Checkout | SHA | Validator/freeze | pytest toàn bộ cấu hình repo |
| --- | --- | --- | --- |
${localTable}

Mỗi checkout chạy scripts/validate_benchmark.py, scripts/freeze_test.py --verify, scripts/freeze_gold.py --verify và python -m pytest -q; HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1. Python/runtime cụ thể có trong JSON. Không chạy model thật hoặc official A/B/Test retrieval. Một test skipped được giữ đúng trạng thái; không chứng minh nguồn luật đã được duyệt hết.

Raw logs lưu exit_code riêng của từng lệnh; tất cả validator/freeze/pytest trong bảng đều exit 0.

## 2. Phần đã sửa — không mở lại lỗi cũ

- PR #25: placeholder, validator và draft clause-overlap đã được sửa trong phạm vi PR; confirmed mapping không tương đương source_checked. Không kết luận 195 draft là lỗi mới.
- PR #26: đã squash-merge tại f89ef83; không còn “chờ merge #26”.
- PR #27: xác nhận Dev 3/Dev 5, sửa answer/citation/reviewer và re-freeze Test đã push; CI #134/#133 success. Chênh hash giữa PR và testing là có giải thích, không tự gọi là corruption.
- PR #32: CI mới #130/#129 success. Run lỗi cũ #125 thuộc deda63d không phải trạng thái head hiện hành. #28 đã đóng chưa merge, không dùng CI đỏ #28 để kết luận metrics mới đang lỗi.

## 3. Khoảng thiếu Tuần 9 đã nhìn thấy trong code hiện tại

| ID | Kết luận có phạm vi | Bằng chứng / hành động |
| --- | --- | --- |
| W9-01 | Zero-shot chưa sẵn sàng official Tuần 9, dù CI metrics xanh | PR #32 scripts/run_zero_shot_dev.py nhận --queries tùy ý và gọi run_benchmark; evaluation/zero_shot.py::load_questions kiểm ID/question nhưng chưa kiểm Dev-only/source_checked/30-ID manifest. Cần guard và chọn đúng official IDs trước gọi model. |
| W9-02 | Đường Zero-shot Test còn thiếu holdout guard | PR #32 scripts/run_zero_shot_test.py mặc định queries_test.json và gọi generation không kiểm freeze/approval. evaluation/test_run_freeze.py có guard cho retrieval Test nhưng không tự bảo vệ entry point này. Chưa chạy script; Dev 2 cần khóa/tách đường này trước bàn giao. |
| W9-03 | Generation config/output chưa theo V3 | PR #32 evaluation/zero_shot.py::answer_question dùng num_predict=512; chỉ truyền question, chưa truyền benchmark as_of_date và chưa lưu done_reason/truncation. Kế hoạch đề xuất 1024 hoặc giá trị M1; Dev 3/2 cần chốt và đồng bộ A/B. Không retune trên 30 official IDs. |
| W9-04 | Artifacts M0/M1 còn thiếu ở các head khảo sát | Không có evaluation/manifests/dev_gold_30_manifest.json/rubric guide ở testing hoặc PR heads khảo sát. Cần Dev 2 bàn giao, Dev 1 D1.4 kiểm leakage; score sheet chỉ sau blind scoring. |
| W9-05 | G3/index identity chưa xác minh đủ | Cần owner chỉ artifact đã push/version/hash và ES/Qdrant identity. Không có tên nhánh results/rerank không đủ để kết luận artifact không tồn tại. |

Probe tái lập: Python scripts/probe_week09_zero_shot.py <PR32 checkout> <result.json>. zero_shot_probe_pr32.json xác nhận loader nhận câu synthetic split=test, mock generation dùng num_predict=512 và trả str làm mất done_reason. Không đọc Test thật và không gọi model thật.

Đây là khoảng thiếu so với yêu cầu Tuần 9 và các điều kiện tích hợp, không phải lý do tuyên bố toàn bộ sửa Sprint 6 thất bại. Không sửa code thuộc Dev 2/3/4/5 trong D1.0; report chỉ nêu bằng chứng và consumer requirement.

## 4. Kiểm tra công cụ audit trước commit

Evidence guard đã kiểm bằng node --test test/test_week09_evidence_guard.cjs: chặn log thiếu command, exit lỗi/timeout, SHA cũ, thiếu bằng chứng clean checkout, checkout bị sửa, PR metadata trùng, freeze mismatch và probe cũ. Node/Python/PowerShell syntax đã kiểm riêng. Không lấy PASS từ câu chữ cố định: generator chỉ sinh báo cáo sau khi validateEvidence chấp nhận đầy đủ bằng chứng đúng SHA và exit 0.

## 5. Kết luận

Không thấy failure trong full pytest của bốn checkout đã chạy. Các sửa mới đã được tính vào snapshot, kể cả squash merge #26 và PR #32 thay #28. D1.0 có đủ báo cáo/hash/config/impact/test evidence để review. M0 vẫn cần Tech Lead ghi accept/defer các PR mở, chốt corpus/Test sau tích hợp và xác nhận handoff/Dev30/M1; CI xanh không thay thế các quyết định đó.
`);
console.log(JSON.stringify({baseline:b.sha,prs:api.details.map(p=>({number:p.number,merged:p.merged,state:p.state})),local_checks:evidence.local_checks},null,2));