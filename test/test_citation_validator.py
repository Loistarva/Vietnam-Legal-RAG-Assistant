import copy
import unittest
from grounding.citation_validator import validate


def fixture():
    evidence={'evidence_index':1,'chunk_id':'c1','document_id':'doc1',
              'article_id':'a8','clause_id':None,'source_title':'Synthetic law fixture',
              'text':'Synthetic legal evidence; not a legal answer.',
              'effective_from':'2020-01-01','effective_to':None}
    context={'query_id':'synthetic-q1','as_of_date':'2026-11-12','evidence':[evidence],
             'source_map':{'1':copy.deepcopy(evidence)},'token_budget':4096}
    response={'answer_draft':'Synthetic draft [1].','evidence_indices':[1],
              'done_reason':'stop','truncated':False,'model':'fake','model_version':'fixture-v1',
              'prompt_version':'fixture-v1','latency_ms':0}
    return context,response


class ValidatorTests(unittest.TestCase):
    def test_pass_and_no_input_mutation(self):
        context,response=fixture();before=copy.deepcopy((context,response))
        result=validate(context,response)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['validated_answer'],response['answer_draft'])
        self.assertEqual(result['citations'][0]['chunk_id'],'c1')
        self.assertEqual((context,response),before)
        result['citations'][0]['chunk_id']='changed'
        self.assertEqual(context['source_map']['1']['chunk_id'],'c1')

    def test_unsupported_duplicate_and_invalid_indices(self):
        for indices,code in [([2],'unsupported_evidence_index'),([1,1],'duplicate_evidence_index'),
                             ([True],'citation_invalid'),(['1'],'citation_invalid'),
                             ([0],'citation_invalid'),([],'citation_invalid'),(None,'citation_invalid')]:
            with self.subTest(indices=indices):
                context,response=fixture();response['evidence_indices']=indices
                result=validate(context,response)
                self.assertIn(code,result['violation_codes'])
                self.assertIsNone(result['validated_answer'])
                self.assertFalse(result['citations'])
                self.assertTrue(result['retryable'])

    def test_all_source_mappings_must_match(self):
        for field,value in [('chunk_id','forged'),('document_id','forged'),('article_id','a9'),
                            ('clause_id','k2'),('source_title','forged'),('text','injected text'),
                            ('effective_from','2021-01-01'),('evidence_index',True)]:
            with self.subTest(field=field):
                context,response=fixture();context['source_map']['1'][field]=value
                result=validate(context,response)
                self.assertIn('context_mismatch',result['violation_codes'])
                self.assertFalse(result['retryable'])

    def test_missing_metadata(self):
        for field in ['chunk_id','document_id','text','source_title','effective_from']:
            context,response=fixture()
            context['evidence'][0].pop(field);context['source_map']['1'].pop(field)
            self.assertIn('citation_metadata_missing',validate(context,response)['violation_codes'])

    def test_bad_contexts_and_alias_indices(self):
        for key in ['01',True,'E1']:
            context,response=fixture();context['source_map']={key:context['source_map']['1']}
            self.assertEqual(validate(context,response)['status'],'FAIL')
        context,response=fixture();context['source_map']['2']=context['source_map']['1']
        self.assertIn('context_mismatch',validate(context,response)['violation_codes'])
        context,response=fixture();context['evidence'].append(copy.deepcopy(context['evidence'][0]))
        self.assertIn('context_mismatch',validate(context,response)['violation_codes'])
        self.assertEqual(validate(None,response)['violation_codes'],['context_invalid'])

    def test_temporal_boundaries_and_unknown_dates(self):
        for start,end,code in [('2027-01-01',None,'evidence_not_effective'),
                               ('2020-01-01','2026-11-12','evidence_not_effective'),
                               ('2020-01-01','2019-01-01','temporal_metadata_invalid'),
                               ('unknown',None,'temporal_metadata_invalid')]:
            context,response=fixture()
            for item in [context['evidence'][0],context['source_map']['1']]:
                item.update(effective_from=start,effective_to=end)
            self.assertIn(code,validate(context,response)['violation_codes'])
        context,response=fixture();context['as_of_date']='20261112'
        self.assertEqual(validate(context,response)['status'],'FAIL')
        context,response=fixture()
        for item in [context['evidence'][0],context['source_map']['1']]:item['effective_from']='2026-11-12'
        self.assertEqual(validate(context,response)['status'],'PASS')

    def test_incomplete_and_fabricated_citations_never_release_draft(self):
        for changes,code in [({'truncated':True},'llm_incomplete'),
                             ({'done_reason':'length'},'llm_incomplete'),
                             ({'done_reason':'unknown'},'llm_incomplete'),
                             ({'citations':[{'document_id':'forged'}]},'json_invalid'),
                             ({'answer_draft':''},'json_invalid'),({'truncated':None},'json_invalid')]:
            context,response=fixture();response.update(changes)
            result=validate(context,response)
            self.assertEqual(result['violation_codes'],[code])
            self.assertIsNone(result['validated_answer'])

    def test_empty_retrieval_not_retryable(self):
        context,response=fixture();context['evidence']=[];context['source_map']={}
        result=validate(context,response)
        self.assertEqual(result['violation_codes'],['retrieval_empty'])
        self.assertFalse(result['retryable'])

    def test_public_model_dump_interface(self):
        class Model:
            def __init__(self,value):self.value=value
            def model_dump(self,mode):return copy.deepcopy(self.value)
        context,response=fixture()
        self.assertEqual(validate(Model(context),Model(response))['status'],'PASS')

    def test_integer_map_keys(self):
        context,response=fixture();context['source_map']={1:context['source_map']['1']}
        self.assertEqual(validate(context,response)['status'],'PASS')

    def test_inline_citations_cannot_bypass_selected_indices(self):
        context,response=fixture();response['answer_draft']='Invalid reference [999].'
        self.assertEqual(validate(context,response)['violation_codes'],['unsupported_evidence_index'])
        context,response=fixture()
        extra=copy.deepcopy(context['evidence'][0]);extra.update(evidence_index=2,chunk_id='c2')
        context['evidence'].append(extra);context['source_map']['2']=copy.deepcopy(extra)
        response['answer_draft']='Unselected reference [2].'
        self.assertEqual(validate(context,response)['violation_codes'],['citation_invalid'])
