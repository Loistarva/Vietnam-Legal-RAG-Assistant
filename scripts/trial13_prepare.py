"""Prepare auditable TXT/metadata, then run the unchanged parser on 13 new PDFs.

Validity is deliberately unverified: this branch is a parsing trial, not a
current-law release. Original PDF bytes are never rewritten.
"""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime
from pathlib import Path
import hashlib
import unicodedata
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'parser'))
import cleaner
import parser as legal_parser
from test_parser import parse_one_file

REPORT = ROOT / 'reports/data/trial13'
EXPECTED_ARTICLES = {
    'l_60_2014_qh13':77, 'l_52_2010_qh12':52, 'l_13_2022_qh15':56,
    'l_35_2013_qh13':33, 'l_51_2010_qh12':53, 'nd_06_2011_nd_cp':20,
    'nd_28_2012_nd_cp':35, 'nd_19_2011_nd_cp':52, 'nd_114_2016_nd_cp':11,
    'nd_15_2014_nd_cp':20,
    'nd_56_2017_nd_cp':58, 'nd_76_2023_nd_cp':45, 'tt_10_2020_tt_btp':9,
}

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def main():
    downloads = json.loads((REPORT/'downloads.json').read_text(encoding='utf-8'))
    if len(downloads) != 13 or any(x['download_status'] != 'downloaded' for x in downloads):
        raise RuntimeError('Expected 13 successful PDF downloads')
    registry_path = ROOT/'data/reference/document_versions.json'
    registry = json.loads(registry_path.read_text(encoding='utf-8'))
    new_ids = {x['document_id'] for x in downloads}
    registry = [x for x in registry if x.get('document_id') not in new_ids]
    next_codes = {}
    for prefix in ['L','ND','TT']:
        existing = [int(m[1]) for row in registry if (m := re.fullmatch(prefix+r'(\d+)',row.get('file_code','')))]
        next_codes[prefix] = max(existing,default=0)+1
    records = []
    for x in downloads:
        fields = x['official_fields']
        issue_date = datetime.strptime(fields['Ngày ban hành'], '%d-%m-%Y').date().isoformat()
        if x['document_id'] in {'l_52_2010_qh12','l_51_2010_qh12'}:
            issue_date = '2010-06-17'  # Adoption date in original PDF; portal differs.
        effective = fields.get('Ngày có hiệu lực')
        effective = datetime.strptime(effective, '%d-%m-%Y').date().isoformat() if effective else None
        effective = {'l_52_2010_qh12':'2011-01-01','l_51_2010_qh12':'2011-01-01','nd_19_2011_nd_cp':'2011-05-08'}.get(x['document_id'],effective)
        title = fields['Trích yếu']
        title = re.sub(r'^(?:Nghị định|Thông tư) số \S+\s+', '', title).rstrip('.')
        title = {'l_35_2013_qh13':'Luật Hòa giải ở cơ sở'}.get(x['document_id'],title)
        record = {
            'document_id':x['document_id'], 'document_number':x['document_number'],
            'document_type':fields['Loại văn bản'], 'title':title,
            'issue_date':issue_date, 'effective_date':effective, 'expiry_date':'',
            'issuing_body':fields['Cơ quan ban hành'], 'validity_status':'Không xác định',
            'source_status':'Chưa xác minh hiệu lực hiện tại - bộ thử parser/chunker',
            'provision_status':'requires_review', 'source_url':x['source_url'],
            'pdf_url':x['url'], 'pdf_path':x['pdf_path'], 'pdf_sha256':x['sha256'],
            'ingest_pdf_path':x.get('standardized_pdf_path',x['pdf_path']),
            'origin':'trial13 - tải PDF gốc từ cơ quan nhà nước',
            'download_status':'Đã tải, kiểm tra lớp chữ', 'verified_at':'2026-11-13',
            'verification_scope':'Số hiệu, ngày ban hành/hiệu lực ban đầu, cấu trúc Điều. Chưa xác minh hiệu lực hiện tại và sửa đổi cấp Điều/Khoản.',
            'trial_only':True,
        }
        prefix = 'L' if record['document_type']=='Luật' else 'ND' if record['document_type']=='Nghị định' else 'TT'
        record['file_code'] = f'{prefix}{next_codes[prefix]:02}'
        next_codes[prefix] += 1
        if x['document_id'] in {'l_52_2010_qh12','l_51_2010_qh12'}:
            record['metadata_note'] = 'Ngày ban hành lấy theo câu thông qua cuối PDF (17/6/2010), không lấy ngày hiển thị khác trên trang Chính phủ.'
        records.append(record)
    write_json(registry_path, registry+records)
    write_json(REPORT/'metadata.json',records)
    rows = '\n'.join(f"| **{x['file_code']}** | `{x['document_id']}` | {x['document_number']} | {x['validity_status']} | {x['title']} |" for x in records)
    for rel, marker in [('docs/data_contract.md','## 6. Bảng Ánh xạ Định danh Văn bản'),('data/raw_data/README.md','Hệ thống sử dụng bảng ánh xạ chuẩn hóa chính thức')]:
        path = ROOT/rel
        text = path.read_text(encoding='utf-8')
        # Replace only trial rows. All existing mapping rows retain their values.
        text = '\n'.join(line for line in text.split('\n') if not (line.startswith('|') and any(f'`{did}`' in line for did in new_ids)))
        start = text.index(marker)
        end = text.find('\n## ',start+len(marker))
        if end<0: end=len(text)
        table_rows = list(re.finditer(r'(?m)^\|.*\|$',text[start:end]))
        insertion = start+table_rows[-1].end()
        text = text[:insertion]+'\n'+rows+text[insertion:]
        path.write_text(text,encoding='utf-8')
    results=[]
    for x in downloads:
        item={'document_id':x['document_id'],'document_number':x['document_number']}
        pdf_path=ROOT/x.get('standardized_pdf_path',x['pdf_path'])
        expected_hash=x.get('standardized_sha256',x['sha256'])
        assert hashlib.sha256(pdf_path.read_bytes()).hexdigest()==expected_hash
        with pymupdf.open(pdf_path) as pdf:
            pages=[cleaner.normalize_extracted_text(p.get_text('text',sort=True)) for p in pdf]
        original=cleaner.normalize_extracted_text('\n\n'.join(pages))
        original_path=REPORT/'original_extracted_texts'/f"{x['document_id']}.txt"
        original_path.parent.mkdir(parents=True,exist_ok=True)
        original_path.write_text(original+'\n',encoding='utf-8')
        # Input preparation only: strip PDF signature metadata and horizontal
        # rules before passing the text to the unchanged cleaner. Keep the full
        # original extraction above for audit and byte-for-byte reproduction.
        raw,signatures=re.subn(r'(?m)^(?:Ký bởi:|Người ký:|Email:|Cơ quan:|Thời gian ký:)[^\n]*\n?', '', original)
        raw,separators=re.subn(r'(?m)^[_\-]{3,}\s*$', '', raw)
        # The ceremonial adoption statement follows the operative articles.
        # Preserve it in original_extracted_texts and metadata, not in the final
        # clause. Match only at a line start near the end of these five laws;
        # never remove an in-body reference to a law's adoption.
        adoption_statements=0
        if x['document_id'].startswith('l_'):
            raw=unicodedata.normalize('NFC',raw)
            adoption=re.search(r'(?m)^Luật này đã được Quốc hội\b',raw)
            signer=re.search(r'(?m)^CHỦ TỊCH QUỐC HỘI\s*$',raw)
            if adoption and signer and adoption.start()<signer.start() and adoption.start()>len(raw)*0.9:
                raw=raw[:adoption.start()]+raw[signer.start():]
                adoption_statements=1
        raw=cleaner.normalize_extracted_text(raw)
        raw_path=ROOT/'parser/extracted_texts_qwen'/f"{x['document_id']}.txt"
        raw_path.write_text(raw+'\n',encoding='utf-8')
        cleaned,counts=cleaner.clean_extracted_text(raw)
        cleaned_path=ROOT/'parser/cleaned_texts'/f"{x['document_id']}.txt"
        cleaned_path.write_text(cleaned+'\n',encoding='utf-8')
        item.update({'normalizations':counts,'signature_lines_removed':signatures,'separator_lines_removed':separators,
                     'adoption_statements_separated':adoption_statements,
                     'raw_text_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                     'cleaned_text_sha256':hashlib.sha256(cleaned.encode()).hexdigest()})
        try:
            parsed_path=parse_one_file(cleaned_path,show_report=False)
            doc=json.loads(parsed_path.read_text(encoding='utf-8'))
            articles=doc['articles']
            item.update({'status':'parsed','num_articles':len(articles),
                         'num_clauses':sum(len(a['clauses']) for a in articles),
                         'expected_articles':EXPECTED_ARTICLES.get(x['document_id']),
                         'last_article_title':articles[-1]['article_title'],
                         'warnings':list(legal_parser.WARNINGS)})
            if item['expected_articles'] and len(articles)!=item['expected_articles']:
                item['status']='coverage_failed'
        except Exception as exc:
            item.update({'status':'failed','error':str(exc)})
        print(json.dumps(item,ensure_ascii=False),flush=True)
        results.append(item)
    write_json(REPORT/'parse_report.json',results)
    if any(x['status']!='parsed' for x in results):
        raise SystemExit(1)

if __name__=='__main__':
    main()
