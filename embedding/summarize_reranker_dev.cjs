/** Check every reranker score/order against the frozen RRF candidate pool. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const {isDeepStrictEqual}=require('node:util');
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
const base='data/structure_v2/';
const r=read(base+'reranker/dev_results.json'),source=read(base+'hybrid/dev_results.json');
const data=base+'embedding/priority_bkai_chunks.json',labelsFile=base+'embedding/priority_bkai_dev.draft.json';
const corpus=new Map(read(data).chunks.map(c=>[c.id,c])), labels=read(labelsFile);
if(r.dataset_sha256!==hash(data)||r.labels_sha256!==hash(labelsFile)||r.candidate_source_sha256!==hash(base+'hybrid/dev_results.json'))throw Error('Input hash mismatch');
if(r.test_evaluated||r.per_query.length!==10||r.truncation!==false||r.candidate_depth!==50||r.pair_token_limit!==512)throw Error('Unexpected evaluation scope');
const seen=new Set();let covered=0,maxPair=0;
for(const q of r.per_query){
 const label=labels.find(x=>x.question_id===q.question_id),old=source.per_query.find(x=>x.question_id===q.question_id);
 if(!label||!old||seen.has(q.question_id)||q.query!==label.query||JSON.stringify(q.relevant_chunk_ids)!==JSON.stringify(label.relevant_chunk_ids))throw Error('Judgment mismatch');
 seen.add(q.question_id);
 const scores=new Map();
 for(const method of ['bm25','dense'])old.candidate_rankings[method].forEach((hit,i)=>{
   const item=scores.get(hit.chunk_id)||{id:hit.chunk_id,score:0,ranks:{}};
   item.score+=1/(60+i+1);item.ranks[method]=i+1;scores.set(hit.chunk_id,item);
 });
 const pool=[...scores.values()].sort((a,b)=>b.score-a.score||Math.min(...Object.values(a.ranks))-Math.min(...Object.values(b.ranks))||(a.id<b.id?-1:a.id>b.id?1:0)).slice(0,50);
 const originals=new Map(pool.map((h,i)=>[h.id,{...h,rank:i+1}]));
 const hits=q.scored_candidates;
 if(hits.length!==pool.length||q.candidate_count!==pool.length||new Set(hits.map(h=>h.chunk_id)).size!==hits.length)throw Error('Candidate coverage mismatch');
 for(const h of hits){
   const original=originals.get(h.chunk_id),c=corpus.get(h.chunk_id);
   if(!original||!c||c.validity_status==='Hết hiệu lực'||h.text!==c.text.trim()||!Number.isFinite(h.reranker_score)||h.score!==h.reranker_score||h.score_kind!=='reranker_logit'||h.pre_rerank_rank!==original.rank||Math.abs(h.rrf_score-original.score)>1e-12)throw Error('Candidate evidence/score drift');
   const reserved=new Set(['id','chunk_id','text','content','metadata','embed_text','seg_text']);
   const metadata=c.metadata || Object.fromEntries(Object.entries(c).filter(([key])=>!reserved.has(key)));
   if(!isDeepStrictEqual(h.metadata,metadata)||!isDeepStrictEqual(h.component_ranks,original.ranks))throw Error('Candidate metadata/component-rank drift');
 }
 const sorted=[...hits].sort((a,b)=>b.reranker_score-a.reranker_score||a.pre_rerank_rank-b.pre_rerank_rank||(a.chunk_id<b.chunk_id?-1:1));
 if(JSON.stringify(sorted.map(h=>h.chunk_id))!==JSON.stringify(hits.map(h=>h.chunk_id)))throw Error('Wrong reranker ordering');
 const relevant=new Set(label.relevant_chunk_ids),ids=hits.slice(0,10).map(h=>h.chunk_id);
 const rank=ids.findIndex(id=>relevant.has(id));
 const recall=new Set(ids.slice(0,5).filter(id=>relevant.has(id))).size/relevant.size;
 if(Math.abs(recall-q.methods.reranked.recall_at_5)>1e-12||Math.abs((rank<0?0:1/(rank+1))-q.methods.reranked.mrr_at_10)>1e-12||JSON.stringify(ids)!==JSON.stringify(q.methods.reranked.ranked_chunk_ids))throw Error('Metric mismatch');
 if(q.max_pair_tokens>512)throw Error('Pair overflow');
 maxPair=Math.max(maxPair,q.max_pair_tokens);
 if([...relevant].every(id=>originals.has(id)))covered++;
 for(const method of ['dense','rrf']){
   const expected=old.methods[method==='rrf'?'hybrid':'dense'];
   if(JSON.stringify(expected)!==JSON.stringify(q.methods[method]))throw Error('Baseline metrics changed');
 }
}
for(const method of ['dense','rrf','reranked'])for(const metric of ['recall_at_5','mrr_at_10']){
 const macro=r.per_query.reduce((s,q)=>s+q.methods[method][metric],0)/10;
 if(Math.abs(macro-r.metrics[method][metric])>1e-12)throw Error('Macro metric mismatch');
}
const validation={hashes_match:true,candidate_sets_and_rrf_scores_match:true,ordering_and_metrics_recomputed:true,
 query_count:seen.size,queries_with_all_labelled_evidence_in_pool:covered,max_pair_tokens:maxPair,
 no_pair_truncation:true,test_evaluated:false};
fs.writeFileSync(path.join(root,base+'reranker/validation.json'),JSON.stringify(validation,null,2)+'\n');
const table=Object.entries(r.metrics).map(([m,s])=>`| ${m} | ${s.recall_at_5.toFixed(3)} | ${s.mrr_at_10.toFixed(3)} |`).join('\n');
const ranks=r.per_query.map(q=>`| ${q.question_id} | ${q.methods.dense.first_relevant_rank||'>10'} | ${q.methods.rrf.first_relevant_rank||'>10'} | ${q.methods.reranked.first_relevant_rank||'>10'} |`).join('\n');
const text=`# Reranker Dev evaluation\n\nThe [publisher's multilingual BGE reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3) scores query/passage pairs. This run pins model and tokenizer revision \`${r.revision}\`, uses CPU FP32 with batch size 16, and reranks the frozen RRF Top-50 candidates into Top-10. No retrieval candidates, labels or Test queries were regenerated.\n\n| Method | Recall@5 | MRR@10 |\n|---|---:|---:|\n${table}\n\n| Question | Dense rank | RRF rank | Reranked rank |\n|---|---:|---:|---:|\n${ranks}\n\n## Validation and cost\n\nAll ${covered}/10 questions have every labelled supporting clause in the candidate pool. Maximum pair length is ${maxPair} tokens against a 512-token budget including special tokens; no truncation is allowed. The checker validates candidate sets, source text, eligibility, preserved RRF scores, new ordering, frozen baseline values and independently recomputed metrics. Seven new regression tests cover score validation, deterministic ties, evidence preservation, empty pools, token overflow and pipeline integration beyond Top-10.\n\nMean rerank wall time is **${r.mean_rerank_seconds.toFixed(3)} seconds/query** on this CPU, including pair tokenization, token-budget checking, model scoring and sorting. It excludes retrieval because candidates were replayed. This is an offline single-run cost measurement, not an API/streaming TTFB measurement. Raw logits rank evidence and are not calibrated legal confidence.\n\n## Scope\n\nThe reusable reranker is integrated as an optional stage in \`HybridRetriever\`. When disabled, the earlier hybrid API/ordering remains available. When enabled, output includes the original hybrid Top-10 plus a separate reranked Top-10, provenance, original fusion rank/score and timing.\n\nThis small Dev set uses incomplete supporting-clause judgments and close-to-source wording. Human review is pending; no parameters or labels were adjusted after scoring. A different valid supporting clause may be unlabelled. Scores here do not choose a production winner or establish legal accuracy. Current-law-only filtering, metadata query extraction, parent context, answer generation, API/UI and full Test validation remain pending.\n\nRun with the embedding environment and internet on first model load:\n\n\`\`\`powershell\n.\\.venv-embedding\\Scripts\\python.exe -u embedding/evaluate_reranker_dev.py\nnode embedding/summarize_reranker_dev.cjs\n.\\.venv-embedding\\Scripts\\python.exe -m unittest discover -s test -p test_reranking.py\n\`\`\`\n\nResults and validation: \`data/structure_v2/reranker/\`. Candidate-source SHA-256: \`${r.candidate_source_sha256}\`. For the completed run, the resolved revision is stored in result JSON; rerunning the evaluator resolves the current model revision again, so check that field before comparing runs.\n`;
fs.writeFileSync(path.join(root,'docs/reranker_dev.md'),text);
fs.appendFileSync(path.join(root,'docs/reranker_dev.md'),
 `\nFor an exact cached rerun, pass \`--revision ${r.revision}\` to the evaluator and set \`HF_HUB_OFFLINE=1\`. This bypasses resolving the current remote revision and reuses the pinned model/tokenizer.\n`);
console.log(JSON.stringify({metrics:r.metrics,validation,mean_rerank_seconds:r.mean_rerank_seconds},null,2));
