import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

VALIDITY_STATUS_MAP = {
    "Còn hiệu lực": "Còn hiệu lực",
    "Hết hiệu lực toàn bộ": "Hết hiệu lực",
    "Hết hiệu lực": "Hết hiệu lực",
    "Hết hiệu lực một phần": "Sửa đổi bổ sung",
    "Có điều khoản bị sửa đổi / bãi bỏ": "Sửa đổi bổ sung",
    "Sắp có hiệu lực": "Sắp có hiệu lực",
    "Cần kiểm tra trạng thái mới nhất": "Không xác định",
    "Không xác định": "Không xác định",
}
"""Thư viện parse văn bản luật (TXT) thành JSON theo Điều / Khoản (Kiến trúc 4 tầng). Không có main; entry point là test_parser.py."""
import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

FIRST_PAGE_NUMBER = 2
UP = "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
WARNINGS: List[str] = []

def warn(msg: str):
    WARNINGS.append(msg)


# =============================================================================
# SCHEMAS (Đã cập nhật theo Data Contract 2.0 - 4 Tầng)
# =============================================================================

class ChunkSchema(BaseModel):
    chunk_id: str
    parent_clause_id: str
    clause_number: Optional[str] = None
    point_letter: Optional[str] = None
    chunk_text: str = Field(..., min_length=10)
    char_count: Optional[int] = None

    @field_validator("chunk_text")
    @classmethod
    def text_must_be_clean(cls, v):
        if "\x00" in v:
            raise ValueError("Văn bản chứa ký tự lỗi (null byte)")
        return v.strip()

class ClauseSchema(BaseModel):
    clause_id: str
    parent_article_id: str
    clause_number: str
    clause_text: str = Field(..., min_length=1, description="Nội dung thô của toàn bộ Khoản")
    chunks: Optional[List[ChunkSchema]] = None

    @field_validator("clause_text")
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
    clauses: List[ClauseSchema] = Field(..., min_length=1)

class LegalMetadata(BaseModel):
    title: str = Field(..., min_length=5)
    document_type: str
    document_number: str
    issue_date: str
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    source_url: str = ""
    issuing_body: str
    validity_status: str

class LegalDocumentSchema(BaseModel):
    document_id: str = Field(..., pattern=r"^[A-Za-z0-9_]+$")
    metadata: LegalMetadata
    articles: List[ArticleSchema] = Field(..., min_length=1)
    footnotes: List[str] = Field(default_factory=list)


# =============================================================================
# PARSER LOGIC
# =============================================================================

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
                    footnotes.append(text[m_fn.start():next_page.start()].strip())
                    text = text[:m_fn.start()] + " " + text[end:]
                    pos = m_fn.start()
                    fn += 1
                    pages_removed += 1
                    misses = 0
                    warn(f"Không tìm thấy số trang {page}; đã bỏ chú thích {fn - 1} bằng mốc trang kế tiếp {next_page.group(1)}.")
                    continue
                warn(f"Không tìm thấy số trang {page}; giữ nguyên phần còn lại để tránh mất dữ liệu.")
                break
            end = m_pg.end()
            footnotes.append(text[m_fn.start():end].strip())
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
            warn(f"Không tìm thấy số trang {page} (có thể do trang cuối hoặc sai lệch đếm).")
            page += 1
            misses += 1

    print(f"[clean] đã bỏ {pages_removed} số trang, {len(footnotes)} chú thích")
    text = re.sub(r"\s+", " ", text).strip()
    return text, footnotes


HEAD_LABEL_RE = re.compile(r"(?<!\S)(Chương\s+[IVXLCDM]+|Mục\s+\d+)(?=\s)")
# Giữ lại để quality_report dùng
HEAD_RE = HEAD_LABEL_RE

# Ranh giới tiêu đề: không dựa vào chữ hoa. Tiêu đề Chương/Mục được lấy
# nguyên văn cho tới khi gặp tiêu đề Mục, Chương hoặc một Điều có số và dấu chấm.
HEADING_BOUNDARY_RE = re.compile(
    r"(?<!\S)(?:Chương\s+[IVXLCDM]+|Mục\s+\d+|Điều\s+\d+\.)"
)


def iter_headings(fragment: str):
    """Sinh (vị_trí_bắt_đầu, nhãn, tiêu_đề); tiêu đề kết thúc ở Mục/Điều kế tiếp."""
    matches = list(HEAD_LABEL_RE.finditer(fragment))
    for i, m in enumerate(matches):
        label = re.sub(r"\s+", " ", m.group(1)).strip()
        title_start = m.end()

        # Tìm ranh giới kế tiếp trong văn bản, không giả định tiêu đề viết HOA.
        boundary = HEADING_BOUNDARY_RE.search(fragment, title_start)
        title_end = boundary.start() if boundary else len(fragment)
        title = re.sub(r"\s+", " ", fragment[title_start:title_end]).strip(" \t\r\n:–—-;,. ")
        if not title:
            continue
        yield m.start(), label, title


def update_headings(fragment: str, state: Dict[str, Optional[str]]):
    for _start, label, title in iter_headings(fragment):
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
        m = re.compile(rf"(?<!\S)Điều\s+{n}\.\s+(?=[{UP}])").search(text, pos)
        if not m:
            break
        markers.append((n, m.start(), m.end()))
        pos = m.end()
        n += 1
    return markers


