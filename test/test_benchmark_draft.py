"""Automated structural and temporal QA. Does not assert that legal answers are verified."""
import sys,unittest,copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.validate_benchmark import inputs,validate_dataset,check
from scripts.freeze_test import manifest

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
    def test_split(self):self.assertEqual((len(self.dev),len(self.test)),(285,15))
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
    def test_unmapped_explicit_not_faked(self):
        pending=[g for g in self.gold if g['mapping_status']=='not_mapped']
        self.assertEqual(len(pending),24)
        self.assertTrue(all(not g['gold_context_ids'] and not g['candidate_context_ids'] for g in pending))
    def test_mapping_counts(self):
        from collections import Counter
        self.assertEqual(Counter(g['mapping_status'] for g in self.gold),
                         {'production_candidate_unverified':276,'not_mapped':24})
        self.assertEqual(sum(bool(g['candidate_context_ids']) for g in self.gold),276)
        self.assertEqual(sum(bool(g['gold_context_ids']) for g in self.gold),0)
    def test_expansion_is_unverified_and_unmapped(self):
        added=[g for g in self.gold if int(g['id'].split('_')[1])>=61]
        self.assertEqual(len(added),240)
        self.assertTrue(all(g['review_status']=='draft' and g['mapping_status']=='production_candidate_unverified'
                            and not g['gold_context_ids'] and bool(g['candidate_context_ids']) and bool(g['gold_article_ids'])
                            and not g['gold_context_ids_confirmed'] for g in added))
    def test_all_new_answers_are_pdf_based_drafts(self):
        added=[g for g in self.gold if int(g['id'].split('_')[1])>=61]
        self.assertEqual(len(added),240)
        self.assertTrue(all(g['evidence_level']=='pdf_text_extracted_unverified'
                            and len(g['answer'])>80 and 'CHUA_XAC_MINH' not in g['answer']
                            and not g['gold_context_ids_confirmed']
                            for g in added))
    def test_original_test_split_unchanged(self):
        self.assertEqual(len(self.test),15)
        self.assertEqual([x['id'] for x in self.test],manifest()['test_ids'])
    def test_no_false_legal_approval(self):self.assertTrue(all(g['review_status']=='draft' for g in self.gold))
    def test_no_false_production_approval(self):self.assertTrue(all(not g['gold_context_ids_confirmed'] and not g['gold_context_ids'] for g in self.gold))
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
        g=copy.deepcopy(self.gold);g[0]['gold_context_ids']=['l01_art_9_chunk_1']
        self.assertTrue(any('không thuộc gold_article_ids' in e for e in self.validate(gt=g)))
    def test_wrong_mapping_status_rejected(self):
        g=copy.deepcopy(self.gold);g[0]['mapping_status']='not_mapped'
        self.assertTrue(any('not_mapped nhưng có context ID' in e for e in self.validate(gt=g)))
    def test_false_verified_flag_rejected(self):
        g=copy.deepcopy(self.gold);g[0]['gold_context_ids_confirmed']=True
        self.assertTrue(any('production nhưng nhãn' in e for e in self.validate(gt=g)))
    def test_review_signature_needed(self):
        g=copy.deepcopy(self.gold);g[0]['review_status']='source_checked'
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
        self.assertTrue(all(g['gold_article_ids'] and not g['gold_context_ids_confirmed'] for g in added))
    def test_test_questions_frozen(self):
        manifestfile=json.loads((ROOT/'docs'/'test_questions_freeze.json').read_text(encoding='utf8'))
        self.assertEqual(manifestfile,manifest())
    def test_reject_smoke_id_in_gold_field(self):
        g=copy.deepcopy(self.gold)
        g[0]['gold_context_ids']=[g[0]['candidate_context_ids'][0]]
        g[0]['candidate_context_ids']=[]
        self.assertTrue(any('chưa được xác nhận production' in e for e in self.validate(gt=g)))
    def test_answer_kind_required(self):
        g=copy.deepcopy(self.gold);del g[0]['answer_kind']
        self.assertTrue(any('answer_kind' in e for e in self.validate(gt=g)))
    def test_final_rejects_extracted_pdf_as_answer(self):
        self.assertTrue(any('answer chưa được biên soạn' in e for e in check(final=True)[0]))
    def test_review_must_use_reviewed_answer_kind(self):
        g=copy.deepcopy(self.gold);g[0]['review_status']='source_checked';g[0]['verified_at']='2026-10-16';g[0]['verified_by']='reviewer'
        self.assertTrue(any('answer_kind chưa phải reviewed_answer' in e for e in self.validate(gt=g)))
    def test_fix_historical_citation(self):
        g=next(i for i in self.gold if i['id']=='HN_053')
        self.assertEqual(g['citations'][0]['document_id'],'52/2014/QH13')

if __name__=='__main__':unittest.main()
