"""
chunking_rules.py — Hierarchical Parent-Child Chunking Engine for Vietnamese Legal Documents.

Kiến trúc chuẩn theo system_architecture.drawio & docs/data_contract.md:
  • Đầu vào chuẩn: Structured Legal JSON do module `parser/` tạo ra (Document -> Articles -> Chunks).
  • Đầu ra:
      - Parent Chunks (<= 1500 ký tự): Lưu tại Parent Store (Key-Value/Document Store) phục vụ
        Parent-Context Resolver và Context Aggregator cho LLM.
      - Child Chunks (<= 256 tokens): Word-segmented bằng underthesea, lưu tại Vector DB (Qdrant)
        và Elasticsearch (BM25) phục vụ Dense Vector & Sparse Hybrid Retrieval.

Public APIs:
  chunk_legal_document(doc_dict, config=None) -> ChunkResult
  chunk_legal_documents(docs, config=None)    -> list[ChunkResult]
  chunk_parsed_file(file_path, config=None)   -> ChunkResult
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any


# ═════════════════════════════════════════════════════════════════════
#  CONFIGURATION DEFAULTS
# ═════════════════════════════════════════════════════════════════════

# --- Parent Chunk Limits (Dành cho Context LLM & Grounding) ---
PARENT_MAX_CHARS: int = 1500     # Ký tự tối đa cho 1 parent chunk
PARENT_MAX_WORDS: int = 260      # Số từ tối đa khi fallback

# --- Child Chunk Limits (Dành cho BGE-M3 Dense & BM25 Sparse Index) ---
CHILD_MAX_TOKENS: int = 256      # Giới hạn token embedding chuẩn BGE-M3
CHILD_MAX_UNITS: int = 200       # Giới hạn đơn vị phân đoạn từ tiếng Việt
CHILD_MIN_WORDS: int = 20        # Mảnh tách từ cùng một Khoản dưới ngưỡng này được gộp với mảnh liền kề;
                                 # Khoản ngắn trọn vẹn vẫn là chunk riêng (không gộp qua ranh giới Khoản)
CHILD_MIN_CHARS: int = 10        # data_contract.md mục 5.2: chunk_text tối thiểu 10 ký tự
CHILD_CONTEXT_MAX_WORDS: int = 60  # Intro của Điều + câu dẫn danh sách điểm đưa vào embed_text

# --- Sliding Window Fallback ---
FALLBACK_OVERLAP_WORDS: int = 40

# --- Table Limits ---
TABLE_MAX_ROWS: int = 15
TABLE_MAX_CHARS: int = 2500


# ═════════════════════════════════════════════════════════════════════
#  DATA CLASSES & SCHEMAS
# ═════════════════════════════════════════════════════════════════════

class ChunkType(Enum):
    ARTICLE = auto()
    TABLE = auto()
    PREAMBLE = auto()
    FOOTER = auto()
    APPENDIX = auto()
    FALLBACK_WINDOW = auto()


@dataclass
class ParentChunk:
    """Parent chunk lớn — Lưu trữ tại Key-Value / Document Store cho Parent-Context Resolver."""
    parent_id: str
    doc_id: str
    title: str
    text: str
    breadcrumb: str
    article_ref: str | None = None
    clause_refs: str = ""
    chunk_type: ChunkType = ChunkType.ARTICLE
    child_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_store_dict(self) -> dict[str, Any]:
        """Format bản ghi lưu trữ vào Parent Store (Redis/PostgreSQL/DocStore)."""
        return {
            "parent_id": self.parent_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "breadcrumb": self.breadcrumb,
            "article_ref": self.article_ref,
            "clause_refs": self.clause_refs,
            "chunk_type": self.chunk_type.name,
            "child_ids": self.child_ids,
            "metadata": self.metadata,
        }


@dataclass
class ChildChunk:
    """Child chunk nhỏ — Đưa vào Qdrant (BGE-M3) và Elasticsearch (BM25)."""
    chunk_id: str
    parent_id: str
    doc_id: str
    title: str
    text: str                    # Original text chuẩn tiếng Việt
    article_id: str = ""
    clause_id: str = ""
    parent_clause_id: str = ""
    seg_text: str = ""           # Word-segmented text (underthesea)
    embed_text: str = ""         # Title_seg + Breadcrumb_seg + Body_seg cho embedding
    embed_text_raw: str = ""
    breadcrumb: str = ""
    article_ref: str | None = None
    clause_ref: str | None = None
    point_ref: str | None = None
    chunk_type: ChunkType = ChunkType.ARTICLE
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_qdrant_payload(self) -> dict[str, Any]:
        """Format payload cho Vector DB (Qdrant)."""
        payload = {
            "id": self.chunk_id,
            "chunk_id": self.chunk_id,
            "parent_id": self.parent_id,
            "doc_id": self.doc_id,
            "document_id": self.doc_id,
            "article_id": self.article_id,
            "clause_id": self.clause_id,
            "parent_clause_id": self.parent_clause_id,
            "title": self.title,
            "text": self.text,
            "chunk_text": self.text,
            "seg_text": self.seg_text,
            "embed_text": self.embed_text,
            "embed_text_raw": self.embed_text_raw or self.text,
            "breadcrumb": self.breadcrumb,
            "article_ref": self.article_ref,
            "clause_ref": self.clause_ref,
            "point_ref": self.point_ref,
            "chunk_type": self.chunk_type.name,
            "document_type": self.metadata.get("document_type"),
            "document_number": self.metadata.get("document_number"),
            "issue_date": str(self.metadata.get("issue_date") or ""),
            "effective_date": str(self.metadata.get("effective_date") or ""),
            "issuing_body": self.metadata.get("issuing_body"),
            "validity_status": self.metadata.get("validity_status"),
            "chapter": self.metadata.get("chapter"),
            "section": self.metadata.get("section"),
            "article_number": self.metadata.get("article_number"),
            "metadata": self.metadata.copy(),
        }
        return payload

    def to_elasticsearch_doc(self) -> dict[str, Any]:
        """Format document cho Elasticsearch BM25 index."""
        return {
            "chunk_id": self.chunk_id,
            "parent_id": self.parent_id,
            "doc_id": self.doc_id,
            "article_id": self.article_id,
            "clause_id": self.clause_id,
            "parent_clause_id": self.parent_clause_id,
            "title": self.title,
            "content": self.text,
            "content_segmented": self.seg_text,
            "breadcrumb": self.breadcrumb,
            "article_ref": self.article_ref,
            "metadata": self.metadata,
        }


@dataclass
class ChunkResult:
    """Kết quả chunking cho 1 văn bản pháp luật."""
    doc_id: str
    title: str
    parents: list[ParentChunk]
    children: list[ChildChunk]
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "stats": self.stats,
            "num_parents": len(self.parents),
            "num_children": len(self.children),
            "parents": [p.to_store_dict() for p in self.parents],
            "children": [c.to_qdrant_payload() for c in self.children],
        }

    def get_qdrant_payloads(self) -> list[dict[str, Any]]:
        return [c.to_qdrant_payload() for c in self.children]

    def get_elasticsearch_docs(self) -> list[dict[str, Any]]:
        return [c.to_elasticsearch_doc() for c in self.children]

    def get_parent_store_records(self) -> list[dict[str, Any]]:
        return [p.to_store_dict() for p in self.parents]


# ═════════════════════════════════════════════════════════════════════
#  NLP & TEXT UTILITIES
# ═════════════════════════════════════════════════════════════════════

def normalize_text(text: str | None) -> str:
    """Chuẩn hóa văn bản: gỡ bỏ ký tự rác, chuẩn hóa khoảng trắng."""
    if not text:
        return ""
    import html as html_lib
    text = html_lib.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def word_segment(text: str | None) -> str:
    """Phân đoạn từ tiếng Việt qua underthesea (nối bằng dấu _).

    Thiếu underthesea thì báo lỗi, không rơi về text gốc: corpus tách từ một nửa
    sẽ lệch với câu hỏi đã tách từ ở BM25/Dense mà không ai biết.
    """
    if not text:
        return ""
    try:
        from underthesea import word_tokenize
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu underthesea: Child chunk bắt buộc tách từ (Sprint 5, Chunking Engine). "
            "Cài đặt theo requirements.txt rồi chạy lại."
        ) from exc
    try:
        segmented = word_tokenize(text, format="text")
    except TypeError:
        segmented = word_tokenize(text)
    if isinstance(segmented, str):
        tokens = segmented.split()
    else:
        tokens = []
        for token in segmented:
            if isinstance(token, (list, tuple)):
                tokens.extend(str(part) for part in token if str(part).strip())
            elif str(token).strip():
                tokens.append(str(token))
    return " ".join(tok.replace(" ", "_") for tok in tokens if tok.strip())


def tokenizer_version() -> str:
    """Phiên bản underthesea dùng để tách từ, ghi vào report để đối chiếu với phía truy vấn."""
    from importlib.metadata import version
    return version("underthesea")


def segment_units(text: str | None) -> list[str]:
    """Tách theo khoảng trắng để ranh giới chunk ổn định giữa các máy."""
    if not text:
        return []
    return text.split()


def _clean_id(raw_str: str | None, default: str = "item") -> str:
    """Chuẩn hóa ID về ASCII theo data contract, giữ chữ/số và dấu gạch dưới."""
    if not raw_str:
        return default
    value = str(raw_str).strip().lower().replace("đ", "d")
    value = "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    cleaned = re.sub(r"[^a-z0-9]+", "_", value)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or default


def _text_tokens(text: str) -> list[str]:
    """Token hóa bảo thủ để so sánh nội dung, không phụ thuộc NLP tokenizer."""
    return re.findall(r"[^\W_]+", normalize_text(text).lower(), flags=re.UNICODE)


def build_breadcrumb(
    chapter: str | None = None,
    section: str | None = None,
    article_ref: str | None = None,
    article_title: str | None = None,
    clause_range: str | None = None,
) -> str:
    """Xây dựng Breadcrumb phân cấp: Chương X > Mục Y > Điều Z. Tiêu đề > Khoản W."""
    parts: list[str] = []
    if chapter:
        parts.append(chapter.strip())
    if section:
        parts.append(section.strip())
    if article_ref:
        art_part = article_ref.strip()
        if article_title and article_title.strip() and article_title.strip() not in art_part:
            art_part = f"{art_part}. {article_title.strip()}"
        parts.append(art_part)
    if clause_range:
        parts.append(clause_range.strip())
    return " > ".join(parts)


# ═════════════════════════════════════════════════════════════════════
#  CORE: CHUNKING CHO STRUCTURED PARSED DOCUMENT
# ═════════════════════════════════════════════════════════════════════

@dataclass
class _ClauseUnit:
    """Đơn vị Khoản (hoặc một phần của Khoản dài) bóc tách từ bài viết."""
    clause_id: str
    article_id: str
    parent_article_id: str
    clause_number: str | None
    point_letter: str | None
    text: str
    char_count: int
    sub_index: int = 1
    total_subs: int = 1
    implicit: bool = False          # clause_1 giả định của Điều không chia Khoản
    point_ref: str | None = None    # Dải Điểm của phần khi Khoản có danh sách điểm bị tách
    lead_text: str | None = None    # Câu dẫn của danh sách điểm, gắn cho phần thứ 2 trở đi


# Thứ tự chữ cái của Điểm trong văn bản quy phạm pháp luật (không dùng f, j, w, z)
POINT_LETTERS: str = "abcdđeghiklmnopqrstuvxy"
_POINT_MARKER_RE = re.compile(r"(?:^|(?<=[:;.]\s)|(?<=\n))([a-zđ])\)\s")
_NUMBERED_CLAUSE_RE = re.compile(r"^\s*1\s*[.)]\s")


def is_implicit_clause(clauses: list[dict[str, Any]]) -> bool:
    """Điều không chia Khoản: parser bọc cả Điều trong một clause_1 giả định
    (data_contract.md, mục 4 Giao thức phối hợp), nội dung không mở đầu bằng "1."."""
    if len(clauses) != 1:
        return False
    text = clauses[0].get("clause_text") or clauses[0].get("text") or ""
    return not _NUMBERED_CLAUSE_RE.match(text)


def split_point_list(text: str) -> tuple[str, list[tuple[str, str]]] | None:
    """Tách Khoản thành câu dẫn và danh sách Điểm a), b), c)...

    Chỉ nhận dấu Điểm ở đầu dòng hoặc ngay sau ":", ";", "." và chữ cái phải tăng
    liên tục từ "a", để không nhầm với trích dẫn "điểm a)" nằm giữa câu.
    """
    starts: list[tuple[int, str]] = []
    for m in _POINT_MARKER_RE.finditer(text):
        if len(starts) < len(POINT_LETTERS) and m.group(1) == POINT_LETTERS[len(starts)]:
            starts.append((m.start(1), m.group(1)))
    if len(starts) < 2:
        return None
    lead = text[:starts[0][0]].strip()
    points = []
    for i, (pos, letter) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        points.append((letter, text[pos:end].strip()))
    return lead, points


def _point_range(letters: list[str]) -> str | None:
    if not letters:
        return None
    return f"Điểm {letters[0]}" if len(letters) == 1 else f"Điểm {letters[0]}-{letters[-1]}"


def _clause_range(units: list[_ClauseUnit]) -> str:
    """Dải Khoản thật của một nhóm unit (bỏ Khoản giả định, không lặp số khi Khoản bị tách)."""
    nums = list(dict.fromkeys(u.clause_number for u in units if u.clause_number and not u.implicit))
    if not nums:
        return ""
    return f"Khoản {nums[0]}" if len(nums) == 1 else f"Khoản {nums[0]}-{nums[-1]}"


def _truncate_words(text: str | None, max_words: int) -> str:
    words = (text or "").split()
    if max_words <= 0 or not words:
        return ""
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + " ..."


def _fits(pieces: list[str], max_chars: int, max_words: int) -> bool:
    joined = " ".join(pieces)
    return len(joined) <= max_chars and len(joined.split()) <= max_words


def _sentence_atoms(text: str, max_chars: int, max_words: int) -> list[str]:
    """Tách text theo câu; câu tự nó vượt giới hạn thì cắt theo số từ."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()] or [text.strip()]
    sentences = [
        s.strip()
        for p in paragraphs
        for s in re.split(r"(?<=[.!?;:])\s+", p)
        if s.strip()
    ] or [text.strip()]

    atoms: list[str] = []
    for s in sentences:
        s_words = s.split()
        if len(s) > max_chars or len(s_words) > max_words:
            for i in range(0, len(s_words), max_words):
                piece = " ".join(s_words[i:i + max_words]).strip()
                if piece:
                    atoms.append(piece)
        else:
            atoms.append(s)
    return atoms


