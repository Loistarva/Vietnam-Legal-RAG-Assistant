"""Validate Dev retrieval outputs and export a combined CSV and metrics report."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEV = ROOT / "data" / "benchmark" / "queries_dev.json"
DEFAULT_CHUNKS = ROOT / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json"
DEFAULT_RESULTS = ROOT / "retrieval" / "results"
METHODS = ("bm25", "dense", "hybrid")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được {path}: {exc}") from exc


def evaluate(dev_path: Path, results_dir: Path, output_dir: Path,
             chunks_path: Path = DEFAULT_CHUNKS, *, dense_model: str = "BAAI/bge-m3",
             elasticsearch_index: str = "legal-child-chunks-dev") -> dict[str, dict[str, float]]:
    dev = read_json(dev_path)
    if not isinstance(dev, list) or not dev:
        raise ValueError("Dev set phải là JSON list không rỗng")
    relevant: dict[str, set[str]] = {}
    for index, item in enumerate(dev, 1):
        if not isinstance(item, dict) or not isinstance(item.get("query"), str):
            raise ValueError(f"Dev record #{index} thiếu query hợp lệ")
        ids = item.get("relevant_chunk_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(cid, str) and cid for cid in ids):
            raise ValueError(f"Dev record #{index} thiếu relevant_chunk_ids hợp lệ")
        query = item["query"].strip()
        if query in relevant:
            raise ValueError(f"Dev set có query trùng: {query}")
        relevant[query] = set(ids)

    # Use the shared loader to support the same flat/hierarchical formats as retrieval.
    from embedding.vector_store import load_chunks
    try:
        normalized_chunks = load_chunks(chunks_path)
    except ValueError as exc:
        raise ValueError(f"Corpus chunk không hợp lệ: {exc}") from exc
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in normalized_chunks}
    missing_gold_ids = {cid for ids in relevant.values() for cid in ids} - chunks_by_id.keys()
    if missing_gold_ids:
        raise ValueError(f"Dev set tham chiếu chunk không có trong corpus: {', '.join(sorted(missing_gold_ids))}")

    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_rows: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, float]] = {}
    def _normalize_dev_rows(raw_list: list[Any]) -> list[dict[str, Any]]:
        flat = []
        for item in raw_list:
            if isinstance(item, dict) and "results" in item and isinstance(item["results"], list):
                q_text = item.get("query") or item.get("query_id") or ""
                for res in item["results"]:
                    flat.append({
                        "query": q_text,
                        "chunk_id": res.get("chunk_id"),
                        "score": res.get("score") if res.get("score") is not None else res.get("rrf_score", 0.0),
                        "rank": res.get("rank"),
                    })
            else:
                flat.append(item)
        return flat

    for method in METHODS:
        raw_rows = read_json(results_dir / f"dev_{method}.json")
        if not isinstance(raw_rows, list):
            raise ValueError(f"Kết quả {method} phải là JSON list")
        rows = _normalize_dev_rows(raw_rows)
        by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"query", "chunk_id", "score", "rank"}
                    or row["query"] not in relevant or not isinstance(row["chunk_id"], str)
                    or not isinstance(row["score"], (int, float)) or not isinstance(row["rank"], int)):
                raise ValueError(f"Kết quả có schema/giá trị không hợp lệ trong dev_{method}.json: {row}")
            if row["chunk_id"] not in chunks_by_id:
                raise ValueError(f"{method} trả chunk_id không có trong corpus: {row['chunk_id']}")
            by_query[row["query"]].append(row)
            query_relevant_ids = sorted(relevant[row["query"]])
            expected_text = "\n\n".join(
                f"[{cid}] {chunks_by_id[cid]['text']}" for cid in query_relevant_ids
            )
            retrieved_chunk = chunks_by_id.get(row["chunk_id"])
            aggregate_rows.append({
                "method": method,
                "query": row["query"],
                "chunk_id": row["chunk_id"],
                "score": row["score"],
                "rank": row["rank"],
                "is_relevant": row["chunk_id"] in relevant[row["query"]],
                "chunk_text": retrieved_chunk["text"] if retrieved_chunk else "",
                "relevant_chunk_ids": ";".join(query_relevant_ids),
                "relevant_chunk_text": expected_text,
            })

        recalls, reciprocal_ranks, ndcgs, precisions = [], [], [], []
        for query, relevant_ids in relevant.items():
            ranked = sorted(by_query.get(query, []), key=lambda row: row["rank"])
            ranks = [row["rank"] for row in ranked]
            if len(ranks) != len(set(ranks)):
                raise ValueError(f"{method}: rank bị trùng trong query {query}")
            returned_ids = [row["chunk_id"] for row in ranked]
            if len(returned_ids) != len(set(returned_ids)):
                raise ValueError(f"{method}: chunk_id bị trùng trong query {query}")
            recalls.append(len(set(returned_ids[:10]) & relevant_ids) / len(relevant_ids))
            hits_at_10 = [1 if cid in relevant_ids else 0 for cid in returned_ids[:10]]
            dcg = sum(hit / math.log2(rank + 1) for rank, hit in enumerate(hits_at_10, 1))
            ideal_hits = min(len(relevant_ids), 10)
            idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
            ndcgs.append(dcg / idcg if idcg else 0.0)
            precisions.append(sum(hits_at_10) / 10)
            reciprocal_ranks.append(next((1 / rank for rank, cid in enumerate(returned_ids[:10], 1)
                                          if cid in relevant_ids), 0.0))
        metrics[method] = {
            "query_count": float(len(relevant)),
            "result_count": float(len(rows)),
            "recall_at_10": sum(recalls) / len(recalls),
            "mrr_at_10": sum(reciprocal_ranks) / len(reciprocal_ranks),
            "ndcg_at_10": sum(ndcgs) / len(ndcgs),
            "precision_at_10": sum(precisions) / len(precisions),
        }

    csv_path = output_dir / "retrieval_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "phương_pháp", "truy_vấn", "mã_chunk", "điểm_số", "thứ_hạng", "có_liên_quan",
            "nội_dung_chunk_truy_xuất", "mã_chunk_liên_quan", "nội_dung_chunk_liên_quan",
        ])
        header_map = {
            "method": "phương_pháp", "query": "truy_vấn", "chunk_id": "mã_chunk",
            "score": "điểm_số", "rank": "thứ_hạng", "is_relevant": "có_liên_quan",
            "chunk_text": "nội_dung_chunk_truy_xuất", "relevant_chunk_ids": "mã_chunk_liên_quan",
            "relevant_chunk_text": "nội_dung_chunk_liên_quan",
        }
        localized_rows = (
            {
                header_map[key]: ("Có" if value else "Không") if key == "is_relevant" else value
                for key, value in row.items()
            }
            for row in aggregate_rows
        )
        writer.writeheader()
        writer.writerows(localized_rows)

    report = [
        "# Báo cáo đánh giá truy xuất",
        "",
        f"- Ngày tạo: {date.today().isoformat()}",
        f"- Bộ Dev: `{str(dev_path.relative_to(ROOT) if dev_path.is_relative_to(ROOT) else dev_path).replace(chr(92), '/')}` ({len(relevant)} câu hỏi)",
        f"- Corpus: `{str(chunks_path.relative_to(ROOT) if chunks_path.is_relative_to(ROOT) else chunks_path).replace(chr(92), '/')}` ({len(normalized_chunks)} chunk; SHA-256 bắt đầu `{hashlib.sha256(chunks_path.read_bytes()).hexdigest()[:12]}`).",
        "- Phạm vi: bộ smoke test phát triển trên một văn bản; chưa phải đánh giá trên corpus lớn hoặc bộ kiểm thử độc lập.",
        "- CSV chứa nội dung chunk được truy xuất, cờ liên quan và nội dung/mã chunk chuẩn để đối chiếu.",
        "- Truy xuất thưa: Elasticsearch BM25 `multi_match` trên nội dung phân đoạn, đường dẫn ngữ cảnh và metadata Điều/Khoản.",
        f"- Elasticsearch index: `{elasticsearch_index}`.",
        f"- Dense model: `{dense_model}`; collection Qdrant embedded dùng cùng corpus.",
        "- Cấu hình: Top-10; Hybrid candidate depth=50; RRF k=60.",
        "- Nhãn liên quan chưa được chuyên gia pháp lý thẩm định.",
        "- Đây là một lượt chạy cố định, chưa phải khảo sát tinh chỉnh tham số. Chỉ tinh chỉnh trên Dev set; repo chưa có Test set độc lập.",
        "",
        "## Kết quả định lượng",
        "",
        "| Phương pháp | Số kết quả | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in METHODS:
        metric = metrics[method]
        report.append(f"| {method.upper()} | {int(metric['result_count'])} | {metric['recall_at_10']:.4f} | {metric['mrr_at_10']:.4f} | {metric['ndcg_at_10']:.4f} | {metric['precision_at_10']:.4f} |")
    report.extend([
        "",
        "## Cách đọc và giới hạn",
        "",
        "Các chỉ số là trung bình macro trên các câu hỏi Dev. Recall@10 đo tỷ lệ chunk liên quan được lấy về trong Top-10; MRR@10 là nghịch đảo thứ hạng của chunk liên quan đầu tiên; nDCG@10 dùng nhãn liên quan nhị phân; Precision@10 chia số chunk liên quan trong Top-10 cho 10.",
        "",
        "Bộ Dev nhỏ này chỉ gồm một văn bản và nhãn chưa được chuyên gia thẩm định. Kết quả xác nhận quy trình và hỗ trợ phát triển; không đại diện cho chất lượng trên các lĩnh vực hoặc văn bản pháp luật khác.",
        "",
        "Chi tiết từng truy vấn và chunk nằm trong `retrieval_results.csv`. Tên cột CSV được viết bằng tiếng Việt.",
        "",
    ])
    (output_dir / "retrieval_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Đã tạo CSV: {csv_path}")
    print(f"Đã tạo báo cáo: {output_dir / 'retrieval_report.md'}")
    for method, metric in metrics.items():
        print(f"{method}: Recall@10={metric['recall_at_10']:.4f}, MRR@10={metric['mrr_at_10']:.4f}, "
              f"nDCG@10={metric['ndcg_at_10']:.4f}, Precision@10={metric['precision_at_10']:.4f}")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-set", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS,
                        help="Corpus JSON used to display retrieved and expected chunk text")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--dense-model", default="BAAI/bge-m3")
    parser.add_argument("--elasticsearch-index", default="legal-child-chunks-dev")
    args = parser.parse_args()
    try:
        evaluate(args.dev_set, args.results_dir, args.output_dir, args.chunks,
                 dense_model=args.dense_model, elasticsearch_index=args.elasticsearch_index)
        return 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
