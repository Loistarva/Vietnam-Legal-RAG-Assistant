#!/usr/bin/env python3
"""Build the immutable D4.4 Dev30 retrieval/rerank precompute artifact.

The script consumes the G3 rerank artifact already pushed on the remote
``results/rerank`` branch. It never runs retrieval or reranking itself.
It selects the official 30 IDs, takes each as_of_date from queries_dev.json,
materializes the exact document_breadcrumb_chunk_text used by the reranker,
and writes JSONL plus a provenance manifest.

Fail-closed guarantees:
- source artifact must be present at the requested remote commit/ref and its
  local bytes must equal the remote Git blob;
- the official TXT must contain exactly 30 unique IDs; an ID manifest is optional
  and, when supplied, is used only as an additional cross-check;
- all 30 IDs must exist exactly once in both benchmark and G3 artifact;
- as_of_date must be present and valid in the benchmark (never default to today);
- source reranker config and local reranker config must use
  document_breadcrumb_chunk_text;
- no output file is overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_IDS = ROOT / "evaluation/rubrics/dev_gold_30_ids_v1.txt"
DEFAULT_BENCHMARK = ROOT / "data/benchmark/queries_dev.json"
DEFAULT_RETRIEVAL_CONFIG = ROOT / "retrieval/config.yaml"
DEFAULT_RERANK_CONFIG = ROOT / "reranking/config.yaml"
DEFAULT_CORPUS = ROOT / "data/chunking_output/chunks.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "evaluation/results/precompute"
DEFAULT_MANIFEST = ROOT / "reports/retrieval/precompute_manifest.json"
EXPECTED_CANDIDATE_TEXT = "document_breadcrumb_chunk_text"
EXPECTED_QUERY_COUNT = 30


class PrecomputeError(RuntimeError):
    """Raised when an input or provenance invariant is not satisfied."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256_bytes(raw)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise PrecomputeError(f"JSON không hợp lệ tại {path}: {exc}") from exc


def read_json_or_jsonl(path: Path) -> Any:
    """Read a normal JSON document, falling back to JSONL when appropriate."""
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        rows: list[Any] = []
        for line_no, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise PrecomputeError(
                    f"G3 artifact không phải JSON/JSONL hợp lệ; lỗi dòng {line_no}: {exc}"
                ) from exc
        if not rows:
            raise PrecomputeError(f"G3 artifact rỗng: {path}")
        return rows


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise PrecomputeError("Thiếu PyYAML. Cài bằng: python -m pip install pyyaml") from exc
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except Exception as exc:
        raise PrecomputeError(f"Không đọc được YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PrecomputeError(f"Config phải là YAML object: {path}")
    return value


def read_official_ids(path: Path, expected_count: int = EXPECTED_QUERY_COUNT) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy danh sách 30 ID: {path}")
    ids = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()
           if line.strip() and not line.lstrip().startswith("#")]
    if len(ids) != expected_count:
        raise PrecomputeError(
            f"Danh sách official phải có đúng {expected_count} ID; hiện có {len(ids)}."
        )
    if any(any(ch.isspace() for ch in item) for item in ids):
        raise PrecomputeError("ID trong dev_gold_30_ids_v1.txt không được chứa khoảng trắng.")
    if len(set(ids)) != len(ids):
        raise PrecomputeError("Danh sách official có ID trùng lặp.")
    return ids


def _walk_manifest_records(value: Any) -> Iterable[dict[str, Any]]:
    """Yield objects that look like per-query records from common manifest layouts."""
    if isinstance(value, dict):
        if isinstance(value.get("id"), str) or isinstance(value.get("query_id"), str):
            yield value
        for key, child in value.items():
            if key in {"items", "records", "queries", "questions", "ids", "query_ids", "manifest"}:
                yield from _walk_manifest_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_manifest_records(child)


