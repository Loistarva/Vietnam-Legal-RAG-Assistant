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

from retrieval.temporal import effective_period, is_effective_at, normalize_as_of_date

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEV = ROOT / "data" / "benchmark" / "queries_dev.json"
DEFAULT_CHUNKS = ROOT / "data" / "chunking_output" / "chunks.jsonl"
DEFAULT_RESULTS = ROOT / "retrieval" / "results"
METHODS = ("bm25", "dense", "hybrid")
from retrieval.settings import DEFAULT_CONFIG_PATH, load_settings
from embedding.model_registry import ModelRegistry


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được {path}: {exc}") from exc


def evaluate(dev_path: Path, results_dir: Path, output_dir: Path,
             chunks_path: Path | None = None, *,
             config_path: Path = DEFAULT_CONFIG_PATH,
             dense_model: str | None = None,
             elasticsearch_index: str | None = None,
             collection: str | None = None,
             top_k: int | None = None,
             candidate_k: int | None = None,
             rrf_k: int | None = None) -> dict[str, dict[str, float]]:
    settings = load_settings(config_path)
    if settings["hybrid"].get("fusion") != "rrf":
        raise ValueError("Evaluator hiện chỉ hỗ trợ kết quả được tạo với fusion=rrf")
    if chunks_path is None:
        chunks_path = Path(settings["retrieval"]["corpus_path"])
        if not chunks_path.is_absolute():
            chunks_path = ROOT / chunks_path
    else:
        chunks_path = Path(chunks_path)
        if not chunks_path.is_absolute():
            chunks_path = ROOT / chunks_path
    registry = ModelRegistry(settings)
    selected_model = dense_model or settings["dense"]["model"]
    model_spec = registry.get_model(selected_model)
    metric_k = top_k if top_k is not None else settings["retrieval"]["result_top_k"]
    candidate_depth = candidate_k if candidate_k is not None else settings["retrieval"]["retrieval_top_k"]
    fusion_k = rrf_k if rrf_k is not None else settings["hybrid"]["rrf_k"]
    selected_index = elasticsearch_index or settings["bm25"]["index"]
    selected_collection = collection or settings["dense"]["collection"]
    if metric_k < 1 or candidate_depth < metric_k or fusion_k < 1:
        raise ValueError("Cấu hình đánh giá cần top_k >= 1, candidate_k >= top_k và rrf_k >= 1")
    expected_run_config = {
        "top_k": metric_k,
        "candidate_k": candidate_depth,
        "rrf_k": fusion_k,
        "dense_model": selected_model,
        "dimension": model_spec["dimension"],
        "collection": selected_collection,
        "elasticsearch_index": selected_index,
        "fusion": settings["hybrid"]["fusion"],
    }
    dev = read_json(dev_path)
    if not isinstance(dev, list) or not dev:
        raise ValueError("Dev set phải là JSON list không rỗng")
    relevant: dict[str, set[str]] = {}
    query_text_by_id: dict[str, str] = {}
    legacy_query_ids: dict[str, str] = {}
    query_dates: dict[str, str] = {}
    for index, item in enumerate(dev, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Dev record #{index} phải là object")
        query_text = item.get("query") or item.get("question")
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError(f"Dev record #{index} thiếu query/question hợp lệ")
        ids = item.get("relevant_chunk_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(cid, str) and cid for cid in ids):
            raise ValueError(f"Dev record #{index} thiếu relevant_chunk_ids hợp lệ")
        query_text = query_text.strip()
        query_id = item.get("id") or item.get("query_id")
        if query_id is None:
            if query_text in legacy_query_ids:
                raise ValueError(
                    f"Dev có câu hỏi trùng nội dung nhưng thiếu id ở record #{index}; "
                    "hãy thêm id/query_id để evaluator phân biệt các nhãn"
                )
            query_id = f"legacy:{index}:{query_text}"
            legacy_query_ids[query_text] = query_id
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"Dev record #{index} có id/query_id không hợp lệ")
        query_id = query_id.strip()
        if query_id in relevant:
            raise ValueError(f"Dev set có id/query_id trùng: {query_id}")
        relevant[query_id] = set(ids)
        query_text_by_id[query_id] = query_text
        query_dates[query_id] = normalize_as_of_date(item.get("as_of_date"))
    # Use the shared loader to support the same flat/hierarchical formats as retrieval.
    from embedding.vector_store import load_chunks
    try:
        normalized_chunks = load_chunks(chunks_path)
    except ValueError as exc:
        raise ValueError(f"Corpus chunk không hợp lệ: {exc}") from exc
    for chunk in normalized_chunks:
        if not chunk.get("text"):
            chunk["text"] = next((
                str(chunk.get(field)).strip()
                for field in ("chunk_text", "content")
                if isinstance(chunk.get(field), str) and chunk.get(field).strip()
            ), "")
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in normalized_chunks}
    corpus_sha256 = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
    expected_run_config["corpus_sha256"] = corpus_sha256
    missing_gold_ids = {cid for ids in relevant.values() for cid in ids} - chunks_by_id.keys()
    if missing_gold_ids:
        raise ValueError(f"Dev set tham chiếu chunk không có trong corpus: {', '.join(sorted(missing_gold_ids))}")

    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_rows: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, float]] = {}
    def _normalize_dev_rows(raw_list: list[Any]) -> list[dict[str, Any]]:
        flat = []
        for item in raw_list:
            if not (isinstance(item, dict) and "results" in item and isinstance(item["results"], list)):
                raise ValueError("Kết quả truy xuất phải tuân thủ RetrievalEnvelope schema (chứa 'results')")
            query_id = item.get("query_id") or item.get("id")
            q_text = item.get("query") or item.get("question") or ""
            if not isinstance(query_id, str) or query_id not in relevant:
                raise ValueError(f"Kết quả {item.get('retriever')} thiếu query_id hợp lệ: {query_id!r}")
            if not isinstance(q_text, str) or q_text.strip() != query_text_by_id[query_id]:
                raise ValueError(f"Query text trong kết quả không khớp Dev query_id={query_id}")
            run_config = item.get("config")
            if not isinstance(run_config, dict):
                raise ValueError("RetrievalEnvelope thiếu config thực tế của lần chạy")
            if item.get("top_k") != metric_k:
                raise ValueError(
                    f"top_k trong RetrievalEnvelope ({item.get('top_k')!r}) không khớp cấu hình đánh giá ({metric_k})"
                )
            mismatched = {
                key: (run_config.get(key), expected)
                for key, expected in expected_run_config.items()
                if run_config.get(key) != expected
            }
            if mismatched:
                details = "; ".join(
                    f"{key}: kết quả={actual!r}, evaluator={expected!r}"
                    for key, (actual, expected) in mismatched.items()
                )
                raise ValueError(f"Cấu hình kết quả {item.get('retriever')} không khớp shared config: {details}")
            config = item.get("config")
            as_of_date = normalize_as_of_date(
                config.get("as_of_date") or query_dates.get(query_id)
            )
            for res in item["results"]:
                flat.append({
                    "query_id": query_id,
                    "query": q_text,
                    "chunk_id": res.get("chunk_id"),
                    "score": res.get("score") if res.get("score") is not None else res.get("rrf_score", 0.0),
                    "rank": res.get("rank"),
                    "as_of_date": as_of_date,
                })
        return flat

    for method in METHODS:
        raw_rows = read_json(results_dir / f"dev_{method}.json")
        if not isinstance(raw_rows, list):
            raise ValueError(f"Kết quả {method} phải là JSON list")
        rows = _normalize_dev_rows(raw_rows)
        by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {
                    "query_id", "query", "chunk_id", "score", "rank", "as_of_date"
            } or row["query_id"] not in relevant or not isinstance(row["chunk_id"], str)
                    or not isinstance(row["score"], (int, float)) or not isinstance(row["rank"], int)):
                raise ValueError(f"Kết quả có schema/giá trị không hợp lệ trong dev_{method}.json: {row}")
            if row["chunk_id"] not in chunks_by_id:
                raise ValueError(f"{method} trả chunk_id không có trong corpus: {row['chunk_id']}")
            if row["query"].strip() != query_text_by_id[row["query_id"]]:
                raise ValueError(f"Query text trong kết quả không khớp Dev query_id={row['query_id']}")
            by_query[row["query_id"]].append(row)
            query_relevant_ids = sorted(relevant[row["query_id"]])
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
                "is_relevant": row["chunk_id"] in relevant[row["query_id"]],
                "chunk_text": retrieved_chunk["text"] if retrieved_chunk else "",
                "relevant_chunk_ids": ";".join(query_relevant_ids),
                "relevant_chunk_text": expected_text,
            })

        recalls, reciprocal_ranks, ndcgs, precisions = [], [], [], []
        temporal_checks = temporal_violations = temporal_metadata_missing = 0
        for row in rows:
            chunk = chunks_by_id[row["chunk_id"]]
            effective_from, effective_to = effective_period(chunk)
            if effective_from is None and effective_to is None:
                temporal_metadata_missing += 1
                continue
            temporal_checks += 1
            if not is_effective_at(chunk, row["as_of_date"]):
                temporal_violations += 1
        for query_id, relevant_ids in relevant.items():
            ranked = sorted(by_query.get(query_id, []), key=lambda row: row["rank"])
            ranks = [row["rank"] for row in ranked]
            if len(ranks) != len(set(ranks)):
                raise ValueError(f"{method}: rank bị trùng trong query_id {query_id}")
            returned_ids = [row["chunk_id"] for row in ranked]
            if len(returned_ids) != len(set(returned_ids)):
                raise ValueError(f"{method}: chunk_id bị trùng trong query_id {query_id}")
            recalls.append(len(set(returned_ids[:metric_k]) & relevant_ids) / len(relevant_ids))
            hits_at_k = [1 if cid in relevant_ids else 0 for cid in returned_ids[:metric_k]]
            dcg = sum(hit / math.log2(rank + 1) for rank, hit in enumerate(hits_at_k, 1))
            ideal_hits = min(len(relevant_ids), metric_k)
            idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
            ndcgs.append(dcg / idcg if idcg else 0.0)
            precisions.append(sum(hits_at_k) / metric_k)
            reciprocal_ranks.append(next((1 / rank for rank, cid in enumerate(returned_ids[:metric_k], 1)
                                          if cid in relevant_ids), 0.0))
        suffix = str(metric_k)
        metrics[method] = {
            "query_count": float(len(relevant)),
            "result_count": float(len(rows)),
            f"recall_at_{suffix}": sum(recalls) / len(recalls),
            f"mrr_at_{suffix}": sum(reciprocal_ranks) / len(reciprocal_ranks),
            f"ndcg_at_{suffix}": sum(ndcgs) / len(ndcgs),
            f"precision_at_{suffix}": sum(precisions) / len(precisions),
            "temporal_violation_rate": (temporal_violations / temporal_checks
                                         if temporal_checks else 0.0),
            "temporal_violation_count": float(temporal_violations),
            "temporal_checked_count": float(temporal_checks),
            "temporal_metadata_missing_count": float(temporal_metadata_missing),
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
        f"- Corpus: `{str(chunks_path.relative_to(ROOT) if chunks_path.is_relative_to(ROOT) else chunks_path).replace(chr(92), '/')}` ({len(normalized_chunks)} chunk; SHA-256 bắt đầu `{corpus_sha256[:12]}`).",
        "- Phạm vi: bộ smoke test phát triển trên một văn bản; chưa phải đánh giá trên corpus lớn hoặc bộ kiểm thử độc lập.",
        "- CSV chứa nội dung chunk được truy xuất, cờ liên quan và nội dung/mã chunk chuẩn để đối chiếu.",
        "- Truy xuất thưa: Elasticsearch BM25 `multi_match` trên nội dung phân đoạn, đường dẫn ngữ cảnh và metadata Điều/Khoản.",
        f"- Elasticsearch index: `{selected_index}`.",
        f"- Dense model: `{selected_model}` (dimension={model_spec['dimension']}); Qdrant collection: `{selected_collection}`.",
        f"- Cấu hình thực tế: Top-{metric_k}; candidate depth={candidate_depth}; fusion={settings['hybrid']['fusion'].upper()}; RRF k={fusion_k}.",
        "- Nhãn liên quan chưa được chuyên gia pháp lý thẩm định.",
        "- Đây là một lượt chạy cố định, chưa phải khảo sát tinh chỉnh tham số. Chỉ tinh chỉnh trên Dev set; repo chưa có Test set độc lập.",
        "",
        "## Kết quả định lượng",
        "",
        f"| Phương pháp | Số kết quả | Recall@{metric_k} | MRR@{metric_k} | nDCG@{metric_k} | Precision@{metric_k} |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in METHODS:
        metric = metrics[method]
        report.append(f"| {method.upper()} | {int(metric['result_count'])} | {metric[f'recall_at_{metric_k}']:.4f} | {metric[f'mrr_at_{metric_k}']:.4f} | {metric[f'ndcg_at_{metric_k}']:.4f} | {metric[f'precision_at_{metric_k}']:.4f} |")
    report.extend([
        "",
        "| Phương pháp | Temporal Violation Rate | Số vi phạm / đã kiểm tra | Chunk thiếu metadata ngày |",
        "| --- | ---: | ---: | ---: |",
    ])
    for method in METHODS:
        metric = metrics[method]
        report.append(
            f"| {method.upper()} | {metric['temporal_violation_rate']:.4f} | "
            f"{int(metric['temporal_violation_count'])} / {int(metric['temporal_checked_count'])} | "
            f"{int(metric['temporal_metadata_missing_count'])} |"
        )
    report.extend([
        "",
        "## Cách đọc và giới hạn",
        "",
        f"Các chỉ số là trung bình macro trên các câu hỏi Dev. Recall@{metric_k} đo tỷ lệ chunk liên quan được lấy về trong Top-{metric_k}; MRR@{metric_k} là nghịch đảo thứ hạng của chunk liên quan đầu tiên; nDCG@{metric_k} dùng nhãn liên quan nhị phân; Precision@{metric_k} chia số chunk liên quan trong Top-{metric_k} cho {metric_k}.",
        "Temporal Violation Rate chỉ tính trên kết quả có ít nhất một mốc hiệu lực; chunk thiếu cả effective_from và effective_to được đếm riêng, không mặc định xem là hợp lệ.",
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
        print(f"{method}: Recall@{metric_k}={metric[f'recall_at_{metric_k}']:.4f}, MRR@{metric_k}={metric[f'mrr_at_{metric_k}']:.4f}, "
              f"nDCG@{metric_k}={metric[f'ndcg_at_{metric_k}']:.4f}, Precision@{metric_k}={metric[f'precision_at_{metric_k}']:.4f}, "
              f"TemporalViolationRate={metric['temporal_violation_rate']:.4f}")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--dev-set", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--chunks", type=Path, default=None,
                        help="Corpus JSON used to display retrieved and expected chunk text")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--dense-model", default=None)
    parser.add_argument("--elasticsearch-index", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--candidate-k", type=int, default=None)
    parser.add_argument("--rrf-k", type=int, default=None)
    args = parser.parse_args()
    try:
        evaluate(args.dev_set, args.results_dir, args.output_dir, args.chunks,
                 config_path=args.config, dense_model=args.dense_model,
                 elasticsearch_index=args.elasticsearch_index, collection=args.collection,
                 top_k=args.top_k, candidate_k=args.candidate_k, rrf_k=args.rrf_k)
        return 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
