import math
import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'embedding'))
from retrieval_policy import RetrievalPolicy, policy_from_query
from hybrid_retrieval import BM25Index, HybridRetriever, lexical_tokens
from legal_context import ParentContextResolver, LegalSearchPipeline


def chunk(cid,status,number):
    return {'chunk_id':cid,'text':'foo foo','embed_text':'foo foo',
            'metadata':{'validity_status':status,'document_number':number,'document_type':'Luật','issue_date':'2014-06-19'}}


class PolicyTests(unittest.TestCase):
    def test_strict_current_and_explicit_research_modes(self):
        for status in ['Còn hiệu lực','Hết hiệu lực','Hết hiệu lực một phần','Không xác định','Hết hiệu lực toàn bộ']:
            with self.subTest(status=status):
                self.assertEqual(RetrievalPolicy().matches({'validity_status':status}),status=='Còn hiệu lực')
                self.assertEqual(RetrievalPolicy(validity_mode='exclude_expired').matches({'validity_status':status}),status not in ['Hết hiệu lực','Hết hiệu lực toàn bộ'])

    def test_query_references_and_publication_year(self):
        p=policy_from_query('Nghị định số 207/2025/ND-CP ban hành năm 2025 quy định gì?')
        self.assertEqual(p.document_numbers,('207/2025/NĐ-CP',))
        self.assertEqual(p.document_types,('Nghị định',))
        self.assertEqual(p.issue_year,2025)
        generic=policy_from_query('Theo pháp luật tôi 20 tuổi và kết hôn năm 2014 thì sao?')
        self.assertFalse(generic.document_types)
        self.assertIsNone(generic.issue_year)
        self.assertFalse(RetrievalPolicy(issue_year=2014).matches({'validity_status':'Còn hiệu lực','issue_date':'2014-02-30'}))
        self.assertFalse(policy_from_query('Ai quyết định việc sử dụng tài sản chung?').document_types)
        self.assertFalse(policy_from_query('Theo pháp luật hôn nhân và gia đình thì sao?').document_types)
        self.assertEqual(policy_from_query('Quyết định số 12/2020/QĐ-TTg quy định gì?').document_types,('Quyết định',))

    def test_invalid_policy_and_collection_immutability(self):
        with self.assertRaises(ValueError): RetrievalPolicy(issue_year=True)
        with self.assertRaises(ValueError): RetrievalPolicy(validity_mode='historical')
        with self.assertRaises(ValueError): RetrievalPolicy(document_numbers='52/2014/QH13')
        numbers=['52/2014/QH13'];p=RetrievalPolicy(document_numbers=numbers)
        numbers.append('x');self.assertEqual(p.document_numbers,('52/2014/QH13',))

    def test_filtered_bm25_statistics_are_computed_before_ranking(self):
        index=BM25Index([chunk('a','Còn hiệu lực','52/2014/QH13'),chunk('b','Không xác định','99/2014/QH13')],analyzer=lexical_tokens)
        hits=index.search('foo',policy=RetrievalPolicy(document_numbers=('52/2014/QH13',)))
        self.assertEqual([h['chunk_id'] for h in hits],['a'])
        self.assertAlmostEqual(hits[0]['score'],math.log(4/3)*1.375)

    def test_same_allowlist_reaches_dense_and_zero_matches_skip_inference(self):
        chunks=[chunk('a','Còn hiệu lực','52/2014/QH13'),chunk('b','Không xác định','99/2014/QH13')]
        class Service:
            calls=0
            def embed_query(self,q): self.calls+=1;return [1]
        class Store:
            def search(self,vector,n,**kwargs):
                self.allowed=kwargs['allowed_chunk_ids'];return [{'chunk_id':cid,'score':1} for cid in self.allowed]
        service,store=Service(),Store()
        engine=HybridRetriever(BM25Index(chunks,analyzer=lexical_tokens),service,store)
        out=engine.retrieve('foo',policy=RetrievalPolicy())
        self.assertEqual(store.allowed,['a']);self.assertEqual(out['hybrid'][0]['chunk_id'],'a')
        empty=engine.retrieve('foo',policy=RetrievalPolicy(document_numbers=('missing',)))
        self.assertEqual(empty['hybrid'],[]);self.assertEqual(service.calls,1)

    def test_backend_cannot_ignore_document_filter(self):
        class Service:
            def embed_query(self,q): return [1]
        class Store:
            def search(self,*args,**kwargs): return [{'chunk_id':'b','score':1}]
        index=BM25Index([chunk('a','Còn hiệu lực','52/2014/QH13'),chunk('b','Còn hiệu lực','99/2014/QH13')],analyzer=lexical_tokens)
        with self.assertRaisesRegex(ValueError,'ineligible'):
            HybridRetriever(index,Service(),Store()).retrieve('foo',policy=RetrievalPolicy(document_numbers=('52/2014/QH13',)))


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolver=ParentContextResolver(ROOT/'data/structure_v2/documents',ROOT/'data/structure_v2/embedding/priority_bkai_chunks.json')

    def test_numbered_and_unnumbered_citations(self):
        numbered=self.resolver.resolve({'chunk_id':'L01_art_8_clause_1_chunk_1'})
        self.assertEqual(numbered['citation']['clause_number'],'1')
        self.assertIn('Khoản 1',numbered['citation']['label'])
        unnumbered=self.resolver.resolve({'chunk_id':'L01_art_20_clause_1_chunk_1'})
        self.assertIsNone(unnumbered['citation']['clause_number'])
        self.assertNotIn('Khoản',unnumbered['citation']['label'])

    def test_split_child_restores_full_clause_and_sibling_context(self):
        candidate=next(c for c in self.resolver.chunks.values() if '_part' in c['chunk_id'] and c['metadata']['document_id']=='ND02')
        out=self.resolver.resolve(candidate)
        doc,article,clause=self.resolver.clauses[out['clause_id']]
        self.assertEqual(out['parent_clause_text'],clause['clause_text'])
        self.assertGreater(len(out['parent_clause_text']),len(candidate['text']))
        for sibling in article['clauses']: self.assertIn(sibling['clause_text'],out['article_text'])

    def test_forged_source_and_unknown_ids_are_rejected(self):
        hit=copy.deepcopy(self.resolver.chunks['L01_art_8_clause_1_chunk_1'])
        hit['metadata']['source_url']='https://invalid.example/'
        with self.assertRaisesRegex(ValueError,'canonical'): self.resolver.resolve(hit)
        with self.assertRaisesRegex(ValueError,'Unknown'): self.resolver.resolve({'chunk_id':'missing'})

    def test_partial_validity_requires_explicit_research_policy(self):
        hit={'chunk_id':'ND01_art_67_clause_1_chunk_1'}
        with self.assertRaisesRegex(ValueError,'excluded'): self.resolver.resolve(hit)
        out=self.resolver.resolve(hit,RetrievalPolicy(validity_mode='exclude_expired'))
        self.assertNotIn('Phụ lục',out['article_text'])
        self.assertIsNone(out['citation']['clause_number'])

    def test_pipeline_deduplicates_parent_articles(self):
        resolver=self.resolver
        class Engine:
            def retrieve(self,q,top_k,policy):
                self.policy=policy
                return {'hybrid':[copy.deepcopy(resolver.chunks[cid]) for cid in ['L01_art_8_clause_1_chunk_1','L01_art_8_clause_2_chunk_1']]}
        engine=Engine();out=LegalSearchPipeline(engine,resolver).search('Điều kiện kết hôn theo Luật số 52/2014/QH13?')
        self.assertEqual(engine.policy.validity_mode,'current_only')
        self.assertEqual(len(out['parent_contexts']),1)
        self.assertEqual(out['parent_contexts'][0]['document_number'],'52/2014/QH13')
        self.assertEqual(len(out['evidence']),2)
        self.assertFalse(out['answer_generated'])


if __name__=='__main__': unittest.main()
