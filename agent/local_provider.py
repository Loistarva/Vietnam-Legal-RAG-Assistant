"""Optional cached Transformers chat adapter for source-ID selection only."""
import json
from .source_generation import InvalidProviderOutput, ProviderUnavailable


class LocalTransformersProvider:
    def __init__(self,config):
        if config.provider!='transformers_local':
            raise ValueError('Local model loading requires explicit opt-in')
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoTokenizer, AutoModelForCausalLM
        snapshot=snapshot_download(config.model_id,revision=config.revision,local_files_only=True)
        kwargs={'local_files_only':True,'trust_remote_code':False}
        self.tokenizer=AutoTokenizer.from_pretrained(snapshot,**kwargs)
        if not self.tokenizer.chat_template:
            raise ValueError('A model-specific chat template is required')
        self.model=AutoModelForCausalLM.from_pretrained(snapshot,**kwargs).to('cpu').eval()
        limit=getattr(self.model.config,'max_position_embeddings',None)
        if not isinstance(limit,int) or config.context_window>limit:
            raise ValueError('Cannot verify the configured model context limit')
        self.model_id=f'{config.model_id}@{config.revision}'
        self.config,self.torch=config,torch

    def count_messages(self,messages):
        ids=self.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
        return len(ids)

    def select_sources(self,messages,max_output_tokens):
        if type(max_output_tokens) is not int or not 0 < max_output_tokens <= self.config.output_reserve:
            raise ValueError('Output limit exceeds configured reserve')
        encoded=self.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,
                                                   return_tensors='pt',return_dict=True).to('cpu')
        input_length=encoded['input_ids'].shape[-1]
        if input_length+max_output_tokens>self.config.context_window:
            raise ValueError('Full chat template exceeds the generation budget')
        try:
            with self.torch.inference_mode():
                generated=self.model.generate(**encoded,max_new_tokens=max_output_tokens,do_sample=False)
            text=self.tokenizer.decode(generated[0,input_length:],skip_special_tokens=True)
        except (RuntimeError,OSError) as exc:
            raise ProviderUnavailable('Local model generation failed') from exc
        try:
            return json.loads(text)
        except (json.JSONDecodeError,TypeError) as exc:
            raise InvalidProviderOutput('Provider did not return a JSON source selection') from exc


def build_provider(config):
    if config.provider=='openai':
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(config)
    return None if config.provider=='disabled' else LocalTransformersProvider(config)
