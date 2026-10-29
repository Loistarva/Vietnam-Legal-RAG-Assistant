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

Corpus-wide tests (chạy trên MỌI văn bản, không chỉ Luật 52/2014 và NĐ 126/2014):
  LEGAL_CORPUS_TXT_DIR=path/to/cleaned_texts     (mặc định parser/cleaned_texts,
                                                  hoặc parser/cleanned_texts nếu có)
  LEGAL_PARSED_JSON_DIR=path/to/parsed_jsons     (mặc định thư mục chứa LEGAL_PARSED_JSON)
"""
import functools
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

from parser.parser import extract_document_number, parse_text_to_articles


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
        "title": "Luật Hôn nhân và gia đình 2014",
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
    # Nhận "Điều N." và "Điều N" đứng riêng một dòng (TXT trích từ một số PDF
    # không có dấu chấm sau số Điều).
    source_numbers = [
        int(number)
        for number in re.findall(
            r"(?m)^[ \t]*Điều[ \t]+(\d{1,3})(?:[ \t]*\.|[ \t]*$)", source_text
        )
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


# ===========================================================================
# Corpus-wide tests (A24 / A25 / A23 / lỗi (4))
#
# Các test ở trên chỉ bao phủ Luật 52/2014 và 2 văn bản (NĐ 126/2014, NQ 01/2024).
# Phần dưới chạy trên TẤT CẢ TXT trong cleaned_texts và JSON trong parsed_jsons,
# để một văn bản mới parse sai không còn lọt qua trước khi commit.
# ===========================================================================
def _first_existing_dir(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


CORPUS_TXT_DIR = Path(os.getenv("LEGAL_CORPUS_TXT_DIR") or _first_existing_dir(
    PARSER_DIR / "cleaned_texts", PARSER_DIR / "cleanned_texts"
))
PARSED_JSON_DIR = Path(os.getenv("LEGAL_PARSED_JSON_DIR") or PARSED_JSON.parent)

# TXT mà parser CHƯA hỗ trợ (chia theo mục La Mã, không có "Điều"). Khi parser hỗ trợ
# được, test `test_known_unparseable_txt_still_fail_loudly` sẽ fail để nhắc xóa dòng ở đây.
KNOWN_UNPARSEABLE_TXT = {
}

# Tiêu đề Điều dài hơn ngưỡng này gần như chắc chắn là nội dung bị nuốt vào tiêu đề.
MAX_TITLE_WORDS_IN_CORPUS = 40
# Ngoại lệ có chủ đích: {(tên_file_txt_không_đuôi, "số Điều")}. Thêm kèm lý do khi cần.
TITLE_LENGTH_ALLOWLIST: set = {
    ("ND01", "8"),  # NĐ 126/2014 Điều 8: tiêu đề thật 44 từ
    ("TT02", "4"),  # TT 02a/2015 Điều 4: tiêu đề thật 41 từ
}
# Ngoại lệ đối chiếu số Khoản: {(tên_file_txt_không_đuôi, "số Điều"): "lý do"}.
CLAUSE_COUNT_EXEMPT: Dict[Tuple[str, str], str] = {}


def corpus_txt_files() -> List[Path]:
    return sorted(CORPUS_TXT_DIR.glob("*.txt")) if CORPUS_TXT_DIR.is_dir() else []


def corpus_json_files() -> List[Path]:
    return sorted(PARSED_JSON_DIR.glob("*.json")) if PARSED_JSON_DIR.is_dir() else []


CORPUS_TXT = corpus_txt_files()
CORPUS_JSON = corpus_json_files()


@functools.lru_cache(maxsize=None)
def parse_corpus_txt(path_str: str):
    """Parse một TXT một lần cho cả module; trả về (text_đã_NFC, articles)."""
    text = unicodedata.normalize("NFC", Path(path_str).read_text(encoding="utf-8"))
    articles, _footnotes = parse_text_to_articles(text, "doc")
    return text, articles


def parse_or_skip(txt_path: Path):
    if txt_path.name in KNOWN_UNPARSEABLE_TXT:
        pytest.skip(KNOWN_UNPARSEABLE_TXT[txt_path.name])
    return parse_corpus_txt(str(txt_path))


def starts_mid_sentence(text: Optional[str]) -> bool:
    """Chữ thường ở đầu (trừ điểm "a)", "đ)") => đoạn bị cắt giữa câu."""
    text = (text or "").strip()
    return bool(text) and text[0].islower() and not re.match(r"[a-zđ]\)", text)


def clause_is_numbered(article: dict) -> bool:
    clauses = article.get("clauses") or []
    return bool(clauses) and re.match(r"1\.\s", clauses[0]["clause_text"]) is not None


def looks_like_signer_name(fragment: str) -> bool:
    """Đoạn ngắn 2-4 từ, mỗi từ viết hoa chữ đầu, không dấu câu (vd. "Trường Chinh")."""
    words = fragment.split()
    return 2 <= len(words) <= 4 and all(w[:1].isupper() and w.isalpha() for w in words)


def txt_article_spans(text: str, article_count: int) -> Optional[List[str]]:
    """Cắt TXT thành thân từng Điều theo mốc "Điều N"/"Điều N." ở ĐẦU DÒNG.

    Trả về None nếu không tìm đủ mốc theo đúng thứ tự (TXT bị làm phẳng).
    """
    marks = []
    pos = 0
    for n in range(1, article_count + 1):
        m = re.compile(rf"(?m)^[ \t]*Điều[ \t]+{n}(?:[ \t]*\.|[ \t]*$)").search(text, pos)
        if not m:
            return None
        marks.append((m.start(), m.end()))
        pos = m.end()
    spans = []
    for i, (_start, end) in enumerate(marks):
        next_start = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        spans.append(text[end:next_start])
    return spans


def count_numbered_lines(span: str) -> int:
    """Số dòng "1.", "2.", "3."... liên tiếp ở đầu dòng (bất kể chữ hoa/thường)."""
    k = 0
    pos = 0
    while True:
        m = re.compile(rf"(?m)^[ \t]*{k + 1}\.[ \t]+\S").search(span, pos)
        if not m:
            return k
        k += 1
        pos = m.end()


def test_corpus_txt_dir_is_found_and_not_empty():
    assert CORPUS_TXT_DIR.is_dir(), (
        f"Không thấy thư mục TXT: {CORPUS_TXT_DIR}. Đặt LEGAL_CORPUS_TXT_DIR nếu khác mặc định."
    )
    assert CORPUS_TXT, f"Thư mục {CORPUS_TXT_DIR} không có file .txt nào"


def test_parsed_json_dir_is_found_and_not_empty():
    assert PARSED_JSON_DIR.is_dir(), (
        f"Không thấy thư mục JSON: {PARSED_JSON_DIR}. Đặt LEGAL_PARSED_JSON_DIR nếu khác mặc định."
    )
    assert CORPUS_JSON, f"Thư mục {PARSED_JSON_DIR} không có file .json nào"


@pytest.mark.parametrize("name", sorted(KNOWN_UNPARSEABLE_TXT))
def test_known_unparseable_txt_still_fail_loudly(name):
    path = CORPUS_TXT_DIR / name
    if not path.is_file():
        pytest.skip(f"Không có {path}")
    with pytest.raises(RuntimeError, match="Không tìm thấy Điều nào"):
        parse_text_to_articles(path.read_text(encoding="utf-8"), "doc")


every_txt = pytest.mark.parametrize(
    "txt_path", CORPUS_TXT, ids=[p.name for p in CORPUS_TXT]
)


@every_txt
def test_article_sequence_is_contiguous(txt_path):
    _text, articles = parse_or_skip(txt_path)
    numbers = [int(a["article_number"]) for a in articles]
    assert numbers == list(range(1, len(numbers) + 1))

@every_txt
def test_every_article_marker_in_txt_was_parsed(txt_path):
    """Không còn mốc "Điều N+1" ở đầu dòng trong TXT sau Điều cuối đã parse (Điều bị bỏ sót)."""
    text, articles = parse_or_skip(txt_path)
    extra = txt_article_spans(text, len(articles) + 1)
    assert extra is None, (
        f"TXT còn mốc Điều {len(articles) + 1} nhưng parser dừng ở Điều {len(articles)}"
    )


@every_txt
def test_no_article_starts_mid_sentence(txt_path):
    """A24: intro hoặc Khoản đầu không được bắt đầu giữa câu."""
    _text, articles = parse_or_skip(txt_path)
    bad = []
    for a in articles:
        if starts_mid_sentence(a.get("intro")):
            bad.append((a["article_number"], "intro", a["intro"][:60]))
        first = a["clauses"][0]["clause_text"]
        if not clause_is_numbered(a) and starts_mid_sentence(first):
            bad.append((a["article_number"], "khoản đầu", first[:60]))
    assert not bad, f"Đoạn bắt đầu giữa câu: {bad[:5]}"

@every_txt
def test_titles_are_not_absurdly_long(txt_path):
    _text, articles = parse_or_skip(txt_path)
    too_long = []
    for a in articles:
        title = a.get("article_title") or ""
        if (
            len(title.split()) > MAX_TITLE_WORDS_IN_CORPUS
            and (txt_path.stem, str(a["article_number"])) not in TITLE_LENGTH_ALLOWLIST
        ):
            too_long.append((a["article_number"], len(title.split())))
    assert not too_long, (
        f"Tiêu đề dài hơn {MAX_TITLE_WORDS_IN_CORPUS} từ (Điều, số từ): {too_long[:5]}"
    )

@every_txt
def test_untitled_documents_have_null_titles(txt_path):
    """Văn bản mà mọi "Điều N" đứng riêng một dòng thì không có tiêu đề Điều nào."""
    text, articles = parse_or_skip(txt_path)
    alone = re.findall(r"(?m)^[ \t]*Điều[ \t]+\d+[a-z]?[ \t]*\.?[ \t]*$", text)
    with_text = re.findall(r"(?m)^[ \t]*Điều[ \t]+\d+[a-z]?[ \t]*\.[ \t]*\S", text)
    if with_text or len(alone) < len(articles):
        return  # văn bản có tiêu đề Điều; kiểm tra này không áp dụng
    titled = [a["article_number"] for a in articles if a.get("article_title")]
    assert not titled, f"Văn bản không có tiêu đề Điều nhưng Điều {titled[:10]} có title"


@every_txt
def test_clause_count_matches_numbered_lines_in_txt(txt_path):
    """Số Khoản trong JSON phải bằng số dòng "1.", "2.", ... của Điều trong TXT."""
    text, articles = parse_or_skip(txt_path)
    spans = txt_article_spans(text, len(articles))
    if spans is None:
        pytest.skip("TXT không có mốc Điều ở đầu dòng; bỏ qua đối chiếu số Khoản")
    mismatches = []
    # Bỏ Điều cuối: sau nó có thể còn phụ lục/biểu mẫu có dòng "1.", "2.".
    for article, span in list(zip(articles, spans))[:-1]:
        number = str(article["article_number"])
        if (txt_path.stem, number) in CLAUSE_COUNT_EXEMPT:
            continue
        expected = count_numbered_lines(span)
        actual = len(article["clauses"]) if clause_is_numbered(article) else 0
        if expected != actual:
            mismatches.append((number, expected, actual))
    assert not mismatches, (
        "Điều có số dòng 'N.' trong TXT khác số Khoản trong JSON "
        f"(Điều, TXT, JSON): {mismatches[:10]}"
    )

@every_txt
def test_last_article_has_no_signature_tail(txt_path):
    """A21: Điều cuối không còn người ký / chức danh / nơi nhận."""
    _text, articles = parse_or_skip(txt_path)
    last_text = articles[-1]["clauses"][-1]["clause_text"].strip()
    for pattern in (
        r"\(\s*Đã\s+ký\s*\)",
        r"Nơi\s+nhận\s*:",
        r"(?:TM|KT|Q|TL)\.\s+[A-ZĐ]",
    ):
        assert not re.search(pattern, last_text), (
            f"Điều cuối còn dấu hiệu ký ban hành {pattern!r}: ...{last_text[-80:]!r}"
        )
    if not re.search(r"[.;:!?\"”)]$", last_text):
        tail = re.split(r"[.;:!?]\s+", last_text)[-1]
        assert not looks_like_signer_name(tail), f"Điều cuối kết thúc bằng tên người ký: {tail!r}"


@pytest.mark.parametrize(
    "json_path", CORPUS_JSON, ids=[p.name for p in CORPUS_JSON]
)
def test_parsed_json_identifiers_follow_contract(json_path):
    """Lỗi (4): document_id chỉ gồm [a-z0-9_], khớp tên file, id con nhất quán, số hiệu sạch."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    doc_id = data["document_id"]
    assert re.fullmatch(r"[a-z0-9_]+", doc_id), (
        f"document_id {doc_id!r} không khớp ^[a-z0-9_]+$"
    )
    assert json_path.stem == doc_id, f"Tên file {json_path.name} khác document_id {doc_id!r}"
    number = data["metadata"].get("document_number") or ""
    assert number == number.strip(), f"document_number có khoảng trắng thừa: {number!r}"
    for article in data["articles"]:
        assert article["article_id"] == f"{doc_id}_art_{article['article_number']}"
        for clause in article["clauses"]:
            assert clause["clause_id"].startswith(f"{article['article_id']}_clause_")
            assert clause["parent_article_id"] == article["article_id"]


