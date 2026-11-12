/** Validate result/fixture/label hashes and produce a bounded Dev report. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const os = require('node:os');
const root = path.resolve(__dirname,'..');
const read = p => JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
const resultFile = 'embedding/results/priority_bkai_dev_support_reviewed.json';
const dataFile = 'embedding/data/priority_bkai_chunks.json';
const labelFile = 'embedding/data/priority_bkai_dev.support_reviewed.json';
const result = read(resultFile), fixture = read(dataFile), labels = read(labelFile);
if(result.chunk_file_sha256 !== hash(dataFile) || result.ground_truth_sha256 !== hash(labelFile)) throw new Error('Result hashes do not match current fixture/labels');
if(result.per_query.length !== labels.length || result.ground_truth_metrics.query_count !== labels.length) throw new Error('Incomplete query results');
const rankRows = result.per_query.map(q => ({question_id:q.question_id, query:q.query,
 relevant_rank:q.ranked_chunk_ids.findIndex(id=>q.relevant_chunk_ids.includes(id))+1,
 recall_at_5:q.recall_at_5, mrr_at_10:q.mrr_at_10, top_1:q.ranked_chunk_ids[0]}));
const metrics = result.ground_truth_metrics;
const context = {model:result.model,
 model_revision:'84f9d9ada0d1a3c37557398b9ae9fcedcdf40be0',
 fixture_sha256:hash(dataFile), labels_sha256:hash(labelFile),
 dependency_snapshot_sha256:hash('embedding/requirements-priority-lock.txt'),
 system:{platform:os.platform(),architecture:os.arch(),cpu:os.cpus()[0]?.model},
 retrieval_filter:'must_not metadata.validity_status == Hết hiệu lực; partial/unknown statuses remain eligible',
 ingested_chunks:fixture.chunks.length,
 eligible_chunks:fixture.chunks.filter(c=>c.validity_status!=='Hết hiệu lực').length,
 human_review_complete:false, exhaustive_relevance_labels:false,
 ground_truth_metrics:metrics, per_query:rankRows};
fs.writeFileSync(path.join(root,'embedding/results/priority_bkai_dev_context.json'),JSON.stringify(context,null,2)+'\n');
const table = rankRows.map(q=>`| ${q.question_id} | ${q.relevant_rank || '>10'} | ${q.recall_at_5.toFixed(3)} | ${q.mrr_at_10.toFixed(3)} | \`${q.top_1}\` |`).join('\n');
const md = `# BKAI development baseline\n\nThis provisional run uses 10 assistant-reviewed supporting-clause questions. Three questions were clarified before retrieval (priority_006, priority_026, priority_041). Human review remains pending; the 40 Test questions were not run or changed.\n\n- Dataset: ${context.ingested_chunks} chunks; ${context.eligible_chunks} eligible under the existing expiry filter.\n- Recall@5: **${metrics.recall_at_5.toFixed(4)}**.\n- MRR@10: **${metrics.mrr_at_10.toFixed(4)}**.\n- Mean query embedding + Qdrant search: **${(metrics.mean_query_embedding_plus_search_seconds*1000).toFixed(2)} ms**, excluding model loading, document indexing and preprocessing outside the encode timer.\n- Labels hash: \`${context.labels_sha256}\`.\n- Dataset hash: \`${context.fixture_sha256}\`.\n- Model revision: \`${context.model_revision}\`.\n\n| Question | First labelled relevant rank | Recall@5 | MRR@10 | Top-1 |\n|---|---:|---:|---:|---|\n${table}\n\nThese are development diagnostics against known supporting clauses, not comprehensive legal-relevance judgments. Other relevant chunks may be unlabelled. The small set is close to source wording. Partial/unknown legal statuses remain eligible and parser structure issues remain; these metrics do not establish production readiness or select a model winner.\n\nNext: inspect missed queries and alternative evidence, review human labels and parser structure, then compare other models on exactly the same corpus and Dev labels. Keep Test reserved until configuration is frozen.\n`;
fs.writeFileSync(path.join(root,'docs/bkai_dev_baseline.md'),md);
const observations = `\n## Post-run evidence review (labels and scores unchanged)\n\n- **priority_036:** labelled Article 70(1) is absent from Top-10, so its stored Recall/MRR are zero. Top-1 is Article 69(1), whose corpus text directly states that parents should love their children and respect their opinions. This is a candidate additional supporting label requiring review; the observed miss is not sufficient to conclude that retrieval returned no useful evidence. No post-run relabelling or optimistic metric was applied.\n- **priority_021:** labelled Article 35(1) is ranked second. Top-1 Article 35(2) discusses written agreement for particular transactions. Top-3 ND01 Article 13(1) also states the agreement rule, but ND01 is partially expired and needs article-level validity verification before its evidence can be approved for current-law answers.\n\nReview these candidate labels in a separately versioned judgment set before comparing models. Preserve this run and its original labels for an honest baseline.\n`;
fs.appendFileSync(path.join(root,'docs/bkai_dev_baseline.md'),observations);
console.log(JSON.stringify({metrics,per_query:rankRows},null,2));
