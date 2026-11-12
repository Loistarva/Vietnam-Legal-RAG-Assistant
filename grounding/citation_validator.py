"""Structural checks only: PASS does not establish semantic legal correctness.

Accept mapping fixtures or public Pydantic model_dump() objects while the Dev 3
canonical models are pending. Never mutate input or repair model citations.
"""
from copy import deepcopy
from datetime import date
from collections.abc import Mapping
import re

IDENTITY=('chunk_id','document_id','article_id','clause_id','source_title',
          'effective_from','effective_to','text')
LLM_FIELDS={'answer_draft','evidence_indices','model','model_version',
            'prompt_version','done_reason','truncated','latency_ms','token_usage'}


def _mapping(value):
    if hasattr(value,'model_dump'):
        value=value.model_dump(mode='json')
    if not isinstance(value,Mapping):
        raise ValueError('Expected an object')
    return dict(value)


def _date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('Expected ISO date')
    return date.fromisoformat(value)


def _result(codes,answer=None,citations=None,retryable=False):
    codes=list(dict.fromkeys(codes))
    return {'status':'FAIL' if codes else 'PASS',
            'validated_answer':None if codes else answer,
            'citations':[] if codes else (citations or []),
            'violation_codes':codes,'retryable':bool(codes) and retryable,
            'abstention_reason':codes[0] if codes else None}


def validate(context,response):
    """validate(ContextPayload, LLMResponse) -> GroundingResult mapping.

    source_map keys are JSON integer strings (or integers); values must contain
    the complete trusted EvidenceItem. effective_to is an exclusive boundary.
    This function does not retrieve, retry, call a model, log or release a draft.
    """
    try:
        context=_mapping(context)
        evidence=context['evidence']
        source_map=context['source_map']
        as_of=_date(context['as_of_date'])
        if not isinstance(evidence,list) or not isinstance(source_map,Mapping):
            raise ValueError('Invalid context')
        if not evidence:return _result(['retrieval_empty'])
        items={}
        for raw in evidence:
            item=_mapping(raw)
            index=item.get('evidence_index')
            if type(index) is not int or index<1 or index in items:
                return _result(['context_mismatch'])
            items[index]=item
        mapped={}
        for key,value in source_map.items():
            if type(key) is int and key>0:index=key
            elif isinstance(key,str) and key.isascii() and key.isdigit() and str(int(key))==key and int(key)>0:index=int(key)
            else:return _result(['context_mismatch'])
            if index in mapped:return _result(['context_mismatch'])
            mapped[index]=_mapping(value)
        if set(mapped)!=set(items):return _result(['context_mismatch'])
        codes=[]
        for index,item in items.items():
            source=mapped[index]
            if type(source.get('evidence_index')) is not int or source.get('evidence_index')!=index or any(item.get(k)!=source.get(k) for k in IDENTITY):
                codes.append('context_mismatch')
            for candidate in (item,source):
                if any(not isinstance(candidate.get(k),str) or not candidate[k].strip()
                       for k in ('chunk_id','document_id','source_title','text','effective_from')):
                    codes.append('citation_metadata_missing')
                for k in ('article_id','clause_id'):
                    if candidate.get(k) is not None and (not isinstance(candidate[k],str) or not candidate[k].strip()):
                        codes.append('citation_metadata_missing')
                try:
                    start=_date(candidate['effective_from'])
                    end=_date(candidate['effective_to']) if candidate.get('effective_to') else None
                    if end is not None and end<=start:raise ValueError('Invalid interval')
                    if start>as_of or (end is not None and as_of>=end):codes.append('evidence_not_effective')
                except (KeyError,ValueError,TypeError):codes.append('temporal_metadata_invalid')
        if codes:return _result(codes)
    except (KeyError,TypeError,ValueError):
        return _result(['context_invalid'])
    try:
        response=_mapping(response)
        if set(response)-LLM_FIELDS:raise ValueError('Unexpected response fields')
        if not isinstance(response.get('answer_draft'),str) or not response['answer_draft'].strip():
            raise ValueError('Missing draft')
        if type(response.get('truncated')) is not bool or not isinstance(response.get('done_reason'),str) or not response['done_reason']:
            raise ValueError('Missing completion metadata')
        if response['truncated'] or response['done_reason'] not in ('stop','eos','end_turn','completed'):
            return _result(['llm_incomplete'],retryable=True)
        indices=response['evidence_indices']
        if not isinstance(indices,list) or not indices or any(type(i) is not int or i<1 for i in indices):
            return _result(['citation_invalid'],retryable=True)
        if len(indices)!=len(set(indices)):
            return _result(['duplicate_evidence_index'],retryable=True)
        if any(i not in items for i in indices):
            return _result(['unsupported_evidence_index'],retryable=True)
        inline=[int(i) for i in re.findall(r'\[(\d+)\]',response['answer_draft'])]
        if any(i not in items for i in inline):
            return _result(['unsupported_evidence_index'],retryable=True)
        if any(i not in indices for i in inline):
            return _result(['citation_invalid'],retryable=True)
    except (KeyError,TypeError,ValueError):
        return _result(['json_invalid'],retryable=True)
    # All metadata comes from the supplied trusted source map, never model prose.
    citations=[{k:deepcopy(mapped[i].get(k)) for k in ('evidence_index',)+IDENTITY if k!='text'} for i in indices]
    return _result([],response['answer_draft'],citations)
