import subprocess
from unittest.mock import patch

import pytest

from scripts.fetch_dev30_sources import ensure_sources, has_commit


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def test_sources_restored_in_shallow_checkout_without_switching_head(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-b", "ci_fixture")
    git(source, "config", "user.name", "CI fixture")
    git(source, "config", "user.email", "ci-fixture@example.invalid")
    shas = []
    for i in range(3):
        (source / "evidence.txt").write_text(str(i), encoding="utf-8")
        git(source, "add", "evidence.txt")
        git(source, "commit", "-m", f"fixture {i}")
        shas.append(git(source, "rev-parse", "HEAD"))
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "clone", "--no-local", "--depth", "1", str(source), str(checkout)], check=True)
    assert not has_commit(checkout, shas[0])
    before = git(checkout, "rev-parse", "HEAD")
    policy = dict(zip(("baseline_git_sha", "gold_audit_git_sha", "excluded_added_data_git_sha"), shas))
    assert set(ensure_sources(checkout, policy)) == set(shas[:2])
    assert all(has_commit(checkout, sha) for sha in shas)
    assert git(checkout, "rev-parse", "HEAD") == before
    assert git(checkout, "status", "--porcelain") == ""
    assert ensure_sources(checkout, policy) == []


@pytest.mark.parametrize("bad", [None, "main", "--all", "a" * 39])
def test_unpinned_or_option_like_refs_rejected_before_git_calls(tmp_path, bad):
    policy = {"baseline_git_sha":bad, "gold_audit_git_sha":"a"*40, "excluded_added_data_git_sha":"b"*40}
    with patch("scripts.fetch_dev30_sources.subprocess.run") as run:
        with pytest.raises(ValueError):
            ensure_sources(tmp_path, policy)
        run.assert_not_called()
