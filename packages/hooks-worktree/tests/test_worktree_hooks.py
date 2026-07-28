"""Coverage for worktree-hooks.py -- the merged WorktreeCreate/WorktreeRemove
lifecycle hooks.

Ported from tests/worktree.bats (bats suite deleted per contract rule 4:
parity proven against it before porting). These exercise the real git
plumbing against throwaway repos so the adversarial cases from the audit
fix-list are covered end to end:
  - create: a path-traversal worktree_name is rejected and no directory
    escapes the managed /tmp/claude-worktrees tree.
  - cleanup: when CWD is the MAIN repo (not a linked worktree) the hook must
    NOT stash the user's WIP.
  - cleanup: a linked worktree containing only UNTRACKED files must still be
    removed (force-remove for managed paths), not silently skipped.

The tests below invoke the script exactly as worktree.bats invoked the two
originals, i.e. without a hook_event_name field, relying on the merged
script's field-shape fallback (worktree_name/git_ref -> create, else remove)
-- the same dispatch a real Claude payload also exercises since Claude does
include hook_event_name, which the script checks first.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "worktree-hooks.py"


def run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture
def repo(tmp_path):
    repo_dir = tmp_path / "main"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_dir, check=True)
    (repo_dir / "file.txt").write_text("hello\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo_dir, check=True)
    yield repo_dir
    subprocess.run(["git", "worktree", "prune"], cwd=repo_dir, capture_output=True)


# --- create: name sanitization -------------------------------------------------


def test_create_path_traversal_name_rejected(repo, tmp_path):
    result = run({"cwd": str(repo), "worktree_name": "../../escape", "git_ref": "HEAD"})
    assert result.returncode != 0
    assert not (tmp_path / "escape").exists()
    assert not Path("/tmp/claude-worktrees/escape").exists()


def test_create_slashed_name_rejected(repo):
    result = run({"cwd": str(repo), "worktree_name": "foo/bar", "git_ref": "HEAD"})
    assert result.returncode != 0


def test_create_dotdot_embedded_name_rejected(repo):
    result = run({"cwd": str(repo), "worktree_name": "a..b", "git_ref": "HEAD"})
    assert result.returncode != 0


def test_create_whitespace_name_collapsed_and_accepted(repo):
    result = run({"cwd": str(repo), "worktree_name": "  my feature  ", "git_ref": "HEAD"})
    assert result.returncode == 0
    path = result.stdout.strip()
    assert path.startswith("/tmp/claude-worktrees/")
    assert path.endswith("/my-feature")
    assert os.path.isdir(path)
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", path], capture_output=True)
    subprocess.run(["rm", "-rf", path])


def test_create_leading_dash_name_defanged(repo):
    result = run({"cwd": str(repo), "worktree_name": "-rf", "git_ref": "HEAD"})
    assert result.returncode == 0
    path = result.stdout.strip()
    assert path.endswith("/rf")
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", path], capture_output=True)
    subprocess.run(["rm", "-rf", path])


def test_create_missing_cwd_exits_nonzero():
    result = run({"worktree_name": "x", "git_ref": "HEAD"})
    assert result.returncode != 0


def test_create_malformed_stdin_does_not_crash():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="this is not json at all }{",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0


# --- cleanup: main-repo guard -----------------------------------------------------


def test_cleanup_main_repo_with_wip_does_not_stash(repo):
    with open(repo / "file.txt", "a") as handle:
        handle.write("uncommitted\n")
    before = subprocess.run(
        ["git", "-C", str(repo), "stash", "list"], capture_output=True, text=True
    ).stdout

    result = run({"cwd": str(repo)})
    assert result.returncode == 0

    after = subprocess.run(
        ["git", "-C", str(repo), "stash", "list"], capture_output=True, text=True
    ).stdout
    assert before == after

    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    assert "file.txt" in status


def test_cleanup_empty_cwd_is_noop():
    result = run({})
    assert result.returncode == 0


def test_cleanup_non_git_cwd_is_noop(tmp_path):
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    result = run({"cwd": str(outside)})
    assert result.returncode == 0


# --- cleanup: linked worktree with untracked files --------------------------------


def test_cleanup_linked_managed_worktree_with_untracked_file_removed(repo):
    repo_name = repo.name
    managed_root = Path(f"/tmp/claude-worktrees/{repo_name}")
    managed_root.mkdir(parents=True, exist_ok=True)
    wt = managed_root / f"cleanup-untracked-{uuid.uuid4().hex}"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "-b", f"worktree-{wt.name}", "HEAD"],
        check=True,
    )
    (wt / "untracked.txt").write_text("scratch\n")

    assert wt.is_dir()
    result = run({"cwd": str(wt)})
    assert result.returncode == 0
    assert not wt.exists()

    listing = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"], capture_output=True, text=True
    ).stdout
    assert f"worktree {wt}" not in listing

    subprocess.run(["rm", "-rf", str(managed_root)])


def test_cleanup_refused_removal_still_deletes_ignored_artifacts(repo, tmp_path):
    wt = tmp_path / "wt-artifacts"
    branch = f"worktree-artifacts-{uuid.uuid4().hex}"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", "-b", branch, str(wt)], check=True
    )
    (wt / ".gitignore").write_text("target/\n")
    subprocess.run(["git", "-C", str(wt), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(wt), "commit", "-qm", "gitignore"], check=True)
    (wt / "target" / "debug").mkdir(parents=True)
    (wt / "target" / "debug" / "app").write_text("bin\n")
    subprocess.run(["git", "-C", str(repo), "worktree", "lock", str(wt)], check=True)

    result = run({"cwd": str(wt)})
    assert result.returncode == 0
    assert wt.is_dir()
    assert not (wt / "target").exists()

    subprocess.run(["git", "-C", str(repo), "worktree", "unlock", str(wt)], capture_output=True)


def test_cleanup_linked_managed_worktree_branch_deleted(repo):
    repo_name = repo.name
    managed_root = Path(f"/tmp/claude-worktrees/{repo_name}")
    managed_root.mkdir(parents=True, exist_ok=True)
    wt = managed_root / f"cleanup-branch-{uuid.uuid4().hex}"
    branch = f"worktree-cleanup-branch-{uuid.uuid4().hex}"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "-b", branch, "HEAD"], check=True
    )

    result = run({"cwd": str(wt)})
    assert result.returncode == 0
    assert not wt.exists()

    branch_list = subprocess.run(
        ["git", "-C", str(repo), "branch", "--list", branch], capture_output=True, text=True
    ).stdout
    assert branch not in branch_list

    subprocess.run(["rm", "-rf", str(managed_root)])
