"""Compare isolated chunk-size variants on Dev using mapped proposal chunk labels."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_envelopes(path: Path, expected_query_ids: set[str], candidate_k: int) -> dict[str, dict[str, Any]]:
    rows = read_json(path)
    if not isinstance(rows, list):
        raise ValueError(f"{path} phải là JSON list")
    result = {}
    for envelope in rows:
        qid = envelope.get("query_id")
        if qid not in expected_query_ids:
            raise ValueError(f"Có query ngoài Dev trong {path}: {qid}")
        if qid in result:
            raise ValueError(f"query_id trùng trong {path}: {qid}")
        hits = sorted(envelope.get("results") or [], key=lambda row: row.get("rank", 0))
        if len(hits) < candidate_k or [hit.get("rank") for hit in hits] != list(range(1, len(hits) + 1)):
            raise ValueError(f"Candidate list không đủ hoặc thứ hạng sai ở {qid} trong {path}")
        result[qid] = {**envelope, "results": hits}
    if set(result) != expected_query_ids:
        raise ValueError(f"{path} thiếu query: {sorted(expected_query_ids - set(result))[:5]}")
    return result


def evaluate(
    rankings: dict[str, list[dict[str, Any]]], labels: dict[str, set[str]], top_k: int,
) -> tuple[dict[str, float | int], list[dict[str, Any]]]:
    recall_values = []
    reciprocal_ranks = []
    per_query = []
    for qid, relevant in labels.items():
        ids = [row["chunk_id"] for row in rankings[qid][:top_k]]
        hits = list(dict.fromkeys(cid for cid in ids if cid in relevant))
        recall = len(hits) / len(relevant)
        reciprocal_rank = 1 / (ids.index(hits[0]) + 1) if hits else 0.0
        recall_values.append(recall)
        reciprocal_ranks.append(reciprocal_rank)
        per_query.append({
            "query_id": qid,
            "retrieved_chunk_ids": ids,
            "hit_chunk_ids": hits,
            "relevant_chunk_count": len(relevant),
            "recall_at_5": recall,
            "reciprocal_rank_at_5": reciprocal_rank,
        })
    return ({
        "queries_scored": len(labels),
        "recall_at_5": statistics.fmean(recall_values) if recall_values else 0.0,
        "mrr_at_5": statistics.fmean(reciprocal_ranks) if reciprocal_ranks else 0.0,
    }, per_query)


def percentile(values: list[float], p: float) -> float | None:
    return values[max(0, math.ceil(p * len(values)) - 1)] if values else None


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dev: đánh giá kích thước chunk",
        "",
        f"- Ngày chạy: {payload['run_date']}",
        f"- Số query Dev có nhãn chunk đối chiếu được: {payload['queries_scored']}",
        f"- Nguồn nhãn: `{payload['labels_source']}`; Test không được dùng.",
        f"- Dense model: `{payload['retrieval_config']['dense_model']}`; RRF k={payload['retrieval_config']['rrf_k']}; candidate Top-{payload['retrieval_config']['candidate_k']}.",
        "- Với mỗi chunking, trọng số được chọn trên Dev từ cùng lưới 21 tỉ lệ BM25/Dense, bước 5%.",
        "- Fallback overlap 40 từ được giữ cố định trong cả bốn phương án; chỉ áp dụng cho nhánh tách fallback window, không được tune riêng.",
        "- Nhãn B/C/E được chuyển theo đoạn text liên tiếp trong cùng `clause_id`; không sửa file proposal gốc.",
        "- Latency của E được đo lại riêng trên Dev ở đúng trọng số đã chọn 0,35/0,65. Latency A/B/C lấy từ lượt truy xuất trước ở 0,65/0,35. Metric Hybrid từng phương án được tính lại offline trên cùng Top-50 BM25/Dense bằng trọng số Dev đã chọn.",
        "",
        "## Kết quả",
        "",
        "| Chunking | Parent chars | Child tokens / words | Số chunks | BM25/Dense | BM25 Recall@5 | Dense Recall@5 | Hybrid Recall@5 | Hybrid MRR@5 | Embed >256 | Latency retrieval (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant, row in payload["variants"].items():
        cfg = row["chunking_config"]
        metrics = row["metrics"]
        weights = row["selected_fusion_weights"]
        audit = row["embedding_tokens"]
        lines.append(
            f"| {variant} | {cfg['parent_max_chars']} | {cfg['child_max_tokens']} / {cfg['child_max_units']} | "
            f"{row['num_chunks']} | {weights['bm25']:.2f} / {weights['dense']:.2f} | {metrics['bm25']['recall_at_5']:.4f} | "
            f"{metrics['dense']['recall_at_5']:.4f} | {metrics['hybrid']['recall_at_5']:.4f} | "
            f"{metrics['hybrid']['mrr_at_5']:.4f} | {audit['over_limit_chunks']}/{audit['chunks']} "
            f"({audit['over_limit_fraction']:.2%}) | {row['latency_ms']['mean']:.1f} |"
        )
    selected = payload["selected_chunking"]
    lines.extend([
        "",
        f"Theo tiêu chí Recall@5 (MRR@5 dùng để phân xử khi bằng nhau), cấu hình Dev được chọn là **{selected['variant']}** "
        f"với BM25/Dense={selected['bm25_weight']:.2f}/{selected['dense_weight']:.2f}: "
        f"Recall@5={selected['recall_at_5']:.4f}, MRR@5={selected['mrr_at_5']:.4f}.",
        "",
        "## Cách đọc kết quả",
        "",
        "Config A được sinh lại và khớp toàn bộ ID cùng text với corpus/index hiện hành. Với B/C/E, một nhãn chunk gốc được ánh xạ sang chunk mới nếu text của chunk mới là đoạn liên tiếp nằm trong chunk gốc hoặc chunk mới chứa toàn bộ đoạn của chunk gốc; điều kiện clause_id phải trùng. Các nhãn `version_*` không thuộc corpus chunk nên bị loại khỏi metric.",
        "",
        f"Tokenizer `{payload['embedding_token_audit']['model']}` có giới hạn {payload['embedding_token_audit']['sequence_limit']} token. Chunk dài hơn giới hạn sẽ bị cắt khi embed; số lượng bị ảnh hưởng có trong bảng. Nhãn proposal còn provisional; đây là tuning trên Dev, không phải đánh giá pháp lý độc lập. Kích thước danh sách relevant thay đổi khi chunk bị tách hoặc gộp.",
        "",
        "Test đã được chạy trước lượt tuning này. Báo cáo Test cũ phản ánh Config A cùng RRF 1:1; không dùng điểm Test để chọn cấu hình mới và không chạy lại tập Test đó.",
        "",
        "## Tệp tái lập",
        "",
        f"- Bản JSON đầy đủ: `{payload['json_file']}`",
        f"- Ánh xạ nhãn theo chunking: `{payload['label_mapping_file']}`",
        "- Corpus/index riêng A, B, C, E: thư mục cùng tên trong `chunking_variants/`.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "retrieval/results/dev_tuning/chunking_variants")
    parser.add_argument("--labels-map", type=Path, default=ROOT / "retrieval/results/dev_tuning/chunking_variants/label_mapping.json")
    parser.add_argument("--token-audit", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants/embedding_token_length_audit.json")
    parser.add_argument("--selected-latency", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants/E/dev_latency.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants/dev_chunking_evaluation.json")
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rrf-k", type=int, default=60)
    args = parser.parse_args()
    try:
        mapping = read_json(args.labels_map)
        token_audit = read_json(args.token_audit)
        selected_latency = read_json(args.selected_latency) if args.selected_latency.is_file() else None
        results: dict[str, Any] = {}
        for variant in ("A", "B", "C", "E"):
            config_dir = args.root / variant
            labels_info = mapping["configs"][variant]
            labels = {qid: set(ids) for qid, ids in labels_info["query_labels"].items()}
            if not labels:
                raise ValueError(f"Không có nhãn chunk ánh xạ được cho cấu hình {variant}")
            expected_ids = {row["query_id"] for row in labels_info["query_details"]}
            bm25 = read_envelopes(config_dir / "results/dev_bm25.json", expected_ids, args.candidate_k)
            dense = read_envelopes(config_dir / "results/dev_dense.json", expected_ids, args.candidate_k)
            hybrid = read_envelopes(config_dir / "results/dev_hybrid.json", expected_ids, args.candidate_k)
            rankings = {
                "bm25": {qid: bm25[qid]["results"] for qid in expected_ids},
                "dense": {qid: dense[qid]["results"] for qid in expected_ids},
            }
            method_metrics: dict[str, Any] = {}
            method_per_query: dict[str, Any] = {}
            for method in ("bm25", "dense"):
                metrics, per_query = evaluate(rankings[method], labels, args.top_k)
                method_metrics[method] = metrics
                method_per_query[method] = per_query
            weight_sweep = read_json(config_dir / "rrf_weight_sweep.json")
            best_config = weight_sweep["selected_config"]
            best_row = next(
                row for row in weight_sweep["weight_sweep"]
                if row["bm25_weight"] == best_config["bm25_weight"]
                and row["dense_weight"] == best_config["dense_weight"]
            )
            method_metrics["hybrid"] = {
                "queries_scored": best_row["queries_scored"],
                "recall_at_5": best_config["recall_at_5"],
                "mrr_at_5": best_config["mrr_at_5"],
            }
            method_per_query["hybrid"] = best_row["per_query"]
            if variant == "E" and selected_latency:
                latency_rows = {row["query_id"]: row for row in selected_latency["per_query"]}
                if set(latency_rows) != expected_ids:
                    raise ValueError("Tệp latency E phải có đúng tập query Dev của retrieval output")
                latencies = sorted(float(latency_rows[qid]["hybrid_latency_ms"]) for qid in expected_ids)
                measured_config = selected_latency.get("config") or {}
            else:
                latencies = sorted(float(hybrid[qid].get("latency_ms", 0.0)) for qid in expected_ids)
                measured_config = hybrid[next(iter(expected_ids))].get("config") or {}
            measured_weights = {
                "bm25": measured_config.get("bm25_weight", 1.0),
                "dense": measured_config.get("dense_weight", 1.0),
            }
            report = read_json(config_dir / "variant_report.json")
            results[variant] = {
                "chunking_config": report["chunking_config"],
                "num_chunks": report["num_children"],
                "num_parents": report["num_parents"],
                "queries_scored": len(labels),
                "queries_excluded_invalid_base_ids": labels_info["queries_excluded_invalid_base_ids"],
                "queries_excluded_unmapped_variant_spans": labels_info["queries_excluded_unmapped_variant_spans"],
                "selected_fusion_weights": {
                    "bm25": best_config["bm25_weight"],
                    "dense": best_config["dense_weight"],
                },
                "metrics": method_metrics,
                "embedding_tokens": token_audit["variants"][variant],
                "latency_ms": {
                    "mean": statistics.fmean(latencies) if latencies else 0.0,
                    "median": statistics.median(latencies) if latencies else 0.0,
                    "p95": percentile(latencies, 0.95),
                    "measured_weights": measured_weights,
                    "measured_path": "BM25 + Dense + weighted RRF song song trong cùng một lần retrieve",
                },
                "retrieval_files": {
                    method: str((config_dir / f"results/dev_{method}.json").relative_to(ROOT))
                    for method in ("bm25", "dense", "hybrid")
                },
                "per_query": method_per_query,
            }

        best = max(results, key=lambda name: (
            results[name]["metrics"]["hybrid"]["recall_at_5"],
            results[name]["metrics"]["hybrid"]["mrr_at_5"],
            -results[name]["num_chunks"],
        ))
        payload = {
            "run_date": __import__("datetime").date.today().isoformat(),
            "labels_source": mapping["labels_source"],
            "embedding_token_audit": token_audit,
            "label_mapping_file": str(args.labels_map.relative_to(ROOT)) if args.labels_map.is_relative_to(ROOT) else str(args.labels_map),
            "json_file": str(args.output.relative_to(ROOT)) if args.output.is_relative_to(ROOT) else str(args.output),
            "queries_scored": min(results[name]["queries_scored"] for name in results),
            "retrieval_config": {
                "candidate_k": args.candidate_k,
                "top_k": args.top_k,
                "rrf_k": args.rrf_k,
                "fallback_overlap_words": 40,
                "dense_model": "bkai-foundation-models/vietnamese-bi-encoder",
            },
            "selected_chunking": {
                "variant": best,
                "bm25_weight": results[best]["selected_fusion_weights"]["bm25"],
                "dense_weight": results[best]["selected_fusion_weights"]["dense"],
                "recall_at_5": results[best]["metrics"]["hybrid"]["recall_at_5"],
                "mrr_at_5": results[best]["metrics"]["hybrid"]["mrr_at_5"],
            },
            "variants": results,
            "notes": [
                "Chỉ query split=dev; không dùng Test hoặc ground_truth.json.",
                "Config A chunk ID và text khớp 2.011/2.011 với corpus hiện hành.",
                "Config B/C/E dùng ánh xạ text-span sang chunk mới trong cùng clause_id.",
                "Nhãn proposal chưa được xác nhận pháp lý đầy đủ; các metric là exploratory.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path = args.output.with_suffix(".md")
        write_report(report_path, payload)
        for variant, row in results.items():
            print(
                f"{variant}: chunks={row['num_chunks']}; "
                f"weights={row['selected_fusion_weights']['bm25']:.2f}/{row['selected_fusion_weights']['dense']:.2f}; "
                f"Hybrid Recall@5={row['metrics']['hybrid']['recall_at_5']:.4f}; "
                f"MRR@5={row['metrics']['hybrid']['mrr_at_5']:.4f}; "
                f"latency_mean={row['latency_ms']['mean']:.1f} ms"
            )
        selected = payload["selected_chunking"]
        print(f"Selected chunking={best}; weights={selected['bm25_weight']:.2f}/{selected['dense_weight']:.2f}; "
              f"JSON={args.output}; report={report_path}")
        return 0
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
