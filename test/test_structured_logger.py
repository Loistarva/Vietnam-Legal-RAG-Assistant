import copy
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from monitoring.structured_logger import StructuredLogger
from monitoring.taxonomy import summarize,STAGES
from monitoring.integration import RequestTrace
from grounding.citation_validator import validate
from test.test_citation_validator import fixture


def event(stage='citation',**metadata):
    return {'query_id':'synthetic-q1','stage':stage,'event_type':'stage_completed',
            'status':'OK','duration_ms':1,'masked_metadata':metadata}


class LoggerTests(unittest.TestCase):
    def setUp(self):self.sink=io.StringIO();self.errors=io.StringIO();self.logger=StructuredLogger(sink=self.sink,error_sink=self.errors)
    def rows(self):return [json.loads(line) for line in self.sink.getvalue().splitlines()]

    def test_all_stages_one_correlation_id(self):
        for stage in sorted(STAGES):self.assertTrue(self.logger.emit(event(stage)))
        rows=self.rows()
        self.assertEqual(len(rows),9)
        self.assertEqual({row['query_id'] for row in rows},{'synthetic-q1'})
        self.assertEqual(len({row['event_id'] for row in rows}),9)
        self.assertTrue(all(datetime.fromisoformat(row['timestamp']).utcoffset().total_seconds()==0 for row in rows))

    def test_default_drops_raw_query_prompt_headers_and_extra_fields(self):
        raw=event(model='fake',query='raw private query',prompt='raw private prompt',
                  error='raw private error',headers={'Authorization':'raw private bearer'},
                  citations=[{'chunk_id':'c1','text':'raw private source','source_title':'sample@example.test'}])
        raw['query']='raw private top';before=copy.deepcopy(raw)
        self.assertTrue(self.logger.emit(raw))
        output=self.sink.getvalue()
        self.assertNotIn('raw private',output)
        self.assertNotIn('sample@example.test',output)
        self.assertEqual(raw,before)

    def test_custom_secret_and_nested_pii(self):
        logger=StructuredLogger(sink=self.sink,secrets=('opaque-fixture-secret',))
        self.assertTrue(logger.emit(event(model='opaque-fixture-secret',citations=[{'source_title':'0912345678'}])))
        self.assertNotIn('opaque-fixture-secret',self.sink.getvalue())
        self.assertNotIn('0912345678',self.sink.getvalue())

    def test_token_usage_counts_are_not_treated_as_secret_tokens(self):
        self.logger.emit(event(token_usage={'input_tokens':123,'output_tokens':45,'total_tokens':168},
                               corpus_hash='abcdef123456789012abcdef'))
        metadata=self.rows()[0]['masked_metadata']
        self.assertEqual(metadata['token_usage'],{'input_tokens':123,'output_tokens':45,'total_tokens':168})
        self.assertEqual(metadata['corpus_hash'],'abcdef123456789012abcdef')

    def test_structural_failures_do_not_imply_hallucination(self):
        self.logger.emit(event(violation_codes=['citation_invalid'],hallucination_flag=True,hallucination_source='citation_validator'))
        metadata=self.rows()[0]['masked_metadata']
        self.assertIsNone(metadata['hallucination_flag'])
        self.assertIsNone(metadata['hallucination_source'])

    def test_rubric_and_approved_verifier_provenance(self):
        for source in ['human_rubric','verifier:reviewed-v1','verifier:unapproved']:
            logger=StructuredLogger(sink=self.sink,approved_verifiers=('reviewed-v1',))
            logger.emit(event(hallucination_flag=False,hallucination_source=source))
        self.assertEqual([r['masked_metadata']['hallucination_flag'] for r in self.rows()],[False,False,None])

    def test_sink_failure_is_nonfatal_and_error_is_safe(self):
        class Broken:
            def write(self,line):raise OSError('credential-secret')
        logger=StructuredLogger(sink=Broken(),error_sink=self.errors)
        self.assertFalse(logger.emit(event()))
        self.assertEqual(self.errors.getvalue(),'structured_log_write_failed\n')

    def test_disabled_and_invalid_events_do_not_write(self):
        self.assertFalse(StructuredLogger(sink=self.sink,enabled=False).emit(event()))
        for changes in [{'stage':'invalid'},{'query_id':'person@example.test'},{'duration_ms':float('nan')},
                        {'status':'raw multiline\nsecret'},{'masked_metadata':{'latency_ms':float('inf')}}]:
            value=event();value.update(changes)
            self.assertFalse(self.logger.emit(value))
        self.assertEqual(self.sink.getvalue(),'')
        self.assertNotIn('secret',self.errors.getvalue())

    def test_file_sink_and_concurrent_line_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'logs/test.jsonl';logger=StructuredLogger(path)
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertTrue(all(pool.map(lambda _:logger.emit(event()),range(40))))
            rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows),40)

    def test_taxonomy_separates_structural_and_rubric_counts(self):
        self.logger.emit(event(violation_codes=['context_mismatch']))
        self.logger.emit(event(hallucination_flag=True,hallucination_source='human_rubric'))
        result=summarize(self.rows())
        self.assertEqual(result['structural_violations'],{'context_mismatch':1})
        self.assertEqual(result['hallucination_assessments'],{'unassessed':1,'true':1})

    def test_timing_callback_preserves_result_and_business_exception(self):
        trace=RequestTrace('synthetic-q1',self.logger.emit)
        result={'answer':'unchanged'}
        with trace.stage('retrieval'):returned=result
        self.assertIs(returned,result)
        with self.assertRaisesRegex(ValueError,'private business error'):
            with trace.stage('llm'):raise ValueError('private business error')
        self.assertNotIn('private business error',self.sink.getvalue())
        self.assertTrue(all(row['duration_ms']>=0 for row in self.rows() if row['duration_ms'] is not None))

    def test_broken_callback_does_not_change_validator_result(self):
        def broken(event):raise RuntimeError('secret')
        trace=RequestTrace('synthetic-q1',broken)
        context,response=fixture();expected=validate(context,response)
        with trace.stage('citation'):actual=validate(context,response)
        self.assertEqual(expected,actual)

    def test_fixture_validator_callback_handoff_pass_and_fail(self):
        trace=RequestTrace('synthetic-q1',self.logger.emit)
        context,response=fixture()
        for indices,status in [([1],'PASS'),([999],'FAIL')]:
            response['evidence_indices']=indices
            result=validate(context,response)
            trace.record('citation','validation_completed',result['status'],
                         {'violation_codes':result['violation_codes'],'grounding_status':result['status'],
                          'citations':result['citations']})
            self.assertEqual(result['status'],status)
            if status=='FAIL':self.assertIsNone(result['validated_answer'])
        self.assertEqual([r['masked_metadata']['grounding_status'] for r in self.rows()],['PASS','FAIL'])
