// Complete article-level context mappings without claiming human/legal review.
// Usage: node scripts/complete_gold_context_ids.cjs [--write]
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const read = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const gtPath = 'data/benchmark/ground_truth.json';
const original = read(gtPath);
const gt = structuredClone(original);
const prod = read('data/reference/production_chunk_index.json');
const corpus = fs.readFileSync(path.join(root, 'data/chunking_output/chunks.jsonl'), 'utf8')
  .split(/\r?\n/).filter(Boolean).map(s => JSON.parse(s));
const corpusById = new Map(corpus.map(c => [c.chunk_id, c]));
const prodById = new Map(prod.map(c => [c.chunk_id, c]));
const articles = new Map(read('data/reference/article_index.json').map(a => [a.article_id, a]));
const tests = read('data/benchmark/queries_test.json');
const dev = read('data/benchmark/queries_dev.json');
const testIds = new Set(tests.map(q => q.id));
const changed = [];
const pending = [];
for (const g of gt) {
  if (g.gold_context_ids.length) continue;
  assert(!testIds.has(g.id), `${g.id}: cannot modify frozen Test`);
  if (g.id === 'HN_053') g.gold_article_ids = ['L01_D132'];
  if (!g.gold_article_ids.length) {
    assert(g.citations.every(c => c.article === 'Trạng thái hiệu lực'));
    pending.push({id: g.id, reason: 'DOCUMENT_VERSION_METADATA_REQUIRES_REVIEW',
      citations: g.citations, answer: g.answer});
    continue;
  }
  // These queries cite complete articles, rather than a selected clause. Include
  // every child chunk, including continuations that the ranked proposals omit.
  const selected = g.gold_article_ids.flatMap(aid => {
    const a = articles.get(aid);
    assert(a, `${g.id}: unknown article ${aid}`);
    assert(g.citations.some(c => c.document_id === a.document_number && c.article === a.article_number),
      `${g.id}: citation is not the complete article ${aid}`);
    const chunks = prod.filter(c => c.article_id === aid);
    assert(chunks.length, `${g.id}: article has no production chunks ${aid}`);
    for (const c of chunks) {
      const actual = corpusById.get(c.chunk_id);
      assert(actual, `${g.id}: missing corpus ID ${c.chunk_id}`);
      assert(c.chunk_text.trim(), `${g.id}: empty text ${c.chunk_id}`);
      assert.equal((actual.text ?? actual.chunk_text).replace(/\s+/g, ' ').trim(),
        c.chunk_text.replace(/\s+/g, ' ').trim(), `${g.id}: corpus/index text mismatch`);
      assert.equal(c.document_number, a.document_number);
    }
    return chunks;
  });
  g.gold_context_ids = [...new Set(selected.map(c => c.chunk_id))];
  g.gold_clause_ids = [...new Set(selected.map(c => c.clause_id).filter(Boolean))];
  g.candidate_context_ids = g.candidate_context_ids.filter(cid => !g.gold_context_ids.includes(cid));
  g.mapping_status = 'production_verified';
  g.context_id_provenance = 'production_index';
  g.gold_context_ids_confirmed = true;
  g.evidence_level = 'chunk_text_matched_unverified';
  // Confirmation above concerns ID/article/corpus mapping only. Keep draft
  // answers, legal review status, reviewer and date exactly as received.
  changed.push({id: g.id, gold_article_ids: g.gold_article_ids,
    gold_context_ids: g.gold_context_ids, review_status: g.review_status,
    basis: 'Complete cited articles; every child chunk matched to production corpus. Legal applicability and answer remain unreviewed.'});
}
for (const g of gt) {
  const before = original.find(x => x.id === g.id);
  if (before.gold_context_ids.length || testIds.has(g.id)) assert.deepEqual(g, before);
  for (const field of ['answer', 'explanation', 'citations', 'review_status', 'answer_kind', 'verified_by', 'verified_at', 'temporal_note'])
    assert.deepEqual(g[field], before[field], `${g.id}: changed protected field ${field}`);
  assert.equal(new Set(g.gold_context_ids).size, g.gold_context_ids.length);
  for (const cid of g.gold_context_ids) {
    if (cid.startsWith('FAKE_')) {
      assert.equal(g.gold_context_ids_confirmed, false);
      assert.equal(g.review_status, 'draft');
      continue; // Explicit synthetic fixture, never a verified production ID.
    }
    const c = prodById.get(cid);
    assert(c && corpusById.has(cid), `${g.id}: invalid gold ID ${cid}`);
    assert(g.gold_article_ids.includes(c.article_id));
    assert(g.citations.some(s => s.document_id === c.document_number));
    assert(!g.candidate_context_ids.includes(cid));
  }
}
const canonical = v => Array.isArray(v) ? v.map(canonical) : v && typeof v === 'object'
  ? Object.fromEntries(Object.keys(v).sort().map(k => [k, canonical(v[k])])) : v;
const payload = {questions: tests, test_ground_truth: tests.map(q => gt.find(g => g.id === q.id))};
const digest = crypto.createHash('sha256').update(JSON.stringify(canonical(payload)) + '\n').digest('hex');
assert.equal(digest, read('docs/test_gold_freeze.json').sha256, 'Frozen Test gold changed');
const counts = rows => ({questions: rows.length, with_gold: rows.filter(g => g.gold_context_ids.length).length,
  missing_gold: rows.filter(g => !g.gold_context_ids.length).length,
  gold_id_references: rows.reduce((n, g) => n + g.gold_context_ids.length, 0)});
const report = {base: 'origin/testing edee794', scope: 'Context mapping only; no human/legal review asserted',
  added_questions: changed.length, total: counts(gt),
  dev: counts(gt.filter(g => dev.some(q => q.id === g.id))),
  test: counts(gt.filter(g => testIds.has(g.id))),
  unique_gold_ids: new Set(gt.flatMap(g => g.gold_context_ids)).size,
  test_gold_freeze_verified: true, changed, pending};
if (process.argv.includes('--write')) {
  fs.writeFileSync(path.join(root, gtPath), JSON.stringify(gt, null, 2) + '\n');
  fs.writeFileSync(path.join(root, 'data/benchmark/gold_context_completion_audit.json'), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify({added: changed.length, ...report.total, dev: report.dev, test: report.test,
  synthetic_questions: gt.filter(g => g.gold_context_ids.some(cid => cid.startsWith('FAKE_'))).length,
  unique_gold_ids: report.unique_gold_ids, pending: pending.map(g => g.id), test_gold_freeze_verified: true}, null, 2));
