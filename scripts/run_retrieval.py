"""Run Hybrid Retrieval + Reranker standalone and print the result JSON.

The defaults follow the architecture: Hybrid (Elasticsearch BM25 + Qdrant + RRF) and the
bge-reranker-v2-m3 cross-encoder. The mock retriever and the mock scorer are opt-in.

Examples:
    python scripts/run_retrieval.py --query "Điều kiện kết hôn là gì?" --top-k 5 \
        --elasticsearch-url http://localhost:9200
    python scripts/run_retrieval.py --query "..." --retriever fixture --reranker mock   # offline
    python scripts/run_retrieval.py --queries data/benchmark/queries_dev.json --output out.json

Two processes, when the dense model and the reranker do not fit in memory together:
    python scripts/run_retrieval.py --queries data/benchmark/queries_dev.json --reranker none \
        --no-parent-context --top-k 50 --output candidates.json
    python scripts/run_retrieval.py --queries data/benchmark/queries_dev.json --retriever precomputed \
        --candidates candidates.json --output reranked.json

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
    PrecomputedRetriever,
    RetrievalPipeline,
    build_hybrid_retriever,
    build_mock_dense_retriever,
    load_retrieval_settings,
)
from reranking.parent_context import ParentContextResolver, load_parent_context_config  # noqa: E402
from reranking.reranker import BACKENDS, DEFAULT_CONFIG_PATH, build_reranker, load_reranker_config  # noqa: E402

logger = logging.getLogger("run_retrieval")
RETRIEVERS = ("hybrid", "precomputed", "mock", "fixture")
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
    parser.add_argument("--as-of-date", default=None,
                        help="Thời điểm áp dụng luật (YYYY-MM-DD) cho --query, và cho các câu của --queries "
                             "không có as_of_date")
    parser.add_argument("--no-parent-context", action="store_true",
                        help="Tắt Parent-Context Resolver (mặc định theo parent_context.enabled)")
    parser.add_argument("--top-k", type=int, default=None,
                        help="Số kết quả trả về (mặc định: rerank_top_k trong reranking/config.yaml)")
    parser.add_argument("--retriever", choices=RETRIEVERS, default="hybrid",
                        help="hybrid: Elasticsearch BM25 + Qdrant + RRF thật (mặc định); precomputed: candidate "
                             "của lần chạy --reranker none trước đó (--candidates); mock: Dense mock offline trên "
                             "corpus; fixture: candidate list cố định")
    parser.add_argument("--reranker", choices=(*BACKENDS, "none"), default=None,
                        help="Ghi đè reranker.backend (mặc định cross_encoder); mock: tỉ lệ token trùng, "
                             "chỉ để chạy offline; 'none' tắt reranking")
    parser.add_argument("--model", default=None, help="Ghi đè reranker.model (backend cross_encoder)")
    parser.add_argument("--retrieval-top-k", type=int, default=None,
                        help="Ghi đè retrieval_top_k (số candidate thô trước reranking)")
    parser.add_argument("--max-candidates", type=int, default=None,
                        help="Ghi đè reranker.max_candidates (trần candidate vào Cross-Encoder)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="reranking/config.yaml")
    parser.add_argument("--retrieval-config", type=Path, default=ROOT / "retrieval" / "config.yaml")
    parser.add_argument("--candidates", type=Path, default=None,
                        help="--retriever precomputed: file --output của lần chạy --reranker none (bắt buộc); "
                             "--retriever fixture: candidate list (mặc định test/fixtures/reranker_candidates.json)")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="Corpus cho --retriever mock")
    parser.add_argument("--elasticsearch-url", default=os.getenv("ELASTICSEARCH_URL"))
    parser.add_argument("--elasticsearch-index", default=os.getenv("ELASTICSEARCH_INDEX"))
    parser.add_argument("--qdrant-path", default=os.getenv("QDRANT_PATH"))
    parser.add_argument("--collection", default="vietnam_legal_chunks")
    parser.add_argument("--dense-model", default=None, help="Ghi đè dense.model của retrieval/config.yaml")
    parser.add_argument("--output", type=Path, default=None, help="Ghi JSON ra file thay vì stdout")
    parser.add_argument("--eval-output", type=Path, default=None,
                        help="Ghi thêm [{query_id, retrieved_chunk_ids}] cho evaluation.metrics.evaluate (Dev 2)")
    parser.add_argument("--allow-test-split", action="store_true",
                        help="Cho phép chạy trên Test set (chỉ dùng cho lần đánh giá chính thức đã khóa cấu hình)")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args(argv)


def read_queries(path: Path, *, allow_test_split: bool,
                 default_as_of_date: str | None = None) -> list[tuple[str, str, str | None]]:
    """Return (query_id, question, as_of_date) triples; refuse the frozen Test set unless explicitly allowed.

    ``as_of_date`` comes from the question row (benchmark field), else ``default_as_of_date``.
    """
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
        as_of_date = default_as_of_date
        if isinstance(row, str):
            query_id, question = f"Q_{index:03d}", row
        elif isinstance(row, dict):
            query_id = row.get("query_id") or row.get("id") or f"Q_{index:03d}"
            question = row.get("question") or row.get("query")
            as_of_date = row.get("as_of_date") or default_as_of_date
        else:
            query_id, question = None, None
        if not isinstance(question, str) or not question.strip():
            raise InputError(f"Câu hỏi #{index} thiếu question/query không rỗng")
        if query_id in seen:
            raise InputError(f"query_id bị trùng: {query_id}")
        seen.add(query_id)
        queries.append((str(query_id), question, as_of_date))
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
    parent_config = load_parent_context_config(args.config, enabled=False if args.no_parent_context else None)
    parent_resolver = ParentContextResolver.from_config(parent_config) if parent_config.enabled else None
    if args.retriever in ("mock", "fixture"):
        logger.warning("--retriever %s: candidate không đến từ truy xuất thật, thứ hạng không mang nghĩa", args.retriever)
    if reranker is not None and reranker.backend == "mock":
        logger.warning("Reranker backend mock: điểm là tỉ lệ token trùng, không phải mô hình liên quan "
                       "(dùng --reranker cross_encoder cho số đo thật)")

    retriever_settings: dict[str, Any] = {}
    retriever_name = args.retriever
    if args.retriever == "fixture":
        candidates = args.candidates or DEFAULT_CANDIDATES
        retriever = FixtureRetriever.from_file(candidates)
        retriever_settings["candidates"] = str(candidates)
    elif args.retriever == "precomputed":
        if args.candidates is None:
            raise ValueError("--retriever precomputed cần --candidates (file --output của lần chạy --reranker none)")
        retriever = PrecomputedRetriever.from_file(args.candidates)
        # Results keep the label of the retriever that produced the candidates (e.g. hybrid_reranker).
        source = retriever.source_settings
        retriever_name = str(source.get("backend") or "precomputed")
        retriever_settings.update({key: value for key, value in source.items()
                                   if key not in ("backend", "retrieval_top_k")})
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
                             retriever_name=retriever_name, retriever_settings=retriever_settings,
                             parent_resolver=parent_resolver)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        if args.query is not None:
            if not args.query.strip():
                raise InputError("--query không được rỗng")
            queries = [(args.query_id, args.query, args.as_of_date)]
        else:
            queries = read_queries(args.queries, allow_test_split=args.allow_test_split,
                                   default_as_of_date=args.as_of_date)
        pipeline = build_pipeline(args)
        outputs = [pipeline.run(question, args.top_k, query_id=query_id, as_of_date=as_of_date)
                   for query_id, question, as_of_date in queries]
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
        rows = [{"query_id": output["query_id"],
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
