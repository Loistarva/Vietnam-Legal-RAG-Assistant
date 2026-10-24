"""Thư viện parse văn bản luật (TXT) thành JSON theo Điều / Khoản (Kiến trúc 4 tầng). Không có main; entry point là test_parser.py."""
import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


MAX_TITLE_WORDS = 80
MAX_TITLE_CHARS = 450

UP = "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"


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
        if "\\x00" in v:
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
        if "\\x00" in v:
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


class BaseSchema(BaseModel):
    """Base schema chung cho các model dữ liệu của parser."""
    pass


class DocumentMetadataSchema(BaseSchema):
    title: str = Field(..., min_length=5)
    document_type: str
    document_number: str
    issue_date: str
    effective_date: Optional[str] = None
    issuing_body: str
    validity_status: str
    expiry_date: Optional[str] = None
    source_url: str = ""


class LegalDocumentSchema(BaseModel):
    document_id: str = Field(..., pattern=r"^[A-Za-z0-9_]+$")
    metadata: DocumentMetadataSchema
    articles: List[ArticleSchema] = Field(..., min_length=1)
    footnotes: List[str] = Field(default_factory=list)


WARNINGS: List[str] = []


def warn(msg: str):
    WARNINGS.append(msg)


# Chỉ nhận Chương/Mục nếu phần tiêu đề thực sự giống heading.
# Hỗ trợ CHƯƠNG/Chương, số La Mã hoặc Ả Rập, và dấu hai chấm.
_HEADING_LABEL = r"(?:Chương\s+(?:[IVXLCDM]+|\d+)|Mục\s+\d+)\s*[.:]?"
HEAD_LABEL_RE = re.compile(rf"(?<!\S)({_HEADING_LABEL})(?=\s)", re.IGNORECASE)
HEAD_RE = HEAD_LABEL_RE  # Giữ tên cũ cho quality_report

HEADING_BOUNDARY_RE = re.compile(
    rf"(?<!\S)(?:{_HEADING_LABEL}|Điều\s+\d+[a-z]?\.)",
    re.IGNORECASE
)


