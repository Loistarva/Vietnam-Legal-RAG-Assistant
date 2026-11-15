"""Create a Run A manifest from an existing JSONL without contacting a model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.zero_shot import manifest_path_for, rebuild_manifest_from_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstruct verifiable Run A metadata from existing JSONL; never calls a model."
    )
    parser.add_argument("--results", type=Path, required=True, help="Existing Run A JSONL (read-only).")
    parser.add_argument("--split", default="unknown", help="Dataset split, if independently known.")
    parser.add_argument("--manifest", type=Path, help="Destination; defaults to sibling *_manifest.json.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing manifest only.")
    args = parser.parse_args()

    try:
        manifest = rebuild_manifest_from_jsonl(args.results, split=args.split)
        destination = args.manifest or manifest_path_for(args.results)
        if destination.exists() and not args.overwrite:
            raise FileExistsError(f"Manifest đã tồn tại: {destination}; dùng --overwrite để thay thế.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Manifest created: {destination.resolve()}")
        print(f"Results preserved: {args.results.resolve()}")
        print(f"Historical fields marked unknown: {len(manifest['unknown_historical_fields'])}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
