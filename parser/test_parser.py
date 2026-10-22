import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
"""
Entry point của pipeline: PDF -> cleaned_texts/*.txt -> parsed_jsons/*.json
(parser kiến trúc 4 tầng: Văn bản -> Điều -> Khoản -> Chunk)

    python test_parser.py                  # chạy cả 2 bước
    python test_parser.py --skip-clean     # chỉ parse các txt có sẵn
    python test_parser.py --only L01 TT01  # chỉ xử lý các file này
    python test_parser.py --no-report      # không in quality report

Sau khi parse, mỗi file JSON được kiểm tra cấu trúc (check_doc_structure).
File nào vi phạm sẽ bị tính là THẤT BẠI và không được ghi ra parsed_jsons.

Unit tests từng hàm của parser nằm ở test_parser_unit.py (chạy bằng pytest).
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import parser as legal_parser  # noqa: E402

CLEANED_DIR = BASE_DIR / "cleaned_texts"
PARSED_DIR = BASE_DIR / "parsed_jsons"

# Các trường metadata nên có giá trị; thiếu thì chỉ nhắc (không làm fail file)
SOFT_METADATA_FIELDS = ("document_number", "issue_date", "issuing_body")


def run_cleaner() -> None:
    print("=" * 60)
    print("BƯỚC 1: PDF -> TXT (cleaner.py)")
    print("=" * 60)

    import cleaner

    total = cleaner.process_all_pdfs()
    print(f"Đã xử lý {total} file PDF.")


def check_doc_structure(doc: dict) -> Tuple[List[str], List[str]]:
    """
    Kiểm tra các ràng buộc cấu trúc của JSON đầu ra.

    Trả về (errors, notes):
      - errors: vi phạm cứng (sai id, mất Điều, sai parent...) -> file bị coi là lỗi
      - notes : nhắc nhẹ (thiếu metadata...) -> chỉ in ra
    """
    errors: List[str] = []
    notes: List[str] = []

    doc_id = doc["document_id"]
    articles = doc.get("articles") or []
    if not articles:
        errors.append("Không có Điều nào trong kết quả.")
        return errors, notes

    # 1. Chuỗi Điều phải liên tục 1..N (Điều lỗi khi dựng bị bỏ qua sẽ làm đứt chuỗi)
    numbers = [int(a["article_number"]) for a in articles]
    expected = list(range(1, numbers[-1] + 1))
    if numbers != expected:
        missing = sorted(set(expected) - set(numbers))
        errors.append(f"Chuỗi Điều không liên tục, thiếu: {missing}")

    for a in articles:
        art_id = a["article_id"]

        if art_id != f"{doc_id}_art_{a['article_number']}":
            errors.append(f"{art_id}: article_id không khớp article_number {a['article_number']}")

        clauses = a.get("clauses") or []
        if not clauses:
            errors.append(f"{art_id}: không có Khoản nào")
            continue

        # 2. Khoản: id, parent, số thứ tự, nội dung
        clause_numbers = []
        for c in clauses:
            cid = c["clause_id"]

            if c["parent_article_id"] != art_id:
                errors.append(f"{cid}: parent_article_id={c['parent_article_id']!r} khác {art_id!r}")

            if cid != f"{art_id}_clause_{c['clause_number']}":
                errors.append(f"{cid}: clause_id không khớp clause_number {c['clause_number']}")

            if not c["clause_text"].strip():
                errors.append(f"{cid}: clause_text rỗng")

            clause_numbers.append(int(c["clause_number"]))

            # 3. Chunk (tầng 4): hiện có thể là None; nếu có thì phải trỏ đúng Khoản cha
            for ch in c.get("chunks") or []:
                if ch["parent_clause_id"] != cid:
                    errors.append(
                        f"{ch['chunk_id']}: parent_clause_id={ch['parent_clause_id']!r} khác {cid!r}"
                    )

        if clause_numbers != list(range(1, len(clause_numbers) + 1)):
            errors.append(f"{art_id}: số thứ tự Khoản không liên tục: {clause_numbers}")

    # 4. Metadata: chỉ nhắc nhẹ
    meta = doc.get("metadata") or {}
    for field in SOFT_METADATA_FIELDS:
        if not meta.get(field):
            notes.append(f"metadata.{field} đang rỗng (parser không tự nhận diện được)")

    return errors, notes


def parse_one_file(txt_path: Path, show_report: bool = True) -> Path:
    raw_text = txt_path.read_text(encoding="utf-8-sig", errors="ignore")

    if not raw_text.strip():
        raise ValueError("File txt rỗng.")

    legal_parser.WARNINGS.clear()
    metadata = legal_parser.extract_metadata(raw_text, str(txt_path))
    metadata_warnings = list(legal_parser.WARNINGS)

    doc_id = legal_parser.build_document_id(
        metadata["document_type"], metadata["document_number"]
    )

    doc = legal_parser.parse_raw_text_to_legal_doc(raw_text, doc_id, metadata)

    legal_parser.WARNINGS[:0] = metadata_warnings

    if show_report:
        legal_parser.quality_report(doc["articles"], doc["footnotes"])

    errors, notes = check_doc_structure(doc)

    for note in notes:
        print(f"   [lưu ý] {note}")

    if errors:
        shown = "; ".join(errors[:5])
        extra = f" (và {len(errors) - 5} lỗi khác)" if len(errors) > 5 else ""
        raise ValueError(f"Cấu trúc JSON không hợp lệ: {shown}{extra}")

    n_articles = len(doc["articles"])
    n_clauses = sum(len(a["clauses"]) for a in doc["articles"])
    print(f"   {n_articles} Điều, {n_clauses} Khoản, {len(doc['footnotes'])} chú thích")

    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PARSED_DIR / f"{doc_id}.json"
    out_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return out_path


def run_parser(only: Optional[List[str]], show_report: bool) -> bool:
    print("=" * 60)
    print("BƯỚC 2: TXT -> JSON (parser.py)")
    print("=" * 60)

    txt_files = sorted(CLEANED_DIR.glob("*.txt")) if CLEANED_DIR.exists() else []

    if only:
        wanted = {s.lower() for s in only}
        txt_files = [p for p in txt_files if p.stem.lower() in wanted]

    if not txt_files:
        print(f"[lỗi] Không có file .txt nào trong {CLEANED_DIR}")
        return False

    ok: List[str] = []
    failed: List[tuple] = []

    for txt_path in txt_files:
        print(f"\n--- Đang parse: {txt_path.name}")
        start = time.time()

        try:
            out_path = parse_one_file(txt_path, show_report=show_report)
            print(f"-> Đã lưu: {out_path.name} ({time.time() - start:.2f}s)")
            ok.append(txt_path.name)
        except Exception as ex:
            print(f"-> LỖI: {type(ex).__name__}: {ex}")
            traceback.print_exc(limit=2)
            failed.append((txt_path.name, str(ex)))

    print("\n" + "=" * 60)
    print(f"TỔNG KẾT: {len(ok)} thành công, {len(failed)} thất bại "
          f"(trên {len(txt_files)} file)")
    print("=" * 60)

    for name, reason in failed:
        print(f"  [x] {name}: {reason[:200]}")

    return not failed


def main() -> int:
    ap = argparse.ArgumentParser(description="Chạy pipeline PDF -> TXT -> JSON")
    ap.add_argument("--skip-clean", action="store_true",
                    help="Bỏ qua bước PDF -> TXT")
    ap.add_argument("--only", nargs="+", metavar="STEM",
                    help="Chỉ parse các file có tên (không đuôi) này")
    ap.add_argument("--no-report", action="store_true",
                    help="Không in quality report")
    args = ap.parse_args()

    if not args.skip_clean:
        run_cleaner()

    return 0 if run_parser(args.only, not args.no_report) else 1


if __name__ == "__main__":
    sys.exit(main())

def test_all_parsed_json_structures():
    """Pytest tests case kiem tra toan bo output json cua parser."""
    json_files = list(PARSED_DIR.glob("*.json"))
    assert len(json_files) > 0, "Khong tim thay file JSON nao trong parsed_jsons"
    for jf in json_files:
        doc = json.loads(jf.read_text(encoding="utf-8"))
        errors, _ = check_doc_structure(doc)
        assert not errors, f"Loi cau truc tai {jf.name}: {errors}"
