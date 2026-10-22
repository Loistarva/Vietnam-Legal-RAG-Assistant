"""
Unit/reference tests for the parser output of Luật Hôn nhân và gia đình 2014.

Expected project layout:
  Vietnam-Legal-RAG-Assistant/
    parser/
      test_parser_unit.py
      cleaned_texts/L01.txt
      parsed_jsons/l_52_2014_qh13.json

Run from the repository root:
  python -m pytest parser/test_parser_unit.py -v

If your input files have different names or locations, set:
  LEGAL_SOURCE_TXT=path/to/L01.txt
  LEGAL_PARSED_JSON=path/to/l_52_2014_qh13.json
"""
import json
import os
import re
from pathlib import Path

import pytest

from parser import parse_text_to_articles


# This test file lives inside <repo>/parser, so parents[1] is the repository root.
PARSER_DIR = Path(__file__).resolve().parent
ROOT = PARSER_DIR.parent

SOURCE_TXT = Path(os.getenv(
    "LEGAL_SOURCE_TXT", PARSER_DIR / "cleaned_texts" / "L01.txt"
))
PARSED_JSON = Path(os.getenv(
    "LEGAL_PARSED_JSON", PARSER_DIR / "parsed_jsons" / "l_52_2014_qh13.json"
))


# Fixed expectations based on the supplied document. Clause counts are focused
# regression cases, not a complete inventory of every article.
REFERENCE = {
    "document_id": "l_52_2014_qh13",
    "metadata": {
        "title": "Luật Hôn nhân và gia đình",
        "document_type": "Luật",
        "document_number": "52/2014/QH13",
        "issue_date": "2014-06-19",
        "effective_date": "2015-01-01",
        "issuing_body": "Quốc hội",
    },
    "article_count": 133,
    "chapter_count": 9,
    "clause_counts": {
        "1": 1,
        "2": 5,
        "3": 25,
        "4": 3,
        "5": 4,
        "7": 2,
        "8": 2,
        "9": 2,
        "10": 3,
        "11": 4,
        "12": 3,
        "14": 2,
        "16": 2,
        "19": 2,
        "24": 3,
        "28": 3,
        "29": 3,
        "30": 2,
    },
}


@pytest.fixture(scope="module")
def source_text():
    if not SOURCE_TXT.exists():
        pytest.fail(
            f"Không tìm thấy TXT nguồn: {SOURCE_TXT}. "
            "Hãy kiểm tra parser/cleaned_texts/L01.txt hoặc đặt biến "
            "LEGAL_SOURCE_TXT."
        )
    return SOURCE_TXT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed():
    if not PARSED_JSON.exists():
        pytest.fail(
            f"Không tìm thấy JSON parser: {PARSED_JSON}. "
            "Hãy kiểm tra parser/parsed_jsons/l_52_2014_qh13.json hoặc đặt biến "
            "LEGAL_PARSED_JSON."
        )
    return json.loads(PARSED_JSON.read_text(encoding="utf-8"))


def articles_by_number(parsed_data):
    return {
        str(article["article_number"]): article
        for article in parsed_data["articles"]
    }


def test_document_metadata_matches_reference(parsed):
    assert parsed["document_id"] == REFERENCE["document_id"]
    metadata = parsed["metadata"]
    for field, expected in REFERENCE["metadata"].items():
        assert metadata.get(field) == expected, (
            f"Metadata {field}: kỳ vọng {expected!r}, nhận {metadata.get(field)!r}"
        )


def test_article_count_and_sequence(parsed):
    numbers = [int(article["article_number"]) for article in parsed["articles"]]
    assert len(numbers) == REFERENCE["article_count"]
    assert numbers == list(range(1, REFERENCE["article_count"] + 1)), (
        "Số Điều bị thiếu, trùng hoặc không liên tục"
    )


def test_chapter_count(parsed):
    chapters = {
        article.get("chapter")
        for article in parsed["articles"]
        if article.get("chapter")
    }
    assert len(chapters) == REFERENCE["chapter_count"]


@pytest.mark.parametrize(
    ("article_number", "expected_count"),
    sorted(REFERENCE["clause_counts"].items(), key=lambda item: int(item[0])),
)
def test_known_article_clause_counts(parsed, article_number, expected_count):
    articles = articles_by_number(parsed)
    assert article_number in articles, f"Không tìm thấy Điều {article_number}"
    actual_count = len(articles[article_number].get("clauses", []))
    assert actual_count == expected_count, (
        f"Điều {article_number}: kỳ vọng {expected_count} Khoản, "
        f"thực tế {actual_count} Khoản"
    )


def test_clause_numbers_are_contiguous_when_numbered(parsed):
    for article in parsed["articles"]:
        clauses = article.get("clauses", [])
        numbers = [str(c.get("clause_number", "")).strip() for c in clauses]
        if numbers and all(number.isdigit() for number in numbers):
            expected = [str(i) for i in range(1, len(numbers) + 1)]
            assert numbers == expected, (
                f"Điều {article['article_number']} có số Khoản bất thường: {numbers}"
            )


