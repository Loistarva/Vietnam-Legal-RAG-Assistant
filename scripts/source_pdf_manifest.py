"""Manifest SHA-256 của PDF nguồn trong data/raw_data (A29).

Mỗi PDF được ghi document_id (theo số hiệu parser đọc được trong parser/cleaned_texts),
sha256, kích thước và commit đã đưa bản hiện tại vào repo. test/test_source_pdfs.py so
manifest với file trên đĩa, nên thay hoặc thêm PDF mà không cập nhật manifest thì test đỏ.

Cách chạy từ thư mục gốc repository:
    python scripts/source_pdf_manifest.py --check
    python scripts/source_pdf_manifest.py --write            # thêm PDF mới, giữ bản ghi cũ
    python scripts/source_pdf_manifest.py --write --allow-changed   # khi cố ý thay PDF
    python scripts/source_pdf_manifest.py --write --map data/raw_data/x.pdf=nd_24_2013_nd_cp
                                        # PDF không có TXT trong parser/cleaned_texts

Manifest không thay cho nguồn tải: URL và ngày tải của từng PDF do người tải ghi vào
download_status của data/reference/document_versions.json (như bản ghi L04).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw_data"
MANIFEST = ROOT / "data" / "reference" / "source_pdfs.json"
CLEANED_DIR = ROOT / "parser" / "cleaned_texts"


def pdf_files() -> list[Path]:
    return sorted((p for p in RAW_DIR.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"),
                  key=lambda p: p.relative_to(ROOT).as_posix().lower())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def document_id_for(pdf: Path) -> str:
    """document_id theo số hiệu mà parser đọc từ TXT đã làm sạch của PDF này."""
    sys.path.insert(0, str(ROOT / "parser"))
    import parser as legal_parser  # noqa: PLC0415 - parser/ chỉ cần khi thêm PDF mới

    txt = CLEANED_DIR / f"{pdf.stem}.txt"
    if not txt.exists():
        raise SystemExit(f"Chưa có {rel(txt)}: chạy parser/cleaner.py cho {rel(pdf)} trước")
    number = legal_parser.extract_document_number(txt.read_text(encoding="utf-8"))
    record = legal_parser.lookup_document_version(number) if number else None
    if not record:
        raise SystemExit(f"Không tìm thấy bản ghi registry cho {rel(pdf)} (số hiệu {number!r})")
    return record["document_id"]


def last_commit(path: Path) -> dict | None:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%h%x09%as", "--", rel(path)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    ).stdout.strip()
    if not out:
        return None
    commit, day = out.split("\t")
    return {"commit": commit, "date": day}


def load() -> list[dict]:
    if not MANIFEST.exists():
        return []
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]


def check(entries: list[dict]) -> list[str]:
    errors = []
    by_path = {e["path"]: e for e in entries}
    on_disk = {rel(p): p for p in pdf_files()}
    for path in sorted(set(on_disk) - set(by_path)):
        errors.append(f"{path}: PDF chưa có trong {rel(MANIFEST)}")
    for path in sorted(set(by_path) - set(on_disk)):
        errors.append(f"{path}: có trong manifest nhưng không còn trên đĩa")
    for path in sorted(set(by_path) & set(on_disk)):
        if sha256(on_disk[path]) != by_path[path]["sha256"]:
            errors.append(f"{path}: sha256 khác manifest (PDF đã bị thay)")
    return errors


def write(entries: list[dict], allow_changed: bool, mapping: dict[str, str] | None = None) -> list[dict]:
    mapping = mapping or {}
    by_path = {e["path"]: e for e in entries}
    result = []
    for pdf in pdf_files():
        path = rel(pdf)
        digest = sha256(pdf)
        old = by_path.get(path)
        if old and old["sha256"] == digest:
            result.append(old)
            continue
        if old and not allow_changed:
            raise SystemExit(f"{path}: sha256 đổi; chạy lại với --allow-changed nếu cố ý thay PDF")
        result.append({
            "path": path,
            "document_id": mapping.get(path) or (old["document_id"] if old else document_id_for(pdf)),
            "sha256": digest,
            "bytes": pdf.stat().st_size,
            "added_in": last_commit(pdf),
        })
    return result


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    cli.add_argument("--allow-changed", action="store_true")
    cli.add_argument("--map", action="append", default=[], metavar="PATH=DOCUMENT_ID",
                     help="document_id cho PDF không có TXT trong parser/cleaned_texts")
    args = cli.parse_args(argv)
    mapping = dict(item.split("=", 1) for item in args.map)
    entries = load()
    if args.check:
        errors = check(entries)
        for error in errors:
            print(error)
        print("PASS" if not errors else f"FAIL: {len(errors)} lỗi")
        return 1 if errors else 0
    files = write(entries, args.allow_changed, mapping)
    MANIFEST.write_text(json.dumps({
        "description": "SHA-256 của PDF nguồn trong data/raw_data; sinh bởi scripts/source_pdf_manifest.py --write, "
                       "kiểm bởi test/test_source_pdfs.py. added_in là commit gần nhất đổi file lúc ghi manifest. "
                       "Nguồn tải và ngày tải ghi ở download_status của document_versions.json.",
        "files": files,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {len(files)} PDF vào {rel(MANIFEST)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