def _whole_or_sentences(text: str, max_chars: int, max_words: int) -> list[str]:
    return [text] if _fits([text], max_chars, max_words) else _sentence_atoms(text, max_chars, max_words)


def _pack_atoms(
    atoms: list[tuple[str, str | None]],
    max_chars: int,
    max_words: int,
    min_words: int,
) -> list[list[tuple[str, str | None]]]:
    """Gom atom (câu hoặc Điểm) thành các phần của cùng một Khoản.

    Phần ngắn hơn min_words được gộp với phần liền kề nếu vừa giới hạn; phần cuối còn
    ngắn thì dời bớt atom từ phần trước sang. Đuôi dưới CHILD_MIN_CHARS ký tự luôn gộp
    vào phần liền trước (data_contract.md mục 5.2).
    """
    def texts(g: list[tuple[str, str | None]]) -> list[str]:
        return [a for a, _ in g]

    def words(g: list[tuple[str, str | None]]) -> int:
        return len(" ".join(texts(g)).split())

    groups: list[list[tuple[str, str | None]]] = []
    current: list[tuple[str, str | None]] = []
    for atom in atoms:
        if current and not _fits(texts(current) + [atom[0]], max_chars, max_words):
            groups.append(current)
            current = [atom]
        else:
            current.append(atom)
    if current:
        groups.append(current)

    merged = True
    while merged and len(groups) > 1:
        merged = False
        for i, g in enumerate(groups):
            if words(g) >= min_words:
                continue
            if i + 1 < len(groups) and _fits(texts(g + groups[i + 1]), max_chars, max_words):
                groups[i:i + 2] = [g + groups[i + 1]]
                merged = True
                break
            if i > 0 and _fits(texts(groups[i - 1] + g), max_chars, max_words):
                groups[i - 1:i + 1] = [groups[i - 1] + g]
                merged = True
                break

    while len(groups) > 1 and words(groups[-1]) < min_words and len(groups[-2]) > 1:
        candidate = [groups[-2][-1]] + groups[-1]
        if not _fits(texts(candidate), max_chars, max_words) or words(groups[-2][:-1]) < min_words:
            break
        groups[-2] = groups[-2][:-1]
        groups[-1] = candidate

    while len(groups) > 1 and len(" ".join(texts(groups[-1]))) < CHILD_MIN_CHARS:
        groups[-2] = groups[-2] + groups.pop()

    return groups


