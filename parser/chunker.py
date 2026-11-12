"""Chunk van ban luat theo Van ban -> Dieu -> Khoan -> Chunk (RAG baseline).

Chay tu thu muc goc du an:
    python parser/chunker.py

Dau vao:
  - L02, ND04, ND05: data/parser_validated/<ID>.json
  - L01, ND01, ND02, ND03: parse PDF goc trong bo nho (KHONG sua PDF/TXT/JSON cu)
Dau ra moi:
  data/chunking_output/documents/<ID>.json
  data/chunking_output/chunks.jsonl
  data/chunking_output/report.json

Chu y: L01.pdf hien chi co 131 dieu. Khong tu sinh Dieu 132-133.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import cleaner
import parser as legal_parser
from verified_sources import apply_verified_sources


BASE = Path(__file__).resolve().parent.parent
READY = BASE / "data" / "parser_validated"
RAW = BASE / "data" / "raw_data" / "laws_and_decrees"
OUTPUT = BASE / "data" / "chunking_output"
DOC_OUTPUT = OUTPUT / "documents"

VALIDATED_CODES = ("L02", "ND04", "ND05")
PDF_CODES = ("L01", "ND01", "ND02", "ND03")
ALL_CODES = ("L01", "L02", "ND01", "ND02", "ND03", "ND04", "ND05")

# Moi khoan duoc giu nguyen. Chi khoan dai moi cat ra nhieu chunk.
MAX_BODY_CHARS = 850
MIN_SPLIT_CHARS = 400


def compact(value: object) -> str:
    return " ".join(str(value or "").split())


def split_clause(text: str, limit: int = MAX_BODY_CHARS) -> list[str]:
    """Chia o ranh gioi cau/dau cach, khong bo mat ky tu nao sau chuan hoa space."""
    rest = compact(text)
    if not rest:
        raise ValueError("Gap clause_text rong.")
    original = rest
    parts: list[str] = []

    while len(rest) > limit:
        # Uu tien ket thuc cau, nhung khong cat qua som.
        punctuation_cuts = [
            rest.rfind(separator, MIN_SPLIT_CHARS, limit)
            for separator in (". ", "; ", "? ", "! ", ": ")
        ]
        best = max(punctuation_cuts)
        if best >= 0:
            cut = best + 1  # giu dau cau trong chunk hien tai
        else:
            # Neu khong co cau: cat theo dau cach gan gioi han.
            cut = rest.rfind(" ", MIN_SPLIT_CHARS, limit + 1)
            if cut < 0:
                # Tu/token qua dai, tim dau cach tiep theo de khong cat giua tu.
                cut = rest.find(" ", limit)
                if cut < 0:
                    break

        head = rest[:cut].strip()
        tail = rest[cut:].strip()
        if not head or not tail:
            break
        parts.append(head)
        rest = tail

    parts.append(rest)
    assert " ".join(parts) == original, "Tach chunk lam mat noi dung!"
    return parts


def article_title_without_number(title: object, number: str) -> str:
    value = compact(title)
    prefix = f"\u0110i\u1ec1u {number}."
    if value.casefold().startswith(prefix.casefold()):
        value = value[len(prefix):].strip()
    return value


def load_document(code: str) -> dict:
    if code in VALIDATED_CODES:
        path = READY / f"{code}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Khong tim thay JSON da xac nhan: {path}")
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        pdf = RAW / f"{code}.pdf"
        if not pdf.is_file():
            raise FileNotFoundError(f"Khong tim thay PDF: {pdf}")
        text = cleaner.clean_text(cleaner.extract_pdf_text(pdf))
        metadata = legal_parser.extract_metadata(text, f"{code}.txt")
        doc = legal_parser.parse_raw_text_to_legal_doc(text, code, metadata)

    if doc.get("document_id") != code:
        raise ValueError(f"Document ID khong khop: {code} => {doc.get('document_id')}")
    doc = apply_verified_sources(doc)
    legal_parser.LegalDocumentSchema.model_validate(doc)
    return doc


def make_chunks(doc: dict, code: str) -> list[dict]:
    meta = doc.get("metadata") or {}
    doc_heading = compact(meta.get("title"))
    doc_number = compact(meta.get("document_number"))
    doc_type = compact(meta.get("document_type"))
    reference = f"{doc_type} {doc_number}".strip()
    source = f"data/raw_data/laws_and_decrees/{code}.pdf"
    records: list[dict] = []

    for article in doc["articles"]:
        number = str(article["article_number"])
        art_title = article_title_without_number(article.get("article_title"), number)
        intro = compact(article.get("intro"))
        chapter = compact(article.get("chapter"))
        section = compact(article.get("section"))
        clauses = article.get("clauses") or []

        # He thong retrieval can biet noi dung thuoc van ban/dieu nao.
        context = [f"Văn bản: {reference} - {doc_heading}".strip(" -")]
        if chapter:
            context.append(f"Chương: {chapter}")
        if section:
            context.append(f"Mục: {section}")
        context.append(f"Điều {number}: {art_title}")

        for clause_index, clause in enumerate(clauses):
            cid = str(clause["clause_id"])
            segments = split_clause(clause["clause_text"])
            # Intro hop le duoc gan vao chunk dau cua khoan dau; khong sua original.
            include_intro = (
                clause_index == 0
                and bool(intro)
                and not compact(clause["clause_text"]).casefold().startswith(intro.casefold())
            )

            created: list[dict] = []
            for index, body in enumerate(segments, start=1):
                chunk_id = f"{cid}_chunk_{index}"
                lines = list(context)
                if include_intro and index == 1:
                    lines.append(f"Dẫn nhập điều: {intro}")
                lines.append(f"Khoản {clause['clause_number']}: {body}")
                chunk_text = "\n".join(lines)
                chunk = {
                    "chunk_id": chunk_id,
                    "parent_clause_id": cid,
                    "clause_number": str(clause["clause_number"]),
                    "point_letter": None,
                    "chunk_text": chunk_text,
                    "char_count": len(chunk_text),
                }
                created.append(chunk)
                records.append({
                    "chunk_id": chunk_id,
                    "document_id": code,
                    "document_number": doc_number,
                    "document_type": doc_type,
                    "document_title": doc_heading,
                    "source_file": article.get("source_file", source),
                    "source_url": article.get("source_url", doc.get("source_verification", {}).get("source_url")),
                    "source_page": article.get("source_page"),
                    "article_id": article["article_id"],
                    "article_number": number,
                    "article_title": art_title,
                    "chapter": article.get("chapter"),
                    "section": article.get("section"),
                    "clause_id": cid,
                    "clause_number": str(clause["clause_number"]),
                    "chunk_index": index,
                    "chunk_text": chunk_text,
                    "char_count": len(chunk_text),
                })

            # V1: chunk duoc gan vao clause (schema 4 tang).
            clause["chunks"] = created

    legal_parser.LegalDocumentSchema.model_validate(doc)
    return records


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise SystemExit(
            f"Thuc muc {OUTPUT} da co du lieu. "
            "Khong ghi de. Hay doi ten/di chuyen thu muc truoc khi chay lai."
        )

    documents: dict[str, dict] = {}
    records: list[dict] = []
    report: dict[str, dict] = {}

    for code in ALL_CODES:
        doc = load_document(code)
        chunks = make_chunks(doc, code)
        n_articles = len(doc["articles"])
        n_clauses = sum(len(a["clauses"]) for a in doc["articles"])
        n_splits = sum(len(c["chunks"]) > 1 for a in doc["articles"] for c in a["clauses"])
        print(f"{code}: {n_articles} dieu, {n_clauses} khoan -> {len(chunks)} chunks ({n_splits} khoan dai)")
        if code == "L01" and n_articles == 131:
            print("  LUU Y: L01.pdf hien co 131/133 dieu; khong tu bo sung Dieu 132-133.")
        documents[code] = doc
        records.extend(chunks)
        report[code] = {
            "articles": n_articles,
            "clauses": n_clauses,
            "chunks": len(chunks),
            "clauses_split": n_splits,
            "source": "validated_json" if code in VALIDATED_CODES else "pdf_parsed_in_memory",
        }

    # Bao dam ID duy nhat, co chunk cho moi khoan va khong mat noi dung khi split.
    ids = [r["chunk_id"] for r in records]
    duplicate_ids = [key for key, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        raise ValueError(f"Chunk ID bi trung: {duplicate_ids[:10]}")

    DOC_OUTPUT.mkdir(parents=True, exist_ok=False)
    for code, doc in documents.items():
        (DOC_OUTPUT / f"{code}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (OUTPUT / "chunks.jsonl").write_text(
        "".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in records),
        encoding="utf-8",
    )
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nHOAN THANH: {len(documents)} van ban, {len(records)} chunks")
    print(f"JSON 4 tang: {DOC_OUTPUT}")
    print(f"JSONL de index RAG: {OUTPUT / 'chunks.jsonl'}")
    print(f"Bao cao: {OUTPUT / 'report.json'}")


if __name__ == "__main__":
    main()
