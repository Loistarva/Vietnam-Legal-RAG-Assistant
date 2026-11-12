/** Independently validate candidate rankings, RRF arithmetic and Dev metrics. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
const r=read('data/structure_v2/hybrid/dev_results.json');
const data='data/structure_v2/embedding/priority_bkai_chunks.json';
const labelFile='data/structure_v2/embedding/priority_bkai_dev.draft.json';
const corpus=read(data).chunks, labels=read(labelFile), baseline=read('data/structure_v2/benchmark/bge_m3_dev.json');
const eligible=new Set(corpus.filter(c=>c.validity_status!=='Hết hiệu lực').map(c=>c.id));
if(r.dataset_sha256!==hash(data)||r.labels_sha256!==hash(labelFile)||r.verified_index_count!==corpus.length||r.eligible_count!==eligible.size)throw Error('Input/index mismatch');
if(r.per_query.length!==10||labels.length!==10||r.test_evaluated)throw Error('Unexpected evaluation scope');
const seen=new Set();
for(const q of r.per_query){
 const label=labels.find(l=>l.question_id===q.question_id);
 if(!label||seen.has(q.question_id)||label.query!==q.query||JSON.stringify([...label.relevant_chunk_ids].sort())!==JSON.stringify([...q.relevant_chunk_ids].sort()))throw Error('Judgment drift');
 seen.add(q.question_id);
 for(const method of ['bm25','dense']){
   const list=q.candidate_rankings[method];
   if(list.length>r.parameters.candidate_k_per_branch||new Set(list.map(h=>h.chunk_id)).size!==list.length||list.some(h=>!eligible.has(h.chunk_id)||!Number.isFinite(h.score)))throw Error('Invalid candidates');
 }
 const fusion=new Map();
 for(const method of ['bm25','dense'])q.candidate_rankings[method].forEach((hit,index)=>{
   const item=fusion.get(hit.chunk_id)||{id:hit.chunk_id,score:0,ranks:{}};
   item.score+=1/(r.parameters.rrf_k+index+1);item.ranks[method]=index+1;fusion.set(hit.chunk_id,item);
 });
 const expected=[...fusion.values()].sort((a,b)=>b.score-a.score||Math.min(...Object.values(a.ranks))-Math.min(...Object.values(b.ranks))||(a.id<b.id?-1:a.id>b.id?1:0)).slice(0,10);
 if(expected.length!==q.hybrid_top_10.length)throw Error('Wrong fusion depth');
 expected.forEach((h,i)=>{const actual=q.hybrid_top_10[i];if(h.id!==actual.chunk_id||Math.abs(h.score-actual.score)>1e-12||JSON.stringify(h.ranks)!==JSON.stringify(actual.component_ranks))throw Error('RRF mismatch');});
 for(const method of ['bm25','dense','hybrid']){
   const ids=(method==='hybrid'?q.hybrid_top_10:q.candidate_rankings[method]).slice(0,10).map(h=>h.chunk_id);
   const relevant=new Set(label.relevant_chunk_ids),rank=ids.findIndex(id=>relevant.has(id));
   const recall=new Set(ids.slice(0,5).filter(id=>relevant.has(id))).size/relevant.size;
   if(Math.abs(recall-q.methods[method].recall_at_5)>1e-12||Math.abs((rank<0?0:1/(rank+1))-q.methods[method].mrr_at_10)>1e-12)throw Error('Per-query metric mismatch');
 }
}
for(const method of ['bm25','dense','hybrid'])for(const metric of ['recall_at_5','mrr_at_10']){
 const macro=r.per_query.reduce((s,q)=>s+q.methods[method][metric],0)/r.per_query.length;
 if(Math.abs(macro-r.metrics[method][metric])>1e-12)throw Error('Macro metric mismatch');
}
const sameDense=r.per_query.every(q=>JSON.stringify(q.methods.dense.ranked_chunk_ids)===JSON.stringify(baseline.per_query.find(p=>p.question_id===q.question_id).ranked_chunk_ids));
const validation={input_hashes_match:true,index_payload_count_verified:r.verified_index_count,eligible_count:eligible.size,
 rrf_independently_recomputed:true,metrics_independently_recomputed:true,
 live_dense_top10_matches_archived_baseline:sameDense,test_evaluated:false};
fs.writeFileSync(path.join(root,'data/structure_v2/hybrid/validation.json'),JSON.stringify(validation,null,2)+'\n');
const names={bm25:'BM25 (local)',dense:'BGE-M3 dense',hybrid:'BM25 + BGE-M3 RRF'};
const table=Object.entries(r.metrics).map(([key,m])=>`| ${names[key]} | ${m.recall_at_5.toFixed(3)} | ${m.mrr_at_10.toFixed(3)} | ${r.per_query.filter(q=>q.methods[key].first_relevant_rank===1).length}/10 |`).join('\n');
const ranks=r.per_query.map(q=>`| ${q.question_id} | ${q.methods.bm25.first_relevant_rank||'>10'} | ${q.methods.dense.first_relevant_rank||'>10'} | ${q.methods.hybrid.first_relevant_rank||'>10'} |`).join('\n');
const text=`# Local BM25 and hybrid/RRF Dev baseline\n\nThe same frozen structure-v2 corpus (1,024 indexed chunks, 630 eligible) and 10 supporting-clause Dev labels were used. No Test queries, new labels, parameter sweep or reranker were used. Human review remains pending.\n\n| Method | Recall@5 | MRR@10 | Labelled evidence Top-1 |\n|---|---:|---:|---:|\n${table}\n\n| Question | BM25 rank | Dense rank | RRF rank |\n|---|---:|---:|---:|\n${ranks}\n\n## Implementation and checks\n\nBM25 uses full contextual text, Vietnamese underthesea segmentation, NFC/lowercase Unicode terms, binary query TF, k1=1.2 and b=0.75. IDF and length statistics are computed only over eligible documents. No-overlap lexical queries return no sparse evidence. These are standard BM25 parameters/IDF as documented by [Apache Lucene](https://lucene.apache.org/core/9_12_1/core/org/apache/lucene/search/similarities/BM25Similarity.html); this Python baseline is not an exact Lucene index or an Elasticsearch deployment.\n\nThe sparse and dense branches run concurrently; each returns up to 50 candidates. RRF uses sum(1/(60+rank)) with one-based ranks, ignores duplicate IDs per branch and uses deterministic ties. Parameters were fixed before viewing results, following the [original RRF paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf). No reranker is present.\n\nThe existing Qdrant collection was reused read-only after checking every ID, text and metadata payload against the fixture. Corpus vectors were not re-encoded. Live dense Top-10 rankings match the archived v2 baseline: **${sameDense}**. A separate checker recomputed RRF and per-query/macro metrics, checked input hashes and rejected ineligible/unknown candidate IDs. Seven algorithm/concurrency/filter regression tests pass. Branch/end-to-end wall times include query preprocessing and are single CPU samples; they are not directly comparable to older encode-only timers.\n\n## Findings and remaining work\n\nRRF keeps all labelled evidence in Top-5 but moves priority_036 from dense rank 1 to fused rank 2, lowering labelled MRR from 1.00 to 0.95. BM25 ranks the same labelled clause third. No parameters or labels were changed to hide this result. The small source-like set has incomplete relevance judgments; it does not demonstrate that hybrid improves legal answer quality.\n\nThis implements an in-process BM25 baseline and parallel rank fusion, not full SRS FR2. Elasticsearch integration, metadata extraction/filtering by query, reranking and parent-context resolution remain pending. Validity filtering still matches the research baseline (fully expired excluded; partial/unknown retained), so it does not yet satisfy NFR1's current-law-only requirement. See [remaining_work.md](remaining_work.md) for the full project backlog.\n\nRun from the repository root with cached models and the v2 Qdrant index available:\n\n\`\`\`powershell\n.\\.venv-embedding\\Scripts\\python.exe embedding/evaluate_hybrid_dev.py\nnode embedding/summarize_hybrid_dev.cjs\n.\\.venv-embedding\\Scripts\\python.exe -m unittest discover -s test -p test_hybrid_retrieval.py\n\`\`\`\n\nResults: \`data/structure_v2/hybrid/dev_results.json\`. Dataset SHA-256: \`${r.dataset_sha256}\`; labels SHA-256: \`${r.labels_sha256}\`.\n`;
fs.writeFileSync(path.join(root,'docs/hybrid_dev.md'),text);
console.log(JSON.stringify({metrics:r.metrics,validation},null,2));
