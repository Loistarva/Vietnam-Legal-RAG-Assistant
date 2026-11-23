"""Evaluate Task 4 outputs against article and candidate chunk labels.

Candidate labels in this project are not legally reviewed gold labels. The
generated metrics are exploratory until those labels are confirmed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import evaluate as evaluate_shared_metrics


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def normalize_results(data: list[dict]) -> list[dict[str, Any]]:
    flat = []
    for item in data:
        if not (isinstance(item, dict) and "results" in item and isinstance(item["results"], list)):
            raise ValueError("Kết quả truy xuất phải tuân thủ RetrievalEnvelope schema (chứa 'results')")
        query_id = item.get("query_id")
        if not isinstance(query_id, str) or not query_id:
            raise ValueError("RetrievalEnvelope thiếu query_id hợp lệ")
        for res in item["results"]:
            flat.append({
                "query_id": query_id,
                "chunk_id": res.get("chunk_id"),
                "score": res.get("score") if res.get("score") is not None else res.get("rrf_score", 0.0),
                "rank": res.get("rank"),
            })
    return flat


def score_with_shared_metrics(
    labels_by_query: dict[str, set[str]],
    retrieved_by_query: dict[str, list[str]],
    k: int,
) -> dict[str, float | None]:
    with tempfile.TemporaryDirectory(prefix="task4-metrics-") as temp_dir:
        temp_path = Path(temp_dir)
        ground_truth_path = temp_path / "ground_truth.json"
        results_path = temp_path / "results.json"
        ground_truth_path.write_text(
            json.dumps([
                {
                    "id": query_id,
                    "gold_context_ids": sorted(labels),
                    "gold_context_ids_confirmed": True,
                }
                for query_id, labels in labels_by_query.items()
            ]),
            encoding="utf-8",
        )
        results_path.write_text(
            json.dumps([
                {
                    "query_id": query_id,
                    "retrieved_chunk_ids": retrieved_by_query[query_id],
                }
                for query_id in labels_by_query
            ]),
            encoding="utf-8",
        )
        return evaluate_shared_metrics(
            results_path, ground_truth_path, ks=(k,)
        )["average"]


def _ranked_results_by_query(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_query[row["query_id"]].append(row)
    return by_query


def _top_ten_chunk_ids(
    method: str,
    query_id: str,
    by_query: dict[str, list[dict[str, Any]]],
) -> list[str]:
    ranked = sorted(by_query.get(query_id, []), key=lambda row: row["rank"])
    if len(ranked) != 10:
        raise ValueError(f"{method}: cần đúng Top-10 cho truy vấn {query_id!r}")
    ids = [row["chunk_id"] for row in ranked]
    if len(set(ids)) != 10:
        raise ValueError(f"{method}: chunk ID trùng trong truy vấn {query_id!r}")
    return ids


def evaluate(dev_path: Path, ground_truth_path: Path, chunks_path: Path,
             results_dir: Path, output_path: Path,
             article_index_path: Path, article_output_path: Path) -> list[dict[str, float | int | str]]:
    dev = read_json(dev_path)
    truth = {row["id"]: row for row in read_json(ground_truth_path)}
    article_by_document_number = {
        (str(row.get("document_number", "")), str(row.get("article_number", ""))): row["article_id"]
        for row in read_json(article_index_path)
    }
    chunk_rows = [
        json.loads(line)
        for line in chunks_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    chunk_ids = {(row.get("chunk_id") or row.get("id")) for row in chunk_rows}
    chunk_to_article = {}
    for row in chunk_rows:
        chunk_id = row.get("chunk_id") or row.get("id")
        article_id = article_by_document_number.get(
            (str(row.get("document_number", "")), str(row.get("article_number", "")))
        )
        if chunk_id and article_id:
            chunk_to_article[chunk_id] = article_id
    query_labels: dict[str, set[str]] = {}
    confirmed_queries = 0
    candidate_queries = 0
    excluded = 0
    for question in dev:
        query_id = question["id"]
        item = truth.get(query_id)
        if item is None:
            raise ValueError(f"Thiếu ground truth cho {query_id}")
        gold = set(item.get("gold_context_ids") or [])
        labels = gold or set(item.get("candidate_context_ids") or [])
        if not labels:
            excluded += 1
            continue
        if gold and item.get("gold_context_ids_confirmed") is True:
            confirmed_queries += 1
        else:
            candidate_queries += 1
        missing = labels - chunk_ids
        if missing:
            raise ValueError(f"Candidate IDs không có trong corpus ({query_id}): {sorted(missing)}")
        query_labels[query_id] = labels

    output_rows = []
    for method in ("bm25", "dense", "hybrid"):
        results = normalize_results(read_json(results_dir / f"dev_{method}.json"))
        by_query = _ranked_results_by_query(results)
        retrieved_by_query = {
            query_id: _top_ten_chunk_ids(method, query_id, by_query)
            for query_id in query_labels
        }
        metrics = score_with_shared_metrics(query_labels, retrieved_by_query, 10)
        output_rows.append({
            "method": method.upper(), "queries_retrieved": len(dev),
            "queries_scored": len(query_labels), "queries_excluded_unlabeled": excluded,
            "queries_scored_gold_confirmed": confirmed_queries,
            "queries_scored_candidate_unverified": candidate_queries,
            "recall_at_10": metrics["strict_match_recall@10"],
            "mrr_at_10": metrics["mrr@10"],
            "ndcg_at_10": metrics["ndcg@10"],
            "precision_at_10": metrics["precision@10"],
        })

    write_csv(output_rows, output_path)
    for row in output_rows:
        print(f"{row['method']}: Recall@10={row['recall_at_10']:.4f}, "
              f"MRR@10={row['mrr_at_10']:.4f}, nDCG@10={row['ndcg_at_10']:.4f}, "
              f"Precision@10={row['precision_at_10']:.4f} "
              f"({row['queries_scored']} scored, {row['queries_excluded_unlabeled']} excluded)")
    print(f"CSV: {output_path}")

    article_labels: dict[str, set[str]] = {}
    article_excluded = 0
    for question in dev:
        query_id = question["id"]
        labels = set(truth[query_id].get("gold_article_ids") or [])
        if labels:
            article_labels[query_id] = labels
        else:
            article_excluded += 1
    article_rows = []
    for method in ("bm25", "dense", "hybrid"):
        results = normalize_results(read_json(results_dir / f"dev_{method}.json"))
        by_query = _ranked_results_by_query(results)
        retrieved_by_query: dict[str, list[str]] = {}
        for query_id in article_labels:
            seen_articles: set[str] = set()
            article_results = []
            for rank, chunk_id in enumerate(
                _top_ten_chunk_ids(method, query_id, by_query), start=1
            ):
                article_id = chunk_to_article.get(chunk_id)
                if article_id and article_id not in seen_articles:
                    seen_articles.add(article_id)
                    article_results.append(article_id)
                else:
                    placeholder = f"__unmatched_article__:{query_id}:{rank}"
                    while placeholder in article_labels[query_id]:
                        placeholder = "_" + placeholder
                    article_results.append(placeholder)
            retrieved_by_query[query_id] = article_results
        metrics = score_with_shared_metrics(article_labels, retrieved_by_query, 10)
        article_rows.append({
            "method": method.upper(), "label_level": "article_id",
            "queries_retrieved": len(dev), "queries_scored": len(article_labels),
            "queries_excluded_unlabeled": article_excluded,
            "queries_scored_gold_confirmed": sum(
                bool(truth[question["id"]].get("gold_context_ids"))
                and truth[question["id"]].get("gold_context_ids_confirmed") is True
                for question in dev if truth[question["id"]].get("gold_article_ids")
            ),
            "queries_scored_candidate_unverified": sum(
                bool(truth[question["id"]].get("gold_article_ids"))
                and truth[question["id"]].get("gold_context_ids_confirmed") is not True
                for question in dev
            ),
            "recall_at_10": metrics["strict_match_recall@10"],
            "mrr_at_10": metrics["mrr@10"],
            "ndcg_at_10": metrics["ndcg@10"],
            "precision_at_10": metrics["precision@10"],
        })
    write_csv(article_rows, article_output_path)
    for row in article_rows:
        print(f"{row['method']} article-level: Recall@10={row['recall_at_10']:.4f}, "
              f"MRR@10={row['mrr_at_10']:.4f}, nDCG@10={row['ndcg_at_10']:.4f}, "
              f"Precision@10={row['precision_at_10']:.4f} "
              f"({row['queries_scored']} scored, {row['queries_excluded_unlabeled']} excluded)")
    print(f"Article-level CSV: {article_output_path}")
    return output_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, default=ROOT / "data/benchmark/queries_dev.json")
    parser.add_argument("--ground-truth", type=Path, default=ROOT / "data/benchmark/ground_truth.json")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/chunking_output/chunks.jsonl")
    parser.add_argument("--results", type=Path, default=ROOT / "retrieval/results")
    parser.add_argument("--output", type=Path, default=ROOT / "retrieval/results/metrics.csv")
    parser.add_argument("--article-index", type=Path, default=ROOT / "data/reference/production_chunk_index.json")
    parser.add_argument("--article-output", type=Path, default=ROOT / "retrieval/results/article_metrics.csv")
    args = parser.parse_args()
    evaluate(args.dev, args.ground_truth, args.chunks, args.results, args.output,
             args.article_index, args.article_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
