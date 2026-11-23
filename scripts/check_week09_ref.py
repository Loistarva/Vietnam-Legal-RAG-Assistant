"""Run offline baseline checks in an existing isolated checkout; save exact results."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

checkout = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()

def tracked_status():
    return subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=checkout, text=True
    ).strip()

initial_status = tracked_status()
if initial_status:
    raise SystemExit("Refusing checks: checkout has modified tracked files")
env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONIOENCODING="utf-8")
commands = [
    ["scripts/validate_benchmark.py"],
    ["scripts/freeze_test.py", "--verify"],
    ["scripts/freeze_gold.py", "--verify"],
    ["-m", "pytest", "-q"],
]
report = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "checkout": str(checkout), "python": sys.version,
          "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip(),
          "tracked_status_before": initial_status,
          "offline": True, "results": []}
for args in commands:
    try:
        result = subprocess.run([sys.executable, *args], cwd=checkout, env=env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        report["results"].append({"args": args, "exit_code": result.returncode,
                                  "stdout": result.stdout, "stderr": result.stderr})
    except subprocess.TimeoutExpired:
        report["results"].append({"args": args, "exit_code": None, "error": "timeout 240s"})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
report["tracked_status_after"] = tracked_status()
report["sha_after"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"sha": report["sha"], "checks": [{"args": r["args"], "exit_code": r["exit_code"],
      "summary": r.get("stdout", "")[-500:]} for r in report["results"]]}, ensure_ascii=False))
sys.exit(0 if all(result["exit_code"] == 0 for result in report["results"])
         and not report["tracked_status_after"] and report["sha_after"] == report["sha"] else 1)
