"""Create isolated Config A/B/C chunk files and map Dev proposal labels by text."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chunking.chunking_rules import chunk_legal_document  # noqa: E402
from chunking.run_experiment import CONFIGS, load_test_documents  # noqa: E402

VARIANTS = {
    "A": "Config A (Baseline - Khuyến nghị)",
    "B": "Config B (Small - Fine-grained)",
    "C": "Config C (Large - Broad Context)",
    "E": "Config E (350 words - 256 token cap)",
}

EXTRA_CONFIGS = {
    "Config E (350 words - 256 token cap)": {
        "parent_max_chars": 1500,
        "child_max_tokens": 256,
        "child_max_units": 350,
        "child_min_words": 30,
        "mo_ta": "Thử chunk con dài hơn nhưng giữ giới hạn token của model; Parent tối đa 1500 ký tự.",
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def chunk_tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)


def is_contiguous_part(shorter: list[str], longer: list[str]) -> bool:
    if not shorter or len(shorter) > len(longer):
        return False
    first = shorter[0]
    for start, token in enumerate(longer):
        if token == first and longer[start:start + len(shorter)] == shorter:
            return True
    return False


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants")
    parser.add_argument("--base-chunks", type=Path, default=ROOT / "data/chunking_output/chunks.jsonl")
    parser.add_argument("--queries", type=Path, default=ROOT / "data/benchmark/queries_dev.json")
    parser.add_argument("--labels", type=Path, default=ROOT / "data/benchmark/gold_id_proposals_300.json")
    args = parser.parse_args()
    try:
        docs = load_test_documents()
        if not docs:
            raise ValueError("Không tìm thấy parsed documents trong parser/parsed_jsons")
        base_rows = read_jsonl(args.base_chunks)
        base_by_id = {row.get("chunk_id") or row.get("id"): row for row in base_rows}
        if len(base_by_id) != len(base_rows):
            raise ValueError("chunks.jsonl có chunk_id thiếu hoặc trùng")

        variant_chunks: dict[str, list[dict[str, Any]]] = {}
        variant_reports: dict[str, dict[str, Any]] = {}
        for variant, config_name in VARIANTS.items():
            params = CONFIGS.get(config_name) or EXTRA_CONFIGS[config_name]
            children: list[dict[str, Any]] = []
            parents: list[dict[str, Any]] = []
            failures: list[str] = []
            for doc_name, doc in docs.items():
                try:
                    result = chunk_legal_document(doc, params)
                except Exception as exc:
                    failures.append(f"{doc_name}: {type(exc).__name__}: {exc}")
                    continue
                children.extend(result.get_qdrant_payloads())
                parents.extend(result.get_parent_store_records())
            if failures:
                raise ValueError(f"Chunking {variant} lỗi ở {len(failures)} văn bản: {failures[:5]}")
            child_ids = [row.get("chunk_id") or row.get("id") for row in children]
            parent_ids = [row.get("parent_id") for row in parents]
            duplicates = [item for item, count in Counter(child_ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Config {variant} sinh chunk_id trùng: {duplicates[:10]}")

            destination = args.output_dir / variant
            destination.mkdir(parents=True, exist_ok=True)
            chunks_path = destination / "chunks.jsonl"
            chunks_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in children),
                encoding="utf-8",
            )
            save_json(destination / "parents.json", parents)
            variant_chunks[variant] = children
            report = {
                "variant": variant,
                "config_name": config_name,
                "chunking_config": {key: value for key, value in params.items() if key != "mo_ta"},
                "num_source_documents": len(docs),
                "num_children": len(children),
                "num_parents": len(parents),
                "num_duplicate_chunk_ids": 0,
                "base_corpus_chunks": len(base_rows),
                "base_chunk_ids_retained": len(set(child_ids) & set(base_by_id)),
                "base_id_and_text_exact_match_count": sum(
                    cid in base_by_id and
                    (base_by_id[cid].get("text") or base_by_id[cid].get("chunk_text")) ==
                    next(row.get("text") or row.get("chunk_text") for row in children
                         if (row.get("chunk_id") or row.get("id")) == cid)
                    for cid in set(child_ids) & set(base_by_id)
                ),
                "chunks_file": str(chunks_path.relative_to(ROOT)) if chunks_path.is_relative_to(ROOT) else str(chunks_path),
                "parents_file": str((destination / "parents.json").relative_to(ROOT))
                if (destination / "parents.json").is_relative_to(ROOT) else str(destination / "parents.json"),
            }
            save_json(destination / "variant_report.json", report)
            variant_reports[variant] = report
            print(f"Config {variant}: {len(children)} chunks, {len(parents)} parents -> {chunks_path}")

        queries = read_json(args.queries)
        dev_ids = {
            row.get("id") or row.get("query_id")
            for row in queries if str(row.get("split", "dev")).casefold() == "dev"
        }
        proposals = read_json(args.labels)
        proposals_by_id = {row.get("id") or row.get("query_id"): row for row in proposals}
        mapping: dict[str, Any] = {
            "labels_source": str(args.labels.relative_to(ROOT)) if args.labels.is_relative_to(ROOT) else str(args.labels),
            "base_chunks": str(args.base_chunks.relative_to(ROOT)) if args.base_chunks.is_relative_to(ROOT) else str(args.base_chunks),
            "method": "map theo cùng clause_id và đoạn text liên tiếp; không map ID version_*; không sửa file proposal gốc",
            "dev_queries": len(dev_ids),
            "configs": {},
        }

        for variant, rows in variant_chunks.items():
            by_clause: dict[str, list[dict[str, Any]]] = defaultdict(list)
            by_id = {row.get("chunk_id") or row.get("id"): row for row in rows}
            for row in rows:
                by_clause[str(row.get("clause_id") or "")].append(row)
            query_labels: dict[str, list[str]] = {}
            query_details: list[dict[str, Any]] = []
            excluded_invalid: list[dict[str, Any]] = []
            excluded_unmapped: list[dict[str, Any]] = []
            label_map: list[dict[str, Any]] = []

            for query_id in sorted(dev_ids):
                proposal = proposals_by_id.get(query_id)
                if proposal is None:
                    raise ValueError(f"Thiếu proposal cho Dev query {query_id}")
                gold_ids = proposal.get("gold_context_ids") or proposal.get("candidate_context_ids") or []
                if not gold_ids:
                    query_details.append({"query_id": query_id, "status": "no_chunk_label", "chunk_ids": []})
                    continue
                missing_base = [gold_id for gold_id in gold_ids if gold_id not in base_by_id]
                if missing_base:
                    excluded_invalid.append({"query_id": query_id, "ids_not_in_base_chunks": missing_base})
                    query_details.append({"query_id": query_id, "status": "label_not_chunk_id", "chunk_ids": []})
                    continue

                mapped: list[str] = []
                per_gold: list[dict[str, Any]] = []
                for gold_id in gold_ids:
                    base_row = base_by_id[gold_id]
                    base_text = chunk_tokens(str(base_row.get("text") or base_row.get("chunk_text") or ""))
                    exact = by_id.get(gold_id)
                    matches: list[dict[str, Any]] = []
                    if exact is not None:
                        matches = [exact]
                        match_method = "same_chunk_id"
                    else:
                        clause_id = str(base_row.get("clause_id") or "")
                        for candidate in by_clause.get(clause_id, []):
                            candidate_text = chunk_tokens(str(candidate.get("text") or candidate.get("chunk_text") or ""))
                            if (is_contiguous_part(candidate_text, base_text)
                                    or is_contiguous_part(base_text, candidate_text)):
                                matches.append(candidate)
                        match_method = "same_clause_text_span"
                    match_ids = [row.get("chunk_id") or row.get("id") for row in matches]
                    mapped.extend(match_ids)
                    per_gold.append({"base_chunk_id": gold_id, "mapped_chunk_ids": match_ids,
                                     "mapping_method": match_method if match_ids else "unmapped"})
                    label_map.append({"query_id": query_id, **per_gold[-1]})

                mapped = list(dict.fromkeys(mapped))
                if not mapped:
                    excluded_unmapped.append({"query_id": query_id, "gold_context_ids": gold_ids,
                                              "reason": "Không tìm thấy text-span liên tiếp trong clause của biến thể"})
                    query_details.append({"query_id": query_id, "status": "variant_label_unmapped", "chunk_ids": []})
                    continue
                query_labels[query_id] = mapped
                query_details.append({"query_id": query_id, "status": "mapped", "chunk_ids": mapped,
                                      "source_gold_context_ids": gold_ids, "per_gold_chunk": per_gold})

            config_data = {
                "variant_report": variant_reports[variant],
                "queries_scored": len(query_labels),
                "queries_excluded_invalid_base_ids": len(excluded_invalid),
                "queries_excluded_unmapped_variant_spans": len(excluded_unmapped),
                "query_labels": query_labels,
                "query_details": query_details,
                "label_mapping": label_map,
                "excluded_invalid_base_ids": excluded_invalid,
                "excluded_unmapped_variant_spans": excluded_unmapped,
            }
            mapping["configs"][variant] = config_data
            save_json(args.output_dir / variant / "dev_chunk_labels.json", config_data)

        save_json(args.output_dir / "label_mapping.json", mapping)
        print(f"Label mapping: {args.output_dir / 'label_mapping.json'}")
        return 0
    except (OSError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
