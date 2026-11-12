"""Evaluate local BM25, BGE dense and RRF on the frozen structure-v2 Dev set.

Uses the existing Qdrant index read-only after checking every ID/text/payload.
Does not re-embed documents, tune on labels or evaluate the Test split.
"""
import hashlib
import json
import os
import time
from importlib.metadata import version
from pathlib import Path

from hybrid_retrieval import BM25Index, HybridRetriever
from vector_store import EmbeddingService, VectorStore, load_chunks

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structure_v2/embedding'
OUTPUT = ROOT / 'data/structure_v2/hybrid'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(hits, relevant):
    ids = [h['chunk_id'] for h in hits]
    rank = next((i for i, cid in enumerate(ids[:10], 1) if cid in relevant), None)
    return {'recall_at_5': len(set(ids[:5]) & relevant) / len(relevant),
            'mrr_at_10': 1 / rank if rank else 0.0,
            'first_relevant_rank': rank, 'ranked_chunk_ids': ids[:10]}


def verify_index(store, chunks):
    expected = {c['chunk_id']: c for c in chunks}
    seen, offset = set(), None
    while True:
        points, offset = store.client.scroll(store.collection_name, limit=256, offset=offset,
                                             with_payload=True, with_vectors=False)
        for point in points:
            payload = point.payload
            cid = payload.get('chunk_id')
            if cid in seen or cid not in expected:
                raise ValueError(f'Unexpected/duplicate indexed ID: {cid}')
            source = expected[cid]
            if payload.get('text') != source['text'] or payload.get('metadata') != source['metadata']:
                raise ValueError(f'Index payload drift: {cid}')
            seen.add(cid)
        if offset is None:
            break
    if seen != set(expected):
        raise ValueError('Existing dense index does not cover the frozen corpus')
    return len(seen)


def main():
    os.environ.setdefault('HF_HOME', str(ROOT / '.venv-embedding/hf-cache'))
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    corpus_path = DATA / 'priority_bkai_chunks.json'
    labels_path = DATA / 'priority_bkai_dev.draft.json'
    chunks = load_chunks(corpus_path)
    judgments = json.loads(labels_path.read_text(encoding='utf-8'))
    frozen = json.loads((ROOT / 'data/structure_v2/benchmark/bge_m3_dev.json').read_text(encoding='utf-8'))
    if frozen['chunk_file_sha256'] != digest(corpus_path) or frozen['ground_truth_sha256'] != digest(labels_path):
        raise ValueError('Dense baseline input hashes differ')
    if len(judgments) != 10 or any(q['split'] != 'dev' for q in judgments):
        raise ValueError('Only the ten frozen Dev questions are allowed')
    known = {c['chunk_id'] for c in chunks}
    if any(not q['relevant_chunk_ids'] or not set(q['relevant_chunk_ids']) <= known for q in judgments):
        raise ValueError('Invalid relevance labels')
    cache_ref = Path(os.environ['HF_HOME']) / 'hub/models--BAAI--bge-m3/refs/main'
    expected_revision = json.loads((ROOT / 'data/structure_v2/benchmark/comparison.json').read_text(encoding='utf-8'))['models'][-1]['model_main_revision']
    if cache_ref.read_text().strip() != expected_revision:
        raise ValueError('Cached BGE main revision differs from the frozen dense experiment')
    service = EmbeddingService('BAAI/bge-m3', device='cpu', batch_size=32)
    store = VectorStore(frozen['collection'], service.dimension,
                        local_path=ROOT / 'qdrant_data/structure_v2/bge_m3', create_if_missing=False)
    try:
        verified_count = verify_index(store, chunks)
        started = time.perf_counter()
        sparse = BM25Index(chunks)
        index_seconds = time.perf_counter() - started
        retriever = HybridRetriever(sparse, service, store, candidate_k=50, rrf_k=60)
        per_query = []
        for q in judgments:
            retrieved = retriever.retrieve(q['query'])
            relevant = set(q['relevant_chunk_ids'])
            row = {'question_id': q['question_id'], 'query': q['query'],
                   'relevant_chunk_ids': q['relevant_chunk_ids'],
                   'review_status': q['review_status'],
                   'methods': {key: metrics(retrieved[key], relevant) for key in ('bm25', 'dense', 'hybrid')},
                   'candidate_rankings': {key: retrieved[key] for key in ('bm25', 'dense')},
                   'hybrid_top_10': retrieved['hybrid'],
                   'timing': {key: retrieved[key] for key in ('sparse_branch_seconds', 'dense_branch_seconds', 'hybrid_wall_seconds')}}
            per_query.append(row)
            print(q['question_id'], {k:v['first_relevant_rank'] for k,v in row['methods'].items()}, flush=True)
        summary = {method: {metric: sum(q['methods'][method][metric] for q in per_query) / len(per_query)
                            for metric in ('recall_at_5', 'mrr_at_10')}
                   for method in ('bm25', 'dense', 'hybrid')}
        report = {'dataset_sha256': digest(corpus_path), 'labels_sha256': digest(labels_path),
                  'verified_index_count': verified_count, 'eligible_count': len(sparse.chunks),
                  'dense_model': 'BAAI/bge-m3', 'dense_main_revision': expected_revision,
                  'parameters': {'bm25_k1': 1.2, 'bm25_b': 0.75, 'query_tf': 'binary',
                                 'rrf_k': 60, 'candidate_k_per_branch': 50,
                                 'analyzer': 'underthesea segmentation + NFC/lowercase Unicode tokens',
                                 'index_text': 'full embed_text including context; eligible documents only',
                                 'selection': 'Fixed conventional defaults before retrieval; no Dev grid search.'},
                  'filter': 'exclude fully expired; partial/unknown remain eligible, matching the baseline',
                  'parallel_branches': True, 'test_evaluated': False, 'human_review_complete': False,
                  'sparse_backend': 'in_process_python_not_Elasticsearch',
                  'reranker': None, 'metadata_query_extraction': False,
                  'packages': {p: version(p) for p in ('underthesea', 'sentence-transformers', 'qdrant-client')},
                  'bm25_index_seconds': index_seconds, 'metrics': summary, 'per_query': per_query}
        OUTPUT.mkdir(parents=True, exist_ok=True)
        with (OUTPUT / 'dev_results.json').open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(summary, indent=2))
    finally:
        store.client.close()


if __name__ == '__main__':
    main()