def _split_long_clause_unit(
    u: _ClauseUnit,
    max_chars: int = 1200,
    max_words: int = 190,
    min_words: int = CHILD_MIN_WORDS,
) -> list[_ClauseUnit]:
    """Tách một Khoản quá dài thành các phần (<= max_chars và <= max_words).

    Khoản có danh sách Điểm được cắt tại ranh giới Điểm; một Điểm chỉ bị tách theo câu
    khi tự nó vượt giới hạn. Mỗi phần ghi dải Điểm vào point_ref, phần thứ 2 trở đi
    mang câu dẫn trong lead_text (chỉ dùng cho embed_text, chunk_text giữ nguyên văn).
    """
    if u.char_count <= max_chars and len(u.text.split()) <= max_words:
        return [u]

    parsed = split_point_list(u.text)
    lead: str | None = None
    atoms: list[tuple[str, str | None]] = []
    if parsed:
        lead, points = parsed
        if lead:
            atoms.extend((s, None) for s in _whole_or_sentences(lead, max_chars, max_words))
        for letter, p_text in points:
            atoms.extend((s, letter) for s in _whole_or_sentences(p_text, max_chars, max_words))
    else:
        atoms = [(s, None) for s in _sentence_atoms(u.text, max_chars, max_words)]

    groups = _pack_atoms(atoms, max_chars, max_words, min_words)
    result_units: list[_ClauseUnit] = []
    for idx, group in enumerate(groups, start=1):
        c_text = " ".join(a for a, _ in group)
        letters = list(dict.fromkeys(letter for _, letter in group if letter))
        result_units.append(_ClauseUnit(
            clause_id=u.clause_id,
            article_id=u.article_id,
            parent_article_id=u.parent_article_id,
            clause_number=u.clause_number,
            point_letter=u.point_letter,
            text=c_text,
            char_count=len(c_text),
            sub_index=idx,
            total_subs=len(groups),
            implicit=u.implicit,
            point_ref=_point_range(letters) if parsed else None,
            lead_text=lead if (lead and idx > 1) else None,
        ))
    return result_units


