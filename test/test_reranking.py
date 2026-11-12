import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'embedding'))
from reranking import CrossEncoderReranker, apply_scores
from hybrid_retrieval import BM25Index, HybridRetriever, lexical_tokens


class RerankingTests(unittest.TestCase):
    def test_non_integer_limits_fail_before_inference(self):
        for value in [True,1.5,float('nan'),0]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                apply_scores([],[],top_k=value)
        with self.assertRaises(ValueError): CrossEncoderReranker(batch_size=1.5)
        with self.assertRaises(ValueError): CrossEncoderReranker(max_tokens=True)
    def test_score_sort_preserves_source_and_does_not_mutate_input(self):
        hits=[{'chunk_id':'a','score':0.03,'metadata':{'source_file':'law.pdf'}},
              {'chunk_id':'b','score':0.02,'metadata':{'source_file':'other.pdf'}}]
        before=copy.deepcopy(hits)
        out=apply_scores(hits,[-4,2],1)
        self.assertEqual(out[0]['chunk_id'],'b')
        self.assertEqual(out[0]['rrf_score'],0.02)
        self.assertEqual(out[0]['score_kind'],'reranker_logit')
        self.assertEqual(out[0]['pre_rerank_rank'],2)
        out[0]['metadata']['source_file']='changed'
        self.assertEqual(hits,before)

    def test_ties_preserve_input_ranking(self):
        hits=[{'chunk_id':'z','score':1},{'chunk_id':'a','score':0.5}]
        self.assertEqual([h['chunk_id'] for h in apply_scores(hits,[0,0])],['z','a'])

    def test_bad_scores_and_duplicate_ids_fail(self):
        hits=[{'chunk_id':'a','score':1}]
        for scores in [[],[float('nan')],[float('inf')]]:
            with self.subTest(scores=scores), self.assertRaises(ValueError): apply_scores(hits,scores)
        with self.assertRaises(ValueError): apply_scores(hits*2,[1,2])

    def test_pair_overflow_fails_before_any_model_inference(self):
        class Tokenizer:
            def __call__(self,*args,**kwargs):
                self.kwargs=kwargs
                return {'length':[513]}
        ranker=CrossEncoderReranker.__new__(CrossEncoderReranker)
        ranker.tokenizer,ranker.max_tokens=Tokenizer(),512
        with self.assertRaisesRegex(ValueError,'do not silently truncate'):
            ranker.rerank('query',[{'chunk_id':'a','text':'full legal text','score':1}])
        self.assertFalse(ranker.tokenizer.kwargs['truncation'])

    def test_empty_pool_does_not_fabricate_results(self):
        ranker=CrossEncoderReranker.__new__(CrossEncoderReranker)
        self.assertEqual(ranker.rerank('query',[]),[])
        self.assertEqual(ranker.last_seconds,0)

    def test_hybrid_reranks_beyond_top10_and_keeps_original_result(self):
        chunks=[{'chunk_id':f'a{i:02d}','text':'foo','embed_text':'foo',
                 'metadata':{'validity_status':'Còn hiệu lực','source_file':'law.pdf'}} for i in range(24)]
        class Service:
            def embed_query(self,q): return [1]
        class Store:
            def search(self,*args,**kwargs): return [{'chunk_id':c['chunk_id'],'score':1-i/24} for i,c in enumerate(chunks)]
        class Ranker:
            last_seconds=0.01
            def rerank(self,q,hits,top_k):
                self.received=len(hits)
                return apply_scores(hits,list(range(len(hits))),top_k)
        sparse=BM25Index(chunks,analyzer=lexical_tokens)
        ranker=Ranker()
        out=HybridRetriever(sparse,Service(),Store(),reranker=ranker).retrieve('foo')
        self.assertEqual(ranker.received,24)
        self.assertEqual(out['hybrid'][0]['chunk_id'],'a00')
        self.assertEqual(out['reranked'][0]['chunk_id'],'a23')
        self.assertEqual(len(out['reranked']),10)

    def test_disabled_reranker_keeps_smaller_candidate_configuration_compatible(self):
        class Service:
            def embed_query(self,q): return [1]
        class Store:
            def search(self,*args,**kwargs): return [{'chunk_id':'a','score':1}]
        sparse=BM25Index([{'chunk_id':'a','text':'foo','embed_text':'foo','metadata':{}}],analyzer=lexical_tokens)
        out=HybridRetriever(sparse,Service(),Store(),candidate_k=10).retrieve('foo')
        self.assertNotIn('reranked',out)
        self.assertEqual(out['hybrid'][0]['chunk_id'],'a')


if __name__=='__main__': unittest.main()
