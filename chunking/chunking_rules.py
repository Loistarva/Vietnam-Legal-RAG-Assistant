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

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION DEFAULTS
# ═══════════════════════════════════════════════════════════════

# --- Parent Chunk Limits (Dành cho Context LLM & Grounding) ---
PARENT_MAX_CHARS: int = 1500     # Ký tự tối đa cho 1 parent chunk
PARENT_MAX_WORDS: int = 260      # Số từ tối đa khi fallback

# --- Child Chunk Limits (Dành cho BGE-M3 Dense & BM25 Sparse Index) ---
CHILD_MAX_TOKENS: int = 256      # Giới hạn token embedding chuẩn BGE-M3
CHILD_MAX_UNITS: int = 200       # Giới hạn đơn vị phân đoạn từ tiếng Việt
CHILD_MIN_WORDS: int = 20        # Gom các khoản/điểm ngắn dưới ngưỡng này để tránh chunk vụn

# --- Sliding Window Fallback ---
FALLBACK_OVERLAP_WORDS: int = 40

# --- Table Limits ---
TABLE_MAX_ROWS: int = 15
TABLE_MAX_CHARS: int = 2500


# ═══════════════════════════════════════════════════════════════
#  DATA CLASSES & SCHEMAS
# ═══════════════════════════════════════════════════════════════

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
    seg_text: str = ""           # Word-segmented text (underthesea)
    embed_text: str = ""         # Title_seg + Breadcrumb_seg + Body_seg cho embedding
    breadcrumb: str = ""
    article_ref: str | None = None
    clause_ref: str | None = None
    point_ref: str | None = None
    parent_clause_id: str | None = None  # Clause ID từ Data Contract (VD: nd_100_art_6_clause_2)
    point_letter: str | None = None      # 'a', 'b', etc.
    char_count: int | None = None
    chunk_type: ChunkType = ChunkType.ARTICLE
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_qdrant_payload(self) -> dict[str, Any]:
        """Format payload cho Vector DB (Qdrant)."""
        return {
            "id": self.chunk_id,
            "chunk_id": self.chunk_id,
            "parent_id": self.parent_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "seg_text": self.seg_text,
            "embed_text": self.embed_text,
            "breadcrumb": self.breadcrumb,
            "article_ref": self.article_ref,
            "clause_ref": self.clause_ref,
            "point_ref": self.point_ref,
            "parent_clause_id": self.parent_clause_id,
            "point_letter": self.point_letter,
            "char_count": self.char_count or len(self.text),
            "chunk_type": self.chunk_type.name,
            "metadata": self.metadata,
            **self.metadata,
        }

    def to_elasticsearch_doc(self) -> dict[str, Any]:
        """Format document cho Elasticsearch BM25 index."""
        return {
            "chunk_id": self.chunk_id,
            "id": self.chunk_id,
            "parent_id": self.parent_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.text,
            "text": self.text,
            "content_segmented": self.seg_text,
            "breadcrumb": self.breadcrumb,
            "article_ref": self.article_ref,
            "clause_ref": self.clause_ref,
            "point_ref": self.point_ref,
            "parent_clause_id": self.parent_clause_id,
            "point_letter": self.point_letter,
            "char_count": self.char_count or len(self.text),
            "chunk_type": self.chunk_type.name,
            "metadata": self.metadata,
            **self.metadata,
        }

    def to_contract_chunk_dict(self) -> dict[str, Any]:
        """Format chunk tuân thủ ChunkSchema trong docs/data_contract.md."""
        cl_num = None
        if self.clause_ref:
            cl_num = self.clause_ref.replace("Khoản ", "").strip()
        return {
            "chunk_id": self.chunk_id,
            "parent_clause_id": self.parent_clause_id or self.parent_id,
            "clause_number": cl_num,
            "point_letter": self.point_letter,
            "chunk_text": self.text,
            "char_count": self.char_count or len(self.text),
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

    def to_contract_doc(self, original_doc: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Khôi phục/xuất ra văn bản có cấu trúc cây 4 tầng chuẩn mực:
        Document -> Article -> Clause -> Chunk (tuân thủ LegalDocumentSchema & ChunkSchema).
        Nếu truyền original_doc, các trường chunks trong từng Clause sẽ được điền đầy đủ.
        """
        import copy
        if original_doc:
            doc_out = copy.deepcopy(original_doc)
        else:
            doc_out = {
                "document_id": self.doc_id,
                "metadata": {
                    "title": self.title,
                    "document_type": "Luật",
                    "document_number": "00/0000",
                    "issue_date": "2020-01-01",
                    "effective_date": "2020-01-01",
                    "issuing_body": "Quốc hội",
                    "validity_status": "Còn hiệu lực",
                },
                "articles": [],
            }

        clause_chunks_map: dict[str, list[dict[str, Any]]] = {}
        for c in self.children:
            c_dict = c.to_contract_chunk_dict()
            key = c.parent_clause_id or c.clause_ref or "default"
            clause_chunks_map.setdefault(key, []).append(c_dict)

        for art in doc_out.get("articles", []):
            for cl in art.get("clauses", []):
                cl_id = cl.get("clause_id")
                cl_num = cl.get("clause_number")
                cl_ref = f"Khoản {cl_num}" if cl_num else None

                matched = clause_chunks_map.get(cl_id) or clause_chunks_map.get(cl_ref) or []
                validated_chunks = []
                for chk in matched:
                    item = dict(chk)
                    if cl_id:
                        item["parent_clause_id"] = cl_id
                    validated_chunks.append(item)
                
                cl["chunks"] = validated_chunks if validated_chunks else None

        return doc_out


# ═══════════════════════════════════════════════════════════════
#  NLP & TEXT UTILITIES
# ═══════════════════════════════════════════════════════════════

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
    """Phân đoạn từ tiếng Việt qua underthesea (nối bằng dấu _), fallback nếu thiếu thư viện."""
    if not text:
        return ""
    try:
        from underthesea import word_tokenize
        tokens = word_tokenize(text)
        return " ".join(tok.replace(" ", "_") for tok in tokens if tok.strip())
    except ImportError:
        return text.strip()


def segment_units(text: str | None) -> list[str]:
    """Trả về danh sách các từ/đơn vị từ đã phân đoạn."""
    if not text:
        return []
    try:
        from underthesea import word_tokenize
        return [tok.replace(" ", "_") for tok in word_tokenize(text) if tok.strip()]
    except ImportError:
        return text.split() if text else []


def _strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để tạo chuỗi ASCII thuần túy."""
    import unicodedata
    s = str(text).replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _clean_id(raw_str: str | None, default: str = "item") -> str:
    """Làm sạch chuỗi để dùng làm Semantic ID an toàn (tuân thủ regex ^[a-zA-Z0-9_]+$)."""
    if not raw_str:
        return default
    ascii_str = _strip_accents(str(raw_str).strip().lower())
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", ascii_str)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or default


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


# ═══════════════════════════════════════════════════════════════
#  CORE: CHUNKING CHO STRUCTURED PARSED DOCUMENT
# ═══════════════════════════════════════════════════════════════

@dataclass
class _ClauseUnit:
    """Đơn vị Khoản / Điểm bóc tách từ bài viết."""
    clause_number: str | None
    point_letter: str | None
    text: str
    char_count: int
    clause_id: str | None = None
    lead_text: str | None = None


def _split_long_clause_unit(
    u: _ClauseUnit,
    max_chars: int,
) -> list[_ClauseUnit]:
    """Tách một Khoản/Điểm quá dài thành các sub-units không vượt quá max_chars."""
    if u.char_count <= max_chars:
        return [u]

    # Cắt nhỏ theo đoạn văn hoặc câu
    paragraphs = [p.strip() for p in u.text.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = [u.text]

    chunks_text: list[str] = []
    curr_pieces: list[str] = []
    curr_len = 0

    for p in paragraphs:
        if len(p) > max_chars:
            sentences = re.split(r"(?<=[.!?;:])\s+", p)
            for s in sentences:
                s_strip = s.strip()
                if not s_strip:
                    continue
                if curr_pieces and curr_len + len(s_strip) > max_chars:
                    chunks_text.append(" ".join(curr_pieces))
                    curr_pieces = [s_strip]
                    curr_len = len(s_strip)
                else:
                    curr_pieces.append(s_strip)
                    curr_len += len(s_strip)
        else:
            if curr_pieces and curr_len + len(p) > max_chars:
                chunks_text.append("\n".join(curr_pieces))
                curr_pieces = [p]
                curr_len = len(p)
            else:
                curr_pieces.append(p)
                curr_len += len(p)

    if curr_pieces:
        chunks_text.append("\n".join(curr_pieces))

    result_units: list[_ClauseUnit] = []
    base_ref = u.clause_number or ""
    for idx, c_text in enumerate(chunks_text, start=1):
        suffix = f" (part {idx})" if len(chunks_text) > 1 else ""
        result_units.append(_ClauseUnit(
            clause_number=f"{base_ref}{suffix}".strip() if base_ref else (f"part {idx}" if len(chunks_text) > 1 else None),
            point_letter=u.point_letter,
            text=c_text,
            char_count=len(c_text),
            clause_id=u.clause_id,
            lead_text=u.lead_text,
        ))

    return result_units


def _extract_clause_units(raw_chunks: list[dict[str, Any]], max_unit_chars: int = 1200) -> list[_ClauseUnit]:
    """Chuyển đổi danh sách chunks thô từ parser thành danh sách _ClauseUnit (đảm bảo mỗi unit <= max_unit_chars)."""
    units: list[_ClauseUnit] = []
    point_regex = re.compile(r'(?:^|\n|(?<=[:;]))\s*([a-zđ])\)\s+', re.IGNORECASE)

    for item in raw_chunks:
        txt = normalize_text(item.get("text") or item.get("chunk_text") or "")
        if not txt:
            continue
        cl_num = str(item.get("clause_number")).strip() if item.get("clause_number") is not None else None
        cl_id = str(item.get("clause_id")).strip() if item.get("clause_id") is not None else None
        pt_let = str(item.get("point_letter")).strip() if item.get("point_letter") is not None else None

        # Trường hợp 1: Item đã có sẵn point_letter (như từ data/sample_documents.json)
        if pt_let:
            base_u = _ClauseUnit(
                clause_number=cl_num,
                point_letter=pt_let,
                text=txt,
                char_count=len(txt),
                clause_id=cl_id,
            )
            if base_u.char_count > max_unit_chars:
                units.extend(_split_long_clause_unit(base_u, max_unit_chars))
            else:
                units.append(base_u)
            continue

        # Trường hợp 2: Item từ Parser (chunks: null), cần bóc tách Điểm a), b), c)... từ clause_text
        matches = list(point_regex.finditer(txt))
        letters = [m.group(1).lower() for m in matches] if matches else []

        if len(matches) >= 2 and letters[0] == 'a' and ('b' in letters):
            lead_end = matches[0].start()
            lead_text = txt[:lead_end].strip()
            for idx, m in enumerate(matches):
                start_pos = m.start()
                end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(txt)
                pt_text = txt[start_pos:end_pos].strip()
                pt_letter = letters[idx]
                full_pt_text = f"{lead_text}\n{pt_text}" if lead_text else pt_text

                pt_u = _ClauseUnit(
                    clause_number=cl_num,
                    point_letter=pt_letter,
                    text=pt_text,
                    char_count=len(full_pt_text),
                    clause_id=cl_id,
                    lead_text=lead_text if lead_text else None,
                )
                if len(full_pt_text) > max_unit_chars:
                    units.extend(_split_long_clause_unit(pt_u, max_unit_chars))
                else:
                    units.append(pt_u)
        else:
            base_u = _ClauseUnit(
                clause_number=cl_num,
                point_letter=None,
                text=txt,
                char_count=len(txt),
                clause_id=cl_id,
            )
            if base_u.char_count > max_unit_chars:
                units.extend(_split_long_clause_unit(base_u, max_unit_chars))
            else:
                units.append(base_u)

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

    last_lead = None
    for u in units:
        if u.lead_text:
            if u.lead_text != last_lead:
                lines.append(u.lead_text)
                last_lead = u.lead_text
            lines.append(f"  {u.text}")
        else:
            lines.append(u.text)
            last_lead = None

    return "\n".join(lines).strip()


def _split_units_to_parent_groups(
    units: list[_ClauseUnit],
    max_chars: int,
    header_len: int,
    intro_len: int = 0,
) -> list[list[_ClauseUnit]]:
    """Gom các Khoản/Điểm thành các nhóm Parent không vượt quá giới hạn ký tự."""
    if not units:
        return []

    groups: list[list[_ClauseUnit]] = []
    current_group: list[_ClauseUnit] = []
    current_size = header_len + intro_len

    for u in units:
        if current_group and (current_size + u.char_count > max_chars):
            groups.append(current_group)
            current_group = [u]
            current_size = header_len + u.char_count
        else:
            current_group.append(u)
            current_size += u.char_count

    if current_group:
        groups.append(current_group)

    return groups


def _create_child_chunks_from_units(
    parent: ParentChunk,
    units: list[_ClauseUnit],
    title_seg: str,
    config: dict | None = None,
    seen_ids: set[str] | None = None,
    intro_text: str | None = None,
) -> list[ChildChunk]:
    """
    Tạo các Child Chunk từ các đơn vị Khoản/Điểm của Parent.
    Quy tắc:
      1. Đóng gói các đơn vị liên tiếp để đạt >= CHILD_MIN_WORDS và <= CHILD_MAX_UNITS.
      2. Nếu 1 Khoản đủ dài: tạo 1 Child riêng biệt.
      3. Nếu nhiều Khoản ngắn (< CHILD_MIN_WORDS): gom thành 1 Child.
      4. Gán Semantic ID theo format: [parent_id]_chunk_[clause]_[point] (hoặc _chunk_[start]_[end] khi gom).
      5. Bảo đảm tính DUY NHẤT tuyệt đối của chunk ID (tránh va chạm ID downstream).
    """
    cfg = config or {}
    max_units = int(cfg.get("child_max_units", CHILD_MAX_UNITS))
    min_words = int(cfg.get("child_min_words", CHILD_MIN_WORDS))

    if seen_ids is None:
        seen_ids = set()

    def _register_cid(candidate: str) -> str:
        cid = candidate
        counter = 1
        while cid in seen_ids:
            counter += 1
            cid = f"{candidate}_{counter}"
        seen_ids.add(cid)
        return cid

    children: list[ChildChunk] = []

    # Nếu có intro_text độc lập và đủ độ dài, phát sinh 1 intro child chunk
    if intro_text and len(intro_text.split()) >= min_words:
        intro_cid = _register_cid(f"{parent.parent_id}_chunk_intro")
        intro_seg = word_segment(intro_text)
        bc_seg = word_segment(parent.breadcrumb)
        children.append(ChildChunk(
            chunk_id=intro_cid,
            parent_id=parent.parent_id,
            doc_id=parent.doc_id,
            title=parent.title,
            text=intro_text,
            seg_text=intro_seg,
            embed_text=f"{title_seg} {bc_seg} {intro_seg}".strip(),
            breadcrumb=parent.breadcrumb,
            article_ref=parent.article_ref,
            clause_ref=None,
            point_ref=None,
            parent_clause_id=None,
            point_letter=None,
            char_count=len(intro_text),
            chunk_type=parent.chunk_type,
            metadata=parent.metadata.copy(),
        ))

    if not units:
        raw_text = parent.text
        words_count = len(raw_text.split())
        if words_count >= min_words or parent.chunk_type in (ChunkType.PREAMBLE, ChunkType.APPENDIX):
            seg_text = word_segment(raw_text)
            bc_seg = word_segment(parent.breadcrumb)
            embed_text = f"{title_seg} {bc_seg} {seg_text}".strip()
            cid = _register_cid(f"{parent.parent_id}_chunk_0")
            child = ChildChunk(
                chunk_id=cid,
                parent_id=parent.parent_id,
                doc_id=parent.doc_id,
                title=parent.title,
                text=raw_text,
                seg_text=seg_text,
                embed_text=embed_text,
                breadcrumb=parent.breadcrumb,
                article_ref=parent.article_ref,
                parent_clause_id=None,
                point_letter=None,
                char_count=len(raw_text),
                chunk_type=parent.chunk_type,
                metadata=parent.metadata.copy(),
            )
            return children + [child]
        return children

    buffer_units: list[_ClauseUnit] = []
    buffer_words = 0

    def _flush_buffer(idx: int) -> ChildChunk | None:
        nonlocal buffer_units, buffer_words
        if not buffer_units:
            return None

        text_parts = []
        seen_lead = set()
        for u in buffer_units:
            if u.lead_text:
                if u.lead_text not in seen_lead:
                    text_parts.append(f"{u.lead_text} {u.text}")
                    seen_lead.add(u.lead_text)
                else:
                    text_parts.append(u.text)
            else:
                text_parts.append(u.text)
        combined_text = "\n".join(text_parts).strip()

        cl_refs = [u.clause_number for u in buffer_units if u.clause_number]
        pt_refs = [u.point_letter for u in buffer_units if u.point_letter]

        cl_ref_str = f"Khoản {cl_refs[0]}" if len(cl_refs) == 1 else (f"Khoản {cl_refs[0]}-{cl_refs[-1]}" if cl_refs else None)
        pt_ref_str = f"Điểm {pt_refs[0]}" if len(pt_refs) == 1 else (f"Điểm {pt_refs[0]}-{pt_refs[-1]}" if pt_refs else None)
        pt_let_val = pt_refs[0] if len(pt_refs) == 1 else (f"{pt_refs[0]}-{pt_refs[-1]}" if pt_refs else None)

        parent_clause_id = buffer_units[0].clause_id if buffer_units[0].clause_id else None

        if len(cl_refs) == 1:
            if pt_refs and len(pt_refs) == 1:
                raw_cid = f"{parent.parent_id}_chunk_{_clean_id(cl_refs[0])}_{_clean_id(pt_refs[0])}"
            elif pt_refs and len(pt_refs) > 1:
                raw_cid = f"{parent.parent_id}_chunk_{_clean_id(cl_refs[0])}_{_clean_id(pt_refs[0])}_{_clean_id(pt_refs[-1])}"
            else:
                raw_cid = f"{parent.parent_id}_chunk_{_clean_id(cl_refs[0])}"
        elif len(cl_refs) > 1:
            raw_cid = f"{parent.parent_id}_chunk_{_clean_id(cl_refs[0])}_{_clean_id(cl_refs[-1])}"
        else:
            if pt_refs and len(pt_refs) == 1:
                raw_cid = f"{parent.parent_id}_chunk_pt_{_clean_id(pt_refs[0])}"
            elif pt_refs and len(pt_refs) > 1:
                raw_cid = f"{parent.parent_id}_chunk_pt_{_clean_id(pt_refs[0])}_{_clean_id(pt_refs[-1])}"
            else:
                raw_cid = f"{parent.parent_id}_chunk_{idx}"

        cid = _register_cid(raw_cid)

        child_bc = parent.breadcrumb
        if cl_ref_str and cl_ref_str not in child_bc:
            child_bc = f"{child_bc} > {cl_ref_str}"
        if pt_ref_str and pt_ref_str not in child_bc:
            child_bc = f"{child_bc} > {pt_ref_str}"

        seg_text = word_segment(combined_text)
        bc_seg = word_segment(child_bc)
        embed_text = f"{title_seg} {bc_seg} {seg_text}".strip()

        child = ChildChunk(
            chunk_id=cid,
            parent_id=parent.parent_id,
            doc_id=parent.doc_id,
            title=parent.title,
            text=combined_text,
            seg_text=seg_text,
            embed_text=embed_text,
            breadcrumb=child_bc,
            article_ref=parent.article_ref,
            clause_ref=cl_ref_str,
            point_ref=pt_ref_str,
            parent_clause_id=parent_clause_id,
            point_letter=pt_let_val,
            char_count=len(combined_text),
            chunk_type=parent.chunk_type,
            metadata=parent.metadata.copy(),
        )
        buffer_units = []
        buffer_words = 0
        return child

    child_idx = 1
    for u in units:
        full_u_text = f"{u.lead_text} {u.text}" if u.lead_text else u.text
        u_words = len(full_u_text.split())

        if u_words > max_units:
            c = _flush_buffer(child_idx)
            if c:
                children.append(c)
                child_idx += 1

            units_list = segment_units(full_u_text)
            for sub_i in range(0, len(units_list), max_units):
                slice_units = units_list[sub_i : sub_i + max_units]
                sub_seg = " ".join(slice_units)
                sub_raw = sub_seg.replace("_", " ")
                if len(sub_raw.split()) < min_words and sub_i > 0:
                    if children:
                        prev = children[-1]
                        prev.text = f"{prev.text} {sub_raw}".strip()
                        prev.seg_text = f"{prev.seg_text} {sub_seg}".strip()
                        prev.char_count = len(prev.text)
                        bc_seg = word_segment(prev.breadcrumb)
                        prev.embed_text = f"{title_seg} {bc_seg} {prev.seg_text}".strip()
                    continue
                cl_part = _clean_id(u.clause_number, default="item")
                pt_part = f"_{_clean_id(u.point_letter)}" if u.point_letter else ""
                raw_sub_cid = f"{parent.parent_id}_chunk_{cl_part}{pt_part}_{sub_i // max_units + 1}"
                sub_cid = _register_cid(raw_sub_cid)
                sub_bc = parent.breadcrumb
                if u.clause_number and f"Khoản {u.clause_number}" not in sub_bc:
                    sub_bc = f"{sub_bc} > Khoản {u.clause_number}"
                if u.point_letter:
                    sub_bc = f"{sub_bc} > Điểm {u.point_letter}"
                bc_seg = word_segment(sub_bc)
                children.append(ChildChunk(
                    chunk_id=sub_cid,
                    parent_id=parent.parent_id,
                    doc_id=parent.doc_id,
                    title=parent.title,
                    text=sub_raw,
                    seg_text=sub_seg,
                    embed_text=f"{title_seg} {bc_seg} {sub_seg}".strip(),
                    breadcrumb=sub_bc,
                    article_ref=parent.article_ref,
                    clause_ref=f"Khoản {u.clause_number}" if u.clause_number else None,
                    point_ref=f"Điểm {u.point_letter}" if u.point_letter else None,
                    parent_clause_id=u.clause_id,
                    point_letter=u.point_letter,
                    char_count=len(sub_raw),
                    chunk_type=parent.chunk_type,
                    metadata=parent.metadata.copy(),
                ))
            continue

        if buffer_words + u_words > max_units and buffer_units:
            c = _flush_buffer(child_idx)
            if c:
                children.append(c)
                child_idx += 1

        buffer_units.append(u)
        buffer_words += u_words

        if buffer_words >= min_words:
            c = _flush_buffer(child_idx)
            if c:
                children.append(c)
                child_idx += 1

    if buffer_units:
        c = _flush_buffer(child_idx)
        if c:
            children.append(c)

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

    doc_id = str(doc.get("document_id") or doc.get("id") or "unknown_doc")

    meta = doc.get("document_metadata") or doc.get("metadata") or {}
    title = str(meta.get("title") or doc.get("title") or "Văn bản pháp luật").strip()
    title_seg = word_segment(title)

    common_metadata = {
        "doc_id": doc_id,
        "title": title,
        "document_type": meta.get("document_type") or doc.get("loai_van_ban"),
        "document_number": meta.get("document_number") or doc.get("so_ky_hieu"),
        "issue_date": str(meta.get("issue_date") or ""),
        "effective_date": str(meta.get("effective_date") or doc.get("ngay_co_hieu_luc") or ""),
        "issuing_body": meta.get("issuing_body") or doc.get("co_quan_ban_hanh"),
        "validity_status": meta.get("validity_status") or doc.get("tinh_trang_hieu_luc") or "Còn hiệu lực",
    }

    articles = doc.get("articles", [])
    if not articles:
        raw_text = doc.get("content_text") or doc.get("content_html") or ""
        if raw_text:
            return _fallback_sliding_window(raw_text, doc_id, title, common_metadata, config)
        return ChunkResult(doc_id=doc_id, title=title, parents=[], children=[], stats={"strategy": "empty"})

    all_parents: list[ParentChunk] = []
    all_children: list[ChildChunk] = []
    seen_child_ids: set[str] = set()
    seen_parent_ids: set[str] = set()

    def _register_pid(candidate: str) -> str:
        pid = candidate
        counter = 1
        while pid in seen_parent_ids:
            counter += 1
            pid = f"{candidate}_{counter}"
        seen_parent_ids.add(pid)
        return pid

    for art in articles:
        art_id_raw = str(art.get("article_id") or "")
        art_num = str(art.get("article_number") or "")

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
            for cl in clauses:
                cl_chunks = cl.get("chunks")
                if cl_chunks and isinstance(cl_chunks, list):
                    for chk in cl_chunks:
                        raw_chunks.append({
                            "clause_number": chk.get("clause_number") or cl.get("clause_number"),
                            "text": chk.get("chunk_text") or chk.get("text") or "",
                            "point_letter": chk.get("point_letter"),
                            "clause_id": cl.get("clause_id"),
                        })
                else:
                    raw_chunks.append({
                        "clause_number": cl.get("clause_number"),
                        "text": cl.get("clause_text") or cl.get("text", ""),
                        "point_letter": None,
                        "clause_id": cl.get("clause_id"),
                    })
        else:
            raw_chunks = art.get("chunks", [])

        clean_doc = _clean_id(doc_id)
        if art_num:
            clean_num = _clean_id(art_num)
            base_parent_id = f"{clean_doc}_art_{clean_num}"
            article_ref = f"Điều {art_num}"
        elif art_id_raw:
            cleaned_raw = _clean_id(art_id_raw)
            if cleaned_raw.startswith(f"{clean_doc}_art_"):
                base_parent_id = cleaned_raw
                suffix = cleaned_raw[len(f"{clean_doc}_art_"):]
                article_ref = f"Điều {suffix}"
            elif "_art_" in cleaned_raw:
                suffix = cleaned_raw.split("_art_", 1)[1]
                base_parent_id = f"{clean_doc}_art_{suffix}"
                article_ref = f"Điều {suffix}"
            elif cleaned_raw.startswith("art_"):
                suffix = cleaned_raw.split("art_", 1)[1]
                base_parent_id = f"{clean_doc}_art_{suffix}"
                article_ref = f"Điều {suffix}"
            else:
                base_parent_id = f"{clean_doc}_art_{cleaned_raw}"
                article_ref = f"Điều {art_id_raw}"
        else:
            base_parent_id = f"{clean_doc}_art_0"
            article_ref = "Điều"

        base_bc = build_breadcrumb(chapter, section, article_ref, art_title)
        article_header = f"[{article_ref}. {art_title}]".strip() if art_title else f"[{article_ref}]"

        # Dọn dẹp footer / chữ ký nếu parser lỡ gắn vào intro của điều cuối
        if art_intro:
            footer_match = re.search(r'(?:[\r\n]+|\s{2,}|\./\.\s*|\.\s+)(?:Nơi nhận:?|TM\.\s+CHÍNH PHỦ|KT\.\s+THỦ TƯỚNG)', art_intro)
            if footer_match:
                art_intro = art_intro[:footer_match.start()].strip()
                if art_intro and not art_intro.endswith('.'):
                    art_intro += '.'

        # Trích xuất và giới hạn kích thước từng unit
        units = _extract_clause_units(raw_chunks, max_unit_chars=max_chars - 300)

        # Tránh lặp lại intro nếu parser đã đưa toàn bộ nội dung bài vào cả intro và chunk[0]
        if art_intro and units:
            unit_sample = units[0].text[:200].strip()
            if art_intro.startswith(unit_sample) or units[0].text.startswith(art_intro[:200]):
                art_intro = ""

        # Nếu intro vẫn quá dài (> max_chars - 300), chuyển thành unit để chunking an toàn không bị tràn parent
        if art_intro and len(art_intro) > max_chars - 300:
            intro_units = _extract_clause_units([{"clause_number": None, "text": art_intro}], max_unit_chars=max_chars - 300)
            units = intro_units + units
            art_intro = ""

        # Tính tổng kích thước bài viết
        full_article_text = _build_parent_text_from_units(article_header, art_intro, units)

        # TRƯỜNG HỢP 1: Toàn bộ Điều vừa trong PARENT_MAX_CHARS -> 1 Parent Chunk duy nhất
        if len(full_article_text) <= max_chars:
            p_id = _register_pid(base_parent_id)
            cl_nums = []
            for u in units:
                if u.clause_number and u.clause_number not in cl_nums:
                    cl_nums.append(u.clause_number)
            if len(cl_nums) == 1:
                clause_refs = f"Khoản {cl_nums[0]}"
            elif len(cl_nums) > 1:
                clause_refs = f"Khoản {cl_nums[0]}-{cl_nums[-1]}"
            else:
                clause_refs = ""

            p_chunk = ParentChunk(
                parent_id=p_id,
                doc_id=doc_id,
                title=title,
                text=full_article_text,
                breadcrumb=base_bc,
                article_ref=article_ref,
                clause_refs=clause_refs,
                chunk_type=ChunkType.ARTICLE,
                metadata={**common_metadata, "chapter": chapter, "section": section, "article_number": art_num},
            )
            children = _create_child_chunks_from_units(
                p_chunk, units, title_seg, config, seen_ids=seen_child_ids, intro_text=art_intro
            )
            p_chunk.child_ids = [c.chunk_id for c in children]

            all_parents.append(p_chunk)
            all_children.extend(children)

        # TRƯỜNG HỢP 2: Điều DÀI -> Tách thành nhiều Parent chunks theo nhóm Khoản
        else:
            header_len = len(article_header) + 2
            intro_len = len(art_intro) + 2 if art_intro else 0
            groups = _split_units_to_parent_groups(units, max_chars, header_len, intro_len=intro_len)

            for g_idx, group_units in enumerate(groups, start=1):
                raw_p_id = f"{base_parent_id}_p{g_idx}"
                p_id = _register_pid(raw_p_id)
                cl_nums = []
                for u in group_units:
                    if u.clause_number and u.clause_number not in cl_nums:
                        cl_nums.append(u.clause_number)
                if len(cl_nums) == 1:
                    range_str = f"Khoản {cl_nums[0]}"
                elif len(cl_nums) > 1:
                    range_str = f"Khoản {cl_nums[0]}-{cl_nums[-1]}"
                else:
                    range_str = f"Phần {g_idx}"

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
                children = _create_child_chunks_from_units(
                    p_chunk, group_units, title_seg, config, seen_ids=seen_child_ids, intro_text=(art_intro if g_idx == 1 else None)
                )
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


# ═══════════════════════════════════════════════════════════════
#  FALLBACK: SLIDING WINDOW (Khi tài liệu là text phẳng phi cấu trúc)
# ═══════════════════════════════════════════════════════════════

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
            title=title,
            text=chunk_text,
            seg_text=seg_text,
            embed_text=embed_text,
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


# ═══════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════

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
) -> ChunkResult | list[ChunkResult]:
    """
    Đọc trực tiếp file .json từ parser_validated/ hoặc parsed_jsons/ và thực hiện chunking.
    
    Hỗ trợ linh hoạt:
      • File chứa 1 văn bản (dict) -> trả về ChunkResult.
      • File chứa danh sách văn bản (list[dict]) -> trả về list[ChunkResult] (hoặc ChunkResult nếu list có 1 phần tử).
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        results = chunk_legal_documents(data, config)
        return results[0] if len(results) == 1 else results
    return chunk_legal_document(data, config)


# ═══════════════════════════════════════════════════════════════
#  CLI / DEMO
# ═══════════════════════════════════════════════════════════════

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
        Path(__file__).parent.parent / "data" / "parser_validated" / "ND04.json",
        Path(__file__).parent.parent / "data" / "parser_validated" / "L02.json",
        Path(__file__).parent.parent / "data" / "parser_validated" / "ND05.json",
        Path(__file__).parent.parent / "parser" / "parsed_jsons" / "luat_52_2014_qh13.json",
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
