"""Resolve canonical parent evidence and source-safe citations after ranking."""
import copy
import json
import re
from pathlib import Path

from retrieval_policy import RetrievalPolicy, policy_from_query
from vector_store import load_chunks


def compact(text):
    return ' '.join(str(text or '').split())


class ParentContextResolver:
    def __init__(self, document_dir, chunk_file):
        self.chunks = {c['chunk_id']: c for c in load_chunks(chunk_file)}
        self.documents, self.articles, self.clauses = {}, {}, {}
        for file in sorted(Path(document_dir).glob('*.json')):
            doc = json.loads(file.read_text(encoding='utf-8-sig'))
            did = doc['document_id']
            if did in self.documents:
                raise ValueError('Duplicate document ID')
            self.documents[did] = doc
            for article in doc['articles']:
                aid = article['article_id']
                if aid in self.articles:
                    raise ValueError('Duplicate article ID')
                self.articles[aid] = (doc, article)
                for clause in article['clauses']:
                    cid = clause['clause_id']
                    if cid in self.clauses or clause['parent_article_id'] != aid:
                        raise ValueError('Duplicate clause or mismatched article parent')
                    self.clauses[cid] = (doc, article, clause)
        for chunk in self.chunks.values():
            metadata = chunk['metadata']
            parent = self.clauses.get(metadata.get('clause_id'))
            if parent is None:
                raise ValueError('Unknown canonical clause parent')
            doc, article, clause = parent
            if metadata.get('document_id') != doc['document_id'] or metadata.get('article_id') != article['article_id'] or metadata.get('parent_id') != clause['clause_id'] or metadata.get('document_number') != doc['metadata']['document_number'] or metadata.get('validity_status') != doc['metadata']['validity_status']:
                raise ValueError('Canonical chunk and document metadata drift')
            if any(metadata.get(key) != doc['metadata'].get(key) for key in ('document_type','issue_date','effective_date')):
                raise ValueError('Canonical filter metadata drift')

    def resolve(self, hit, policy=None):
        canonical = self.chunks.get(hit.get('chunk_id'))
        if canonical is None:
            raise ValueError('Unknown evidence chunk')
        metadata = canonical['metadata']
        if not (policy or RetrievalPolicy()).matches(metadata):
            raise ValueError('Evidence excluded by the applied metadata policy')
        supplied = hit.get('metadata')
        if supplied is not None:
            for key in ('document_id','article_id','clause_id','parent_id','document_number','source_file','source_url','source_page','validity_status'):
                if supplied.get(key) != metadata.get(key):
                    raise ValueError('Hit metadata conflicts with canonical source')
        if 'text' in hit and hit['text'].strip() != canonical['text']:
            raise ValueError('Hit text conflicts with canonical source')
        doc, article, clause = self.clauses[metadata['clause_id']]
        number = str(clause['clause_number'])
        synthetic = bool(clause.get('number_is_synthetic') or metadata.get('clause_number_is_synthetic'))
        synthetic = synthetic or not bool(re.match(r'^\s*' + re.escape(number) + r'\.\s+', clause['clause_text']))
        title = compact(article.get('article_title'))
        article_text = [f"Điều {article['article_number']}" + (f'. {title}' if title else '')]
        intro = compact(article.get('intro'))
        if intro and not any(compact(c['clause_text']).startswith(intro) for c in article['clauses']):
            article_text.append(article['intro'])
        article_text.extend(c['clause_text'] for c in article['clauses'])
        citation = {'document_id':doc['document_id'], 'document_type':doc['metadata']['document_type'],
                    'document_number':doc['metadata']['document_number'],
                    'article_number':str(article['article_number']),
                    'clause_number':None if synthetic else number, 'point_letter':None,
                    'source_url':metadata.get('source_url'), 'source_file':metadata.get('source_file'),
                    'source_page':metadata.get('source_page'), 'clause_number_is_synthetic':synthetic}
        citation['label'] = f"{citation['document_type']} {citation['document_number']}, Điều {citation['article_number']}"
        if not synthetic:
            citation['label'] += f", Khoản {number}"
        return {'document_id':doc['document_id'], 'article_id':article['article_id'],
                'clause_id':clause['clause_id'], 'parent_clause_text':clause['clause_text'],
                'article_text':'\n'.join(article_text), 'citation':citation,
                'validity_status':metadata['validity_status']}


class LegalSearchPipeline:
    """Strict-by-default search/evidence assembly; no generated legal answer."""
    def __init__(self, retriever, resolver):
        self.retriever, self.resolver = retriever, resolver

    def search(self, query, top_k=10, policy=None):
        if not isinstance(query,str) or not query.strip():
            raise ValueError('Require a nonempty query')
        effective = policy or policy_from_query(query)
        retrieved = self.retriever.retrieve(query, top_k=top_k, policy=effective)
        selected = retrieved.get('reranked', retrieved['hybrid'])
        evidence, parents = [], {}
        for hit in selected:
            context = self.resolver.resolve(hit, effective)
            text = context.pop('article_text')
            parents.setdefault(context['article_id'], {'article_id':context['article_id'],
                              'document_id':context['document_id'],
                              'document_number':context['citation']['document_number'],
                              'article_number':context['citation']['article_number'],
                              'source_url':context['citation']['source_url'],
                              'source_file':context['citation']['source_file'],
                              'validity_status':context['validity_status'], 'text':text})
            evidence.append({**copy.deepcopy(hit), 'context':context})
        return {**retrieved, 'evidence':evidence, 'parent_contexts':list(parents.values()),
                'applied_policy':effective.to_dict(), 'policy_source':'explicit' if policy else 'explicit_query_reference_rules',
                'status':'evidence_found' if evidence else 'no_eligible_evidence',
                'answer_generated':False}
