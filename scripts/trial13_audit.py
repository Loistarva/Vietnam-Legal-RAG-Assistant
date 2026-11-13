"""Check PDF provenance, schema, coverage and unchanged baseline chunk payloads."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from collections import Counter
import jsonschema

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'parser'))
import cleaner
from trial13_prepare import EXPECTED_ARTICLES
BASE='cdca079ba63b5e3d48da690df269ff51bb47c887'
REPORT=ROOT/'reports/data/trial13'

def original(path):
    return subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT)

def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

def main():
    downloads=read('reports/data/trial13/downloads.json')
    new_ids={x['document_id'] for x in downloads}
    assert len(new_ids)==13
    schema=read('schemas/metadata_schema.json')
    parsed=[]
    for x in downloads:
        assert hashlib.sha256((ROOT/x['pdf_path']).read_bytes()).hexdigest()==x['sha256']
        if x.get('standardized_pdf_path'):
            assert hashlib.sha256((ROOT/x['standardized_pdf_path']).read_bytes()).hexdigest()==x['standardized_sha256']
        doc=read(f"parser/parsed_jsons/{x['document_id']}.json")
        jsonschema.Draft7Validator(schema,format_checker=jsonschema.FormatChecker()).validate(doc)
        assert len(doc['articles'])==EXPECTED_ARTICLES[x['document_id']]
        assert [a['article_number'] for a in doc['articles']]==[str(i) for i in range(1,len(doc['articles'])+1)]
        source=ROOT/'parser/extracted_texts_qwen'/f"{x['document_id']}.txt"
        cleaned=ROOT/'parser/cleaned_texts'/source.name
        assert cleaned.read_text('utf-8')==cleaner.clean_extracted_text(source.read_text('utf-8'))[0]+'\n'
        parsed.append(doc)
    children=[json.loads(line) for line in (ROOT/'data/chunking_output/chunks.jsonl').read_text('utf-8').splitlines() if line]
    parents=read('data/chunking_output/parents.json')
    old_children=[json.loads(line) for line in original('data/chunking_output/chunks.jsonl').decode('utf-8').splitlines() if line]
    old_parents=json.loads(original('data/chunking_output/parents.json'))
    by_id={x['chunk_id']:x for x in children}
    parents_by_id={x['parent_id']:x for x in parents}
    assert len(by_id)==len(children)
    assert len(parents_by_id)==len(parents)
    assert all(by_id.get(x['chunk_id'])==x for x in old_children),'Changed old child payload'
    assert all(parents_by_id.get(x['parent_id'])==x for x in old_parents),'Changed old parent payload'
    assert all(c['parent_id'] in parents_by_id for c in children)
    assert Counter(c['chunk_id'] for c in children)==Counter(cid for p in parents for cid in p['child_ids'])
    assert all(len(p['text'])<=1500 for p in parents)
    unchanged=[]
    for path in ['parser/parser.py','parser/cleaner.py','chunking/chunking_rules.py','chunking/export_legal_chunks.py']:
        assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n')==original(path).replace(b'\r\n',b'\n'),path
        unchanged.append(path)
    report=read('data/chunking_output/chunking_report.json')
    new_stats=[x for x in report['documents'] if x['document_id'] in new_ids]
    result={'baseline_commit':BASE,'new_documents':len(new_ids),
            'total_documents':report['num_documents'],'total_pdfs':len(list((ROOT/'data/raw_data').rglob('*.pdf'))),
            'new_articles':sum(len(x['articles']) for x in parsed),
            'new_clauses':sum(len(a['clauses']) for x in parsed for a in x['articles']),
            'new_parents':len(parents)-len(old_parents),'new_children':len(children)-len(old_children),
            'total_parents':len(parents),'total_children':len(children),
            'unchanged_baseline_parents':len(old_parents),'unchanged_baseline_children':len(old_children),
            'duplicate_child_ids':0,'all_new_schemas_valid':True,'all_new_article_counts_verified':True,
            'cleaner_reproducible':True,'pdf_hashes_match':True,'unchanged_pipeline_files':unchanged,
            'tokenizer':report['tokenization_backend'],'tokenizer_version':report['tokenization_version'],
            'documents':new_stats,
            'limitations':['Trial corpus only: current validity and provision-level amendments remain unverified.',
                'Original PDFs retain annexes; existing parser exports main articles, not forms/annexes.',
                'Automated structure/content checks and sampled visual review do not certify every legal sentence.']}
    (REPORT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'documents','limitations'}},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
