"""Reproducible Dev 1 synthetic handoff, not a live application E2E run."""
import copy
import json
import tempfile
from pathlib import Path
from statistics import median
from time import perf_counter
from grounding.citation_validator import validate
from .integration import RequestTrace
from .structured_logger import StructuredLogger
from .taxonomy import summarize

ROOT=Path(__file__).resolve().parents[1]


def main():
    source={'evidence_index':1,'chunk_id':'fixture-chunk-1','document_id':'fixture-doc-1',
            'article_id':'fixture-article-1','clause_id':None,'source_title':'Synthetic source',
            'text':'Synthetic fixture only; not an actual legal source.',
            'effective_from':'2020-01-01','effective_to':None}
    context={'query_id':'fixture-week10-pass','as_of_date':'2026-11-12','token_budget':4096,
             'evidence':[source],'source_map':{'1':copy.deepcopy(source)}}
    response={'answer_draft':'Synthetic draft referencing supplied source [1].',
              'evidence_indices':[1],'done_reason':'stop','truncated':False,
              'model':'fixture-no-llm','model_version':'fixture-v1','prompt_version':'fixture-v1',
              'latency_ms':0,'token_usage':None}
    passed=validate(context,response)
    invalid={**response,'evidence_indices':[999]}
    failed=validate(context,invalid)
    assert passed['status']=='PASS' and failed['status']=='FAIL'
    assert failed['validated_answer'] is None and not failed['citations']
    base={'model':'fixture-no-llm','model_version':'fixture-v1','prompt_version':'fixture-v1',
          'config_version':'fixture-v1','corpus_hash':'synthetic-no-real-corpus',
          'route':'LEGAL_IN_SCOPE','as_of_date':context['as_of_date']}
    logs=ROOT/'logs';logs.mkdir(exist_ok=True)
    # These two files contain generated synthetic fixtures only, never user data.
    with (logs/'sample_request.jsonl').open('w',encoding='utf-8',newline='\n') as sink:
        logger=StructuredLogger(sink=sink)
        trace=RequestTrace(context['query_id'],logger.emit,base)
        for stage in ('api','router','retrieval','rerank','context','llm','citation','gate','response'):
            metadata={'grounding_status':'PASS' if stage in ('citation','gate','response') else 'NOT_RUN',
                      'violation_codes':[],'citations':passed['citations'] if stage in ('citation','gate','response') else []}
            assert trace.record(stage,'fixture_completed','OK',metadata)
    with (logs/'sample_gate_fail.jsonl').open('w',encoding='utf-8',newline='\n') as sink:
        trace=RequestTrace('fixture-week10-fail',StructuredLogger(sink=sink).emit,base)
        assert trace.record('citation','validation_completed','FAIL',
                            {'grounding_status':'FAIL','violation_codes':failed['violation_codes']})
        assert trace.record('gate','gate_fail','ABSTAIN',
                            {'grounding_status':'ABSTAIN','violation_codes':['gate_fail']})
    rows=[]
    for name in ('sample_request.jsonl','sample_gate_fail.jsonl'):
        rows.extend(json.loads(line) for line in (logs/name).read_text(encoding='utf-8').splitlines())
    with tempfile.TemporaryDirectory() as directory:
        logger=StructuredLogger(Path(directory)/'benchmark.jsonl');timings=[]
        for _ in range(100):
            start=perf_counter()
            assert logger.emit({'query_id':'fixture-benchmark','stage':'response','event_type':'fixture_completed',
                                'status':'OK','masked_metadata':base})
            timings.append((perf_counter()-start)*1000)
    report={'scope':'Dev 1 synthetic validation and logging handoff only',
            'canonical_contract_status':'PENDING_DEV3_FREEZE','live_api_integrated':False,
            'live_llm_calls':0,'semantic_hallucination_assessed':False,
            'fixtures':{'context':context,'llm_pass':response,'llm_fail':invalid,
                        'grounding_pass':passed,'grounding_fail':failed},
            'log_statistics':summarize(rows),
            'logger_file_benchmark':{'records':100,'p50_ms':median(timings),
                                     'p95_ms':sorted(timings)[94],
                                     'scope':'single-process local file emit only; not API/model latency'}}
    path=ROOT/'reports/week10/dev1_handoff.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='fixtures'},ensure_ascii=True))


if __name__=='__main__':main()
