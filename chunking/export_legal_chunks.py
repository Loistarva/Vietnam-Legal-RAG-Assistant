"""Xuất Parent/Child Chunk từ parser/parsed_jsons.

Cách chạy (từ thư mục gốc repository, môi trường phải có underthesea):
    python chunking/export_legal_chunks.py
"""
from __future__ import annotations

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
    CHILD_MIN_CHARS,
    CHILD_MIN_WORDS,
    CHILD_CONTEXT_MAX_WORDS,
    FALLBACK_OVERLAP_WORDS,
    PARENT_MAX_CHARS,
    chunk_parsed_file,
    is_implicit_clause,
    normalize_text,
    tokenizer_version,
)  # noqa: E402

KHOAN_SEGMENT_RE = re.compile(r"Khoản \S+")


def _tokens(text: str) -> list[str]:
    """Token stream dùng để bảo đảm không làm rơi chữ/số so với parser."""
    return re.findall(r"[^\W_]+", text.lower(), flags=re.UNICODE)


def _kept_intro(article: dict[str, Any]) -> str:
    """Intro còn giữ sau khi chunker bỏ intro trùng với đầu Khoản đầu tiên."""
    intro = normalize_text(article.get("intro") or "")
    clauses = article.get("clauses") or []
    intro_tokens = _tokens(intro)
    first_clause_tokens = _tokens(
        normalize_text((clauses[0].get("clause_text") or clauses[0].get("text") or ""))
    ) if clauses else []
    if intro_tokens and not (
        len(intro_tokens) <= len(first_clause_tokens)
        and first_clause_tokens[:len(intro_tokens)] == intro_tokens
    ):
        return intro
    return ""


def _assert_source_text_preserved(doc: dict[str, Any], result: Any, source_name: str) -> list[str]:
    """Bảo đảm clause parser không bị mất token trong Child chunks và intro vào được Child.

    Trả về danh sách Điều có intro bị cắt bớt trong embed_text (để ghi cảnh báo).
    """
    by_article: dict[str, list[str]] = defaultdict(list)
    embed_by_article: dict[str, list[str]] = defaultdict(list)
    for child in result.children:
        art_no = str(child.metadata.get("article_number"))
        by_article[art_no].append(child.text)
        embed_by_article[art_no].append(child.embed_text_raw)

    parent_by_article: dict[str, list[str]] = defaultdict(list)
    for parent in result.parents:
        parent_by_article[str(parent.metadata.get("article_number"))].append(parent.text)

    truncated_intro: list[str] = []
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

        # Intro trùng ở đầu clause thì chỉ cần xuất hiện một lần trong Parent.
        intro = _kept_intro(article)
        intro_tokens = _tokens(intro)
        expected_parent = intro_tokens + expected
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

        # Intro (vd "Việc kết hôn bị cấm trong những trường hợp sau đây:") phải tìm được qua Child.
        if intro_tokens:
            embed_tokens = [" ".join(_tokens(t)) for t in embed_by_article.get(article_number, [])]
            head = " ".join(intro_tokens[:3])
            if not any(head in t for t in embed_tokens):
                raise ValueError(f"{source_name} Điều {article_number}: intro không có trong embed_text của Child nào")
            if not any(" ".join(intro_tokens) in t for t in embed_tokens):
                truncated_intro.append(f"{source_name} Điều {article_number}")
    return truncated_intro


def _assert_breadcrumb(child: Any, implicit_clause_ids: set[str]) -> None:
    """Breadcrumb của Child chỉ chứa đúng Khoản của chính nó (không dải Khoản, không "(phần")."""
    segments = child.breadcrumb.split(" > ")
    khoan_segments = [s for s in segments if KHOAN_SEGMENT_RE.fullmatch(s)]
    if child.clause_id in implicit_clause_ids:
        if child.clause_ref is not None or khoan_segments:
            raise ValueError(f"Điều không chia Khoản nhưng chunk ghi Khoản: {child.chunk_id}")
        return
    expected = [child.clause_ref] if child.clause_ref else []
    if khoan_segments != expected or "(phần" in child.breadcrumb:
        raise ValueError(f"Breadcrumb sai Khoản ({child.breadcrumb!r}): {child.chunk_id}")