def _extract_clause_units(
    raw_chunks: list[dict[str, Any]],
    max_unit_chars: int = 1200,
    max_unit_words: int = 190,
    min_words: int = CHILD_MIN_WORDS,
) -> list[_ClauseUnit]:
    """Chuyển đổi danh sách chunks thô từ parser thành danh sách _ClauseUnit (đảm bảo mỗi unit <= max_unit_chars và <= max_unit_words)."""
    units: list[_ClauseUnit] = []
    for item in raw_chunks:
        txt = normalize_text(item.get("text", ""))
        if not txt:
            continue
        base_u = _ClauseUnit(
            clause_id=str(item.get("clause_id") or "").strip(),
            article_id=str(item.get("article_id") or "").strip(),
            parent_article_id=str(item.get("parent_article_id") or "").strip(),
            clause_number=str(item.get("clause_number")).strip() if item.get("clause_number") is not None else None,
            point_letter=str(item.get("point_letter")).strip() if item.get("point_letter") is not None else None,
            text=txt,
            char_count=len(txt),
            sub_index=1,
            total_subs=1,
            implicit=bool(item.get("implicit")),
        )
        units.extend(_split_long_clause_unit(base_u, max_chars=max_unit_chars, max_words=max_unit_words, min_words=min_words))
    return units


def _build_parent_text_from_units(
    article_header: str,
    intro: str | None,
    units: list[_ClauseUnit],
) -> str:
    """Ghép văn bản trọn vẹn cho Parent Chunk."""
    lines: list[str] = []
    if article_header:
        lines.append(article_header)
    if intro and intro.strip() and intro.strip() not in article_header:
        lines.append(intro.strip())
    for u in units:
        lines.append(u.text)
    return "\n".join(lines).strip()


def _split_units_to_parent_groups(
    units: list[_ClauseUnit],
    max_chars: int,
    header_len: int,
    first_group_extra: int = 0,
) -> list[list[_ClauseUnit]]:
    """Gom các Khoản/Điểm thành nhóm Parent, tính cả header và xuống dòng."""
    if not units:
        return []

    groups: list[list[_ClauseUnit]] = []
    current_group: list[_ClauseUnit] = []
    current_size = header_len + first_group_extra

    for u in units:
        unit_size = u.char_count + 1  # newline trước unit trong parent.text
        if current_group and (current_size + unit_size > max_chars):
            groups.append(current_group)
            current_group = [u]
            current_size = header_len + unit_size
        else:
            current_group.append(u)
            current_size += unit_size

    if current_group:
        groups.append(current_group)

    return groups


