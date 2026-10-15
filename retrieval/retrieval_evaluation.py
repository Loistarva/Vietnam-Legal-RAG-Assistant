"""Validate Dev retrieval outputs and export a combined CSV and metrics report."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEV = ROOT / "embedding" / "data" / "dev_queries.json"
DEFAULT_CHUNKS = ROOT / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json"
DEFAULT_RESULTS = ROOT / "retrieval" / "results"
METHODS = ("bm25", "dense", "hybrid")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được {path}: {exc}") from exc


def evaluate(dev_path: Path, results_dir: Path, output_dir: Path,
             chunks_path: Path = DEFAULT_CHUNKS) -> dict[str, dict[str, float]]:
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
    for method in METHODS:
        rows = read_json(results_dir / f"dev_{method}.json")
        if not isinstance(rows, list):
            raise ValueError(f"Kết quả {method} phải là JSON list")
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

        recalls, reciprocal_ranks = [], []
        for query, relevant_ids in relevant.items():
            ranked = sorted(by_query.get(query, []), key=lambda row: row["rank"])
            ranks = [row["rank"] for row in ranked]
            if len(ranks) != len(set(ranks)):
                raise ValueError(f"{method}: rank bị trùng trong query {query}")
            returned_ids = [row["chunk_id"] for row in ranked]
            if len(returned_ids) != len(set(returned_ids)):
                raise ValueError(f"{method}: chunk_id bị trùng trong query {query}")
            recalls.append(len(set(returned_ids[:10]) & relevant_ids) / len(relevant_ids))
            reciprocal_ranks.append(next((1 / rank for rank, cid in enumerate(returned_ids[:10], 1)
                                          if cid in relevant_ids), 0.0))
        metrics[method] = {
            "query_count": float(len(relevant)),
            "result_count": float(len(rows)),
            "recall_at_10": sum(recalls) / len(recalls),
            "mrr_at_10": sum(reciprocal_ranks) / len(reciprocal_ranks),
        }

    csv_path = output_dir / "retrieval_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "method", "query", "chunk_id", "score", "rank", "is_relevant",
            "chunk_text", "relevant_chunk_ids", "relevant_chunk_text",
        ])
        writer.writeheader()
        writer.writerows(aggregate_rows)

    report = [
        "# Retrieval evaluation report",
        "",
        f"- Ngày tạo: {date.today().isoformat()}",
        f"- Dev set: `{dev_path.relative_to(ROOT).as_posix() if dev_path.is_relative_to(ROOT) else dev_path}` ({len(relevant)} câu hỏi)",
        "- Corpus: `embedding/data/han_gia_dinh_smoke_chunks.json` (321 chunks; fixture SHA-256 bắt đầu `f1d9af4423dd`).",
        "- CSV includes retrieved chunk text, relevance flag, and expected relevant chunk IDs/text for direct comparison.",
        "- Dense model: BKAI Vietnamese Bi-Encoder; Qdrant local collection khớp fixture.",
        "- Cấu hình truy xuất: Top-10; Hybrid candidate depth=50; RRF k=60.",
        "- Nhãn relevant được đối chiếu với nội dung chunk nhưng chưa được chuyên gia pháp lý thẩm định.",
        "- Cấu hình hiện tại là một lượt chạy cố định, chưa phải sweep tuning. Tinh chỉnh tham số chỉ trên Dev set; repo hiện chưa có Test set tách biệt.",
        "",
        "## Kết quả",
        "",
        "| Phương pháp | Số kết quả | Recall@10 | MRR@10 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for method in METHODS:
        metric = metrics[method]
        report.append(f"| {method.upper()} | {int(metric['result_count'])} | {metric['recall_at_10']:.4f} | {metric['mrr_at_10']:.4f} |")
    report.extend([
        "",
        "## Diễn giải và giới hạn",
        "",
        "Các chỉ số là macro average trên 14 câu hỏi. Recall@10 là tỷ lệ chunk có nhãn relevant được lấy về trong 10 kết quả; MRR@10 là nghịch đảo hạng của chunk relevant đầu tiên, hoặc 0 nếu không có chunk relevant trong Top-10.",
        "",
        "Đây là bộ Dev nhỏ, được tạo từ một văn bản và nhãn chưa qua đánh giá chuyên gia. Kết quả chỉ xác nhận quy trình và hỗ trợ phát triển; không đại diện cho chất lượng trên các lĩnh vực pháp luật hoặc văn bản khác.",
        "",
        "Chi tiết từng truy vấn và chunk nằm trong `retrieval_results.csv`.",
        "",
    ])
    (output_dir / "retrieval_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"CSV: {csv_path}")
    print(f"Report: {output_dir / 'retrieval_report.md'}")
    for method, metric in metrics.items():
        print(f"{method}: Recall@10={metric['recall_at_10']:.4f}, MRR@10={metric['mrr_at_10']:.4f}")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-set", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS,
                        help="Corpus JSON used to display retrieved and expected chunk text")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    try:
        evaluate(args.dev_set, args.results_dir, args.output_dir, args.chunks)
        return 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
