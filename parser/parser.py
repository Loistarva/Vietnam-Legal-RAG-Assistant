# -*- coding: utf-8 -*-
"""
Parser văn bản luật (file TXT một dòng) -> JSON theo Điều / Khoản.

Cách làm:
  1. Làm sạch: bỏ phần đầu văn bản, bỏ dấu chú thích dính chữ, bỏ chú thích cuối trang
     và số trang (đếm tuần tự: trang 2, 3, 4, ...).
  2. Tìm Điều theo số thứ tự mong đợi (1, 2, 3, ...), chỉ nhận dạng "Điều N. Chữ-hoa".
     Tham chiếu như "Điều 8 của Luật này" không có dấu chấm nên không bị nhầm.
  3. Tách Chương/Mục (viết HOA) ra metadata, không để dính vào nội dung Điều.
  4. Trong mỗi Điều: tách tiêu đề, phần dẫn nhập (intro) và các Khoản (1., 2., 3. ... tuần tự).
  5. Khoản quá dài (> MAX_CLAUSE_CHARS) và có điểm a), b)... thì tách thêm theo điểm,
     mỗi chunk điểm được gắn câu dẫn của khoản.

Dùng trong test_parser.py:  parse_raw_text_to_legal_doc(raw_text, doc_id, metadata)
Chạy độc lập:  python parser.py -i input.txt -o output.json
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

# ==========================================
# CẤU HÌNH
# ==========================================
INPUT_FILE = r"E:\nhom AI\Vietnam-Legal-RAG-Assistant\parser\cleaned_texts\L01.txt"
OUTPUT_FILE = r"E:\nhom AI\Vietnam-Legal-RAG-Assistant\parser\cleaned_texts\L01_schema_parsed.json"

DOCUMENT_ID = "L01"
DOCUMENT_TITLE = "Luật Hôn nhân và Gia đình"
DOCUMENT_NUMBER = "52/2014/QH13"

FIRST_PAGE_NUMBER = 2          # số trang đầu tiên xuất hiện trong luồng văn bản
SPLIT_LONG_CLAUSES = True      # tách khoản dài theo điểm a), b), ...
MAX_CLAUSE_CHARS = 1500

# Tiêu đề các Điều không thể tự tách (không có khoản, hoặc có câu dẫn nhập).
# Lấy từ chính văn bản luật; bổ sung thêm nếu log báo "không rõ tiêu đề".
TITLES: Dict[str, str] = {
    "1": "Phạm vi điều chỉnh",
    "3": "Giải thích từ ngữ",
    "6": "Áp dụng quy định của Bộ luật dân sự và các luật khác có liên quan",
    "13": "Xử lý việc đăng ký kết hôn không đúng thẩm quyền",
    "15": "Quyền, nghĩa vụ của cha mẹ và con trong trường hợp nam, nữ chung sống với nhau như vợ chồng mà không đăng ký kết hôn",
    "17": "Bình đẳng về quyền, nghĩa vụ giữa vợ, chồng",
    "18": "Bảo vệ quyền, nghĩa vụ về nhân thân của vợ, chồng",
    "20": "Lựa chọn nơi cư trú của vợ chồng",
    "21": "Tôn trọng danh dự, nhân phẩm, uy tín của vợ, chồng",
    "22": "Tôn trọng quyền tự do tín ngưỡng, tôn giáo của vợ, chồng",
    "23": "Quyền, nghĩa vụ về học tập, làm việc, tham gia hoạt động chính trị, kinh tế, văn hóa, xã hội",
    "31": "Giao dịch liên quan đến nhà là nơi ở duy nhất của vợ chồng",
    "36": "Tài sản chung được đưa vào kinh doanh",
    "37": "Nghĩa vụ chung về tài sản của vợ chồng",
    "42": "Chia tài sản chung trong thời kỳ hôn nhân bị vô hiệu",
    "45": "Nghĩa vụ riêng về tài sản của vợ, chồng",
    "47": "Thỏa thuận xác lập chế độ tài sản của vợ chồng",
    "52": "Khuyến khích hòa giải ở cơ sở",
    "54": "Hòa giải tại Tòa án",
    "55": "Thuận tình ly hôn",
    "58": "Quyền, nghĩa vụ của cha mẹ và con sau khi ly hôn",
    "63": "Quyền lưu cư của vợ hoặc chồng khi ly hôn",
    "64": "Chia tài sản chung của vợ chồng đưa vào kinh doanh",
    "65": "Thời điểm chấm dứt hôn nhân",
    "74": "Bồi thường thiệt hại do con gây ra",
    "80": "Quyền, nghĩa vụ của con dâu, con rể, cha mẹ vợ, cha mẹ chồng",
    "92": "Xác định cha, mẹ, con trong trường hợp người có yêu cầu chết",
    "94": "Xác định cha, mẹ trong trường hợp mang thai hộ vì mục đích nhân đạo",
    "100": "Xử lý hành vi vi phạm về sinh con bằng kỹ thuật hỗ trợ sinh sản và mang thai hộ",
    "105": "Quyền, nghĩa vụ của anh, chị, em",
    "106": "Quyền, nghĩa vụ của cô, dì, chú, cậu, bác ruột và cháu ruột",
    "108": "Một người cấp dưỡng cho nhiều người",
    "109": "Nhiều người cùng cấp dưỡng cho một người hoặc cho nhiều người",
    "110": "Nghĩa vụ cấp dưỡng của cha, mẹ đối với con",
    "111": "Nghĩa vụ cấp dưỡng của con đối với cha, mẹ",
    "112": "Nghĩa vụ cấp dưỡng giữa anh, chị, em",
    "115": "Nghĩa vụ cấp dưỡng giữa vợ và chồng khi ly hôn",
    "117": "Phương thức cấp dưỡng",
    "118": "Chấm dứt nghĩa vụ cấp dưỡng",
    "120": "Khuyến khích việc trợ giúp của tổ chức, cá nhân",
    "124": "Hợp pháp hóa lãnh sự giấy tờ, tài liệu về hôn nhân và gia đình",
    "130": "Áp dụng chế độ tài sản của vợ chồng theo thỏa thuận; giải quyết hậu quả của việc nam, nữ chung sống với nhau như vợ chồng mà không đăng ký kết hôn có yếu tố nước ngoài",
}

# Chữ in hoa tiếng Việt (KHÔNG dùng khoảng À-Ỵ vì khoảng đó lẫn cả chữ thường)
UP = "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
POINT_LETTERS = "abcdđeghiklmnopqrstuvxy"  # bảng chữ cái dùng cho điểm (không có f, j, w, z)

WARNINGS: List[str] = []


def warn(msg: str):
    WARNINGS.append(msg)


# ==========================================
# 1. PYDANTIC SCHEMAS
# ==========================================
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


class LegalMetadata(BaseModel):
    title: str
    document_type: Literal["Luật", "Nghị định", "Thông tư", "Quyết định", "Chỉ thị"]
    document_number: str
    issue_date: str
    effective_date: Optional[str] = None
    issuing_body: str
    validity_status: str


class DocumentSchema(BaseModel):
    document_id: str = Field(..., pattern=r"^[A-Za-z0-9_]+$")
    metadata: LegalMetadata
    articles: List[ArticleSchema]
    footnotes: List[str] = Field(default_factory=list)


# ==========================================
# 2. LÀM SẠCH: CHÚ THÍCH + SỐ TRANG
# ==========================================
# Số lẻ dính liền chữ cái, ví dụ "khu vực2", "THI HÀNH3" -> dấu chú thích
GLUED_MARKER = re.compile(r"(?<=[^\W\d_])\d(?=[\s.,;:”]|$)")
# Số đứng riêng (ứng viên số trang)
NUM_TOKEN = re.compile(r"(?<=\s)(\d{1,3})(?=\s|$)")

# Số đứng sau/trước các từ này là số thật trong câu, không phải số trang
PREV_BAD = {"Điều", "điều", "khoản", "điểm", "các", "và", "từ", "đến", "ngày", "tháng", "năm", "số", "hoặc"}
NEXT_BAD = {"tháng", "năm", "ngày", "tuổi"}


def find_page_token(text: str, pos: int, page: int):
    for m in NUM_TOKEN.finditer(text, pos):
        tok = m.group(1)
        if tok.startswith("0") or int(tok) != page:
            continue
        prev = text[: m.start()].rstrip().rsplit(" ", 1)[-1]
        nxt = text[m.end():].lstrip().split(" ", 1)[0]
        if prev in PREV_BAD or prev.endswith(","):
            continue
        if nxt in NEXT_BAD:
            continue
        return m
    return None


def footnote_regex(n: int):
    # Thân chú thích: đứng sau dấu kết câu, dạng " 1 Luật số ...", " 3 Điều 3 của ..."
    return re.compile(rf"(?<=[.”\"]\s){n}\s+(?=[{UP}])")


def clean_text(text: str) -> Tuple[str, List[str]]:
    """Bỏ chú thích cuối trang và số trang. Trả về (text sạch, danh sách chú thích)."""
    text = GLUED_MARKER.sub("", text)
    footnotes: List[str] = []
    page, fn, pos, misses, pages_removed = FIRST_PAGE_NUMBER, 1, 0, 0, 0

    while misses < 5:
        m_pg = find_page_token(text, pos, page)
        m_fn = footnote_regex(fn).search(text, pos)

        if m_fn and (m_pg is None or m_fn.start() < m_pg.start()):
            # Chú thích thường kết thúc ở số trang. Tuy nhiên nếu số trang
            # bị lệch/mất (ví dụ parser đang chờ trang 26 nhưng văn bản đã
            # chuyển sang một số trang khác), TUYỆT ĐỐI không được xóa tới EOF.
            if m_pg is None:
                # Tìm một số trang "giống số trang" ngay sau chú thích.
                # Ưu tiên số đứng ngay trước "Điều" hoặc "Chương", vì đây là
                # dạng xuất hiện ở ranh giới trang trong file TXT này.
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
                    # Không tăng page ở đây vì số trang thực tế đã lệch.
                    warn(
                        f"Không tìm thấy số trang {page}; đã bỏ chú thích {fn - 1} "
                        f"bằng mốc trang kế tiếp {next_page.group(1)}."
                    )
                    continue

                # Không tìm được điểm kết thúc an toàn: giữ nguyên phần còn lại.
                # Quan trọng: không bao giờ cắt từ chú thích tới EOF.
                warn(
                    f"Không tìm thấy số trang {page}; giữ nguyên phần còn lại "
                    f"để tránh mất dữ liệu."
                )
                break

            end = m_pg.end()
            footnotes.append(text[m_fn.start():end].strip())
            text = text[: m_fn.start()] + " " + text[end:]
            pos = m_fn.start()
            fn += 1
            page += 1
            pages_removed += 1
            misses = 0
        elif m_pg:
            text = text[: m_pg.start()] + " " + text[m_pg.end():]
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


# ==========================================
# 3. CHƯƠNG / MỤC
# ==========================================
HEAD_RE = re.compile(
    rf"(?<!\S)(Chương\s+[IVXLC]+|Mục\s+\d+)\s+((?:[{UP}][{UP},]*(?:\s+|$))+)"
)


def update_headings(fragment: str, state: Dict[str, Optional[str]]):
    for m in HEAD_RE.finditer(fragment):
        label = re.sub(r"\s+", " ", m.group(1)).strip()
        title = m.group(2).strip()
        if label.startswith("Chương"):
            state["chapter"] = f"{label} {title}"
            state["section"] = None
        else:
            state["section"] = f"{label} {title}"


# ==========================================
# 4. TÁCH ĐIỀU / KHOẢN / ĐIỂM
# ==========================================
def find_articles(text: str) -> List[Tuple[int, int, int]]:
    markers = []
    pos, n = 0, 1
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
    starts = [(1, first.start())]
    pos, k = first.end(), 2
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


def split_points(clause_text: str) -> Optional[List[Tuple[str, str]]]:
    """Tách khoản thành các điểm a), b), ... (tuần tự). Mỗi phần gắn câu dẫn của khoản."""
    starts = []
    pos = 0
    for ch in POINT_LETTERS:
        m = re.compile(rf"(?<!\S){re.escape(ch)}\)\s+").search(clause_text, pos)
        if not m:
            break
        starts.append((ch, m.start()))
        pos = m.end()
    if len(starts) < 2:
        return None
    lead = clause_text[: starts[0][1]].strip()
    out = []
    for i, (ch, s) in enumerate(starts):
        e = starts[i + 1][1] if i + 1 < len(starts) else len(clause_text)
        out.append((ch, f"{lead} {clause_text[s:e].strip()}".strip()))
    return out


def split_head(num: str, raw: str):
    """Trả về (title, intro, body_text, has_clauses)."""
    first = clause_regex(1).search(raw)
    head = raw[: first.start()].strip() if first else raw.strip()
    body = raw[first.start():] if first else ""

    known = TITLES.get(num)
    if known and head.startswith(known):
        title, rest = known, head[len(known):].strip()
    elif first and not head.endswith(":"):
        title, rest = head, ""          # Điều có khoản, không có câu dẫn: phần đầu là tiêu đề
    else:
        title, rest = None, head
        warn(f"Điều {num}: không rõ tiêu đề, hãy bổ sung vào TITLES. Đầu Điều: {head[:70]!r}")

    if first:
        return title, (rest or None), body, True
    return title, None, (rest or head), False


def build_chunks(art_id: str, body: str, has_clauses: bool) -> List[ChunkSchema]:
    pieces: List[Tuple[Optional[str], Optional[str], str]] = []

    if not has_clauses:
        pieces.append((None, None, body))
    else:
        for k, ctext in split_clauses(body):
            sub = split_points(ctext) if (SPLIT_LONG_CLAUSES and len(ctext) > MAX_CLAUSE_CHARS) else None
            if sub:
                for letter, ptext in sub:
                    pieces.append((k, letter, ptext))
            else:
                pieces.append((k, None, ctext))

    chunks = []
    for i, (k, letter, t) in enumerate(pieces, start=1):
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
    """Phân tích văn bản thô -> (danh sách Điều dạng dict, danh sách chú thích)."""
    WARNINGS.clear()  # mỗi lần gọi là một văn bản mới

    text = re.sub(r"\s+", " ", raw_text).strip()

    # Cắt phần đầu (quốc hiệu, tên luật, căn cứ...) trước "Chương I"
    m0 = re.search(rf"(?<!\S)Chương\s+I\s+[{UP}]", text)
    if m0:
        text = text[m0.start():]
    else:
        warn("Không tìm thấy 'Chương I', giữ nguyên phần đầu văn bản.")

    text, footnotes = clean_text(text)

    markers = find_articles(text)
    if not markers:
        raise RuntimeError("Không tìm thấy Điều nào.")

    # Kiểm tra không bị mất Điều trong quá trình làm sạch.
    found_numbers = [n for n, _s, _e in markers]
    if found_numbers != list(range(1, found_numbers[-1] + 1)):
        missing = sorted(set(range(1, found_numbers[-1] + 1)) - set(found_numbers))
        raise RuntimeError(
            f"Chuỗi Điều bị đứt sau khi làm sạch. "
            f"Điều bị thiếu: {missing}. Không tiếp tục xuất JSON."
        )

    state: Dict[str, Optional[str]] = {"chapter": None, "section": None}
    update_headings(text[: markers[0][1]], state)

    articles = []
    for i, (n, _s, e) in enumerate(markers):
        end = markers[i + 1][1] if i + 1 < len(markers) else len(text)
        raw = text[e:end].strip()
        num = str(n)

        chapter, section = state["chapter"], state["section"]
        mh = HEAD_RE.search(raw)
        if mh:
            update_headings(raw[mh.start():], state)
            raw = raw[: mh.start()].strip()

        title, intro, body, has_clauses = split_head(num, raw)
        art_id = f"dieu_{num}"
        try:
            chunks = build_chunks(art_id, body, has_clauses)
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
        except Exception as ex:  # không bao giờ bỏ Điều trong im lặng
            warn(f"Điều {num} lỗi khi dựng chunk: {ex}")

    return articles, footnotes


def parse_raw_text_to_legal_doc(raw_text: str, doc_id: str, metadata: dict) -> dict:
    """
    Hàm chính cho test_parser.py.
    Nhận text thô + doc_id + metadata, trả về dict JSON-serializable:
    {"document_id", "metadata", "articles", "footnotes"}.
    """
    meta = LegalMetadata(**metadata)  # validate metadata trước khi tốn công parse
    articles, footnotes = parse_text_to_articles(raw_text)
    doc = DocumentSchema(
        document_id=doc_id,
        metadata=meta,
        articles=articles,
        footnotes=footnotes,
    )
    return doc.model_dump()


def parse_legal_document_to_schema(file_path: str):
    """Tiện ích đọc từ file .txt -> (articles, footnotes). Giữ lại cho tương thích cũ."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Đường dẫn file không hợp lệ: {path.resolve()}")
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        content = f.read()
    return parse_text_to_articles(content)