def uppercase_ratio(text: str) -> float:
    """Tỷ lệ chữ cái viết hoa trong đoạn; bỏ qua chữ số và dấu câu."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(ch.isupper() for ch in letters) / len(letters)


# Số dòng tối đa được ghép thêm vào tiêu đề Chương/Mục khi tiêu đề bị xuống dòng.
# Tiêu đề dài nhất hiện có chiếm 5 dòng (TT 38/2025 Chương II, TT 04/2020 Mục 5);
# việc ghép vẫn dừng ở mốc cấu trúc kế tiếp hoặc dòng không viết hoa.
MAX_HEADING_CONTINUATION_LINES = 8
# Dòng bắt đầu một cấu trúc mới (Điều 52, CHƯƠNG 3, Mục 2, Phần I...), không phải phần tiếp của tiêu đề.
_STRUCTURAL_LINE_RE = re.compile(r"(?i)^(?:điều|chương|mục|phần)\s+(?:\d+|[ivxlcdm]+)\b")


def _heading_title_candidate(fragment: str, label_match: re.Match, next_boundary: Optional[re.Match]) -> str:
    """Lấy phần tiêu đề gần nhãn nhất, tránh gộp header/trang sau vào tiêu đề."""
    title_start = label_match.end()
    title_end = next_boundary.start() if next_boundary else len(fragment)
    segment = fragment[title_start:title_end]

    # Nếu còn xuống dòng, ưu tiên phần cùng dòng với nhãn; nếu nhãn đứng riêng
    # thì lấy dòng không rỗng kế tiếp. Tiêu đề dài bị PDF xuống dòng thì ghép thêm
    # các dòng liền sau nếu chúng viết hoa rõ ràng (vd. "...VỚI NGƯỜI" + "NƯỚC NGOÀI").
    # Nếu text đã bị làm phẳng, dùng cả segment.
    lines = segment.splitlines()
    if len(lines) > 1:
        strip_chars = " \t\r\n:–—-;,. "
        parts: List[str] = []
        for line in lines:
            candidate = line.strip(strip_chars)
            if not parts:
                if candidate:
                    # Dấu câu cuối dòng ("...KẾT HÔN," / "...PHÔI;") là của tiêu đề:
                    # chỉ bỏ dấu ở đầu dòng (sau nhãn), dấu cuối bỏ khi ghép xong.
                    parts.append(line.strip().lstrip(strip_chars))
                continue
            # Dòng sau chỉ được ghép khi là phần xuống dòng của tiêu đề: không rỗng,
            # viết hoa rõ ràng, không phải nhãn cấu trúc (Điều/Chương/Mục/Phần N).
            if (
                not candidate
                or uppercase_ratio(candidate) < 0.80
                or _STRUCTURAL_LINE_RE.match(candidate)
                or len(parts) > MAX_HEADING_CONTINUATION_LINES
            ):
                break
            parts.append(line.strip().lstrip(strip_chars))
        if parts:
            return re.sub(r"\s+", " ", " ".join(parts)).strip(strip_chars)
    return re.sub(r"\s+", " ", segment).strip(" \t\r\n:–—-;,. ")


def iter_headings(fragment: str):
    """Sinh (vị_trí_bắt_đầu, nhãn, tiêu_đề) chỉ cho heading viết hoa rõ ràng."""
    matches = list(HEAD_LABEL_RE.finditer(fragment))
    for m in matches:
        boundary = HEADING_BOUNDARY_RE.search(fragment, m.end())
        title = _heading_title_candidate(fragment, m, boundary)
        if not title:
            continue
        if len(title) > 300:
            warn(f"Heading {m.group(1)!r} có tiêu đề dài bất thường ({len(title)} ký tự); không tự động dùng làm chapter/section.")
            continue
        # Chặn câu dẫn chiếu như "... các tội quy định tại Chương XIV Bộ luật Hình sự ...".
        if uppercase_ratio(title) < 0.80:
            continue
        label = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(":. ")
        yield m.start(), label, title


def update_headings(fragment: str, state: Dict[str, Optional[str]]):
    for _start, label, title in iter_headings(fragment):
        if label.lower().startswith("chương"):
            state["chapter"] = f"{label} {title}".strip()
            state["section"] = None
        else:
            state["section"] = f"{label} {title}".strip()


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
    """Nhận diện đầu Khoản kể cả khi câu mở đầu bằng dấu ngoặc kép.

    Hỗ trợ các dạng: `1. Nội dung`, `1. “Nội dung”` và `1.“Nội dung”`.
    Chỉ chấp nhận chữ hoa sau dấu ngoặc mở để hạn chế nhận nhầm số thứ tự
    nằm giữa câu thành ranh giới Khoản.
    """
    opening_quote = r'[“‘"«]'
    return re.compile(
        rf"(?<!\S){k}\.(?=\s*(?:{opening_quote}\s*)?[{UP}])\s*"
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
    "Yêu cầu", "Hội Liên hiệp", "Bộ Tư pháp", "Bộ Ngoại giao", "Bộ Công an",
    "Vợ hoặc chồng", "Vợ, chồng", "Vợ", "Chồng",
    "Các Bộ", "Trong vụ án", "Trong trường hợp", "Ủy ban nhân dân",
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
        if len(title.split()) > MAX_TITLE_WORDS or len(body) < 25:
            continue
        if re.search(r"[.!?]$", title):
            continue
        # Không cắt tại danh từ riêng nằm trong tiêu đề (ví dụ "Việt Nam").
        # Điểm cắt chỉ đáng tin khi phần sau mở đầu bằng cụm quy phạm thường gặp.
        if not any(body.startswith(phrase) for phrase in ARTICLE_BODY_STARTS):
            continue
        return title, body
    return None


# Chữ hoa mở đầu thường là danh từ riêng/tên văn bản nằm TRONG tiêu đề, không phải đầu câu.
PROPER_NOUN_PREFIXES = {
    "Bộ", "Luật", "Nghị", "Thông", "Hiến", "Việt", "Quốc", "Hội", "Tòa",
    "Viện", "Ủy", "Chính", "Nhà", "Hôn", "Hợp", "Cộng", "Liên", "Tổng", "Hà", "Thành",
}


def split_title_by_capital_loose(head: str) -> Optional[Tuple[str, str]]:
    """Dự phòng khi nội dung mở đầu bằng cụm KHÔNG có trong ARTICLE_BODY_STARTS
    (ví dụ "Giữa", "Vì lợi ích", "Sau khi", "Thời hạn").

    Chọn chữ hoa đầu tiên đứng sau một từ thường, không phải từ nối, không thuộc
    PROPER_NOUN_PREFIXES; phần sau phải đủ dài và phần trước không có dấu kết câu."""
    head = normalize_spaces(head)
    tokens = head.split(" ")
    pos, offsets = 0, []
    for tok in tokens:
        offsets.append(pos)
        pos += len(tok) + 1
    for i in range(3, len(tokens)):
        tok, prev = tokens[i], tokens[i - 1]
        if not tok or not tok[0].isupper() or not prev:
            continue
        if prev[-1:] in ",;:" or prev.lower().strip(",;:") in TITLE_CONNECTORS:
            continue
        if prev[0].isupper() and prev[1:].islower():  # "Việt" / "Nam"
            continue
        if tok.strip(",;:.") in PROPER_NOUN_PREFIXES:
            continue
        title = head[:offsets[i]].strip(" ,;:")
        body = head[offsets[i]:].strip()
        if not (3 <= len(title.split()) <= MAX_TITLE_WORDS) or len(body) < 40:
            continue
        if re.search(r"[.!?]$", title):
            continue
        return title, body
    return None


def split_title_best(head: str) -> Optional[Tuple[str, str]]:
    """Chọn ranh giới tiêu đề/nội dung sớm nhất giữa bản chặt và bản lỏng."""
    found = [r for r in (split_title_by_capital(head), split_title_by_capital_loose(head)) if r]
    return min(found, key=lambda r: len(r[0])) if found else None


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
            split = split_title_best(before)
            if split:
                t, lead = split
                intro = f"{lead}: {after}".strip() if after else f"{lead}:"
                return t, intro
            if looks_like_title(before):
                intro = after
                return before, intro or None
        return None, head

    best = split_title_best(head)
    if best:
        return best[0], best[1]

    sentences = split_sentences(head)
    if len(sentences) >= 2:
        candidate = sentences[0]
        remainder = " ".join(sentences[1:]).strip()
        if looks_like_title(candidate):
            # TXT có thể làm rơi dấu xuống dòng giữa tiêu đề và phần bổ nghĩa.
            # Nếu phần sau bắt đầu bằng chữ thường, thường đó là phần tiếp của
            # tiêu đề bị tách nhầm (ví dụ: "... gia đình" + "có yếu tố nước ngoài.").
            # Không ghép nếu phần sau có dấu hiệu rõ của câu dẫn/nội dung.
            remainder_first = remainder[:1]
            title_continuation = bool(
                remainder_first and remainder_first.islower()
                and len(remainder.split()) <= 18
                and not re.match(
                    r"(?i)^(theo quy định|trong trường hợp|việc|người|các bên|cơ quan|nếu|khi)\b",
                    remainder,
                )
            )
            if title_continuation and not candidate.endswith((":", ";")):
                return normalize_spaces(candidate + " " + remainder).rstrip("."), None
            return candidate, remainder or None

    if looks_like_title(head):
        return head, None

    warn(f"Không chắc chắn title tự động: {head[:120]!r}")
    return None, head


# Từ đầu của tên riêng nhiều từ; nếu dòng tiêu đề kết thúc bằng một trong các từ này
# thì dòng sau chắc chắn là phần tiếp ("Việt / Nam", "Luật / Hôn nhân và gia đình").
PROPER_NOUN_LINE_ENDINGS = {
    "Việt", "Luật", "Bộ", "Hiến", "Nghị", "Cộng", "Liên", "Quốc", "Hội", "Ủy",
    "Thành", "Hà", "Hồ", "Đà", "Cần",
}


def split_title_from_line_structure(head: str) -> Optional[Tuple[str, str]]:
    """Tách tiêu đề khỏi nội dung dựa trên cấu trúc xuống dòng của TXT.

    Nguyên tắc bảo thủ:
    - Dừng trước dòng có dấu hiệu rõ ràng là câu/nội dung quy phạm.
    - Chỉ nối dòng tiếp theo khi có dấu hiệu hợp lý rằng tiêu đề bị wrap.
    - Không mặc định nối mọi dòng không kết thúc bằng dấu câu vào tiêu đề.
    """
    if "\n" not in head:
        return None

    lines = [normalize_spaces(line).strip() for line in head.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    first_line = lines[0].strip(" :;")
    if not first_line or len(first_line) > MAX_TITLE_CHARS:
        return None

    # title_lines (đã bỏ " :;" hai đầu) dùng để quyết định có ghép dòng hay không;
    # title_parts giữ dấu câu cuối dòng ("...nước ngoài;" + "cấp Giấy...") cho tiêu đề xuất ra.
    title_lines = [first_line]
    title_parts = [lines[0].lstrip(" :;")]
    idx = 1

    # Các từ/cụm cuối dòng thường cho thấy tiêu đề còn thiếu phần bổ nghĩa.
    title_incomplete_endings = {
        "của", "và", "về", "với", "theo", "trong", "cho", "hoặc", "tại",
        "từ", "đến", "do", "bởi", "như", "đối", "để", "nhằm", "bằng",
        "là", "có", "được", "bị", "trên", "dưới", "ở", "qua", "sau",
        "trước", "mà", "bao", "gồm", "giữa",
    }

    while idx < len(lines):
        line = lines[idx].strip(" :;")
        if not line:
            idx += 1
            continue

        previous = title_lines[-1].rstrip()
        previous_tokens = re.findall(r"[A-Za-zÀ-ỹĐđ0-9]+", previous)
        previous_word = previous_tokens[-1].lower() if previous_tokens else ""
        previous_tail = " ".join(w.lower() for w in previous_tokens[-2:])

        # Nội dung thường mở đầu bằng các cụm quy phạm này. So khớp có phân biệt
        # hoa/thường để không chặn nhầm phần tiêu đề như "Trung tâm", "Thông tin...".
        previous_last_raw = re.findall(r"[A-Za-zÀ-ỹĐđ0-9]+", previous)
        previous_proper_prefix = bool(
            previous_last_raw and previous_last_raw[-1] in PROPER_NOUN_LINE_ENDINGS
            and len(previous_last_raw) >= 2
        )
        if previous_proper_prefix:
            title_lines.append(line.rstrip("."))
            title_parts.append(lines[idx].lstrip(" :;").rstrip("."))
            idx += 1
            continue

        starts_body = any(line.startswith(phrase) for phrase in ARTICLE_BODY_STARTS)
        if starts_body and not (
            previous.endswith((",", ";", ":", "-", "–", "—"))
            or previous_word in title_incomplete_endings
            or previous_tail in title_incomplete_endings
        ):
            break

        # Phần bổ nghĩa viết thường ở đầu dòng có thể là phần tiếp của tiêu đề,
        # kể cả khi dòng kết thúc bằng dấu chấm (vd. "có yếu tố nước ngoài.").
        first_char = next((ch for ch in line if ch.isalpha()), "")
        starts_lowercase = bool(first_char and first_char.islower())
        if starts_lowercase:
            prev_tokens = re.findall(r"[A-Za-zÀ-ỹĐđ0-9]+", previous)
            prev_word = prev_tokens[-1].lower() if prev_tokens else ""
            prev_tail = " ".join(w.lower() for w in prev_tokens[-2:])

            # Dòng bắt đầu bằng chữ thường thường là phần tiêu đề bị wrap,
            # ví dụ "... tài khoản chứng khoán, động" + "sản khác ...".
            # Chỉ nối khi dòng trước chưa kết thúc một câu hoàn chỉnh; không
            # dùng giới hạn độ dài cứng vì dòng wrap có thể dài.
            previous_is_sentence_end = bool(re.search(r"[.!?]$", previous))
            if (
                not previous_is_sentence_end
                and not line.endswith((":", ";"))
            ):
                title_lines.append(line.rstrip("."))
                title_parts.append(lines[idx].lstrip(" :;").rstrip("."))
                idx += 1
                continue

        # Dòng kết thúc bằng dấu câu hoàn chỉnh thường là nội dung, không phải title.
        if re.search(r"[.!?]$", line):
            break

        # Chỉ nối dòng viết hoa khi dòng trước có dấu hiệu tiêu đề còn dang dở,
        # hoặc dòng trước kết thúc bằng danh từ riêng viết hoa bị ngắt dòng.
        # Dòng viết thường có thể là phần tiếp nối của tiêu đề bị wrap.
        first_char = next((ch for ch in line if ch.isalpha()), "")
        starts_lowercase = bool(first_char and first_char.islower())
        previous_ends_punctuation = previous.endswith((",", ";", ":", "-", "–", "—"))
        previous_incomplete = (
            previous_ends_punctuation
            or previous_word in title_incomplete_endings
            or previous_tail in title_incomplete_endings
        )
        # Chỉ coi là tên riêng bị ngắt dòng nếu từ cuối của dòng trước viết hoa
        # nhưng không phải từ đầu dòng (ví dụ "... Việt" / "Nam").
        previous_words = previous.split()
        last_token = previous_words[-1].strip(".,;:()[]{}") if previous_words else ""
        previous_ends_capitalized_word = bool(
            len(previous_words) >= 2
            and last_token
            and last_token[0].isupper()
            and last_token[1:].islower()
        )

        # Dòng dài giống câu nội dung không được nối, trừ khi tiêu đề có dấu hiệu
        # ngữ pháp mạnh cho thấy nó đang tiếp diễn.
        continuation_limit = max(24, int(len(first_line) * 0.72))
        if len(line) > continuation_limit and not previous_incomplete:
            break

        if starts_lowercase or previous_incomplete or previous_ends_capitalized_word:
            title_lines.append(line)
            title_parts.append(lines[idx].lstrip(" :;"))
            idx += 1
            continue

        # Không có bằng chứng đủ mạnh: xem dòng này là phần nội dung.
        break

    if idx >= len(lines):
        # Toàn bộ các dòng còn lại là phần tiếp của tiêu đề; không có remainder.
        title = normalize_spaces(" ".join(title_parts)).rstrip(" :;,")
        if title and len(title.split()) <= MAX_TITLE_WORDS:
            return title.rstrip("."), ""
        return None

    title = normalize_spaces(" ".join(title_parts)).rstrip(" :;,")
    remainder = normalize_spaces(" ".join(lines[idx:]))

    if not title or not remainder or re.search(r"[.!?]$", title):
        return None

    # Chặn tiêu đề bất thường dài, dấu hiệu phổ biến khi nội dung bị nuốt vào title.
    if len(title.split()) > MAX_TITLE_WORDS:
        warn(f"Tiêu đề dài bất thường ({len(title.split())} từ); kiểm tra tách title/body: {title[:120]!r}")
        return None

    return title, remainder


def merge_title_continuation(title: Optional[str], intro: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Ghép lại phần bổ nghĩa ngắn bị tách nhầm khỏi tiêu đề."""
    if not title or not intro:
        return title, intro
    intro_norm = normalize_spaces(intro)
    words = intro_norm.split()
    if (
        words
        and words[0][:1].islower()
        and len(words) <= 20
        and not re.match(
            r"(?i)^(theo quy định|trong trường hợp|việc|người|các bên|cơ quan|nếu|khi|được thực hiện|phải)\b",
            intro_norm,
        )
        and not title.rstrip().endswith((":", ";", ".", "!", "?"))
    ):
        return normalize_spaces(title + " " + intro_norm).rstrip("."), None
    return title, intro


