"""Read-only D1.4 preflight. No inference, metrics, network or artifact rewriting."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from evaluation.dev30_guard import check_handoff

if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    try:
        print(json.dumps(check_handoff(),ensure_ascii=True,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(f"FAIL: {exc}");raise SystemExit(1)
