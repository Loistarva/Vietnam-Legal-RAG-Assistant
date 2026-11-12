"""Refresh generated exports using reviewed source corrections, preserving originals.

Run: python parser/refresh_verified_export.py
Only data/chunking_output generated files are updated. Raw PDFs and validated
parser input JSONs are never overwritten.
"""
import json
from collections import Counter
from chunker import BASE, ALL_CODES, make_chunks, legal_parser
from verified_sources import apply_verified_sources


def main():
    output = BASE / 'data/chunking_output'
    documents, rows = {}, []
    for code in ALL_CODES:
        doc = json.loads((output / 'documents' / f'{code}.json').read_text(encoding='utf-8-sig'))
        apply_verified_sources(doc)
        rows.extend(make_chunks(doc, code))
        legal_parser.LegalDocumentSchema.model_validate(doc)
        documents[code] = doc
    duplicates = [cid for cid, n in Counter(r['chunk_id'] for r in rows).items() if n > 1]
    if duplicates:
        raise ValueError(f'Duplicate IDs: {duplicates}')
    report = {}
    for code, doc in documents.items():
        with (output / 'documents' / f'{code}.json').open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
        report[code] = {'articles': len(doc['articles']),
                        'clauses': sum(len(a['clauses']) for a in doc['articles']),
                        'chunks': sum(r['document_id'] == code for r in rows),
                        'source': 'existing_export_with_official_source_corrections'}
    with (output / 'chunks.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    with (output / 'report.json').open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