def validate_id_manifest(path: Path, official_ids: list[str]) -> dict[str, Any]:
    manifest = read_json(path)
    records = list(_walk_manifest_records(manifest))
    manifest_ids: set[str] = set()
    record_by_id: dict[str, dict[str, Any]] = {}
    for row in records:
        query_id = row.get("query_id") or row.get("id")
        if isinstance(query_id, str) and query_id.strip():
            query_id = query_id.strip()
            manifest_ids.add(query_id)
            record_by_id[query_id] = row

    if manifest_ids != set(official_ids):
        missing = sorted(set(official_ids) - manifest_ids)
        extra = sorted(manifest_ids - set(official_ids))
        raise PrecomputeError(
            "ID manifest không khớp file dev_gold_30_ids_v1.txt. "
            f"Thiếu={missing[:5]}, thừa={extra[:5]}."
        )

    for query_id in official_ids:
        row = record_by_id[query_id]
        split = row.get("split")
        if split is not None and str(split).lower() != "dev":
            raise PrecomputeError(f"{query_id} không thuộc split dev trong ID manifest.")
        review_status = row.get("review_status")
        source_checked = row.get("source_checked")
        if review_status is not None:
            if str(review_status).lower() != "source_checked":
                raise PrecomputeError(f"{query_id} chưa có review_status=source_checked.")
        elif source_checked is not True:
            raise PrecomputeError(
                f"{query_id} thiếu xác nhận source_checked=true trong ID manifest."
            )
        if split is None:
            raise PrecomputeError(f"{query_id} thiếu split=dev trong ID manifest.")

    return manifest


def read_benchmark(path: Path, official_ids: list[str]) -> dict[str, dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, list):
        raise PrecomputeError("queries_dev.json phải là JSON list.")
    by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(data, 1):
        if not isinstance(row, dict):
            raise PrecomputeError(f"Benchmark record #{index} không phải object.")
        query_id = row.get("id") or row.get("query_id")
        if not isinstance(query_id, str) or not query_id.strip():
            raise PrecomputeError(f"Benchmark record #{index} thiếu id/query_id.")
        query_id = query_id.strip()
        if query_id in by_id:
            raise PrecomputeError(f"Benchmark có query ID trùng: {query_id}.")
        question = row.get("question") or row.get("query")
        if not isinstance(question, str) or not question.strip():
            raise PrecomputeError(f"Benchmark {query_id} thiếu question/query.")
        as_of_date = row.get("as_of_date")
        if not isinstance(as_of_date, str) or not as_of_date.strip():
            raise PrecomputeError(
                f"Benchmark {query_id} thiếu as_of_date; D4.4 không được tự lấy ngày hiện tại."
            )
        try:
            parsed = date.fromisoformat(as_of_date.strip())
        except ValueError as exc:
            raise PrecomputeError(
                f"Benchmark {query_id} có as_of_date không hợp lệ: {as_of_date!r}"
            ) from exc
        if parsed.isoformat() != as_of_date.strip():
            raise PrecomputeError(
                f"Benchmark {query_id} as_of_date phải có định dạng YYYY-MM-DD."
            )
        by_id[query_id] = {
            "query_id": query_id,
            "query": question.strip(),
            "as_of_date": parsed.isoformat(),
        }

    missing = sorted(set(official_ids) - set(by_id))
    if missing:
        raise PrecomputeError(f"Có ID official không nằm trong queries_dev.json: {missing[:10]}")
    return {query_id: by_id[query_id] for query_id in official_ids}