def clause_regex(k: int):
    return re.compile(rf"(?<!\S){k}\.\s+(?=[{UP}])")


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
        e = starts[i + 1][1] if i + 1 < len(starts) else len(body)
        out.append((str(k), body[s:e].strip()))
    return out


INTRO_END_RE = re.compile(
    r"(?::|như sau|bao gồm|cụ thể như sau|sau đây|theo quy định sau|được quy định như sau)\s*[.:]?\s*$",
    re.IGNORECASE
)

def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def split_sentences(text: str) -> List[str]:
    text = normalize_spaces(text)
    if not text:
        return []
    parts = re.split(
        r"(?<=[.!?;:])\s+(?=[A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ])",
        text
    )
    return [p.strip() for p in parts if p.strip()]

def looks_like_title(text: str) -> bool:
    text = normalize_spaces(text)
    if not text or text.endswith(":") or len(text) > 220:
        return False
    intro_words = (
        "việc ", "theo ", "trong ", "đối với ", "khi ", "nếu ", "trường hợp ", "căn cứ ",
        "người ", "các ", "những ", "để ", "nhằm ", "khiếu ", "cơ quan ",
    )
    if text.lower().startswith(intro_words) or re.search(r"[.!?]$", text) or len(text.split()) > 30:
        return False
    return True

# Các cụm thường mở đầu phần quy phạm/nội dung của Điều khi văn bản TXT
# đã bị làm phẳng thành một dòng, khiến tiêu đề không còn dấu xuống dòng.
# Chỉ dùng để tìm ranh giới khi phần trước thực sự giống một tiêu đề ngắn.
ARTICLE_BODY_STARTS = (
    "Các bên", "Nghị định này", "Luật này", "Bộ luật này", "Pháp lệnh này",
    "Thông tư này", "Cơ quan", "Tòa án", "Tòa án nhân dân", "Người",
    "Việc", "Trong trường hợp", "Trường hợp", "Hành vi", "Các tổ chức",
    "Tổ chức, cá nhân", "Mọi tổ chức", "Chính phủ", "Bộ trưởng",
    "Ủy ban", "Đối với", "Khi", "Nếu", "Nội dung", "Quyền và nghĩa vụ",
    "Việc xác định", "Các cá nhân", "Cá nhân", "Bên mang thai hộ",
)


def split_title_from_unlabelled_body(head: str) -> Optional[Tuple[str, str]]:
    """Tách tiêu đề khỏi nội dung Điều khi không có Khoản 1 và TXT bị làm phẳng.

    Trả về (title, body) khi tìm được ranh giới đủ đáng tin cậy; ngược lại None.
    Không dùng danh sách này cho phần đã có các khoản đánh số.
    """
    head = normalize_spaces(head)
    candidates = []

    for start_phrase in ARTICLE_BODY_STARTS:
        # Cụm mở đầu nội dung phải xuất hiện đúng dạng viết hoa ở đầu câu.
        pattern = re.compile(rf"(?<!\S)({re.escape(start_phrase)})\b")
        for match in pattern.finditer(head):
            title = head[:match.start()].strip(" ,;:")
            body = head[match.start():].strip()
            words = title.split()

            # Tránh cắt vào tiêu đề quá ngắn hoặc nhận nhầm cả đoạn dài là tiêu đề.
            if not (3 <= len(words) <= 25):
                continue
            if not (len(title) >= 15 and len(title) <= 220 and len(body) >= 25):
                continue
            if not looks_like_title(title):
                continue
            if re.search(r"[.!?]$", title):
                continue

            candidates.append((match.start(), title, body))

    if not candidates:
        return None

    # Ranh giới sớm nhất là điểm bắt đầu nội dung đầu tiên hợp lệ.
    _, title, body = min(candidates, key=lambda item: item[0])
    return title, body


# Từ đứng TRƯỚC một chữ hoa mà cho thấy chữ hoa đó vẫn thuộc tiêu đề
# (danh từ riêng: "của Bộ luật dân sự", "theo Luật này"...), không phải đầu câu nội dung.
TITLE_CONNECTORS = {
    "của", "và", "về", "với", "theo", "trong", "cho", "hoặc", "tại", "từ", "đến",
    "do", "bởi", "như", "khi", "các", "những", "giữa", "đối", "để", "nhằm", "bằng",
    "là", "có", "được", "bị", "trên", "dưới", "ở", "qua", "sau", "trước", "thì",
    "mà", "nếu", "bao", "gồm", "tới", "vào", "cùng",
}


