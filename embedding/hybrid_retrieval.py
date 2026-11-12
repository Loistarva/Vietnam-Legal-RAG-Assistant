"""Local BM25 + dense retrieval with rank-only RRF and shared eligibility.

Formula references and experiment scope are documented in docs/hybrid_dev.md.
This in-process BM25 baseline is not an Elasticsearch deployment.
"""
import math
import copy
import re
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor


def lexical_tokens(text):
    return re.findall(r'[^\W_]+(?:_[^\W_]+)*', unicodedata.normalize('NFC', text).lower())


def vietnamese_tokens(text):
    from underthesea import word_tokenize
    segmented = ' '.join(token.replace(' ', '_') for token in word_tokenize(text))
    return lexical_tokens(segmented)


class BM25Index:
    def __init__(self, chunks, analyzer=vietnamese_tokens, k1=1.2, b=0.75):
        if not math.isfinite(k1) or k1 < 0 or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError('Invalid BM25 k1/b')
        self.analyzer, self.k1, self.b = analyzer, k1, b
        ids = [c['chunk_id'] for c in chunks]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate BM25 IDs')
        # Match the frozen dense experiment's existing validity policy.
        self.chunks = {c['chunk_id']: c for c in chunks
                       if c['metadata'].get('validity_status') != 'Hết hiệu lực'}
        if not self.chunks:
            raise ValueError('No eligible BM25 documents')
        self.lengths, self.postings = {}, defaultdict(dict)
        for cid, chunk in self.chunks.items():
            counts = Counter(analyzer(chunk['embed_text']))
            self.lengths[cid] = sum(counts.values())
            for term, tf in counts.items():
                self.postings[term][cid] = tf
        self.average_length = sum(self.lengths.values()) / len(self.chunks)
        if not self.average_length:
            raise ValueError('Eligible corpus has no lexical tokens')

    def search(self, query, top_k=10, policy=None):
        if top_k < 1 or not isinstance(query, str) or not query.strip():
            raise ValueError('Require nonempty query and positive top_k')
        scores = defaultdict(float)
        active = {cid for cid,c in self.chunks.items() if policy is None or policy.matches(c['metadata'])}
        if not active:
            return []
        average_length = sum(self.lengths[cid] for cid in active) / len(active)
        if not average_length:
            return []
        for term in sorted(set(self.analyzer(query))):  # Binary query TF, fixed before evaluation.
            posting = {cid:tf for cid,tf in self.postings.get(term, {}).items() if cid in active}
            idf = math.log1p((len(active) - len(posting) + 0.5) / (len(posting) + 0.5))
            for cid, tf in posting.items():
                norm = self.k1 * (1 - self.b + self.b * self.lengths[cid] / average_length)
                scores[cid] += idf * tf * (self.k1 + 1) / (tf + norm)
        return [{'chunk_id': cid, 'score': score}
                for cid, score in sorted(scores.items(), key=lambda row: (-row[1], row[0]))[:top_k]
                if score > 0]


def reciprocal_rank_fusion(rankings, k=60, top_k=10):
    if not math.isfinite(k) or k <= 0 or top_k < 1:
        raise ValueError('Require positive RRF k and top_k')
    scores, positions = defaultdict(float), defaultdict(dict)
    for name, hits in rankings.items():
        seen = set()
        for hit in hits:
            cid = hit['chunk_id']
            if cid in seen:
                continue
            seen.add(cid)
            rank = len(seen)
            scores[cid] += 1 / (k + rank)
            positions[cid][name] = rank
    ordered = sorted(scores, key=lambda cid: (-scores[cid], min(positions[cid].values()), cid))[:top_k]
    return [{'chunk_id': cid, 'score': scores[cid], 'component_ranks': positions[cid]}
            for cid in ordered]


class HybridRetriever:
    def __init__(self, sparse, embedding_service, vector_store, candidate_k=50, rrf_k=60,
                 reranker=None, rerank_depth=50):
        if candidate_k < 10 or rrf_k <= 0:
            raise ValueError('Require at least 10 candidates and positive RRF constant')
        self.sparse, self.service, self.store = sparse, embedding_service, vector_store
        self.candidate_k, self.rrf_k = candidate_k, rrf_k
        if reranker is not None and (rerank_depth < 10 or rerank_depth > candidate_k):
            raise ValueError('Rerank depth must be between 10 and candidate_k')
        self.reranker, self.rerank_depth = reranker, rerank_depth

    def retrieve(self, query, top_k=10, policy=None):
        if not isinstance(query,str) or not query.strip():
            raise ValueError('Require a nonempty query')
        if top_k < 1 or top_k > self.candidate_k:
            raise ValueError('top_k must be within candidate_k')
        if self.reranker is not None and top_k > self.rerank_depth:
            raise ValueError('top_k must be within the rerank candidate depth')
        started = time.perf_counter()
        allowed = {cid for cid,c in self.sparse.chunks.items() if policy is None or policy.matches(c['metadata'])}
        if not allowed:
            result = {'bm25':[], 'dense':[], 'hybrid':[], 'sparse_branch_seconds':0.0,
                      'dense_branch_seconds':0.0, 'hybrid_wall_seconds':time.perf_counter()-started}
            if self.reranker is not None:
                result.update(reranked=[], rerank_seconds=0.0, total_wall_seconds=result['hybrid_wall_seconds'])
            return result

        def sparse_branch():
            start = time.perf_counter()
            hits = (self.sparse.search(query, self.candidate_k) if policy is None else
                    self.sparse.search(query, self.candidate_k, policy=policy))
            return hits, time.perf_counter() - start

        def dense_branch():
            start = time.perf_counter()
            vector = self.service.embed_query(query)
            kwargs = {'exclude_expired':True}
            if policy is not None:
                kwargs['allowed_chunk_ids'] = sorted(allowed)
            hits = self.store.search(vector, self.candidate_k, **kwargs)
            return hits, time.perf_counter() - start

        with ThreadPoolExecutor(max_workers=2) as pool:
            sparse_future, dense_future = pool.submit(sparse_branch), pool.submit(dense_branch)
            sparse_hits, sparse_seconds = sparse_future.result()
            dense_hits, dense_seconds = dense_future.result()
        for hit in dense_hits:
            if hit['chunk_id'] not in allowed:
                raise ValueError('Dense returned unknown/ineligible evidence')
        depth = self.rerank_depth if self.reranker is not None else top_k
        fused = reciprocal_rank_fusion({'bm25': sparse_hits, 'dense': dense_hits}, self.rrf_k, depth)
        for hit in fused:
            chunk = self.sparse.chunks[hit['chunk_id']]
            hit.update(text=chunk['text'], metadata=copy.deepcopy(chunk['metadata']))
        result = {'bm25': sparse_hits, 'dense': dense_hits, 'hybrid': fused[:top_k],
                'sparse_branch_seconds': sparse_seconds, 'dense_branch_seconds': dense_seconds,
                'hybrid_wall_seconds': time.perf_counter() - started}
        if self.reranker is not None:
            result['reranked'] = self.reranker.rerank(query, fused, top_k)
            result['rerank_seconds'] = self.reranker.last_seconds
            result['total_wall_seconds'] = time.perf_counter() - started
        return result
