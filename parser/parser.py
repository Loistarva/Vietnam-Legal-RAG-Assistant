"""Thư viện parse văn bản luật (TXT) thành JSON theo Điều / Khoản. Không có main; entry point là test_parser.py."""
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


FIRST_PAGE_NUMBER = 2
SPLIT_LONG_CLAUSES = True
MAX_CLAUSE_CHARS = 1500

UP = "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"

POINT_LETTERS = "abcdđeghiklmnopqrstuvxy"

WARNINGS: List[str] = []


def warn(msg: str):
    WARNINGS.append(msg)


class ChunkSchema(BaseModel):
    chunk_id: str
    clause_number: Optional[str] = None
    point_letter: Optional[str] = None
    text: str = Field(..., min_length=10)
    parent_id: str
    char_count: Optional[int] = None

    @field_validator("text")
    @classmethod
    def text_must_be_clean(cls, v):
        if "\x00" in v:
            raise ValueError("Văn bản chứa ký tự lỗi (null byte)")
        return v.strip()


class ArticleSchema(BaseModel):
    article_id: str
    article_number: str
    article_title: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    intro: Optional[str] = None
    chunks: List[ChunkSchema] = Field(..., min_length=1)

    @field_validator("chunks")
    @classmethod
    def chunks_parent_id_must_match_article(cls, v, info):
        if "article_id" in info.data:
            for chunk in v:
                if chunk.parent_id != info.data["article_id"]:
                    raise ValueError(
                        f"Chunk {chunk.chunk_id} có parent_id không khớp với article_id"
                    )
        return v


class DocumentMetadataSchema(BaseModel):
    title: str
    document_type: Literal[
        "Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị"
    ]
    document_number: str
    issue_date: str
    effective_date: Optional[str] = None
    issuing_body: str
    validity_status: str


class LegalDocumentSchema(BaseModel):
    document_id: str = Field(..., pattern=r"^[A-Za-z0-9_]+$")
    metadata: DocumentMetadataSchema
    articles: List[ArticleSchema]
    footnotes: List[str] = Field(default_factory=list)


GLUED_MARKER = re.compile(r"(?<=[^\W\d_])\d(?=[\s.,;:”]|$)")
NUM_TOKEN = re.compile(r"(?<=\s)(\d{1,3})(?=\s|$)")

PREV_BAD = {
    "Điều", "điều", "khoản", "điểm", "các", "và", "từ",
    "đến", "ngày", "tháng", "năm", "số", "hoặc"
}

NEXT_BAD = {"tháng", "năm", "ngày", "tuổi"}


def find_page_token(text: str, pos: int, page: int):
    for m in NUM_TOKEN.finditer(text, pos):
        tok = m.group(1)

        if tok.startswith("0") or int(tok) != page:
            continue

        prev = text[:m.start()].rstrip().rsplit(" ", 1)[-1]
        nxt = text[m.end():].lstrip().split(" ", 1)[0]

        if prev in PREV_BAD or prev.endswith(","):
            continue

        if nxt in NEXT_BAD:
            continue

        return m

    return None


def footnote_regex(n: int):
    return re.compile(rf"(?<=[.”\"]\s){n}\s+(?=[{UP}])")


def clean_text(text: str) -> Tuple[str, List[str]]:
    text = GLUED_MARKER.sub("", text)

    footnotes: List[str] = []
    page = FIRST_PAGE_NUMBER
    fn = 1
    pos = 0
    misses = 0
    pages_removed = 0

    while misses < 5:
        m_pg = find_page_token(text, pos, page)
        m_fn = footnote_regex(fn).search(text, pos)

        if m_fn and (m_pg is None or m_fn.start() < m_pg.start()):

            if m_pg is None:
                next_page = None

                for cand in NUM_TOKEN.finditer(text, m_fn.end()):
                    after = text[cand.end():].lstrip()

                    if re.match(r"(?:Điều|Chương)\b", after):
                        next_page = cand
                        break

                if next_page:
                    end = next_page.end()

                    footnotes.append(
                        text[m_fn.start():next_page.start()].strip()
                    )

                    text = text[:m_fn.start()] + " " + text[end:]
                    pos = m_fn.start()
                    fn += 1
                    pages_removed += 1
                    misses = 0

                    warn(
                        f"Không tìm thấy số trang {page}; đã bỏ chú thích "
                        f"{fn - 1} bằng mốc trang kế tiếp "
                        f"{next_page.group(1)}."
                    )
                    continue

                warn(
                    f"Không tìm thấy số trang {page}; giữ nguyên phần còn lại "
                    f"để tránh mất dữ liệu."
                )
                break

            end = m_pg.end()

            footnotes.append(
                text[m_fn.start():end].strip()
            )

            text = text[:m_fn.start()] + " " + text[end:]
            pos = m_fn.start()
            fn += 1
            page += 1
            pages_removed += 1
            misses = 0

        elif m_pg:
            text = text[:m_pg.start()] + " " + text[m_pg.end():]
            pos = m_pg.start()
            page += 1
            pages_removed += 1
            misses = 0

        else:
            warn(
                f"Không tìm thấy số trang {page} "
                f"(có thể do trang cuối hoặc sai lệch đếm)."
            )
            page += 1
            misses += 1

    print(
        f"[clean] đã bỏ {pages_removed} số trang, "
        f"{len(footnotes)} chú thích"
    )

    text = re.sub(r"\s+", " ", text).strip()

    return text, footnotes


