"""Cross-encoder ranking of an already filtered candidate pool.

Raw logits order passages; they are not calibrated legal-confidence scores.
Query/passage pairs exceeding the configured budget fail instead of truncating.
"""
import copy
import math
import time

MODEL = 'BAAI/bge-reranker-v2-m3'


def positive_integer(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(f'{name} must be a positive integer')


def apply_scores(hits, scores, top_k=10):
    positive_integer(top_k, 'top_k')
    if top_k < 1 or len(hits) != len(scores):
        raise ValueError('Invalid reranker depth or score count')
    ids = [h['chunk_id'] for h in hits]
    if len(ids) != len(set(ids)) or any(not isinstance(cid, str) or not cid for cid in ids):
        raise ValueError('Duplicate/invalid reranker candidate IDs')
    if any(not math.isfinite(float(s)) for s in scores):
        raise ValueError('Non-finite reranker score')
    ranked = []
    for rank, (hit, score) in enumerate(zip(hits, scores), 1):
        item = copy.deepcopy(hit)
        item.update(rrf_score=item['score'], score=float(score),
                    reranker_score=float(score), score_kind='reranker_logit', pre_rerank_rank=rank)
        ranked.append(item)
    return sorted(ranked, key=lambda h: (-h['reranker_score'], h['pre_rerank_rank'], h['chunk_id']))[:top_k]


class CrossEncoderReranker:
    def __init__(self, model_name=MODEL, revision=None, device='cpu', batch_size=16, max_tokens=512):
        positive_integer(batch_size, 'batch_size')
        positive_integer(max_tokens, 'max_tokens')
        if batch_size < 1 or max_tokens < 1:
            raise ValueError('Invalid reranker batch/token budget')
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        started = time.perf_counter()
        self.model_name, self.revision = model_name, revision
        kwargs = {'revision': revision} if revision else {}
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, **kwargs)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name, **kwargs).to(device).eval()
        if self.model.config.num_labels != 1:
            raise ValueError('Require one relevance logit per pair')
        self.torch, self.device = torch, device
        self.batch_size, self.max_tokens = batch_size, max_tokens
        self.load_seconds = time.perf_counter() - started

    def rerank(self, query, hits, top_k=10):
        positive_integer(top_k, 'top_k')
        if not isinstance(query, str) or not query.strip() or top_k < 1:
            raise ValueError('Require nonempty query and positive top_k')
        if not hits:
            self.last_seconds, self.last_max_pair_tokens = 0.0, 0
            return []
        if any(not isinstance(h.get('text'), str) or not h['text'].strip() for h in hits):
            raise ValueError('Candidate text is missing')
        started = time.perf_counter()
        lengths = self.tokenizer([query]*len(hits), [h['text'] for h in hits],
                                 truncation=False, padding=False, return_length=True)['length']
        self.last_max_pair_tokens = max(lengths)
        if self.last_max_pair_tokens > self.max_tokens:
            raise ValueError(f'Reranker pair exceeds {self.max_tokens} tokens; do not silently truncate evidence')
        scores = []
        with self.torch.inference_mode():
            for start in range(0, len(hits), self.batch_size):
                batch = hits[start:start+self.batch_size]
                tokens = self.tokenizer([query]*len(batch), [h['text'] for h in batch],
                                        truncation=False, padding=True, return_tensors='pt').to(self.device)
                scores.extend(self.model(**tokens).logits.view(-1).float().cpu().tolist())
        result = apply_scores(hits, scores, top_k)
        self.last_seconds = time.perf_counter() - started
        return result
