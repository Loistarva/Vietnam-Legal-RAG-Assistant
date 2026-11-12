"""Single-process, serialized access to the existing local retrieval index."""
import json
import os
import sys
from pathlib import Path
from threading import Lock
from dataclasses import asdict
from agent.routing import route_query
from agent.provider_config import ProviderConfig
from agent.local_provider import build_provider
from agent.context_packing import ContextPacker
from agent.controller import LegalAgent
from agent.source_generation import SourceGenerationStage

ROOT=Path(__file__).resolve().parents[1]


class AgentService:
    def __init__(self):
        self.lock=Lock()
        self.agent=None
        self.store=None
        self.provider=None
        self.known_numbers=[json.loads(p.read_text(encoding='utf-8'))['metadata']['document_number']
                            for p in (ROOT/'data/structure_v2/documents').glob('*.json')]

    def initialize(self):
        sys.path.insert(0,str(ROOT/'embedding'))
        from vector_store import load_chunks, EmbeddingService, VectorStore
        from evaluate_hybrid_dev import digest, verify_index
        from hybrid_retrieval import BM25Index, HybridRetriever
        from legal_context import ParentContextResolver, LegalSearchPipeline
        os.environ.setdefault('HF_HOME',str(ROOT/'.venv-embedding/hf-cache'))
        os.environ.setdefault('HF_HUB_OFFLINE','1')
        config=ProviderConfig.from_environment()
        provider=build_provider(config)
        path=ROOT/'data/structure_v2/embedding/priority_bkai_chunks.json'
        baseline=json.loads((ROOT/'data/structure_v2/benchmark/bge_m3_dev.json').read_text(encoding='utf-8'))
        if baseline['chunk_file_sha256']!=digest(path):raise ValueError('Corpus drift')
        chunks=load_chunks(path)
        embedding=EmbeddingService('BAAI/bge-m3',device='cpu')
        store=VectorStore(baseline['collection'],embedding.dimension,
                          local_path=ROOT/'qdrant_data/structure_v2/bge_m3',create_if_missing=False)
        try:
            verify_index(store,chunks)
            resolver=ParentContextResolver(ROOT/'data/structure_v2/documents',path)
            pipeline=LegalSearchPipeline(HybridRetriever(BM25Index(chunks),embedding,store),resolver)
            def proxy(messages):
                return len(embedding.model.tokenizer.encode(json.dumps(messages,ensure_ascii=False),truncation=False))
            packer=ContextPacker(provider.count_messages if provider else proxy,
                                'provider full-request counter' if provider else 'offline BGE proxy',
                                config.context_window,config.output_reserve,provider.model_id if provider else None)
            self.agent=LegalAgent(pipeline,packer,self.known_numbers)
            self.generation=SourceGenerationStage(provider,config.max_attempts)
            self.store,self.provider=store,provider
        except Exception:
            store.client.close()
            if provider and hasattr(provider,'client'):provider.client.close()
            raise

    def chat(self,query):
        decision=route_query(query,self.known_numbers)
        if decision.kind!='legal':
            return {'status':decision.kind,'route':asdict(decision),'message':decision.message,
                    'retrieval_called':False,'llm_called':False,'answer_generated':False}
        with self.lock:
            if self.agent is None:self.initialize()
            prepared=self.agent.prepare(query)
            result=self.generation.run(prepared)
            return {**{k:v for k,v in prepared.items() if k!='packed_request'},**result}

    def close(self):
        with self.lock:
            if self.store:self.store.client.close()
            if self.provider and hasattr(self.provider,'client'):self.provider.client.close()
            self.agent=self.store=self.provider=None