# ---------------------------------------------------------------------------
# A23: tiêu đề/intro/chương của TT 02a/2015/TT-BTP (Điều 9, 14)
# ---------------------------------------------------------------------------
def locate_corpus_txt(marker: str) -> Optional[Path]:
    """Tìm TXT theo số hiệu văn bản trong phần đầu file (không phụ thuộc tên file)."""
    for path in CORPUS_TXT:
        head = unicodedata.normalize("NFC", path.read_text(encoding="utf-8")[:4000])
        if marker in head:
            return path
    return None


@pytest.fixture(scope="module")
def tt02a_articles():
    path = locate_corpus_txt("02a/2015/TT-BTP")
    if path is None:
        pytest.fail(f"Không tìm thấy TXT của TT 02a/2015/TT-BTP trong {CORPUS_TXT_DIR}")
    articles, _ = parse_text_to_articles(
        path.read_text(encoding="utf-8"), "tt_02a_2015_tt_btp"
    )
    return {str(a["article_number"]): a for a in articles}


@pytest.mark.parametrize(
    ("number", "expected_title", "expected_intro_start", "expected_clause1_start"),
    [
        (
            "9",
            "Trình tự giải quyết hồ sơ cấp Giấy xác nhận tình trạng hôn nhân",
            "Trình tự giải quyết hồ sơ cấp Giấy xác nhận tình trạng hôn nhân được thực hiện "
            "theo quy định tại khoản 2",
            "1. Trong trường hợp cần thiết, Sở Tư pháp",
        ),
        (
            "14",
            "Điều kiện thành lập Trung tâm",
            "Điều kiện thành lập Trung tâm thực hiện theo quy định tại Điều 53",
            "1. Địa điểm hoạt động của Trung tâm",
        ),
    ],
)
def test_tt02a_title_and_intro_are_split_correctly(
    tt02a_articles, number, expected_title, expected_intro_start, expected_clause1_start
):
    article = tt02a_articles[number]
    assert article["article_title"] == expected_title
    assert (article.get("intro") or "").startswith(expected_intro_start)
    assert article["clauses"][0]["clause_text"].startswith(expected_clause1_start)


