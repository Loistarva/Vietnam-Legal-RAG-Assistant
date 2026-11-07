import hashlib
import tempfile
import unittest
from pathlib import Path

from embedding.vector_store import chunk_file_sha256
from evaluation.test_run_freeze import _file_sha256


class CorpusHashTest(unittest.TestCase):
    def test_crlf_and_lf_corpus_give_the_same_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            lf = Path(tmp) / "lf.jsonl"
            crlf = Path(tmp) / "crlf.jsonl"
            lf.write_bytes(b'{"chunk_id": "a"}\n{"chunk_id": "b"}\n')
            crlf.write_bytes(b'{"chunk_id": "a"}\r\n{"chunk_id": "b"}\r\n')
            self.assertEqual(chunk_file_sha256(lf), chunk_file_sha256(crlf))
            self.assertEqual(chunk_file_sha256(lf), hashlib.sha256(lf.read_bytes()).hexdigest())
            # Kết quả retrieval và manifest Test phải ghi cùng một hash corpus.
            self.assertEqual(chunk_file_sha256(crlf), _file_sha256(crlf))


if __name__ == "__main__":
    unittest.main()
