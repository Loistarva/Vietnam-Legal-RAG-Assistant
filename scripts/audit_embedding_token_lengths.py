"""Audit actual embedding-token lengths against a SentenceTransformer sequence limit."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants-root", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants")
    parser.add_argument("--variants", nargs="+", default=["A", "B", "C", "E"])
    parser.add_argument("--model", default="bkai-foundation-models/vietnamese-bi-encoder")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "retrieval/results/dev_tuning/chunking_variants/embedding_token_length_audit.json")
    args = parser.parse_args()
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(args.model)
        tokenizer = model.tokenizer
        limit = int(model.max_seq_length)
        variant_results: dict[str, Any] = {}
        for variant in args.variants:
            path = args.variants_root / variant / "chunks.jsonl"
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            lengths: list[int] = []
            over_limit: list[dict[str, Any]] = []
            for row in rows:
                embed_text = row.get("embed_text")
                chunk_id = row.get("chunk_id") or row.get("id")
                if not isinstance(embed_text, str) or not embed_text:
                    raise ValueError(f"{variant}/{chunk_id}: thiếu embed_text")
                count = len(tokenizer(embed_text, add_special_tokens=True, truncation=False,
                                      padding=False)["input_ids"])
                lengths.append(count)
                if count > limit:
                    over_limit.append({"chunk_id": chunk_id, "token_count": count})
            ordered = sorted(lengths)
            variant_results[variant] = {
                "chunks": len(lengths),
                "mean_tokens": round(statistics.fmean(lengths), 2) if lengths else 0.0,
                "median_tokens": statistics.median(lengths) if lengths else 0,
                "p95_tokens": ordered[max(0, int(0.95 * len(ordered)) - 1)] if ordered else 0,
                "max_tokens": max(lengths) if lengths else 0,
                "sequence_limit": limit,
                "over_limit_chunks": len(over_limit),
                "over_limit_fraction": len(over_limit) / len(lengths) if lengths else 0.0,
                "over_limit_chunk_ids": over_limit,
            }
        payload = {
            "model": args.model,
            "sequence_limit": limit,
            "tokenizer": type(tokenizer).__name__,
            "variants": variant_results,
            "note": "Đếm token bằng tokenizer thật của model, có tính special tokens; model cắt đầu vào dài hơn sequence_limit.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({variant: {
            "chunks": row["chunks"],
            "sequence_limit": row["sequence_limit"],
            "over_limit_chunks": row["over_limit_chunks"],
            "over_limit_fraction": round(row["over_limit_fraction"], 4),
            "p95_tokens": row["p95_tokens"],
            "max_tokens": row["max_tokens"],
        } for variant, row in variant_results.items()}, ensure_ascii=False, indent=2))
        print(f"Audit: {args.output}")
        return 0
    except (OSError, json.JSONDecodeError, ValueError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
