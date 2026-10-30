"""Automated structural, clause-level, and temporal QA for the 300-question benchmark."""
import sys,unittest,copy,hashlib,json,collections,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.validate_benchmark import inputs,validate_dataset,check
from scripts.freeze_test import manifest
from scripts.freeze_gold import current as current_gold_freeze

class BenchmarkContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dev,cls.test,cls.gold,cls.articles,cls.chunks,cls.docs,cls.schema=inputs()
    def validate(self,**kwargs):
        data={'dev':copy.deepcopy(self.dev),'test':copy.deepcopy(self.test),'gt':copy.deepcopy(self.gold),
              'articles':copy.deepcopy(self.articles),'chunks':copy.deepcopy(self.chunks),
              'docs':copy.deepcopy(self.docs),'schema':copy.deepcopy(self.schema)}
        data.update(kwargs);return validate_dataset(**data)
    def test_schema_and_data_pass_handoff(self):self.assertEqual(check()[0],[])
    def test_total_between_50_and_300(self):self.assertTrue(50<=len(self.dev+self.test)<=300)
    def test_split(self):self.assertEqual((len(self.dev),len(self.test)),(270,30))
    def test_split_disjoint(self):self.assertFalse({q['id'] for q in self.dev}&{q['id'] for q in self.test})
    def test_all_questions_have_gold(self):self.assertEqual({q['id'] for q in self.dev+self.test},{g['id'] for g in self.gold})
    def test_no_duplicate_question(self):self.assertEqual(len({q['question'] for q in self.dev+self.test}),300)
    def test_unique_context_registry(self):self.assertEqual(len({c['chunk_id'] for c in self.chunks}),len(self.chunks))
    def test_all_mapped_chunks_in_registry(self):
        seen={c['chunk_id'] for c in self.chunks}
        production=ROOT/'data'/'reference'/'production_chunk_index.json'
        self.assertTrue(production.exists())
        seen |= {c['chunk_id'] for c in json.loads(production.read_text(encoding='utf-8'))}
        self.assertTrue(all(set(g['gold_context_ids']+g['candidate_context_ids'])<=seen for g in self.gold))

    def test_article_index_matches_parsed_json_articles(self):
        parsed_dir = ROOT / 'parser' / 'parsed_jsons'
        parsed_files = list(parsed_dir.glob('*.json'))
        self.assertTrue(parsed_files)

        parsed_articles = {}
        for f in parsed_files:
            doc = json.loads(f.read_text(encoding='utf-8'))
            doc_number = doc['metadata']['document_number']
            for a in doc.get('articles', []):
                art_no = str(a['article_number'])
                raw_title = (a.get('title') or '').strip()
                expected_title = f"Điều {art_no}. {raw_title}" if raw_title else f"Điều {art_no}"
                parsed_articles[(doc_number, art_no)] = expected_title

        doc_registry = {d['document_number']: d for d in self.docs}
        index_articles = {}
        article_by_id = {}
        for r in self.articles:
            doc_no = r['document_number']
            art_no = str(r['article_number'])
            index_articles[(doc_no, art_no)] = (r.get('article_title') or '').strip()
            article_by_id[r['article_id']] = r
            self.assertIn(doc_no, doc_registry)
            expected_prefix = doc_registry[doc_no]['file_code'] + '_D'
            self.assertTrue(r['article_id'].startswith(expected_prefix), f"ID format mismatch for {r['article_id']}")
            self.assertEqual(
                (r.get('article_title') or '').strip(),
                parsed_articles.get((doc_no, art_no)),
                f"Article title mismatch for {r['article_id']}",
            )

        self.assertEqual(set(parsed_articles.keys()), set(index_articles.keys()))
        self.assertEqual(parsed_articles, index_articles)
        self.assertEqual(len({r['article_id'] for r in self.articles}), len(self.articles))

        # C5: Every article_id in gold_article_ids of reviewed questions must have verified verification_status
        reviewed_gold = [g for g in self.gold if g.get('review_status') != 'draft']
        self.assertEqual(len(reviewed_gold), 100)
        for g in reviewed_gold:
            for aid in g.get('gold_article_ids', []):
                self.assertIn(aid, article_by_id, f"{g['id']}: missing {aid} in article_index")
                vstatus = article_by_id[aid].get('verification_status')
                self.assertNotIn(
                    vstatus,
                    ('metadata_only_unverified', 'not_checked', None, ''),
                    f"{g['id']}: article {aid} has unverified status {vstatus!r}",
                )
                self.assertEqual(vstatus, 'source_checked')

    def test_gold_clause_ids_map_to_chunks_in_corpus(self):
        chunks_path = ROOT / 'data' / 'chunking_output' / 'chunks.jsonl'
        self.assertTrue(chunks_path.exists())
        chunks = [
            json.loads(line)
            for line in chunks_path.read_text(encoding='utf-8-sig').splitlines()
            if line.strip()
        ]
        chunk_to_clause = {c['chunk_id']: c.get('parent_clause_id') for c in chunks}
        clause_to_chunks = collections.defaultdict(list)
        for c in chunks:
            if c.get('parent_clause_id'):
                clause_to_chunks[c['parent_clause_id']].append(c['chunk_id'])

        # 1. Verify all items with non-empty gold_clause_ids
        for g in self.gold:
            clause_ids = g.get('gold_clause_ids', [])
            if clause_ids:
                for clid in clause_ids:
                    self.assertIn(clid, clause_to_chunks, f"{g['id']}: clause {clid} not in corpus chunks")
                for cid in g.get('gold_context_ids', []):
                    parent_clause = chunk_to_clause.get(cid)
                    self.assertIn(parent_clause, clause_ids, f"{g['id']}: chunk {cid} parent {parent_clause} not in gold_clause_ids")

        # 2. Test all 3 cases of bidirectional mapping function sync_gold_context_ids_from_clauses + backup
        from scripts.prepare_production_benchmark import sync_gold_context_ids_from_clauses
        sample_chunk = chunks[0]
        sample_cid = sample_chunk['chunk_id']
        sample_clause = sample_chunk['parent_clause_id']
        other_chunk = next(c for c in chunks if c['parent_clause_id'] != sample_clause)
        other_clause = other_chunk['parent_clause_id']

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / 'ground_truth.json'
            backup_dir = Path(tmpdir) / 'backups'

            # Case 2: chunk -> clause (gold_context_ids populated, gold_clause_ids empty)
            mock_gt_c2 = [{'id': 'HN_001', 'gold_context_ids': [sample_cid], 'gold_clause_ids': []}]
            tmp_path.write_text(json.dumps(mock_gt_c2), encoding='utf-8')
            res_c2 = sync_gold_context_ids_from_clauses(
                chunks_path=chunks_path, ground_truth_path=tmp_path, save=True, backup_dir=backup_dir
            )
            self.assertEqual(res_c2[0]['gold_clause_ids'], [sample_clause])
            self.assertTrue(list(backup_dir.glob('*.bak')), "Expected automatic backup file before write")

            # Case 1: clause -> chunk (gold_clause_ids populated, gold_context_ids empty)
            mock_gt_c1 = [{'id': 'HN_001', 'gold_context_ids': [], 'gold_clause_ids': [sample_clause]}]
            tmp_path.write_text(json.dumps(mock_gt_c1), encoding='utf-8')
            res_c1 = sync_gold_context_ids_from_clauses(
                chunks_path=chunks_path, ground_truth_path=tmp_path, save=False
            )
            self.assertEqual(res_c1[0]['gold_context_ids'], clause_to_chunks[sample_clause])

            # Case 3a: both populated and consistent -> succeeds without error
            mock_gt_c3_ok = [{
                'id': 'HN_001',
                'gold_context_ids': list(clause_to_chunks[sample_clause]),
                'gold_clause_ids': [sample_clause],
            }]
            tmp_path.write_text(json.dumps(mock_gt_c3_ok), encoding='utf-8')
            res_c3_ok = sync_gold_context_ids_from_clauses(
                chunks_path=chunks_path, ground_truth_path=tmp_path, save=False
            )
            self.assertEqual(res_c3_ok[0]['gold_clause_ids'], [sample_clause])

            # Case 3b: both populated and mismatch -> MUST raise ValueError with question ID
            mock_gt_c3_err = [{
                'id': 'HN_001',
                'gold_context_ids': [sample_cid],
                'gold_clause_ids': [other_clause],
            }]
            tmp_path.write_text(json.dumps(mock_gt_c3_err), encoding='utf-8')
            with self.assertRaises(ValueError) as ctx:
                sync_gold_context_ids_from_clauses(
                    chunks_path=chunks_path, ground_truth_path=tmp_path, save=False
                )
            self.assertIn('HN_001', str(ctx.exception))

    def test_unmapped_explicit_not_faked(self):
        pending=[g for g in self.gold if g['mapping_status']=='not_mapped']
        self.assertEqual(len(pending),24)
        self.assertTrue(all(not g['gold_context_ids'] and not g['candidate_context_ids'] for g in pending))
    def test_mapping_counts(self):
        from collections import Counter
        counts = Counter(g['mapping_status'] for g in self.gold)
        self.assertEqual(sum(counts.values()), 300)
        self.assertEqual(counts['not_mapped'], 24)
        self.assertEqual(counts['production_verified'], 100)
        self.assertEqual(counts['production_candidate_unverified'], 176)
        self.assertEqual(counts['production_candidate_unverified'] + counts['production_verified'], 276)
        self.assertEqual(sum(bool(g['candidate_context_ids'] or g['gold_context_ids']) for g in self.gold), 276)
        self.assertTrue(all(bool(g['gold_context_ids']) == bool(g['gold_context_ids_confirmed']) for g in self.gold))

    def test_expansion_is_unverified_and_unmapped(self):
        added=[g for g in self.gold if int(g['id'].split('_')[1])>=61]
        self.assertEqual(len(added),240)
        verified_added=[g for g in added if g['review_status']!='draft']
        draft_added=[g for g in added if g['review_status']=='draft']
        self.assertEqual(len(verified_added),64)
        self.assertEqual(len(draft_added),176)
        self.assertTrue(all(g['mapping_status']=='production_candidate_unverified'
                            and not g['gold_context_ids'] and bool(g['candidate_context_ids']) and bool(g['gold_article_ids'])
                            and not g['gold_context_ids_confirmed'] for g in draft_added))
        self.assertTrue(all(g['mapping_status']=='production_verified'
                            and bool(g['gold_context_ids']) and bool(g['gold_clause_ids']) and bool(g['gold_article_ids'])
                            and g['gold_context_ids_confirmed'] for g in verified_added))
    def test_all_new_answers_are_pdf_based_drafts(self):
        added=[g for g in self.gold if int(g['id'].split('_')[1])>=61]
        self.assertEqual(len(added),240)
        draft_added=[g for g in added if g['review_status']=='draft']
        verified_added=[g for g in added if g['review_status']!='draft']
        self.assertEqual(len(draft_added),176)
        self.assertEqual(len(verified_added),64)
        self.assertTrue(all(g['evidence_level']=='pdf_text_extracted_unverified'
                            and len(g['answer'])>80 and 'CHUA_XAC_MINH' not in g['answer']
                            and not g['gold_context_ids_confirmed']
                            for g in draft_added))
        self.assertTrue(all(g['evidence_level']=='full_text_checked'
                            and g['answer_kind']=='reviewed_answer'
                            and len(g['answer'])>80 and 'CHUA_XAC_MINH' not in g['answer']
                            and g['gold_context_ids_confirmed']
                            for g in verified_added))
    def test_original_test_split_unchanged(self):
        self.assertEqual(len(self.test),30)
        self.assertEqual([x['id'] for x in self.test],manifest()['test_ids'])
    def test_no_clause_leakage_between_dev_and_test(self):
        by_id = {g['id']: g for g in self.gold}
        test_ids = {q['id'] for q in self.test}
        dev_ids = {q['id'] for q in self.dev}
        self.assertEqual(len(test_ids), 30)
        self.assertEqual(len(dev_ids), 270)
        test_clauses = set()
        for qid in test_ids:
            g = by_id[qid]
            self.assertEqual(g['review_status'], 'source_checked', f"Test question {qid} must be source_checked")
            self.assertTrue(g.get('gold_clause_ids'), f"Test question {qid} must have gold_clause_ids")
            self.assertTrue(g.get('gold_context_ids'), f"Test question {qid} must have gold_context_ids")
            test_clauses.update(g['gold_clause_ids'])
        dev_clauses = {
            cl
            for qid in dev_ids
            for cl in by_id[qid].get('gold_clause_ids', [])
        }
        self.assertFalse(test_clauses & dev_clauses, f"Leakage of gold_clause_ids between Dev and Test: {test_clauses & dev_clauses}")
    def test_test_gold_frozen(self):
        gold_manifest_path = ROOT / 'docs' / 'test_gold_freeze.json'
        self.assertTrue(gold_manifest_path.exists())
        gold_manifest = json.loads(gold_manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(gold_manifest, current_gold_freeze())
    def test_no_false_legal_approval(self):
        for g in self.gold:
            if g['review_status'] == 'draft':
                self.assertNotEqual(g['answer_kind'], 'reviewed_answer', g['id'])
            else:
                self.assertIn(g['review_status'], ('source_checked', 'peer_reviewed', 'lawyer_verified'), g['id'])
                self.assertEqual(g['answer_kind'], 'reviewed_answer', g['id'])
                self.assertTrue(g['verified_by'] and g['verified_at'], g['id'])
                self.assertNotIn('HO_TEN_', g['verified_by'], g['id'])

    def test_no_false_production_approval(self):
        production = ROOT/'data'/'reference'/'production_chunk_index.json'
        index = {c['chunk_id']:c for c in json.loads(production.read_text(encoding='utf-8'))}
        for g in self.gold:
            if g['gold_context_ids_confirmed']:
                self.assertTrue(g['gold_context_ids'], g['id'])
                self.assertEqual(g['mapping_status'], 'production_verified', g['id'])
                self.assertEqual(g['context_id_provenance'], 'production_index', g['id'])
                self.assertTrue(set(g['gold_context_ids']) <= set(index), g['id'])
                self.assertTrue(all(index[c]['article_id'] in g['gold_article_ids'] for c in g['gold_context_ids']), g['id'])
            else:
                self.assertFalse(g['gold_context_ids'], g['id'])
                self.assertNotEqual(g['mapping_status'], 'production_verified', g['id'])

    def test_duplicate_query_id_is_detected(self):
        q=copy.deepcopy(self.test);q[0]['id']=self.dev[0]['id']
        self.assertTrue(any('Trùng question ID' in e for e in self.validate(test=q)))

    def test_missing_question_text_fails_schema(self):
        q=copy.deepcopy(self.dev);del q[0]['question']
        self.assertTrue(any('required property' in e for e in self.validate(dev=q)))
    def test_invalid_date_fails_schema(self):
        q=copy.deepcopy(self.test);q[0]['as_of_date']='2026-99-99'
        self.assertTrue(any('date' in e.lower() for e in self.validate(test=q)))
    def test_gold_missing_fails(self):
        g=copy.deepcopy(self.gold);g.pop()
        self.assertTrue(any('Question IDs lệch' in e for e in self.validate(gt=g)))
    def test_duplicated_gold_id_fails(self):
        g=copy.deepcopy(self.gold);g[1]['id']=g[0]['id']
        self.assertTrue(any('Trùng ground-truth ID' in e for e in self.validate(gt=g)))
    def test_wrong_article_id_rejected(self):
        g=copy.deepcopy(self.gold);g[0]['gold_article_ids']=['NOT_REAL']
        self.assertTrue(any('article ID không tồn tại' in e for e in self.validate(gt=g)))
    def test_fabricated_gold_chunk_rejected(self):
        g=copy.deepcopy(self.gold);g[0]['gold_context_ids']=['FAKE_CHUNK_1']
        self.assertTrue(any('chunk ID giả' in e for e in self.validate(gt=g)))
    def test_article_not_allowed_as_context_id(self):
        g=copy.deepcopy(self.gold);g[0]['gold_context_ids']=['L01_D08']
        self.assertTrue(any('article_id không được dùng' in e for e in self.validate(gt=g)))
    def test_cross_document_chunk_rejected(self):
        g=copy.deepcopy(self.gold);g[0]['gold_context_ids']=['DIFF_DOC']
        c=copy.deepcopy(self.chunks);c.append({'chunk_id':'DIFF_DOC','document_number':'22/2000/QH10','article_id':'XXX', 'chunk_text':'text'})
        self.assertTrue(any('sai văn bản' in e for e in self.validate(gt=g,chunks=c)))
    def test_wrong_article_chunk_rejected(self):
        g=copy.deepcopy(self.gold);g[0]['gold_context_ids']=['l_52_2014_qh13_art_9_clause_1_chunk_1']
        self.assertTrue(any('không thuộc gold_article_ids' in e for e in self.validate(gt=g)))
    def test_wrong_mapping_status_rejected(self):
        g=copy.deepcopy(self.gold);g[0]['mapping_status']='not_mapped'
        self.assertTrue(any('not_mapped nhưng có context ID' in e for e in self.validate(gt=g)))
    def test_false_verified_flag_rejected(self):
        g = copy.deepcopy(self.gold)
        candidate = next(item for item in g if item['review_status'] == 'draft' and item['candidate_context_ids'])
        candidate['gold_context_ids_confirmed'] = True
        self.assertTrue(any('production nhưng nhãn' in e or 'không có gold_context_ids' in e
                            for e in self.validate(gt=g)))

    def test_review_signature_needed(self):
        g = copy.deepcopy(self.gold)
        draft = next(item for item in g if item['review_status'] == 'draft' and item['candidate_context_ids'])
        draft['review_status'] = 'source_checked'
        self.assertTrue(any('thiếu verified_at' in e for e in self.validate(gt=g)))

    def test_temporal_source_check(self):
        q=copy.deepcopy(self.dev);q[0]['as_of_date']='2012-10-15'
        self.assertTrue(any('trước ngày có hiệu lực' in e for e in self.validate(dev=q)))
    def test_final_gating_not_false_success(self):
        self.assertTrue(any('chưa có gold_context_ids' in e for e in check(final=True)[0]))
    def test_all_300_have_nonempty_answers_and_explanations(self):
        self.assertEqual(len(self.gold),300)
        self.assertTrue(all(len(g['answer'].strip())>=3 and len(g['explanation'].strip())>=30 for g in self.gold))
    def test_test_freeze_detects_mutated_question(self):
        q=copy.deepcopy(self.test)
        q[0]['question'] += ' (thay đổi trái phép)'
        self.assertTrue(any('Test set đã thay đổi' in e for e in self.validate(test=q)))
    def test_all_300_have_at_least_one_citation(self):
        self.assertTrue(all(g['citations'] for g in self.gold))
    def test_final_rejects_draft_even_with_source_reference(self):
        issues=self.validate()
        self.assertEqual(issues, [])
        self.assertTrue(any('chưa xác minh chunk' in e or 'chưa có gold_context_ids' in e for e in check(final=True)[0]))
    def test_unique_gold_and_article_mapping_for_expansion(self):
        added=[g for g in self.gold if int(g['id'][3:])>60]
        self.assertEqual(len(added),240)
        self.assertTrue(all(bool(g['gold_article_ids']) for g in added))
        self.assertEqual(sum(1 for g in added if g['gold_context_ids_confirmed']), 64)
        self.assertEqual(sum(1 for g in added if not g['gold_context_ids_confirmed']), 176)
    def test_test_questions_frozen(self):
        manifestfile=json.loads((ROOT/'docs'/'test_questions_freeze.json').read_text(encoding='utf8'))
        self.assertEqual(manifestfile,manifest())
    def test_reject_smoke_id_in_gold_field(self):
        g = copy.deepcopy(self.gold)
        draft = next(item for item in g if item['review_status'] == 'draft' and item['candidate_context_ids'])
        draft['gold_context_ids'] = [draft['candidate_context_ids'][0]]
        draft['candidate_context_ids'] = draft['candidate_context_ids'][1:]
        self.assertTrue(any('chưa được xác nhận production' in e for e in self.validate(gt=g)))

    def test_answer_kind_required(self):
        g=copy.deepcopy(self.gold);del g[0]['answer_kind']
        self.assertTrue(any('answer_kind' in e for e in self.validate(gt=g)))
    def test_final_rejects_extracted_pdf_as_answer(self):
        self.assertTrue(any('answer chưa được biên soạn' in e for e in check(final=True)[0]))
    def test_review_must_use_reviewed_answer_kind(self):
        g = copy.deepcopy(self.gold)
        draft = next(item for item in g if item['review_status'] == 'draft' and item['candidate_context_ids'])
        draft['review_status'] = 'source_checked'
        draft['verified_at'] = '2026-10-18'
        draft['verified_by'] = 'test_reviewer'
        self.assertTrue(any('answer_kind chưa phải reviewed_answer' in e for e in self.validate(gt=g)))

    def test_fix_historical_citation(self):
        g=next(i for i in self.gold if i['id']=='HN_053')
        self.assertEqual(g['citations'][0]['document_id'],'52/2014/QH13')

if __name__=='__main__':unittest.main()
