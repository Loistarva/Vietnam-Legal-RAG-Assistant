"""Dựng lại PDF có lớp text từ một file TXT, mỗi dòng TXT là một dòng PDF.

Dùng cho văn bản nhóm phải dựng lại (vd TT 07/2001/TT-BTP, TT 07/2002/TT-BTP, A26).
Sau khi dựng, script trích xuất lại bằng parser/cleaner.py::process_pdf và dừng nếu
text trích ra khác TXT nguồn (so sau khi gộp khoảng trắng).

Font hệ thống thường dùng chung một glyph cho nhiều mã (gạch nối "-" với soft hyphen U+00AD,
dấu cách với U+00A0, ";" với U+037E). PyMuPDF ghi ToUnicode theo mã lớn nhất, nên cleaner
đọc ra soft hyphen rồi xóa mất "-". Script tạo bản sao font chỉ giữ mã nhỏ nhất cho mỗi glyph.

Usage (cần pymupdf, fontTools):
    python scripts/rebuild_text_pdf.py SOURCE.txt OUTPUT.pdf --font C:/Windows/Fonts/times.ttf
"""
import argparse
import re
import sys
import tempfile
from pathlib import Path

import pymupdf
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "parser"))
import cleaner  # noqa: E402

PAGE_W, PAGE_H, MARGIN = 595, 842, 36  # A4, điểm


def dedupe_font(src: Path, dst: Path) -> None:
    font = TTFont(src)
    cmap = font["cmap"]
    cmap.tables = [t for t in cmap.tables if t.isUnicode()]
    for table in cmap.tables:
        first: dict[str, int] = {}
        for cp in sorted(table.cmap):
            first.setdefault(table.cmap[cp], cp)
        table.cmap = {cp: g for cp, g in table.cmap.items() if first[g] == cp}
    font.save(dst)


def build(lines: list[str], font_path: Path, out: Path) -> float:
    font = pymupdf.Font(fontfile=str(font_path))
    size = 11.0
    while max(font.text_length(line, fontsize=size) for line in lines) > PAGE_W - 2 * MARGIN:
        size -= 0.25
    lead = size * 1.35
    doc = pymupdf.open()
    page, y = None, 0.0
    for line in lines:
        if page is None or y + lead > PAGE_H - MARGIN:
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            page.insert_font(fontname="body", fontfile=str(font_path))
            y = MARGIN + size
        if line.strip():
            page.insert_text((MARGIN, y), line, fontname="body", fontsize=size)
        y += lead
    doc.set_metadata({"title": out.stem, "creator": "scripts/rebuild_text_pdf.py", "producer": "PyMuPDF"})
    doc.save(out, garbage=4, deflate=True)
    doc.close()
    return size


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--font", type=Path, required=True, help="TTF hỗ trợ tiếng Việt, vd Times New Roman")
    args = ap.parse_args()

    lines = args.source.read_text(encoding="utf-8").splitlines()
    with tempfile.TemporaryDirectory() as tmp:
        font = Path(tmp) / "font.ttf"
        dedupe_font(args.font, font)
        size = build(lines, font, args.output)
        raw, clean = Path(tmp) / "raw.txt", Path(tmp) / "clean.txt"
        if not cleaner.process_pdf(args.output, raw, clean):
            raise SystemExit("process_pdf không trích xuất được PDF vừa dựng")
        norm = lambda s: [re.sub(r"\s+", " ", x).strip() for x in s.splitlines() if x.strip()]  # noqa: E731
        if norm(raw.read_text(encoding="utf-8")) != norm("\n".join(lines)):
            raise SystemExit("Text trích từ PDF khác TXT nguồn; không dùng file này")
    print(f"{args.output}: {pymupdf.open(args.output).page_count} trang, cỡ chữ {size}, trích xuất khớp nguồn")


if __name__ == "__main__":
    main()
