import math
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'embedding'))
from hybrid_retrieval import BM25Index, HybridRetriever, lexical_tokens, reciprocal_rank_fusion


def chunk(cid, text, status='Còn hiệu lực'):
    return {'chunk_id':cid, 'text':text, 'embed_text':text,
            'metadata':{'validity_status':status, 'source_file':'law.pdf', 'parent_id':'clause'}}


class HybridTests(unittest.TestCase):
    def test_bm25_hand_calculation_and_expiry_statistics(self):
        index=BM25Index([chunk('a','foo foo'), chunk('b','bar'), chunk('expired','foo '*100,'Hết hiệu lực')], analyzer=lexical_tokens)
        result=index.search('foo')
        self.assertEqual([h['chunk_id'] for h in result],['a'])
        # N=2, df=1, dl=2, average length=1.5: IDF=ln(2), TF factor=4.4/3.5.
        self.assertAlmostEqual(result[0]['score'], math.log(2)*4.4/3.5, places=12)
        self.assertEqual(len(index.chunks),2)

    def test_unknown_query_does_not_fill_with_arbitrary_evidence(self):
        index=BM25Index([chunk('a','foo')],analyzer=lexical_tokens)
        self.assertEqual(index.search('unrelated'),[])
        self.assertEqual(index.search('foo foo'), index.search('foo'))

    def test_rrf_uses_ranks_not_scores_and_deduplicates_each_branch(self):
        rankings={'bm25':[{'chunk_id':'a','score':1000},{'chunk_id':'a','score':1},{'chunk_id':'b','score':0}],
                  'dense':[{'chunk_id':'b','score':0.001}]}
        hits=reciprocal_rank_fusion(rankings)
        self.assertEqual(hits[0]['chunk_id'],'b')
        self.assertAlmostEqual(hits[0]['score'],1/62+1/61)
        self.assertAlmostEqual(hits[1]['score'],1/61)
        self.assertEqual(hits[0]['component_ranks'],{'bm25':2,'dense':1})

    def test_rrf_ties_are_deterministic_and_single_branch_preserves_order(self):
        lists={'sparse':[{'chunk_id':'b'},{'chunk_id':'a'}], 'dense':[{'chunk_id':'a'},{'chunk_id':'b'}]}
        self.assertEqual([h['chunk_id'] for h in reciprocal_rank_fusion(lists)],['a','b'])
        self.assertEqual([h['chunk_id'] for h in reciprocal_rank_fusion({'dense':lists['dense']})],['a','b'])

    def test_parameter_validation(self):
        with self.assertRaises(ValueError): BM25Index([chunk('a','foo')],k1=-1)
        with self.assertRaises(ValueError): BM25Index([chunk('a','foo')],b=2)
        with self.assertRaises(ValueError): reciprocal_rank_fusion({},k=0)
        with self.assertRaises(ValueError): BM25Index([chunk('a','foo'),chunk('a','bar')])

    def test_parallel_branches_and_preserved_evidence(self):
        barrier=threading.Barrier(2)
        class Sparse(BM25Index):
            def search(self,*args,**kwargs):
                barrier.wait(timeout=3)
                return super().search(*args,**kwargs)
        class Service:
            def embed_query(self,q):
                barrier.wait(timeout=3)
                return [1.0]
        class Store:
            def search(self,*args,**kwargs): return [{'chunk_id':'a','score':0.5}]
        sparse=Sparse([chunk('a','foo')],analyzer=lexical_tokens)
        output=HybridRetriever(sparse,Service(),Store()).retrieve('foo',top_k=1)
        self.assertEqual(output['hybrid'][0]['metadata']['source_file'],'law.pdf')
        self.assertEqual(output['hybrid'][0]['component_ranks'],{'bm25':1,'dense':1})
        output['hybrid'][0]['metadata']['source_file']='modified'
        self.assertEqual(sparse.chunks['a']['metadata']['source_file'],'law.pdf')

    def test_backend_cannot_leak_ineligible_dense_evidence(self):
        class Service:
            def embed_query(self,q): return [1.0]
        class Store:
            def search(self,*args,**kwargs): return [{'chunk_id':'expired','score':1.0}]
        sparse=BM25Index([chunk('a','foo'),chunk('expired','foo','Hết hiệu lực')],analyzer=lexical_tokens)
        with self.assertRaisesRegex(ValueError,'ineligible'):
            HybridRetriever(sparse,Service(),Store()).retrieve('foo')


if __name__=='__main__': unittest.main()