def split_title_by_capital(head: str) -> Optional[Tuple[str, str]]:
    """Tách tiêu đề khỏi nội dung khi TXT bị làm phẳng và Điều không có Khoản 1.

    Tiêu đề Điều viết kiểu câu (chỉ chữ đầu viết hoa) và không có dấu chấm cuối,
    còn nội dung bắt đầu bằng một chữ hoa mới. Chọn chữ hoa đầu tiên đứng sau một
    từ KHÔNG phải từ nối/giới từ (để bỏ qua danh từ riêng nằm trong tiêu đề)."""
    head = normalize_spaces(head)
    tokens = head.split(" ")
    pos = 0
    offsets = []
    for tok in tokens:
        offsets.append(pos)
        pos += len(tok) + 1

    for i in range(3, len(tokens)):  # tiêu đề tối thiểu 3 từ
        tok = tokens[i]
        if not tok or not tok[0].isupper():
            continue
        prev = tokens[i - 1]
        if prev[-1:] in ",;:" or prev.lower().strip(",;:") in TITLE_CONNECTORS:
            continue
        title = head[:offsets[i]].strip(" ,;:")
        body = head[offsets[i]:].strip()
        if len(title.split()) > 40 or len(body) < 25:
            continue
        if re.search(r"[.!?]$", title):
            continue
        return title, body
    return None


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
                    intro = f"{intro_before}:" if intro_before else ""
                    if after:
                        intro = f"{intro} {after}".strip()
                    return candidate_title, intro or None
            # Tiêu đề dính liền câu dẫn: "<Tiêu đề> Việc ... như sau:" -> tách theo chữ hoa đầu câu
            split = split_title_by_capital(before)
            if split:
                t, lead = split
                intro = f"{lead}: {after}".strip() if after else f"{lead}:"
                return t, intro
            if looks_like_title(before):
                intro = after
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

    warn(f"Không chắc chắn title tự động: {head[:120]!r}")
    return None, head


def split_head(num: str, raw: str):
    first = clause_regex(1).search(raw)
    if first:
        head = raw[:first.start()].strip()
        body = raw[first.start():].strip()
    else:
        head = raw.strip()
        body = ""

    # Khi có Khoản 1, ranh giới tiêu đề/khoản đã rõ: không dò body-start.
    if first:
        title, intro = detect_title_and_intro(head)
        if title is None and intro and not re.search(r"[.!?:]$", intro) and len(intro.split()) <= 40:
            # Giữa "Điều n." và Khoản 1 chỉ có một cụm không dấu câu cuối: đó là tiêu đề
            # (kể cả khi bắt đầu bằng "Người", "Những", "Việc", "Căn cứ"...).
            title, intro = intro, None
        return title, intro, body, True

    # Với Điều không đánh số khoản, TXT thường bị làm phẳng nên tiêu đề và
    # câu quy phạm dính liền nhau (vd: "... mang thai hộ Các bên trong ...").
    split_result = split_title_by_capital(head) or split_title_from_unlabelled_body(head)
    if split_result:
        title, body = split_result
        return title, None, body, False

    title, intro = detect_title_and_intro(head)
    if title and intro:
        body = intro
        intro = None
    elif title:
        body = raw
    else:
        body = raw
    return title, intro, body, False


def build_clauses(art_id: str, body: str, has_clauses: bool) -> List[ClauseSchema]:
    """Thay thế build_chunks: Trả về Clause, không băm nhỏ thành Chunk."""
    clauses = []
    
    if not has_clauses:
        clause_id = f"{art_id}_clause_1"
        clauses.append(
            ClauseSchema(
                clause_id=clause_id,
                parent_article_id=art_id,
                clause_number="1",
                clause_text=body.strip(),
                chunks=None
            )
        )
    else:
        raw_clauses = split_clauses(body)
        for k, ctext in raw_clauses:
            clause_id = f"{art_id}_clause_{k}"
            clauses.append(
                ClauseSchema(
                    clause_id=clause_id,
                    parent_article_id=art_id,
                    clause_number=str(k),
                    clause_text=ctext.strip(),
                    chunks=None
                )
            )
    return clauses


APPENDIX_HEADING_RE = re.compile(
    r"(?<!\S)(?:PHỤ\s+LỤC|Phụ\s+lục)(?:\s+[IVXLCDM]+)?(?:\s+MẪU)?(?=\s|$)",
    re.IGNORECASE,
)
ARTICLE_MARKER_ANY_RE = re.compile(r"(?<!\S)Điều\s+\d+[a-z]?\.\s+(?=[" + UP + r"])" , re.IGNORECASE)


def strip_appendices(text: str) -> str:
    """Cắt bỏ phần phụ lục ở cuối văn bản, không đưa biểu mẫu vào các Điều.

    Chỉ cắt khi đã có nội dung Điều trước tiêu đề PHỤ LỤC và không còn
    Điều luật đánh số tiếp theo sau mốc đó. Tránh cắt nhầm câu đang nhắc tới phụ lục.
    """
    first_article = ARTICLE_MARKER_ANY_RE.search(text)
    if not first_article:
        return text

    for match in APPENDIX_HEADING_RE.finditer(text, first_article.end()):
        # Nếu sau mốc này còn Điều N. theo cấu trúc điều luật, không coi đây là phụ lục cuối.
        if ARTICLE_MARKER_ANY_RE.search(text, match.end()):
            continue
        removed_chars = len(text) - match.start()
        print(f"[clean] đã bỏ phần phụ lục từ vị trí {match.start()} ({removed_chars} ký tự)")
        return text[:match.start()].rstrip()
    return text