def split_head(num: str, raw: str):
    first = clause_regex(1).search(raw)
    if first:
        head = raw[:first.start()].strip()
        body = raw[first.start():].strip()
    else:
        head = raw.strip()
        body = ""

    # Ưu tiên ranh giới dòng của TXT đã qua cleaner. Điều này giữ được danh từ
    # riêng trong tiêu đề (Bộ Tư pháp, Bộ Ngoại giao, Việt Nam...) và tiêu đề wrap.
    line_split = split_title_from_line_structure(head)
    if line_split:
        title, remainder = line_split
        if first:
            return title, remainder or None, body, True
        if remainder:
            return title, None, remainder, False
        # Không có Khoản 1 và cả head bị nối thành "tiêu đề" -> đây là nội dung Điều
        # không có tiêu đề riêng; giữ nguyên làm body.
        return None, None, head, False

    # Phần head chỉ có MỘT dòng và dòng đó không kết thúc bằng dấu câu: đó là dòng
    # tiêu đề (không có intro). Không được coi là text bị làm phẳng rồi cắt tại chữ
    # hoa giữa dòng (vd. "Người có quyền yêu cầu Tòa án chấm dứt việc nuôi con nuôi").
    # Text làm phẳng thật sự có intro thì kết thúc bằng ":" hoặc dấu chấm nên không vào đây.
    if first:
        head_lines = [ln for ln in head.splitlines() if ln.strip()]
        if len(head_lines) == 1:
            only = normalize_spaces(head_lines[0]).strip()
            if (
                only
                and not re.search(r"[.!?:;]$", only)
                and len(only.split()) <= MAX_TITLE_WORDS
            ):
                return only, None, body, True

    # Khi có Khoản 1, vẫn dò điểm bắt đầu nội dung nếu phần head có câu quy phạm
    # bị dính ngay sau tiêu đề; nếu không có điểm cắt đáng tin cậy thì dùng detector cũ.
    if first:
        flat_split = split_title_by_capital(head) or split_title_from_unlabelled_body(head)
        if flat_split:
            title, intro = flat_split
            return title, intro or None, body, True
        title, intro = detect_title_and_intro(head)
        title, intro = merge_title_continuation(title, intro)
        if title is None and intro and not re.search(r"[.!?:]$", intro) and len(intro.split()) <= 40:
            title, intro = intro, None
        return title, intro, body, True

    # Phương án dự phòng cho TXT đã bị làm phẳng.
    split_result = split_title_by_capital(head) or split_title_from_unlabelled_body(head)
    if split_result:
        title, body = split_result
        return title, None, body, False

    title, intro = detect_title_and_intro(head)
    title, intro = merge_title_continuation(title, intro)
    if title and intro:
        body = intro
        intro = None
    elif title:
        body = raw
    else:
        body = raw
    return title, intro, body, False