@pytest.mark.parametrize(
    ("number", "expected_chapter_end"),
    [
        ("9", "GHI VÀO SỔ VIỆC KẾT HÔN, GHI VÀO SỔ VIỆC LY HÔN"),
        ("14", "HÔN NHÂN VÀ GIA ĐÌNH CÓ YẾU TỐ NƯỚC NGOÀI"),
    ],
)
def test_tt02a_wrapped_chapter_title_is_complete(
    tt02a_articles, number, expected_chapter_end
):
    """Tiêu đề Chương bị PDF xuống dòng phải được ghép đủ, không cụt ở dòng đầu."""
    assert tt02a_articles[number]["chapter"].endswith(expected_chapter_end)


def test_tt02a_wrapped_article_title_keeps_line_end_punctuation(tt02a_articles):
    """Dấu ";" cuối dòng của tiêu đề Điều bị xuống dòng phải giữ lại (A28)."""
    assert tt02a_articles["4"]["article_title"].startswith(
        "Đình chỉ giải quyết hồ sơ đăng ký kết hôn, nhận cha, mẹ, con có yếu tố nước ngoài; "
        "cấp Giấy xác nhận tình trạng hôn nhân;"
    )


# ---------------------------------------------------------------------------
# A28: ghép dòng không làm mất dấu câu, cụt tiêu đề hay tách số hiệu
# ---------------------------------------------------------------------------
HEADING_VALUE_RE = re.compile(r"^((?:Chương|CHƯƠNG|Mục|MỤC)\s+(?:[IVXLCDM]+|\d+))\s+(.*)$")
STRUCTURAL_WORD_RE = re.compile(r"(?:Điều|Chương|CHƯƠNG|Mục|MỤC)$")
SPLIT_HYPHEN_RE = re.compile(r"[0-9A-Za-zÀ-ỹĐđ]-\s+[0-9A-ZĐ]")


