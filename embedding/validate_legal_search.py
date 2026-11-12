"""Live read-only smoke checks for strict filtered search and parent evidence.

No Dev/Test metrics are changed. Reranking is disabled to isolate metadata and
context behavior and avoid repeating the earlier expensive scoring experiment.
"""
import json
import os
from pathlib import Path

from evaluate_hybrid_dev import digest, verify_index
from hybrid_retrieval import BM25Index, HybridRetriever
from legal_context import ParentContextResolver, LegalSearchPipeline
from retrieval_policy import RetrievalPolicy
from vector_store import EmbeddingService, VectorStore, load_chunks

ROOT=Path(__file__).resolve().parents[1]


def main():
    os.environ.setdefault('HF_HOME',str(ROOT/'.venv-embedding/hf-cache'))
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    path=ROOT/'data/structure_v2/embedding/priority_bkai_chunks.json'
    chunks=load_chunks(path)
    baseline=json.loads((ROOT/'data/structure_v2/benchmark/bge_m3_dev.json').read_text(encoding='utf-8'))
    if baseline['chunk_file_sha256']!=digest(path): raise ValueError('Corpus drift')
    service=EmbeddingService('BAAI/bge-m3',device='cpu')
    store=VectorStore(baseline['collection'],service.dimension,
                      local_path=ROOT/'qdrant_data/structure_v2/bge_m3',create_if_missing=False)
    try:
        verify_index(store,chunks)
        sparse=BM25Index(chunks)
        resolver=ParentContextResolver(ROOT/'data/structure_v2/documents',path)
        pipeline=LegalSearchPipeline(HybridRetriever(sparse,service,store),resolver)
        cases=[
            ('law_reference','Điều kiện kết hôn theo Luật số 52/2014/QH13?',{'L01'}),
            ('decree_reference','Sinh con bằng kỹ thuật hỗ trợ sinh sản theo Nghị định số 207/2025/NĐ-CP?',{'ND02'}),
            ('publication_year','Nghị định ban hành năm 2025 quy định về sinh con thế nào?',{'ND02'}),
            ('expired_document','Nghị định số 10/2015/NĐ-CP quy định gì?',set()),
            ('unknown_status','Nghị quyết số 01/2024/NQ-HĐTP hướng dẫn gì?',set()),
            ('partial_status','Nghị định số 126/2014/NĐ-CP hướng dẫn gì?',set()),
            ('generic_verb','Ai quyết định việc sử dụng tài sản chung?',None),
        ]
        rows=[]
        for name,query,expected in cases:
            result=pipeline.search(query,top_k=3)
            docs={h['metadata']['document_id'] for h in result['evidence']}
            if expected is not None and docs!=expected: raise ValueError(f'Unexpected scoped documents in {name}: {docs}')
            if expected is None and (not docs or result['applied_policy']['document_types']):
                raise ValueError('Generic decision verb was treated as a document-type filter')
            if any(h['metadata']['validity_status']!='Còn hiệu lực' for h in result['evidence']):
                raise ValueError('Strict status filter leaked evidence')
            for hit in result['evidence']:
                if hit['context']['citation']['document_number']!=hit['metadata']['document_number']:
                    raise ValueError('Citation identity mismatch')
            rows.append({'case':name,'query':query,'result':result})
            print(name,result['status'],sorted(docs),flush=True)
        # Prove the actual backend's empty allowlist returns no global fallback.
        if store.search([0.0]*service.dimension,allowed_chunk_ids=[]):
            raise ValueError('Empty allowlist broadened the backend query')
        report={'dataset_sha256':digest(path),'indexed_count':len(chunks),
                'legacy_research_eligible_count':len(sparse.chunks),
                'strict_current_eligible_count':sum(RetrievalPolicy().matches(c['metadata']) for c in chunks),
                'case_count':len(rows),'cases_passed':True,'empty_backend_allowlist_passed':True,
                'reranker_enabled':False,'answer_generated':False,'test_evaluated':False,'cases':rows}
        output=ROOT/'data/structure_v2/context_policy';output.mkdir(parents=True,exist_ok=True)
        with (output/'smoke_results.json').open('w',encoding='utf-8',newline='\n') as stream:
            stream.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    finally:
        store.client.close()


if __name__=='__main__': main()
