"""Xuất Parent/Child Chunk từ JSON của nhóm và sửa nhãn văn bản 02a/2015/TT-BTP.

Cách chạy (từ thư mục worktree Chunking):
    python chunking/export_legal_chunks.py

Không thay thế nguồn parser gốc bị ghi nhầm; tạo bản chuẩn hóa riêng tại
    data/parser_validated/tt_02a_2015_tt_btp.json
"""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "chunking"))
from chunking_rules import chunk_parsed_file  # noqa: E402

BAD_NAME = "nd_158_2005_nd_cp.json"
CORRECT_NAME = "tt_02a_2015_tt_btp.json"
OLD_ID = "nd_158_2005_nd_cp"
NEW_ID = "tt_02a_2015_tt_btp"
ID_KEYS = {"id", "document_id", "article_id", "clause_id", "parent_article_id", "chunk_id", "parent_id"}


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


def main() -> None:
    corrected_path = create_corrected_source()
    inputs = sorted((REPO / "parser/parsed_jsons").glob("*.json"))
    inputs += sorted((REPO / "data/parser_validated").glob("*.json"))
    excluded = {"l_52_2014_qh13.json", BAD_NAME}
    inputs = [p for p in inputs if p.name not in excluded]

    parents = []
    children = []
    file_summary = []
    seen_legal_numbers: set[str] = set()

    for path in inputs:
        with path.open(encoding="utf-8") as f:
            doc = json.load(f)
        metadata = doc.get("document_metadata") or doc.get("metadata") or {}
        legal_number = str(metadata.get("document_number") or "").strip().upper()
        if not legal_number:
            raise ValueError(f"Thiếu số hiệu văn bản: {path.name}")
        if legal_number in seen_legal_numbers:
            raise ValueError(f"Số hiệu văn bản bị trùng: {legal_number} ({path.name})")
        seen_legal_numbers.add(legal_number)

        result = chunk_parsed_file(path)
        source_articles = {str(a.get("article_number")) for a in doc.get("articles", [])}
        covered_articles = {
            str(c.metadata.get("article_number"))
            for c in result.children
            if c.metadata.get("article_number") is not None
        }
        missing_articles = sorted(source_articles - covered_articles)
        if missing_articles:
            raise ValueError(f"{path.name} còn điều không có chunk: {missing_articles}")
        if not result.children:
            raise ValueError(f"Không sinh được Child Chunk cho {path.name}")

        for parent in result.parents:
            parents.append(parent.to_store_dict())
        for child in result.children:
            if not child.text.strip():
                raise ValueError(f"Chunk rỗng: {child.chunk_id}")
            payload = child.to_qdrant_payload()
            payload.update({
                "chunk_id": child.chunk_id,
                "document_id": child.doc_id,
                "article_number": child.metadata.get("article_number"),
                "chunk_text": child.text,
                "metadata": child.metadata.copy(),
            })
            children.append(payload)

        file_summary.append({
            "source": str(path.relative_to(REPO)).replace("\\", "/"),
            "document_id": result.doc_id,
            "document_number": legal_number,
            "validity_status": metadata.get("validity_status"),
            "num_articles": len(source_articles),
            "num_parents": len(result.parents),
            "num_children": len(result.children),
        })
        print(f"{path.name}: {len(result.parents)} Parent, {len(result.children)} Child")

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

    output = REPO / "data/chunking_output"
    output.mkdir(parents=True, exist_ok=True)
    chunks_path = output / "chunks.jsonl"
    parent_path = output / "parents.json"
    report_path = output / "chunking_report.json"

    chunks_text = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in children)
    parents_text = json.dumps(parents, ensure_ascii=False, indent=2) + "\n"
    report = {
        "num_documents": len(inputs),
        "num_parents": len(parents),
        "num_children": len(children),
        "num_duplicate_child_ids": len(dup_child),
        "corrected_document": str(corrected_path.relative_to(REPO)).replace("\\", "/"),
        "excluded_source_files": sorted(excluded),
        "documents": file_summary,
        "warnings": [
            "Chưa hoàn thành xác minh hiệu lực pháp lý ở các JSON nguồn khác.",
            "Luật 52/2014/QH13 mới có 131 điều trong JSON nguồn (cần rà soát Điều 132-133).",
            "Chỉ xác minh Gold Context sau khi kiểm tra nội dung chunk và phiên bản văn bản.",
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
    print("So van ban:", len(inputs))
    print("Parent:", len(parents))
    print("Child:", len(children))
    print("ID trung:", len(dup_child))
    print("Da sua nhan TT02a:", corrected_path.relative_to(REPO))
    print("Child output:", chunks_path.relative_to(REPO))
    print("Parent output:", parent_path.relative_to(REPO))
    print("Bao cao:", report_path.relative_to(REPO))
    print("LUU Y: Metadata hieu luc cac van ban khac chua duoc nghiem thu.")


if __name__ == "__main__":
    main()