def flatten_txt(text: str) -> str:
    """TXT bỏ xuống dòng như parser: "NĐ-" + "CP" ghép liền, xuống dòng khác thành dấu cách."""
    text = re.sub(r"(?<=\w)-[ \t]*\n[ \t]*(?=[0-9A-ZĐ])", "-", text)
    return re.sub(r"\s+", " ", text)


@every_txt
def test_heading_titles_match_txt_and_are_complete(txt_path):
    """Tiêu đề Chương/Mục khớp nguyên văn TXT (cả dấu câu) và kéo tới mốc cấu trúc kế tiếp."""
    text, articles = parse_or_skip(txt_path)
    flat = flatten_txt(text)
    values = {a.get(key) for a in articles for key in ("chapter", "section")} - {None}
    bad = []
    for value in sorted(values):
        m = HEADING_VALUE_RE.match(value)
        if not m:
            bad.append((value[:60], "nhãn không đúng dạng"))
            continue
        label, title = m.groups()
        heading_re = re.compile(rf"(?i:{re.escape(label)})\s*[.:]?\s*{re.escape(title)}\s*(\S+)")
        next_words = [h.group(1) for h in heading_re.finditer(flat)]
        if not next_words:
            bad.append((value[-60:], "không khớp TXT"))
        elif not any(STRUCTURAL_WORD_RE.match(w) for w in next_words):
            bad.append((value[-60:], f"cụt, TXT còn {next_words[0]!r}"))
    assert not bad, f"Tiêu đề Chương/Mục sai: {bad[:5]}"


