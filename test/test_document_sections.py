import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'parser'))
from document_sections import partition_document
import parser as legal_parser


class DocumentSectionTests(unittest.TestCase):
    def test_exact_source_partition_with_fake_article_in_appendix(self):
        raw = ('Điều 1. Nội dung\nNội dung phải giữ./.\nTM. CHÍNH PHỦ\nNgười ký\n'
               'Phụ lục\nDANH MỤC\nĐiều 2. Đây là biểu mẫu\n1. Mục phụ lục')
        parts = partition_document(raw)
        self.assertEqual([p['section_type'] for p in parts], ['body', 'footer', 'appendix'])
        self.assertEqual(''.join(p['text'] for p in parts), raw)
        self.assertTrue(all(raw[p['start']:p['end']] == p['text'] for p in parts))
        metadata = {'title':'Văn bản kiểm thử', 'document_type':'Nghị định',
                    'document_number':'1/2020/NĐ-CP', 'issue_date':'2020-01-01',
                    'issuing_body':'Chính phủ', 'validity_status':'Không xác định'}
        with contextlib.redirect_stdout(io.StringIO()):
            doc = legal_parser.parse_raw_text_to_legal_doc(raw, 'TEST', metadata)
        self.assertEqual([a['article_number'] for a in doc['articles']], ['1'])
        self.assertTrue(doc['articles'][0]['clauses'][0]['number_is_synthetic'])
        self.assertEqual(len(doc['ancillary_sections']), 2)
        self.assertTrue(all(not p['retrieval_eligible'] for p in doc['ancillary_sections']))

    def test_inline_references_and_quoted_signature_are_not_boundaries(self):
        for raw in ['Điều 1. Áp dụng theo Phụ lục của Nghị định này.',
                    'Điều 1. Xem Phụ lục DANH MỤC kèm theo văn bản này.',
                    'Điều 1. Chuỗi ký tự “./. Nơi nhận:” là ví dụ, vẫn còn nội dung.']:
            with self.subTest(raw=raw):
                self.assertEqual(partition_document(raw)[0]['text'], raw)
                self.assertEqual(len(partition_document(raw)), 1)

    def test_flattened_tail_still_separates(self):
        raw = 'Điều 1. Nội dung./. Nơi nhận: TM. CHÍNH PHỦ Phụ lục MẪU CÔNG VĂN'
        self.assertEqual([p['section_type'] for p in partition_document(raw)], ['body', 'footer', 'appendix'])

    def test_real_archives_reconstruct_and_earlier_articles_are_unchanged(self):
        for code, number in [('ND01', '67'), ('ND04', '26')]:
            with self.subTest(code=code):
                baseline = json.loads((ROOT / f'data/chunking_output/documents/{code}.json').read_text(encoding='utf-8'))
                doc = json.loads((ROOT / f'data/structure_v2/documents/{code}.json').read_text(encoding='utf-8'))
                archive = json.loads((ROOT / f'data/structure_v2/source_archives/{code}.json').read_text(encoding='utf-8'))
                self.assertEqual(''.join(p['text'] for p in archive['sections']), archive['source_text'])
                self.assertEqual(baseline['articles'][:-1], doc['articles'][:-1])
                article = doc['articles'][-1]
                self.assertEqual(article['article_number'], number)
                self.assertEqual(article['article_title'], 'Trách nhiệm thi hành')
                self.assertEqual(len(article['clauses']), 1)
                self.assertTrue(article['clauses'][0]['number_is_synthetic'])
                self.assertIn('\nNội dung điều: ', article['clauses'][0]['chunks'][0]['chunk_text'])
                self.assertTrue(article['clauses'][0]['chunks'][0]['clause_number_is_synthetic'])
                body = article['clauses'][0]['clause_text']
                self.assertIn('chịu trách nhiệm thi hành Nghị định này./.', ' '.join(body.split()))
                for marker in ['Phụ lục', 'PHỤ LỤC', 'Nơi nhận:', 'TM. CHÍNH PHỦ', 'Mẫu số']:
                    self.assertNotIn(marker, body)
                legal_parser.LegalDocumentSchema.model_validate(doc)

    def test_nd04_keeps_cross_reference_number_from_pdf(self):
        doc = json.loads((ROOT / 'data/structure_v2/documents/ND04.json').read_text(encoding='utf-8'))
        body = ' '.join(doc['articles'][-1]['clauses'][0]['clause_text'].split())
        self.assertIn('Khoản 5 Điều 3', body)
        self.assertEqual(doc['articles'][-1]['source_page'], 13)

    def test_v2_retrieval_contains_only_articles_and_migrated_evidence_is_unchanged(self):
        folder = ROOT / 'data/structure_v2/embedding'
        data = json.loads((folder / 'priority_chunks.json').read_text(encoding='utf-8'))
        by_id = {c['id']: c for c in data['chunks']}
        self.assertEqual(len(by_id), len(data['chunks']))
        self.assertTrue(all(c['section_type'] == 'article' for c in by_id.values()))
        old = {c['id']: c for c in json.loads((ROOT / 'embedding/data/priority_bkai_chunks.json').read_text(encoding='utf-8'))['chunks']}
        labels = json.loads((folder / 'priority_questions.draft.json').read_text(encoding='utf-8'))['questions']
        self.assertEqual(len(labels), 50)
        for q in labels:
            for cid in q['relevant_chunk_ids']:
                self.assertEqual(by_id[cid]['text'], old[cid]['text'])


if __name__ == '__main__':
    unittest.main()