def _create_child_chunks_from_units(
    parent: ParentChunk,
    units: list[_ClauseUnit],
    title_seg: str,
    config: dict | None = None,
    article_breadcrumb: str | None = None,
    article_intro: str | None = None,
) -> list[ChildChunk]:
    """
    Tạo các Child Chunk từ các đơn vị Khoản/Điểm của Parent.
    Quy tắc:
      1. Mỗi chunk thuộc đúng 1 Clause, không gộp các Khoản khác nhau qua ranh giới Khoản.
      2. Semantic ID chuẩn: {clause_id}_chunk_{idx}.
      3. Gán trực tiếp parent_clause_id = clause_id.
      4. Breadcrumb = breadcrumb cấp Điều + "Khoản N" (+ dải Điểm); Khoản giả định không ghi "Khoản".
      5. Intro của Điều và câu dẫn danh sách điểm chỉ vào embed_text/embed_text_raw,
         trong giới hạn child_max_tokens; text giữ nguyên văn để trích dẫn.
    """
    cfg = config or {}
    max_tokens = int(cfg.get("child_max_tokens", CHILD_MAX_TOKENS))
    context_max = int(cfg.get("child_context_max_words", CHILD_CONTEXT_MAX_WORDS))
    article_bc = article_breadcrumb if article_breadcrumb is not None else parent.breadcrumb
    children: list[ChildChunk] = []

    if not units:
        raw_text = parent.text
        words_count = len(raw_text.split())
        if words_count >= 1 or parent.chunk_type in (ChunkType.PREAMBLE, ChunkType.APPENDIX):
            seg_text = word_segment(raw_text)
            bc_seg = word_segment(parent.breadcrumb)
            embed_text = f"{title_seg} {bc_seg} {seg_text}".strip()
            cid = f"{parent.parent_id}_chunk_1"
            child = ChildChunk(
                chunk_id=cid,
                parent_id=parent.parent_id,
                doc_id=parent.doc_id,
                article_id=parent.parent_id,
                clause_id=f"{parent.parent_id}_clause_1",
                parent_clause_id=f"{parent.parent_id}_clause_1",
                title=parent.title,
                text=raw_text,
                seg_text=seg_text,
                embed_text=embed_text,
                embed_text_raw=f"{parent.title} {parent.breadcrumb} {raw_text}".strip(),
                breadcrumb=parent.breadcrumb,
                article_ref=parent.article_ref,
                chunk_type=parent.chunk_type,
                metadata=parent.metadata.copy(),
            )
            return [child]
        return []

    for u in units:
        combined_text = u.text
        seg_text = word_segment(combined_text)

        # Định dạng chunk_id chuẩn: {clause_id}_chunk_{idx}
        cid = f"{u.clause_id}_chunk_{u.sub_index}"

        cl_ref_str = f"Khoản {u.clause_number}" if u.clause_number and not u.implicit else None
        pt_ref_str = u.point_ref

        # Không lấy breadcrumb của Parent: Parent của Điều dài mang dải Khoản ("Khoản 1-10").
        child_bc = " > ".join(p for p in (article_bc, cl_ref_str, pt_ref_str) if p)
        bc_seg = word_segment(child_bc)

        # Câu dẫn được ưu tiên giữ trọn trước intro khi thiếu chỗ.
        budget = min(context_max, max_tokens - len(f"{title_seg} {bc_seg} {seg_text}".split()))
        lead_part = _truncate_words(u.lead_text, budget)
        intro_part = _truncate_words(article_intro, budget - len(lead_part.split()))
        context = " ".join(p for p in (intro_part, lead_part) if p)
        context_seg = word_segment(context)

        embed_text = " ".join(p for p in (title_seg, bc_seg, context_seg, seg_text) if p)
        embed_text_raw = " ".join(p for p in (parent.title, child_bc, context, combined_text) if p)

        child_meta = parent.metadata.copy()
        child_meta["document_title"] = child_meta.get("title") or parent.title
        child_meta["clause_number"] = str(u.clause_number) if u.clause_number is not None and not u.implicit else None
        child_meta["source_url"] = parent.metadata.get("source_url") or ""
        child_meta["effective_from"] = parent.metadata.get("effective_from") or parent.metadata.get("effective_date") or ""
        child_meta["effective_to"] = parent.metadata.get("effective_to") or parent.metadata.get("expiry_date")
        child_meta["validity_status"] = parent.metadata.get("validity_status")

        child = ChildChunk(
            chunk_id=cid,
            parent_id=parent.parent_id,
            doc_id=parent.doc_id,
            article_id=u.article_id,
            clause_id=u.clause_id,
            parent_clause_id=u.clause_id,
            title=parent.title,
            text=combined_text,
            seg_text=seg_text,
            embed_text=embed_text,
            embed_text_raw=embed_text_raw,
            breadcrumb=child_bc,
            article_ref=parent.article_ref,
            clause_ref=cl_ref_str,
            point_ref=pt_ref_str,
            chunk_type=parent.chunk_type,
            metadata=child_meta,
        )
        children.append(child)

    return children