@every_txt
def test_article_titles_match_txt(txt_path):
    """Tiêu đề Điều khớp nguyên văn TXT ngay sau "Điều N." (không mất dấu câu khi ghép dòng)."""
    text, articles = parse_or_skip(txt_path)
    flat = flatten_txt(text)
    bad = [
        (a["article_number"], a["article_title"][:60])
        for a in articles
        if a.get("article_title")
        and not re.search(
            rf"Điều\s+{a['article_number']}\s*[.:]?\s*{re.escape(a['article_title'])}", flat
        )
    ]
    assert not bad, f"Tiêu đề Điều không khớp TXT: {bad[:5]}"


@every_txt
def test_no_number_split_after_hyphen(txt_path):
    """Số hiệu, ngày bị PDF xuống dòng sau "-" phải ghép liền ("126/2014/NĐ-CP", không "NĐ- CP")."""
    _text, articles = parse_or_skip(txt_path)
    bad = []
    for a in articles:
        fields = [a.get("article_title"), a.get("intro")] + [c["clause_text"] for c in a["clauses"]]
        for field in filter(None, fields):
            bad += [field[max(0, m.start() - 15):m.end() + 5] for m in SPLIT_HYPHEN_RE.finditer(field)]
    assert not bad, f"Số hiệu bị tách sau dấu gạch: {bad[:5]}"


