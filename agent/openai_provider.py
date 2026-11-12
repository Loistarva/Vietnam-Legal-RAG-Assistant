"""Opt-in Responses API source selection with full-request token counting."""
import json
import os
from collections import OrderedDict
from .source_generation import InvalidProviderOutput, ProviderUnavailable


class OpenAIProvider:
    def __init__(self,config,client=None):
        if config.provider!='openai':
            raise ValueError('OpenAI requires explicit opt-in')
        self.error_types=(TimeoutError,ConnectionError)
        if client is None:
            from openai import OpenAI, APIError
            if not os.environ.get('OPENAI_API_KEY'):
                raise ValueError('Set OPENAI_API_KEY locally before enabling OpenAI')
            client=OpenAI(base_url='https://api.openai.com/v1',timeout=30,max_retries=0)
            self.error_types+=(APIError,)
        self.client,self.config,self.model_id=client,config,config.model_id
        self.counts=OrderedDict()

    def request(self,messages):
        data=json.loads(messages[-1]['content'])
        ids=[source['source_id'] for source in data['sources']]
        item={'type':'string'}
        if ids:
            item['enum']=ids
        schema={'type':'object','properties':{'selected_source_ids':
                {'type':'array','items':item,'maxItems':5}},
                'required':['selected_source_ids'],'additionalProperties':False}
        return {'model':self.model_id,'input':messages,'truncation':'disabled',
                'text':{'format':{'type':'json_schema','name':'source_selection','strict':True,'schema':schema}}}

    def count_messages(self,messages):
        payload=self.request(messages)
        key=json.dumps(payload,ensure_ascii=False,sort_keys=True)
        if key not in self.counts:
            try:
                value=self.client.responses.input_tokens.count(**payload).input_tokens
            except self.error_types as exc:
                raise ProviderUnavailable('OpenAI token counting unavailable') from exc
            if type(value) is not int or value<0:
                raise InvalidProviderOutput('Invalid token count')
            self.counts[key]=value
            if len(self.counts)>128:
                self.counts.popitem(last=False)
        return self.counts[key]

    def select_sources(self,messages,max_output_tokens):
        if type(max_output_tokens) is not int or not 0<max_output_tokens<=self.config.output_reserve:
            raise ValueError('Invalid output reserve')
        if self.count_messages(messages)+max_output_tokens>self.config.context_window:
            raise ValueError('Full request exceeds context budget')
        try:
            response=self.client.responses.create(**self.request(messages),
                        max_output_tokens=max_output_tokens,store=False)
        except self.error_types as exc:
            raise ProviderUnavailable('OpenAI generation unavailable') from exc
        if response.status!='completed':
            raise InvalidProviderOutput('Incomplete provider response')
        try:
            return json.loads(response.output_text)
        except (TypeError,json.JSONDecodeError) as exc:
            raise InvalidProviderOutput('Invalid provider JSON') from exc