def main() -> None:
    try:
        backend_version = tokenizer_version()
    except Exception as exc:  # PackageNotFoundError hoặc lỗi cài đặt
        raise SystemExit(
            "Thiếu underthesea: không export corpus chưa tách từ. Cài theo requirements.txt rồi chạy lại."
        ) from exc

    parser_sources = sorted((REPO / "parser/parsed_jsons").glob("*.json"))
    if not parser_sources:
        raise FileNotFoundError("Không tìm thấy JSON nguồn trong parser/parsed_jsons")

    parents = []
    children = []
    file_summary = []
    seen_legal_numbers: set[str] = set()
    truncated_intros: list[str] = []
    short_fragments: list[str] = []
    unknown_validity: list[str] = []

    for source_path in parser_sources:
        with source_path.open(encoding="utf-8") as f:
            doc = json.load(f)
        metadata = doc.get("document_metadata") or doc.get("metadata") or {}
        legal_number = str(metadata.get("document_number") or "").strip().upper()
        if not legal_number:
            raise ValueError(f"Thiếu số hiệu văn bản: {source_path.name}")
        if legal_number in seen_legal_numbers:
            raise ValueError(f"Số hiệu văn bản bị trùng: {legal_number} ({source_path.name})")
        seen_legal_numbers.add(legal_number)
        if metadata.get("validity_status") == "Không xác định":
            unknown_validity.append(source_path.name)

        source_clause_ids: set[str] = set()
        implicit_clause_ids: set[str] = set()
        for article in doc.get("articles", []):
            clauses = article.get("clauses") or []
            ids = {str(c.get("clause_id")) for c in clauses if c.get("clause_id")}
            source_clause_ids |= ids
            if is_implicit_clause(clauses):
                implicit_clause_ids |= ids

        result = chunk_parsed_file(source_path)
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
        truncated_intros.extend(_assert_source_text_preserved(doc, result, source_path.name))

        chunks_per_clause = Counter(c.clause_id for c in result.children)
        for parent in result.parents:
            parents.append(parent.to_store_dict())
        for child in result.children:
            if not child.text.strip():
                raise ValueError(f"Chunk rỗng: {child.chunk_id}")
            if len(child.text) < CHILD_MIN_CHARS:
                raise ValueError(f"Chunk dưới {CHILD_MIN_CHARS} ký tự (data_contract.md mục 5.2): {child.chunk_id}")
            if "\x00" in child.text or "\x00" in child.seg_text or "\x00" in child.embed_text:
                raise ValueError(f"Chunk chứa NUL byte: {child.chunk_id}")
            # The structural limit is based on canonical source whitespace units.
            # Segmented text can have a different token count across Underthesea versions.
            if len(child.text.split()) > CHILD_MAX_UNITS:
                raise ValueError(f"Chunk vượt CHILD_MAX_UNITS: {child.chunk_id}")
            if child.clause_id not in source_clause_ids:
                raise ValueError(f"clause_id không có trong parser: {child.chunk_id}")
            _assert_breadcrumb(child, implicit_clause_ids)
            if chunks_per_clause[child.clause_id] > 1 and len(child.text.split()) < CHILD_MIN_WORDS:
                short_fragments.append(child.chunk_id)
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
            if not re.fullmatch(r"[a-z0-9_]+", child.chunk_id):
                raise ValueError(f"chunk_id không theo data contract (chữ thường, số, gạch dưới): {child.chunk_id}")
            children.append(payload)

        file_summary.append({
            "source": str(source_path.relative_to(REPO)).replace("\\", "/"),
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
        raise ValueError(f"Parent vượt giới hạn {PARENT_MAX_CHARS} ký tự: {oversized_parents[:10]}")

    output = REPO / "data/chunking_output"
    output.mkdir(parents=True, exist_ok=True)
    chunks_path = output / "chunks.jsonl"
    parent_path = output / "parents.json"
    report_path = output / "chunking_report.json"

    chunks_text = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in children)
    parents_text = json.dumps(parents, ensure_ascii=False, indent=2) + "\n"

    warnings = [
        "Các kiểm tra chunk xác nhận bảo toàn nội dung parser, không thay thế đối chiếu pháp lý với văn bản chính thức.",
    ]
    if unknown_validity:
        warnings.append(f"validity_status 'Không xác định' ở {len(unknown_validity)} văn bản: {unknown_validity}")
    if short_fragments:
        warnings.append(
            f"{len(short_fragments)} mảnh dưới {CHILD_MIN_WORDS} từ của Khoản bị tách, không gộp được trong giới hạn: "
            f"{short_fragments[:20]}"
        )
    if truncated_intros:
        warnings.append(
            f"Intro bị cắt bớt trong embed_text (giới hạn {CHILD_CONTEXT_MAX_WORDS} từ / {CHILD_MAX_TOKENS} token) "
            f"ở {len(truncated_intros)} Điều: {truncated_intros[:20]}"
        )

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
            "child_min_chars": CHILD_MIN_CHARS,
            "child_context_max_words": CHILD_CONTEXT_MAX_WORDS,
            "fallback_overlap_words": FALLBACK_OVERLAP_WORDS,
        },
        "tokenization_backend": "underthesea",
        "tokenization_version": backend_version,
        "included_source_files": [str(p.relative_to(REPO)).replace("\\", "/") for p in parser_sources],
        "excluded_source_files": [],
        "documents": file_summary,
        "warnings": warnings,
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
    print("Tokenization: underthesea", backend_version)
    print("Canh bao:", len(warnings) - 1)
    print("Child output:", chunks_path.relative_to(REPO))
    print("Parent output:", parent_path.relative_to(REPO))
    print("Bao cao:", report_path.relative_to(REPO))


if __name__ == "__main__":
    main()
