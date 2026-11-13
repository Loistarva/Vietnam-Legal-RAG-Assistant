"""Probe guard/config gaps with synthetic data and a mocked model, never holdout data."""
import json
from pathlib import Path
import sys
import tempfile
import subprocess

checkout = Path(sys.argv[1]).resolve()
def tracked_status():
    return subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=checkout, text=True).strip()

if tracked_status():
    raise SystemExit("Refusing probe: modified tracked files")
source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
sys.path.insert(0, str(checkout))
# No Ollama runtime dependency required: the gateway gets a fake transport and never calls a provider.
from evaluation import zero_shot
from model_gateway.llm_gateway import QwenGateway

sent: list[dict] = []


def fake_transport(url, payload, timeout):
    sent.append(payload)
    return {"model": payload["model"], "response": "synthetic answer", "done": True, "done_reason": "length"}


with tempfile.TemporaryDirectory() as directory:
    query_file = Path(directory) / "synthetic_test.json"
    query_file.write_text(json.dumps([{"id": "SYNTHETIC_HOLDOUT_PROBE", "question": "Synthetic guard probe",
                                        "split": "test", "as_of_date": "2000-01-01"}]), encoding="utf-8")
    accepted = zero_shot.load_questions(query_file)
answer, _prompt = zero_shot.answer_question("Synthetic guard probe", query_id="SYNTHETIC_HOLDOUT_PROBE",
                                            as_of_date="2000-01-01", gateway=QwenGateway(transport=fake_transport))
report = {
    "source_sha": source_sha,
    "tracked_status_after": tracked_status(),
    "synthetic_test_split_accepted_by_loader": len(accepted) == 1,
    "mock_generation_options": sent[0]["options"],
    "mock_generation_prompt": sent[0]["prompt"],
    "answer_return_type": type(answer).__name__,
    "done_reason_preserved": answer.done_reason == "length",
    "real_model_calls": 0,
    "real_test_queries_read": 0,
}
Path(sys.argv[2]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=True))
