"""Probe guard/config gaps with synthetic data and a mocked model, never holdout data."""
import json
from pathlib import Path
import sys
import tempfile
import types
import subprocess
from unittest.mock import patch

checkout = Path(sys.argv[1]).resolve()
def tracked_status():
    return subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=checkout, text=True).strip()

if tracked_status():
    raise SystemExit("Refusing probe: modified tracked files")
source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
sys.path.insert(0, str(checkout))
# No Ollama runtime dependency required: this probe never uses a provider.
sys.modules["ollama"] = types.SimpleNamespace(chat=lambda **kwargs: None)
from evaluation import zero_shot

with tempfile.TemporaryDirectory() as directory:
    query_file = Path(directory) / "synthetic_test.json"
    query_file.write_text(json.dumps([{"id": "SYNTHETIC_HOLDOUT_PROBE", "question": "Synthetic guard probe",
                                        "split": "test", "as_of_date": "2000-01-01"}]), encoding="utf-8")
    accepted = zero_shot.load_questions(query_file)
with patch.object(zero_shot.ollama, "chat", return_value={"message": {"content": "synthetic answer"},
                                                          "done_reason": "length"}) as model:
    answer = zero_shot.answer_question("Synthetic guard probe", "mock-model")
report = {
    "source_sha": source_sha,
    "tracked_status_after": tracked_status(),
    "synthetic_test_split_accepted_by_loader": len(accepted) == 1,
    "mock_generation_options": model.call_args.kwargs["options"],
    "mock_generation_messages": model.call_args.kwargs["messages"],
    "answer_return_type": type(answer).__name__,
    "done_reason_preserved": isinstance(answer, dict) and "done_reason" in answer,
    "real_model_calls": 0,
    "real_test_queries_read": 0,
}
Path(sys.argv[2]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=True))
