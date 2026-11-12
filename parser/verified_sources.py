"""Apply explicit, traceable official-source corrections after extraction."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def apply_verified_sources(doc: dict) -> dict:
    registry = json.loads((ROOT / 'data/verified_legal_sources.json').read_text(encoding='utf-8'))
    entry = registry['documents'].get(doc['document_id'])
    if not entry:
        return doc
    if doc['metadata']['document_number'] != entry['document_number']:
        raise ValueError('Official metadata overlay document number mismatch')
    # Preserve extraction evidence; never present the raw parser output as verified.
    doc.setdefault('extracted_metadata', dict(doc['metadata']))
    doc['metadata'].update(entry['metadata'])
    doc['source_verification'] = {**entry, 'checked_at': registry['checked_at']}
    supplement = entry.get('supplement')
    if supplement:
        source = ROOT / supplement['source_file']
        if hashlib.sha256(source.read_bytes()).hexdigest() != supplement['sha256']:
            raise ValueError('Official supplement PDF checksum mismatch')
        for item in supplement['articles']:
            aid = f"{doc['document_id']}_art_{item['article_number']}"
            matches = [a for a in doc['articles'] if a['article_id'] == aid]
            if matches:
                # Fail on divergent content rather than silently replacing an article.
                existing = ' '.join(c['clause_text'] for c in matches[0]['clauses'])
                if ' '.join(existing.split()) != ' '.join(item['text'].split()):
                    raise ValueError(f'Conflicting supplement article: {aid}')
                continue
            doc['articles'].append({
                'article_id': aid, 'article_number': item['article_number'],
                'article_title': item['article_title'],
                'chapter': 'Chương IX ĐIỀU KHOẢN THI HÀNH', 'section': None,
                'intro': None, 'source_file': supplement['source_file'],
                'source_url': supplement['source_url'], 'source_page': supplement['page'],
                'clauses': [{'clause_id': aid + '_clause_1',
                             'parent_article_id': aid, 'clause_number': '1',
                             'clause_text': item['text'], 'chunks': []}],
            })
    return doc
