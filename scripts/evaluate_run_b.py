"""Evaluate a saved Run B result; does not run the model."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.run_metrics import evaluate_saved_run


if __name__ == "__main__":
    evaluate_saved_run("B")
