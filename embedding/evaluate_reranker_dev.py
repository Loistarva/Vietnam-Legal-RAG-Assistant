"""Rerank the frozen RRF top-50 pool; never rebuild retrieval or inspect Test."""
import json
import os
import argparse
import re
from importlib.metadata import version
from pathlib import Path

from evaluate_hybrid_dev import digest, metrics
from hybrid_retrieval import reciprocal_rank_fusion
from reranking import CrossEncoderReranker, MODEL
from vector_store import load_chunks

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/structure_v2/reranker'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default=None, help='Exact 40-character model commit SHA; enables cached offline reruns')
    args = parser.parse_args()
    if args.revision and not re.fullmatch(r'[0-9a-f]{40}', args.revision):
        raise ValueError('--revision must be an exact model commit SHA')
    os.environ.setdefault('HF_HOME', str(ROOT / '.venv-embedding/hf-cache'))
    from huggingface_hub import HfApi
    corpus_path = ROOT / 'data/structure_v2/embedding/priority_bkai_chunks.json'
    label_path = ROOT / 'data/structure_v2/embedding/priority_bkai_dev.draft.json'
    source_path = ROOT / 'data/structure_v2/hybrid/dev_results.json'
    corpus = {c['chunk_id']: c for c in load_chunks(corpus_path)}
    labels = json.loads(label_path.read_text(encoding='utf-8'))
    source = json.loads(source_path.read_text(encoding='utf-8'))
    if source['dataset_sha256'] != digest(corpus_path) or source['labels_sha256'] != digest(label_path):
        raise ValueError('Frozen retrieval input hashes differ')
    if source['parameters']['rrf_k'] != 60 or source['parameters']['candidate_k_per_branch'] != 50:
        raise ValueError('Frozen candidate parameters differ')
    if len(labels) != 10 or any(q['split'] != 'dev' for q in labels) or source['test_evaluated']:
        raise ValueError('Require the frozen ten-query Dev scope')
    pools = []
    for q in labels:
        previous = next(row for row in source['per_query'] if row['question_id'] == q['question_id'])
        if q['query'] != previous['query'] or q['relevant_chunk_ids'] != previous['relevant_chunk_ids']:
            raise ValueError('Query/relevance drift')
        branches = previous['candidate_rankings']
        for hits in branches.values():
            ids = [h['chunk_id'] for h in hits]
            if len(ids) > 50 or len(ids) != len(set(ids)) or any(cid not in corpus or corpus[cid]['metadata'].get('validity_status') == 'Hết hiệu lực' for cid in ids):
                raise ValueError('Invalid/ineligible retrieval candidates')
        pool = reciprocal_rank_fusion(branches, k=60, top_k=50)
        if [h['chunk_id'] for h in pool[:10]] != previous['methods']['hybrid']['ranked_chunk_ids']:
            raise ValueError('Reconstructed RRF top-10 differs from baseline')
        for hit in pool:
            c = corpus[hit['chunk_id']]
            hit.update(text=c['text'], metadata=c['metadata'])
        pools.append((q, previous, pool))
    # Resolve once and pin both tokenizer and weights before scoring any labels.
    revision = args.revision or HfApi().model_info(MODEL).sha
    print(f'Loading {MODEL} at revision {revision}', flush=True)
    reranker = CrossEncoderReranker(revision=revision, device='cpu', batch_size=16, max_tokens=512)
    rows = []
    for q, previous, pool in pools:
        ranked = reranker.rerank(q['query'], pool, top_k=50)
        relevant = set(q['relevant_chunk_ids'])
        row = {'question_id': q['question_id'], 'query': q['query'],
               'relevant_chunk_ids': q['relevant_chunk_ids'], 'review_status': q['review_status'],
               'candidate_count': len(pool), 'candidate_coverage': bool(relevant & {h['chunk_id'] for h in pool}),
               'methods': {'rrf': previous['methods']['hybrid'], 'dense': previous['methods']['dense'],
                           'reranked': metrics(ranked, relevant)},
               'rerank_seconds': reranker.last_seconds, 'max_pair_tokens': reranker.last_max_pair_tokens,
               'scored_candidates': ranked}
        rows.append(row)
        print(q['question_id'], row['methods']['reranked']['first_relevant_rank'], flush=True)
    report = {'model': MODEL, 'revision': revision, 'device': 'cpu', 'batch_size': 16,
              'pair_token_limit': 512, 'truncation': False, 'candidate_depth': 50,
              'score_kind': 'raw_relevance_logit_not_legal_confidence',
              'selection': 'Fixed multilingual model and candidate/pair budgets before evaluation; no Dev tuning.',
              'dataset_sha256': digest(corpus_path), 'labels_sha256': digest(label_path),
              'candidate_source_sha256': digest(source_path),
              'test_evaluated': False, 'human_review_complete': False,
              'packages': {p: version(p) for p in ('torch', 'transformers', 'safetensors')},
              'load_seconds': reranker.load_seconds,
              'metrics': {method: {key: sum(q['methods'][method][key] for q in rows)/len(rows)
                                   for key in ('recall_at_5', 'mrr_at_10')}
                          for method in ('dense', 'rrf', 'reranked')},
              'mean_rerank_seconds': sum(q['rerank_seconds'] for q in rows)/len(rows), 'per_query': rows}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / 'dev_results.json').open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report['metrics'], indent=2))


if __name__ == '__main__':
    main()