def parse_text_to_articles(raw_text: str, doc_id: str):
    WARNINGS.clear()
    # Chuẩn hóa Unicode về NFC: TXT trích từ PDF hay chứa ký tự tiếng Việt dạng
    # tổ hợp (NFD, vd "Ệ" = "E" + dấu mũ + dấu nặng). Khi đó các regex/từ khóa
    # dựng sẵn (UP, ARTICLE_BODY_STARTS, "Các bên"...) không khớp.
    raw_text = unicodedata.normalize("NFC", raw_text)
    raw_text = re.sub(r"[\u200b-\u200d\u2060\ufeff\u00ad]", "", raw_text)  # ký tự vô hình
    text = re.sub(r"\s+", " ", raw_text).strip()

    m0 = re.search(rf"(?<!\S)Chương\s+I\s+[{UP}]", text)
    if m0:
        text = text[m0.start():]
    else:
        warn("Không tìm thấy 'Chương I', giữ nguyên phần đầu văn bản.")

    # Bỏ phụ lục ở cuối trước khi tách Điều/Khoản, để biểu mẫu không bị nhập vào Điều cuối.
    text = strip_appendices(text)
    text, footnotes = clean_text(text)
    markers = find_articles(text)
    if not markers:
        raise RuntimeError("Không tìm thấy Điều nào.")

    found_numbers = [n for n, _s, _e in markers]
    if found_numbers != list(range(1, found_numbers[-1] + 1)):
        missing = sorted(set(range(1, found_numbers[-1] + 1)) - set(found_numbers))
        raise RuntimeError(f"Chuỗi Điều bị đứt sau khi làm sạch. Điều bị thiếu: {missing}. Không tiếp tục xuất JSON.")

    state: Dict[str, Optional[str]] = {"chapter": None, "section": None}
    update_headings(text[:markers[0][1]], state)
    articles = []

    for i, (n, _s, e) in enumerate(markers):
        end = markers[i + 1][1] if i + 1 < len(markers) else len(text)
        raw = text[e:end].strip()
        num = str(n)
        chapter = state["chapter"]
        section = state["section"]

        mh = next(iter_headings(raw), None)
        if mh:
            # Tiêu đề Chương/Mục ở cuối đoạn hiện tại mở đầu phần kế tiếp.
            # Cập nhật state cho các Điều tiếp theo nhưng giữ chapter/section
            # đã chụp ở đầu vòng lặp cho Điều đang xử lý.
            update_headings(raw[mh[0]:], state)
            raw = raw[:mh[0]].strip()

        title, intro, body, has_clauses = split_head(num, raw)
        art_id = f"{doc_id}_art_{num}"

        try:
            clauses = build_clauses(art_id, body, has_clauses)
            articles.append(
                ArticleSchema(
                    article_id=art_id,
                    article_number=num,
                    article_title=title,
                    chapter=chapter,
                    section=section,
                    intro=intro,
                    clauses=clauses,
                ).model_dump()
            )
        except Exception as ex:
            warn(f"Điều {num} lỗi khi dựng clause: {ex}")

    return articles, footnotes


DOCUMENT_TYPE_PATTERNS = [
    ("Luật", re.compile(r"(?<!\w)L(?:UẬT|uật)\b")),
    ("Nghị định", re.compile(r"(?<!\w)N(?:GHỊ ĐỊNH|ghị định)\b")),
    ("Thông tư", re.compile(r"(?<!\w)T(?:HÔNG TƯ|hông tư)\b")),
    ("Quyết định", re.compile(r"(?<!\w)Q(?:UYẾT ĐỊNH|uyết định)\b")),
    ("Chỉ thị", re.compile(r"(?<!\w)C(?:HỈ THỊ|hỉ thị)\b")),
]

# Hỗ trợ số hiệu có chữ cái gắn ngay sau phần số, ví dụ 02a/2015/TT-BTP.
DOCUMENT_NUMBER_CODE = r"[0-9]{1,5}[A-Za-z]?/[0-9]{4}/[A-ZĐ][A-ZĐ0-9]*(?:-[A-Za-z0-9Đđ]+)*"
# Ưu tiên số hiệu có nhãn "Số:" để tránh bắt nhầm số hiệu được nhắc trong nội dung.
DOCUMENT_NUMBER_RE = re.compile(
    rf"(?<!\w)Số\s*:\s*({DOCUMENT_NUMBER_CODE})",
    re.IGNORECASE
)
DATE_RE = re.compile(r"(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")

ISSUING_BODY_PATTERNS = [
    (re.compile(r"\bQUỐC HỘI\b", re.IGNORECASE), "Quốc hội"),
    (re.compile(r"\bCHÍNH PHỦ\b", re.IGNORECASE), "Chính phủ"),
    (re.compile(r"\bTHỦ TƯỚNG CHÍNH PHỦ\b", re.IGNORECASE), "Thủ tướng Chính phủ"),
    (re.compile(r"\bBỘ TƯ PHÁP\b", re.IGNORECASE), "Bộ Tư pháp"),
    (re.compile(r"\bBỘ CÔNG AN\b", re.IGNORECASE), "Bộ Công an"),
    (re.compile(r"\bBỘ TÀI CHÍNH\b", re.IGNORECASE), "Bộ Tài chính"),
    (re.compile(r"\bBỘ Y TẾ\b", re.IGNORECASE), "Bộ Y tế"),
    (re.compile(r"\bBỘ GIÁO DỤC VÀ ĐÀO TẠO\b", re.IGNORECASE), "Bộ Giáo dục và Đào tạo"),
    (re.compile(r"\bTÒA ÁN NHÂN DÂN TỐI CAO\b", re.IGNORECASE), "Tòa án nhân dân tối cao"),
    (re.compile(r"\bVIỆN KIỂM SÁT NHÂN DÂN TỐI CAO\b", re.IGNORECASE), "Viện kiểm sát nhân dân tối cao"),
]

VALIDITY_PATTERNS = [
    (re.compile(r"còn hiệu lực", re.IGNORECASE), "Còn hiệu lực"),
    (re.compile(r"hết hiệu lực", re.IGNORECASE), "Hết hiệu lực"),
    (re.compile(r"ngưng hiệu lực", re.IGNORECASE), "Ngưng hiệu lực"),
    (re.compile(r"đang có hiệu lực", re.IGNORECASE), "Còn hiệu lực"),
]


