const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {validateDocument} = require('../embedding/prepare_priority_dataset.cjs');
const root = path.resolve(__dirname, '..');
const read = p => JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const doc = read('data/chunking_output/documents/L01.json');
const rows = new Map(fs.readFileSync(path.join(root,'data/chunking_output/chunks.jsonl'),'utf8').trim().split(/\r?\n/).map(line => {const r=JSON.parse(line); return [r.chunk_id,r];}));
test('existing parser output preserves every clause body', () => assert.deepEqual(validateDocument(doc,rows),[]));
test('validator detects missing legal content', () => {
 const bad = structuredClone(doc);
 bad.articles[0].clauses[0].clause_text += ' LOST CONTENT';
 assert.ok(validateDocument(bad,rows).some(e => e.startsWith('Content loss:')));
});
test('validator detects incorrect parent references', () => {
 const bad = structuredClone(doc);
 bad.articles[0].clauses[0].parent_article_id = 'wrong';
 assert.ok(validateDocument(bad,rows).some(e => e.startsWith('Clause parent:')));
});
test('draft labels reference the frozen dataset and keep articles across splits separate', () => {
 const chunks = read('embedding/data/priority_chunks.json').chunks;
 const ids = new Set(chunks.map(c=>c.id));
 const questions = read('embedding/data/priority_questions.draft.json').questions;
 assert.equal(questions.length,50);
 const articles = {dev:new Set(), test:new Set()};
 for(const q of questions) {
   assert.ok(q.relevant_chunk_ids.every(id=>ids.has(id)));
   assert.ok(q.reference_answer_excerpt.trim());
   articles[q.split].add(q.source_clause_id.split('_clause_')[0]);
 }
 assert.equal(questions.filter(q=>q.split==='dev').length,10);
 assert.ok([...articles.dev].every(a=>!articles.test.has(a)));
});
