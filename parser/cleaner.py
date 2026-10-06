import os
import re
from pathlib import Path
import pdfplumber

# 1. Khai báo đường dẫn
BASE_DIR = Path(__file__).parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw_data"
OUTPUT_DIR = Path(__file__).parent / "cleaned_texts"

# Đảm bảo thư mục đầu ra tồn tại
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(text: str) -> str:
    if not text:
        return ""

    # 1. Bỏ ký tự không in được / null bytes
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 2. Xóa các ký tự thừa phổ biến trong PDF văn bản pháp luật Việt Nam
    text = text.replace('\xa0', ' ')

    # 3. Nối từ bị nối gạch ngang ở cuối dòng (ví dụ: "nghị -\n định" -> "nghị định")
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

    # 4. Gộp các dòng bị ngắt lẻ tẻ trong cùng một đoạn văn
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)

    # 5. Xóa khoảng trắng thừa giữa các từ
    text = re.sub(r'[ \t]+', ' ', text)

    return text.strip()


def process_all_pdfs():
    # Danh sách các thư mục con chứa file PDF trong raw_data
    sub_folders = ["circulars", "laws_and_decrees"]

    for folder_name in sub_folders:
        folder_path = RAW_DATA_DIR / folder_name

        if not folder_path.exists():
            continue

        # Duyệt qua tất cả các file .pdf trong thư mục con
        for pdf_file in folder_path.glob("*.pdf"):
            print(f"Đang xử lý: {folder_name}/{pdf_file.name}")

            extracted_text = ""
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += page_text + "\n"

            # Làm sạch văn bản
            cleaned = clean_text(extracted_text)

            # Tạo file .txt trong cleaned_texts (ví dụ: TT01.pdf -> TT01.txt)
            output_file = OUTPUT_DIR / f"{pdf_file.stem}.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(cleaned)

            print(f"-> Đã lưu: {output_file.name}")


