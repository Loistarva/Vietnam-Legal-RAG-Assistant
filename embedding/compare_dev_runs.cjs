/** Compare dense runs only when fixture, judgments and token audits match. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname,'..');
const read = p => JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
const fixture = 'embedding/data/priority_bkai_chunks.json';
const labels = 'embedding/data/priority_bkai_dev.support_reviewed.json';
const judgments = read(labels), corpus = read(fixture).chunks;
const corpusById = new Map(corpus.map(c=>[c.id,c]));
const inputs = [
 ['BKAI','priority_bkai_dev_support_reviewed.json','priority_bkai_token_safe_audit.json','84f9d9ada0d1a3c37557398b9ae9fcedcdf40be0'],
 ['AITeamVN','priority_aiteamvn_dev_support_reviewed.json','priority_aiteamvn_token_audit.json','dea33aa1ab339f38d66ae0a40e6c40e0a9249568'],
 ['BGE-M3','priority_bge_m3_dev_support_reviewed.json','priority_bge_m3_token_audit.json','5617a9f61b028005a4858fdac845db406aefb181'],
];
const rows = inputs.map(([name,file,auditFile,observedRevision]) => {
 const run = read('embedding/results/'+file), audit=read('embedding/results/'+auditFile);
 if(run.chunk_file_sha256!==hash(fixture) || run.ground_truth_sha256!==hash(labels) || audit.dataset_sha256!==hash(fixture)) throw new Error(`${name}: incompatible input hashes`);
 if(run.chunk_count!==corpus.length || audit.chunk_count!==corpus.length || audit.oversized_count!==0) throw new Error(`${name}: incomplete corpus/token validation`);
 if(run.per_query.length!==judgments.length) throw new Error(`${name}: incomplete query evaluation`);
 const seen = new Set();
 const scores=run.per_query.map(q=>{
   const original=judgments.find(x=>x.question_id===q.question_id);
   if(!original || seen.has(q.question_id) || original.query!==q.query || JSON.stringify([...original.relevant_chunk_ids].sort())!==JSON.stringify([...q.relevant_chunk_ids].sort())) throw new Error(`${name}: query/label mismatch`);
   if(q.ranked_chunk_ids.length!==10 || new Set(q.ranked_chunk_ids).size!==10 || q.ranked_chunk_ids.some(id=>!corpusById.has(id) || corpusById.get(id).validity_status==='Hết hiệu lực')) throw new Error(`${name}: invalid or expired Top-10 evidence`);
   seen.add(q.question_id);
   const relevant=new Set(q.relevant_chunk_ids);
   const recall=new Set(q.ranked_chunk_ids.slice(0,5).filter(id=>relevant.has(id))).size/relevant.size;
   const rank=q.ranked_chunk_ids.slice(0,10).findIndex(id=>relevant.has(id));
   return {question_id:q.question_id, recall_at_5:recall, mrr_at_10:rank<0?0:1/(rank+1), first_relevant_rank:rank<0?null:rank+1, top_1:q.ranked_chunk_ids[0]};
 });
 const recall=scores.reduce((s,q)=>s+q.recall_at_5,0)/scores.length;
 const mrr=scores.reduce((s,q)=>s+q.mrr_at_10,0)/scores.length;
 if(Math.abs(recall-run.ground_truth_metrics.recall_at_5)>1e-10 || Math.abs(mrr-run.ground_truth_metrics.mrr_at_10)>1e-10) throw new Error(`${name}: aggregate metric mismatch`);
 return {name, model:run.model, model_revision:run.model_revision || observedRevision,
   model_revision_source:run.model_revision ? 'model_config' : 'snapshot_directory_observed_during_run',
   recall_at_5:recall, mrr_at_10:mrr, labelled_top_1:scores.filter(q=>q.first_relevant_rank===1).length,
   query_encode_plus_search_ms:run.ground_truth_metrics.mean_query_embedding_plus_search_seconds*1000,
   document_encode_seconds:run.embedding_seconds, per_query:scores, result_file:file};
});
const report={scope:'provisional_single_run_dense_Dev_comparison', dataset_sha256:hash(fixture), labels_sha256:hash(labels),
 chunk_count:corpus.length, eligible_chunk_count:corpus.filter(c=>c.validity_status!=='Hết hiệu lực').length,
 query_count:judgments.length, human_review_complete:false, test_split_evaluated:false,
 filter:'must_not metadata.validity_status == Hết hiệu lực; partial/unknown retained', models:rows,
 limitations:['Supporting-clause labels are incomplete; alternate evidence is tracked separately.','Only ten source-like Dev queries; no Test conclusions or model-winner claim.','Single CPU runs; timings exclude preprocessing and are not a controlled latency benchmark.','Existing parser structure and article-level validity issues remain.']};
fs.writeFileSync(path.join(root,'embedding/results/priority_dense_dev_comparison.json'),JSON.stringify(report,null,2)+'\n');
const table=rows.map(r=>`| ${r.name} | ${r.recall_at_5.toFixed(3)} | ${r.mrr_at_10.toFixed(3)} | ${r.labelled_top_1}/10 | ${r.query_encode_plus_search_ms.toFixed(2)} |`).join('\n');
const details=judgments.map(q=>`| ${q.question_id} | ${rows.map(r=>r.per_query.find(x=>x.question_id===q.question_id).first_relevant_rank || '>10').join(' | ')} |`).join('\n');
const text=`# Provisional dense retrieval comparison on Dev\n\nAll three runs use the same frozen 1,079-chunk corpus and the same 10 assistant-reviewed Dev questions. The current filter leaves ${report.eligible_chunk_count} eligible chunks. Human review is pending; the 40 Test questions were not evaluated. Every model passed a full-corpus tokenizer audit.\n\n| Model | Recall@5 | MRR@10 | Labelled evidence Top-1 | Mean encode + search (ms) |\n|---|---:|---:|---:|---:|\n${table}\n\nTimes exclude model loading, corpus ingestion and preprocessing outside the encode timer. These single CPU runs are exploratory, not a controlled performance ranking.\n\n| Question | BKAI relevant rank | AITeamVN relevant rank | BGE-M3 relevant rank |\n|---|---:|---:|---:|\n${details}\n\nDataset SHA-256: \`${report.dataset_sha256}\`.\nLabels SHA-256: \`${report.labels_sha256}\`.\nModel revisions, source results and recomputed per-query scores are in \`embedding/results/priority_dense_dev_comparison.json\`.\n\nThe baseline judgments remain frozen. Article 69(1), returned for priority_036, is a candidate alternative supporting clause, so missing the labelled Article 70(1) does not establish that no useful evidence was retrieved. See \`embedding/data/priority_dev.candidate_relevance_review.json\`; candidate labels were not silently applied to any model's score.\n\nDo not pick a production winner from ten source-like questions. Next, review corpus-wide relevance labels and parser structure/validity, freeze a new Dev judgment version if needed, then implement and compare BM25/hybrid retrieval. Keep Test reserved until configuration is fixed and labels are reviewed.\n`;
fs.writeFileSync(path.join(root,'docs/dense_dev_comparison.md'),text);
fs.appendFileSync(path.join(root,'docs/dense_dev_comparison.md'),
 '\n## Observed parser issue to address next\n\nThe BGE-M3 default smoke query returns `ND01_art_67_clause_1_chunk_1` and `ND01_art_67_clause_4_chunk_1` in its Top-5. Those corpus records contain appendix material classified as Article 67 clauses; the appendix describes customs to eliminate or prohibit, so its list items must not be read as standalone current-law prohibitions. This is an observed context-boundary problem, distinct from the ten-query retrieval metric. Separate article text, appendix headings/items and footer material in ND01 and ND04 before building an answer generator or declaring production readiness. Preserve this frozen baseline when regenerating corrected data.\n');
console.log(JSON.stringify(rows.map(({per_query,...rest})=>rest),null,2));
