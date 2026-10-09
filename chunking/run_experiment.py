"""
run_experiment.py — Bộ công cụ chạy thử nghiệm & đánh giá các cấu hình Chunking.

Tạo ra 2 sản phẩm đầu ra bắt buộc theo yêu cầu:
  1. chunking/chunking_evaluation.xlsx: Bảng đánh giá, so sánh các cấu hình chi tiết (Excel).
  2. chunking/chunking_examples.json: Tệp JSON chứa các trường hợp chunking mẫu minh họa:
     - Điều bình thường
     - Điều dài được tách thành nhiều Parent (lặp lại tiêu đề, breadcrumb Khoản)
     - Khoản dài có nhiều Điểm
     - Gom các Khoản ngắn
     - Định dạng payload cho Qdrant, Elasticsearch, Parent Store.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# Đảm bảo import được chunking_rules
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from chunking_rules import (  # noqa: E402
    PARENT_MAX_CHARS,
    CHILD_MAX_TOKENS,
    CHILD_MAX_UNITS,
    CHILD_MIN_WORDS,
    ChunkResult,
    chunk_legal_document,
    chunk_parsed_file,
)


# ═══════════════════════════════════════════════════════════════
#  CÁC CẤU HÌNH THỬ NGHIỆM (CONFIG MATRIX)
# ═══════════════════════════════════════════════════════════════

CONFIGS: dict[str, dict[str, Any]] = {
    "Config A (Baseline - Khuyến nghị)": {
        "parent_max_chars": 1500,
        "child_max_tokens": 256,
        "child_max_units": 200,
        "child_min_words": 20,
        "mo_ta": "Cân bằng tối ưu: Parent chứa trọn điều/nhóm khoản <=1500 ký tự; Child <=200 từ vừa vặn embedding BGE-M3 (256 tokens)",
    },
    "Config B (Small - Fine-grained)": {
        "parent_max_chars": 800,
        "child_max_tokens": 128,
        "child_max_units": 100,
        "child_min_words": 15,
        "mo_ta": "Tách nhỏ hơn: Parent <=800 ký tự; Child <=100 từ phù hợp các mô hình Bi-Encoder có context window hẹp",
    },
    "Config C (Large - Broad Context)": {
        "parent_max_chars": 2500,
        "child_max_tokens": 512,
        "child_max_units": 350,
        "child_min_words": 30,
        "mo_ta": "Ngữ cảnh rộng: Parent <=2500 ký tự; Child <=350 từ giữ nhiều thông tin bổ trợ nhưng có thể làm loãng vector similarity",
    },
    "Config D (Strict - Không gom khoản)": {
        "parent_max_chars": 1500,
        "child_max_tokens": 256,
        "child_max_units": 200,
        "child_min_words": 1,
        "mo_ta": "Tách tuyệt đối theo từng khoản, không gom khoản ngắn; dễ tạo ra các chunk chỉ có 5-10 từ",
    },
}


def load_test_documents() -> dict[str, dict[str, Any]]:
    """Nạp tất cả các file JSON mẫu có trong repo."""
    docs: dict[str, dict[str, Any]] = {}

    candidates = [
        BASE_DIR.parent / "parser" / "parsed_jsons" / "L01.json",
        BASE_DIR.parent / "parser" / "parsed_jsons" / "ND01.json",
        BASE_DIR.parent / "parser" / "parsed_jsons" / "TT01.json",
        BASE_DIR.parent / "data" / "sample_documents.json",
        BASE_DIR.parent / "parsed_output_test.json",
    ]

    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = json.load(f)
                if isinstance(content, list):
                    for idx, item in enumerate(content):
                        docs[f"{p.stem}_{idx}"] = item
                elif isinstance(content, dict):
                    docs[p.stem] = content
            except Exception as e:
                print(f"[Cảnh báo] Không thể đọc {p.name}: {e}")

    return docs


def evaluate_config(
    docs: dict[str, dict[str, Any]],
    cfg_name: str,
    cfg_params: dict[str, Any],
) -> dict[str, Any]:
    """Chạy thử nghiệm trên 1 cấu hình và thu thập số liệu thống kê."""
    total_parents = 0
    total_children = 0
    parent_lengths: list[int] = []
    child_words: list[int] = []
    split_article_count = 0
    has_breadcrumb_count = 0
    under_50_words = 0
    w50_to_150_words = 0
    w150_to_250_words = 0
    over_250_words = 0

    per_doc_stats = {}

    for doc_key, doc in docs.items():
        res: ChunkResult = chunk_legal_document(doc, cfg_params)
        n_p = len(res.parents)
        n_c = len(res.children)
        total_parents += n_p
        total_children += n_c

        # Thống kê chi tiết từng doc
        per_doc_stats[doc_key] = {
            "num_parents": n_p,
            "num_children": n_c,
            "ratio": round(n_c / n_p, 2) if n_p else 0,
        }

        for p in res.parents:
            plen = len(p.text)
            parent_lengths.append(plen)
            if "_p" in p.parent_id:
                split_article_count += 1
            if p.breadcrumb and " > " in p.breadcrumb:
                has_breadcrumb_count += 1

        for c in res.children:
            cw = len(c.text.split())
            child_words.append(cw)
            if cw < 50:
                under_50_words += 1
            elif 50 <= cw <= 150:
                w50_to_150_words += 1
            elif 150 < cw <= 250:
                w150_to_250_words += 1
            else:
                over_250_words += 1

    avg_p_len = round(sum(parent_lengths) / len(parent_lengths), 1) if parent_lengths else 0
    max_p_len = max(parent_lengths) if parent_lengths else 0
    avg_c_words = round(sum(child_words) / len(child_words), 1) if child_words else 0
    max_c_words = max(child_words) if child_words else 0
    bc_rate = round(has_breadcrumb_count / total_parents * 100, 1) if total_parents else 0

    return {
        "config_name": cfg_name,
        "parent_max_chars": cfg_params.get("parent_max_chars"),
        "child_max_tokens": cfg_params.get("child_max_tokens"),
        "child_min_words": cfg_params.get("child_min_words"),
        "total_parents": total_parents,
        "total_children": total_children,
        "child_per_parent_ratio": round(total_children / total_parents, 2) if total_parents else 0,
        "avg_parent_chars": avg_p_len,
        "max_parent_chars": max_p_len,
        "avg_child_words": avg_c_words,
        "max_child_words": max_c_words,
        "split_parents_count": split_article_count,
        "breadcrumb_coverage_pct": bc_rate,
        "child_under_50_words": under_50_words,
        "child_50_to_150_words": w50_to_150_words,
        "child_150_to_250_words": w150_to_250_words,
        "child_over_250_words": over_250_words,
        "mo_ta": cfg_params.get("mo_ta", ""),
        "per_doc_stats": per_doc_stats,
    }


def generate_evaluation_excel(results: list[dict[str, Any]], out_path: Path):
    """Xuất file Excel đánh giá đẹp mắt với nhiều sheet phân tích."""
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # Sheet 1: Bảng so sánh tổng quan
        summary_rows = []
        for r in results:
            summary_rows.append({
                "Cấu hình": r["config_name"],
                "Parent Max (ký tự)": r["parent_max_chars"],
                "Child Max (token)": r["child_max_tokens"],
                "Child Min (từ)": r["child_min_words"],
                "Tổng số Parent": r["total_parents"],
                "Tổng số Child": r["total_children"],
                "Tỷ lệ Child / Parent": r["child_per_parent_ratio"],
                "Độ dài Parent TB (ký tự)": r["avg_parent_chars"],
                "Độ dài Parent Max (ký tự)": r["max_parent_chars"],
                "Độ dài Child TB (từ)": r["avg_child_words"],
                "Độ dài Child Max (từ)": r["max_child_words"],
                "Số Parent bị tách do Điều dài": r["split_parents_count"],
                "Bao phủ Breadcrumb (%)": f"{r['breadcrumb_coverage_pct']}%",
                "Mô tả & Định hướng": r["mo_ta"],
            })
        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_excel(writer, sheet_name="TongQuan_SoSanh", index=False)

        # Sheet 2: Chi tiết theo từng văn bản
        doc_rows = []
        doc_names = list(results[0]["per_doc_stats"].keys()) if results else []
        for dname in doc_names:
            row = {"Văn bản": dname}
            for r in results:
                d_stat = r["per_doc_stats"].get(dname, {})
                cfg_short = r["config_name"].split(" ")[1]
                row[f"{cfg_short}_Parents"] = d_stat.get("num_parents", 0)
                row[f"{cfg_short}_Children"] = d_stat.get("num_children", 0)
                row[f"{cfg_short}_Tyle"] = d_stat.get("ratio", 0)
            doc_rows.append(row)
        df_docs = pd.DataFrame(doc_rows)
        df_docs.to_excel(writer, sheet_name="ChiTiet_TungVanBan", index=False)

        # Sheet 3: Phân bố kích thước Child Chunk
        dist_rows = []
        for r in results:
            tot = r["total_children"] or 1
            dist_rows.append({
                "Cấu hình": r["config_name"],
                "Tổng số Child": r["total_children"],
                "< 50 từ (Số lượng)": r["child_under_50_words"],
                "< 50 từ (Tỷ lệ %)": f"{round(r['child_under_50_words'] / tot * 100, 1)}%",
                "50 - 150 từ (Số lượng)": r["child_50_to_150_words"],
                "50 - 150 từ (Tỷ lệ %)": f"{round(r['child_50_to_150_words'] / tot * 100, 1)}%",
                "150 - 250 từ (Số lượng)": r["child_150_to_250_words"],
                "150 - 250 từ (Tỷ lệ %)": f"{round(r['child_150_to_250_words'] / tot * 100, 1)}%",
                "> 250 từ (Số lượng)": r["child_over_250_words"],
                "> 250 từ (Tỷ lệ %)": f"{round(r['child_over_250_words'] / tot * 100, 1)}%",
            })
        df_dist = pd.DataFrame(dist_rows)
        df_dist.to_excel(writer, sheet_name="PhanBo_KichThuoc", index=False)

        # Sheet 4: Đề xuất & Kết luận
        recom_rows = [
            {"Mục": "Cấu hình khuyến nghị", "Nội dung": "Config A (Baseline)"},
            {"Mục": "Ngưỡng Parent", "Nội dung": "1500 ký tự (chứa trọn vẹn 1 Điều hoặc 1 cụm 2-4 Khoản liên quan trực tiếp)"},
            {"Mục": "Ngưỡng Child", "Nội dung": "256 tokens / ~200 từ (khớp max_seq_length của BKAI / BGE-M3 Dense Vector)"},
            {"Mục": "Xử lý Khoản ngắn", "Nội dung": "Tự động gom các khoản < 20 từ vào khoản liền kề để tránh chunk vụn (giảm rác trong Vector DB)"},
            {"Mục": "Xử lý Điều dài", "Nội dung": "Tách thành nhiều Parent, bắt buộc lặp lại [Điều X. Tiêu đề] và cập nhật breadcrumb Khoản X-Y"},
            {"Mục": "Đánh giá Config D", "Nội dung": "Không khuyến nghị do sinh ra quá nhiều chunk < 50 từ (làm giảm chất lượng embedding và tăng chi phí index)"},
            {"Mục": "Đánh giá Config C", "Nội dung": "Không khuyến nghị cho BGE-M3 do chunk quá dài (>250 từ) dễ bị cắt bớt (truncation) khi vector hóa"},
        ]
        df_recom = pd.DataFrame(recom_rows)
        df_recom.to_excel(writer, sheet_name="DeXuat_QuyTac", index=False)


def generate_examples_json(docs: dict[str, Any], out_path: Path):
    """
    Trích xuất các trường hợp chunking tiêu biểu ra file chunking_examples.json:
      - Case 1: Điều bình thường (vừa vặn 1 Parent, 1-N Child)
      - Case 2: Điều DÀI (vượt ngưỡng 1500 ký tự, tách thành _p1, _p2 với tiêu đề lặp lại)
      - Case 3: Khoản DÀI có nhiều Điểm (tách theo từng Điểm a, b, c)
      - Case 4: Gom các Khoản ngắn (< 20 từ)
      - Case 5: Định dạng đầy đủ payload cho Qdrant, Elasticsearch, Parent Store.
    """
    # Chạy config A trên L01 và sample_documents
    l01_doc = docs.get("L01")
    sample_doc = docs.get("sample_documents_0") or docs.get("sample_documents")

    examples: dict[str, Any] = {
        "metadata": {
            "title": "Tập hợp các trường hợp mẫu (Chunking Examples) theo quy tắc RAG",
            "version": "2.0",
            "document_contract": "docs/data_contract.md",
        },
        "examples": [],
    }

    if l01_doc:
        res = chunk_legal_document(l01_doc, CONFIGS["Config A (Baseline - Khuyến nghị)"])

        # Case 1: Điều thông thường (Điều 1)
        p_normal = next((p for p in res.parents if "art_1" in p.parent_id and "_p" not in p.parent_id), None)
        c_normal = [c for c in res.children if c.parent_id == (p_normal.parent_id if p_normal else "")]

        if p_normal:
            examples["examples"].append({
                "case_name": "Case 1: Điều thông thường (Standard Article)",
                "description": "Điều có độ dài vừa phải (<= 1500 ký tự), tạo thành 1 Parent Chunk duy nhất và các Child Chunks tương ứng.",
                "parent_chunk": p_normal.to_store_dict(),
                "child_chunks": [c.to_qdrant_payload() for c in c_normal],
            })

        # Case 2: Điều DÀI (tìm Parent có _p1 và _p2)
        p_long_1 = next((p for p in res.parents if "_p1" in p.parent_id), None)
        if p_long_1:
            base_id = p_long_1.parent_id[:-3]
            related_parents = [p for p in res.parents if p.parent_id.startswith(base_id)]
            examples["examples"].append({
                "case_name": "Case 2: Điều DÀI vượt ngưỡng (Split Long Article)",
                "description": "Điều có tổng độ dài > 1500 ký tự được tách thành nhiều Parent Chunks liên tiếp (_p1, _p2). Tiêu đề Điều được lặp lại ở đầu mỗi Parent và Breadcrumb được cập nhật chỉ rõ nhóm Khoản.",
                "parents": [p.to_store_dict() for p in related_parents[:2]],
                "child_chunks_preview": [
                    c.to_qdrant_payload()
                    for c in res.children
                    if c.parent_id in [p.parent_id for p in related_parents[:2]]
                ][:3],
            })

    # Case 3: Khoản có nhiều Điểm (từ sample_documents nếu có)
    if sample_doc:
        res_sample = chunk_legal_document(sample_doc, CONFIGS["Config A (Baseline - Khuyến nghị)"])
        p_pts = res_sample.parents[0] if res_sample.parents else None
        if p_pts:
            examples["examples"].append({
                "case_name": "Case 3: Khoản chi tiết có nhiều Điểm (Points in Clause)",
                "description": "Mỗi điểm a, b, c được gán Semantic ID chi tiết và gắn phần lời dẫn của khoản.",
                "parent_chunk": p_pts.to_store_dict(),
                "child_chunks": [c.to_qdrant_payload() for c in res_sample.children],
            })

    # Case 4: Minh họa Payload Database nạp vào 3 thành phần trong Kiến trúc
    if examples["examples"]:
        first_child = None
        for ex in examples["examples"]:
            if "child_chunks" in ex and ex["child_chunks"]:
                first_child = ex["child_chunks"][0]
                break

        if first_child:
            examples["examples"].append({
                "case_name": "Case 4: Định dạng Payload nạp vào Cơ sở dữ liệu (Database Payloads)",
                "description": "Minh họa cấu trúc JSON sẵn sàng nạp vào Vector DB (Qdrant), Sparse Index (Elasticsearch) và Parent Store.",
                "qdrant_payload": first_child,
                "elasticsearch_doc": {
                    "chunk_id": first_child.get("id"),
                    "parent_id": first_child.get("parent_id"),
                    "doc_id": first_child.get("doc_id"),
                    "title": first_child.get("title"),
                    "content": first_child.get("text"),
                    "content_segmented": first_child.get("seg_text"),
                    "breadcrumb": first_child.get("breadcrumb"),
                    "article_ref": first_child.get("article_ref"),
                },
                "parent_store_record": examples["examples"][0]["parent_chunk"],
            })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 70)
    print("🔬 CHẠY THỬ NGHIỆM ĐÁNH GIÁ CẤU HÌNH CHUNKING VÀ XUẤT BÁO CÁO")
    print("=" * 70)

    docs = load_test_documents()
    print(f"📄 Đã nạp thành công {len(docs)} tài liệu mẫu: {', '.join(docs.keys())}\n")

    results = []
    print("Đang đánh giá các cấu hình:")
    for cfg_name, cfg_params in CONFIGS.items():
        print(f"  ▶ Đang chạy: {cfg_name}...")
        r = evaluate_config(docs, cfg_name, cfg_params)
        results.append(r)
        print(f"      -> {r['total_parents']} Parents, {r['total_children']} Children (Tỷ lệ: {r['child_per_parent_ratio']})")

    # Xuất file Excel
    excel_path = BASE_DIR / "chunking_evaluation.xlsx"
    print(f"\n📊 Đang xuất bảng đánh giá: {excel_path.name}...")
    generate_evaluation_excel(results, excel_path)
    print(f"  ✅ Đã lưu {excel_path}")

    # Xuất file JSON ví dụ
    json_path = BASE_DIR / "chunking_examples.json"
    print(f"📋 Đang xuất các trường hợp mẫu: {json_path.name}...")
    generate_examples_json(docs, json_path)
    print(f"  ✅ Đã lưu {json_path}")

    print("\n" + "=" * 70)
    print("🎉 HOÀN THÀNH THỬ NGHIỆM VÀ XUẤT TẤT CẢ FILE BÁO CÁO!")
    print("=" * 70)


if __name__ == "__main__":
    main()

