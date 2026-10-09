"""
Entry point của pipeline: PDF -> cleaned_texts/*.txt -> parsed_jsons/*.json

    python test_parser.py                  # chạy cả 2 bước
    python test_parser.py --skip-clean     # chỉ parse các txt có sẵn
    python test_parser.py --only L01 TT01  # chỉ xử lý các file này
    python test_parser.py --no-report      # không in quality report
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import parser as legal_parser  # noqa: E402

CLEANED_DIR = BASE_DIR / "cleaned_texts"
PARSED_DIR = BASE_DIR / "parsed_jsons"


def run_cleaner() -> None:
    print("=" * 60)
    print("BƯỚC 1: PDF -> TXT (cleaner.py)")
    print("=" * 60)

    import cleaner

    total = cleaner.process_all_pdfs()
    print(f"Đã xử lý {total} file PDF.")


def parse_one_file(txt_path: Path, show_report: bool = True) -> Path:
    raw_text = txt_path.read_text(encoding="utf-8-sig", errors="ignore")

    if not raw_text.strip():
        raise ValueError("File txt rỗng.")

    doc_id = legal_parser.normalize_document_id(str(txt_path))

    legal_parser.WARNINGS.clear()
    metadata = legal_parser.extract_metadata(raw_text, str(txt_path))
    metadata_warnings = list(legal_parser.WARNINGS)

    doc = legal_parser.parse_raw_text_to_legal_doc(raw_text, doc_id, metadata)

    legal_parser.WARNINGS[:0] = metadata_warnings

    if show_report:
        legal_parser.quality_report(doc["articles"], doc["footnotes"])

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