def marker_has_no_title_on_line(marker_text: str) -> bool:
    """True nếu dòng "Điều N." không có chữ nào phía sau (xuống dòng ngay sau dấu chấm).

    `marker_text` là đoạn khớp của find_articles, gồm cả khoảng trắng sau "Điều N.".
    Ví dụ Luật HNGĐ 1986: TXT chỉ có dòng "Điều 1." rồi nội dung ở dòng kế tiếp; văn bản
    này không có tiêu đề Điều, nên không được lấy câu đầu của nội dung làm tiêu đề.
    """
    after_dot = marker_text[marker_text.rfind(".") + 1:]
    return "\n" in after_dot


def split_head_without_title(raw: str):
    """Tách phần đầu Điều khi Điều không có tiêu đề: title = None, không gọi hàm tách tiêu đề.

    Toàn bộ nội dung được giữ nguyên: nếu có Khoản 1 thì phần trước Khoản 1 là intro,
    nếu không thì cả đoạn là body của một Khoản duy nhất.
    """
    first = clause_regex(1).search(raw)
    if first:
        head = normalize_spaces(raw[:first.start()])
        body = raw[first.start():].strip()
        return None, (head or None), body, True
    return None, None, raw.strip(), False


def clean_clause_text(text: str) -> str:
    """Làm phẳng xuống dòng thật và chuỗi escape literal \n thành một dấu cách.

    Dùng ở tầng clause_text để JSON không chứa các chuỗi \n do file TXT đầu vào
    đã ghi literal, đồng thời tránh nối dính từ ở hai phía của xuống dòng.
    """
    text = text.replace("\\n", " ")  # hai ký tự literal: backslash + n
    return normalize_spaces(text)


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
                clause_text=clean_clause_text(body),
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
                    clause_text=clean_clause_text(ctext),
                    chunks=None
                )
            )
    return clauses


