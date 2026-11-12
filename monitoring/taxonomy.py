"""Structural failure is independent of semantic hallucination labels."""
from collections import Counter

STAGES={'api','router','retrieval','rerank','context','llm','citation','gate','response'}
CODES={'citation_invalid','unsupported_evidence_index','context_mismatch','gate_fail',
       'retrieval_empty','low_confidence','citation_metadata_missing',
       'temporal_metadata_invalid','evidence_not_effective','context_invalid',
       'duplicate_evidence_index','json_invalid','llm_incomplete'}


def summarize(events):
    stages=Counter();violations=Counter();hallucinations=Counter()
    for event in events:
        if event.get('stage') in STAGES:stages[event['stage']]+=1
        metadata=event.get('masked_metadata',{})
        for code in metadata.get('violation_codes',[]):
            if code in CODES:violations[code]+=1
        flag=metadata.get('hallucination_flag')
        if type(flag) is bool:
            hallucinations['true' if flag else 'false']+=1
        else:hallucinations['unassessed']+=1
    return {'by_stage':dict(stages),'structural_violations':dict(violations),
            'hallucination_assessments':dict(hallucinations)}
