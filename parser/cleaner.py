import re
from pathlib import Path

import pdfplumber

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw_data"
OUTPUT_DIR = Path(__file__).resolve().parent / "cleaned_texts"
SUB_FOLDERS = ["circulars", "laws_and_decrees"]


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)

    return text.strip()


def extract_pdf_text(pdf_file: Path) -> str:
    extracted_text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                extracted_text += page_text + "\n"
    return extracted_text


def process_all_pdfs() -> int:
    """Chuyển toàn bộ PDF trong raw_data thành TXT. Trả về số file đã xử lý."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    for folder_name in SUB_FOLDERS:
        folder_path = RAW_DATA_DIR / folder_name

        if not folder_path.exists():
            continue

        for pdf_file in sorted(folder_path.glob("*.pdf")):
            print(f"Đang xử lý: {folder_name}/{pdf_file.name}")

            cleaned = clean_text(extract_pdf_text(pdf_file))

            output_file = OUTPUT_DIR / f"{pdf_file.stem}.txt"
            output_file.write_text(cleaned, encoding="utf-8")

            print(f"-> Đã lưu: {output_file.name}")
            count += 1

    return count