ARTICLE_MARKER_ANY_RE = re.compile(
    r"(?<!\S)Điều\s+\d+[a-z]?\.\s+(?=[" + UP + r"])",
    re.IGNORECASE,
)

# Dấu kết thúc văn bản/ký tên thường xuất hiện sau Điều cuối, trước phụ lục
# hoặc biểu mẫu. Không phụ thuộc vào tiêu đề "PHỤ LỤC"/"Mẫu số".
TERMINAL_MARKER_PATTERNS = (
    ("./.", re.compile(r"\./\.")),
    # Văn bản hợp nhất thường có dòng xác nhận của Văn phòng Quốc hội sau Điều cuối.
    ("VĂN PHÒNG QUỐC HỘI / số hiệu văn bản hợp nhất", re.compile(
        r"(?im)^\s*VĂN\s+PHÒNG\s+QUỐC\s+HỘI(?:\s*Số\s*:\s*\d+\s*/\s*VBHN-VPQH)?\b"
    )),
    ("Nơi nhận:", re.compile(r"(?i)(?<!\S)Nơi\s+nhận\s*:")),
    (
        "chức danh ký",
        re.compile(
            r"(?i)(?<!\S)(?:TM|KT|Q|TL)\.\s+"
            r"(?=(?:BỘ\s+TRƯỞNG|THỨ\s+TRƯỞNG|CHỦ\s+TỊCH|PHÓ\s+CHỦ\s+TỊCH|"
            r"THỦ\s+TƯỚNG|PHÓ\s+THỦ\s+TƯỚNG|TỔNG\s+THƯ\s+KÝ|"
            r"CHÁNH\s+ÁN|VIỆN\s+TRƯỞNG|BỘ\s+TRƯỞNG|GIÁM\s+ĐỐC))"
        ),
    ),
    ("CHỦ TỊCH QUỐC HỘI", re.compile(r"(?i)(?<!\S)CHỦ\s+TỊCH\s+QUỐC\s+HỘI")),
    ("(Đã ký)", re.compile(r"(?i)\(\s*Đã\s+ký\s*\)")),
    # Chức danh ký đứng riêng một dòng, viết hoa (TM. CHÍNH PHỦ / THỦ TƯỚNG / PHÓ THỦ TƯỚNG).
    # Phân biệt hoa/thường để không cắt nhầm "Thủ tướng Chính phủ" trong nội dung.
    ("TM./KT. CHÍNH PHỦ", re.compile(r"(?<!\S)(?:TM|KT|Q|TL)\.\s+CHÍNH\s+PHỦ\b")),
    ("dòng chức danh THỦ TƯỚNG", re.compile(r"(?m)^\s*(?:KT\.\s+)?(?:PHÓ\s+)?THỦ\s+TƯỚNG\b(?:[ \t]*$|[ \t]+[A-ZĐ][a-zà-ỹ])")),
    ("TM. HỘI ĐỒNG THẨM PHÁN", re.compile(
    r"(?i)(?<!\S)(?:TM|KT|Q|TL)\.\s+HỘI\s+ĐỒNG\s+THẨM\s+PHÁN\b")),
)

# Các dấu hiệu mà tên người ký thường đứng NGAY TRƯỚC (tên ký rồi mới tới chức danh /
# "(Đã ký)" / khối xác thực VBHN). Khi cắt tại các dấu hiệu này, bỏ luôn dòng tên người ký
# để không phải liệt kê từng tên viết cứng.
SIGNER_PRECEDES_LABELS = frozenset({
    "VĂN PHÒNG QUỐC HỘI / số hiệu văn bản hợp nhất",
    "chức danh ký",
    "CHỦ TỊCH QUỐC HỘI",
    "(Đã ký)",
    "TM./KT. CHÍNH PHỦ",
    "dòng chức danh THỦ TƯỚNG",
})

_SIGNER_WORD = rf"[{UP}][^\W\d_]*"
# Tên người ký: 2–4 từ, mỗi từ bắt đầu bằng chữ hoa (Title Case hoặc IN HOA),
# không có chữ số / dấu câu.
SIGNER_NAME_RE = re.compile(rf"^{_SIGNER_WORD}(?:\s+{_SIGNER_WORD}){{1,3}}$")
_SIGNER_NOT_NAME_FIRST_WORDS = frozenset({"chương", "mục", "phần", "điều", "khoản", "điểm", "phụ"})
_SENTENCE_END_RE = re.compile(r"[.;:!?]\s+")


def strip_trailing_signer_name(text: str, min_pos: int = 0) -> str:
    """Bỏ tên người ký (dòng ngắn 2–4 từ viết hoa) nằm ở cuối `text`.

    Chỉ nhìn đoạn cuối: ưu tiên dòng cuối cùng; nếu tên dính cùng dòng với nội dung
    thì lấy phần sau dấu kết câu cuối cùng. Không bao giờ cắt lùi quá `min_pos`.
    """
    body = text.rstrip()
    line_start = body.rfind("\n") + 1
    tail = body[line_start:]

    candidates = [line_start]
    ends = list(_SENTENCE_END_RE.finditer(tail))
    if ends:
        candidates.append(line_start + ends[-1].end())

    for start in candidates:
        if start <= min_pos:
            continue
        segment = body[start:].strip()
        if not SIGNER_NAME_RE.match(segment):
            continue
        if segment.split()[0].lower() in _SIGNER_NOT_NAME_FIRST_WORDS:
            continue
        return body[:start].rstrip()
    return body