def _chunk_structured_document(
    doc: dict[str, Any],
    config: dict | None = None,
) -> ChunkResult:
    """
    Xử lý văn bản có cấu trúc JSON từ module `parser/` hoặc theo Data Contract.
    """
    cfg = config or {}
    max_chars = int(cfg.get("parent_max_chars", PARENT_MAX_CHARS))
    max_unit_words = int(cfg.get("child_max_units", CHILD_MAX_UNITS)) - 10
    min_words = int(cfg.get("child_min_words", CHILD_MIN_WORDS))

    doc_id = str(doc.get("document_id") or doc.get("id") or "unknown_doc")

    meta = doc.get("document_metadata") or doc.get("metadata") or {}
    title = str(meta.get("title") or doc.get("title") or "Văn bản pháp luật")
    title_seg = word_segment(title)

    validity_status = meta.get("validity_status") or doc.get("tinh_trang_hieu_luc")
    if not validity_status:
        raise ValueError(f"Thiếu validity_status cho văn bản {doc_id}")

    effective_date = meta.get("effective_date") or doc.get("ngay_co_hieu_luc")
    if not effective_date:
        raise ValueError(f"Thiếu effective_date cho văn bản {doc_id}")

    effective_from = str(effective_date).strip()
    raw_expiry = meta.get("expiry_date") or meta.get("effective_to")
    effective_to = str(raw_expiry).strip() if raw_expiry else None

    source_url = str(meta.get("source_url") or doc.get("source_url") or "").strip()

    common_metadata = {
        "doc_id": doc_id,
        "title": title,
        "document_type": meta.get("document_type") or doc.get("loai_van_ban"),
        "document_number": meta.get("document_number") or doc.get("so_ky_hieu"),
        "issue_date": str(meta.get("issue_date") or ""),
        "effective_date": effective_from,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "source_url": source_url,
        "issuing_body": meta.get("issuing_body") or doc.get("co_quan_ban_hanh"),
        "validity_status": validity_status,
    }

    articles = doc.get("articles", [])
    if not articles:
        raw_text = doc.get("content_text") or doc.get("content_html") or ""
        if raw_text:
            return _fallback_sliding_window(raw_text, doc_id, title, common_metadata, config)
        return ChunkResult(doc_id=doc_id, title=title, parents=[], children=[], stats={"strategy": "empty"})

    all_parents: list[ParentChunk] = []
    all_children: list[ChildChunk] = []

    for art in articles:
        art_id_raw = str(art.get("article_id") or "")
        art_num = str(art.get("article_number") or "")

        clean_doc = _clean_id(doc_id)
        clean_num = _clean_id(art_num or art_id_raw, default="0")
        base_parent_id = f"{clean_doc}_art_{clean_num}"
        art_id = art_id_raw if art_id_raw else base_parent_id

        # Trích xuất tiêu đề ngắn gọn
        raw_title = (art.get("article_title") or "").strip()
        raw_intro = (art.get("intro") or "").strip()

        if raw_title:
            art_title = raw_title if len(raw_title) <= 120 else raw_title[:120].rsplit(" ", 1)[0] + "..."
            art_intro = raw_intro
        elif raw_intro:
            title_candidate = raw_intro.split("\n")[0].split(".")[0].strip()
            if len(title_candidate) > 100:
                title_candidate = title_candidate[:100].rsplit(" ", 1)[0] + "..."
            art_title = title_candidate
            art_intro = raw_intro
        else:
            art_title = ""
            art_intro = ""

        chapter = art.get("chapter")
        section = art.get("section")
        clauses = art.get("clauses", [])
        raw_chunks = []
        if clauses:
            implicit = is_implicit_clause(clauses)
            for cl in clauses:
                cl_num = str(cl.get("clause_number")).strip() if cl.get("clause_number") is not None else None
                cl_id = str(cl.get("clause_id") or "").strip()
                if not cl_id:
                    cl_id = f"{art_id}_clause_{_clean_id(cl_num or '1')}"
                parent_art_id = str(cl.get("parent_article_id") or "").strip() or art_id
                raw_chunks.append({
                    "clause_id": cl_id,
                    "article_id": art_id,
                    "parent_article_id": parent_art_id,
                    "clause_number": cl_num,
                    "text": cl.get("clause_text") or cl.get("text", ""),
                    "point_letter": None,
                    "implicit": implicit,
                })
        else:
            for ch in art.get("chunks", []):
                cl_num = str(ch.get("clause_number")).strip() if ch.get("clause_number") is not None else None
                cl_id = str(ch.get("clause_id") or "").strip()
                if not cl_id:
                    cl_id = f"{art_id}_clause_{_clean_id(cl_num or '1')}"
                raw_chunks.append({
                    "clause_id": cl_id,
                    "article_id": art_id,
                    "parent_article_id": art_id,
                    "clause_number": cl_num,
                    "text": ch.get("text", ""),
                    "point_letter": ch.get("point_letter"),
                })

        article_ref = f"Điều {art_num}" if art_num else (f"Điều {art_id_raw}" if art_id_raw else "Điều")
        base_bc = build_breadcrumb(chapter, section, article_ref, art_title)
        # Breadcrumb dùng tiêu đề rút gọn; header của Parent giữ tiêu đề đầy đủ để phần bị cắt không mất hẳn.
        header_title = raw_title or art_title
        article_header = f"[{article_ref}. {header_title}]".strip() if header_title else f"[{article_ref}]"

        # Chỉ bỏ intro khi toàn bộ intro đã nằm ở đầu Khoản đầu tiên. So với Khoản gốc,
        # không so với phần đầu sau khi Khoản dài đã bị tách.
        if art_intro and raw_chunks:
            intro_tokens = _text_tokens(art_intro)
            first_clause_tokens = _text_tokens(raw_chunks[0]["text"])
            if (
                intro_tokens
                and len(intro_tokens) <= len(first_clause_tokens)
                and first_clause_tokens[:len(intro_tokens)] == intro_tokens
            ):
                art_intro = ""

        # Trích xuất và giới hạn kích thước từng unit
        unit_kwargs = {"max_unit_words": max_unit_words, "min_words": min_words}
        units = _extract_clause_units(raw_chunks, max_unit_chars=max_chars - 300, **unit_kwargs)

        # Parent đầu tiên chứa header + intro + phần đầu của Khoản đầu: tách nhỏ phần đó
        # nếu không vừa, để Parent không vượt max_chars.
        if art_intro and units:
            budget = max_chars - len(article_header) - len(art_intro) - 2
            if units[0].char_count > budget:
                if budget < 200:
                    raise ValueError(
                        f"{doc_id} Điều {art_num}: intro dài {len(art_intro)} ký tự, "
                        f"không xếp được vào Parent <= {max_chars} ký tự"
                    )
                first_id = units[0].clause_id
                first_raw = [rc for rc in raw_chunks if rc["clause_id"] == first_id]
                units = _extract_clause_units(first_raw, max_unit_chars=budget, **unit_kwargs) + [
                    u for u in units if u.clause_id != first_id
                ]

        # Tính tổng kích thước bài viết
        full_article_text = _build_parent_text_from_units(article_header, art_intro, units)
        child_kwargs = {"article_breadcrumb": base_bc, "article_intro": art_intro or None}

        # TRƯỜNG HỢP 1: Toàn bộ Điều vừa trong PARENT_MAX_CHARS -> 1 Parent Chunk duy nhất
        if len(full_article_text) <= max_chars:
            p_chunk = ParentChunk(
                parent_id=base_parent_id,
                doc_id=doc_id,
                title=title,
                text=full_article_text,
                breadcrumb=base_bc,
                article_ref=article_ref,
                clause_refs=_clause_range(units),
                chunk_type=ChunkType.ARTICLE,
                metadata={**common_metadata, "chapter": chapter, "section": section, "article_number": art_num},
            )
            children = _create_child_chunks_from_units(p_chunk, units, title_seg, config, **child_kwargs)
            p_chunk.child_ids = [c.chunk_id for c in children]

            all_parents.append(p_chunk)
            all_children.extend(children)

        # TRƯỜNG HỢP 2: Điều DÀI -> Tách thành nhiều Parent chunks theo nhóm Khoản
        else:
            header_len = len(article_header) + 1
            first_group_extra = len(art_intro) + 1 if art_intro else 0
            groups = _split_units_to_parent_groups(
                units,
                max_chars,
                header_len,
                first_group_extra=first_group_extra,
            )

            for g_idx, group_units in enumerate(groups, start=1):
                p_id = f"{base_parent_id}_p{g_idx}"
                range_str = _clause_range(group_units) or f"Phần {g_idx}"

                group_bc = f"{base_bc} > {range_str}"
                group_text = _build_parent_text_from_units(
                    article_header,
                    art_intro if g_idx == 1 else None,
                    group_units,
                )

                p_chunk = ParentChunk(
                    parent_id=p_id,
                    doc_id=doc_id,
                    title=title,
                    text=group_text,
                    breadcrumb=group_bc,
                    article_ref=article_ref,
                    clause_refs=range_str,
                    chunk_type=ChunkType.ARTICLE,
                    metadata={**common_metadata, "chapter": chapter, "section": section, "article_number": art_num},
                )
                children = _create_child_chunks_from_units(p_chunk, group_units, title_seg, config, **child_kwargs)
                p_chunk.child_ids = [c.chunk_id for c in children]

                all_parents.append(p_chunk)
                all_children.extend(children)

    stats = {
        "strategy": "hierarchical_structured_parent_child",
        "num_articles": len(articles),
        "num_parents": len(all_parents),
        "num_children": len(all_children),
        "avg_children_per_parent": round(len(all_children) / len(all_parents), 2) if all_parents else 0,
    }

    return ChunkResult(
        doc_id=doc_id,
        title=title,
        parents=all_parents,
        children=all_children,
        stats=stats,
    )