def test_no_null_bytes_in_content(parsed):
    for article in parsed["articles"]:
        values = [article.get("article_title") or "", article.get("intro") or ""]
        values.extend(
            clause.get("clause_text") or ""
            for clause in article.get("clauses", [])
        )
        for value in values:
            assert "\x00" not in value, (
                f"Null byte ở Điều {article['article_number']}"
            )


def test_no_url_or_page_header_noise_in_clause_text(parsed):
    url_re = re.compile(r"https?://|www\.", re.IGNORECASE)
    noise_patterns = [
        re.compile(
            r"^\s*(?:CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM|"
            r"Độc lập\s*-\s*Tự do\s*-\s*Hạnh phúc)\s*$",
            re.IGNORECASE,
        ),
        re.compile(r"^\s*(?:Trang|Page)\s+\d+(?:\s*/\s*\d+)?\s*$", re.IGNORECASE),
    ]
    for article in parsed["articles"]:
        for clause in article.get("clauses", []):
            value = clause.get("clause_text") or ""
            assert not url_re.search(value), (
                f"URL trong Điều {article['article_number']}, "
                f"Khoản {clause.get('clause_number')}"
            )
            assert not any(pattern.search(value) for pattern in noise_patterns), (
                f"Header/số trang trong Điều {article['article_number']}"
            )


def test_source_and_json_article_numbers_agree(source_text, parsed):
    source_numbers = [
        int(number)
        for number in re.findall(r"(?m)^\s*Điều\s+(\d{1,3})\s*\.", source_text)
    ]
    parsed_numbers = [
        int(article["article_number"]) for article in parsed["articles"]
    ]
    assert source_numbers == parsed_numbers, (
        "Danh sách số Điều trong TXT và JSON không trùng nhau. "
        "Nếu TXT chứa mục lục/chú thích có dạng 'Điều N.', hãy tinh chỉnh regex."
    )

# ---------------------------------------------------------------------------
# Regression tests: title/intro splitting when source TXT preserves line breaks
# ---------------------------------------------------------------------------
TITLE_TEST_DIR = Path(__file__).resolve().parent
ND126_TXT = Path(os.getenv(
    "LEGAL_ND126_SOURCE_TXT", TITLE_TEST_DIR / "cleaned_texts" / "ND01.txt"
))
NQ012024_TXT = Path(os.getenv(
    "LEGAL_NQ012024_SOURCE_TXT", TITLE_TEST_DIR / "cleaned_texts" / "ND03.txt"
))


@pytest.fixture(scope="module")
def nd126_articles():
    if not ND126_TXT.is_file():
        pytest.skip(f"Không có TXT nguồn NĐ 126/2014: {ND126_TXT}")
    articles, _ = parse_text_to_articles(
        ND126_TXT.read_text(encoding="utf-8"),
        "nd_126_2014_nd_cp",
    )
    return {str(a["article_number"]): a for a in articles}


@pytest.fixture(scope="module")
def nq012024_articles():
    if not NQ012024_TXT.is_file():
        pytest.skip(f"Không có TXT nguồn NQ 01/2024: {NQ012024_TXT}")
    articles, _ = parse_text_to_articles(
        NQ012024_TXT.read_text(encoding="utf-8"),
        "nq_01_2024_nq_hdtp",
    )
    return {str(a["article_number"]): a for a in articles}


@pytest.mark.parametrize(
    ("number", "expected_title", "expected_intro_start"),
    [
        ("29", "Từ chối cấp giấy xác nhận tình trạng hôn nhân cho công dân Việt Nam cư trú trong nước để kết hôn với người nước ngoài tại cơ quan có thẩm quyền của nước ngoài", "Yêu cầu cấp giấy xác nhận tình trạng hôn nhân"),
        ("53", "Điều kiện thành lập Trung tâm", "Hội Liên hiệp phụ nữ quyết định thành lập Trung tâm"),
        ("58", "Nhiệm vụ, quyền hạn của Bộ Tư pháp", "Bộ Tư pháp chịu trách nhiệm"),
        ("59", "Nhiệm vụ, quyền hạn của Bộ Ngoại giao", "Bộ Ngoại giao thực hiện"),
        ("61", "Nhiệm vụ, quyền hạn của Bộ Công an", "Bộ Công an thực hiện"),
    ],
)
def test_nd126_title_and_intro_are_split_by_lines(
    nd126_articles, number, expected_title, expected_intro_start
):
    article = nd126_articles[number]
    assert article["article_title"] == expected_title
    assert (article.get("intro") or "").startswith(expected_intro_start)


def test_nq012024_article10_title_is_not_cut_at_vietnam(nq012024_articles):
    article = nq012024_articles["10"]
    assert article["article_title"] == (
        "Giải quyết vụ án ly hôn có bị đơn là người Việt Nam ở nước ngoài nhưng không rõ địa chỉ"
    )
    assert (article.get("intro") or "").startswith("Trong vụ án ly hôn,")


def test_nd126_article62_body_is_not_absorbed_into_title(nd126_articles):
    article = nd126_articles["62"]
    assert article["article_title"] == (
        "Nhiệm vụ của các Bộ, cơ quan ngang Bộ, cơ quan thuộc Chính phủ"
    )
    assert article["clauses"][0]["clause_text"].startswith(
        "Các Bộ, cơ quan ngang Bộ, cơ quan thuộc Chính phủ"
    )

