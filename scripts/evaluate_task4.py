"""Evaluate Task 4 outputs against article and candidate chunk labels.

Candidate labels in this project are not legally reviewed gold labels. The
generated metrics are exploratory until those labels are confirmed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def normalize_results(data: list[dict]) -> list[dict]:
    flat = []
    for item in data:
        if not (isinstance(item, dict) and "results" in item and isinstance(item["results"], list)):
            raise ValueError("Kết quả truy xuất phải tuân thủ RetrievalEnvelope schema (chứa 'results')")
        q_text = item.get("query") or item.get("query_id") or ""
        for res in item["results"]:
            flat.append({
                "query": q_text,
                "chunk_id": res.get("chunk_id"),
                "score": res.get("score") if res.get("score") is not None else res.get("rrf_score", 0.0),
                "rank": res.get("rank"),
            })
    return flat


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
        item = truth.get(question["id"])
        if item is None:
            raise ValueError(f"Thiếu ground truth cho {question['id']}")
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
            raise ValueError(f"Candidate IDs không có trong corpus ({question['id']}): {sorted(missing)}")
        query_labels[question["question"]] = labels

    output_rows = []
    for method in ("bm25", "dense", "hybrid"):
        results = normalize_results(read_json(results_dir / f"dev_{method}.json"))
        by_query: dict[str, list[dict]] = defaultdict(list)
        for row in results:
            by_query[row["query"]].append(row)
        recalls, mrrs, ndcgs, precisions = [], [], [], []
        for query, relevant in query_labels.items():
            ranked = sorted(by_query.get(query, []), key=lambda row: row["rank"])
            if len(ranked) != 10:
                raise ValueError(f"{method}: cần đúng Top-10 cho truy vấn {query!r}")
            ids = [row["chunk_id"] for row in ranked]
            if len(set(ids)) != 10:
                raise ValueError(f"{method}: chunk ID trùng trong truy vấn {query!r}")
            hit_ranks = [rank for rank, cid in enumerate(ids, 1) if cid in relevant]
            recalls.append(len(set(ids) & relevant) / len(relevant))
            mrrs.append(1 / hit_ranks[0] if hit_ranks else 0.0)
            dcg = sum(1 / math.log2(rank + 1) for rank in hit_ranks)
            idcg = sum(1 / math.log2(rank + 1) for rank in range(1, min(10, len(relevant)) + 1))
            ndcgs.append(dcg / idcg if idcg else 0.0)
            precisions.append(len(hit_ranks) / 10)
        n = len(query_labels)
        output_rows.append({
            "method": method.upper(), "queries_retrieved": len(dev),
            "queries_scored": n, "queries_excluded_unlabeled": excluded,
            "queries_scored_gold_confirmed": confirmed_queries,
            "queries_scored_candidate_unverified": candidate_queries,
            "recall_at_10": sum(recalls) / n, "mrr_at_10": sum(mrrs) / n,
            "ndcg_at_10": sum(ndcgs) / n, "precision_at_10": sum(precisions) / n,
        })

    write_csv(output_rows, output_path)
    for row in output_rows:
        print(f"{row['method']}: Recall@10={row['recall_at_10']:.4f}, "
              f"MRR@10={row['mrr_at_10']:.4f}, nDCG@10={row['ndcg_at_10']:.4f}, "
              f"Precision@10={row['precision_at_10']:.4f} "
              f"({row['queries_scored']} scored, {row['queries_excluded_unlabeled']} excluded)")
    print(f"CSV: {output_path}")

    # Also score article-level labels from gold_article_ids. This is a distinct
    # metric from exact chunk matching and remains provisional until labels are reviewed.
    article_labels: dict[str, set[str]] = {}
    article_excluded = 0
    for question in dev:
        item = truth[question["id"]]
        labels = set(item.get("gold_article_ids") or [])
        if labels:
            article_labels[question["question"]] = labels
        else:
            article_excluded += 1
    article_rows = []
    for method in ("bm25", "dense", "hybrid"):
        results = normalize_results(read_json(results_dir / f"dev_{method}.json"))
        by_query: dict[str, list[dict]] = defaultdict(list)
        for row in results:
            by_query[row["query"]].append(row)
        recalls, mrrs, ndcgs, precisions = [], [], [], []
        for query, relevant in article_labels.items():
            ranked = sorted(by_query.get(query, []), key=lambda row: row["rank"])
            if len(ranked) != 10:
                raise ValueError(f"{method}: cần đúng Top-10 cho truy vấn {query!r}")
            seen: set[str] = set()
            article_hits: list[tuple[int, str]] = []
            for rank, row in enumerate(ranked, 1):
                article_id = chunk_to_article.get(row["chunk_id"])
                if article_id and article_id not in seen:
                    seen.add(article_id)
                    article_hits.append((rank, article_id))
            hit_ranks = [rank for rank, aid in article_hits if aid in relevant]
            recalls.append(len({aid for rank, aid in article_hits if rank <= 10} & relevant) / len(relevant))
            mrrs.append(1 / hit_ranks[0] if hit_ranks else 0.0)
            dcg = sum(1 / math.log2(rank + 1) for rank in hit_ranks)
            idcg = sum(1 / math.log2(rank + 1) for rank in range(1, min(10, len(relevant)) + 1))
            ndcgs.append(dcg / idcg if idcg else 0.0)
            precisions.append(len(hit_ranks) / 10)
        n = len(article_labels)
        article_rows.append({
            "method": method.upper(), "label_level": "article_id",
            "queries_retrieved": len(dev), "queries_scored": n,
            "queries_excluded_unlabeled": article_excluded,
            "queries_scored_gold_confirmed": sum(
                bool(truth[q["id"]].get("gold_context_ids"))
                and truth[q["id"]].get("gold_context_ids_confirmed") is True
                for q in dev if truth[q["id"]].get("gold_article_ids")
            ),
            "queries_scored_candidate_unverified": sum(
                bool(truth[q["id"]].get("gold_article_ids"))
                and truth[q["id"]].get("gold_context_ids_confirmed") is not True
                for q in dev
            ),
            "recall_at_10": sum(recalls) / n, "mrr_at_10": sum(mrrs) / n,
            "ndcg_at_10": sum(ndcgs) / n, "precision_at_10": sum(precisions) / n,
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
