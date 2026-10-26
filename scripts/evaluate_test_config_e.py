"""Run one frozen Test benchmark for the Dev-selected Config E (no tuning)."""
from __future__ import annotations

import argparse
import json
import math
import re
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
from retrieval.hybrid_retriever import ElasticsearchBM25Retriever, HybridRetriever, HybridSearchConfig  # noqa: E402
from reranking.reranker import build_reranker, load_reranker_config  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)


def contiguous(shorter: list[str], longer: list[str]) -> bool:
    return bool(shorter) and len(shorter) <= len(longer) and any(
        longer[start:start + len(shorter)] == shorter
        for start in range(len(longer) - len(shorter) + 1)
    )


def chunk_id(row: dict[str, Any]) -> str:
    return str(row.get("chunk_id") or row.get("id") or "")


def chunk_text(row: dict[str, Any]) -> str:
    return str(row.get("text") or row.get("chunk_text") or "")


def map_test_labels(
    query_ids: set[str], proposals: list[dict[str, Any]], base_chunks: list[dict[str, Any]],
    target_chunks: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    """Map proposal IDs to E by the Dev chunking evaluation's same-ID/text-span rule."""
    base_by_id = {chunk_id(row): row for row in base_chunks}
    target_by_id = {chunk_id(row): row for row in target_chunks}
    by_clause: dict[str, list[dict[str, Any]]] = {}
    for row in target_chunks:
        by_clause.setdefault(str(row.get("clause_id") or ""), []).append(row)
    proposals_by_id = {str(row.get("id") or row.get("query_id")): row for row in proposals}

    labels: dict[str, set[str]] = {}
    mappings: list[dict[str, Any]] = []
    for qid in sorted(query_ids):
        proposal = proposals_by_id.get(qid)
        if proposal is None:
            raise ValueError(f"Thiếu proposal cho Test query {qid}")
        gold_ids = proposal.get("gold_context_ids") or proposal.get("candidate_context_ids") or []
        if not gold_ids:
            raise ValueError(f"Test query {qid} không có chunk ID trong gold proposals")
        mapped: list[str] = []
        for gold_id in gold_ids:
            source = base_by_id.get(str(gold_id))
            if source is None:
                raise ValueError(f"Gold ID {gold_id} của {qid} không tồn tại trong chunks.jsonl")
            exact = target_by_id.get(str(gold_id))
            if exact is not None:
                matches = [exact]
                method = "same_chunk_id"
            else:
                source_tokens = tokens(chunk_text(source))
                clause = str(source.get("clause_id") or "")
                matches = []
                for candidate in by_clause.get(clause, []):
                    candidate_tokens = tokens(chunk_text(candidate))
                    if contiguous(candidate_tokens, source_tokens) or contiguous(source_tokens, candidate_tokens):
                        matches.append(candidate)
                method = "same_clause_text_span"
            mapped_ids = [chunk_id(row) for row in matches if chunk_id(row)]
            if not mapped_ids:
                raise ValueError(f"Gold ID {gold_id} của {qid} không ánh xạ được sang Config E")
            mapped.extend(mapped_ids)
            mappings.append({
                "query_id": qid,
                "source_gold_chunk_id": str(gold_id),
                "config_e_chunk_ids": mapped_ids,
                "method": method,
            })
        labels[qid] = set(mapped)
    return labels, mappings


def score(top5: list[dict[str, Any]], relevant: set[str]) -> tuple[float, float, list[str], list[str]]:
    ids = [chunk_id(row) for row in top5]
    hits = list(dict.fromkeys(cid for cid in ids if cid in relevant))
    first_rank = next((rank for rank, cid in enumerate(ids, 1) if cid in relevant), None)
    return len(hits) / len(relevant), (1.0 / first_rank if first_rank else 0.0), ids, hits


def percentile(values: list[float], p: float) -> float | None:
    return values[max(0, math.ceil(p * len(values)) - 1)] if values else None


def summarize(values: list[float]) -> dict[str, float | None]:
    return {
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "p95": percentile(sorted(values), 0.95),
    }


def main() -> int:
    queries_path = ROOT / "data/benchmark/queries_test.json"
    labels_path = ROOT / "data/benchmark/gold_id_proposals_300_test_revised.json"
    base_chunks_path = ROOT / "data/chunking_output/chunks.jsonl"
    config_path = ROOT / "retrieval/config.yaml"
    reranker_config_path = ROOT / "reranking/config.yaml"
    e_dir = ROOT / "retrieval/results/dev_tuning/chunking_variants/E"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "retrieval/results/test_run/config_e_final",
        help="Thư mục output mới; script từ chối ghi đè kết quả Test đã có.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    expected_outputs = ("test_config_e_metrics.json", "test_config_e_rankings.json", "test_config_e_report.md")
    if any((output_dir / name).exists() for name in expected_outputs):
        parser.error(f"Đã có kết quả trong {output_dir}; hãy chọn --output-dir mới để không ghi đè Test.")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        queries = read_json(queries_path)
        if not isinstance(queries, list) or not queries:
            raise ValueError("queries_test.json phải là JSON list không rỗng")
        if any(str(row.get("split", "")).casefold() != "test" for row in queries):
            raise ValueError("queries_test.json phải chỉ chứa split=test")
        query_rows = {str(row.get("id") or row.get("query_id")): row for row in queries}
        query_ids = set(query_rows)
        if len(query_rows) != len(queries):
            raise ValueError("queries_test.json có ID thiếu hoặc trùng")

        import yaml
        config_yaml = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        hybrid_settings = config_yaml.get("hybrid") or {}
        chunking_settings = config_yaml.get("chunking") or {}
        bm25_settings = config_yaml.get("bm25") or {}
        dense_settings = config_yaml.get("dense") or {}
        if chunking_settings.get("variant") != "E":
            raise ValueError("retrieval/config.yaml không trỏ tới Config E đã chốt")
        candidate_k = int(hybrid_settings.get("candidate_k", 0))
        rrf_k = int(hybrid_settings.get("rrf_k", -1))
        bm25_weight = float(hybrid_settings.get("bm25_weight", -1))
        dense_weight = float(hybrid_settings.get("dense_weight", -1))
        top_k = 5
        if (candidate_k != 50 or rrf_k != 60 or not math.isclose(bm25_weight, 0.35)
                or not math.isclose(dense_weight, 0.65)):
            raise ValueError("Cấu hình retrieval không khớp E đã khóa (Top-50, RRF k=60, 0.35/0.65)")

        target_chunks_path = ROOT / str(chunking_settings["chunks_file"])
        target_chunks = read_jsonl(target_chunks_path)
        base_chunks = read_jsonl(base_chunks_path)
        proposals = read_json(labels_path)
        labels, label_mappings = map_test_labels(query_ids, proposals, base_chunks, target_chunks)
        if set(labels) != query_ids:
            raise ValueError("Tập query có nhãn chunk không trùng queries_test")

        elasticsearch_url = "http://localhost:9200"
        from elasticsearch import Elasticsearch
        es = Elasticsearch(elasticsearch_url, request_timeout=30)
        if not es.ping():
            raise ConnectionError(f"Không kết nối được Elasticsearch tại {elasticsearch_url}")
        index = str(bm25_settings["index"])
        if not es.indices.exists(index=index):
            raise ValueError(f"Elasticsearch index thiếu: {index}")
        es_count = int(es.count(index=index)["count"])
        if es_count != len(target_chunks):
            raise ValueError(f"Index E có {es_count} docs, chunks E có {len(target_chunks)}")
        sparse = ElasticsearchBM25Retriever(es, index, text_field=str(bm25_settings.get("text_field", "content_segmented")))

        model_name = str(dense_settings["model"])
        collection = str(dense_settings["collection"])
        qdrant_path = ROOT / str(dense_settings["storage_path"])
        store = LegalVectorStore(collection_name=collection, dimension=MODEL_DIMENSIONS[model_name],
                                 storage_path=str(qdrant_path))
        qdrant_count = store.count()
        if qdrant_count != len(target_chunks):
            raise ValueError(f"Qdrant E có {qdrant_count} points, chunks E có {len(target_chunks)}")
        dense = DenseRetriever(vector_store=store, model_name=model_name)
        hybrid = HybridRetriever(
            sparse, dense,
            HybridSearchConfig(top_k=candidate_k, candidate_k=candidate_k, rrf_k=rrf_k,
                               bm25_weight=bm25_weight, dense_weight=dense_weight),
        )

        reranker_config = load_reranker_config(reranker_config_path, backend="cross_encoder", rerank_top_k=10)
        if reranker_config.model != "BAAI/bge-reranker-v2-m3" or reranker_config.max_candidates != 50:
            raise ValueError("Reranker không khớp cấu hình Cross-Encoder đã khóa")
        reranker = build_reranker(reranker_config)
        if reranker is None or reranker.backend != "cross_encoder":
            raise ValueError("Không khởi tạo được Cross-Encoder thật")

        per_query: list[dict[str, Any]] = []
        raw_queries: list[dict[str, Any]] = []
        latencies: dict[str, list[float]] = {"bm25": [], "hybrid": [], "hybrid_cross_encoder": []}
        model_load_ms = 0.0
        for position, qid in enumerate(query_rows, 1):
            query_row = query_rows[qid]
            question = str(query_row.get("question") or query_row.get("query") or "").strip()
            if not question:
                raise ValueError(f"Query rỗng: {qid}")
            relevant = labels[qid]

            started = time.perf_counter()
            bm25_top5 = sparse.search(question, top_k)
            bm25_ms = (time.perf_counter() - started) * 1000.0

            started = time.perf_counter()
            branches = hybrid.retrieve(question)
            hybrid_ms = (time.perf_counter() - started) * 1000.0
            fused = branches["fused"]
            if len(fused) != candidate_k:
                raise ValueError(f"{qid}: cần {candidate_k} fused candidates, nhận {len(fused)}")

            started = time.perf_counter()
            ce_top10 = reranker.rerank(question, fused, top_k=10)
            ce_total_ms = (time.perf_counter() - started) * 1000.0
            ce_stats = dict(reranker.last_stats)
            model_load_ms += float(ce_stats.get("model_load_ms", 0.0))
            latencies["bm25"].append(bm25_ms)
            latencies["hybrid"].append(hybrid_ms)
            latencies["hybrid_cross_encoder"].append(hybrid_ms + ce_total_ms)

            method_rows: dict[str, Any] = {}
            for method, ranked in (
                ("bm25_only", bm25_top5),
                ("hybrid", fused),
                ("hybrid_cross_encoder", ce_top10),
            ):
                recall, reciprocal_rank, ids, hits = score(ranked[:top_k], relevant)
                method_rows[method] = {
                    "retrieved_chunk_ids_top5": ids,
                    "hit_chunk_ids": hits,
                    "recall_at_5": recall,
                    "mrr_at_5": reciprocal_rank,
                }
            per_query.append({
                "query_id": qid,
                "relevant_chunk_ids": sorted(relevant),
                "relevant_chunk_count": len(relevant),
                "methods": method_rows,
                "latency_ms": {
                    "bm25_only": round(bm25_ms, 3),
                    "hybrid": round(hybrid_ms, 3),
                    "reranker_only": round(ce_total_ms, 3),
                    "hybrid_cross_encoder_end_to_end": round(hybrid_ms + ce_total_ms, 3),
                    "cross_encoder_model_load": ce_stats.get("model_load_ms", 0.0),
                },
                "cross_encoder": ce_stats,
            })
            raw_queries.append({
                "query_id": qid,
                "query": question,
                "bm25_top50": branches["bm25"],
                "dense_top50": branches["dense"],
                "rrf_top50": fused,
                "cross_encoder_top10": ce_top10,
            })
            print(f"Test Config E: {position}/{len(query_rows)} — {qid}", flush=True)

        metrics: dict[str, Any] = {}
        for method in ("bm25_only", "hybrid", "hybrid_cross_encoder"):
            recalls = [row["methods"][method]["recall_at_5"] for row in per_query]
            mrrs = [row["methods"][method]["mrr_at_5"] for row in per_query]
            latency_key = "bm25" if method == "bm25_only" else (
                "hybrid" if method == "hybrid" else "hybrid_cross_encoder"
            )
            metrics[method] = {
                "queries_scored": len(per_query),
                "recall_at_5": statistics.fmean(recalls),
                "mrr_at_5": statistics.fmean(mrrs),
                "latency_ms": summarize(latencies[latency_key]),
            }

        payload = {
            "run_date": date.today().isoformat(),
            "split": "test",
            "repeated_test_notice": "Tập Test đã được xem trong lượt Config A trước đó; đây là lần đánh giá lại Config E, không phải Test độc lập mới.",
            "queries_file": str(queries_path.relative_to(ROOT)),
            "labels_file": str(labels_path.relative_to(ROOT)),
            "labels_status": "gold_id_proposals; proposal IDs được ánh xạ sang chunk E theo cùng chunk_id hoặc cùng clause_id + text span liên tiếp; file gốc không bị sửa.",
            "corpus": {
                "variant": "E",
                "chunks_file": str(target_chunks_path.relative_to(ROOT)),
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
                "benchmark_top_k": top_k,
                "cross_encoder": {
                    "model": reranker_config.model,
                    "backend": reranker_config.backend,
                    "device": reranker_config.device,
                    "batch_size": reranker_config.batch_size,
                    "max_length": reranker_config.max_length,
                    "max_candidates": reranker_config.max_candidates,
                    "pipeline_top_k": reranker_config.rerank_top_k,
                },
            },
            "metrics": metrics,
            "latency_ms": {key: summarize(values) for key, values in latencies.items()},
            "cross_encoder_model_load_total_ms": round(model_load_ms, 3),
            "label_mapping": label_mappings,
            "per_query": per_query,
            "raw_rankings": raw_queries,
            "notes": [
                "Không có tham số nào được tune trên kết quả Test.",
                "Recall@5/MRR@5 tính trên đúng 5 kết quả đầu; Cross-Encoder rerank Top-50 và giữ Top-10 theo runtime config trước khi chấm Top-5.",
                "Các retriever đang loại validity_status='Hết hiệu lực'; Hybrid hiện chưa truyền as_of_date theo từng query, nên metric chưa phản ánh temporal pre-filter đầy đủ.",
                "Nhãn đến từ gold_id_proposals_300_test_revised.json; nhãn proposal chưa được xác minh pháp lý độc lập.",
            ],
        }
        json_path = output_dir / "test_config_e_metrics.json"
        raw_path = output_dir / "test_config_e_rankings.json"
        json_payload = {key: value for key, value in payload.items() if key != "raw_rankings"}
        json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raw_path.write_text(json.dumps({"config": payload["config"], "queries": raw_queries},
                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        report = [
            "# Đánh giá Test — cấu hình E đã khóa",
            "",
            f"- Ngày chạy: {payload['run_date']}",
            f"- Queries: `{payload['queries_file']}` ({len(query_rows)} câu)",
            f"- Nhãn: `{payload['labels_file']}`; ánh xạ nhãn sang chunk E bằng cùng ID hoặc text-span liên tiếp trong cùng clause.",
            f"- Corpus: E, {len(target_chunks)} chunks; Elasticsearch `{index}`; Qdrant `{collection}`.",
            f"- Dense: `{model_name}`; RRF Top-{candidate_k}, k={rrf_k}, BM25/Dense={bm25_weight:.2f}/{dense_weight:.2f}.",
            f"- Reranker thật: `{reranker_config.model}`; Top-{reranker_config.rerank_top_k} đầu ra, chấm tối đa {reranker_config.max_candidates} ứng viên.",
            "- Metric lấy đúng Top-5; không dùng Test để điều chỉnh tham số.",
            "- **Lưu ý:** cùng tập Test đã được xem ở lượt Config A; đây là đánh giá lại Config E, không phải Test độc lập mới.",
            "",
            "| Phương pháp | Recall@5 | MRR@5 | Latency mean / median / p95 (ms) |",
            "| --- | ---: | ---: | ---: |",
        ]
        labels_for_report = {
            "bm25_only": "BM25-only",
            "hybrid": "Hybrid RRF",
            "hybrid_cross_encoder": "Hybrid + Cross-Encoder thật",
        }
        for method, label in labels_for_report.items():
            row = metrics[method]
            latency = row["latency_ms"]
            report.append(
                f"| {label} | {row['recall_at_5']:.4f} | {row['mrr_at_5']:.4f} | "
                f"{latency['mean']:.1f} / {latency['median']:.1f} / {latency['p95']:.1f} |"
            )
        report.extend([
            "",
            "## Giới hạn diễn giải",
            "",
            "Hybrid hiện chưa truyền `as_of_date` từ từng query vào hai nhánh truy xuất; bộ lọc `Hết hiệu lực` dùng trạng thái hiện tại. Kết quả vì vậy đánh giá ranking trên cấu hình E đang chạy, chưa xác nhận đầy đủ Metadata & Temporal Pre-filter theo sơ đồ.",
            "Nhãn proposal còn provisional. Hai nhãn chunk từ corpus gốc có thay đổi ranh giới ở E được ánh xạ bằng text-span trong cùng clause; mapping chi tiết nằm trong JSON metric.",
            "",
            "## Tệp kết quả",
            "",
            f"- Metric và kết quả theo query: `{json_path.relative_to(ROOT)}`",
            f"- Top-50 BM25/Dense/RRF và Top-10 rerank: `{raw_path.relative_to(ROOT)}`",
        ])
        report_path = output_dir / "test_config_e_report.md"
        report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
        print(json.dumps({"metrics": metrics, "metrics_file": str(json_path),
                          "raw_file": str(raw_path), "report_file": str(report_path)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
