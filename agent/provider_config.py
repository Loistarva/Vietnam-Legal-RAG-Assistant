"""Explicit opt-in provider configuration; disabled unless configured."""
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = 'disabled'
    model_id: str | None = None
    revision: str | None = None
    context_window: int = 4096
    output_reserve: int = 512
    max_attempts: int = 1

    def __post_init__(self):
        if self.provider not in ('disabled','transformers_local','openai'):
            raise ValueError('Unsupported provider; no implicit remote fallback')
        if type(self.context_window) is not int or type(self.output_reserve) is not int or not 0 < self.output_reserve < self.context_window:
            raise ValueError('Invalid provider context/output budget')
        if type(self.max_attempts) is not int or self.max_attempts not in (1,2):
            raise ValueError('Provider attempts must be 1 or 2')
        if self.provider=='openai' and (not isinstance(self.model_id,str) or not self.model_id.strip()):
            raise ValueError('OpenAI requires an explicit LLM_MODEL_ID')
        if self.provider=='transformers_local' and (not isinstance(self.model_id,str) or not self.model_id.strip() or not isinstance(self.revision,str) or not re.fullmatch(r'[0-9a-f]{40}',self.revision)):
            raise ValueError('Local provider requires model ID and exact cached 40-character revision')

    @classmethod
    def from_environment(cls,environment=None):
        env=os.environ if environment is None else environment
        return cls(provider=env.get('LLM_PROVIDER','disabled'),model_id=env.get('LLM_MODEL_ID') or None,
                   revision=env.get('LLM_MODEL_REVISION') or None,
                   context_window=int(env.get('LLM_CONTEXT_WINDOW','4096')),
                   output_reserve=int(env.get('LLM_OUTPUT_RESERVE','512')),
                   max_attempts=int(env.get('LLM_MAX_ATTEMPTS','1')))
