"""Đánh giá Cross-Encoder thật và phân tích lỗi từng query trên Dev, cấu hình E."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding.dense_retriever import DenseRetriever, MODEL_DIMENSIONS  # noqa: E402
from embedding.vector_store import LegalVectorStore  # noqa: E402
from retrieval.hybrid_retriever import (  # noqa: E402
    ElasticsearchBM25Retriever,
    HybridRetriever,
    HybridSearchConfig,
)
from reranking.reranker import build_reranker, load_reranker_config  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def chunk_id(row: dict[str, Any]) -> str:
    return str(row.get("chunk_id") or row.get("id") or "")


def score(ranked: list[dict[str, Any]], relevant: set[str], k: int = 5) -> dict[str, Any]:
    ids = [chunk_id(row) for row in ranked[:k]]
    hits = list(dict.fromkeys(cid for cid in ids if cid in relevant))
    first_rank = next((rank for rank, cid in enumerate(ids, 1) if cid in relevant), None)
    return {
        "retrieved_chunk_ids": ids,
        "hit_chunk_ids": hits,
        "recall_at_5": len(hits) / len(relevant) if relevant else 0.0,
        "mrr_at_5": 1.0 / first_rank if first_rank else 0.0,
    }


def percentile(values: list[float], p: float) -> float | None:
    return values[max(0, math.ceil(p * len(values)) - 1)] if values else None


def summarize(values: list[float]) -> dict[str, float | None]:
    return {
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "p95": percentile(sorted(values), 0.95),
    }


def rank_of(chunk: str, rows: list[dict[str, Any]]) -> int | None:
    return next((rank for rank, row in enumerate(rows, 1) if chunk_id(row) == chunk), None)


def main() -> int:
    queries_path = ROOT / "data/benchmark/queries_dev.json"
    labels_path = ROOT / "retrieval/results/dev_tuning/chunking_variants/E/dev_chunk_labels.json"
    base_chunks_path = ROOT / "retrieval/results/dev_tuning/chunking_variants/E/chunks.jsonl"
    config_path = ROOT / "retrieval/config.yaml"
    reranker_config_path = ROOT / "reranking/config.yaml"
    output_default = ROOT / "retrieval/results/dev_tuning/cross_encoder_config_e"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=output_default,
                        help="Thư mục output mới; không ghi đè kết quả đã có.")
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    expected_outputs = (
        "dev_cross_encoder_metrics.json",
        "dev_cross_encoder_rankings.json",
        "dev_cross_encoder_report.md",
    )
    if any((output_dir / name).exists() for name in expected_outputs):
        parser.error(f"Đã có kết quả trong {output_dir}; hãy chọn --output-dir mới.")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        queries = read_json(queries_path)
        labels_doc = read_json(labels_path)
        if not isinstance(queries, list) or not queries:
            raise ValueError("queries_dev.json phải là JSON list không rỗng")
        if any(str(row.get("split", "")).casefold() != "dev" for row in queries):
            raise ValueError("queries_dev.json phải chỉ chứa split=dev")
        query_rows = {str(row.get("id") or row.get("query_id")): row for row in queries}
        if len(query_rows) != len(queries):
            raise ValueError("queries_dev.json có ID thiếu hoặc trùng")

        label_rows = labels_doc.get("query_labels") or {}
        if not isinstance(label_rows, dict):
            raise ValueError("dev_chunk_labels.json thiếu object query_labels")
        query_ids = [qid for qid in query_rows if qid in label_rows and label_rows[qid]]
        excluded_ids = [qid for qid in query_rows if qid not in label_rows or not label_rows[qid]]
        if len(query_ids) != int(labels_doc.get("queries_scored", len(query_ids))):
            raise ValueError("Số query có nhãn không khớp metadata dev_chunk_labels.json")
        labels = {qid: set(map(str, label_rows[qid])) for qid in query_ids}
        target_chunks = read_jsonl(base_chunks_path)
        target_ids = {chunk_id(row) for row in target_chunks}
        unknown_labels = {qid: sorted(ids - target_ids) for qid, ids in labels.items() if ids - target_ids}
        if unknown_labels:
            raise ValueError(f"Có nhãn Dev không thuộc chunks E: {list(unknown_labels.items())[:3]}")

        import yaml
        config_yaml = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        hybrid_settings = config_yaml.get("hybrid") or {}
        chunking_settings = config_yaml.get("chunking") or {}
        bm25_settings = config_yaml.get("bm25") or {}
        dense_settings = config_yaml.get("dense") or {}
        if chunking_settings.get("variant") != "E":
            raise ValueError("retrieval/config.yaml không trỏ tới Config E")
        candidate_k = int(hybrid_settings.get("candidate_k", 0))
        rrf_k = int(hybrid_settings.get("rrf_k", -1))
        bm25_weight = float(hybrid_settings.get("bm25_weight", -1))
        dense_weight = float(hybrid_settings.get("dense_weight", -1))
        if (candidate_k != 50 or rrf_k != 60 or not math.isclose(bm25_weight, 0.35)
                or not math.isclose(dense_weight, 0.65)):
            raise ValueError("Cần cấu hình E đã chốt: Top-50, RRF k=60, BM25/Dense=0,35/0,65")

        chunks_path = ROOT / str(chunking_settings["chunks_file"])
        if chunks_path.resolve() != base_chunks_path.resolve():
            raise ValueError("chunks_file trong retrieval/config.yaml không trỏ tới chunks E dùng gán nhãn")

        from elasticsearch import Elasticsearch
        es = Elasticsearch("http://localhost:9200", request_timeout=30)
        if not es.ping():
            raise ConnectionError("Không kết nối được Elasticsearch tại http://localhost:9200")
        index = str(bm25_settings["index"])
        if not es.indices.exists(index=index):
            raise ValueError(f"Thiếu Elasticsearch index E: {index}")
        es_count = int(es.count(index=index)["count"])
        if es_count != len(target_chunks):
            raise ValueError(f"Elasticsearch E có {es_count} docs, chunks E có {len(target_chunks)}")
        sparse = ElasticsearchBM25Retriever(
            es, index, text_field=str(bm25_settings.get("text_field", "content_segmented"))
        )

        model_name = str(dense_settings["model"])
        collection = str(dense_settings["collection"])
        qdrant_path = ROOT / str(dense_settings["storage_path"])
        store = LegalVectorStore(collection_name=collection,
                                 dimension=MODEL_DIMENSIONS[model_name],
                                 storage_path=str(qdrant_path))
        qdrant_count = store.count()
        if qdrant_count != len(target_chunks):
            raise ValueError(f"Qdrant E có {qdrant_count} points, chunks E có {len(target_chunks)}")
        dense = DenseRetriever(vector_store=store, model_name=model_name)
        hybrid = HybridRetriever(
            sparse,
            dense,
            HybridSearchConfig(top_k=candidate_k, candidate_k=candidate_k, rrf_k=rrf_k,
                               bm25_weight=bm25_weight, dense_weight=dense_weight),
        )

        reranker_config = load_reranker_config(
            reranker_config_path, backend="cross_encoder", rerank_top_k=10
        )
        if (reranker_config.model != "BAAI/bge-reranker-v2-m3"
                or reranker_config.max_candidates != 50):
            raise ValueError("Reranker không khớp cấu hình Cross-Encoder đã chốt")
        reranker = build_reranker(reranker_config)
        if reranker is None or reranker.backend != "cross_encoder":
            raise ValueError("Không khởi tạo được Cross-Encoder thật")

        per_query: list[dict[str, Any]] = []
        raw_queries: list[dict[str, Any]] = []
        latencies: dict[str, list[float]] = {
            "bm25_only": [], "hybrid_retrieval": [], "reranker_inference": [],
            "hybrid_cross_encoder_end_to_end": [],
        }
        total_model_load_ms = 0.0

        for position, qid in enumerate(query_ids, 1):
            question = str(query_rows[qid].get("question") or query_rows[qid].get("query") or "").strip()
            if not question:
                raise ValueError(f"Query rỗng: {qid}")
            relevant = labels[qid]

            started = time.perf_counter()
            bm25_top5 = sparse.search(question, top_k=5)
            bm25_ms = (time.perf_counter() - started) * 1000.0

            started = time.perf_counter()
            branches = hybrid.retrieve(question)
            hybrid_ms = (time.perf_counter() - started) * 1000.0
            bm25_branch = branches["bm25"]
            dense_branch = branches["dense"]
            fused = branches["fused"]
            if len(fused) != candidate_k:
                raise ValueError(f"{qid}: cần {candidate_k} fused candidates, nhận {len(fused)}")

            started = time.perf_counter()
            ce_top10 = reranker.rerank(question, fused, top_k=10)
            ce_total_ms = (time.perf_counter() - started) * 1000.0
            ce_stats = dict(reranker.last_stats)
            total_model_load_ms += float(ce_stats.get("model_load_ms", 0.0))
            rerank_ms = float(ce_stats.get("rerank_latency_ms", ce_total_ms))
            latencies["bm25_only"].append(bm25_ms)
            latencies["hybrid_retrieval"].append(hybrid_ms)
            latencies["reranker_inference"].append(rerank_ms)
            latencies["hybrid_cross_encoder_end_to_end"].append(hybrid_ms + ce_total_ms)

            method_rows = {
                "bm25_only": score(bm25_top5, relevant),
                "hybrid": score(fused, relevant),
                "hybrid_cross_encoder": score(ce_top10, relevant),
            }
            relevant_diagnostics = []
            for relevant_id in sorted(relevant):
                bm25_rank = rank_of(relevant_id, bm25_branch)
                dense_rank = rank_of(relevant_id, dense_branch)
                fused_rank = rank_of(relevant_id, fused)
                ce_rank = rank_of(relevant_id, ce_top10)
                if ce_rank is not None and ce_rank <= 5:
                    stage = "cross_encoder_top5"
                elif fused_rank is not None:
                    stage = "cross_encoder_day_nhan_ra_khoi_top5"
                elif bm25_rank is not None or dense_rank is not None:
                    stage = "fusion_khong_giu_trong_top50"
                else:
                    stage = "khong_co_trong_bm25_hoac_dense_top50"
                relevant_diagnostics.append({
                    "relevant_chunk_id": relevant_id,
                    "bm25_rank_top50": bm25_rank,
                    "dense_rank_top50": dense_rank,
                    "hybrid_rank_top50": fused_rank,
                    "cross_encoder_rank_top10": ce_rank,
                    "failure_stage": stage,
                })

            ce_hits = method_rows["hybrid_cross_encoder"]["hit_chunk_ids"]
            hybrid_hits = method_rows["hybrid"]["hit_chunk_ids"]
            branch_has_relevant = any(d["bm25_rank_top50"] or d["dense_rank_top50"]
                                      for d in relevant_diagnostics)
            fused_has_relevant = any(d["hybrid_rank_top50"] for d in relevant_diagnostics)
            if len(ce_hits) == len(relevant):
                query_diagnosis = "cross_encoder_tim_du_nhan_trong_top5"
            elif ce_hits:
                query_diagnosis = "cross_encoder_tim_duoc_mot_phan_nhan"
            elif fused_has_relevant:
                query_diagnosis = "reranker_day_nhan_khoi_top5"
            elif branch_has_relevant:
                query_diagnosis = "fusion_cat_nhan_khoi_top50"
            else:
                query_diagnosis = "candidate_generation_khong_co_nhan"

            per_query.append({
                "query_id": qid,
                "question": question,
                "relevant_chunk_ids": sorted(relevant),
                "relevant_chunk_count": len(relevant),
                "methods": method_rows,
                "relevant_chunk_diagnostics": relevant_diagnostics,
                "query_diagnosis": query_diagnosis,
                "latency_ms": {
                    "bm25_only": round(bm25_ms, 3),
                    "hybrid_retrieval": round(hybrid_ms, 3),
                    "reranker_inference": round(rerank_ms, 3),
                    "hybrid_cross_encoder_end_to_end": round(hybrid_ms + ce_total_ms, 3),
                    "cross_encoder_model_load": ce_stats.get("model_load_ms", 0.0),
                },
                "cross_encoder": ce_stats,
            })
            raw_queries.append({
                "query_id": qid,
                "question": question,
                "relevant_chunk_ids": sorted(relevant),
                "bm25_top50": bm25_branch,
                "dense_top50": dense_branch,
                "hybrid_rrf_top50": fused,
                "cross_encoder_top10": ce_top10,
            })
            print(f"Dev E + Cross-Encoder: {position}/{len(query_ids)} — {qid}", flush=True)

        metrics: dict[str, Any] = {}
        for method in ("bm25_only", "hybrid", "hybrid_cross_encoder"):
            recalls = [row["methods"][method]["recall_at_5"] for row in per_query]
            mrrs = [row["methods"][method]["mrr_at_5"] for row in per_query]
            latency_key = {
                "bm25_only": "bm25_only",
                "hybrid": "hybrid_retrieval",
                "hybrid_cross_encoder": "hybrid_cross_encoder_end_to_end",
            }[method]
            metrics[method] = {
                "queries_scored": len(per_query),
                "recall_at_5": statistics.fmean(recalls),
                "mrr_at_5": statistics.fmean(mrrs),
                "latency_ms": summarize(latencies[latency_key]),
            }

        total_relevant = sum(len(row["relevant_chunk_ids"]) for row in per_query)
        found_in_hybrid_top50 = sum(
            sum(d["hybrid_rank_top50"] is not None for d in row["relevant_chunk_diagnostics"])
            for row in per_query
        )
        diagnosis_counts: dict[str, int] = {}
        for row in per_query:
            diagnosis_counts[row["query_diagnosis"]] = diagnosis_counts.get(row["query_diagnosis"], 0) + 1
        cross_improved = sum(
            row["methods"]["hybrid_cross_encoder"]["recall_at_5"]
            > row["methods"]["hybrid"]["recall_at_5"] for row in per_query
        )
        cross_hurt = sum(
            row["methods"]["hybrid_cross_encoder"]["recall_at_5"]
            < row["methods"]["hybrid"]["recall_at_5"] for row in per_query
        )
        cross_same = len(per_query) - cross_improved - cross_hurt

        payload = {
            "run_date": date.today().isoformat(),
            "split": "dev",
            "queries_file": str(queries_path.relative_to(ROOT)),
            "labels_file": str(labels_path.relative_to(ROOT)),
            "labels_status": "gold_id_proposals_300 đã ánh xạ sang chunk E; chỉ chấm 267 query có nhãn chunk hợp lệ.",
            "queries_total": len(queries),
            "queries_scored": len(per_query),
            "queries_excluded_without_valid_chunk_label": excluded_ids,
            "corpus": {
                "variant": "E",
                "chunks_file": str(chunks_path.relative_to(ROOT)),
                "chunks": len(target_chunks),
                "elasticsearch_index": index,
                "elasticsearch_documents": es_count,
                "qdrant_collection": collection,
                "qdrant_points": qdrant_count,
            },
            "config": {
                "chunking": chunking_settings,
                "dense_model": model_name,
                "candidate_k": candidate_k,
                "rrf_k": rrf_k,
                "bm25_weight": bm25_weight,
                "dense_weight": dense_weight,
                "benchmark_top_k": 5,
                "cross_encoder": {
                    "model": reranker_config.model,
                    "backend": reranker_config.backend,
                    "device": reranker_config.device,
                    "batch_size": reranker_config.batch_size,
                    "max_length": reranker_config.max_length,
                    "max_candidates": reranker_config.max_candidates,
                    "pipeline_top_k": reranker_config.rerank_top_k,
                    "candidate_text": reranker_config.candidate_text,
                },
            },
            "metrics": metrics,
            "diagnostics": {
                "relevant_chunk_labels_total": total_relevant,
                "relevant_chunks_recalled_in_hybrid_top50": found_in_hybrid_top50,
                "hybrid_candidate_recall_at_50": found_in_hybrid_top50 / total_relevant if total_relevant else 0,
                "cross_encoder_improved_queries": cross_improved,
                "cross_encoder_hurt_queries": cross_hurt,
                "cross_encoder_unchanged_queries": cross_same,
                "query_diagnosis_counts": diagnosis_counts,
            },
            "latency_ms": {key: summarize(values) for key, values in latencies.items()},
            "cross_encoder_model_load_total_ms": round(total_model_load_ms, 3),
            "per_query": per_query,
            "raw_rankings": raw_queries,
            "notes": [
                "Chỉ dùng split=dev; không đọc hoặc sử dụng queries_test hay nhãn Test.",
                "Cross-Encoder thật BAAI/bge-reranker-v2-m3 chấm cùng Top-50 ứng viên Hybrid RRF; đầu ra Top-10, metric lấy đúng Top-5.",
                "Recall@5 là macro-average theo query, recall từng query = số chunk nhãn được tìm thấy / tổng chunk nhãn của query.",
                "Nhãn đến từ gold_id_proposals_300 đã ánh xạ theo chunk E; 18 query không có nhãn chunk hợp lệ bị loại khỏi metric.",
                "Metadata lọc trạng thái hết hiệu lực như code hiện hành; chưa truyền as_of_date riêng từng query.",
            ],
        }

        metrics_path = output_dir / expected_outputs[0]
        raw_path = output_dir / expected_outputs[1]
        report_path = output_dir / expected_outputs[2]
        metrics_payload = {key: value for key, value in payload.items() if key != "raw_rankings"}
        metrics_path.write_text(json.dumps(metrics_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raw_path.write_text(json.dumps({"config": payload["config"], "queries": raw_queries},
                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        report = [
            "# Đánh giá Cross-Encoder trên Dev — cấu hình E",
            "",
            f"- Ngày chạy: {payload['run_date']}",
            f"- Queries: `{payload['queries_file']}` ({len(queries)} câu; chấm {len(per_query)}, loại {len(excluded_ids)} thiếu nhãn chunk hợp lệ).",
            f"- Nhãn: `{payload['labels_file']}`; gold_id_proposals đã ánh xạ sang chunk E.",
            f"- Corpus: E, {len(target_chunks)} chunks; Elasticsearch `{index}`; Qdrant `{collection}`.",
            f"- Dense: `{model_name}`; Hybrid Top-{candidate_k}, RRF k={rrf_k}, BM25/Dense={bm25_weight:.2f}/{dense_weight:.2f}.",
            f"- Cross-Encoder thật: `{reranker_config.model}`; nhận cùng Top-{candidate_k}, xuất Top-{reranker_config.rerank_top_k}, metric trên Top-5.",
            "- Chỉ dùng Dev; không dùng hoặc điều chỉnh theo Test.",
            "",
            "## Kết quả tổng hợp",
            "",
            "| Phương pháp | Recall@5 | MRR@5 | Latency mean / median / p95 (ms) |",
            "| --- | ---: | ---: | ---: |",
        ]
        method_labels = {
            "bm25_only": "BM25-only",
            "hybrid": "Hybrid RRF",
            "hybrid_cross_encoder": "Hybrid + Cross-Encoder thật",
        }
        for method, label in method_labels.items():
            row = metrics[method]
            latency = row["latency_ms"]
            report.append(
                f"| {label} | {row['recall_at_5']:.4f} | {row['mrr_at_5']:.4f} | "
                f"{latency['mean']:.1f} / {latency['median']:.1f} / {latency['p95']:.1f} |"
            )
        report.extend([
            "",
            "## Chẩn đoán theo tầng",
            "",
            f"- Candidate Recall@50 của Hybrid: {found_in_hybrid_top50}/{total_relevant} nhãn chunk ({payload['diagnostics']['hybrid_candidate_recall_at_50']:.4f}).",
            f"- Cross-Encoder cải thiện recall theo query: {cross_improved}; làm giảm: {cross_hurt}; không đổi: {cross_same}.",
            "- Số query theo chẩn đoán: " + "; ".join(f"`{key}`: {value}" for key, value in sorted(diagnosis_counts.items())) + ".",
            "",
            "## Phân tích từng query",
            "",
            "`BM25/Dense/Hybrid/CE` là thứ hạng của chunk nhãn trong BM25 Top-50, Dense Top-50, Hybrid Top-50 và Cross-Encoder Top-10; `—` nghĩa là không có trong danh sách.",
            "",
            "| Query | Chẩn đoán | Nhãn liên quan: BM25/Dense/Hybrid/CE rank | Hybrid hit@5 → CE hit@5 |",
            "| --- | --- | --- | ---: |",
        ])
        for row in per_query:
            diagnosis = row["query_diagnosis"]
            label_ranks = "; ".join(
                f"`{d['relevant_chunk_id']}`: {d['bm25_rank_top50'] or '—'}/"
                f"{d['dense_rank_top50'] or '—'}/{d['hybrid_rank_top50'] or '—'}/"
                f"{d['cross_encoder_rank_top10'] or '—'}"
                for d in row["relevant_chunk_diagnostics"]
            )
            hybrid_hits = len(row["methods"]["hybrid"]["hit_chunk_ids"])
            ce_hits = len(row["methods"]["hybrid_cross_encoder"]["hit_chunk_ids"])
            report.append(f"| `{row['query_id']}` | `{diagnosis}` | {label_ranks} | {hybrid_hits} → {ce_hits} |")
        report.extend([
            "",
            "## Diễn giải và giới hạn",
            "",
            "Nếu nhãn không xuất hiện trong BM25/Dense Top-50 thì cần xử lý candidate generation, chunking hoặc biểu diễn query. Nếu nhãn có trong Hybrid Top-50 nhưng không còn ở CE Top-5 thì Cross-Encoder đã đẩy nhãn xuống; nếu nhãn có ở một nhánh nhưng vắng trong Hybrid Top-50 thì xem lại fusion.",
            "Nhãn proposal chưa được xác minh pháp lý độc lập. Metric là kết quả đối chiếu theo chunk IDs trong file proposal. Bộ lọc hiện loại `Hết hiệu lực`, nhưng chưa áp dụng `as_of_date` riêng từng query.",
            "",
            "## Tệp kết quả",
            "",
            f"- Metric và chẩn đoán từng query: `{metrics_path.relative_to(ROOT)}`",
            f"- Danh sách đầy đủ BM25/Dense/Hybrid Top-50 và CE Top-10: `{raw_path.relative_to(ROOT)}`",
        ])
        report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
        print(json.dumps({
            "metrics": metrics,
            "diagnostics": payload["diagnostics"],
            "metrics_file": str(metrics_path),
            "raw_file": str(raw_path),
            "report_file": str(report_path),
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
