import unittest

from evaluation.citation_parser import _parse_provisions, parse_citations
from evaluation.document_aliases import build_alias_map


class ProvisionParsingTest(unittest.TestCase):
    def setUp(self):
        self.alias_map = build_alias_map([{
            "document_id": "luat_hon_nhan_gia_dinh_2014",
            "document_number": "52/2014/QH13",
            "file_code": "52_2014",
            "title": "Luật hôn nhân và gia đình 2014",
            "document_type": "Luật",
            "issue_date": "2014-06-19",
            "effective_from": "2015-01-01",
        }])

    def test_vietnamese_words_are_not_mistaken_for_provisions(self):
        phrases = (
            "điều kiện kết hôn",
            "điều này là sai",
            "khoản nợ chung",
            "khoản tiền cấp dưỡng",
            "khoản chi phí",
            "điểm nóng",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(_parse_provisions(phrase), [])

    def test_non_numeric_clause_and_point_words_do_not_attach_to_article(self):
        cases = (
            ("Khoản nợ chung được xác định theo Điều 8.", None, None),
            ("Điểm nóng được đề cập tại Điều 8.", None, None),
            ("Điều kiện kết hôn được quy định tại Điều 8.", None, None),
        )
        for text, clause_number, point in cases:
            with self.subTest(text=text):
                provisions = _parse_provisions(text)
                self.assertEqual(len(provisions), 1)
                self.assertEqual(provisions[0]["article_number"], "8")
                self.assertEqual(provisions[0]["clause_number"], clause_number)
                self.assertEqual(provisions[0]["point"], point)

    def test_public_parser_does_not_emit_citations_for_prose(self):
        phrases = (
            "điều kiện kết hôn",
            "điều này là sai",
            "khoản nợ chung",
            "khoản tiền cấp dưỡng",
            "khoản chi phí",
            "điểm nóng",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(parse_citations(phrase, self.alias_map), [])

    def test_public_parser_keeps_valid_numeric_and_lettered_citation(self):
        citations = parse_citations(
            "Theo Khoản 1 Điều 8, điểm đ của Luật Hôn nhân và Gia đình 2014.",
            self.alias_map,
        )
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["article_number"], "8")
        self.assertEqual(citations[0]["clause_number"], "1")
        self.assertEqual(citations[0]["point"], "đ")
        self.assertEqual(citations[0]["document_id"], "luat_hon_nhan_gia_dinh_2014")

    def test_numeric_article_clause_and_lettered_point_are_preserved(self):
        provision = _parse_provisions("Khoản 1 Điều 8, điểm đ")[0]
        self.assertEqual(provision["article_number"], "8")
        self.assertEqual(provision["clause_number"], "1")
        self.assertEqual(provision["point"], "đ")

    def test_alphanumeric_provision_suffixes_are_preserved(self):
        provision = _parse_provisions("Khoản 1a Điều 8a, điểm đ")[0]
        self.assertEqual(provision["article_number"], "8a")
        self.assertEqual(provision["clause_number"], "1a")
        self.assertEqual(provision["point"], "đ")


if __name__ == "__main__":
    unittest.main()