def normalize_document_id(file_path: str) -> str:
    stem = Path(file_path).stem.strip()
    if not stem:
        raise ValueError("Không thể tạo document_id từ tên file rỗng.")
    doc_id = re.sub(r"[^A-Za-z0-9_]+", "_", stem)
    doc_id = re.sub(r"_+", "_", doc_id).strip("_")
    if not doc_id:
        raise ValueError(f"Tên file {Path(file_path).name!r} không tạo được document_id hợp lệ.")
    return doc_id

# Mã loại văn bản nằm trong số hiệu: "01/2024/NQ-HĐTP" -> mã "NQ" -> Nghị quyết
NUMBER_CODE_TO_TYPE = {
    "ND": "Nghị định",
    "NQ": "Nghị quyết",
    "TT": "Thông tư",
    "TTLT": "Thông tư liên tịch",
    "QD": "Quyết định",
    "CT": "Chỉ thị",
    "PL": "Pháp lệnh",
    "VBHN": "Văn bản hợp nhất",
}
NUMBER_PARTS_RE = re.compile(r"^\d{1,5}/\d{4}/(?P<code>.+)$")

DOCUMENT_TYPE_PREFIX = {
    "Luật": "l",
    "Nghị định": "nd",
    "Nghị quyết": "nq",
    "Thông tư": "tt",
    "Thông tư liên tịch": "ttlt",
    "Quyết định": "qd",
    "Chỉ thị": "ct",
    "Pháp lệnh": "pl",
    "Văn bản hợp nhất": "vbhn",
}


def document_type_from_number(document_number: str) -> Optional[str]:
    """Suy loại văn bản từ số hiệu. Trả về None nếu không nhận ra mã."""
    m = NUMBER_PARTS_RE.match((document_number or "").strip())
    if not m:
        return None
    code = m.group("code").upper().replace("Đ", "D")
    head = code.split("-")[0]
    if re.fullmatch(r"QH\d*", head):  # 52/2014/QH13 -> Luật
        return "Luật"
    return NUMBER_CODE_TO_TYPE.get(head)


def resolve_document_type(raw_text: str, document_number: str) -> str:
    """Ưu tiên suy từ số hiệu; chỉ khi không nhận ra mã mới quay về cách cũ (đọc tên văn bản)."""
    doc_type = document_type_from_number(document_number)
    if doc_type:
        return doc_type
    warn(f"Không suy được document_type từ số hiệu {document_number!r}; dùng cách đọc tên văn bản.")
    return extract_document_type(raw_text)


def slugify_ascii(text: str) -> str:
    """'126/2014/NĐ-CP' -> '126_2014_nd_cp' (bỏ dấu, chữ thường, ký tự lạ -> '_')."""
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return text.strip("_")


def build_document_id(document_type: str, document_number: str) -> str:
    """
    Semantic ID: [loại_văn_bản]_[số_hiệu_đã_slug]
    VD: ('Nghị định', '100/2019/NĐ-CP') -> 'nd_100_2019_nd_cp'
    """
    number_slug = slugify_ascii(document_number or "")
    if not number_slug:
        raise ValueError("Không tạo được document_id: document_number rỗng hoặc không nhận diện được.")
    prefix = DOCUMENT_TYPE_PREFIX.get(document_type) or slugify_ascii(document_type or "")
    return f"{prefix}_{number_slug}" if prefix else number_slug


TITLE_KEYWORD_TO_TYPE = {
    "BỘ LUẬT": "Luật",
    "LUẬT": "Luật",
    "NGHỊ ĐỊNH": "Nghị định",
    "THÔNG TƯ": "Thông tư",
    "QUYẾT ĐỊNH": "Quyết định",
    "CHỈ THỊ": "Chỉ thị",
}


def extract_document_type(text: str) -> str:
    # Ưu tiên: từ khóa IN HOA mở đầu tên văn bản (LUẬT / NGHỊ ĐỊNH / THÔNG TƯ ...)
    _head, _start, located = locate_document_title(text)

    if located:
        m = TITLE_TYPE_RE.match(located)

        if m:
            return TITLE_KEYWORD_TO_TYPE[m.group(0)]

    # Dự phòng: cách cũ
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
    # Ưu tiên số hiệu có nhãn trong phần đầu văn bản.
    head = text[:5000]
    m = DOCUMENT_NUMBER_RE.search(head)
    if m:
        return m.group(1)

    # Dự phòng: tìm số hiệu trước tên văn bản, tránh bắt số hiệu được dẫn lại
    # ở phần căn cứ/nội dung phía sau.
    _head, title_start, _located_title = locate_document_title(text)
    if title_start is not None:
        before_title = text[:title_start]
        matches = list(re.finditer(rf"(?<!\w)({DOCUMENT_NUMBER_CODE})(?!\w)", before_title))
        if matches:
            return matches[-1].group(1)

    # Dự phòng cuối: chỉ tìm trong 1000 ký tự đầu văn bản.
    fallback = re.search(rf"(?<!\w)({DOCUMENT_NUMBER_CODE})(?!\w)", text[:1000])
    if fallback:
        return fallback.group(1)

    warn("Không tự nhận diện được document_number.")
    return ""

