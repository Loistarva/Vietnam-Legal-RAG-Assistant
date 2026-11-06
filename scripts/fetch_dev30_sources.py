"""Fetch missing pinned Dev30 Git commits; run before offline validation/tests."""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("baseline_git_sha", "gold_audit_git_sha", "excluded_added_data_git_sha")


def has_commit(root, sha):
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=root,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def ensure_sources(root, policy):
    shas = [policy.get(key) for key in KEYS]
    if any(not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha) for sha in shas):
        raise ValueError("Every Dev30 source must be pinned to a full Git SHA")
    fetched = []
    for sha in dict.fromkeys(shas):
        if has_commit(root, sha):
            continue
        subprocess.run(["git", "fetch", "--no-tags", "origin", sha], cwd=root, check=True)
        if not has_commit(root, sha):
            raise ValueError(f"Pinned source commit still missing after fetch: {sha}")
        fetched.append(sha)
    return fetched


def main():
    policy = json.loads((ROOT / "evaluation/manifests/dev_gold_30_selection_policy_v1.json").read_text(encoding="utf-8-sig"))
    fetched = ensure_sources(ROOT, policy)
    print(f"Pinned Dev30 sources available; fetched {len(fetched)} missing commits")


if __name__ == "__main__":
    main()
