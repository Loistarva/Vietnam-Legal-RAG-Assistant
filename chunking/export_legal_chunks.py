"""Xuất Parent/Child Chunk từ parser/parsed_jsons.

Cách chạy (từ thư mục gốc repository):
    python chunking/export_legal_chunks.py
"""
from __future__ import annotations

import copy
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "chunking"))
from chunking_rules import (
    CHILD_MAX_TOKENS,
    CHILD_MAX_UNITS,
    CHILD_MIN_WORDS,
    FALLBACK_OVERLAP_WORDS,
    PARENT_MAX_CHARS,
    chunk_parsed_file,
    normalize_text,
)  # noqa: E402

BAD_NAME = "nd_158_2005_nd_cp.json"
CORRECT_NAME = "tt_02a_2015_tt_btp.json"
OLD_ID = "nd_158_2005_nd_cp"
NEW_ID = "tt_02a_2015_tt_btp"
ID_KEYS = {"id", "document_id", "article_id", "clause_id", "parent_article_id", "chunk_id", "parent_id", "parent_clause_id"}


def update_internal_identifiers(value: Any) -> Any:
    """Chỉ thay mã định danh, không thay nội dung pháp luật hay các trích dẫn."""
    if isinstance(value, list):
        return [update_internal_identifiers(v) for v in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in ID_KEYS and isinstance(item, str) and item.startswith(OLD_ID):
                result[key] = NEW_ID + item[len(OLD_ID):]
            else:
                result[key] = update_internal_identifiers(item)
        return result
    return value


def create_corrected_source() -> Path:
    original_path = REPO / "parser/parsed_jsons" / BAD_NAME
    if not original_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file nguồn cần sửa nhãn: {original_path}")
    with original_path.open(encoding="utf-8") as file:
        raw = json.load(file)

    meta = raw.get("metadata") or {}
    title = str(meta.get("title") or "").upper()
    if "THÔNG TƯ" not in title or "126/2014" not in title:
        raise ValueError("Tên văn bản không giống Thông tư 02a/2015/TT-BTP; dừng để tránh gán nhầm.")
    if len(raw.get("articles") or []) != 17:
        raise ValueError("Số điều không phải 17 như file đã kiểm tra; cần đối chiếu nguồn trước.")

    corrected = update_internal_identifiers(copy.deepcopy(raw))
    corrected["document_id"] = NEW_ID
    metadata = corrected.setdefault("metadata", {})
    metadata.update({
        "document_type": "Thông tư",
        "document_number": "02a/2015/TT-BTP",
        "issue_date": "2015-02-23",
        "effective_date": "2015-04-10",
        "issuing_body": "Bộ Tư pháp",
        "validity_status": "Hết hiệu lực",
        "expiry_date": "2016-01-02",
    })

    destination = REPO / "data/parser_validated" / CORRECT_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(corrected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def _tokens(text: str) -> list[str]:
    """Token stream dùng để bảo đảm không làm rơi chữ/số so với parser."""
    return re.findall(r"[^\W_]+", text.lower(), flags=re.UNICODE)


def _assert_source_text_preserved(doc: dict[str, Any], result: Any, source_name: str) -> None:
    """Bảo đảm clause parser không bị mất token trong Child chunks."""
    by_article: dict[str, list[str]] = defaultdict(list)
    for child in result.children:
        by_article[str(child.metadata.get("article_number"))].append(child.text)

    parent_by_article: dict[str, list[str]] = defaultdict(list)
    for parent in result.parents:
        parent_by_article[str(parent.metadata.get("article_number"))].append(parent.text)

    for article in doc.get("articles", []):
        article_number = str(article.get("article_number"))
        clauses = article.get("clauses") or []
        source_text = " ".join(
            normalize_text(clause.get("clause_text") or clause.get("text") or "")
            for clause in clauses
        )
        if not source_text:
            source_text = " ".join(
                normalize_text(chunk.get("text") or "")
                for chunk in article.get("chunks", [])
            )
        expected = _tokens(source_text)
        actual = _tokens(" ".join(by_article.get(article_number, [])))
        cursor = 0
        for token in actual:
            if cursor < len(expected) and token == expected[cursor]:
                cursor += 1
        if cursor != len(expected):
            missing = " ".join(expected[cursor:cursor + 12])
            raise ValueError(
                f"{source_name} Điều {article_number}: Child chunks làm mất/đảo nội dung "
                f"ở token {cursor}/{len(expected)}: {missing!r}"
            )

        intro = normalize_text(article.get("intro") or "")
        intro_tokens = _tokens(intro)
        first_clause_tokens = _tokens(
            normalize_text((clauses[0].get("clause_text") or clauses[0].get("text") or ""))
        ) if clauses else []
        # Intro trùng ở đầu clause thì chỉ cần xuất hiện một lần trong Parent.
        if intro_tokens and not (
            len(intro_tokens) <= len(first_clause_tokens)
            and first_clause_tokens[:len(intro_tokens)] == intro_tokens
        ):
            expected_parent = intro_tokens + expected
        else:
            expected_parent = expected
        actual_parent = _tokens(" ".join(parent_by_article.get(article_number, [])))
        parent_cursor = 0
        for token in actual_parent:
            if parent_cursor < len(expected_parent) and token == expected_parent[parent_cursor]:
                parent_cursor += 1
        if parent_cursor != len(expected_parent):
            missing = " ".join(expected_parent[parent_cursor:parent_cursor + 12])
            raise ValueError(
                f"{source_name} Điều {article_number}: Parent chunks làm mất/đảo nội dung "
                f"ở token {parent_cursor}/{len(expected_parent)}: {missing!r}"
            )


def main() -> None:
    parser_sources = sorted((REPO / "parser/parsed_jsons").glob("*.json"))
    if not parser_sources:
        raise FileNotFoundError("Không tìm thấy JSON nguồn trong parser/parsed_jsons")

    original_bad = REPO / "parser/parsed_jsons" / BAD_NAME
    if original_bad.exists():
        corrected_path = create_corrected_source()
        inputs = [
            (source, corrected_path if source.name == BAD_NAME else source)
            for source in parser_sources
        ]
        corrected_doc_str = str(corrected_path.relative_to(REPO)).replace("\\", "/")
    else:
        inputs = [(source, source) for source in parser_sources]
        corrected_doc_str = "parser/parsed_jsons/tt_02a_2015_tt_btp.json"

    parents = []
    children = []
    file_summary = []
    seen_legal_numbers: set[str] = set()

    for source_path, chunk_path in inputs:
        with chunk_path.open(encoding="utf-8") as f:
            doc = json.load(f)
        metadata = doc.get("document_metadata") or doc.get("metadata") or {}
        legal_number = str(metadata.get("document_number") or "").strip().upper()
        if not legal_number:
            raise ValueError(f"Thiếu số hiệu văn bản: {source_path.name}")
        if legal_number in seen_legal_numbers:
            raise ValueError(f"Số hiệu văn bản bị trùng: {legal_number} ({source_path.name})")
        seen_legal_numbers.add(legal_number)

        result = chunk_parsed_file(chunk_path)
        source_articles = {str(a.get("article_number")) for a in doc.get("articles", [])}
        covered_articles = {
            str(c.metadata.get("article_number"))
            for c in result.children
            if c.metadata.get("article_number") is not None
        }
        missing_articles = sorted(source_articles - covered_articles)
        if missing_articles:
            raise ValueError(f"{source_path.name} còn điều không có chunk: {missing_articles}")
        if not result.children:
            raise ValueError(f"Không sinh được Child Chunk cho {source_path.name}")
        _assert_source_text_preserved(doc, result, source_path.name)

        for parent in result.parents:
            parents.append(parent.to_store_dict())
        for child in result.children:
            if not child.text.strip():
                raise ValueError(f"Chunk rỗng: {child.chunk_id}")
            if "\x00" in child.text or "\x00" in child.seg_text or "\x00" in child.embed_text:
                raise ValueError(f"Chunk chứa NUL byte: {child.chunk_id}")
            # The structural limit is based on canonical source whitespace units.
            # Segmented text can have a different token count across Underthesea versions.
            if len(child.text.split()) > CHILD_MAX_UNITS:
                raise ValueError(f"Chunk vượt CHILD_MAX_UNITS: {child.chunk_id}")
            payload = child.to_qdrant_payload()
            payload.update({
                "chunk_id": child.chunk_id,
                "document_id": child.doc_id,
                "article_id": child.article_id,
                "clause_id": child.clause_id,
                "parent_clause_id": child.parent_clause_id,
                "article_number": child.metadata.get("article_number"),
                "chunk_text": child.text,
                "metadata": child.metadata.copy(),
            })
            if payload["id"] != payload["chunk_id"]:
                raise ValueError(f"id và chunk_id không khớp: {child.chunk_id}")
            if payload["document_id"] != payload["doc_id"]:
                raise ValueError(f"document_id và doc_id không khớp: {child.chunk_id}")
            if payload["text"] != payload["chunk_text"]:
                raise ValueError(f"text và chunk_text không khớp: {child.chunk_id}")
            if payload["doc_id"] != payload["metadata"].get("doc_id"):
                raise ValueError(f"doc_id metadata không khớp: {child.chunk_id}")
            if payload["article_number"] != payload["metadata"].get("article_number"):
                raise ValueError(f"article_number metadata không khớp: {child.chunk_id}")
            if not re.fullmatch(r"[A-Za-z0-9_]+", child.chunk_id):
                raise ValueError(f"chunk_id không theo data contract ASCII: {child.chunk_id}")
            children.append(payload)

        file_summary.append({
            "source": str(source_path.relative_to(REPO)).replace("\\", "/"),
            "chunking_source": str(chunk_path.relative_to(REPO)).replace("\\", "/"),
            "document_id": result.doc_id,
            "document_number": legal_number,
            "validity_status": metadata.get("validity_status"),
            "num_articles": len(source_articles),
            "num_parents": len(result.parents),
            "num_children": len(result.children),
        })
        print(f"{source_path.name}: {len(result.parents)} Parent, {len(result.children)} Child")

    child_ids = [c["chunk_id"] for c in children]
    parent_ids = [p["parent_id"] for p in parents]
    dup_child = [x for x, n in Counter(child_ids).items() if n > 1]
    dup_parent = [x for x, n in Counter(parent_ids).items() if n > 1]
    if dup_child or dup_parent:
        raise ValueError(f"ID trùng: Child={dup_child[:10]}, Parent={dup_parent[:10]}")
    parent_id_set = set(parent_ids)
    if any(c["parent_id"] not in parent_id_set for c in children):
        raise ValueError("Có Child không có Parent tương ứng")
    parent_links = [cid for p in parents for cid in p.get("child_ids", [])]
    if Counter(parent_links) != Counter(child_ids):
        raise ValueError("Parent.child_ids và danh sách Child không khớp")
    oversized_parents = [
        p["parent_id"] for p in parents if len(p["text"]) > PARENT_MAX_CHARS
    ]
    if oversized_parents:
        raise ValueError(f"Parent vượt giới hạn 1500 ký tự: {oversized_parents[:10]}")

    output = REPO / "data/chunking_output"
    output.mkdir(parents=True, exist_ok=True)
    chunks_path = output / "chunks.jsonl"
    parent_path = output / "parents.json"
    report_path = output / "chunking_report.json"

    chunks_text = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in children)
    parents_text = json.dumps(parents, ensure_ascii=False, indent=2) + "\n"
    try:
        import underthesea  # noqa: F401
        tokenization_backend = "underthesea"
    except ImportError:
        tokenization_backend = "fallback_whitespace"

    report = {
        "num_documents": len(parser_sources),
        "num_parents": len(parents),
        "num_children": len(children),
        "num_duplicate_child_ids": len(dup_child),
        "chunker": "chunking/chunking_rules.py::chunk_parsed_file",
        "chunking_config": {
            "parent_max_chars": PARENT_MAX_CHARS,
            "child_max_tokens": CHILD_MAX_TOKENS,
            "child_max_units": CHILD_MAX_UNITS,
            "child_min_words": CHILD_MIN_WORDS,
            "fallback_overlap_words": FALLBACK_OVERLAP_WORDS,
        },
        "tokenization_backend": tokenization_backend,
        "corrected_document": corrected_doc_str,
        "included_source_files": [str(p.relative_to(REPO)).replace("\\", "/") for p in parser_sources],
        "excluded_source_files": [],
        "documents": file_summary,
        "warnings": [
            "Chưa hoàn thành xác minh hiệu lực pháp lý ở các JSON nguồn khác.",
            "JSON parser l_52_2014_qh13.json chỉ có 131 điều; văn bản chính thức có Điều 132-133 nên corpus đang thiếu phần này.",
            "JSON parser nq_01_2024_nq_hdtp.json: Điều 8 chỉ có một khoản và clause_text kết thúc ở 'tại'; cần khôi phục toàn văn từ nguồn chính thức.",
            "Các kiểm tra chunk xác nhận bảo toàn nội dung parser, không thay thế đối chiếu pháp lý với văn bản chính thức.",
        ],
    }

    for path, text in [
        (chunks_path, chunks_text),
        (parent_path, parents_text),
        (report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
    ]:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(path)

    print("\n===== XUAT CHUNKING THANH CONG =====")
    print("So file parser:", len(parser_sources))
    print("Parent:", len(parents))
    print("Child:", len(children))
    print("ID trung:", len(dup_child))
    print("Da sua nhan TT02a:", corrected_doc_str)
    print("Tokenization:", tokenization_backend)
    print("Child output:", chunks_path.relative_to(REPO))
    print("Parent output:", parent_path.relative_to(REPO))
    print("Bao cao:", report_path.relative_to(REPO))
    print("LUU Y: Metadata hieu luc cac van ban khac chua duoc nghiem thu.")


if __name__ == "__main__":
    main()