HEAD_RE = re.compile(
    rf"(?<!\S)(Chương\s+[IVXLC]+|Mục\s+\d+)\s+"
    rf"((?:[{UP}][{UP},]*(?:\s+|$))+)"
)


def update_headings(
    fragment: str,
    state: Dict[str, Optional[str]]
):
    for m in HEAD_RE.finditer(fragment):
        label = re.sub(r"\s+", " ", m.group(1)).strip()
        title = m.group(2).strip()

        if label.startswith("Chương"):
            state["chapter"] = f"{label} {title}"
            state["section"] = None
        else:
            state["section"] = f"{label} {title}"


def find_articles(text: str) -> List[Tuple[int, int, int]]:
    markers = []
    pos = 0
    n = 1

    while True:
        m = re.compile(
            rf"(?<!\S)Điều\s+{n}\.\s+(?=[{UP}])"
        ).search(text, pos)

        if not m:
            break

        markers.append((n, m.start(), m.end()))
        pos = m.end()
        n += 1

    return markers


def clause_regex(k: int):
    return re.compile(
        rf"(?<!\S){k}\.\s+(?=[{UP}])"
    )


def split_clauses(body: str) -> List[Tuple[str, str]]:
    first = clause_regex(1).search(body)

    if not first:
        return []

    starts = [(1, first.start())]

    pos = first.end()
    k = 2

    while True:
        m = clause_regex(k).search(body, pos)

        if not m:
            break

        starts.append((k, m.start()))
        pos = m.end()
        k += 1

    out = []

    for i, (k, s) in enumerate(starts):
        e = (
            starts[i + 1][1]
            if i + 1 < len(starts)
            else len(body)
        )

        out.append(
            (str(k), body[s:e].strip())
        )

    return out


def split_points(
    clause_text: str
) -> Optional[List[Tuple[str, str]]]:

    starts = []
    pos = 0

    for ch in POINT_LETTERS:
        m = re.compile(
            rf"(?<!\S){re.escape(ch)}\)\s+"
        ).search(clause_text, pos)

        if not m:
            break

        starts.append((ch, m.start()))
        pos = m.end()

    if len(starts) < 2:
        return None

    lead = clause_text[:starts[0][1]].strip()

    out = []

    for i, (ch, s) in enumerate(starts):
        e = (
            starts[i + 1][1]
            if i + 1 < len(starts)
            else len(clause_text)
        )

        point_text = clause_text[s:e].strip()

        if lead:
            point_text = f"{lead} {point_text}"

        out.append((ch, point_text.strip()))

    return out