# ---------------------------------------------------------------------------
# A27: cấp Mục của TT 04/2020/TT-BTP; A23: tiêu đề TTLT 01/2016 Điều 9
# ---------------------------------------------------------------------------
def parse_located_txt(marker: str, doc_id: str) -> Dict[str, dict]:
    path = locate_corpus_txt(marker)
    if path is None:
        pytest.fail(f"Không tìm thấy TXT của {marker} trong {CORPUS_TXT_DIR}")
    articles, _ = parse_text_to_articles(path.read_text(encoding="utf-8"), doc_id)
    return {str(a["article_number"]): a for a in articles}


def test_tt04_2020_sections_are_detected():
    articles = parse_located_txt("04/2020/TT-BTP", "tt_04_2020_tt_btp")
    sections = {a["section"] for a in articles.values() if a.get("section")}
    assert len(sections) == 8, sorted(sections)
    leaked = [
        c["clause_id"]
        for a in articles.values()
        for c in a["clauses"]
        if re.search(r"\bMục\s+\d+\.?\s+[A-ZĐ]{2,}", c["clause_text"])
    ]
    assert not leaked, f"Tên Mục lọt vào Khoản: {leaked[:5]}"


def test_ttlt_01_2016_article_9_title_and_body():
    article = parse_located_txt("01/2016/TTLT", "ttlt_01_2016_ttlt_tandtc")["9"]
    assert article["article_title"] == "Giải thích, sửa đổi, bổ sung Thông tư liên tịch"
    assert article["clauses"][0]["clause_text"].startswith("Trong quá trình thực hiện, nếu có vướng mắc")


