"""Run BM25, dense, and RRF retrieval over one shared Dev query JSON file."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding.dense_retriever import DenseRetriever
from embedding.vector_store import LegalVectorStore, chunk_file_sha256
from embedding.model_registry import ModelRegistry
from reranking.pipeline import to_contract_result
from retrieval.hybrid_retriever import (
    ElasticsearchBM25Retriever,
    HybridRetriever,
    HybridSearchConfig,
)
from retrieval.settings import DEFAULT_CONFIG_PATH, ROOT as SETTINGS_ROOT, load_settings
from retrieval.temporal import normalize_as_of_date


def resolve_run_config(settings: dict[str, Any], *, top_k: int | None = None,
                       candidate_k: int | None = None, rrf_k: int | None = None,
                       model: str | None = None, collection: str | None = None,
                       elasticsearch_index: str | None = None,
                       chunks: Path | None = None) -> dict[str, Any]:
    """Resolve CLI overrides over the shared config and return the exact run contract."""
    registry = ModelRegistry(settings)
    selected_model = model or settings["dense"]["model"]
    model_spec = registry.get_model(selected_model)
    resolved = {
        "top_k": top_k if top_k is not None else settings["retrieval"]["result_top_k"],
        "candidate_k": candidate_k if candidate_k is not None else settings["retrieval"]["retrieval_top_k"],
        "rrf_k": rrf_k if rrf_k is not None else settings["hybrid"]["rrf_k"],
        "dense_model": selected_model,
        "dimension": model_spec["dimension"],
        "collection": collection or settings["dense"]["collection"],
        "qdrant_storage_path": str(resolve_qdrant_storage_path(settings)),
        "elasticsearch_index": elasticsearch_index or settings["bm25"]["index"],
        "chunks": str(chunks) if chunks is not None else settings["retrieval"]["corpus_path"],
        "fusion": settings["hybrid"]["fusion"],
    }
    if resolved["top_k"] < 1 or resolved["candidate_k"] < resolved["top_k"]:
        raise ValueError("Cần top_k >= 1 và candidate_k >= top_k")
    if resolved["rrf_k"] < 1:
        raise ValueError("rrf_k phải là số nguyên dương")
    return resolved


def resolve_qdrant_storage_path(settings: dict[str, Any], *,
                                env_path: str | Path | None = None) -> Path:
    """Resolve Qdrant storage from QDRANT_PATH or shared dense.index_dir."""
    if env_path is not None:
        path = Path(env_path)
    elif os.getenv("QDRANT_PATH"):
        # Backward-compatible override: QDRANT_PATH points directly at Qdrant storage.
        path = Path(os.environ["QDRANT_PATH"])
    else:
        index_dir = Path(settings["dense"]["index_dir"])
        if not index_dir.is_absolute():
            index_dir = SETTINGS_ROOT / index_dir
        path = index_dir / "qdrant_storage"
    if not path.is_absolute():
        path = SETTINGS_ROOT / path
    return path


def read_queries(path: Path) -> list[tuple[str, str, str]]:
    """Return (query_id, query, as_of_date) rows; missing dates use today's date."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được Dev query file {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ValueError("Dev set phải là JSON list không rỗng")
    queries = []
    for index, row in enumerate(data, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Dev query #{index} phải là object có id và question")
        query_id = row.get("id") or row.get("query_id")
        query = row.get("query") or row.get("question")
        try:
            as_of_date = normalize_as_of_date(row.get("as_of_date"))
        except ValueError as exc:
            raise ValueError(f"Dev query #{index} ({query_id or 'chưa có id'}) có as_of_date sai: {exc}") from exc
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"Dev query #{index} thiếu id")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"Dev query {query_id} thiếu question không rỗng")
        queries.append((query_id.strip(), query.strip(), as_of_date))
    if len({query_id for query_id, _, _ in queries}) != len(queries):
        raise ValueError("Dev query file có id trùng lặp")
    return queries


def count_chunks(path: Path) -> int:
    """Count and validate chunk IDs without requiring a dense-index payload schema."""
    try:
        if path.suffix.lower() == ".jsonl":
            data = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip()]
        else:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được chunk file {path}: {exc}") from exc
    chunks = data if isinstance(data, list) else data.get("chunks") if isinstance(data, dict) else None
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Chunk file phải là JSON list không rỗng hoặc object có trường chunks")
    chunk_ids = [str(row.get("chunk_id") or row.get("id") or "").strip()
                 for row in chunks if isinstance(row, dict)]
    if len(chunk_ids) != len(chunks) or any(not chunk_id for chunk_id in chunk_ids):
        raise ValueError("Mỗi chunk phải là object có chunk_id hoặc id không rỗng")
    if len(set(chunk_ids)) != len(chunk_ids):
        raise ValueError("Chunk file có chunk_id trùng lặp")
    return len(chunks)


