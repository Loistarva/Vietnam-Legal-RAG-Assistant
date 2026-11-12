"""Rebuild only the contaminated final articles from page-aware PDF text.

Earlier articles and metadata are preserved. All extracted PDF text and every
partition are archived separately by the v2 export, including page artifacts.
"""
import copy
import hashlib
import re
from importlib.metadata import version
from pathlib import Path

import pdfplumber
import parser as legal_parser
from document_sections import partition_document

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'ND01': 67, 'ND04': 26}


def extract_source(path: Path):
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                raise ValueError(f'No extractable text: {path}, page {page.page_number}')
            pages.append(text)
    return '\n'.join(pages), pages


def clean_page_artifacts(text: str) -> str:
    # Remove recognizable repeated publishing/browser lines, never arbitrary
    # integers in legal text (e.g. the 5 in 'Khoản 5 Điều 3'). Raw text is archived.
    lines = text.splitlines()
    return '\n'.join(line for line in lines if not (
        re.match(r'^\s*(?:\d+\s+)?CÔNG BÁO/', line)
        or re.match(r'^\s*\d{1,2}/\d{1,2}/\d{2,4},\s+\d', line)
        or re.match(r'^\s*https?://\S+\s+\d+/\d+\s*$', line)))


def repair_tail(original: dict):
    code = original['document_id']
    number = TARGETS[code]
    source_file = f'data/raw_data/laws_and_decrees/{code}.pdf'
    path = ROOT / source_file
    raw, pages = extract_source(path)
    sections = partition_document(raw)
    kinds = {s['section_type'] for s in sections}
    if not {'body', 'footer', 'appendix'} <= kinds:
        raise ValueError(f'Cannot confidently locate all tail boundaries: {code}')
    body_section = next(s for s in sections if s['section_type'] == 'body')
    body = clean_page_artifacts(body_section['text'])
    headings = list(re.finditer(rf'(?m)^\s*Điều {number}\.\s*([^\n]+)\n', body))
    if len(headings) != 1:
        raise ValueError(f'Expected exactly one final article heading: {code}')
    heading = headings[0]
    title = heading.group(1).strip()
    article_body = body[heading.end():].strip()
    if not article_body.endswith('./.'):
        raise ValueError(f'Unexpected final article termination: {code}')
    if re.search(r'Phụ lục|PHỤ LỤC|Nơi nhận:|TM\. CHÍNH PHỦ', article_body):
        raise ValueError(f'Tail contamination remains: {code}')
    doc = copy.deepcopy(original)
    article = doc['articles'][-1]
    if article['article_number'] != str(number):
        raise ValueError(f'Unexpected final article number: {code}')
    article['article_title'] = title
    article['intro'] = None
    article['clauses'] = [{
        'clause_id': f'{code}_art_{number}_clause_1',
        'parent_article_id': f'{code}_art_{number}',
        'clause_number': '1', 'number_is_synthetic': True,
        'clause_text': article_body, 'chunks': [],
    }]
    # Both final articles have unnumbered paragraphs: one synthetic clause.
    # Find the actual PDF page rather than a printed page-number heuristic.
    source_page = next(i + 1 for i, text in enumerate(pages)
                       if re.search(rf'(?m)^\s*Điều {number}\.', text))
    article['source_file'] = source_file
    article['source_page'] = source_page
    doc['ancillary_sections'] = [s for s in sections if s['section_type'] != 'body']
    provenance = {
        'source_file': source_file,
        'pdf_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'extraction_versions': {name: version(name) for name in ('pdfplumber', 'pdfminer.six', 'pydantic')},
        'extracted_text_sha256': hashlib.sha256(raw.encode()).hexdigest(),
        'source_page': source_page,
        'offset_unit': 'Unicode code points in source_text; PDF pages joined by newline.',
        'repaired_article_id': article['article_id'],
        'synthetic_clause_reason': 'Unnumbered paragraphs in the PDF final article.',
        'section_reconstruction_exact': ''.join(s['text'] for s in sections) == raw,
        'original_clause_ids': [c['clause_id'] for c in original['articles'][-1]['clauses']],
        'limitation': 'Repairs final-article structure only; earlier extraction and legal validity are not certified.',
    }
    doc['structure_repair'] = provenance
    legal_parser.LegalDocumentSchema.model_validate(doc)
    return doc, {'source_text': raw, 'sections': sections, 'provenance': provenance}