def _records_from_artifact(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        if isinstance(data.get("records"), list):
            records = data["records"]
        elif isinstance(data.get("items"), list):
            records = data["items"]
        elif (data.get("query_id") or data.get("id")) and isinstance(data.get("results"), list):
            records = [data]
        else:
            raise PrecomputeError(
                "G3 JSON cần là list các RetrievalEnvelope, object có records/items, "
                "hoặc một RetrievalEnvelope {query_id, query, results, config}."
            )
    else:
        raise PrecomputeError("G3 artifact phải là JSON list/object hoặc JSONL.")

    if not records or any(not isinstance(row, dict) for row in records):
        raise PrecomputeError("G3 artifact có record rỗng hoặc record không phải object.")
    return records


def _get_reranker_config(record: dict[str, Any]) -> dict[str, Any] | None:
    config = record.get("config")
    if isinstance(config, dict):
        for key in ("reranker", "reranking"):
            value = config.get(key)
            if isinstance(value, dict):
                return value
    for key in ("reranker_config", "reranking_config", "reranker"):
        value = record.get(key)
        if isinstance(value, dict):
            return value
    return None


def _get_hit_list(record: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "reranked_results", "hits"):
        value = record.get(key)
        if isinstance(value, list):
            if any(not isinstance(hit, dict) for hit in value):
                raise PrecomputeError(f"G3 record {record.get('query_id') or record.get('id')} có hit không phải object.")
            return value
    raise PrecomputeError(
        f"G3 record {record.get('query_id') or record.get('id')} không có results/reranked_results/hits list."
    )


def load_candidate_text_builder():
    try:
        from reranking.reranker import CANDIDATE_TEXT_MODES, candidate_text as build_candidate_text
    except Exception as exc:
        raise PrecomputeError(
            "Không import được reranking.reranker.candidate_text; chạy script từ repo có module reranking hiện hành."
        ) from exc
    if EXPECTED_CANDIDATE_TEXT not in CANDIDATE_TEXT_MODES:
        raise PrecomputeError(
            "reranking.reranker hiện tại chưa hỗ trợ candidate_text="
            f"{EXPECTED_CANDIDATE_TEXT!r}; cần đồng bộ code với config/PR G3 trước khi chạy."
        )
    return build_candidate_text


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise PrecomputeError(f"Git command thất bại: git {' '.join(args)}\n{stderr}")
    return result


def verify_remote_source(
    artifact_path: Path,
    source_ref: str,
    source_commit: str,
    source_pr_url: str,
) -> dict[str, str]:
    parsed = urlparse(source_pr_url)
    if parsed.scheme != "https" or not parsed.netloc or not re.search(r"/(pull|merge_requests)/\d+", parsed.path):
        raise PrecomputeError("--source-pr-url phải là URL HTTPS của Pull Request/Merge Request.")
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", source_commit):
        raise PrecomputeError("--source-commit phải là full Git SHA (40 hoặc 64 ký tự hex), không dùng SHA rút gọn.")
    if not source_ref or source_ref.startswith("-"):
        raise PrecomputeError("--source-ref không hợp lệ.")
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy G3 artifact local: {artifact_path}")

    rel_path = artifact_path.resolve().relative_to(ROOT.resolve()).as_posix()
    refspec = f"refs/heads/{source_ref}"
    _git(["fetch", "--quiet", "origin", refspec])
    remote_head = _git(["rev-parse", "FETCH_HEAD^{commit}"]).stdout.decode().strip()

    ancestor = _git(["merge-base", "--is-ancestor", source_commit, remote_head], check=False)
    if ancestor.returncode != 0:
        raise PrecomputeError(
            f"Source commit {source_commit} không phải ancestor của remote {refspec} ({remote_head})."
        )

    remote_blob = _git(["show", f"{source_commit}:{rel_path}"]).stdout
    local_bytes = artifact_path.read_bytes()
    if remote_blob != local_bytes:
        raise PrecomputeError(
            "Nội dung G3 artifact local không trùng blob tại source commit trên remote. "
            "Hãy checkout/copy đúng artifact từ remote PR trước khi precompute."
        )

    return {
        "source_ref": refspec,
        "source_commit": source_commit.lower(),
        "remote_ref_head": remote_head,
        "source_pr_url": source_pr_url,
        "source_artifact_path": rel_path,
        "source_artifact_sha256": sha256_bytes(local_bytes),
    }


def _config_values(retrieval_cfg: dict[str, Any], rerank_cfg: dict[str, Any]) -> dict[str, Any]:
    retrieval = retrieval_cfg.get("retrieval")
    hybrid = retrieval_cfg.get("hybrid")
    reranker = rerank_cfg.get("reranker")
    if not isinstance(retrieval, dict) or not isinstance(hybrid, dict):
        raise PrecomputeError("retrieval/config.yaml cần có các mục retrieval và hybrid.")
    if not isinstance(reranker, dict):
        raise PrecomputeError("reranking/config.yaml cần có mục reranker.")

    values = {
        "retrieval_top_k": retrieval.get("retrieval_top_k"),
        # In the current retrieval config, result_top_k is stored as hybrid.top_k.
        "result_top_k": retrieval.get("result_top_k", hybrid.get("top_k")),
        "rrf_k": hybrid.get("rrf_k"),
        "rerank_top_k": reranker.get("rerank_top_k"),
        "max_candidates": reranker.get("max_candidates"),
        "candidate_text": reranker.get("candidate_text"),
        "reranker_backend": reranker.get("backend"),
        "reranker_model": reranker.get("model"),
    }
    expected = {
        "retrieval_top_k": 50,
        "result_top_k": 10,
        "rrf_k": 60,
        "rerank_top_k": 5,
        "max_candidates": 50,
        "candidate_text": EXPECTED_CANDIDATE_TEXT,
        "reranker_backend": "cross_encoder",
    }
    mismatches = {
        key: (values.get(key), expected_value)
        for key, expected_value in expected.items()
        if values.get(key) != expected_value
    }
    if mismatches:
        details = "; ".join(
            f"{key}={actual!r}, expected={expected_value!r}"
            for key, (actual, expected_value) in mismatches.items()
        )
        raise PrecomputeError(f"Config hiện tại không đúng contract D4.4: {details}")
    return values


def build_precompute_records(
    source_records: list[dict[str, Any]],
    benchmark_rows: dict[str, dict[str, Any]],
    official_ids: list[str],
    candidate_text_builder,
    reranker_config_values: dict[str, Any],
) -> list[dict[str, Any]]:
    source_by_id: dict[str, dict[str, Any]] = {}
    for record in source_records:
        query_id = record.get("query_id") or record.get("id")
        if not isinstance(query_id, str) or not query_id.strip():
            raise PrecomputeError("Một G3 record thiếu query_id/id.")
        query_id = query_id.strip()
        if query_id in source_by_id:
            raise PrecomputeError(f"G3 artifact có query ID trùng: {query_id}.")
        source_by_id[query_id] = record

    missing = sorted(set(official_ids) - set(source_by_id))
    if missing:
        raise PrecomputeError(f"G3 artifact thiếu official query IDs: {missing[:10]}.")

    outputs: list[dict[str, Any]] = []
    observed_candidate_mode: set[str] = set()
    for query_id in official_ids:
        source_record = source_by_id[query_id]
        benchmark = benchmark_rows[query_id]
        source_query = source_record.get("query") or source_record.get("question")
        if isinstance(source_query, str) and source_query.strip() != benchmark["query"]:
            raise PrecomputeError(f"Query text G3 không khớp benchmark cho {query_id}.")

        source_rerank_config = _get_reranker_config(source_record)
        if source_rerank_config is None:
            raise PrecomputeError(
                f"G3 record {query_id} không có config.reranker; không thể chứng minh candidate_text mode đã dùng."
            )
        source_rerank_expected = {
            "backend": "cross_encoder",
            "model": reranker_config_values["reranker_model"],
            "rerank_top_k": reranker_config_values["rerank_top_k"],
            "max_candidates": reranker_config_values["max_candidates"],
            "candidate_text": EXPECTED_CANDIDATE_TEXT,
        }
        source_rerank_mismatches = {
            key: (source_rerank_config.get(key), expected)
            for key, expected in source_rerank_expected.items()
            if source_rerank_config.get(key) != expected
        }
        if source_rerank_mismatches:
            details = "; ".join(
                f"{key}={actual!r}, expected={expected!r}"
                for key, (actual, expected) in source_rerank_mismatches.items()
            )
            raise PrecomputeError(f"G3 reranker config không đúng cho {query_id}: {details}")

        source_run_config = source_record.get("config")
        if not isinstance(source_run_config, dict):
            raise PrecomputeError(f"G3 record {query_id} thiếu config snapshot.")
        source_retrieval_config = source_run_config.get("retriever")
        if not isinstance(source_retrieval_config, dict):
            raise PrecomputeError(f"G3 record {query_id} thiếu config.retriever snapshot.")
        source_retrieval_expected = {
            "retrieval_top_k": reranker_config_values["retrieval_top_k"],
            "rrf_k": reranker_config_values["rrf_k"],
        }
        source_retrieval_mismatches = {
            key: (source_retrieval_config.get(key), expected)
            for key, expected in source_retrieval_expected.items()
            if source_retrieval_config.get(key) != expected
        }
        if source_retrieval_mismatches:
            details = "; ".join(
                f"{key}={actual!r}, expected={expected!r}"
                for key, (actual, expected) in source_retrieval_mismatches.items()
            )
            raise PrecomputeError(f"G3 retrieval config không đúng cho {query_id}: {details}")
        observed_candidate_mode.add(EXPECTED_CANDIDATE_TEXT)

        hits = _get_hit_list(source_record)
        if not hits:
            raise PrecomputeError(f"G3 record {query_id} không có reranked candidates.")
        if len(hits) > int(reranker_config_values["rerank_top_k"]):
            raise PrecomputeError(
                f"G3 record {query_id} có {len(hits)} results, vượt rerank_top_k="
                f"{reranker_config_values['rerank_top_k']}."
            )

        output_hits: list[dict[str, Any]] = []
        seen_chunk_ids: set[str] = set()
        for position, raw_hit in enumerate(hits, 1):
            hit = dict(raw_hit)
            chunk_id = hit.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise PrecomputeError(f"G3 {query_id} candidate #{position} thiếu chunk_id.")
            if chunk_id in seen_chunk_ids:
                raise PrecomputeError(f"G3 {query_id} có chunk_id trùng: {chunk_id}.")
            seen_chunk_ids.add(chunk_id)

            chunk_text = hit.get("chunk_text")
            if not isinstance(chunk_text, str) or not chunk_text.strip():
                raise PrecomputeError(f"G3 {query_id}/{chunk_id} thiếu chunk_text.")
            rank = hit.get("rank", position)
            score = hit.get("score")
            if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
                raise PrecomputeError(f"G3 {query_id}/{chunk_id} có rank không hợp lệ.")
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                raise PrecomputeError(f"G3 {query_id}/{chunk_id} thiếu reranker score.")
            metadata = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
            candidate = candidate_text_builder(hit, mode=EXPECTED_CANDIDATE_TEXT)
            if not isinstance(candidate, str) or not candidate.strip():
                raise PrecomputeError(f"Không dựng được candidate_text cho {query_id}/{chunk_id}.")
            if hit.get("candidate_text") is not None and hit["candidate_text"] != candidate:
                raise PrecomputeError(
                    f"candidate_text đã lưu trong G3 không khớp candidate_text dựng lại: {query_id}/{chunk_id}."
                )

            # Keep the full original hit for downstream replay; explicitly materialize
            # the exact scorer input as candidate_text.
            hit["candidate_text"] = candidate
            hit["rank"] = rank
            hit["score"] = float(score)
            hit.setdefault("retrieval_rank", hit.get("source_rank"))
            hit.setdefault("retrieval_score", hit.get("rrf_score"))
            output_hits.append(hit)

        output_hits.sort(key=lambda row: row["rank"])
        ranks = [row["rank"] for row in output_hits]
        if len(set(ranks)) != len(ranks):
            raise PrecomputeError(f"G3 {query_id} có rank trùng.")

        source_config = source_record.get("config")
        outputs.append({
            "schema_version": "d4.4.precomputed_retrieval.v1",
            "query_id": query_id,
            "query": benchmark["query"],
            "as_of_date": benchmark["as_of_date"],
            "as_of_date_source": "data/benchmark/queries_dev.json",
            "precomputed": True,
            "retriever": source_record.get("retriever", "hybrid_reranker"),
            "candidate_text_mode": EXPECTED_CANDIDATE_TEXT,
            "retrieval_config": {
                "retrieval_top_k": reranker_config_values["retrieval_top_k"],
                "result_top_k": reranker_config_values["result_top_k"],
                "rrf_k": reranker_config_values["rrf_k"],
            },
            "reranker_config": {
                "backend": reranker_config_values["reranker_backend"],
                "model": reranker_config_values["reranker_model"],
                "max_candidates": reranker_config_values["max_candidates"],
                "rerank_top_k": reranker_config_values["rerank_top_k"],
                "candidate_text": EXPECTED_CANDIDATE_TEXT,
            },
            "source_run_config": source_config,
            "reranked_result_count": len(output_hits),
            "retrieval_candidate_pool": int(source_retrieval_config["retrieval_top_k"]),
            "results": output_hits,
        })

    if observed_candidate_mode != {EXPECTED_CANDIDATE_TEXT}:
        raise PrecomputeError("Không nhất quán candidate_text mode giữa các G3 records.")
    if len(outputs) != EXPECTED_QUERY_COUNT:
        raise PrecomputeError(f"Output phải có đúng 30 record, nhận được {len(outputs)}.")
    return outputs


def write_new_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise PrecomputeError(f"Từ chối ghi đè artifact đã tồn tại: {path}")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp") as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # Path.rename does not replace an existing target on Windows.
        temp_path.rename(path)
        temp_path = None
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-artifact", type=Path, required=True,
                        help="Local copy of remote G3 artifact, e.g. reranking/results/dev_hybrid_reranker.json")
    parser.add_argument("--source-ref", default="results/rerank",
                        help="Remote branch containing G3; default: results/rerank")
    parser.add_argument("--source-commit", required=True,
                        help="Full commit SHA on remote source branch")
    parser.add_argument("--source-pr-url", required=True,
                        help="Remote PR/MR URL that delivered G3")
    parser.add_argument("--ids", type=Path, default=DEFAULT_IDS)
    parser.add_argument(
        "--id-manifest", type=Path, default=None,
        help="Manifest Dev30 JSON tùy chọn để đối chiếu bổ sung; danh sách TXT vẫn là nguồn IDs chính thức.",
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--retrieval-config", type=Path, default=DEFAULT_RETRIEVAL_CONFIG)
    parser.add_argument("--rerank-config", type=Path, default=DEFAULT_RERANK_CONFIG)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--run-date", default=datetime.now(timezone.utc).strftime("%Y%m%d"),
                        help="Run date YYYYMMDD; default is current UTC date")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    try:
        if not re.fullmatch(r"\d{8}", args.run_date):
            raise PrecomputeError("--run-date phải có định dạng YYYYMMDD.")

        # Resolve relative paths from repository root for predictable PowerShell usage.
        path_args = ("source_artifact", "ids", "id_manifest", "benchmark", "retrieval_config",
                     "rerank_config", "corpus", "output_dir", "manifest_output")
        for name in path_args:
            value = getattr(args, name)
            if value is not None and not value.is_absolute():
                setattr(args, name, ROOT / value)

        if args.output_dir.resolve() == args.manifest_output.parent.resolve():
            # This is allowed; the JSONL and manifest have distinct requested names.
            pass

        print("[1/7] Verify G3 remote PR/ref/commit and artifact blob...")
        remote = verify_remote_source(
            args.source_artifact, args.source_ref, args.source_commit, args.source_pr_url
        )

        print("[2/7] Validate official 30 IDs from TXT...")
        official_ids = read_official_ids(args.ids)
        optional_id_manifest = None
        if args.id_manifest is not None:
            optional_id_manifest = validate_id_manifest(args.id_manifest, official_ids)
        ids_sha = sha256_bytes(("\n".join(official_ids) + "\n").encode("utf-8"))

        print("[3/7] Load benchmark dates and config snapshots...")
        benchmark_rows = read_benchmark(args.benchmark, official_ids)
        retrieval_cfg = read_yaml(args.retrieval_config)
        rerank_cfg = read_yaml(args.rerank_config)
        config_values = _config_values(retrieval_cfg, rerank_cfg)

        config_bundle = {
            "retrieval_config_path": args.retrieval_config.resolve().relative_to(ROOT).as_posix(),
            "retrieval_config_sha256": sha256_file(args.retrieval_config),
            "rerank_config_path": args.rerank_config.resolve().relative_to(ROOT).as_posix(),
            "rerank_config_sha256": sha256_file(args.rerank_config),
            "values": config_values,
        }
        config_bundle_sha = canonical_sha256(config_bundle)
        corpus_sha = sha256_file(args.corpus)
        ids_manifest_sha = sha256_file(args.id_manifest) if args.id_manifest is not None else None
        benchmark_sha = sha256_file(args.benchmark)

        print("[4/7] Parse G3 artifact and build the 30 precomputed records...")
        source_data = read_json_or_jsonl(args.source_artifact)
        source_records = _records_from_artifact(source_data)
        candidate_text_builder = load_candidate_text_builder()
        output_records = build_precompute_records(
            source_records, benchmark_rows, official_ids, candidate_text_builder, config_values
        )

        output_path = args.output_dir / f"{args.run_date}_dev30_retrieval.jsonl"
        if output_path.exists() or args.manifest_output.exists():
            raise PrecomputeError(
                "Output/manifest đã tồn tại. Không ghi đè run official; chọn --run-date khác "
                "hoặc lưu trữ manifest run trước trước khi chạy lại."
            )

        output_bytes = "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
            for row in output_records
        ).encode("utf-8")
        output_sha = sha256_bytes(output_bytes)

        current_git_sha = _git(["rev-parse", "HEAD"]).stdout.decode().strip()
        current_branch = _git(["branch", "--show-current"]).stdout.decode().strip()
        dirty = bool(_git(["status", "--porcelain"]).stdout.strip())

        per_query_dates = {row["query_id"]: row["as_of_date"] for row in output_records}
        manifest = {
            "manifest_schema_version": "d4.4.precompute_manifest.v1",
            "run_id": f"{args.run_date}_dev30_retrieval",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "precomputed": True,
            "split": "dev",
            "query_count": len(output_records),
            "query_ids": official_ids,
            "dataset_ids_sha256": ids_sha,
            "official_ids_file": {
                "path": args.ids.resolve().relative_to(ROOT).as_posix(),
                "sha256": sha256_file(args.ids),
                "count": len(official_ids),
                "selection_source": "official_dev_gold_30_ids_txt",
            },
            "optional_id_manifest": (
                {
                    "path": args.id_manifest.resolve().relative_to(ROOT).as_posix(),
                    "sha256": ids_manifest_sha,
                    "validated": True,
                } if args.id_manifest is not None else None
            ),
            "benchmark_path": args.benchmark.resolve().relative_to(ROOT).as_posix(),
            "benchmark_sha256": benchmark_sha,
            "as_of_date_source": "data/benchmark/queries_dev.json",
            "as_of_dates": per_query_dates,
            "candidate_text": EXPECTED_CANDIDATE_TEXT,
            "retrieval_config": {
                "path": config_bundle["retrieval_config_path"],
                "sha256": config_bundle["retrieval_config_sha256"],
            },
            "rerank_config": {
                "path": config_bundle["rerank_config_path"],
                "sha256": config_bundle["rerank_config_sha256"],
            },
            "config_values": config_values,
            "config_bundle_sha256": config_bundle_sha,
            "corpus_path": args.corpus.resolve().relative_to(ROOT).as_posix(),
            "corpus_sha256": corpus_sha,
            "source_artifact": remote,
            "output_path": output_path.resolve().relative_to(ROOT).as_posix(),
            "output_sha256": output_sha,
            "repository": {
                "branch": current_branch,
                "git_sha": current_git_sha,
                "working_tree_dirty": dirty,
            },
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")

        print("[5/7] Write immutable JSONL...")
        write_new_file(output_path, output_bytes)
        print("[6/7] Write provenance manifest...")
        try:
            write_new_file(args.manifest_output, manifest_bytes)
        except Exception:
            # Avoid leaving a seemingly complete precompute output without its manifest.
            if output_path.exists():
                output_path.unlink()
            raise

        print("[7/7] Verify output SHA and query count...")
        if sha256_file(output_path) != output_sha:
            raise PrecomputeError("Output SHA-256 verification failed after write.")
        written = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        written_ids = [row.get("query_id") for row in written]
        if (
            len(written) != EXPECTED_QUERY_COUNT
            or written_ids != official_ids
            or len(set(written_ids)) != EXPECTED_QUERY_COUNT
            or any(row.get("precomputed") is not True for row in written)
            or any(not row.get("as_of_date") for row in written)
            or any(
                not isinstance(hit.get("candidate_text"), str) or not hit["candidate_text"].strip()
                for row in written for hit in row.get("results", [])
            )
        ):
            raise PrecomputeError(
                "Post-write validation failed: expected exactly 30 ordered IDs, benchmark dates, "
                "precomputed=true, and non-empty candidate_text for every result."
            )

        print(json.dumps({
            "status": "PASS",
            "precomputed": True,
            "query_count": len(written),
            "output": str(output_path),
            "output_sha256": output_sha,
            "manifest": str(args.manifest_output),
            "source_artifact_sha256": remote["source_artifact_sha256"],
            "corpus_sha256": corpus_sha,
            "config_bundle_sha256": config_bundle_sha,
        }, ensure_ascii=False, indent=2))
        return 0

    except (OSError, PrecomputeError, ValueError, KeyError, TypeError) as exc:
        print(f"D4.4 PRECOMPUTE FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
