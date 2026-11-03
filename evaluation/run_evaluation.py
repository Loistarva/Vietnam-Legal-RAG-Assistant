"""Shared helpers for scoring saved retrieval results."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import DEFAULT_KS, evaluate


def read_json_array(path: Path) -> list[dict[str, Any]]:
    try:
        content = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được {path}: {exc}") from exc
    if not isinstance(content, list):
        raise ValueError(f"{path} phải chứa JSON array.")
    if not all(isinstance(item, dict) for item in content):
        raise ValueError(f"Mỗi phần tử trong {path} phải là JSON object.")
    return content


def load_parent_ids(chunks_path: Path) -> dict[str, str]:
    parent_by_chunk: dict[str, str] = {}
    try:
        with chunks_path.open("r", encoding="utf-8-sig") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"JSONL lỗi tại {chunks_path}:{line_number}: {exc}"
                    ) from exc
                if not isinstance(chunk, dict):
                    raise ValueError(
                        f"Chunk tại {chunks_path}:{line_number} phải là JSON object."
                    )
                chunk_id = chunk.get("chunk_id")
                if not isinstance(chunk_id, str) or not chunk_id.strip():
                    raise ValueError(
                        f"Chunk tại {chunks_path}:{line_number} thiếu chunk_id."
                    )
                parent_id = chunk.get("parent_clause_id")
                if isinstance(parent_id, str) and parent_id.strip():
                    previous = parent_by_chunk.get(chunk_id)
                    if previous is not None and previous != parent_id:
                        raise ValueError(
                            f"Chunk {chunk_id!r} có parent_clause_id mâu thuẫn."
                        )
                    parent_by_chunk[chunk_id] = parent_id
    except OSError as exc:
        raise ValueError(f"Không đọc được corpus {chunks_path}: {exc}") from exc
    return parent_by_chunk


def normalize_results(
    results_path: Path,
    method: str | None,
    expected_query_ids: set[str],
) -> list[dict[str, Any]]:
    envelopes = read_json_array(results_path)
    normalized: list[dict[str, Any]] = []
    seen_query_ids: set[str] = set()

    for envelope in envelopes:
        query_id = envelope.get("query_id")
        if not isinstance(query_id, str) or query_id not in expected_query_ids:
            raise ValueError(
                f"{results_path} chứa query_id không thuộc query set: {query_id!r}"
            )
        if query_id in seen_query_ids:
            raise ValueError(f"{results_path} có query_id trùng: {query_id}")
        if method is not None and envelope.get("retriever") != method:
            raise ValueError(
                f"{results_path}: query {query_id} khai báo retriever "
                f"{envelope.get('retriever')!r}, mong đợi {method!r}."
            )
        results = envelope.get("results")
        if not isinstance(results, list):
            raise ValueError(
                f"{results_path}: query {query_id} thiếu mảng results."
            )
        ranked: list[dict[str, Any]] = []
        for result in results:
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("rank"), int)
                or isinstance(result.get("rank"), bool)
                or not isinstance(result.get("chunk_id"), str)
            ):
                raise ValueError(
                    f"{results_path}: chunk result không hợp lệ cho {query_id}."
                )
            ranked.append(result)
        ranked.sort(key=lambda result: result["rank"])
        if len({result["rank"] for result in ranked}) != len(ranked):
            raise ValueError(f"{results_path}: rank bị trùng cho {query_id}.")
        if len({result["chunk_id"] for result in ranked}) != len(ranked):
            raise ValueError(f"{results_path}: chunk_id bị trùng cho {query_id}.")

        normalized.append({
            "query_id": query_id,
            "retrieved_chunk_ids": [result["chunk_id"] for result in ranked],
            "retrieved_parent_clause_ids": [
                result.get("parent_clause_id") for result in ranked
            ],
            "category": envelope.get("category"),
        })
        seen_query_ids.add(query_id)

    missing_query_ids = expected_query_ids - seen_query_ids
    if missing_query_ids:
        raise ValueError(
            f"{results_path} thiếu query: {', '.join(sorted(missing_query_ids))}"
        )
    return normalized


def run_evaluation(
    results_path: Path,
    queries: Sequence[dict[str, Any]],
    ground_truth_path: Path,
    metrics_path: Path,
    *,
    expected_split: str,
    top_k: int = 10,
    method: str | None = None,
    parent_by_chunk: Mapping[str, str] | None = None,
    ks: Sequence[int] | None = None,
    report_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one saved retrieval file against an explicitly supplied query set."""
    if top_k < 1:
        raise ValueError("top_k phải lớn hơn 0")
    effective_ks = tuple(ks) if ks is not None else DEFAULT_KS

    query_ids: set[str] = set()
    query_by_id: dict[str, dict[str, Any]] = {}
    for position, query in enumerate(queries, start=1):
        query_id = query.get("id")
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"Query thứ {position} thiếu id hợp lệ.")
        if query_id in query_ids:
            raise ValueError(f"Query id bị trùng: {query_id}")
        query_ids.add(query_id)
        query_by_id[query_id] = query
    if not query_ids:
        raise ValueError("Tập queries phải không rỗng.")

    truth = read_json_array(ground_truth_path)
    truth_by_id = {
        row.get("id"): row
        for row in truth
        if isinstance(row.get("id"), str)
    }
    for query_id in query_ids:
        label = truth_by_id.get(query_id)
        if label is None or label.get("split") != expected_split:
            raise ValueError(
                f"Query {query_id!r} không thuộc split {expected_split} "
                "trong ground truth."
            )

    normalized = normalize_results(results_path, method, query_ids)
    for item in normalized:
        category = item.get("category") or query_by_id[item["query_id"]].get("category")
        if category:
            item["category"] = category

    with tempfile.TemporaryDirectory(prefix="retrieval-evaluation-") as temp_dir:
        normalized_path = Path(temp_dir) / "normalized_results.json"
        normalized_path.write_text(
            json.dumps(normalized, ensure_ascii=False), encoding="utf-8"
        )
        report = evaluate(
            normalized_path,
            ground_truth_path,
            output_path=metrics_path,
            ks=effective_ks,
            parent_by_chunk=parent_by_chunk,
            verified_only=True,
            report_metadata=report_metadata,
        )

    missing_parent_rows = [
        row
        for row in report["per_question"]
        if row.get("parent_match_metadata_missing")
    ]
    if missing_parent_rows:
        print(
            "Thiếu metadata parent cho "
            f"{len(missing_parent_rows)} câu (Parent Recall không tính được):"
        )
        for row in missing_parent_rows:
            query = query_by_id[row["query_id"]]
            question = query.get("question") or query.get("query")
            cutoffs = [
                f"@{k}"
                for k in effective_ks
                if row.get(f"parent_match_metadata_missing@{k}")
            ]
            print(
                f"  - {row['query_id']} [{', '.join(cutoffs)}]: "
                f"{question or '(không có nội dung câu hỏi)'}"
            )
    else:
        print("Không có câu nào thiếu metadata parent.")
    return report


if __name__ == "__main__":
    raise SystemExit(
        "evaluation.run_evaluation is a shared helper module, not a CLI. "
        "Run saved Dev metrics with: python scripts/run_baselines_metrics.py"
    )