def to_envelope(method: str, query_id: str, query: str, hits: list[dict[str, Any]],
                config: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    """One RetrievalEnvelope per query and method (data_contract.md mục 5.4)."""
    results = []
    for rank, hit in enumerate(hits, 1):
        row = to_contract_result(hit)
        row["rank"] = rank
        results.append(row)
    return {
        "query_id": query_id,
        "query": query,
        "retriever": method,
        "results": results,
        "latency_ms": latency_ms,
        "top_k": config["top_k"],
        "config": config,
    }


class TimedRetriever:
    """Transparent search wrapper recording one branch's wall-clock time."""

    def __init__(self, retriever: Any):
        self.retriever = retriever
        self.last_latency_ms = 0.0

    def search(self, query: str, top_k: int, *, as_of_date: str | None = None) -> list[dict[str, Any]]:
        started = time.perf_counter()
        try:
            return self.retriever.search(query, top_k, as_of_date=as_of_date)
        finally:
            self.last_latency_ms = round((time.perf_counter() - started) * 1000.0, 3)


def latency_by_method(sparse: TimedRetriever, dense: TimedRetriever,
                      hybrid_latency_ms: float) -> dict[str, float]:
    """Return branch-level timings and the end-to-end Hybrid timing separately."""
    return {
        "bm25": sparse.last_latency_ms,
        "dense": dense.last_latency_ms,
        "hybrid": hybrid_latency_ms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH,
                        help="Shared Retrieval YAML config")
    parser.add_argument("--queries", type=Path, default=ROOT / "data" / "benchmark" / "queries_dev.json",
                        help='Benchmark query file: JSON list of objects with id and question')
    parser.add_argument("--chunks", type=Path, default=None,
                        help="Corpus override; default retrieval.corpus_path from shared config")
    parser.add_argument("--model", default=None,
                        help="Dense model override; default dense.model from shared config")
    parser.add_argument("--collection", default=None,
                        help="Qdrant collection đã nạp đúng model và chunk fixture")
    parser.add_argument("--elasticsearch-url", default=os.getenv("ELASTICSEARCH_URL"),
                        help="URL Elasticsearch (hoặc đặt biến ELASTICSEARCH_URL)")
    parser.add_argument("--elasticsearch-index", default=None,
                        help="Elasticsearch index override; default bm25.index from shared config")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "retrieval" / "results")
    parser.add_argument("--top-k", type=int, default=None,
                        help="Override retrieval.result_top_k")
    parser.add_argument("--candidate-k", type=int, default=None,
                        help="Override retrieval.retrieval_top_k")
    parser.add_argument("--rrf-k", type=int, default=None,
                        help="Override hybrid.rrf_k")
    args = parser.parse_args()
    try:
        settings = load_settings(args.config)
        run_config = resolve_run_config(
            settings, top_k=args.top_k, candidate_k=args.candidate_k, rrf_k=args.rrf_k,
            model=args.model, collection=args.collection,
            elasticsearch_index=args.elasticsearch_index, chunks=args.chunks,
        )
        chunks_path = args.chunks or Path(settings["retrieval"]["corpus_path"])
        if not chunks_path.is_absolute():
            chunks_path = SETTINGS_ROOT / chunks_path
        run_config["chunks"] = str(chunks_path)
        run_config["corpus_sha256"] = chunk_file_sha256(chunks_path)
        queries = read_queries(args.queries)
        chunk_count = count_chunks(chunks_path)
        if not args.elasticsearch_url:
            raise ValueError("Cần --elasticsearch-url hoặc biến ELASTICSEARCH_URL; sparse/BM25 được Elasticsearch xử lý")
        try:
            from elasticsearch import Elasticsearch
        except ImportError as exc:
            raise RuntimeError("Cần cài elasticsearch client để chạy retrieval theo kiến trúc") from exc
        es_client = Elasticsearch(args.elasticsearch_url)
        if not es_client.ping():
            raise ConnectionError(f"Không kết nối được Elasticsearch tại {args.elasticsearch_url}")
        if not es_client.indices.exists(index=run_config["elasticsearch_index"]):
            raise ValueError(f"Elasticsearch index không tồn tại: {run_config['elasticsearch_index']}; nạp child chunks trước")
        sparse = TimedRetriever(ElasticsearchBM25Retriever(
            es_client, run_config["elasticsearch_index"],
            text_field=settings["bm25"]["text_field"], settings=settings,
        ))
        bm25_metadata = sparse.retriever._verify_index_tokenizer()
        if bm25_metadata.get("corpus_sha256") != run_config["corpus_sha256"]:
            raise ValueError(
                "Elasticsearch BM25 index được dựng từ corpus khác với corpus benchmark "
                "(corpus_sha256 không khớp)."
            )
        dimension = run_config["dimension"]
        collection = run_config["collection"]
        qdrant_path = Path(run_config["qdrant_storage_path"])
        store = LegalVectorStore(
            collection_name=collection,
            dimension=dimension,
            storage_path=qdrant_path,
        )
        count = store.count()
        if count != chunk_count:
            raise ValueError(f"Collection {collection} có {count} points, fixture có {chunk_count} chunks")
        dense = TimedRetriever(DenseRetriever(
            vector_store=store, model_name=run_config["dense_model"],
            corpus_path=chunks_path, settings=settings,
        ))
        config = HybridSearchConfig(top_k=run_config["top_k"],
                                    candidate_k=run_config["candidate_k"], rrf_k=run_config["rrf_k"])
        hybrid_retriever = HybridRetriever(sparse, dense, config)
        run_config["latency_measurement"] = (
            "bm25_and_dense_branch_wall_time; hybrid_end_to_end_pipeline_wall_time"
        )

        saved: dict[str, list[dict[str, Any]]] = {"bm25": [], "dense": [], "hybrid": []}
        for query_id, query, query_as_of_date in queries:
            started = time.perf_counter()
            ranked = hybrid_retriever.retrieve(query, as_of_date=query_as_of_date)
            hybrid_latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            per_method_latency = latency_by_method(sparse, dense, hybrid_latency_ms)
            for method in saved:
                query_config = {**run_config, "as_of_date": query_as_of_date}
                saved[method].append(to_envelope(
                    method, query_id, query, ranked[method], query_config, per_method_latency[method]
                ))

        args.output_dir.mkdir(parents=True, exist_ok=True)
        for method, envelopes in saved.items():
            destination = args.output_dir / f"dev_{method}.json"
            destination.write_text(json.dumps(envelopes, ensure_ascii=False, indent=2), encoding="utf-8")
            hits = sum(len(envelope["results"]) for envelope in envelopes)
            print(f"{method}: {hits} hits / {len(envelopes)} queries -> {destination}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
