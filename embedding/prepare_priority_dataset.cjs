/** Validate the current parser/chunker export and freeze a retrieval dataset.
 * Run from any directory: node embedding/prepare_priority_dataset.cjs
 * No PDF, parser JSON, or existing embedding results are overwritten.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const compact = value => String(value ?? '').replace(/\s+/gu, ' ').trim();
const read = file => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8').replace(/^\uFEFF/, ''));
const write = (file, value) => {
  fs.mkdirSync(path.dirname(path.join(root, file)), {recursive: true});
  fs.writeFileSync(path.join(root, file), JSON.stringify(value, null, 2) + '\n');
};

function validateDocument(doc, rows) {
  const errors = [];
  const ids = new Set();
  const check = (ok, message) => { if (!ok) errors.push(message); };
  for (const article of doc.articles) {
    check(article.article_id === `${doc.document_id}_art_${article.article_number}`, `Article ID: ${article.article_id}`);
    for (const clause of article.clauses) {
      check(clause.parent_article_id === article.article_id, `Clause parent: ${clause.clause_id}`);
      check(clause.clause_id === `${article.article_id}_clause_${clause.clause_number}`, `Clause ID: ${clause.clause_id}`);
      check(clause.chunks.length > 0, `Missing chunks: ${clause.clause_id}`);
      const bodies = [];
      for (const chunk of clause.chunks) {
        check(!ids.has(chunk.chunk_id), `Duplicate ID: ${chunk.chunk_id}`);
        ids.add(chunk.chunk_id);
        const row = rows.get(chunk.chunk_id);
        check(Boolean(row), `Missing JSONL record: ${chunk.chunk_id}`);
        check(chunk.parent_clause_id === clause.clause_id, `Chunk parent: ${chunk.chunk_id}`);
        check(chunk.char_count === chunk.chunk_text.length, `Character count: ${chunk.chunk_id}`);
        if (row) {
          check(row.chunk_text === chunk.chunk_text && row.clause_id === clause.clause_id && row.article_id === article.article_id && row.document_id === doc.document_id, `JSONL drift: ${chunk.chunk_id}`);
          check(fs.existsSync(path.join(root, row.source_file)), `Missing source: ${row.source_file}`);
        }
        const marker = chunk.clause_number_is_synthetic ? 'Nội dung điều: ' : `Khoản ${clause.clause_number}: `;
        const offset = chunk.chunk_text.lastIndexOf('\n' + marker);
        check(offset >= 0, `Missing clause body: ${chunk.chunk_id}`);
        bodies.push(chunk.chunk_text.slice(offset + 1 + marker.length));
      }
      check(compact(bodies.join(' ')) === compact(clause.clause_text), `Content loss: ${clause.clause_id}`);
    }
  }
  return errors;
}

function main() {
  const source = 'data/chunking_output/chunks.jsonl';
  const bytes = fs.readFileSync(path.join(root, source));
  const rows = bytes.toString('utf8').trim().split(/\r?\n/u).map(JSON.parse);
  const lookup = new Map(rows.map(row => [row.chunk_id, row]));
  const errors = [];
  if (lookup.size !== rows.length) errors.push('Duplicate JSONL IDs');
  const normalized = read('data/normalized_metadata.json').documents;
  const documents = [];
  const warnings = [];
  const chunks = [];
  const codes = [...new Set(rows.map(row => row.document_id))].sort();
  for (const code of codes) {
    const doc = read(`data/chunking_output/documents/${code}.json`);
    errors.push(...validateDocument(doc, lookup));
    const canonical = normalized.find(item => item.document_id === code);
    if (canonical && canonical.effective_date !== doc.metadata.effective_date) warnings.push({document_id: code, field: 'effective_date', parsed: doc.metadata.effective_date, normalized: canonical.effective_date, action: 'Verify against authoritative source; neither value auto-approved.'});
    if (!doc.metadata.validity_status || doc.metadata.validity_status === 'Không xác định') warnings.push({document_id: code, field: 'validity_status', action: 'Requires legal source verification before production retrieval.'});
    const verification = doc.source_verification;
    if (verification?.restriction) warnings.push({document_id: code, field: 'source_restriction', action: verification.restriction});
    if (verification?.expected_article_count && doc.articles.length !== verification.expected_article_count) warnings.push({document_id: code, field: 'source_completeness', expected: verification.expected_article_count, actual: doc.articles.length});
    const numbers = new Set(doc.articles.map(a => Number(a.article_number)));
    const missing = Array.from({length: Math.max(...numbers)}, (_, i) => i + 1).filter(i => !numbers.has(i));
    if (missing.length) warnings.push({document_id: code, field: 'article_sequence', missing});
    documents.push({document_id: code, articles: doc.articles.length, clauses: doc.articles.reduce((n,a) => n + a.clauses.length, 0), chunks: rows.filter(r => r.document_id === code).length});
    for (const row of rows.filter(r => r.document_id === code)) chunks.push({id: row.chunk_id, text: row.chunk_text, embed_text: row.chunk_text, ...Object.fromEntries(Object.entries(row).filter(([k]) => !['chunk_id','chunk_text','char_count'].includes(k))), ...doc.metadata, parent_id: row.clause_id, metadata_verification: verification ? 'official_source_corrections_applied_not_full_text_certification' : 'unverified', validity_checked_at: verification?.checked_at ?? null});
  }
  const represented = documents.reduce((n,d) => n + d.chunks, 0);
  if (represented !== rows.length) errors.push('Orphan JSONL records');
  const report = {source, source_sha256: hash(bytes), documents, chunk_count: chunks.length, errors, warnings, token_limit_check: 'Not run: requires each embedding model tokenizer; character limits do not prove token limits.', production_ready: false};
  write('data/chunking_output/validation_report.json', report);
  if (errors.length) throw new Error(JSON.stringify(errors));
  write('embedding/data/priority_chunks.json', {dataset_name: 'parser_chunking_priority_v1', source_sha256: report.source_sha256, preprocessing: 'raw text; model-specific preprocessing belongs to EmbeddingService', chunks});
  console.log(JSON.stringify(report, null, 2));
}
if (require.main === module) main();
module.exports = {validateDocument};