INTRO_END_RE = re.compile(
    r"(?:"
    r":|"
    r"như sau|"
    r"bao gồm|"
    r"cụ thể như sau|"
    r"sau đây|"
    r"theo quy định sau|"
    r"được quy định như sau"
    r")"
    r"\s*[.:]?\s*$",
    re.IGNORECASE
)


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> List[str]:
    text = normalize_spaces(text)

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?;:])\s+(?=[A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ"
        r"ÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ"
        r"ÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ])",
        text
    )

    return [
        p.strip()
        for p in parts
        if p.strip()
    ]


def looks_like_title(text: str) -> bool:

    text = normalize_spaces(text)

    if not text:
        return False

    if text.endswith(":"):
        return False

    if len(text) > 220:
        return False

    intro_words = (
        "việc ",
        "theo ",
        "trong ",
        "đối với ",
        "khi ",
        "nếu ",
        "trường hợp ",
        "căn cứ ",
        "người ",
        "các ",
        "những ",
        "để ",
        "nhằm ",
        "khiếu ",
        "cơ quan ",
    )

    lower = text.lower()

    if lower.startswith(intro_words):
        return False

    if re.search(r"[.!?]$", text):
        return False

    word_count = len(text.split())

    if word_count > 30:
        return False

    return True


def detect_title_and_intro(head: str) -> Tuple[Optional[str], Optional[str]]:

    head = normalize_spaces(head)

    if not head:
        return None, None

    if INTRO_END_RE.search(head):
        colon_pos = head.rfind(":")

        if colon_pos > 0:
            before = head[:colon_pos].strip()
            after = head[colon_pos + 1:].strip()

            sentences = split_sentences(before)

            if len(sentences) >= 2:
                candidate_title = sentences[0]
                intro_before = " ".join(sentences[1:]).strip()

                if looks_like_title(candidate_title):
                    intro = (
                        f"{intro_before}:"
                        if intro_before
                        else ""
                    )

                    if after:
                        intro = f"{intro} {after}".strip()

                    return candidate_title, intro or None

            if looks_like_title(before):
                intro = after

                if intro:
                    intro = f"{intro}"

                return before, intro or None

        return None, head

    sentences = split_sentences(head)

    if len(sentences) >= 2:
        candidate = sentences[0]
        remainder = " ".join(sentences[1:]).strip()

        if looks_like_title(candidate):
            return candidate, remainder or None

    if looks_like_title(head):
        return head, None

    warn(
        f"Không chắc chắn title tự động: {head[:120]!r}"
    )

    return None, head


def split_head(
    num: str,
    raw: str
):

    first = clause_regex(1).search(raw)

    if first:
        head = raw[:first.start()].strip()
        body = raw[first.start():].strip()
    else:
        head = raw.strip()
        body = ""

    title, intro = detect_title_and_intro(head)

    if first:
        return title, intro, body, True

    if title and intro:
        body = intro
        intro = None

    elif title:
        body = raw

    else:
        body = raw

    return title, intro, body, False


def build_chunks(
    art_id: str,
    body: str,
    has_clauses: bool
) -> List[ChunkSchema]:

    pieces: List[
        Tuple[Optional[str], Optional[str], str]
    ] = []

    if not has_clauses:
        pieces.append(
            (None, None, body)
        )

    else:
        clauses = split_clauses(body)

        for k, ctext in clauses:

            sub = (
                split_points(ctext)
                if (
                    SPLIT_LONG_CLAUSES
                    and len(ctext) > MAX_CLAUSE_CHARS
                )
                else None
            )

            if sub:
                for letter, ptext in sub:
                    pieces.append(
                        (k, letter, ptext)
                    )
            else:
                pieces.append(
                    (k, None, ctext)
                )

    chunks = []

    for i, (k, letter, t) in enumerate(
        pieces,
        start=1
    ):
        t = t.strip()

        chunks.append(
            ChunkSchema(
                chunk_id=f"{art_id}_chunk_{i}",
                clause_number=k,
                point_letter=letter,
                text=t,
                parent_id=art_id,
                char_count=len(t),
            )
        )

    return chunks


def parse_text_to_articles(raw_text: str):

    """Tách văn bản thô thành danh sách Điều và chú thích."""
    WARNINGS.clear()

    text = re.sub(
        r"\s+",
        " ",
        raw_text
    ).strip()


    m0 = re.search(
        rf"(?<!\S)Chương\s+I\s+[{UP}]",
        text
    )

    if m0:
        text = text[m0.start():]

    else:
        warn(
            "Không tìm thấy 'Chương I', "
            "giữ nguyên phần đầu văn bản."
        )


    text, footnotes = clean_text(text)


    markers = find_articles(text)

    if not markers:
        raise RuntimeError(
            "Không tìm thấy Điều nào."
        )

    found_numbers = [
        n
        for n, _s, _e in markers
    ]

    if found_numbers != list(
        range(
            1,
            found_numbers[-1] + 1
        )
    ):
        missing = sorted(
            set(
                range(
                    1,
                    found_numbers[-1] + 1
                )
            )
            -
            set(found_numbers)
        )

        raise RuntimeError(
            "Chuỗi Điều bị đứt sau khi làm sạch. "
            f"Điều bị thiếu: {missing}. "
            "Không tiếp tục xuất JSON."
        )


    state: Dict[
        str,
        Optional[str]
    ] = {
        "chapter": None,
        "section": None
    }

    update_headings(
        text[:markers[0][1]],
        state
    )

    articles = []


    for i, (n, _s, e) in enumerate(markers):

        end = (
            markers[i + 1][1]
            if i + 1 < len(markers)
            else len(text)
        )

        raw = text[e:end].strip()

        num = str(n)

        chapter = state["chapter"]
        section = state["section"]

        mh = HEAD_RE.search(raw)

        if mh:
            update_headings(
                raw[mh.start():],
                state
            )

            chapter = state["chapter"]
            section = state["section"]

            raw = raw[:mh.start()].strip()

        title, intro, body, has_clauses = split_head(
            num,
            raw
        )

        art_id = f"dieu_{num}"

        try:
            chunks = build_chunks(
                art_id,
                body,
                has_clauses
            )

            articles.append(
                ArticleSchema(
                    article_id=art_id,
                    article_number=num,
                    article_title=title,
                    chapter=chapter,
                    section=section,
                    intro=intro,
                    chunks=chunks,
                ).model_dump()
            )

        except Exception as ex:
            warn(
                f"Điều {num} lỗi khi dựng chunk: {ex}"
            )

    return articles, footnotes


DOCUMENT_TYPE_PATTERNS = [
    ("Luật", re.compile(r"(?<!\w)L(?:UẬT|uật)\b")),
    ("Nghị định", re.compile(r"(?<!\w)N(?:GHỊ ĐỊNH|ghị định)\b")),
    ("Thông tư", re.compile(r"(?<!\w)T(?:HÔNG TƯ|hông tư)\b")),
    ("Quyết định", re.compile(r"(?<!\w)Q(?:UYẾT ĐỊNH|uyết định)\b")),
    ("Chỉ thị", re.compile(r"(?<!\w)C(?:HỈ THỊ|hỉ thị)\b")),
]

DOCUMENT_NUMBER_RE = re.compile(
    r"(?:Số|Số:|số|số:)\s*"
    r"([0-9]{1,5}/[0-9]{4}/[A-ZĐ]+(?:-[A-Z0-9Đ]+)?)"
)

DATE_RE = re.compile(
    r"(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    re.IGNORECASE
)

ISO_DATE_RE = re.compile(
    r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b"
)

ISSUING_BODY_PATTERNS = [
    (re.compile(r"\bQUỐC HỘI\b", re.IGNORECASE), "Quốc hội"),
    (re.compile(r"\bCHÍNH PHỦ\b", re.IGNORECASE), "Chính phủ"),
    (re.compile(r"\bTHỦ TƯỚNG CHÍNH PHỦ\b", re.IGNORECASE), "Thủ tướng Chính phủ"),
    (re.compile(r"\bBỘ TƯ PHÁP\b", re.IGNORECASE), "Bộ Tư pháp"),
    (re.compile(r"\bBỘ CÔNG AN\b", re.IGNORECASE), "Bộ Công an"),
    (re.compile(r"\bBỘ TÀI CHÍNH\b", re.IGNORECASE), "Bộ Tài chính"),
    (re.compile(r"\bBỘ Y TẾ\b", re.IGNORECASE), "Bộ Y tế"),
    (re.compile(r"\bBỘ GIÁO DỤC VÀ ĐÀO TẠO\b", re.IGNORECASE),
     "Bộ Giáo dục và Đào tạo"),
    (re.compile(r"\bTÒA ÁN NHÂN DÂN TỐI CAO\b", re.IGNORECASE),
     "Tòa án nhân dân tối cao"),
    (re.compile(r"\bVIỆN KIỂM SÁT NHÂN DÂN TỐI CAO\b", re.IGNORECASE),
     "Viện kiểm sát nhân dân tối cao"),
]

VALIDITY_PATTERNS = [
    (re.compile(r"còn hiệu lực", re.IGNORECASE), "Còn hiệu lực"),
    (re.compile(r"hết hiệu lực", re.IGNORECASE), "Hết hiệu lực"),
    (re.compile(r"ngưng hiệu lực", re.IGNORECASE), "Ngưng hiệu lực"),
    (re.compile(r"đang có hiệu lực", re.IGNORECASE), "Còn hiệu lực"),
]


def normalize_document_id(file_path: str) -> str:
    """Tạo document_id hợp lệ từ tên file."""
    stem = Path(file_path).stem.strip()

    if not stem:
        raise ValueError("Không thể tạo document_id từ tên file rỗng.")

    doc_id = re.sub(r"[^A-Za-z0-9_]+", "_", stem)
    doc_id = re.sub(r"_+", "_", doc_id).strip("_")

    if not doc_id:
        raise ValueError(
            f"Tên file {Path(file_path).name!r} không tạo được document_id hợp lệ."
        )

    return doc_id


def extract_document_type(text: str) -> str:
    head = text[:5000]

    for doc_type, pattern in [
        ("Nghị định", re.compile(r"\bNGHỊ ĐỊNH\b", re.IGNORECASE)),
        ("Thông tư", re.compile(r"\bTHÔNG TƯ\b", re.IGNORECASE)),
        ("Quyết định", re.compile(r"\bQUYẾT ĐỊNH\b", re.IGNORECASE)),
        ("Chỉ thị", re.compile(r"\bCHỈ THỊ\b", re.IGNORECASE)),
        ("Luật", re.compile(r"\bLUẬT\b", re.IGNORECASE)),
    ]:
        if pattern.search(head):
            return doc_type

    warn("Không tự nhận diện được document_type; mặc định là 'Luật'.")
    return "Luật"


def extract_document_number(text: str) -> str:
    head = text[:8000]

    m = DOCUMENT_NUMBER_RE.search(head)

    if m:
        return m.group(1)

    fallback = re.search(
        r"\b\d{1,5}/\d{4}/[A-ZĐ]+(?:-[A-Z0-9Đ]+)?\b",
        head
    )

    if fallback:
        return fallback.group(0)

    warn("Không tự nhận diện được document_number.")
    return ""


def vietnamese_date_to_iso(day: str, month: str, year: str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def extract_issue_date(text: str) -> str:
    head = text[:10000]

    m = DATE_RE.search(head)

    if m:
        return vietnamese_date_to_iso(
            m.group(1),
            m.group(2),
            m.group(3)
        )

    m = ISO_DATE_RE.search(head)

    if m:
        return (
            f"{int(m.group(1)):04d}-"
            f"{int(m.group(2)):02d}-"
            f"{int(m.group(3)):02d}"
        )

    warn("Không tự nhận diện được issue_date.")
    return ""


def extract_issuing_body(text: str) -> str:
    head = text[:5000]

    ordered = sorted(
        ISSUING_BODY_PATTERNS,
        key=lambda x: len(x[1]),
        reverse=True
    )

    for pattern, body in ordered:
        if pattern.search(head):
            return body

    warn("Không tự nhận diện được issuing_body.")
    return ""


def extract_validity_status(text: str) -> str:
    head = text[:12000]

    for pattern, status in VALIDITY_PATTERNS:
        if pattern.search(head):
            return status

    return "Không xác định"


def clean_document_title_candidate(text: str) -> Optional[str]:
    head = re.sub(r"\s+", " ", text[:12000]).strip()

    patterns = [
        r"\b(LUẬT\s+.+?)(?=\s+(?:Căn cứ|Chương\s+I)\b)",
        r"\b(NGHỊ ĐỊNH\s+.+?)(?=\s+(?:Căn cứ|Chương\s+I)\b)",
        r"\b(THÔNG TƯ\s+.+?)(?=\s+(?:Căn cứ|Chương\s+I)\b)",
        r"\b(QUYẾT ĐỊNH\s+.+?)(?=\s+(?:Căn cứ|Chương\s+I)\b)",
        r"\b(CHỈ THỊ\s+.+?)(?=\s+(?:Căn cứ|Chương\s+I)\b)",
    ]

    for p in patterns:
        m = re.search(p, head, re.IGNORECASE)
        if m:
            candidate = normalize_spaces(m.group(1))
            candidate = re.sub(
                r"\s+Số[:\s].*$",
                "",
                candidate,
                flags=re.IGNORECASE
            )
            if 2 <= len(candidate.split()) <= 40:
                return candidate

    m = re.search(
        r"\b(LUẬT|NGHỊ ĐỊNH|THÔNG TƯ|QUYẾT ĐỊNH|CHỈ THỊ)\b"
        r"(.{0,300}?)"
        r"(?=\s+(?:Căn cứ|Chương\s+I)\b)",
        head,
        re.IGNORECASE
    )

    if m:
        candidate = normalize_spaces(m.group(0))
        if 2 <= len(candidate.split()) <= 40:
            return candidate

    return None


def extract_document_title(text: str) -> str:
    candidate = clean_document_title_candidate(text)

    if candidate:
        return candidate

    head = re.sub(r"\s+", " ", text[:8000]).strip()

    m = re.search(
        r"\b(?:LUẬT|NGHỊ ĐỊNH|THÔNG TƯ|QUYẾT ĐỊNH|CHỈ THỊ)\b"
        r".{0,200}?(?=\s+Chương\s+I\b)",
        head,
        re.IGNORECASE
    )

    if m:
        candidate = normalize_spaces(m.group(0))
        if candidate:
            return candidate

    warn("Không tự nhận diện được document title.")
    return Path("unknown").stem


def extract_metadata(
    raw_text: str,
    file_path: Optional[str] = None
) -> dict:
    """Tự nhận diện metadata của văn bản từ nội dung."""
    if file_path:
        document_id = normalize_document_id(file_path)
    else:
        document_id = "document"

    return {
        "title": extract_document_title(raw_text),
        "document_type": extract_document_type(raw_text),
        "document_number": extract_document_number(raw_text),
        "issue_date": extract_issue_date(raw_text),
        "effective_date": None,
        "issuing_body": extract_issuing_body(raw_text),
        "validity_status": extract_validity_status(raw_text),
    }


def parse_raw_text_to_legal_doc(
    raw_text: str,
    doc_id: str,
    metadata: dict
) -> dict:

    """Parse văn bản thô thành dict LegalDocumentSchema."""
    meta = DocumentMetadataSchema(
        **metadata
    )

    articles, footnotes = parse_text_to_articles(
        raw_text
    )

    doc = LegalDocumentSchema(
        document_id=doc_id,
        metadata=meta,
        articles=articles,
        footnotes=footnotes,
    )

    return doc.model_dump()


def parse_legal_document_to_schema(
    file_path: str
):

    """Đọc file .txt rồi parse thành (articles, footnotes)."""
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Đường dẫn file không hợp lệ: "
            f"{path.resolve()}"
        )

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        errors="ignore"
    ) as f:
        content = f.read()

    return parse_text_to_articles(content)


