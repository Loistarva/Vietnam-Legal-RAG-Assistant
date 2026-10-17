"""
test_chunking.py — Unit tests and validation for the chunking module and chunk_parsed_file API.
Kiểm thử toàn diện trên cả 2 thư mục dữ liệu:
  - data/parser_validated/*.json (L02, ND04, ND05)
  - parser/parsed_jsons/*.json (luat_52, nd_126, nd_158, nd_207, nq_01, tt_32, tt_34, ttlt_01)
  - data/sample_documents.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chunking.chunking_rules import (
    chunk_parsed_file,
    chunk_legal_document,
    chunk_legal_documents,
    ChunkResult,
    ParentChunk,
    ChildChunk,
)


class TestChunkingModule(unittest.TestCase):
    def setUp(self):
        self.base_dir = PROJECT_ROOT
        self.validated_dir = self.base_dir / "data" / "parser_validated"
        self.parsed_dir = self.base_dir / "parser" / "parsed_jsons"

    def test_chunk_parsed_validated_data(self):
        """Kiểm tra chunking trên các file mới được kiểm định trong data/parser_validated/ (L02, ND04, ND05)."""
        validated_files = sorted(list(self.validated_dir.glob("*.json")))
        self.assertGreaterEqual(len(validated_files), 3, "Phải có ít nhất 3 file trong data/parser_validated/")

        for fpath in validated_files:
            with self.subTest(file=fpath.name):
                result = chunk_parsed_file(fpath)
                self.assertIsInstance(result, ChunkResult, f"{fpath.name} phải trả về ChunkResult")
                self.assertTrue(result.doc_id, f"{fpath.name} phải có doc_id hợp lệ")
                self.assertGreater(len(result.parents), 0, f"{fpath.name} phải có ít nhất 1 parent chunk")
                self.assertGreater(len(result.children), 0, f"{fpath.name} phải có ít nhất 1 child chunk")

                # Kiểm tra độ dài parent chunks không vượt quá ngưỡng an toàn
                for p in result.parents:
                    self.assertLessEqual(len(p.text), 1800, f"Parent {p.parent_id} trong {fpath.name} quá dài: {len(p.text)}")

                # Kiểm tra DB payloads
                es_docs = result.get_elasticsearch_docs()
                qdrant_payloads = result.get_qdrant_payloads()
                parent_stores = result.get_parent_store_records()

                self.assertEqual(len(es_docs), len(result.children))
                self.assertEqual(len(qdrant_payloads), len(result.children))
                self.assertEqual(len(parent_stores), len(result.parents))

    def test_chunk_parsed_jsons_folder(self):
        """Kiểm tra chunking trên toàn bộ các file trong parser/parsed_jsons/."""
        parsed_files = sorted(list(self.parsed_dir.glob("*.json")))
        self.assertGreater(len(parsed_files), 0, "Phải có file JSON trong parser/parsed_jsons/")

        for fpath in parsed_files:
            with self.subTest(file=fpath.name):
                result = chunk_parsed_file(fpath)
                self.assertIsInstance(result, ChunkResult)
                self.assertGreater(len(result.parents), 0)
                self.assertGreater(len(result.children), 0)

    def test_chunk_parsed_file_list_json(self):
        """Kiểm tra chunk_parsed_file với file chứa mảng danh sách (data/sample_documents.json)."""
        sample_path = self.base_dir / "data" / "sample_documents.json"
        if sample_path.exists():
            result = chunk_parsed_file(sample_path)
            self.assertTrue(isinstance(result, (ChunkResult, list)))
            if isinstance(result, ChunkResult):
                self.assertGreater(len(result.parents), 0)
                # Đảm bảo unpack được các chunks chi tiết bên trong clause
                self.assertGreaterEqual(len(result.children), 2, "sample_documents phải sinh ra ít nhất 2 child chunks")

    def test_semantic_id_format_compliance(self):
        """Kiểm tra ID tuân thủ nghiêm ngặt regex ^[a-zA-Z0-9_]+$ (không dấu tiếng Việt, không ký tự lạ)."""
        import re
        test_file = self.validated_dir / "ND04.json"
        result = chunk_parsed_file(test_file)

        id_pattern = re.compile(r"^[a-zA-Z0-9_]+$")
        for p in result.parents:
            self.assertTrue(
                bool(id_pattern.match(p.parent_id)),
                f"Parent ID '{p.parent_id}' không tuân thủ regex ^[a-zA-Z0-9_]+$"
            )

        for c in result.children:
            self.assertTrue(
                bool(id_pattern.match(c.chunk_id)),
                f"Child ID '{c.chunk_id}' không tuân thủ regex ^[a-zA-Z0-9_]+$"
            )

    def test_cross_module_embedding_compatibility(self):
        """Kiểm tra tính tương thích 100% của Child Chunk payloads với embedding/vector_store.py::_normalize_chunk."""
        from embedding.vector_store import _normalize_chunk

        all_files = sorted(list(self.validated_dir.glob("*.json")) + list(self.parsed_dir.glob("*.json")))
        for fpath in all_files:
            with self.subTest(file=fpath.name):
                res = chunk_parsed_file(fpath)
                res_list = res if isinstance(res, list) else [res]
                for r in res_list:
                    payloads = r.get_qdrant_payloads()
                    ids = [p["id"] for p in payloads]
                    # Đảm bảo tuyệt đối không có chunk ID trùng lặp trong mỗi văn bản
                    self.assertEqual(len(ids), len(set(ids)), f"Phát hiện chunk ID trùng lặp trong {fpath.name}")
                    for p in payloads:
                        norm = _normalize_chunk(p)
                        self.assertTrue(norm["chunk_id"])
                        self.assertTrue(norm["text"])
                        self.assertIsInstance(norm["metadata"], dict)
                        self.assertTrue(norm["embed_text"])


if __name__ == "__main__":
    unittest.main()


