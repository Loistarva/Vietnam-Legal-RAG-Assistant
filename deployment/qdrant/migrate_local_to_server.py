"""Copy the existing embedded Qdrant collection to a Qdrant server without re-embedding."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import Distance, PointStruct, VectorParams  # noqa: E402

from embedding.vector_store import chunk_file_sha256  # noqa: E402


def portable_path(path: Path) -> str:
    """Keep report paths repository-relative and avoid exposing machine paths."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return "<external-path>"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def payload_digest(point: Any) -> str:
    raw = canonical_json(point.payload or {}).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_all_points(client: QdrantClient, collection: str, batch_size: int) -> list[Any]:
    points: list[Any] = []
    offset = None
    while True:
        page, offset = client.scroll(collection_name=collection, limit=batch_size, offset=offset,
                                     with_payload=True, with_vectors=True)
        points.extend(page)
        if offset is None:
            return points


def point_map(points: list[Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for point in points:
        key = str(point.id)
        if key in result:
            raise RuntimeError(f"Duplicate point ID: {key}")
        result[key] = point
    return result


def payload_digest_map(points: list[Any]) -> dict[str, str]:
    return {str(point.id): payload_digest(point) for point in points}


def aggregate_hash(mapping: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for point_id in sorted(mapping):
        digest.update(point_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(mapping[point_id].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def points_equivalent(source: Any, target: Any, vector_atol: float = 1e-7) -> bool:
    """Require exact IDs/payloads and allow only bounded absolute vector drift."""
    if str(source.id) != str(target.id):
        return False
    if canonical_json(source.payload or {}) != canonical_json(target.payload or {}):
        return False
    source_vector, target_vector = source.vector, target.vector
    if not isinstance(source_vector, list) or not isinstance(target_vector, list):
        return False
    if len(source_vector) != len(target_vector):
        return False
    try:
        return all(
            math.isfinite(float(source_value))
            and math.isfinite(float(target_value))
            and math.isclose(float(source_value), float(target_value), rel_tol=0.0, abs_tol=vector_atol)
            for source_value, target_value in zip(source_vector, target_vector)
        )
    except (TypeError, ValueError):
        return False


def vector_comparison_metrics(source_map: dict[str, Any], target_map: dict[str, Any]) -> dict[str, float]:
    max_abs_diff = 0.0
    min_cosine_similarity = 1.0
    for point_id, source_point in source_map.items():
        source_vector = source_point.vector
        target_vector = target_map[point_id].vector
        if not isinstance(source_vector, list) or not isinstance(target_vector, list):
            raise RuntimeError(f"Point {point_id} has an unsupported vector representation.")
        if len(source_vector) != len(target_vector):
            raise RuntimeError(f"Vector dimension differs for point {point_id}.")
        left = [float(value) for value in source_vector]
        right = [float(value) for value in target_vector]
        if not all(math.isfinite(value) for value in left + right):
            raise RuntimeError(f"Point {point_id} contains a non-finite vector value.")
        max_abs_diff = max(max_abs_diff, max((abs(a - b) for a, b in zip(left, right)), default=0.0))
        dot = sum(a * b for a, b in zip(left, right))
        norm_product = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
        if norm_product == 0:
            raise RuntimeError(f"Point {point_id} has a zero vector norm.")
        cosine = dot / norm_product
        min_cosine_similarity = min(min_cosine_similarity, cosine)
    return {"max_abs_vector_diff": max_abs_diff, "min_cosine_similarity": min_cosine_similarity}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-path", type=Path, default=ROOT / "data/indexes/qdrant_storage")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/chunking_output/chunks.jsonl",
                        help="Corpus JSONL được dùng để đối chiếu SHA chuẩn hóa")
    parser.add_argument("--url", default="http://127.0.0.1:6333")
    parser.add_argument("--collection", default="vietnam_legal_chunks")
    parser.add_argument("--expected-count", type=int, default=2322)
    parser.add_argument("--expected-corpus-sha256", required=True,
                        help="Corpus SHA-256 chuẩn hóa được phép migrate")
    parser.add_argument("--replace-target", action="store_true",
                        help="Xóa và tạo lại collection server hiện tại sau khi source baseline đã xác minh")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--vector-atol", type=float, default=1e-7,
                        help="Maximum allowed absolute vector-coordinate drift during verification.")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/retrieval/d4_3_qdrant_migration.json")
    parser.add_argument("--diagnose-only", action="store_true",
                        help="Read source and target and report differences without writing points.")
    args = parser.parse_args()
    expected_sha = args.expected_corpus_sha256.strip().lower()
    if len(expected_sha) != 64 or any(char not in "0123456789abcdef" for char in expected_sha):
        parser.error("--expected-corpus-sha256 phải là 64 ký tự hex")
    if (args.expected_count < 1 or args.batch_size < 1 or not math.isfinite(args.vector_atol)
            or args.vector_atol < 0):
        parser.error("--expected-count and --batch-size must be positive; --vector-atol must be finite and non-negative")

    sidecar_path = args.source_path.parent / f"{args.collection}_metadata.json"
    if not sidecar_path.is_file():
        raise FileNotFoundError(f"Metadata sidecar not found: {sidecar_path}")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    corpus_sha256 = sidecar.get("corpus_sha256")
    if (sidecar.get("collection_name") != args.collection
            or sidecar.get("chunk_count") != args.expected_count
            or not isinstance(corpus_sha256, str) or len(corpus_sha256) != 64
            or corpus_sha256.lower() != expected_sha):
        raise RuntimeError("Metadata sidecar collection/count/corpus_sha256 does not match migration baseline.")
    actual_corpus_sha = chunk_file_sha256(args.chunks)
    if actual_corpus_sha != expected_sha:
        raise RuntimeError(
            f"Current corpus SHA mismatch: {actual_corpus_sha} != {expected_sha}; migration not started."
        )

    source = QdrantClient(path=str(args.source_path))
    target = QdrantClient(url=args.url, timeout=60)
    try:
        print("[1/6] Reading source collection...")
        source_info = source.get_collection(args.collection)
        source_points = read_all_points(source, args.collection, args.batch_size)
        if len(source_points) != args.expected_count:
            raise RuntimeError(f"Source count mismatch: {len(source_points)} != {args.expected_count}")
        vectors = source_info.config.params.vectors
        if isinstance(vectors, dict):
            raise RuntimeError("Named vectors detected. Stop and review migration strategy.")
        if vectors.size != 1024:
            raise RuntimeError(f"Unexpected dimension: {vectors.size}")
        if vectors.distance != Distance.COSINE:
            raise RuntimeError(f"Unexpected distance: {vectors.distance}")
        if source_info.payload_schema:
            raise RuntimeError("Source has payload indexes; migration strategy requires review.")
        source_map = point_map(source_points)
        source_payload_hash = aggregate_hash(payload_digest_map(source_points))

        print("[2/6] Checking target collection...")
        target_names = {item.name for item in target.get_collections().collections}
        if args.collection in target_names and args.replace_target:
            target.delete_collection(args.collection)
            target_names.remove(args.collection)
            print("Removed existing target collection after validating local source baseline.")
        if args.collection not in target_names:
            if args.diagnose_only:
                raise RuntimeError(f"Target collection does not exist: {args.collection}")
            target.create_collection(args.collection, vectors_config=VectorParams(
                size=vectors.size, distance=vectors.distance))
            print("Created target collection.")
        else:
            target_info = target.get_collection(args.collection)
            target_vectors = target_info.config.params.vectors
            if isinstance(target_vectors, dict):
                raise RuntimeError("Target has unexpected named vectors configuration.")
            if target_vectors.size != vectors.size or target_vectors.distance != vectors.distance:
                raise RuntimeError("Target vector configuration does not match source.")

        print("[3/6] Reading existing target points...")
        target_points = read_all_points(target, args.collection, args.batch_size)
        target_map = point_map(target_points)
        if args.diagnose_only:
            source_by_id = {str(point.id): point for point in source_points}
            target_by_id = {str(point.id): point for point in target_points}
            shared_ids = set(source_by_id) & set(target_by_id)
            payload_mismatches = []
            vector_mismatches = 0
            max_abs_diff = 0.0
            vector_samples = []
            for point_id in shared_ids:
                source_point, target_point = source_by_id[point_id], target_by_id[point_id]
                if (source_point.payload or {}) != (target_point.payload or {}):
                    payload_mismatches.append(point_id)
                source_vector, target_vector = source_point.vector, target_point.vector
                if source_vector != target_vector:
                    vector_mismatches += 1
                    if (isinstance(source_vector, list) and isinstance(target_vector, list)
                            and len(source_vector) == len(target_vector)):
                        delta = max((abs(float(a) - float(b)) for a, b in zip(source_vector, target_vector)),
                                    default=0.0)
                        max_abs_diff = max(max_abs_diff, delta)
                        if len(vector_samples) < 5:
                            vector_samples.append({"point_id": point_id, "max_abs_diff": delta,
                                                   "source_prefix": source_vector[:5],
                                                   "target_prefix": target_vector[:5]})
                    elif len(vector_samples) < 5:
                        vector_samples.append({"point_id": point_id,
                                               "source_vector_type": type(source_vector).__name__,
                                               "target_vector_type": type(target_vector).__name__})
            diagnostic = {
                "mode": "diagnose_only",
                "source_count": len(source_points),
                "target_count": len(target_points),
                "missing_ids": len(set(source_by_id) - set(target_by_id)),
                "extra_ids": len(set(target_by_id) - set(source_by_id)),
                "vector_mismatched_points": vector_mismatches,
                "vector_max_abs_diff": max_abs_diff,
                "payload_mismatched_points": len(payload_mismatches),
                "payload_mismatch_sample": payload_mismatches[:5],
                "vector_mismatch_sample": vector_samples,
            }
            print(json.dumps(diagnostic, ensure_ascii=False, indent=2))
            return
        extra_ids = set(target_map) - set(source_map)
        if extra_ids:
            raise RuntimeError(f"Target contains {len(extra_ids)} unexpected point IDs; no points uploaded.")
        mismatched = [key for key, target_point in target_map.items()
                      if not points_equivalent(source_map[key], target_point, args.vector_atol)]
        if mismatched:
            raise RuntimeError(f"Target has {len(mismatched)} conflicting points; no points overwritten.")
        missing = set(source_map) - set(target_map)
        print(f"Missing points to migrate: {len(missing)}")

        print("[4/6] Upserting missing points...")
        pending = [point for point in source_points if str(point.id) in missing]
        for start in range(0, len(pending), args.batch_size):
            batch = pending[start:start + args.batch_size]
            target.upsert(args.collection, points=[
                PointStruct(id=point.id, vector=point.vector, payload=point.payload or {})
                for point in batch
            ], wait=True)
            print(f"Uploaded {min(start + len(batch), len(pending))}/{len(pending)}")

        print("[5/6] Verifying target...")
        final_points = read_all_points(target, args.collection, args.batch_size)
        final_map = point_map(final_points)
        target_count = target.count(args.collection, exact=True).count
        if target_count != args.expected_count:
            raise RuntimeError(f"Target count mismatch: {target_count} != {args.expected_count}")
        if set(final_map) != set(source_map):
            raise RuntimeError("Source and target point IDs differ.")
        mismatched = [key for key, source_point in source_map.items()
                      if not points_equivalent(source_point, final_map[key], args.vector_atol)]
        if mismatched:
            raise RuntimeError(f"Final verification failed for {len(mismatched)} points.")
        target_payload_hash = aggregate_hash(payload_digest_map(final_points))
        if source_payload_hash != target_payload_hash:
            raise RuntimeError("Source and target ID/payload SHA-256 mismatch.")
        metrics = vector_comparison_metrics(source_map, final_map)

        print("[6/6] Writing migration report...")
        report = {
            "collection": args.collection,
            "qdrant_client_version": version("qdrant-client"),
            "corpus_sha256": corpus_sha256,
            "expected_corpus_sha256": expected_sha,
            "source_path": portable_path(args.source_path),
            "target_url": args.url,
            "point_count": target_count,
            "vector_dimension": vectors.size,
            "distance": vectors.distance.value,
            "source_payload_sha256": source_payload_hash,
            "target_payload_sha256": target_payload_hash,
            "payload_hash_match": source_payload_hash == target_payload_hash,
            "vector_atol": args.vector_atol,
            "vectors_within_tolerance": True,
            "max_abs_vector_diff": metrics["max_abs_vector_diff"],
            "min_cosine_similarity": metrics["min_cosine_similarity"],
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "PASS",
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    main()
