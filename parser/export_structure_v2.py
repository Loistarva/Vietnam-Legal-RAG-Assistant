"""Export repaired article-only corpus without overwriting the frozen baseline."""
import copy
import hashlib
import json
from pathlib import Path

from chunker import ALL_CODES, BASE, make_chunks, legal_parser
from repair_document_tail import TARGETS, repair_tail

OUTPUT = BASE / 'data/structure_v2'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    baseline = BASE / 'data/chunking_output'
    documents, archives, rows, changed = {}, {}, [], []
    for code in ALL_CODES:
        original = json.loads((baseline / 'documents' / f'{code}.json').read_text(encoding='utf-8'))
        doc = copy.deepcopy(original)
        if code in TARGETS:
            doc, archive = repair_tail(original)
            archives[code] = archive
            changed.append({'document_id': code,
                            'original_last_article_clauses': len(original['articles'][-1]['clauses']),
                            'corrected_last_article_clauses': len(doc['articles'][-1]['clauses']),
                            'original_last_article_chunk_ids': [c['chunk_id'] for cl in original['articles'][-1]['clauses'] for c in cl['chunks']],
                            'id_policy': 'Final-article IDs may have changed content; do not migrate affected labels by ID alone.'})
        rows.extend(make_chunks(doc, code))
        legal_parser.LegalDocumentSchema.model_validate(doc)
        documents[code] = doc
    ids = [r['chunk_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate article chunk IDs')
    fixture = []
    for row in rows:
        doc = documents[row['document_id']]
        fixture.append({'id': row['chunk_id'], 'text': row['chunk_text'],
                        'embed_text': row['chunk_text'],
                        **{k: v for k, v in row.items() if k not in ('chunk_id', 'chunk_text', 'char_count')},
                        **doc['metadata'], 'parent_id': row['clause_id'],
                        'section_type': 'article', 'dataset_version': 'structure_v2',
                        'validity_checked_at': doc.get('source_verification', {}).get('checked_at'),
                        'metadata_verification': 'official_source_corrections_applied_not_full_text_certification'})
    baseline_fixture = json.loads((BASE / 'embedding/data/priority_bkai_chunks.json').read_text(encoding='utf-8'))
    old_by_id = {c['id']: c for c in baseline_fixture['chunks']}
    new_by_id = {c['id']: c for c in fixture}
    labels = json.loads((BASE / 'embedding/data/priority_bkai_questions.draft.json').read_text(encoding='utf-8'))
    reviewed_dev = json.loads((BASE / 'embedding/data/priority_bkai_dev.support_reviewed.json').read_text(encoding='utf-8'))
    dev_by_id = {q['question_id']: q for q in reviewed_dev}
    questions = []
    for original_q in labels['questions']:
        q = copy.deepcopy(dev_by_id.get(original_q['question_id'], original_q))
        for cid in q['relevant_chunk_ids']:
            if cid not in new_by_id or new_by_id[cid]['text'] != old_by_id[cid]['text']:
                raise ValueError(f'Label requires manual migration: {q["question_id"]}, {cid}')
        q.pop('dataset_sha256', None)
        questions.append(q)
    # Validate and prepare everything before writing any generated artifacts.
    for code, doc in documents.items():
        write(OUTPUT / 'documents' / f'{code}.json', doc)
    for code, archive in archives.items():
        write(OUTPUT / 'source_archives' / f'{code}.json', archive)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / 'chunks.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    fixture_path = OUTPUT / 'embedding/priority_chunks.json'
    write(fixture_path, {'dataset_name': 'article_only_structure_v2',
                         'baseline_dataset_sha256': hashlib.sha256((BASE / 'embedding/data/priority_bkai_chunks.json').read_bytes()).hexdigest(),
                         'ancillary_policy': 'Raw appendix/footer retained in source_archives and excluded from article retrieval.',
                         'chunks': fixture})
    digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    write(OUTPUT / 'embedding/priority_questions.draft.json', {
        'status': 'dev_assistant_reviewed_test_draft_human_review_pending',
        'dataset_sha256': digest, 'questions': questions})
    report = {'version': 'structure_v2', 'documents': len(documents),
              'article_count': sum(len(d['articles']) for d in documents.values()),
              'clause_count': sum(len(a['clauses']) for d in documents.values() for a in d['articles']),
              'chunk_count': len(rows), 'changes': changed, 'dataset_sha256': digest,
              'source_reconstruction_exact': all(a['provenance']['section_reconstruction_exact'] for a in archives.values()),
              'migrated_labels': len(questions), 'label_evidence_text_unchanged': True,
              'production_ready': False,
              'limitations': ['Only ND01/ND04 final articles repaired; other extraction issues remain.',
                              'ND01 article-level validity and ND03 status remain unresolved.',
                              'Ancillary sections are preserved but not indexed; form/appendix retrieval is a separate future path.',
                              'Corpus hash changed; old benchmark metrics do not apply to v2.']}
    write(OUTPUT / 'report.json', report)
    print(json.dumps({k:v for k,v in report.items() if k != 'changes'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
