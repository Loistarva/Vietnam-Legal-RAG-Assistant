/** Recompute v2 Dev metrics and compare identical query/label semantics to baseline. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
const folder='data/structure_v2/benchmark/';
const dataPath='data/structure_v2/embedding/priority_bkai_chunks.json';
const labelPath='data/structure_v2/embedding/priority_bkai_dev.draft.json';
const corpus=read(dataPath).chunks, byId=new Map(corpus.map(c=>[c.id,c]));
const labels=read(labelPath), oldLabels=read('embedding/data/priority_bkai_dev.support_reviewed.json');
const semantics=qs=>qs.map(q=>[q.question_id,q.query,[...q.relevant_chunk_ids].sort()]);
if(JSON.stringify(semantics(labels))!==JSON.stringify(semantics(oldLabels)) || labels.some(q=>q.split!=='dev') || labels.length!==10)throw Error('Dev semantics differ');
const status=read(folder+'run_status.json');
const baselineContext=read('embedding/results/priority_dense_dev_comparison.json');
if(!status.complete || status.dataset_sha256!==hash(dataPath) || status.labels_sha256!==hash(labelPath))throw Error('Run incomplete or stale');
const models=[['bkai','BKAI','priority_bkai_dev_support_reviewed.json'],['aiteamvn','AITeamVN','priority_aiteamvn_dev_support_reviewed.json'],['bge_m3','BGE-M3','priority_bge_m3_dev_support_reviewed.json']];
const rows=models.map(([slug,name,oldFile])=>{
 const run=read(folder+slug+'_dev.json'),audit=read(folder+slug+'_token_audit.json');
 const old=read('embedding/results/'+oldFile);
 if(old.chunk_file_sha256!==baselineContext.dataset_sha256||old.ground_truth_sha256!==baselineContext.labels_sha256)throw Error(`${name}: baseline inputs differ from recorded context`);
 const priorModel=baselineContext.models.find(m=>m.model===run.model);
 const snapshots=status.models[slug].observed_cache_snapshots;
 const weightEvidence=slug==='bge_m3'&&snapshots.length>1?read(folder+'bge_weight_equivalence.json'):null;
 if(weightEvidence && (!weightEvidence.all_tensor_values_and_dtypes_equal || !snapshots.includes(weightEvidence.additional_safetensors_snapshot)))throw Error('BGE weight equivalence is unverified');
 const mainRevision=status.models[slug].cached_main_revision || (snapshots.length===1?snapshots[0]:weightEvidence?.main_revision);
 if(!priorModel||!snapshots.includes(mainRevision)||mainRevision!==priorModel.model_revision)throw Error(`${name}: model main revision differs from baseline`);
 if(run.chunk_file_sha256!==hash(dataPath)||run.ground_truth_sha256!==hash(labelPath)||audit.dataset_sha256!==hash(dataPath)||audit.oversized_count!==0||run.chunk_count!==corpus.length||audit.chunk_count!==corpus.length)throw Error(`${name}: input/count/audit mismatch`);
 const seen=new Set();
 const perQuery=run.per_query.map(q=>{
   const label=labels.find(x=>x.question_id===q.question_id), prior=old.per_query.find(x=>x.question_id===q.question_id);
   if(!label||!prior||seen.has(q.question_id)||label.query!==q.query||prior.query!==q.query||JSON.stringify([...q.relevant_chunk_ids].sort())!==JSON.stringify([...label.relevant_chunk_ids].sort()))throw Error(`${name}: query drift`);
   seen.add(q.question_id);
   const ranked=q.ranked_chunk_ids;
   if(ranked.length!==10||new Set(ranked).size!==10||ranked.some(id=>!byId.has(id)||byId.get(id).validity_status==='Hết hiệu lực'))throw Error(`${name}: invalid Top-10`);
   const relevant=new Set(label.relevant_chunk_ids);
   const rank=ranked.findIndex(id=>relevant.has(id));
   const oldRank=prior.ranked_chunk_ids.findIndex(id=>relevant.has(id));
   const recall=new Set(ranked.slice(0,5).filter(id=>relevant.has(id))).size/relevant.size;
   const mrr=rank<0?0:1/(rank+1);
   if(Math.abs(recall-q.recall_at_5)>1e-10||Math.abs(mrr-q.mrr_at_10)>1e-10)throw Error(`${name}: per-query metric mismatch`);
   return {question_id:q.question_id,first_relevant_rank:rank<0?null:rank+1,baseline_first_relevant_rank:oldRank<0?null:oldRank+1,recall_at_5:recall,mrr_at_10:mrr,top_1:ranked[0]};
 });
 if(seen.size!==labels.length)throw Error(`${name}: missing queries`);
 const recall=perQuery.reduce((s,q)=>s+q.recall_at_5,0)/perQuery.length;
 const mrr=perQuery.reduce((s,q)=>s+q.mrr_at_10,0)/perQuery.length;
 if(Math.abs(recall-run.ground_truth_metrics.recall_at_5)>1e-10||Math.abs(mrr-run.ground_truth_metrics.mrr_at_10)>1e-10)throw Error(`${name}: macro metric mismatch`);
 return {name,model:run.model,model_main_revision:mainRevision,
   main_revision_source:status.models[slug].cached_main_revision?'run_start_cache_ref':snapshots.length===1?'single_snapshot_observed_at_run_start':'archived_weight_equivalence_and_main_ref_evidence',
   observed_cache_snapshots:status.models[slug].observed_cache_snapshots,
   recall_at_5:recall,mrr_at_10:mrr,baseline_recall_at_5:old.ground_truth_metrics.recall_at_5,baseline_mrr_at_10:old.ground_truth_metrics.mrr_at_10,
   labelled_top_1:perQuery.filter(q=>q.first_relevant_rank===1).length,
   mean_encode_plus_search_ms:run.ground_truth_metrics.mean_query_embedding_plus_search_seconds*1000,per_query:perQuery};
});
const report={dataset_sha256:hash(dataPath),labels_sha256:hash(labelPath),query_count:labels.length,
 corpus_count:corpus.length,eligible_count:corpus.filter(c=>c.validity_status!=='Hết hiệu lực').length,
 query_and_label_semantics_unchanged:true,human_review_complete:false,test_evaluated:false,models:rows,
 limitations:['Ten supporting-clause Dev labels are incomplete and close to source wording.','Only the identified ND01/ND04 article-tail boundaries were repaired.','Partial/unknown validity remains eligible under the existing filter.','Single CPU timings exclude preprocessing; no production winner or Test claim.']};
fs.writeFileSync(path.join(root,folder+'comparison.json'),JSON.stringify(report,null,2)+'\n');
const table=rows.map(r=>`| ${r.name} | ${r.baseline_recall_at_5.toFixed(2)} → ${r.recall_at_5.toFixed(2)} | ${r.baseline_mrr_at_10.toFixed(2)} → ${r.mrr_at_10.toFixed(2)} | ${r.labelled_top_1}/10 |`).join('\n');
const details=labels.map(q=>`| ${q.question_id} | ${rows.map(r=>r.per_query.find(p=>p.question_id===q.question_id).first_relevant_rank||'>10').join(' | ')} |`).join('\n');
const text=`# Structure-v2 Dev rerun\n\nAll three models were run sequentially on CPU with the same 10 Dev query/label semantics as the frozen baseline. Only the corpus version changed: 1,079 → ${report.corpus_count} token-safe article chunks, with ${report.eligible_count} eligible under the unchanged expiry filter. Every model passed its tokenizer audit. Human review remains pending; no Test queries were run.\n\n| Model | Recall@5: baseline → v2 | MRR@10: baseline → v2 | Labelled evidence Top-1 in v2 |\n|---|---:|---:|---:|\n${table}\n\n| Question | BKAI relevant rank | AITeamVN relevant rank | BGE-M3 relevant rank |\n|---|---:|---:|---:|\n${details}\n\nThe baseline files were preserved. Fixture/label hashes, query semantics, corpus/point counts, token audits, unique existing Top-10 IDs, expiry exclusion and per-query/macro metrics were independently checked. Raw result JSONs, cache snapshot observations and recomputed comparison are in \`data/structure_v2/benchmark\`.\n\nDataset SHA-256: \`${report.dataset_sha256}\`.\nLabels SHA-256: \`${report.labels_sha256}\`.\n\nThese are provisional diagnostics on ten source-like questions, not a legal-accuracy certification. Candidate alternative evidence (e.g. Article 69 for the Article 70 question) remains outside the frozen judgments; labels were not edited to improve scores. Partial/unknown validity is still eligible and other parser issues remain. Timings are single CPU samples excluding preprocessing.\n\nNext: review corpus-wide relevance and article-level validity, then implement a BM25 baseline and hybrid/RRF comparison on this frozen Dev version. Keep Test reserved until the configuration and labels are fixed.\n`;
fs.writeFileSync(path.join(root,'docs/structure_v2_dev.md'),text);
fs.appendFileSync(path.join(root,'docs/structure_v2_dev.md'),
 '\nBGE cache provenance was checked separately: its main revision matches the baseline; the additional safetensors-only snapshot has identical values and dtypes for all 391 tensors compared with the cached base `.bin` weights. Exact file hashes and the read-only verification method are in `data/structure_v2/benchmark/bge_weight_equivalence.json`. The result collector uses archived evidence and does not require a local model cache to rebuild this report.\n');
console.log(JSON.stringify(rows.map(({per_query,...rest})=>rest),null,2));
