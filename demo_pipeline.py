"""demo_pipeline.py: End-to-End Legal Data Pipeline tự động."""
import glob
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

# Cấu hình UTF-8 cho console Windows tránh UnicodeEncodeError (cp1252)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Nạp động LegalDocumentSchema từ test/schema_test.py để tránh xung đột với module 'test' của Python standard library
schema_spec = importlib.util.spec_from_file_location(
    "schema_test", BASE_DIR / "test" / "schema_test.py"
)
schema_mod = importlib.util.module_from_spec(schema_spec)
schema_spec.loader.exec_module(schema_mod)
LegalDocumentSchema = schema_mod.LegalDocumentSchema

from chunking.chunking_rules import chunk_legal_document


def run_pipeline():
    start_time = time.time()
    print("=" * 60)
    print("BẮT ĐẦU CHẠY END-TO-END LEGAL DATA PIPELINE")
    print("=" * 60)

    try:
        # BƯỚC 1: Thu thập file JSON đã parse
        print("\n[Bước 1/4] Kiểm tra dữ liệu đầu ra từ Parser...")
        parsed_files = sorted(glob.glob("parser/parsed_jsons/*.json"))
        if not parsed_files:
            raise FileNotFoundError("Không tìm thấy file JSON nào trong parser/parsed_jsons!")
        print(f"-> Tìm thấy {len(parsed_files)} văn bản đã bóc tách.")

        # BƯỚC 2: Kiểm định Data Contract (Giao thức 1)
        print("\n[Bước 2/4] Kiểm định Data Contract qua LegalDocumentSchema...")
        validated_docs = []
        for file_path in parsed_files:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            doc_obj = LegalDocumentSchema(**raw_json)
            validated_docs.append(raw_json)
        print(f"-> 100% ({len(validated_docs)}/{len(parsed_files)}) văn bản vượt qua Schema Validation!")

        # BƯỚC 3: Phân mảnh ngữ nghĩa phân cấp (Hierarchical Chunking)
        print("\n[Bước 3/4] Phân mảnh cấu trúc (Parent-Child Chunking)...")
        total_parents = 0
        total_children = 0
        all_child_payloads = []

        for doc_json in validated_docs:
            chunk_res = chunk_legal_document(doc_json)
            total_parents += len(chunk_res.parents)
            total_children += len(chunk_res.children)
            all_child_payloads.extend(chunk_res.get_qdrant_payloads())

        print(f"-> Đã tạo {total_parents} Parent Chunks (<= 1500 ký tự)")
        print(f"-> Đã tạo {total_children} Child Chunks (word-segmented, <= 256 tokens)")

        # BƯỚC 4: Kiểm tra tính sẵn sàng của Payload cho Embedding & Vector DB
        print("\n[Bước 4/4] Kiểm tra định dạng Payload chuẩn bị cho Vector DB...")
        assert len(all_child_payloads) > 0, "Không có child chunk nào được tạo ra!"
        sample_payload = all_child_payloads[0]
        assert "embed_text" in sample_payload, "Payload thiếu trường embed_text!"
        assert "validity_status" in sample_payload, "Payload thiếu validity_status cho bộ lọc!"
        print(f"-> Payload mẫu hợp lệ:")
        print(f"   + ID: {sample_payload.get('id')}")
        print(f"   + Breadcrumb: {sample_payload.get('breadcrumb')}")
        print(f"   + Validity Status: {sample_payload.get('validity_status')}")

        print("\n" + "=" * 60)
        print(f"PIPELINE THỰC THI THÀNH CÔNG TRỌN VẸN TRONG {time.time() - start_time:.2f}s!")
        print("=" * 60)

    except Exception as exc:
        print(f"\n[CRITICAL ERROR] Pipeline thất bại: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
