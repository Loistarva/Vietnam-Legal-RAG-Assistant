"""Allowlisted JSONL logging; failures never propagate into business results."""
import json
import math
import re
import sys
from datetime import datetime,timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4
from .pii_masker import mask
from .taxonomy import CODES, STAGES

METADATA={'prompt_version','model','model_version','config_version','corpus_hash',
          'retrieval_config_version','threshold_config_version','route','latency_ms',
          'status','citations','grounding_status','violation_codes','error_code',
          'done_reason','truncated','token_usage','hallucination_flag',
          'hallucination_source','query_hash','prompt_hash','as_of_date',
          'status_ttfb_ms','verified_answer_latency_ms','total_latency_ms'}
CITATION_FIELDS={'evidence_index','chunk_id','document_id','article_id','clause_id',
                 'source_title','effective_from','effective_to'}
ID=re.compile(r'^[A-Za-z0-9_-]{1,128}$')
LABEL=re.compile(r'^[A-Za-z0-9_.:-]{1,80}$')


class StructuredLogger:
    def __init__(self,path=None,*,sink=None,enabled=True,secrets=(),approved_verifiers=(),error_sink=None):
        self.path=Path(path) if path is not None else None
        self.sink=sink
        self.enabled=enabled
        self.secrets=tuple(secrets)
        self.approved_verifiers=set(approved_verifiers)
        self.error_sink=error_sink if error_sink is not None else sys.stderr
        self.lock=Lock()

    def _event(self,event):
        if hasattr(event,'model_dump'):event=event.model_dump(mode='json')
        if not isinstance(event,dict):raise ValueError('Invalid log event')
        query_id=event.get('query_id')
        if not isinstance(query_id,str) or not ID.fullmatch(query_id):raise ValueError('Invalid correlation ID')
        if mask(query_id,self.secrets)!=query_id:raise ValueError('Correlation ID must be opaque')
        stage=event.get('stage')
        if stage not in STAGES:raise ValueError('Invalid stage')
        for field in ('event_type','status'):
            if not isinstance(event.get(field),str) or not LABEL.fullmatch(event[field]):raise ValueError('Invalid label')
            if mask(event[field],self.secrets)!=event[field]:raise ValueError('Label contains private data')
        duration=event.get('duration_ms')
        if duration is not None and (type(duration) not in (int,float) or not math.isfinite(duration) or duration<0):
            raise ValueError('Invalid duration')
        metadata=event.get('masked_metadata',{})
        if not isinstance(metadata,dict):raise ValueError('Invalid metadata')
        metadata={k:v for k,v in metadata.items() if k in METADATA}
        if 'citations' in metadata:
            if not isinstance(metadata['citations'],list):raise ValueError('Invalid citations')
            metadata['citations']=[{k:v for k,v in c.items() if k in CITATION_FIELDS}
                                   for c in metadata['citations'] if isinstance(c,dict)]
        if 'violation_codes' in metadata:
            if not isinstance(metadata['violation_codes'],list):raise ValueError('Invalid codes')
            metadata['violation_codes']=[c for c in metadata['violation_codes'] if isinstance(c,str) and c in CODES]
        flag=metadata.get('hallucination_flag')
        source=metadata.get('hallucination_source')
        allowed=source=='human_rubric' or (isinstance(source,str) and source.startswith('verifier:') and source[9:] in self.approved_verifiers)
        if type(flag) is not bool or not allowed:
            metadata['hallucination_flag']=None
            metadata['hallucination_source']=None
        result={'event_id':str(uuid4()),'query_id':query_id,'stage':stage,
                'event_type':event['event_type'],'status':event['status'],
                'timestamp':datetime.now(timezone.utc).isoformat(),
                'duration_ms':duration,'masked_metadata':mask(metadata,self.secrets)}
        return result

    def emit(self,event):
        if not self.enabled:return False
        try:
            # Validate/serialize completely before writing a single JSONL line.
            line=json.dumps(self._event(event),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
            with self.lock:
                if self.sink is not None:
                    self.sink.write(line)
                    self.sink.flush()
                elif self.path is not None:
                    self.path.parent.mkdir(parents=True,exist_ok=True)
                    with self.path.open('a',encoding='utf-8',newline='\n') as stream:stream.write(line)
                else:raise ValueError('Configure a JSONL sink')
            return True
        except Exception:
            try:self.error_sink.write('structured_log_write_failed\n')
            except Exception:pass
            return False

    log=emit
