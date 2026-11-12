import json
import unittest
from types import SimpleNamespace as NS
from agent.provider_config import ProviderConfig
from agent.openai_provider import OpenAIProvider
from agent.source_generation import InvalidProviderOutput, ProviderUnavailable


class OpenAITests(unittest.TestCase):
    def setUp(self):
        self.count_calls=[];self.calls=[]
        self.response=NS(status='completed',output_text='{"selected_source_ids":["E1"]}')
        def count(**kwargs):
            self.count_calls.append(kwargs)
            return NS(input_tokens=20)
        def create(**kwargs):
            self.calls.append(kwargs)
            return self.response
        self.client=NS(responses=NS(input_tokens=NS(count=count),create=create))
        self.provider=OpenAIProvider(ProviderConfig(provider='openai',model_id='configured-model',context_window=100,output_reserve=30),self.client)
        self.messages=[{'role':'user','content':json.dumps({'query':'test','sources':[{'source_id':'E1','text':'source'}]})}]

    def test_identical_count_and_generation_payload(self):
        self.assertEqual(self.provider.count_messages(self.messages),20)
        self.assertEqual(self.provider.select_sources(self.messages,30),{'selected_source_ids':['E1']})
        self.assertEqual(len(self.count_calls),1)
        generated=self.calls[0].copy()
        self.assertFalse(generated.pop('store'))
        self.assertEqual(generated.pop('max_output_tokens'),30)
        self.assertEqual(generated,self.count_calls[0])
        self.assertEqual(generated['text']['format']['schema']['properties']['selected_source_ids']['items']['enum'],['E1'])

    def test_budget_blocks_generation(self):
        self.provider.config=ProviderConfig(provider='openai',model_id='configured-model',context_window=40,output_reserve=30)
        with self.assertRaises(ValueError):self.provider.select_sources(self.messages,30)
        self.assertFalse(self.calls)

    def test_invalid_and_incomplete_output(self):
        for status,text in [('incomplete','{}'),('completed','not json'),('completed','')]:
            self.response.status,self.response.output_text=status,text
            with self.assertRaises(InvalidProviderOutput):self.provider.select_sources(self.messages,30)

    def test_count_failure_blocks_generation(self):
        def fail(**kwargs):raise TimeoutError('secret')
        self.client.responses.input_tokens.count=fail
        with self.assertRaises(ProviderUnavailable):self.provider.select_sources(self.messages,30)
        self.assertFalse(self.calls)

    def test_requires_explicit_model(self):
        with self.assertRaises(ValueError):ProviderConfig(provider='openai')