def vietnamese_date_to_iso(day: str, month: str, year: str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

def extract_issue_date(text: str) -> str:
    """
    Trích xuất ngày ban hành theo ngữ cảnh, không lấy ngày hiệu lực làm ngày ban hành.

    Thứ tự:
    1. Ngày gắn với cụm thông qua / ban hành / ký.
    2. Ngày trong phần đầu văn bản (trước Chương I), loại ngữ cảnh hiệu lực.
    3. Không đủ căn cứ thì trả về chuỗi rỗng và ghi cảnh báo.
    """
    text = re.sub(r"\s+", " ", text).strip()

    # Hỗ trợ ngày dạng "19 tháng 6 năm 2014", "2014-06-19",
    # hoặc "2014/06/19".
    date_pattern = (
        r"(?:"
        r"(?P<vn_day>\d{1,2})\s+tháng\s+"
        r"(?P<vn_month>\d{1,2})\s+năm\s+(?P<vn_year>\d{4})"
        r"|"
        r"(?P<iso_year>20\d{2})[-/](?P<iso_month>\d{1,2})[-/](?P<iso_day>\d{1,2})"
        r")"
    )

    def to_iso(match: re.Match) -> str:
        if match.group("vn_day"):
            return vietnamese_date_to_iso(
                match.group("vn_day"),
                match.group("vn_month"),
                match.group("vn_year"),
            )
        return (
            f"{int(match.group('iso_year')):04d}-"
            f"{int(match.group('iso_month')):02d}-"
            f"{int(match.group('iso_day')):02d}"
        )

    # Chỉ ưu tiên ngày nằm ngay sau cụm ngữ cảnh ban hành/thông qua/ký.
    # Cho phép có phần mô tả như "được Quốc hội ... thông qua ngày ...".
    contextual_patterns = [
        rf"(?:được\s+quốc hội\b.{{0,200}}?thông qua|"
        rf"quốc hội\b.{{0,200}}?thông qua|"
        rf"thông qua|ban hành|ngày ký|ký)\s+"
        rf"(?:vào\s+)?(?:ngày\s+)?{date_pattern}",
    ]

    for pattern in contextual_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return to_iso(match)

    # Dự phòng: tìm trong phần đầu văn bản, thường chứa thông tin ban hành.
    # Nếu tìm thấy Chương I thì không quét qua phần nội dung điều luật.
    chapter_match = re.search(r"(?<!\S)Chương\s+I\b", text, re.IGNORECASE)
    header = text[:chapter_match.start()] if chapter_match else text[:10000]

    for match in re.finditer(date_pattern, header, re.IGNORECASE):
        context = header[max(0, match.start() - 150):match.start()].lower()

        # Bỏ qua ngày xuất hiện trong ngữ cảnh hiệu lực thi hành.
        if re.search(r"hiệu lực(?:\s+thi hành)?|có hiệu lực", context):
            continue

        return to_iso(match)

    warn("Không tự nhận diện được issue_date.")
    return ""

# Ngày bắt đầu hiệu lực: lấy từ điều "Hiệu lực thi hành" (thường nằm gần cuối văn bản)
EFFECTIVE_HEADING_RE = re.compile(r"Điều\s+\d+[a-z]?\s*[.:]?\s*Hiệu lực\s+thi hành", re.IGNORECASE)
EFFECTIVE_HEADING_LOOSE_RE = re.compile(r"Điều\s+\d+[a-z]?\s*[.:]?\s*Hiệu lực\b", re.IGNORECASE)
NEXT_ARTICLE_RE = re.compile(r"Điều\s+\d+[a-z]?\s*[.:]\s*[A-ZĐ]")
HIEU_LUC_RE = re.compile(r"có\s+hiệu\s+lực", re.IGNORECASE)
CUT_AFTER_RE = re.compile(r"hết\s+hiệu\s+lực|bãi\s+bỏ|được\s+thay\s+thế", re.IGNORECASE)
SLASH_DATE_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")


def _effective_date_in_article(flat: str, heading) -> Optional[str]:
    """Ngày đầu tiên đứng sau cụm 'có hiệu lực' trong điều có tiêu đề `heading`."""
    nxt = NEXT_ARTICLE_RE.search(flat, heading.end())
    section = flat[heading.end(): nxt.start() if nxt else heading.end() + 2000]

    m = HIEU_LUC_RE.search(section)
    if not m:
        return None

    window = section[m.start(): m.start() + 250]
    cut = CUT_AFTER_RE.search(window)
    if cut:
        window = window[:cut.start()]

    candidates = []
    for rx in (DATE_RE, SLASH_DATE_RE):
        d = rx.search(window)
        if d:
            candidates.append((d.start(), d))

    if not candidates:
        return None

    _, d = min(candidates, key=lambda x: x[0])
    try:
        return vietnamese_date_to_iso(d.group(1), d.group(2), d.group(3))
    except ValueError:
        return None


def extract_effective_date(text: str) -> Optional[str]:
    """
    Ngày bắt đầu hiệu lực = ngày trong điều "Hiệu lực thi hành" của văn bản gốc.
    Chỉ đọc các điều có tiêu đề "Điều N. Hiệu lực thi hành" (không đọc phần mở đầu).
    Nếu có nhiều điều như vậy (bản hợp nhất kèm điều của các luật sửa đổi) thì lấy NGÀY CŨ NHẤT,
    vì luật gốc luôn có hiệu lực trước các lần sửa đổi.
    Trả về 'YYYY-MM-DD'; nếu không ghi ngày cụ thể (vd 'từ ngày ký', 'sau 45 ngày')
    thì trả về None và ghi cảnh báo.
    """
    flat = re.sub(r"\s+", " ", text)
    headings = list(EFFECTIVE_HEADING_RE.finditer(flat)) or list(EFFECTIVE_HEADING_LOOSE_RE.finditer(flat))

    if not headings:
        warn("Không tìm thấy điều 'Hiệu lực thi hành' để lấy effective_date.")
        return None

    dates = [d for d in (_effective_date_in_article(flat, h) for h in headings) if d]

    if not dates:
        warn("Điều 'Hiệu lực thi hành' không ghi ngày cụ thể; effective_date để trống.")
        return None

    return min(dates)  # chuỗi ISO so sánh theo thứ tự thời gian


def extract_issuing_body(text: str) -> str:
    # Cơ quan ban hành nằm ở phần đầu văn bản, TRƯỚC dòng tên văn bản
    # (NGHỊ ĐỊNH / THÔNG TƯ / ...). Chọn cơ quan xuất hiện sớm nhất trong phần đó,
    # để không bị nhầm với cơ quan chỉ được nhắc tới ở "Căn cứ"/"Theo đề nghị".
    head, title_start, _ = locate_document_title(text)
    header = head[:title_start] if title_start else ""

    if header:
        best = None

        for pattern, body in ISSUING_BODY_PATTERNS:
            m = pattern.search(header)

            if m and (best is None or m.start() < best[0]):
                best = (m.start(), body)

        if best:
            return best[1]

    # Dự phòng: cách cũ (quét 5000 ký tự đầu, tên dài thử trước)
    ordered = sorted(
        ISSUING_BODY_PATTERNS,
        key=lambda x: len(x[1]),
        reverse=True
    )

    for pattern, body in ordered:
        if pattern.search(text[:5000]):
            return body

    warn("Không tự nhận diện được issuing_body.")
    return ""


def extract_validity_status(text: str) -> str:
    """Tạm thời không tự suy đoán trạng thái hiệu lực từ nội dung văn bản."""
    return "Không xác định"

# Tên văn bản: chỉ nhận chữ IN HOA (phân biệt hoa/thường), bỏ qua "PHÁP LUẬT" trong
# dòng đầu trang kiểu "PHẦN VĂN BẢN QUY PHẠM PHÁP LUẬT".
TITLE_TYPE_RE = re.compile(
    r"(?<!PHÁP )(?<!\w)(?:BỘ LUẬT|LUẬT|NGHỊ ĐỊNH|THÔNG TƯ|QUYẾT ĐỊNH|CHỈ THỊ)(?!\w)"
)
TITLE_END_RE = re.compile(
    r"\s+(?:Căn cứ|Theo đề nghị|Quốc hội ban hành|Chương\s+I)\b"
)
TITLE_MAX_GAP = 600
TITLE_SELF_REF_RE = re.compile(r"\s+[Ss]ố\s*:?\s*\d{1,5}/\d{4}/")


def dedupe_repeated_title(title: str) -> str:
    """Nếu tiêu đề bị lặp 2 lần (khác nhau chỉ ở hoa/thường), chỉ giữ lần đầu.
    Ví dụ: 'LUẬT HÔN NHÂN VÀ GIA ĐÌNH Luật Hôn nhân và gia đình' -> 'LUẬT HÔN NHÂN VÀ GIA ĐÌNH'."""
    words = title.split()
    n = len(words)

    if n % 2 == 0 and n >= 4:
        half = n // 2

        if [w.lower() for w in words[:half]] == [w.lower() for w in words[half:]]:
            return " ".join(words[:half])

    return title


def locate_document_title(text: str):
    """Tìm tên văn bản. Trả về (head_đã_chuẩn_hóa, vị_trí_bắt_đầu, tiêu_đề) hoặc (head, None, None)."""
    head = re.sub(r"\s+", " ", text[:12000]).strip()

    for m in TITLE_TYPE_RE.finditer(head):
        end = TITLE_END_RE.search(head, m.end())

        if not end or end.start() - m.start() > TITLE_MAX_GAP:
            continue

        candidate = head[m.start():end.start()].strip()

        # Bản hợp nhất thường có: "<TÊN> <Tên> số 52/2014/QH13 ngày ... có hiệu lực ...":
        # chỉ giữ phần trước "số <số hiệu>".
        ref = TITLE_SELF_REF_RE.search(candidate)

        if ref and len(candidate[:ref.start()].split()) >= 2:
            candidate = candidate[:ref.start()].strip()

        candidate = dedupe_repeated_title(candidate)

        if 2 <= len(candidate.split()) <= 60:
            return head, m.start(), candidate

    return head, None, None


def clean_document_title_candidate(text: str) -> Optional[str]:
    head, _start, located = locate_document_title(text)

    if located:
        return located

    # Dự phòng: cách tìm cũ
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
            candidate = re.sub(r"\s+Số[:\s].*$", "", candidate, flags=re.IGNORECASE)
            if 2 <= len(candidate.split()) <= 40:
                return candidate
    m = re.search(
        r"\b(LUẬT|NGHỊ ĐỊNH|THÔNG TƯ|QUYẾT ĐỊNH|CHỈ THỊ)\b(.{0,300}?)(?=\s+(?:Căn cứ|Chương\s+I)\b)",
        head, re.IGNORECASE
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
        r"\b(?:LUẬT|NGHỊ ĐỊNH|THÔNG TƯ|QUYẾT ĐỊNH|CHỈ THỊ)\b.{0,200}?(?=\s+Chương\s+I\b)",
        head, re.IGNORECASE
    )
    if m:
        candidate = normalize_spaces(m.group(0))
        if candidate:
            return candidate
    warn("Không tự nhận diện được document title.")
    return Path("unknown").stem

def extract_metadata(raw_text: str, file_path: Optional[str] = None) -> dict:
    if file_path:
        document_id = normalize_document_id(file_path)
        file_stem = Path(file_path).stem
    else:
        document_id = "document"
        file_stem = ""

    document_number = extract_document_number(raw_text)

    # Đồng bộ metadata với data/reference/document_versions.json
    versions_file = Path(__file__).resolve().parent.parent / "data" / "reference" / "document_versions.json"
    matched_entry = None
    if versions_file.exists():
        try:
            with open(versions_file, "r", encoding="utf-8") as f:
                versions_data = json.load(f)
            for entry in versions_data:
                if file_stem and (entry.get("file_code") == file_stem or entry.get("document_id") == file_stem):
                    matched_entry = entry
                    break
                if document_number and (
                    entry.get("document_number") == document_number
                    or document_number.startswith(entry.get("document_number", "___"))
                    or entry.get("document_number", "").startswith(document_number)
                ):
                    matched_entry = entry
                    break
        except Exception as ex:
            warn(f"Không thể đọc document_versions.json: {ex}")

    extracted_effective_date = extract_effective_date(raw_text)
    extracted_issue_date = extract_issue_date(raw_text)

    validity_status = "Không xác định"
    expiry_date = None
    source_url = ""

    if matched_entry:
        raw_status = matched_entry.get("status") or matched_entry.get("validity_status") or ""
        validity_status = VALIDITY_STATUS_MAP.get(raw_status, "Không xác định")
        expiry_date = matched_entry.get("expiry_date") or None
        if expiry_date == "":
            expiry_date = None
        source_url = matched_entry.get("source_url") or ""
        if not extracted_effective_date and matched_entry.get("effective_date"):
            extracted_effective_date = matched_entry.get("effective_date")
        if not extracted_issue_date and matched_entry.get("issue_date"):
            extracted_issue_date = matched_entry.get("issue_date")
    else:
        validity_status = extract_validity_status(raw_text)

    return {
        "title": extract_document_title(raw_text),
        "document_type": resolve_document_type(raw_text, document_number),
        "document_number": document_number,
        "issue_date": extracted_issue_date,
        "effective_date": extracted_effective_date,
        "expiry_date": expiry_date,
        "source_url": source_url,
        "issuing_body": extract_issuing_body(raw_text),
        "validity_status": validity_status,
    }

def parse_raw_text_to_legal_doc(raw_text: str, doc_id: str, metadata: dict) -> dict:
    meta = LegalMetadata(**metadata)
    articles, footnotes = parse_text_to_articles(raw_text, doc_id)
    doc = LegalDocumentSchema(
        document_id=doc_id,
        metadata=meta,
        articles=articles,
        footnotes=footnotes,
    )
    return doc.model_dump()

def parse_legal_document_to_schema(file_path: str):
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Đường dẫn file không hợp lệ: {path.resolve()}")
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        content = unicodedata.normalize("NFC", f.read())
    number = extract_document_number(content)
    doc_id = build_document_id(resolve_document_type(content, number), number)
    return parse_text_to_articles(content, doc_id)


def quality_report(articles, footnotes):
    last_article = articles[-1]["article_number"] if articles else "N/A"
    print(f"\n[report] Số Điều: {len(articles)} (Điều cuối: {last_article})")
    print(f"[report] Số Khoản (clauses): {sum(len(a['clauses']) for a in articles)}")

    if articles:
        nums = [int(a["article_number"]) for a in articles]
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        if missing:
            print(f"[report] CẢNH BÁO: thiếu Điều: {missing}")
        else:
            print(f"[report] Chuỗi Điều liên tục: 1 -> {max(nums)}")

    sus_footnote = re.compile(r"Luật số \d+/\d{4}/QH|Cụm từ “")
    sus_heading = re.compile(rf"(?<!\S)(Chương [IVXLC]+|Mục \d+) [{UP}]{{2}}")
    bad = []

    for a in articles:
        for c in a["clauses"]:
            t = c["clause_text"]
            if sus_footnote.search(t) or sus_heading.search(t):
                bad.append((c["clause_id"], "lẫn chú thích/tiêu đề Chương-Mục"))
            elif not re.search(r"[.;:”)]$", t):
                bad.append((c["clause_id"], "không kết thúc bằng dấu câu (nghi dư số trang)"))

    print(f"[report] Khoản đáng nghi: {len(bad)}")
    for cid, why in bad[:15]:
        print(f"   - {cid}: {why}")

    empty_title = [a["article_number"] for a in articles if not a["article_title"]]
    if empty_title:
        print(f"[report] Điều chưa có tiêu đề: {empty_title}")

    for w in WARNINGS[:30]:
        print("[warn]", w)
    if len(WARNINGS) > 30:
        print(f"[warn] ... và {len(WARNINGS) - 30} cảnh báo khác")
