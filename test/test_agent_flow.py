import json
import unittest

from agent.routing import route_query
from agent.context_packing import ContextPacker, BudgetExceeded
from agent.controller import LegalAgent
from agent.source_generation import SourceGenerationStage, validate_selection


def result(article='NGUYÊN ĐIỀU. '*4,clause='Nguyên khoản đầy đủ.',duplicate=False):
    citation={'document_type':'Luật','document_number':'52/2014/QH13','article_number':'8',
              'clause_number':'1','clause_number_is_synthetic':False,'label':'Luật 52/2014/QH13, Điều 8, Khoản 1'}
    hit={'chunk_id':'child1','context':{'article_id':'L01_art_8','clause_id':'L01_art_8_clause_1',
         'parent_clause_text':clause,'citation':citation}}
    return {'evidence':[hit,hit] if duplicate else [hit],
            'parent_contexts':[{'article_id':'L01_art_8','text':article}],
            'applied_policy':{'validity_mode':'current_only'}}


def packer(window=2500,provider_model=None):
    return ContextPacker(lambda msgs:sum(len(m['content']) for m in msgs),'test-character-counter',
                         context_window=window,output_reserve=100,provider_model=provider_model)


class AgentFlowTests(unittest.TestCase):
    def test_router_social_legal_mixed_and_historical(self):
        self.assertEqual(route_query('Xin chào').kind,'general')
        self.assertEqual(route_query('Xin chào, tuổi kết hôn là bao nhiêu?').kind,'legal')
        self.assertEqual(route_query('Cha có quyền nhận con không?').kind,'legal')
        self.assertNotEqual(route_query('Nhân công hôm nay có bao nhiêu?').kind,'legal')
        self.assertEqual(route_query('Ly hôn').kind,'clarify')
        self.assertEqual(route_query('Thuế thu nhập cá nhân là gì?').kind,'out_of_scope')
        self.assertEqual(route_query('Thuế tài sản chung của vợ chồng?').kind,'clarify')
        self.assertEqual(route_query('Luật hôn nhân còn hiệu lực năm 2010 không?').reason,'historical_validity_unavailable')
        self.assertNotEqual(route_query('152/2014/QH13',known_numbers=['52/2014/QH13']).kind,'legal')

    def test_fast_paths_never_search_or_generate(self):
        class Search:
            def search(self,q): raise AssertionError('Retrieval must be bypassed')
        agent=LegalAgent(Search(),packer())
        for q in ['Xin chào','Ly hôn','Thuế thu nhập cá nhân là gì?']:
            out=agent.prepare(q)
            self.assertFalse(out['retrieval_called']);self.assertFalse(out['llm_called'])

    def test_long_query_is_rejected_before_embedding(self):
        class Search:
            def search(self,q): raise AssertionError('Oversized query must be rejected first')
        out=LegalAgent(Search(),packer(800)).prepare('Điều kiện kết hôn? '+'nội dung '*200)
        self.assertEqual(out['reason'],'request_too_large')
        self.assertFalse(out['retrieval_called'])

    def test_article_dedup_and_correct_citation_scope(self):
        out=packer().pack('Tuổi kết hôn?',result(duplicate=True))
        self.assertEqual(len(out['sources']),1)
        self.assertEqual(out['sources'][0]['text'],'NGUYÊN ĐIỀU. '*4)
        self.assertEqual(out['sources'][0]['scope'],'article')
        self.assertIsNone(out['sources'][0]['citation']['clause_number'])
        self.assertNotIn('Khoản',out['sources'][0]['citation']['label'])
        self.assertLessEqual(out['input_token_count'],out['input_budget'])

    def test_whole_clause_fallback_not_truncation(self):
        out=packer(2200).pack('Tuổi kết hôn?',result(article='A'*10000,clause='Khoản nguyên vẹn.'))
        self.assertEqual(out['sources'][0]['scope'],'clause')
        self.assertEqual(out['sources'][0]['text'],'Khoản nguyên vẹn.')
        self.assertEqual(out['sources'][0]['citation']['clause_number'],'1')
        none=packer(2200).pack('Tuổi kết hôn?',result(article='A'*10000,clause='B'*10000))
        self.assertEqual(none['status'],'no_evidence_fits')
        self.assertEqual(none['sources'],[])

    def test_budget_validation_and_request_invariant(self):
        with self.assertRaises(ValueError): ContextPacker(lambda m:1,'bad',context_window=True)
        with self.assertRaises(BudgetExceeded): packer(200).pack('Tuổi kết hôn?',result())
        p=packer();p.count_messages=lambda m:float('nan')
        with self.assertRaises(ValueError): p.pack('Tuổi kết hôn?',result())

    def test_no_evidence_clarifies_and_does_not_call_provider(self):
        class Search:
            def search(self,q): return {'evidence':[],'applied_policy':{'validity_mode':'current_only'}}
        out=LegalAgent(Search(),packer()).prepare('Tuổi kết hôn là bao nhiêu?')
        self.assertEqual(out['reason'],'no_eligible_evidence')
        self.assertFalse(out['llm_called'])

    def test_source_gate_rejects_unknown_duplicate_and_freeform_output(self):
        for response in [{'selected_source_ids':['missing']},{'selected_source_ids':['E1','E1']},
                         {'selected_source_ids':[{}]},{'selected_source_ids':['E1'],'answer':'invented'}]:
            with self.subTest(response=response),self.assertRaises(ValueError): validate_selection(response,{'E1':{}})

    def test_proxy_counter_cannot_authorize_provider_call(self):
        class Provider:
            model_id='fake-model'
            def select_sources(self,*args): raise AssertionError('Provider must not be called')
        prepared={'status':'ready_for_source_selection','packed_request':packer().pack('Tuổi kết hôn?',result())}
        with self.assertRaisesRegex(ValueError,'matching'): SourceGenerationStage(Provider()).run(prepared)

    def test_valid_provider_and_offline_fallback_forward_only_source_text(self):
        class Provider:
            model_id='fake-model'
            def select_sources(self,*args): return {'selected_source_ids':['E1']}
        packed=packer(provider_model='fake-model').pack('Tuổi kết hôn?',result())
        prepared={'status':'ready_for_source_selection','packed_request':packed}
        out=SourceGenerationStage(Provider()).run(prepared)
        self.assertEqual(out['sources'][0]['text'],packed['sources'][0]['text'])
        self.assertFalse(out['free_form_legal_advice']);self.assertTrue(out['llm_called'])
        local=SourceGenerationStage().run(prepared)
        self.assertFalse(local['llm_called']);self.assertFalse(local['answer_generated'])
        self.assertEqual(local['selection_mode'],'retrieval_order_extractive_fallback')

    def test_invalid_provider_selection_abstains(self):
        class Provider:
            model_id='fake-model'
            def select_sources(self,*args): return {'selected_source_ids':['missing']}
        prepared={'status':'ready_for_source_selection','packed_request':packer(provider_model='fake-model').pack('Tuổi kết hôn?',result())}
        out=SourceGenerationStage(Provider()).run(prepared)
        self.assertEqual(out['status'],'abstain');self.assertFalse(out['answer_generated'])


if __name__=='__main__': unittest.main()
