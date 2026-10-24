"""
test_chunking.py — Unit tests cho module chunking.

Kiểm thử trên toàn bộ parser/parsed_jsons/*.json (cùng nguồn với export_legal_chunks.py)
và trên các văn bản tổng hợp nhỏ cho từng quy tắc:
  - mỗi chunk thuộc đúng 1 Khoản, chunk_id = {clause_id}_chunk_{n}
  - Điều không chia Khoản không ghi "Khoản 1"
  - breadcrumb của Child chỉ có Khoản của chính nó
  - intro của Điều và câu dẫn danh sách Điểm nằm trong embed_text, không nằm trong text
  - Khoản dài có danh sách Điểm được cắt tại ranh giới Điểm
  - Parent không vượt PARENT_MAX_CHARS kể cả khi intro trùng Khoản đầu dài
  - thiếu underthesea thì báo lỗi
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chunking.chunking_rules import (  # noqa: E402
    CHILD_MAX_UNITS,
    CHILD_MIN_CHARS,
    PARENT_MAX_CHARS,
    ChunkResult,
    chunk_legal_document,
    chunk_parsed_file,
    is_implicit_clause,
    split_point_list,
    word_segment,
)

PARSED_DIR = PROJECT_ROOT / "parser" / "parsed_jsons"
KHOAN_SEGMENT_RE = re.compile(r"Khoản \S+")


def _doc(articles: list[dict], doc_id: str = "tt_99_2099_tt_test") -> dict:
    return {
        "document_id": doc_id,
        "metadata": {
            "title": "Thông tư thử nghiệm",
            "document_type": "Thông tư",
            "document_number": "99/2099/TT-TEST",
            "issue_date": "2099-01-01",
            "effective_date": "2099-01-01",
            "issuing_body": "Bộ Thử nghiệm",
            "validity_status": "Còn hiệu lực",
        },
        "articles": articles,
    }


def _article(number: int, clauses: list[str], intro: str | None = None, title: str = "Quy định thử") -> dict:
    art_id = f"tt_99_2099_tt_test_art_{number}"
    return {
        "article_id": art_id,
        "article_number": str(number),
        "article_title": title,
        "chapter": "Chương I QUY ĐỊNH CHUNG",
        "section": None,
        "intro": intro,
        "clauses": [
            {
                "clause_id": f"{art_id}_clause_{i}",
                "parent_article_id": art_id,
                "clause_number": str(i),
                "clause_text": text,
                "chunks": None,
            }
            for i, text in enumerate(clauses, start=1)
        ],
    }


def _sentence(n_words: int, word: str = "quy định") -> str:
    words = (word.split() * n_words)[:n_words]
    return " ".join(words) + "."


class TestChunkingOnParsedJsons(unittest.TestCase):
    """Bất biến trên mọi văn bản parser hiện có."""

    @classmethod
    def setUpClass(cls):
        cls.docs: dict[str, dict] = {}
        cls.results: dict[str, ChunkResult] = {}
        for fpath in sorted(PARSED_DIR.glob("*.json")):
            with open(fpath, encoding="utf-8") as f:
                cls.docs[fpath.name] = json.load(f)
            cls.results[fpath.name] = chunk_parsed_file(fpath)

    def test_parsed_jsons_present(self):
        self.assertGreater(len(self.docs), 0, "Phải có file JSON trong parser/parsed_jsons/")

    def test_size_limits_and_ids(self):
        for name, res in self.results.items():
            with self.subTest(file=name):
                self.assertGreater(len(res.parents), 0)
                self.assertGreater(len(res.children), 0)
                for p in res.parents:
                    self.assertLessEqual(len(p.text), PARENT_MAX_CHARS, p.parent_id)
                ids = [c.chunk_id for c in res.children]
                self.assertEqual(len(ids), len(set(ids)), "chunk_id trùng")
                clause_ids = {
                    cl["clause_id"] for a in self.docs[name]["articles"] for cl in (a.get("clauses") or [])
                }
                for c in res.children:
                    self.assertGreaterEqual(len(c.text), CHILD_MIN_CHARS, c.chunk_id)
                    self.assertLessEqual(len(c.text.split()), CHILD_MAX_UNITS, c.chunk_id)
                    self.assertRegex(c.chunk_id, rf"^{re.escape(c.clause_id)}_chunk_\d+$")
                    self.assertEqual(c.parent_clause_id, c.clause_id)
                    self.assertIn(c.clause_id, clause_ids)
                    self.assertTrue(c.seg_text and c.embed_text)

    def test_implicit_clause_has_no_khoan(self):
        checked = 0
        for name, res in self.results.items():
            implicit_ids = {
                cl["clause_id"]
                for a in self.docs[name]["articles"]
                if is_implicit_clause(a.get("clauses") or [])
                for cl in a["clauses"]
            }
            for c in res.children:
                if c.clause_id in implicit_ids:
                    checked += 1
                    self.assertIsNone(c.clause_ref, c.chunk_id)
                    self.assertIsNone(c.metadata.get("clause_number"), c.chunk_id)
                    self.assertNotIn("Khoản 1", c.embed_text_raw.split(c.text)[0], c.chunk_id)
        self.assertGreater(checked, 0)

    def test_child_breadcrumb_has_only_own_clause(self):
        for name, res in self.results.items():
            for c in res.children:
                khoan = [s for s in c.breadcrumb.split(" > ") if KHOAN_SEGMENT_RE.fullmatch(s)]
                self.assertEqual(khoan, [c.clause_ref] if c.clause_ref else [], f"{name} {c.chunk_id}: {c.breadcrumb}")

    def test_article_intro_in_embed_text_only(self):
        res = self.results["l_52_2014_qh13.json"]
        intro = "Trong Luật này, các từ ngữ dưới đây được hiểu như sau:"
        art3 = [c for c in res.children if c.article_id == "l_52_2014_qh13_art_3"]
        self.assertGreater(len(art3), 1)
        for c in art3:
            self.assertIn(intro, c.embed_text_raw)
            self.assertNotIn(intro, c.text)

    def test_point_list_split_at_point_boundaries(self):
        res = self.results["l_52_2014_qh13.json"]
        parts = [c for c in res.children if c.clause_id == "l_52_2014_qh13_art_5_clause_2"]
        self.assertGreater(len(parts), 1)
        for c in parts:
            self.assertRegex(c.point_ref or "", r"^Điểm [a-zđ](-[a-zđ])?$")
            self.assertTrue(c.breadcrumb.endswith(c.point_ref))
        for c in parts[1:]:
            self.assertRegex(c.text, r"^[a-zđ]\) ")
            self.assertIn("Cấm các hành vi sau đây:", c.embed_text_raw)
            self.assertNotIn("Cấm các hành vi sau đây:", c.text)

    def test_vector_store_accepts_payloads(self):
        from embedding.vector_store import normalize_chunk_record

        for c in self.results["l_52_2014_qh13.json"].children:
            norm = normalize_chunk_record(c.to_qdrant_payload())
            self.assertEqual(norm["chunk_id"], c.chunk_id)


class TestChunkingRules(unittest.TestCase):
    """Các quy tắc trên văn bản tổng hợp."""

    def test_split_point_list_requires_letter_sequence(self):
        self.assertIsNone(split_point_list("Áp dụng theo điểm a) khoản 1 Điều 5 của Luật này."))
        self.assertIsNone(split_point_list("Hồ sơ gồm: a) Tờ khai; c) Giấy tờ khác."))
        lead, points = split_point_list("2. Cấm các hành vi sau đây: a) Kết hôn giả tạo; b) Tảo hôn; đ) X; c) Bạo lực.")
        self.assertEqual(lead, "2. Cấm các hành vi sau đây:")
        self.assertEqual([p[0] for p in points], ["a", "b", "c"])

    def test_duplicate_intro_of_long_first_clause_keeps_parent_limit(self):
        # Như NĐ 68/2002 Điều 39: intro trùng nguyên văn khoản 1 dài hơn 190 từ.
        long_clause = " ".join(_sentence(20) for _ in range(12))
        doc = _doc([_article(1, [long_clause], intro=long_clause, title="")])
        res = chunk_legal_document(doc)
        self.assertGreater(len(res.children), 1)
        for p in res.parents:
            self.assertLessEqual(len(p.text), PARENT_MAX_CHARS)

    def test_intro_and_first_clause_fit_first_parent(self):
        # header + intro (~420 ký tự) + khoản 1 (~1.080 ký tự) > 1.500: khoản 1 phải tách nhỏ hơn.
        intro = _sentence(120, "căn cứ")
        clauses = [_sentence(180, "trách nhiệm") for _ in range(4)]
        res = chunk_legal_document(_doc([_article(2, [f"{i}. {t}" for i, t in enumerate(clauses, 1)], intro=intro)]))
        for p in res.parents:
            self.assertLessEqual(len(p.text), PARENT_MAX_CHARS)
        self.assertIn(intro, res.parents[0].text)
        self.assertGreater(sum(c.clause_id.endswith("_clause_1") for c in res.children), 1)

    def test_intro_too_long_raises(self):
        intro = _sentence(230, "trách nhiệm")
        with self.assertRaises(ValueError):
            chunk_legal_document(_doc([_article(3, ["1. " + _sentence(150), "2. " + _sentence(30)], intro=intro)]))

    def test_short_fragment_rebalanced_within_clause(self):
        clause = "1. " + " ".join([_sentence(100), _sentence(85, "hồ sơ"), _sentence(8, "thời hạn")])
        doc = _doc([_article(4, [clause, "2. " + _sentence(30)])])
        merged = [c for c in chunk_legal_document(doc).children if c.clause_id.endswith("_clause_1")]
        strict = [
            c for c in chunk_legal_document(doc, {"child_min_words": 1}).children
            if c.clause_id.endswith("_clause_1")
        ]
        self.assertEqual(min(len(c.text.split()) for c in strict), 8)
        self.assertGreaterEqual(min(len(c.text.split()) for c in merged), 20)
        self.assertEqual(Counter(" ".join(c.text for c in merged).split()), Counter(clause.split()))

    def test_short_clauses_are_not_merged_across_clauses(self):
        doc = _doc([_article(5, ["1. Ngắn một.", "2. Ngắn hai.", "3. Ngắn ba."])])
        res = chunk_legal_document(doc)
        self.assertEqual([c.clause_ref for c in res.children], ["Khoản 1", "Khoản 2", "Khoản 3"])
        self.assertEqual(res.parents[0].clause_refs, "Khoản 1-3")

    def test_word_segment_requires_underthesea(self):
        with mock.patch.dict(sys.modules, {"underthesea": None}):
            with self.assertRaises(RuntimeError):
                word_segment("Kết hôn")


if __name__ == "__main__":
    unittest.main()
