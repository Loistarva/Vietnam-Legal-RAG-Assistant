"""Provider-neutral source selection and verbatim rendering, not free-form advice."""
import copy
from typing import Protocol


class InvalidProviderOutput(ValueError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


class SourceSelectionProvider(Protocol):
    model_id: str

    def select_sources(self,messages,max_output_tokens):
        """Return a parsed object: {selected_source_ids: [E1, ...]}."""
        ...


def validate_selection(response,source_map):
    if not isinstance(response,dict) or set(response)!={'selected_source_ids'}:
        raise ValueError('Only source IDs are accepted; free-form claims are not validated')
    ids=response['selected_source_ids']
    if not isinstance(ids,list) or len(ids)>5 or any(not isinstance(i,str) or i not in source_map for i in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Unknown/duplicate/invalid source selection')
    return ids


def render_extracts(ids,source_map):
    if not ids:
        return {'status':'abstain','answer_generated':False,'message':'Chưa đủ căn cứ để chọn trích đoạn phù hợp.'}
    excerpts=[copy.deepcopy(source_map[i]) for i in ids]
    # No provider-generated prose is forwarded. Preserve full selected sources.
    text='Các trích đoạn để đối chiếu với câu hỏi:\n\n'+'\n\n'.join(
        f"[{b['source_id']}] {b['citation']['label']}\n{b['text']}" for b in excerpts)
    return {'status':'source_excerpts','answer_generated':False,'extracts_rendered':True,
            'message':text,'sources':excerpts,'free_form_legal_advice':False}


class SourceGenerationStage:
    def __init__(self,provider=None,max_attempts=1):
        if type(max_attempts) is not int or max_attempts not in (1,2):
            raise ValueError('Source selection attempts must be 1 or 2')
        self.provider=provider
        self.max_attempts=max_attempts

    def run(self,prepared):
        if prepared.get('status')!='ready_for_source_selection':
            return prepared
        packed=prepared['packed_request']
        if self.provider is None:
            # Explicit offline extractive fallback, never labelled as an LLM answer.
            ids=list(packed['source_map'])[:3]
            return {**render_extracts(ids,packed['source_map']),'llm_called':False,
                    'selection_mode':'retrieval_order_extractive_fallback'}
        if not packed['provider_counter_configured'] or packed['provider_model']!=self.provider.model_id:
            raise ValueError('Configure a matching full-request token counter before calling a provider')
        for attempt in range(1,self.max_attempts+1):
            try:
                response=self.provider.select_sources(copy.deepcopy(packed['messages']),packed['output_reserve'])
            except ProviderUnavailable:
                return {'status':'provider_unavailable','answer_generated':False,'llm_called':False,
                        'provider_attempted':True,'attempt_count':attempt,
                        'message':'Dịch vụ chọn nguồn hiện không khả dụng. Chưa thể trả kết quả từ mô hình.'}
            except InvalidProviderOutput:
                response=None
            try:
                ids=validate_selection(response,packed['source_map'])
            except ValueError:
                continue
            return {**render_extracts(ids,packed['source_map']),'llm_called':True,'attempt_count':attempt,
                    'selection_mode':'provider_source_selection','free_form_legal_advice':False}
        return {'status':'abstain','answer_generated':False,'llm_called':True,'attempt_count':self.max_attempts,
                'message':'Đầu ra không khớp nguồn được cung cấp; chưa thể trả kết quả có căn cứ.',
                'reason':'source_selection_gate_rejected'}