def quality_report(
    articles,
    footnotes
):
    """In báo cáo chất lượng kết quả parse."""
    last_article = (
        articles[-1]["article_number"]
        if articles
        else "N/A"
    )

    print(
        f"\n[report] Số Điều: {len(articles)} "
        f"(Điều cuối: {last_article})"
    )

    print(
        "[report] Số chunk: "
        f"{sum(len(a['chunks']) for a in articles)}"
    )

    if articles:

        nums = [
            int(a["article_number"])
            for a in articles
        ]

        missing = sorted(
            set(
                range(
                    1,
                    max(nums) + 1
                )
            )
            -
            set(nums)
        )

        if missing:
            print(
                f"[report] CẢNH BÁO: thiếu Điều: {missing}"
            )

        else:
            print(
                "[report] Chuỗi Điều liên tục: "
                f"1 -> {max(nums)}"
            )

    sus_footnote = re.compile(
        r"Luật số \d+/\d{4}/QH|Cụm từ “"
    )

    sus_heading = re.compile(
        rf"(?<!\S)(Chương [IVXLC]+|Mục \d+) [{UP}]{{2}}"
    )

    bad = []

    for a in articles:

        for c in a["chunks"]:

            t = c["text"]

            if sus_footnote.search(t) or sus_heading.search(t):

                bad.append(
                    (
                        c["chunk_id"],
                        "lẫn chú thích/tiêu đề Chương-Mục"
                    )
                )

            elif not re.search(
                r"[.;:”)]$",
                t
            ):

                bad.append(
                    (
                        c["chunk_id"],
                        "không kết thúc bằng dấu câu "
                        "(nghi dư số trang)"
                    )
                )

    print(
        f"[report] Chunk đáng nghi: {len(bad)}"
    )

    for cid, why in bad[:15]:
        print(
            f"   - {cid}: {why}"
        )

    empty_title = [
        a["article_number"]
        for a in articles
        if not a["article_title"]
    ]

    if empty_title:
        print(
            "[report] Điều chưa có tiêu đề: "
            f"{empty_title}"
        )

    for w in WARNINGS[:30]:
        print(
            "[warn]",
            w
        )

    if len(WARNINGS) > 30:
        print(
            "[warn] ... và "
            f"{len(WARNINGS) - 30} cảnh báo khác"
        )
