"""Run Hybrid Retrieval + Reranker standalone and print the result JSON.

Examples:
    python scripts/run_retrieval.py --query "Điều kiện kết hôn là gì?" --top-k 5
    python scripts/run_retrieval.py --query "..." --retriever fixture
    python scripts/run_retrieval.py --query "..." --retriever hybrid --reranker cross_encoder \
        --elasticsearch-url http://localhost:9200
    python scripts/run_retrieval.py --queries data/benchmark/queries_dev.json --output out.json

Exit codes: 0 success, 1 retriever/reranker/service error, 2 invalid input or config.
The Dev 4 batch runner for BM25/Dense/Hybrid comparison is ``python -m retrieval.run_dev_retrieval``.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reranking.pipeline import (  # noqa: E402
    FixtureRetriever,
    PipelineError,
    RetrievalPipeline,
    build_hybrid_retriever,
    build_mock_dense_retriever,
    load_retrieval_settings,
)
from reranking.reranker import BACKENDS, DEFAULT_CONFIG_PATH, build_reranker, load_reranker_config  # noqa: E402

RETRIEVERS = ("mock", "fixture", "hybrid")
DEFAULT_CANDIDATES = ROOT / "test" / "fixtures" / "reranker_candidates.json"
DEFAULT_CHUNKS = ROOT / "data" / "chunking_output" / "chunks.jsonl"


class InputError(ValueError):
    """Invalid user input (exit code 2)."""


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid Retrieval + Reranker (Sprint 6, Dev 5)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--query", help="Câu hỏi cần truy xuất")
    source.add_argument("--queries", type=Path,
                        help="JSON list câu hỏi (chuỗi hoặc object có id/query_id và question/query)")
    parser.add_argument("--query-id", default="Q_CLI_001", help="query_id cho chế độ --query")
    parser.add_argument("--top-k", type=int, default=None,
                        help="Số kết quả trả về (mặc định: rerank_top_k trong reranking/config.yaml)")
    parser.add_argument("--retriever", choices=RETRIEVERS, default="mock",
                        help="mock: Dense mock offline trên corpus; fixture: candidate list cố định; "
                             "hybrid: Elasticsearch BM25 + Qdrant + RRF thật")
    parser.add_argument("--reranker", choices=(*BACKENDS, "none"), default=None,
                        help="Ghi đè reranker.backend; 'none' tắt reranking")
    parser.add_argument("--model", default=None, help="Ghi đè reranker.model (backend cross_encoder)")
    parser.add_argument("--retrieval-top-k", type=int, default=None,
                        help="Ghi đè retrieval_top_k (số candidate thô trước reranking)")
    parser.add_argument("--max-candidates", type=int, default=None,
                        help="Ghi đè reranker.max_candidates (trần candidate vào Cross-Encoder)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="reranking/config.yaml")
    parser.add_argument("--retrieval-config", type=Path, default=ROOT / "retrieval" / "config.yaml")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES, help="Fixture cho --retriever fixture")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="Corpus cho --retriever mock")
    parser.add_argument("--elasticsearch-url", default=os.getenv("ELASTICSEARCH_URL"))
    parser.add_argument("--elasticsearch-index", default=os.getenv("ELASTICSEARCH_INDEX"))
    parser.add_argument("--qdrant-path", default=os.getenv("QDRANT_PATH"))
    parser.add_argument("--collection", default="vietnam_legal_chunks")
    parser.add_argument("--dense-model", default=None, help="Ghi đè dense.model của retrieval/config.yaml")
    parser.add_argument("--output", type=Path, default=None, help="Ghi JSON ra file thay vì stdout")
    parser.add_argument("--eval-output", type=Path, default=None,
                        help="Ghi thêm [{question_id, retrieved_chunk_ids}] cho evaluation.metrics.evaluate (Dev 2)")
    parser.add_argument("--allow-test-split", action="store_true",
                        help="Cho phép chạy trên Test set (chỉ dùng cho lần đánh giá chính thức đã khóa cấu hình)")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args(argv)


def read_queries(path: Path, *, allow_test_split: bool) -> list[tuple[str, str]]:
    """Return (query_id, question) pairs; refuse the frozen Test set unless explicitly allowed."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"Không đọc được file câu hỏi {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise InputError("File câu hỏi phải là JSON list không rỗng")
    is_test = "test" in path.stem.casefold() or any(
        isinstance(row, dict) and str(row.get("split", "")).casefold() == "test" for row in data)
    if is_test and not allow_test_split:
        raise InputError("Test set đang đóng băng; chỉ tuning trên Dev set (thêm --allow-test-split cho lần chạy chính thức)")
    queries, seen = [], set()
    for index, row in enumerate(data, 1):
        if isinstance(row, str):
            query_id, question = f"Q_{index:03d}", row
        elif isinstance(row, dict):
            query_id = row.get("query_id") or row.get("id") or f"Q_{index:03d}"
            question = row.get("question") or row.get("query")
        else:
            query_id, question = None, None
        if not isinstance(question, str) or not question.strip():
            raise InputError(f"Câu hỏi #{index} thiếu question/query không rỗng")
        if query_id in seen:
            raise InputError(f"query_id bị trùng: {query_id}")
        seen.add(query_id)
        queries.append((str(query_id), question))
    return queries


def build_pipeline(args: argparse.Namespace) -> RetrievalPipeline:
    settings = load_retrieval_settings(args.retrieval_config)
    if args.retrieval_top_k is not None:
        settings["retrieval_top_k"] = args.retrieval_top_k
    reranker_config = load_reranker_config(
        args.config,
        enabled=False if args.reranker == "none" else (True if args.reranker else None),
        backend=args.reranker if args.reranker not in (None, "none") else None,
        model=args.model,
        max_candidates=args.max_candidates,
    )
    reranker = build_reranker(reranker_config)

    retriever_settings: dict[str, Any] = {}
    if args.retriever == "fixture":
        retriever = FixtureRetriever.from_file(args.candidates)
        retriever_settings["candidates"] = str(args.candidates)
    elif args.retriever == "mock":
        retriever = build_mock_dense_retriever(args.chunks)
        retriever_settings.update(chunks=str(args.chunks), embedding="deterministic_mock")
    else:
        retriever = build_hybrid_retriever(
            settings, elasticsearch_url=args.elasticsearch_url, elasticsearch_index=args.elasticsearch_index,
            qdrant_path=args.qdrant_path, collection=args.collection, dense_model=args.dense_model)
        retriever_settings.update(rrf_k=settings["rrf_k"], dense_model=args.dense_model or settings["dense_model"],
                                  bm25_index=args.elasticsearch_index or settings["bm25_index"],
                                  collection=args.collection)
    return RetrievalPipeline(retriever, reranker, retrieval_top_k=settings["retrieval_top_k"],
                             retriever_name=args.retriever, retriever_settings=retriever_settings)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        if args.query is not None:
            if not args.query.strip():
                raise InputError("--query không được rỗng")
            queries = [(args.query_id, args.query)]
        else:
            queries = read_queries(args.queries, allow_test_split=args.allow_test_split)
        pipeline = build_pipeline(args)
        outputs = [pipeline.run(question, args.top_k, query_id=query_id) for query_id, question in queries]
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (ValueError, FileNotFoundError) as exc:  # bad flags, config, query or input file
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # services, missing packages, model loading
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    payload = outputs[0] if args.query is not None else outputs
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        write_json(args.output, text)
        print(f"Đã ghi {len(outputs)} kết quả -> {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text + "\n")
    if args.eval_output:
        rows = [{"question_id": output["query_id"],
                 "retrieved_chunk_ids": [row["chunk_id"] for row in output["results"]]} for output in outputs]
        write_json(args.eval_output, json.dumps(rows, ensure_ascii=False, indent=2))
        print(f"Đã ghi file cho evaluation -> {args.eval_output}", file=sys.stderr)
    return 0


def write_json(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8")
            except (AttributeError, ValueError):
                pass
    raise SystemExit(main())
