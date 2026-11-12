"""Offline live-evidence validation; no real generation provider/API is called."""
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'embedding'))
from vector_store import load_chunks, EmbeddingService, VectorStore
from evaluate_hybrid_dev import digest, verify_index
from hybrid_retrieval import BM25Index, HybridRetriever
from legal_context import ParentContextResolver, LegalSearchPipeline
from .controller import LegalAgent
from .context_packing import ContextPacker
from .source_generation import SourceGenerationStage


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
        resolver=ParentContextResolver(ROOT/'data/structure_v2/documents',path)
        pipeline=LegalSearchPipeline(HybridRetriever(BM25Index(chunks),service,store),resolver)
        class CountedSearch:
            calls=0
            def search(self,q):
                self.calls+=1
                return pipeline.search(q)
        search=CountedSearch()
        def counter(messages):
            # Exact for this serialized proxy request, NOT a generation-model counter.
            text=json.dumps(messages,ensure_ascii=False,separators=(',',':'))
            return len(service.model.tokenizer.encode(text,truncation=False))
        packer=ContextPacker(counter,'BAAI/bge-m3 serialized-request proxy (not a generation tokenizer)',
                              context_window=4096,output_reserve=512,provider_model=None)
        agent=LegalAgent(search,packer,[d['metadata']['document_number'] for d in resolver.documents.values()])
        generation=SourceGenerationStage(provider=None)
        cases=[('greeting','Xin chào','general',False),
               ('ambiguous','Ly hôn','clarify',False),
               ('out_of_scope','Thuế thu nhập cá nhân tính thế nào?','out_of_scope',False),
               ('historical','Luật hôn nhân còn hiệu lực năm 2010 không?','clarify',False),
               ('legal','Điều kiện kết hôn theo Luật số 52/2014/QH13?','ready_for_source_selection',True),
               ('no_eligible','Nghị quyết số 01/2024/NQ-HĐTP quy định gì?','clarify',True),
               ('oversized','Điều kiện kết hôn? '+'nội dung '*5000,'clarify',False)]
        rows=[]
        for name,query,expected,searched in cases:
            previous_calls=search.calls
            prepared=agent.prepare(query)
            if prepared['status']!=expected or bool(search.calls-previous_calls)!=searched:
                raise ValueError(f'Incorrect route/inference behavior: {name}')
            rendered=generation.run(prepared)
            if rendered.get('llm_called') or rendered.get('answer_generated'):
                raise ValueError('Offline validation must not call or claim a generative LLM')
            packed=prepared.get('packed_request')
            if packed:
                if packed['input_token_count']>packed['input_budget'] or packed['provider_counter_configured']:
                    raise ValueError('Budget/provider configuration mismatch')
                original=json.loads(packed['messages'][1]['content'])
                if original['sources']!=packed['sources']:
                    raise ValueError('Prompt/source map drift')
            rows.append({'case':name,'query':query if name!='oversized' else '[oversized synthetic query omitted]',
                         'prepared':prepared,'rendered':rendered})
            print(name,prepared['status'],rendered['status'],flush=True)
        output=ROOT/'data/structure_v2/agent';output.mkdir(parents=True,exist_ok=True)
        report={'dataset_sha256':digest(path),'cases_passed':True,'case_count':len(rows),
                'real_llm_provider':None,'real_llm_calls':0,'generation_tokenizer_configured':False,
                'counter_scope':'offline BGE proxy; not permission to call a generation provider',
                'test_evaluated':False,'retrieval_calls':search.calls,'cases':rows}
        with (output/'offline_flow.json').open('w',encoding='utf-8',newline='\n') as stream:
            stream.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    finally:
        store.client.close()


if __name__=='__main__': main()
