"""Regression checks for traceable metadata corrections and official supplements."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'parser'))
from verified_sources import apply_verified_sources


class VerifiedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / 'data/chunking_output/documents/L01.json').read_text(encoding='utf-8'))

    def test_overlay_is_idempotent_and_retains_extracted_metadata(self):
        before = copy.deepcopy(self.doc)
        apply_verified_sources(self.doc)
        self.assertEqual(self.doc, before)
        self.assertEqual(self.doc['metadata']['effective_date'], '2015-01-01')
        self.assertEqual(self.doc['extracted_metadata']['effective_date'], '2025-07-01')

    def test_missing_articles_are_restored_with_pdf_provenance(self):
        self.doc['articles'] = [a for a in self.doc['articles'] if int(a['article_number']) <= 131]
        apply_verified_sources(self.doc)
        self.assertEqual(len(self.doc['articles']), 133)
        self.assertEqual(self.doc['articles'][-1]['source_page'], 43)
        self.assertIn('2015', self.doc['articles'][-2]['clauses'][0]['clause_text'])

    def test_conflicting_supplement_is_rejected(self):
        self.doc['articles'][-1]['clauses'][0]['clause_text'] = 'Incorrect legal text'
        with self.assertRaisesRegex(ValueError, 'Conflicting supplement'):
            apply_verified_sources(self.doc)

    def test_wrong_document_number_is_rejected(self):
        self.doc['metadata']['document_number'] = 'different law'
        with self.assertRaisesRegex(ValueError, 'number mismatch'):
            apply_verified_sources(self.doc)


if __name__ == '__main__':
    unittest.main()
