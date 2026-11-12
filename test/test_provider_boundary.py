import json
import unittest
from types import SimpleNamespace
from contextlib import nullcontext

from agent.provider_config import ProviderConfig
from agent.local_provider import LocalTransformersProvider,build_provider
from agent.context_packing import ContextPacker
from agent.source_generation import SourceGenerationStage,InvalidProviderOutput,ProviderUnavailable


def prepared():
    return {'status':'ready_for_source_selection','packed_request':{
        'provider_counter_configured':True,'provider_model':'test-model',
        'messages':[{'role':'user','content':'fixed'}],'output_reserve':10,
        'source_map':{'E1':{'source_id':'E1','text':'Nội dung đầy đủ.',
                           'citation':{'label':'Luật X, Điều 1'}}}}}


class ProviderBoundaryTests(unittest.TestCase):
    def test_default_disabled_never_loads_model(self):
        config=ProviderConfig.from_environment({})
        self.assertEqual(config.provider,'disabled')
        self.assertIsNone(build_provider(config))

    def test_opt_in_requires_exact_revision_and_valid_budgets(self):
        for kwargs in [{'provider':'remote'},{'provider':'transformers_local'},
                       {'provider':'transformers_local','model_id':'org/model','revision':'main'},
                       {'provider':'transformers_local','model_id':42,'revision':'a'*40},
                       {'max_attempts':3},{'output_reserve':4096}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError): ProviderConfig(**kwargs)

    def test_invalid_output_retry_is_bounded_and_does_not_mutate_request(self):
        class Provider:
            model_id='test-model';calls=0
            def select_sources(self,messages,reserve):
                self.calls+=1
                self.asserted=messages[0]['content']=='fixed' and reserve==10
                messages[0]['content']='mutated'
                if self.calls==1: raise InvalidProviderOutput('not JSON')
                return {'selected_source_ids':['E1']}
        provider=Provider();p=prepared()
        out=SourceGenerationStage(provider,max_attempts=2).run(p)
        self.assertEqual(out['status'],'source_excerpts');self.assertEqual(provider.calls,2)
        self.assertTrue(provider.asserted);self.assertEqual(p['packed_request']['messages'][0]['content'],'fixed')

    def test_invalid_selection_exhausts_without_expanding_sources(self):
        class Provider:
            model_id='test-model';calls=0
            def select_sources(self,messages,reserve): self.calls+=1;return {'selected_source_ids':['missing']}
        p=Provider();out=SourceGenerationStage(p,2).run(prepared())
        self.assertEqual(p.calls,2);self.assertEqual(out['status'],'abstain')
        self.assertFalse(out['answer_generated'])

    def test_provider_unavailability_is_not_a_fake_success_or_retry(self):
        class Provider:
            model_id='test-model';calls=0
            def select_sources(self,*args): self.calls+=1;raise ProviderUnavailable('internal detail')
        p=Provider();out=SourceGenerationStage(p,2).run(prepared())
        self.assertEqual(out['status'],'provider_unavailable');self.assertEqual(p.calls,1)
        self.assertNotIn('internal detail',out['message'])

    def test_exact_chat_counter_and_generation_budget_use_same_template(self):
        class Encoded(dict):
            def to(self,device): return self
        class Tokenizer:
            calls=[]
            def apply_chat_template(self,messages,**kwargs):
                self.calls.append(kwargs)
                return Encoded(input_ids=SimpleNamespace(shape=(1,7))) if kwargs.get('return_tensors') else list(range(7))
            def decode(self,*args,**kwargs): return '{"selected_source_ids":["E1"]}'
        class Generated:
            def __getitem__(self,key): return [8,9]
        class Model:
            calls=0
            def generate(self,**kwargs): self.calls+=1;self.kwargs=kwargs;return Generated()
        p=LocalTransformersProvider.__new__(LocalTransformersProvider)
        p.tokenizer,p.model=Tokenizer(),Model()
        p.torch=SimpleNamespace(inference_mode=nullcontext)
        p.config=ProviderConfig(context_window=20,output_reserve=10)
        self.assertEqual(p.count_messages([]),7)
        self.assertEqual(p.select_sources([],10),{'selected_source_ids':['E1']})
        self.assertFalse(p.model.kwargs['do_sample'])
        p.config=ProviderConfig(context_window=16,output_reserve=10)
        with self.assertRaisesRegex(ValueError,'budget'): p.select_sources([],10)
        self.assertEqual(p.model.calls,1)


if __name__=='__main__': unittest.main()