def strip_terminal_material(text: str) -> str:
    """Bỏ phần ký ban hành/nơi nhận và phụ lục sau phần quy phạm cuối.

    Cắt tại dấu hiệu kết thúc xuất hiện sớm nhất. Dùng nhiều dấu hiệu vì một số
    văn bản không có './.' ở cuối Điều (ví dụ kết thúc bằng 'KT. BỘ TRƯỞNG').
    Hàm chạy trước khi tách Điều/Khoản để phần thừa không lọt vào intro/clause.
    """
    first_article = ARTICLE_MARKER_ANY_RE.search(text)
    if not first_article:
        return text

    candidates = []
    for label, pattern in TERMINAL_MARKER_PATTERNS:
        match = pattern.search(text, first_article.end())
        if match:
            candidates.append((match.start(), label))

    if not candidates:
        return text

    cut_pos, label = min(candidates, key=lambda item: item[0])
    # Chỉ cắt nếu trước dấu hiệu đã có nội dung Điều đáng kể; tránh xóa văn bản
    # khi một từ khóa tình cờ xuất hiện ngay sau Điều đầu.
    if cut_pos <= first_article.end():
        return text

    kept = text[:cut_pos].rstrip()
    if label in SIGNER_PRECEDES_LABELS:
        stripped = strip_trailing_signer_name(kept, min_pos=first_article.end())
        if len(stripped) < len(kept):
            print(f"[clean] đã bỏ tên người ký: {kept[len(stripped):].strip()!r}")
            kept = stripped

    removed_chars = len(text) - len(kept)
    print(
        f"[clean] đã bỏ phần cuối văn bản từ dấu hiệu {label!r} "
        f"tại vị trí {cut_pos} ({removed_chars} ký tự)"
    )
    return kept


# "-" dính chữ/số phía trước ở cuối dòng, dòng sau mở đầu bằng chữ hoa hoặc chữ số
# nhưng không phải Khoản ("2. ") hay mốc cấu trúc (Điều/Chương/Mục/Phần).
HYPHEN_LINE_BREAK_RE = re.compile(
    r"(?<=[0-9A-Za-zÀ-ỹĐđ])- ?\n ?"
    r"(?=[0-9A-ZĐ])(?!\d+\.\s)(?!(?:Điều|Chương|CHƯƠNG|Mục|MỤC|Phần|PHẦN)\s)"
)