# ==========================================
# 5. KIỂM TRA CHẤT LƯỢNG
# ==========================================
def quality_report(articles, footnotes):
    last_article = articles[-1]["article_number"] if articles else "N/A"
    print(f"\n[report] Số Điều: {len(articles)} (Điều cuối: {last_article})")
    print(f"[report] Số chunk: {sum(len(a['chunks']) for a in articles)}")

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
        for c in a["chunks"]:
            t = c["text"]
            if sus_footnote.search(t) or sus_heading.search(t):
                bad.append((c["chunk_id"], "lẫn chú thích/tiêu đề Chương-Mục"))
            elif not re.search(r"[.;:”)]$", t):
                bad.append((c["chunk_id"], "không kết thúc bằng dấu câu (nghi dư số trang)"))
    print(f"[report] Chunk đáng nghi: {len(bad)}")
    for cid, why in bad[:15]:
        print(f"   - {cid}: {why}")

    empty_title = [a["article_number"] for a in articles if not a["article_title"]]
    if empty_title:
        print(f"[report] Điều chưa có tiêu đề: {empty_title}")

    for w in WARNINGS[:30]:
        print("[warn]", w)
    if len(WARNINGS) > 30:
        print(f"[warn] ... và {len(WARNINGS) - 30} cảnh báo khác")


