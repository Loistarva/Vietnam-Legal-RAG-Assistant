"""Sweep weighted RRF settings using Dev queries and gold_id_proposals_300 only."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.rrf import reciprocal_rank_fusion  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_chunks(path: Path) -> set[str]:
    ids: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        chunk_id = row.get("chunk_id") or row.get("id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError(f"Chunk ở dòng {line_no} thiếu chunk_id")
        if chunk_id in ids:
            raise ValueError(f"chunk_id trùng trong corpus: {chunk_id}")
        ids.add(chunk_id)
    return ids


def read_envelopes(path: Path, query_ids: set[str], *, expected_candidates: int) -> dict[str, dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"{path} phải là JSON list RetrievalEnvelope")
    result: dict[str, dict[str, Any]] = {}
    for envelope in data:
        query_id = envelope.get("query_id")
        if query_id not in query_ids:
            raise ValueError(f"Kết quả ngoài Dev hoặc query_id lạ trong {path}: {query_id}")
        if query_id in result:
            raise ValueError(f"query_id trùng trong {path}: {query_id}")
        hits = envelope.get("results")
        if not isinstance(hits, list) or len(hits) < expected_candidates:
            raise ValueError(f"{query_id}: cần ít nhất {expected_candidates} kết quả trong {path}")
        ranked = sorted(hits, key=lambda row: row.get("rank", 0))
        if [row.get("rank") for row in ranked] != list(range(1, len(ranked) + 1)):
            raise ValueError(f"Thứ hạng trong {path} không liên tục cho {query_id}")
        if len({row.get("chunk_id") for row in ranked}) != len(ranked):
            raise ValueError(f"chunk_id trùng trong {path} cho {query_id}")
        result[query_id] = {**envelope, "results": ranked}
    if set(result) != query_ids:
        missing = sorted(query_ids - set(result))
        raise ValueError(f"{path} thiếu {len(missing)} query Dev, ví dụ {missing[:5]}")
    return result


def score_rankings(
    rankings: dict[str, list[dict[str, Any]]],
    labels: dict[str, set[str]],
    top_k: int,
) -> tuple[dict[str, float | int], list[dict[str, Any]]]:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    per_query: list[dict[str, Any]] = []
    for query_id, relevant in labels.items():
        ranked_ids = [row["chunk_id"] for row in rankings[query_id][:top_k]]
        hits = [chunk_id for chunk_id in ranked_ids if chunk_id in relevant]
        recall = len(set(hits)) / len(relevant)
        reciprocal_rank = 1.0 / (ranked_ids.index(hits[0]) + 1) if hits else 0.0
        recalls.append(recall)
        reciprocal_ranks.append(reciprocal_rank)
        per_query.append({
            "query_id": query_id,
            "retrieved_chunk_ids": ranked_ids,
            "hit_chunk_ids": list(dict.fromkeys(hits)),
            "relevant_chunk_count": len(relevant),
            "recall_at_5": recall,
            "reciprocal_rank_at_5": reciprocal_rank,
        })
    return ({
        "queries_scored": len(labels),
        "recall_at_5": sum(recalls) / len(recalls) if recalls else 0.0,
        "mrr_at_5": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0,
    }, per_query)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    return values[max(0, math.ceil(p * len(values)) - 1)]


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dev: đánh giá trọng số Reciprocal Rank Fusion",
        "",
        f"- Ngày chạy: {payload['run_date']}",
        f"- Truy vấn Dev: {payload['data_scope']['dev_queries']}",
        f"- Truy vấn có nhãn được chấm: {payload['data_scope']['queries_scored']}",
        f"- Loại khỏi metric chunk-level: {payload['data_scope']['queries_excluded_unmapped_chunk_ids']} query có nhãn `version_*` không tồn tại trong `chunks.jsonl`.",
        f"- Nhãn: `{payload['labels_file']}`; không nạp hàng thuộc Test.",
        (f"- File ánh xạ nhãn theo biến thể: `{payload['label_mapping_file']}` ({payload['label_mapping_variant']})."
         if payload.get("label_mapping_file") else ""),
        f"- Corpus: `{payload['chunks_file']}` ({payload['corpus_chunk_count']} chunks).",
        f"- Candidate depth: {payload['config']['candidate_k']}; RRF k: {payload['config']['rrf_k']}.",
        "- Đơn vị liên quan: `chunk_id`; Recall@5 là số nhãn chunk tìm thấy trong Top-5 chia tổng nhãn của query.",
        "",
        "## Baseline và lựa chọn",
        "",
        "| Cấu hình | BM25 / Dense | Recall@5 | MRR@5 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, item in payload["baselines"].items():
        weights = item.get("weights")
        ratio = f"{weights['bm25']:.2f} / {weights['dense']:.2f}" if weights else "—"
        lines.append(f"| {name} | {ratio} | {item['recall_at_5']:.4f} | {item['mrr_at_5']:.4f} |")
    selected = payload["selected_config"]
    lines.extend([
        "",
        f"Lưới cho thấy cấu hình được chọn theo Recall@5 (hòa thì ưu tiên MRR@5) là BM25 {selected['bm25_weight']:.2f} / Dense {selected['dense_weight']:.2f}. ",
        "Cấu hình này được chọn chỉ theo Dev; kết quả Test đã chạy trước đó không được dùng để chọn trọng số.",
        "",
        "## Lưới trọng số Dev",
        "",
        "| BM25 | Dense | Recall@5 | MRR@5 |",
        "| ---: | ---: | ---: | ---: |",
    ])
    for row in payload["weight_sweep"]:
        lines.append(
            f"| {row['bm25_weight']:.2f} | {row['dense_weight']:.2f} | "
            f"{row['recall_at_5']:.4f} | {row['mrr_at_5']:.4f} |"
        )
    lat = payload["latency_ms"]
    lines.extend([
        "",
        "## Độ trễ",
        "",
        f"Thời gian truy xuất BM25 + Dense + RRF trung bình {lat['mean']:.1f} ms; "
        f"trung vị {lat['median']:.1f} ms; p95 {lat['p95']:.1f} ms. Đây là một lần retrieve chung cho hai nhánh song song, "
        "không phải latency tách riêng từng nhánh.",
        "",
        "## Giới hạn diễn giải",
        "",
        f"Trong {payload['data_scope']['queries_scored']} query Dev, {payload['data_scope']['confirmed_label_queries']} có `gold_context_ids_confirmed=true`; "
        f"{payload['data_scope']['provisional_label_queries']} query dùng nhãn proposal chưa được xác nhận đầy đủ. "
        "Vì vậy metric là kết quả tuning theo proposal, chưa phải kết luận chất lượng pháp lý độc lập.",
        "",
        "Các query có ID nhãn phiên bản văn bản (`version_*`) được liệt kê riêng trong JSON và không tính là miss retrieval, "
        "vì benchmark này đối chiếu ở cấp chunk và các ID đó không tồn tại trong corpus chunk.",
        "",
        "Tuning trọng số không đổi chunking. Kết quả này không dùng Test; do Test đã được xem ở lượt trước, "
        "không chạy lại Test để chọn cấu hình mới.",
        "",
        "## Tệp nguồn",
        "",
        f"- BM25 Top-50: `{payload['inputs']['bm25_results']}`",
        f"- Dense Top-50: `{payload['inputs']['dense_results']}`",
        f"- Hybrid RRF Top-50 đối chiếu: `{payload['inputs']['hybrid_results']}`",
        f"- Kết quả đầy đủ theo query và từng trọng số: `{payload['json_file']}`",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, default=ROOT / "data/benchmark/queries_dev.json")
    parser.add_argument("--labels", type=Path, default=ROOT / "data/benchmark/gold_id_proposals_300.json")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/chunking_output/chunks.jsonl")
    parser.add_argument("--bm25", type=Path, default=ROOT / "retrieval/results/dev_tuning/current_top50/dev_bm25.json")
    parser.add_argument("--dense", type=Path, default=ROOT / "retrieval/results/dev_tuning/current_top50/dev_dense.json")
    parser.add_argument("--hybrid", type=Path, default=ROOT / "retrieval/results/dev_tuning/current_top50/dev_hybrid.json")
    parser.add_argument("--label-mapping", type=Path, default=None,
                        help="File ánh xạ nhãn theo chunking variant; nếu có thì dùng thay nhãn trực tiếp")
    parser.add_argument("--variant", default=None, help="Tên biến thể trong label-mapping, ví dụ C hoặc E")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/current_top50/rrf_weight_sweep.json")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--step", type=float, default=0.05,
                        help="Bước quét trọng số BM25 từ 0 đến 1; Dense = 1 - BM25")
    args = parser.parse_args()
    try:
        if args.top_k < 1 or args.candidate_k < args.top_k:
            raise ValueError("Cần candidate-k >= top-k >= 1")
        if not 0 < args.step <= 1:
            raise ValueError("step phải nằm trong khoảng (0, 1]")
        step_count = round(1 / args.step)
        if not math.isclose(step_count * args.step, 1.0, abs_tol=1e-8):
            raise ValueError("step phải chia hết 1, ví dụ 0.05, 0.1, 0.25 hoặc 1")

        if "test" in args.queries.stem.casefold():
            raise ValueError("Từ chối dùng file có tên Test trong bước tune RRF trên Dev")
        queries = read_json(args.queries)
        dev_rows = [row for row in queries if str(row.get("split", "dev")).casefold() == "dev"]
        if len(dev_rows) != len(queries) or not dev_rows:
            raise ValueError("File query phải chỉ chứa Dev; không đưa Test vào lượt tuning")
        query_ids = [row.get("id") or row.get("query_id") for row in dev_rows]
        if any(not isinstance(qid, str) or not qid for qid in query_ids) or len(set(query_ids)) != len(query_ids):
            raise ValueError("Dev query có ID thiếu hoặc trùng")
        query_id_set = set(query_ids)

        proposals = read_json(args.labels)
        proposal_by_id: dict[str, dict[str, Any]] = {}
        for row in proposals:
            qid = row.get("id") or row.get("query_id")
            if qid in proposal_by_id:
                raise ValueError(f"Proposal ID trùng: {qid}")
            proposal_by_id[qid] = row
        chunks = read_chunks(args.chunks)

        labels: dict[str, set[str]] = {}
        confirmed_queries = 0
        provisional_queries = 0
        no_label_queries: list[str] = []
        unmapped_labels: list[dict[str, Any]] = []
        label_mapping_variant = None
        label_mapping_file = None
        if args.label_mapping:
            if not args.variant:
                raise ValueError("Cần --variant khi dùng --label-mapping")
            mapping_data = read_json(args.label_mapping)
            mapped = mapping_data.get("configs", {}).get(args.variant)
            if not isinstance(mapped, dict):
                raise ValueError(f"Không có biến thể {args.variant} trong {args.label_mapping}")
            labels = {qid: set(ids) for qid, ids in mapped.get("query_labels", {}).items()}
            if not labels or not set(labels).issubset(query_id_set):
                raise ValueError("File ánh xạ không có nhãn hoặc chứa query ngoài Dev")
            for qid, relevant in labels.items():
                missing = relevant - chunks
                if missing:
                    raise ValueError(f"Ánh xạ {qid} chứa chunk ID không thuộc corpus: {sorted(missing)[:5]}")
                proposal = proposal_by_id.get(qid, {})
                if proposal.get("gold_context_ids_confirmed") is True:
                    confirmed_queries += 1
                else:
                    provisional_queries += 1
            no_label_queries = [row["query_id"] for row in mapped.get("query_details", [])
                                if row.get("status") == "no_chunk_label"]
            unmapped_labels = list(mapped.get("excluded_invalid_base_ids", [])) + list(
                mapped.get("excluded_unmapped_variant_spans", [])
            )
            label_mapping_variant = args.variant
            label_mapping_file = str(args.label_mapping.relative_to(ROOT)) if args.label_mapping.is_relative_to(ROOT) else str(args.label_mapping)
            labels_source = mapping_data.get("labels_source", str(args.labels))
        else:
            if args.variant:
                raise ValueError("--variant chỉ dùng cùng --label-mapping")
            labels_source = str(args.labels)
            for qid in query_ids:
                proposal = proposal_by_id.get(qid)
                if proposal is None:
                    raise ValueError(f"Thiếu proposal cho Dev query {qid}")
                relevant = proposal.get("gold_context_ids") or proposal.get("candidate_context_ids") or []
                if not isinstance(relevant, list):
                    raise ValueError(f"Nhãn chunk không phải list ở {qid}")
                if not relevant:
                    no_label_queries.append(qid)
                    continue
                missing = set(relevant) - chunks
                if missing:
                    unmapped_labels.append({"query_id": qid, "ids_not_in_chunks_jsonl": sorted(missing)})
                    continue
                labels[qid] = set(relevant)
                if proposal.get("gold_context_ids_confirmed") is True:
                    confirmed_queries += 1
                else:
                    provisional_queries += 1
        if not labels:
            raise ValueError("Không có Dev query nào có nhãn chunk")

        bm25 = read_envelopes(args.bm25, query_id_set, expected_candidates=args.candidate_k)
        dense = read_envelopes(args.dense, query_id_set, expected_candidates=args.candidate_k)
        hybrid = read_envelopes(args.hybrid, query_id_set, expected_candidates=args.candidate_k)

        baseline_rows: dict[str, dict[str, list[dict[str, Any]]]] = {
            "BM25-only": {qid: bm25[qid]["results"] for qid in labels},
            "Dense-only": {qid: dense[qid]["results"] for qid in labels},
            "Hybrid RRF hiện tại": {qid: hybrid[qid]["results"] for qid in labels},
        }
        baselines: dict[str, dict[str, Any]] = {}
        for name, rows in baseline_rows.items():
            metrics, _ = score_rankings(rows, labels, args.top_k)
            baselines[name] = metrics

        sweep: list[dict[str, Any]] = []
        rankings_by_weight: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for i in range(step_count + 1):
            bm25_weight = round(i * args.step, 8)
            dense_weight = round(1.0 - bm25_weight, 8)
            rankings: dict[str, list[dict[str, Any]]] = {}
            for qid in labels:
                rankings[qid] = reciprocal_rank_fusion(
                    [bm25[qid]["results"], dense[qid]["results"]],
                    top_k=args.candidate_k,
                    rrf_k=args.rrf_k,
                    weights=[bm25_weight, dense_weight],
                )
            metrics, per_query = score_rankings(rankings, labels, args.top_k)
            row = {
                "bm25_weight": bm25_weight,
                "dense_weight": dense_weight,
                **metrics,
                "per_query": per_query,
            }
            sweep.append(row)
            rankings_by_weight[f"{bm25_weight:.8f}"] = rankings

        # Verify saved Hybrid output against its source-weight ratio when that ratio is in the sweep.
        first_qid = next(iter(labels))
        saved_config = hybrid[first_qid].get("config", {})
        saved_bm25_weight = float(saved_config.get("bm25_weight", 1.0))
        saved_dense_weight = float(saved_config.get("dense_weight", 1.0))
        saved_total_weight = saved_bm25_weight + saved_dense_weight
        saved_ratio = round(saved_bm25_weight / saved_total_weight, 8) if saved_total_weight else None
        saved_key = f"{saved_ratio:.8f}" if saved_ratio is not None else ""
        matched_top_k: int | None = None
        if saved_key in rankings_by_weight:
            saved_rankings = rankings_by_weight[saved_key]
            matched_top_k = sum(
                [row["chunk_id"] for row in saved_rankings[qid][:args.top_k]]
                == [row["chunk_id"] for row in hybrid[qid]["results"][:args.top_k]]
                for qid in labels
            )
            if matched_top_k != len(labels):
                raise ValueError(
                    f"Lỗi đối chiếu: RRF trọng số đã lưu khớp Top-{args.top_k} ở "
                    f"{matched_top_k}/{len(labels)} query"
                )

        selected = max(sweep, key=lambda row: (row["recall_at_5"], row["mrr_at_5"]))
        latencies = sorted(float(hybrid[qid].get("latency_ms", 0.0)) for qid in labels)
        payload: dict[str, Any] = {
            "run_date": date.today().isoformat(),
            "labels_file": labels_source,
            "label_mapping_file": label_mapping_file,
            "label_mapping_variant": label_mapping_variant,
            "chunks_file": str(args.chunks.relative_to(ROOT)) if args.chunks.is_relative_to(ROOT) else str(args.chunks),
            "corpus_chunk_count": len(chunks),
            "inputs": {
                "bm25_results": str(args.bm25.relative_to(ROOT)) if args.bm25.is_relative_to(ROOT) else str(args.bm25),
                "dense_results": str(args.dense.relative_to(ROOT)) if args.dense.is_relative_to(ROOT) else str(args.dense),
                "hybrid_results": str(args.hybrid.relative_to(ROOT)) if args.hybrid.is_relative_to(ROOT) else str(args.hybrid),
            },
            "json_file": str(args.output.relative_to(ROOT)) if args.output.is_relative_to(ROOT) else str(args.output),
            "data_scope": {
                "dev_queries": len(dev_rows),
                "queries_scored": len(labels),
                "queries_without_chunk_labels": len(no_label_queries),
                "queries_excluded_unmapped_chunk_ids": len(unmapped_labels),
                "confirmed_label_queries": confirmed_queries,
                "provisional_label_queries": provisional_queries,
                "test_queries_used": 0,
                "queries_without_labels": no_label_queries,
                "unmapped_chunk_label_details": unmapped_labels,
            },
            "config": {
                "top_k": args.top_k,
                "candidate_k": args.candidate_k,
                "rrf_k": args.rrf_k,
                "weight_step": args.step,
                "selection_metric": "Recall@5; MRR@5 để phân xử nếu Recall@5 bằng nhau",
                "dense_model": hybrid[next(iter(labels))].get("config", {}).get("dense_model"),
                "elasticsearch_index": hybrid[next(iter(labels))].get("config", {}).get("elasticsearch_index"),
                "qdrant_collection": hybrid[next(iter(labels))].get("config", {}).get("collection"),
            },
            "baselines": baselines,
            "saved_hybrid_weights": {"bm25": saved_bm25_weight, "dense": saved_dense_weight},
            "saved_hybrid_top_k_match_count": matched_top_k,
            "selected_config": {
                "bm25_weight": selected["bm25_weight"],
                "dense_weight": selected["dense_weight"],
                "recall_at_5": selected["recall_at_5"],
                "mrr_at_5": selected["mrr_at_5"],
            },
            "latency_ms": {
                "mean": statistics.fmean(latencies) if latencies else 0.0,
                "median": statistics.median(latencies) if latencies else 0.0,
                "p95": percentile(latencies, 0.95),
                "measured_path": "BM25 + Dense + RRF song song trong cùng một lần retrieve",
            },
            "weight_sweep": sweep,
            "notes": [
                "Nhãn chỉ đọc từ gold_id_proposals_300.json; hàng thuộc Test không được dùng.",
                "Các proposal chưa được xác nhận pháp lý đầy đủ; metric phản ánh nhãn Dev hiện có.",
                "Cấu hình trọng số đã lưu được đối chiếu Top-5 nếu có trong lưới sweep.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path = args.output.with_suffix(".md")
        write_report(report_path, payload)
        print(f"Dev query={len(dev_rows)}; scored={len(labels)}; Test used=0")
        print(f"BM25: Recall@5={baselines['BM25-only']['recall_at_5']:.4f}, MRR@5={baselines['BM25-only']['mrr_at_5']:.4f}")
        print(f"Dense: Recall@5={baselines['Dense-only']['recall_at_5']:.4f}, MRR@5={baselines['Dense-only']['mrr_at_5']:.4f}")
        print(f"Hybrid RRF: Recall@5={baselines['Hybrid RRF hiện tại']['recall_at_5']:.4f}, MRR@5={baselines['Hybrid RRF hiện tại']['mrr_at_5']:.4f}")
        print(f"Selected BM25/Dense weights={selected['bm25_weight']:.2f}/{selected['dense_weight']:.2f}; "
              f"Recall@5={selected['recall_at_5']:.4f}, MRR@5={selected['mrr_at_5']:.4f}")
        print(f"JSON: {args.output}")
        print(f"Report: {report_path}")
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