# ---------------------------------------------------------------------------
# C6: Kiểm tra tính toàn vẹn của Registry và đối chiếu với hai bảng và chunks.jsonl
# ---------------------------------------------------------------------------
def test_registry_and_mapping_tables_integrity():
    repo_root = Path(__file__).resolve().parent.parent
    registry_path = repo_root / "data" / "reference" / "document_versions.json"
    data_contract_path = repo_root / "docs" / "data_contract.md"
    readme_path = repo_root / "data" / "raw_data" / "README.md"
    chunks_path = repo_root / "data" / "chunking_output" / "chunks.jsonl"

    # (a) Mọi document_id trong data/reference/document_versions.json là duy nhất và khớp regex ^[a-z0-9_]+$
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    doc_ids = [d["document_id"] for d in registry]
    assert len(doc_ids) == len(set(doc_ids)), f"Trùng document_id trong registry: {len(doc_ids)} vs {len(set(doc_ids))}"
    for did in doc_ids:
        assert re.fullmatch(r"^[a-z0-9_]+$", did), f"document_id '{did}' không khớp ^[a-z0-9_]+$"

    registry_by_id = {d["document_id"]: d for d in registry}

    # Helper parse markdown table rows from a specific section
    def parse_section_table(file_path: Path, header_marker: str):
        text = file_path.read_text(encoding="utf-8")
        if header_marker in text:
            text = text.split(header_marker, 1)[1]
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                break
            if line.startswith("|") and line.endswith("|"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4 and not parts[0].startswith(":") and not parts[0].startswith("-") and "file_code" not in parts[0] and "Kiểu dữ liệu" not in parts[1]:
                    file_code = parts[0].replace("*", "").strip()
                    doc_id = parts[1].replace("`", "").strip()
                    doc_number = parts[2].strip()
                    validity_status = parts[3].strip()
                    rows.append({
                        "file_code": file_code,
                        "document_id": doc_id,
                        "document_number": doc_number,
                        "validity_status": validity_status,
                        "title": parts[4].strip() if len(parts) >= 5 else None,
                    })
        return rows

    # (b) Mọi dòng trong bảng ánh xạ ở Mục 6 docs/data_contract.md và data/raw_data/README.md đều khớp 100% với document_versions.json
    contract_rows = parse_section_table(data_contract_path, "## 6. Bảng Ánh xạ Định danh Văn bản")
    readme_rows = parse_section_table(readme_path, "Hệ thống sử dụng bảng ánh xạ chuẩn hóa chính thức")

    assert contract_rows, "Không đọc được bảng Mục 6 của data_contract.md"
    assert readme_rows, "Không đọc được bảng ánh xạ của data/raw_data/README.md"
    contract_ids = {r["document_id"] for r in contract_rows}
    readme_ids = {r["document_id"] for r in readme_rows}
    assert readme_ids == contract_ids, f"Hai bảng ID lệch nhau: {sorted(readme_ids ^ contract_ids)}"

    for row in contract_rows:
        did = row["document_id"]
        assert did in registry_by_id, f"document_id '{did}' trong data_contract.md không có trong registry"
        reg = registry_by_id[did]
        assert row["file_code"] == reg.get("file_code"), f"file_code lệch cho '{did}'"
        assert row["document_number"] == reg.get("document_number"), f"document_number lệch cho '{did}'"
        assert row["validity_status"] == reg.get("validity_status"), f"validity_status lệch cho '{did}'"
        assert row["title"] == (reg.get("title") or "").strip(), f"title lệch cho '{did}'"

    for row in readme_rows:
        did = row["document_id"]
        assert did in registry_by_id, f"document_id '{did}' trong README.md không có trong registry"
        reg = registry_by_id[did]
        assert row["file_code"] == reg.get("file_code"), f"file_code lệch cho '{did}'"
        assert row["document_number"] == reg.get("document_number"), f"document_number lệch cho '{did}'"
        assert row["validity_status"] == reg.get("validity_status"), f"validity_status lệch cho '{did}'"
        assert row["title"] == (reg.get("title") or "").strip(), f"title lệch cho '{did}'"

    # (c) Mọi document_id xuất hiện trong data/chunking_output/chunks.jsonl đều tồn tại trong document_versions.json và trong bảng Mục 6 docs/data_contract.md
    contract_doc_ids = {r["document_id"] for r in contract_rows}
    parsed_titles = {}
    for path in (repo_root / "parser" / "parsed_jsons").glob("*.json"):
        parsed = json.loads(path.read_text(encoding="utf-8"))
        parsed_titles[parsed["document_id"]] = parsed["metadata"]["title"]
    parsed_doc_ids = set(parsed_titles)

    chunk_doc_ids = set()
    stale_title_chunks = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                cdid = c.get("document_id") or c.get("metadata", {}).get("doc_id") or c.get("chunk_id").split("_art_")[0]
                chunk_doc_ids.add(cdid)
                if cdid in parsed_titles and c.get("title") != parsed_titles[cdid]:
                    stale_title_chunks.append(c.get("chunk_id"))

    # (d) Corpus phải được sinh lại sau khi title trong registry/parsed_jsons đổi
    assert not stale_title_chunks, (
        f"{len(stale_title_chunks)} chunk có title khác parsed_jsons (vd {stale_title_chunks[0]}); "
        "chạy lại chunking/export_legal_chunks.py"
    )
    assert chunk_doc_ids == parsed_doc_ids, (
        f"document_id của chunks.jsonl lệch parsed_jsons: {sorted(chunk_doc_ids ^ parsed_doc_ids)}"
    )
    for did in chunk_doc_ids:
        assert did in registry_by_id, f"document_id '{did}' trong chunks.jsonl không có trong registry"
        assert did in contract_doc_ids, f"document_id '{did}' trong chunks.jsonl không có trong bảng Mục 6 data_contract.md"


def test_document_number_comes_from_so_label():
    # Số hiệu của văn bản được hướng dẫn đứng trước nhãn "Số:" không được lấy làm số hiệu.
    text = (
        "Hướng dẫn thi hành Nghị định 126/2014/NĐ-CP\n"
        "CHÍNH PHỦ\n"
        "Số: 207/2025/NĐ-CP\n"
        "NGHỊ ĐỊNH\n"
    )
    assert extract_document_number(text) == "207/2025/NĐ-CP"