# ═════════════════════════════════════════════════════════════════════
#  FALLBACK: SLIDING WINDOW (Khi tài liệu là text phẳng phi cấu trúc)
# ═════════════════════════════════════════════════════════════════════

def _fallback_sliding_window(
    text: str,
    doc_id: str,
    title: str,
    metadata: dict[str, Any],
    config: dict | None = None,
) -> ChunkResult:
    """Sliding window fallback khi văn bản không có cấu trúc Điều/Khoản phân cấp."""
    cfg = config or {}
    max_words = int(cfg.get("parent_max_words", PARENT_MAX_WORDS))
    overlap = int(cfg.get("fallback_overlap_words", FALLBACK_OVERLAP_WORDS))
    min_words = int(cfg.get("child_min_words", CHILD_MIN_WORDS))

    normalized = normalize_text(text)
    words = normalized.split()
    if not words:
        return ChunkResult(doc_id=doc_id, title=title, parents=[], children=[], stats={"strategy": "fallback_empty"})

    title_seg = word_segment(title)
    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []

    start = 0
    p_idx = 1
    clean_doc = _clean_id(doc_id)

    while start < len(words):
        end = min(start + max_words, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        if len(chunk_words) < min_words and p_idx > 1:
            break

        pid = f"{clean_doc}_p{p_idx}"
        bc = f"{title} > Đoạn {p_idx}"
        parent = ParentChunk(
            parent_id=pid,
            doc_id=doc_id,
            title=title,
            text=chunk_text,
            breadcrumb=bc,
            chunk_type=ChunkType.FALLBACK_WINDOW,
            metadata=metadata.copy(),
        )

        cid = f"{pid}_chunk_1"
        seg_text = word_segment(chunk_text)
        bc_seg = word_segment(bc)
        embed_text = f"{title_seg} {bc_seg} {seg_text}".strip()

        child = ChildChunk(
            chunk_id=cid,
            parent_id=pid,
            doc_id=doc_id,
            article_id=f"{clean_doc}_art_0",
            clause_id=f"{clean_doc}_art_0_clause_{p_idx}",
            parent_clause_id=f"{clean_doc}_art_0_clause_{p_idx}",
            title=title,
            text=chunk_text,
            seg_text=seg_text,
            embed_text=embed_text,
            embed_text_raw=f"{title} {bc} {chunk_text}".strip(),
            breadcrumb=bc,
            chunk_type=ChunkType.FALLBACK_WINDOW,
            metadata=metadata.copy(),
        )
        parent.child_ids.append(cid)

        parents.append(parent)
        children.append(child)

        p_idx += 1
        if end == len(words):
            break
        start = max(0, end - overlap)

    return ChunkResult(
        doc_id=doc_id,
        title=title,
        parents=parents,
        children=children,
        stats={
            "strategy": "fallback_sliding_window",
            "num_parents": len(parents),
            "num_children": len(children),
        },
    )


# ═════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═════════════════════════════════════════════════════════════════════

def chunk_legal_document(
    doc: dict[str, Any],
    config: dict | None = None,
) -> ChunkResult:
    """
    Entry point chính để chunking 1 văn bản pháp luật.
    Tự động nhận diện:
      • Nếu `doc` có key "articles" -> Thực hiện Hierarchical Parent-Child trên cấu trúc đã parse.
      • Nếu `doc` chỉ có text phẳng ("content_text") -> Tự động chuyển tiếp sang Fallback Sliding Window.
    """
    if not isinstance(doc, dict):
        raise TypeError("doc phải là một dict JSON hợp lệ")

    if "articles" in doc and isinstance(doc["articles"], list):
        return _chunk_structured_document(doc, config)

    # Legacy raw text handler
    doc_id = str(doc.get("id") or doc.get("document_id") or "unknown")
    title = str(doc.get("title") or "Văn bản pháp luật")
    content = doc.get("content_text") or doc.get("content_html") or ""
    metadata = {
        "doc_id": doc_id,
        "title": title,
        "so_ky_hieu": doc.get("so_ky_hieu"),
        "doc_type": doc.get("loai_van_ban"),
        "co_quan_ban_hanh": doc.get("co_quan_ban_hanh"),
        "effective_date": doc.get("ngay_co_hieu_luc"),
        "tinh_trang_hieu_luc": doc.get("tinh_trang_hieu_luc"),
    }
    return _fallback_sliding_window(content, doc_id, title, metadata, config)


def chunk_legal_documents(
    docs: list[dict[str, Any]],
    config: dict | None = None,
) -> list[ChunkResult]:
    """Chunking danh sách nhiều văn bản pháp luật."""
    return [chunk_legal_document(d, config) for d in docs]


def chunk_parsed_file(
    file_path: str | Path,
    config: dict | None = None,
) -> ChunkResult:
    """Đọc trực tiếp file .json từ parser/parsed_jsons/ và thực hiện chunking."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return chunk_legal_document(data, config)


# ═════════════════════════════════════════════════════════════════════
#  CLI / DEMO
# ═════════════════════════════════════════════════════════════════════

def _demo():
    """Chạy thử nghiệm trên các file mẫu có sẵn trong repo."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 70)
    print("🚀 DEMO: HIERARCHICAL PARENT-CHILD CHUNKING FOR VIETNAMESE LEGAL RAG")
    print("=" * 70)

    sample_files = [
        Path(__file__).parent.parent / "parser" / "parsed_jsons" / "l_52_2014_qh13.json",
        Path(__file__).parent.parent / "parser" / "parsed_jsons" / "nd_126_2014_nd_cp.json",
        Path(__file__).parent.parent / "data" / "sample_documents.json",
        Path(__file__).parent.parent / "parsed_output_test.json",
    ]

    chosen_file = None
    for candidate in sample_files:
        if candidate.exists():
            chosen_file = candidate
            break

    if not chosen_file:
        print("❌ Không tìm thấy file JSON nào trong parser/parsed_jsons/ hoặc data/.")
        return

    print(f"📂 Đang đọc dữ liệu từ: {chosen_file}")
    with open(chosen_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    doc_to_chunk = raw_data[0] if isinstance(raw_data, list) else raw_data

    result = chunk_legal_document(doc_to_chunk)

    print("\n📊 THỐNG KÊ KẾT QUẢ CHUNKING:")
    print(f"  • Document ID       : {result.doc_id}")
    print(f"  • Tiêu đề           : {result.title[:80]}...")
    print(f"  • Số Parent Chunks  : {len(result.parents)}")
    print(f"  • Số Child Chunks   : {len(result.children)}")
    print(f"  • Chiến lược        : {result.stats.get('strategy')}")
    print(f"  • Tỷ lệ Child/Parent: {result.stats.get('avg_children_per_parent', 0)}")

    if result.parents:
        p0 = result.parents[0]
        print("\n" + "-" * 50)
        print("🔍 MẪU PARENT CHUNK (Lưu Store cho Parent-Context Resolver):")
        print(f"  • Parent ID   : {p0.parent_id}")
        print(f"  • Breadcrumb  : {p0.breadcrumb}")
        print(f"  • Article Ref : {p0.article_ref}")
        print(f"  • Child IDs   : {p0.child_ids}")
        print(f"  • Text preview ({len(p0.text)} chars):")
        for line in p0.text.split("\n")[:4]:
            print(f"      {line}")

    if result.children:
        c0 = result.children[0]
        print("\n" + "-" * 50)
        print("🔍 MẪU CHILD CHUNK (Lưu Qdrant & Elasticsearch):")
        print(f"  • Child ID    : {c0.chunk_id}")
        print(f"  • Parent ID   : {c0.parent_id}")
        print(f"  • Breadcrumb  : {c0.breadcrumb}")
        print(f"  • Clause Ref  : {c0.clause_ref}")
        print(f"  • Text preview: {c0.text[:120]}...")
        print(f"  • Embed preview: {c0.embed_text[:120]}...")

    print("\n" + "=" * 70)
    print("✅ Hoàn tất kiểm tra!")


if __name__ == "__main__":
    _demo()
