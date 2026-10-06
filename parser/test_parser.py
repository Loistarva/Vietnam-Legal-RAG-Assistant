import os
import json
import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path để import các module
CURRENT_DIR = Path(__file__).resolve().parent
BASE_DIR = CURRENT_DIR.parent
sys.path.append(str(BASE_DIR))

# Import các hàm từ cleaner và parser
try:
    from cleaner import process_all_pdfs, OUTPUT_DIR as CLEANED_DIR
    HAS_CLEANER = True
except ImportError as e:
    HAS_CLEANER = False
    CLEANED_DIR = CURRENT_DIR / "cleaned_texts"
    print(f" Không thể import cleaner: {e}")

from parser import parse_raw_text_to_legal_doc

PARSED_OUTPUT_DIR = CURRENT_DIR / "parsed_jsons"
PARSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_pipeline():
    print("=" * 50)
    print(" BẮT ĐẦU LUỒNG XỬ LÝ DỮ LIỆU")
    print("=" * 50)

    # --- BƯỚC 1: Làm sạch dữ liệu (Cleaner) ---
    print("\n--- BƯỚC 1: Làm sạch dữ liệu (Cleaner) ---")
    if HAS_CLEANER:
        try:
            print("Đang đọc và làm sạch các file PDF từ raw_data...")
            process_all_pdfs()
            print(" Chuyển đổi và làm sạch PDF hoàn tất!")
        except Exception as e:
            print(f" Lỗi khi chạy cleaner: {e}")
    else:
        print(" Bỏ qua bước làm sạch (dùng các file .txt sẵn có).")

    # --- BƯỚC 2: Chuyển đổi sang JSON (Parser) ---
    print("\n--- BƯỚC 2: Chuyển đổi sang JSON (Parser) ---")
    
    txt_files = list(CLEANED_DIR.glob("*.txt")) if CLEANED_DIR.exists() else []
    
    if not txt_files:
        print(f" Không tìm thấy file .txt nào trong thư mục: {CLEANED_DIR}")
        return

    print(f" Tìm thấy {len(txt_files)} file .txt cần xử lý...")

    success_count = 0
    fail_count = 0

    for txt_file in txt_files:
        doc_id = txt_file.stem  # Giữ nguyên tên gốc (vd: L01); Pydantic regex ^[A-Za-z0-9_]+$
        
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                raw_text = f.read()

            if not raw_text.strip():
                print(f" Bỏ qua file rỗng: {txt_file.name}")
                continue

            # Mẫu Metadata hợp lệ chuẩn hóa theo Pydantic Schema
            metadata = {
                "title": f"Văn bản pháp luật {txt_file.stem}",
                "document_type": "Luật",  # Chỉ nhận 'Luật', 'Nghị định', 'Thông tư', 'Quyết định', 'Chỉ thị'
                "document_number": txt_file.stem,
                "issue_date": "2024-01-01",
                "effective_date": "2024-01-01",
                "issuing_body": "Quốc hội",
                "validity_status": "Còn hiệu lực"
            }

            parsed_doc = parse_raw_text_to_legal_doc(
                raw_text=raw_text,
                doc_id=doc_id,
                metadata=metadata
            )

            output_file = PARSED_OUTPUT_DIR / f"{doc_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(parsed_doc, f, ensure_ascii=False, indent=2)

            print(f" Thành công: {txt_file.name} -> {output_file.name}")
            success_count += 1

        except Exception as e:
            print(f" Error processing {txt_file.name}: {e}")
            fail_count += 1

    print("\n" + "=" * 50)
    print(f" THÀNH CÔNG: {success_count}/{len(txt_files)} file.")
    print(f" THẤT BẠI: {fail_count} file.")
    print(f" Kết quả JSON được lưu tại: {PARSED_OUTPUT_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    run_pipeline()