# ==========================================
# 6. CHẠY ĐỘC LẬP (CLI)
# ==========================================
def main():
    ap = argparse.ArgumentParser(description="Legal Document Parser to RAG-ready JSON")
    ap.add_argument("--input", "-i", default=INPUT_FILE, help="Đường dẫn file TXT đầu vào")
    ap.add_argument("--output", "-o", default=OUTPUT_FILE, help="Đường dẫn xuất file JSON")
    ap.add_argument("--doc-id", default=DOCUMENT_ID, help="Mã định danh văn bản")
    ap.add_argument("--doc-title", default=DOCUMENT_TITLE, help="Tên văn bản luật")
    ap.add_argument("--doc-num", default=DOCUMENT_NUMBER, help="Số hiệu văn bản")
    args = ap.parse_args()

    metadata = {
        "title": args.doc_title,
        "document_type": "Luật",
        "document_number": args.doc_num,
        "issue_date": "2024-01-01",
        "effective_date": "2024-01-01",
        "issuing_body": "Quốc hội",
        "validity_status": "Còn hiệu lực",
    }

    try:
        with open(args.input, "r", encoding="utf-8-sig", errors="ignore") as f:
            raw_text = f.read()
        doc = parse_raw_text_to_legal_doc(raw_text, args.doc_id, metadata)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        quality_report(doc["articles"], doc["footnotes"])
        print(f"✅ Xử lý thành công! Đã trích xuất {len(doc['articles'])} Điều -> {args.output}")
    except Exception as e:
        print(f"❌ Xử lý thất bại: {e}")


if __name__ == "__main__":
    main()