def parse_text_to_articles(raw_text: str, doc_id: str):
    WARNINGS.clear()
    # Chuẩn hóa Unicode về NFC: TXT trích từ PDF hay chứa ký tự tiếng Việt dạng
    # tổ hợp (NFD, vd "Ệ" = "E" + dấu mũ + dấu nặng). Khi đó các regex/từ khóa
    # dựng sẵn (UP, ARTICLE_BODY_STARTS, "Các bên"...) không khớp.
    raw_text = unicodedata.normalize("NFC", raw_text)
    raw_text = re.sub(r"[\u200b-\u200d\u2060\ufeff\u00ad]", "", raw_text)  # ký tự vô hình
    # Giữ xuống dòng để nhận diện heading theo cấu trúc PDF; không làm phẳng trước
    # khi xác định Chương/Mục. Các hàm tách Điều/Khoản vẫn chấp nhận whitespace.
    text = re.sub(r"[ \t\f\v]+", " ", raw_text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # PDF xuống dòng ngay sau "-" của số hiệu, ngày ("126/2014/NĐ-" + "CP", "10-5-" + "2012"):
    # ghép liền, không để bước làm phẳng chèn dấu cách ("NĐ- CP").
    text = HYPHEN_LINE_BREAK_RE.sub("-", text)

    # Mốc mở đầu hỗ trợ CHƯƠNG I / Chương I / Chương 1 và dấu hai chấm.
    # Chỉ cắt từ mốc nếu phần tiêu đề theo sau đủ giống heading viết hoa.
    chapter_start_re = re.compile(
        rf"(?<!\S)Chương\s+(?:I|1)\s*[.:]?(?=\s)",
        re.IGNORECASE
    )
    m0 = None
    for candidate in chapter_start_re.finditer(text):
        boundary = HEADING_BOUNDARY_RE.search(text, candidate.end())
        title_candidate = _heading_title_candidate(text, candidate, boundary)
        if title_candidate and uppercase_ratio(title_candidate) >= 0.80:
            m0 = candidate
            break
    if m0:
        text = text[m0.start():]
    else:
        warn("Không tìm thấy heading mở đầu Chương I/1 đủ tin cậy; giữ nguyên phần đầu văn bản.")

    # Cắt phần ký ban hành/nơi nhận/phụ lục trước khi tách Điều/Khoản.
    # Không dựa vào tiêu đề phụ lục vì nhiều biểu mẫu không có nhãn "Phụ lục".
    text = strip_terminal_material(text)
    # Page counters and Công báo markings are handled by cleaner.py.
    # Do not run the old parser-side cleaner here, as it could delete legal text.
    footnotes: List[str] = []
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
            heading_suffix = raw[mh[0]:]
            if len(heading_suffix) > 300:
                # Không cắt bỏ một đoạn dài không rõ ràng khỏi Điều hiện tại.
                # Giữ nguyên dữ liệu và phát cảnh báo để kiểm tra thủ công.
                warn(
                    f"Điều {num}: phần từ heading {mh[1]!r} đến cuối Điều dài "
                    f"{len(heading_suffix)} ký tự; giữ nguyên nội dung, không tự động cắt."
                )
            else:
                # Tiêu đề Chương/Mục ở cuối đoạn hiện tại mở đầu phần kế tiếp.
                # Cập nhật state cho các Điều tiếp theo nhưng giữ chapter/section
                # đã chụp ở đầu vòng lặp cho Điều đang xử lý.
                update_headings(heading_suffix, state)
                raw = raw[:mh[0]].strip()

        if marker_has_no_title_on_line(text[_s:e]):
            title, intro, body, has_clauses = split_head_without_title(raw)
        else:
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


# Số hiệu theo cách ghi hiện đại, ví dụ:
#   02a/2015/TT-BTP
#   01/2016/TTLT-TANDTC-VKSNDTC-BTP
DOCUMENT_NUMBER_MODERN_CODE = (
    r"[0-9]{1,5}[A-Za-z]?/[0-9]{4}/"
    r"[A-ZĐ][A-ZĐ0-9]*(?:-[A-Za-z0-9Đđ]+)*"
)

# Một số văn bản cũ dùng định dạng như "21-LCT/HĐNN7":
# số thứ tự - ký hiệu loại văn bản / ký hiệu cơ quan ban hành.
# Giới hạn từng thành phần để tránh bắt nhầm các cụm tùy ý trong nội dung.
DOCUMENT_NUMBER_LEGACY_CODE = (
    r"[0-9]{1,5}-[A-Za-zĐđ]{1,12}/[A-Za-zĐđ0-9]{1,12}"
)

# Kết hợp hai định dạng; giữ nguyên hỗ trợ số hiệu hiện đại hiện có.
DOCUMENT_NUMBER_CODE = (
    rf"(?:{DOCUMENT_NUMBER_MODERN_CODE}|{DOCUMENT_NUMBER_LEGACY_CODE})"
)

# Ưu tiên số hiệu có nhãn "Số:" để tránh bắt nhầm số hiệu được nhắc trong nội dung.
DOCUMENT_NUMBER_RE = re.compile(
    rf"(?<!\\w)Số\\s*:\\s*({DOCUMENT_NUMBER_CODE})",
    re.IGNORECASE
)
def normalize_document_id(file_path: str) -> str:
    stem = Path(file_path).stem.strip()
    if not stem:
        raise ValueError("Không thể tạo document_id từ tên file rỗng.")
    doc_id = re.sub(r"[^A-Za-z0-9_]+", "_", stem)
    doc_id = re.sub(r"_+", "_", doc_id).strip("_")
    if not doc_id:
        raise ValueError(f"Tên file {Path(file_path).name!r} không tạo được document_id hợp lệ.")
    return doc_id

def slugify_ascii(text: str) -> str:
    """'126/2014/NĐ-CP' -> '126_2014_nd_cp' (bỏ dấu, chữ thường, ký tự lạ -> '_')."""
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return text.strip("_")


# Prefix dùng để tạo document_id ổn định theo loại văn bản.
# Đây là quy tắc đặt ID, không phải logic suy luận metadata.
DOCUMENT_TYPE_PREFIX = {
    "Luật": "l",
    "Bộ luật": "bl",
    "Nghị định": "nd",
    "Thông tư": "tt",
    "Thông tư liên tịch": "ttlt",
    "Nghị quyết": "nq",
    "Nghị quyết liên tịch": "nqlt",
    "Quyết định": "qd",
    "Chỉ thị": "ct",
    "Pháp lệnh": "pl",
    "Lệnh": "lenh",
    "Thông báo": "tb",
    "Quy chế": "qc",
    "Quy định": "qdinh",
    "Công văn": "cv",
}


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


def resolve_document_id(metadata: dict) -> str:
    """
    document_id chuẩn lấy từ document_versions.json (bảng ánh xạ của data contract).
    Chỉ tạo bằng build_document_id() khi bản ghi registry chưa có document_id.
    """
    record = lookup_document_version(metadata.get("document_number") or "")
    registry_id = str((record or {}).get("document_id") or "").strip()
    if registry_id:
        return registry_id
    return build_document_id(metadata["document_type"], metadata["document_number"])


def extract_document_number(text: str) -> str:
    """
    Nhận diện số hiệu ở phần đầu văn bản.
    Cho phép số hiệu bị xuống dòng sau dấu gạch nối, ví dụ:
    01/2016/TTLT-TANDTC-
    VKSNDTC-BTP.
    """
    # Chỉ chuẩn hóa khoảng trắng trong bản dùng để nhận diện số hiệu;
    # không sửa nội dung TXT gốc mà parser dùng để tách Điều/Khoản.
    number_text = unicodedata.normalize("NFC", text or "")
    number_text = re.sub(r"(?<=[A-Za-zĐđ0-9])\s*[-–]\s*(?=[A-Za-zĐđ0-9])", "-", number_text)
    number_text = re.sub(r"(?<=[A-Za-zĐđ0-9])\s+(?=[A-Za-zĐđ0-9])", " ", number_text)
    number_text = re.sub(r"\s+", " ", number_text).strip()

    head = number_text[:5000]
    m = DOCUMENT_NUMBER_RE.search(head)
    if m:
        return re.sub(r"\s+", "", m.group(1))

    # Không nhận diện tên văn bản từ TXT nữa. Nếu không có nhãn "Số:",
    # tìm trực tiếp số hiệu trong phần đầu văn bản.
    fallback = re.search(rf"(?<!\w)({DOCUMENT_NUMBER_CODE})(?!\w)", number_text[:5000])
    if fallback:
        return re.sub(r"\s+", "", fallback.group(1))

    warn("Không tự nhận diện được document_number.")
    return ""

# =============================================================================
# METADATA REGISTRY: document_versions.json là nguồn metadata chuẩn
# =============================================================================

_DOCUMENT_VERSIONS_CACHE: Optional[Dict[str, dict]] = None
_DOCUMENT_VERSIONS_PATH: Optional[Path] = None


def normalize_document_number(document_number: str) -> str:
    """Chuẩn hóa số hiệu để đối chiếu, không thay đổi giá trị xuất ra."""
    value = unicodedata.normalize("NFC", (document_number or "").strip())
    value = re.sub(r"\s+", "", value)
    return value.upper().replace("Đ", "D")


def find_document_versions_file() -> Path:
    """Tìm registry metadata theo cấu hình, sau đó theo cấu trúc repository.

    Thứ tự:
    1. DOCUMENT_VERSIONS_PATH nếu được cấu hình.
    2. <repo>/data/reference/document_versions.json.
    3. Các vị trí dự phòng: cạnh parser.py và trong các thư mục cha.
    """
    candidates = []
    env_path = os.getenv("DOCUMENT_VERSIONS_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())

    parser_dir = Path(__file__).resolve().parent
    # parser.py thường nằm tại <repo>/parser/parser.py.
    # Xác định đường dẫn từ vị trí mã nguồn, không phụ thuộc thư mục chạy lệnh.
    repo_root = parser_dir.parent
    candidates.append(repo_root / "data" / "reference" / "document_versions.json")

    # Dự phòng để tương thích với bố cục dự án cũ.
    candidates.append(parser_dir / "document_versions.json")
    candidates.extend(
        parent / "document_versions.json"
        for parent in list(parser_dir.parents)[:4]
    )

    # Loại đường dẫn trùng, giữ nguyên thứ tự ưu tiên.
    unique_candidates = []
    seen = set()
    for candidate in candidates:
        key = str(candidate.expanduser().resolve(strict=False)).casefold()
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)

    for candidate in unique_candidates:
        if candidate.is_file():
            return candidate.resolve()

    searched = "\n".join(f" - {p}" for p in unique_candidates)
    raise FileNotFoundError(
        "Không tìm thấy document_versions.json. Đặt registry tại "
        "<repo>/data/reference/document_versions.json hoặc cấu hình "
        "DOCUMENT_VERSIONS_PATH.\nĐã tìm:\n" + searched
    )


def load_document_versions(force_reload: bool = False) -> Dict[str, dict]:
    """Đọc registry một lần và lập chỉ mục theo document_number."""
    global _DOCUMENT_VERSIONS_CACHE, _DOCUMENT_VERSIONS_PATH

    path = find_document_versions_file()
    if (
        not force_reload
        and _DOCUMENT_VERSIONS_CACHE is not None
        and _DOCUMENT_VERSIONS_PATH == path
    ):
        return _DOCUMENT_VERSIONS_CACHE

    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as ex:
        raise ValueError(f"document_versions.json không phải JSON hợp lệ: {path}: {ex}") from ex

    if not isinstance(data, list):
        raise ValueError(
            f"document_versions.json phải là một danh sách JSON các bản ghi: {path}"
        )

    indexed: Dict[str, dict] = {}
    for index, record in enumerate(data):
        if not isinstance(record, dict):
            warn(f"Bỏ qua bản ghi metadata thứ {index + 1}: không phải object JSON.")
            continue

        number = str(record.get("document_number") or "").strip()
        if not number:
            warn(f"Bỏ qua bản ghi metadata thứ {index + 1}: thiếu document_number.")
            continue

        key = normalize_document_number(number)
        if key in indexed:
            raise ValueError(
                f"document_versions.json có document_number trùng sau chuẩn hóa: {number!r}"
            )
        indexed[key] = record

    _DOCUMENT_VERSIONS_CACHE = indexed
    _DOCUMENT_VERSIONS_PATH = path
    print(f"[metadata] Đã nạp {len(indexed)} văn bản từ {path}")
    return indexed


def lookup_document_version(document_number: str) -> Optional[dict]:
    """Tra cứu bản ghi metadata theo số hiệu do extract_document_number nhận diện."""
    if not document_number:
        return None
    return load_document_versions().get(normalize_document_number(document_number))


def metadata_from_document_version(record: dict, extracted_number: str) -> dict:
    """Chỉ lấy metadata chuẩn từ registry; không tự suy luận để lấp trường thiếu."""
    # Hỗ trợ cả file gốc (type/status) lẫn file đã chuẩn hóa (document_type/validity_status).
    document_type = record.get("document_type") or record.get("type") or "Không xác định"
    validity_status = record.get("validity_status") or record.get("status") or "Không xác định"

    issue_date = record.get("issue_date")
    effective_date = record.get("effective_date")
    issuing_body = record.get("issuing_body")
    # Metadata title phải lấy trực tiếp từ document_versions.json; không suy luận
    # từ tiêu đề trích xuất trong TXT và không âm thầm dùng giá trị thay thế.
    title = record.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(
            f"Metadata của {extracted_number}: thiếu trường 'title' hợp lệ "
            "trong document_versions.json. Hãy bổ sung title vào registry rồi chạy lại."
        )
    title = title.strip()

    if not issue_date:
        warn(f"Metadata của {extracted_number}: issue_date đang trống trong document_versions.json.")
    if not effective_date:
        warn(f"Metadata của {extracted_number}: effective_date đang trống trong document_versions.json.")
    if not issuing_body:
        warn(f"Metadata của {extracted_number}: issuing_body đang trống trong document_versions.json.")
    if not title:
        warn(f"Metadata của {extracted_number}: title đang trống trong document_versions.json.")

    return {
        "title": title,
        "document_type": document_type,
        "document_number": str(record.get("document_number") or extracted_number),
        "issue_date": issue_date or "",
        "effective_date": effective_date or None,
        "issuing_body": issuing_body or "Không xác định",
        "validity_status": validity_status,
        # Các trường này lấy từ đúng bản ghi registry khớp document_number.
        # Không suy diễn ngày hết hiệu lực hoặc URL nếu registry không có dữ liệu.
        "expiry_date": record.get("expiry_date") or None,
        "source_url": str(record.get("source_url") or "").strip(),
    }


def extract_metadata(raw_text: str, file_path: Optional[str] = None) -> dict:
    """
    Lấy document_number bằng logic nhận diện hiện có, sau đó tra metadata chuẩn
    trong document_versions.json. Không suy luận metadata từ ngữ cảnh khi không khớp.
    """
    document_number = extract_document_number(raw_text)
    if not document_number:
        warn("Không thể tra metadata: parser không nhận diện được document_number.")
        raise ValueError(
            "Không thể lấy metadata vì không nhận diện được số hiệu văn bản. "
            "Kiểm tra phần đầu file TXT hoặc logic extract_document_number()."
        )

    record = lookup_document_version(document_number)
    if record is None:
        warn(
            f"Không tìm thấy document_number {document_number!r} trong document_versions.json. "
            "Không dùng metadata suy luận từ ngữ cảnh."
        )
        raise ValueError(
            f"Không tìm thấy số hiệu {document_number!r} trong document_versions.json. "
            "Hãy bổ sung/đối chiếu bản ghi trong file metadata rồi chạy lại."
        )

    return metadata_from_document_version(record, document_number)


def parse_raw_text_to_legal_doc(raw_text: str, doc_id: str, metadata: dict) -> dict:
    meta = DocumentMetadataSchema(**metadata)
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
    record = lookup_document_version(number)
    if record is None:
        raise ValueError(
            f"Không tìm thấy số hiệu {number!r} trong document_versions.json; "
            "không thể tạo document_id theo metadata chuẩn."
        )
    metadata = metadata_from_document_version(record, number)
    doc_id = resolve_document_id(metadata)
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