import json
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'embedding'))
from fit_token_budget import split_record, remap_questions


class TokenBudgetTests(unittest.TestCase):
    def test_lossless_split_repeats_context_and_preserves_metadata(self):
        text = 'Văn bản: X\nĐiều 1: Y\nDẫn nhập điều: ' + 'nội dung. ' * 30 + '\nKhoản 1: kết thúc.'
        original = {'id': 'example', 'text': text, 'embed_text': text,
                    'parent_id': 'clause_1', 'source_file': 'source.pdf'}
        count = lambda s: len(s.split()) + 2
        pieces = split_record(original, count, 25)
        prefix_len = pieces[0]['repeated_context_chars']
        self.assertEqual(text[:prefix_len] + ''.join(p['text'][prefix_len:] for p in pieces), text)
        self.assertTrue(all(count(p['embed_text']) <= 25 for p in pieces))
        self.assertTrue(all(p['parent_id'] == 'clause_1' and p['source_file'] == 'source.pdf' for p in pieces))
        self.assertEqual(original['text'], text)

    def test_fitting_record_keeps_id_and_content(self):
        original = {'id': 'fits', 'text': 'short text', 'embed_text': 'short text'}
        self.assertEqual(split_record(original, lambda s: 5, 256), [original])

    def test_unrepresentable_header_fails_without_truncation(self):
        record = {'id': 'bad', 'text': 'header too long\nKhoản 1: body', 'embed_text': 'oversized'}
        with self.assertRaisesRegex(ValueError, 'single word exceeds'):
            split_record(record, lambda s: 999, 256)

    def test_remaps_all_relevant_parts_and_keeps_draft_status(self):
        questions = [{'query': 'Q', 'relevant_chunk_ids': ['a', 'b'], 'review_status': 'draft'}]
        result = remap_questions(questions, {'a': ['a_part1', 'a_part2'], 'b': ['b']})
        self.assertEqual(result[0]['relevant_chunk_ids'], ['a_part1', 'a_part2', 'b'])
        self.assertEqual(result[0]['review_status'], 'draft')

    def test_generated_dataset_reconstructs_every_source_chunk(self):
        def read(name):
            return json.loads((ROOT / 'embedding/data' / name).read_text(encoding='utf-8'))
        source = read('priority_chunks.json')['chunks']
        derived = {c['id']: c for c in read('priority_bkai_chunks.json')['chunks']}
        mapping = read('priority_bkai_id_map.json')['id_map']
        for original in source:
            pieces = [derived[cid] for cid in mapping[original['id']]]
            if len(pieces) == 1 and pieces[0]['id'] == original['id']:
                self.assertEqual(pieces[0], original)
                continue
            prefix_len = pieces[0]['repeated_context_chars']
            self.assertEqual(original['text'][:prefix_len] + ''.join(p['text'][prefix_len:] for p in pieces), original['text'])
            for p in pieces:
                for field in ['source_file', 'source_url', 'source_page', 'parent_id', 'clause_id', 'validity_status']:
                    self.assertEqual(p.get(field), original.get(field))

    def test_derived_labels_match_fixture_hash_and_all_ids(self):
        folder = ROOT / 'embedding/data'
        data = (folder / 'priority_bkai_chunks.json').read_bytes()
        ids = {c['id'] for c in json.loads(data)['chunks']}
        labels = json.loads((folder / 'priority_bkai_questions.draft.json').read_text(encoding='utf-8'))
        self.assertEqual(labels['dataset_sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(len(labels['questions']), 50)
        self.assertEqual(sum(q['split'] == 'dev' for q in labels['questions']), 10)
        for q in labels['questions']:
            self.assertTrue(q['relevant_chunk_ids'])
            self.assertTrue(all(cid in ids for cid in q['relevant_chunk_ids']))


if __name__ == '__main__':
    unittest.main()
