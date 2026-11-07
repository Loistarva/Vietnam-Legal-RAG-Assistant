"""Add documents from parser/parsed_jsons that data/reference/article_index.json does not cover yet.

Existing rows are kept as they are. New rows follow the registry file code:
article_id = {file_code}_D{article number, 2 digits}, e.g. ND06_D01.

Usage: python scripts/extend_article_index.py [--check]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'data' / 'reference' / 'article_index.json'
REGISTRY = ROOT / 'data' / 'reference' / 'document_versions.json'
PARSED = ROOT / 'parser' / 'parsed_jsons'
NUMBER_RE = re.compile(r'(\d+)([a-z]?)')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def article_rows(doc, record):
    code = record.get('file_code')
    if not code:
        raise ValueError(f"{doc['document_id']}: registry has no file_code")
    rows = []
    for article in doc['articles']:
        number = str(article['article_number'])
        match = NUMBER_RE.fullmatch(number)
        if not match:
            raise ValueError(f"{doc['document_id']}: unsupported article number {number!r}")
        title = (article.get('article_title') or '').strip()
        rows.append({
            'article_id': f'{code}_D{int(match[1]):02d}{match[2]}',
            'document_id': code,
            'document_number': record['document_number'],
            'article_number': number,
            'article_title': f'Điều {number}. {title}' if title else f'Điều {number}',
            'source_url': record.get('source_url') or '',
            'article_text_available': False,
            'verification_status': 'metadata_only_unverified',
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true', help='only report missing documents, exit 1 if any')
    args = parser.parse_args()

    index = load(INDEX)
    covered = {row['document_number'] for row in index}
    registry = {record['document_id']: record for record in load(REGISTRY)}
    added = []
    for record in registry.values():
        path = PARSED / f"{record['document_id']}.json"
        if record['document_number'] in covered or not path.is_file():
            continue
        rows = article_rows(load(path), record)
        added.append((record['document_id'], len(rows)))
        index.extend(rows)

    ids = [row['article_id'] for row in index]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate article_id after extending the index')
    for document_id, count in added:
        print(f'{document_id}: {count} articles')
    if args.check:
        return 1 if added else 0
    if added:
        INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'added {len(added)} documents, {sum(c for _, c in added)} articles; total {len(index)} articles')
    return 0


if __name__ == '__main__':
    sys.exit(main())
