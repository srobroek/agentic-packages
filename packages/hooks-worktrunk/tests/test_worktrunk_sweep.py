"""Tests for worktrunk-sweep.py.

The safety tests are the point. This hook deletes directories, so every signal that
should stop it gets a case: uncommitted work of each kind, unpushed commits, a
recent commit, a detached worktree, and any missing or malformed field. The
predecessor (worktree-orphan-cleanup) inferred abandonment from a dead pid and could
not distinguish finished work from interrupted work; these cases pin that it now
takes several independent signals to agree.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worktrunk-sweep.py"


def load():
    spec = importlib.util.spec_from_file_location("worktrunk_sweep", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sweep = load()

NOW = 1_800_000_000.0
OLD = int(NOW - 30 * 24 * 3600)
RECENT = int(NOW - 60)


def record(**overrides):
    """A worktree record that IS stale, so each test can spoil one field."""
    base = {
        "branch": "feat/x",
        "path": "/tmp/does-not-matter",
        "is_main": False,
        "is_current": False,
        "working_tree": {
            "staged": False,
            "modified": False,
            "untracked": False,
            "renamed": False,
            "deleted": False,
        },
        "remote": {"name": "origin", "branch": "feat/x", "ahead": 0, "behind": 3},
        "commit": {"sha": "abc", "timestamp": OLD},
    }
    base.update(overrides)
    return base


@pytest.fixture
def real_dir(tmp_path, monkeypatch):
    """A record pointing at a directory that exists, so the isdir check passes."""
    directory = tmp_path / "wt"
    directory.mkdir()
    return str(directory)


# --- script contract ------------------------------------------------------


def test_has_shebang_and_is_executable():
    assert SCRIPT.read_text(encoding="utf-8").splitlines()[0] == "#!/usr/bin/env python3"
    assert os.access(SCRIPT, os.X_OK)


def test_compiles():
    subprocess.run([sys.executable, "-m", "py_compile", str(SCRIPT)], check=True)


def test_spawns_no_jq_or_awk():
    body = SCRIPT.read_text(encoding="utf-8")
    for banned in ("'jq'", '"jq"', "'awk'", '"awk"', "'sed'", '"sed"'):
        assert banned not in body


def test_pins_the_json_schema_it_parses():
    """wt warns that a future release switches the default schema; this reads
    schema-1 field names, so the version must be requested explicitly rather than
    inherited from wt's default."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "--format" in body and "json" in body


# --- staleness: the safe answer is always "leave it alone" ----------------


def test_a_clean_pushed_old_worktree_is_stale(real_dir):
    ok, reason = sweep.is_stale(record(path=real_dir), NOW)
    assert ok
    assert "clean, pushed" in reason


@pytest.mark.parametrize("field", ["staged", "modified", "untracked", "renamed", "deleted"])
def test_any_uncommitted_work_blocks_the_sweep(field, real_dir):
    working = dict(record()["working_tree"])
    working[field] = True
    ok, reason = sweep.is_stale(record(path=real_dir, working_tree=working), NOW)
    assert not ok
    assert field in reason


def test_unpushed_commits_block_the_sweep(real_dir):
    remote = {"name": "origin", "branch": "feat/x", "ahead": 2, "behind": 0}
    ok, reason = sweep.is_stale(record(path=real_dir, remote=remote), NOW)
    assert not ok
    assert "unpushed" in reason


def test_a_recent_commit_blocks_the_sweep(real_dir):
    commit = {"sha": "abc", "timestamp": RECENT}
    ok, reason = sweep.is_stale(record(path=real_dir, commit=commit), NOW)
    assert not ok
    assert reason == "recent"


@pytest.mark.parametrize(
    "overrides,expected",
    [
        pytest.param({"is_main": True}, "active", id="main-checkout"),
        pytest.param({"is_current": True}, "active", id="current-checkout"),
        pytest.param({"branch": None}, "detached", id="detached-null-branch"),
        pytest.param({"branch": ""}, "detached", id="empty-branch"),
        pytest.param({"working_tree": None}, "working-tree", id="no-working-tree"),
        pytest.param({"remote": None}, "remote", id="no-remote"),
        pytest.param({"remote": {"name": "origin"}}, "ahead", id="no-ahead-count"),
        pytest.param({"commit": None}, "commit", id="no-commit"),
        pytest.param({"commit": {"sha": "x"}}, "timestamp", id="no-timestamp"),
    ],
)
def test_missing_or_malformed_signals_block_the_sweep(overrides, expected, real_dir):
    """Fewer signals means less confidence, not more license."""
    ok, reason = sweep.is_stale(record(path=real_dir, **overrides), NOW)
    assert not ok
    assert expected in reason


def test_a_missing_directory_blocks_the_sweep():
    ok, reason = sweep.is_stale(record(path="/nonexistent-xyz-123"), NOW)
    assert not ok
    assert "no directory" in reason


def test_detached_worktree_from_real_wt_output_is_skipped(real_dir):
    """`wt list` reports branch: null for a detached worktree -- observed on this
    machine, which is why the null case is pinned separately from the empty one."""
    ok, _ = sweep.is_stale(record(path=real_dir, branch=None), NOW)
    assert not ok


# --- artifact reclamation ------------------------------------------------


def test_only_git_ignored_directories_are_removed(tmp_path, monkeypatch):
    """A tracked dist/ must survive: check-ignore gates every removal."""
    root = tmp_path / "wt"
    (root / "node_modules").mkdir(parents=True)
    (root / "dist").mkdir()
    (root / "node_modules" / "f").write_text("x")
    (root / "dist" / "f").write_text("keep")

    # node_modules ignored, dist tracked.
    monkeypatch.setattr(sweep, "ignored", lambda path, name: name == "node_modules")
    removed = sweep.reclaim(str(root))

    assert removed == ["node_modules"]
    assert not (root / "node_modules").exists()
    assert (root / "dist" / "f").read_text() == "keep"


def test_a_symlinked_artifact_dir_is_not_followed(tmp_path, monkeypatch):
    """Removing through a symlink would delete outside the worktree."""
    root = tmp_path / "wt"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious").write_text("keep")
    (root / "node_modules").symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(sweep, "ignored", lambda path, name: True)
    assert sweep.reclaim(str(root)) == []
    assert (outside / "precious").read_text() == "keep"


def test_reclaim_leaves_source_alone(tmp_path, monkeypatch):
    root = tmp_path / "wt"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text("code")
    (root / "target").mkdir()
    monkeypatch.setattr(sweep, "ignored", lambda path, name: True)
    sweep.reclaim(str(root))
    assert (root / "src" / "main.py").read_text() == "code"


def test_real_check_ignore_gates_removal(tmp_path):
    """Exercise the real git call rather than a stub, so the flag order is pinned."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "."], cwd=root, check=True, capture_output=True)
    (root / ".gitignore").write_text("node_modules/\n")
    # The directory must exist: a trailing-slash pattern matches a directory, and
    # git reports "not ignored" for a path that is not there.
    (root / "node_modules").mkdir()
    (root / "src").mkdir()
    assert sweep.ignored(str(root), "node_modules")
    assert not sweep.ignored(str(root), "src")


# --- hook behaviour ------------------------------------------------------


def live_record(path, **overrides):
    """A stale record against the REAL clock, since main() reads time.time()."""
    stamp = int(time.time() - 60 * 24 * 3600)
    return record(path=path, commit={"sha": "abc", "timestamp": stamp}, **overrides)


def drive(payload, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    code = sweep.main()
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None)


def test_subagents_do_not_sweep(monkeypatch, capsys):
    """N finishing agents must not race on the same directories."""
    calls = []
    monkeypatch.setattr(sweep, "worktrees", lambda: calls.append(1) or [])
    code, out = drive(json.dumps({"agent_id": "sub"}), monkeypatch, capsys)
    assert code == 0
    assert out is None
    assert calls == []


def test_absent_wt_is_inert(monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda name: None)
    code, out = drive("{}", monkeypatch, capsys)
    assert code == 0
    assert out is None


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json", id="unparsable"),
        pytest.param("[]", id="not-an-object"),
        pytest.param("{}", id="empty-object"),
    ],
)
def test_malformed_payloads_never_raise(payload, monkeypatch, capsys):
    monkeypatch.setattr(sweep, "worktrees", lambda: [])
    code, _ = drive(payload, monkeypatch, capsys)
    assert code == 0


def test_nothing_stale_is_silent(monkeypatch, capsys):
    monkeypatch.setattr(sweep, "worktrees", lambda: [record(commit={"sha": "x", "timestamp": int(time.time())})])
    code, out = drive("{}", monkeypatch, capsys)
    assert code == 0
    assert out is None


def test_report_never_removes_the_worktree_or_branch(monkeypatch, capsys, tmp_path):
    """Branch and worktree removal belong to `wt remove`, which already refuses an
    unmerged branch. Reimplementing that here would duplicate its safety net."""
    directory = tmp_path / "wt"
    directory.mkdir()
    monkeypatch.setattr(sweep, "worktrees", lambda: [live_record(str(directory))])
    monkeypatch.setattr(sweep, "reclaim", lambda path: ["target"])
    ran = []
    monkeypatch.setattr(sweep, "run", lambda command, **k: ran.append(command))

    code, out = drive("{}", monkeypatch, capsys)
    assert code == 0
    assert out is not None
    context = out["hookSpecificOutput"]["additionalContext"]
    assert "wt remove" in context and "wt prune" in context
    assert directory.is_dir(), "the worktree itself must survive"
    for command in ran:
        assert "remove" not in command
        assert "branch" not in command


def test_report_names_the_branch_and_the_reason(monkeypatch, capsys, tmp_path):
    directory = tmp_path / "wt"
    directory.mkdir()
    monkeypatch.setattr(sweep, "worktrees", lambda: [live_record(str(directory), branch="feat/abandoned")])
    monkeypatch.setattr(sweep, "reclaim", lambda path: [])
    _, out = drive("{}", monkeypatch, capsys)
    context = out["hookSpecificOutput"]["additionalContext"]
    assert "feat/abandoned" in context
    assert "no build output" in context


def test_report_is_capped(monkeypatch, capsys, tmp_path):
    directory = tmp_path / "wt"
    directory.mkdir()
    many = [live_record(str(directory), branch=f"feat/b{index}") for index in range(15)]
    monkeypatch.setattr(sweep, "worktrees", lambda: many)
    monkeypatch.setattr(sweep, "reclaim", lambda path: [])
    _, out = drive("{}", monkeypatch, capsys)
    context = out["hookSpecificOutput"]["additionalContext"]
    assert "and 5 more" in context
    assert "15 abandoned" in context


def test_event_name_is_session_start(monkeypatch, capsys, tmp_path):
    directory = tmp_path / "wt"
    directory.mkdir()
    monkeypatch.setattr(sweep, "worktrees", lambda: [live_record(str(directory))])
    monkeypatch.setattr(sweep, "reclaim", lambda path: [])
    _, out = drive("{}", monkeypatch, capsys)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"


# --- wt output parsing ---------------------------------------------------


def test_worktrees_tolerates_a_leading_banner(monkeypatch):
    """wt prints schema advisories before the array."""

    class Result:
        returncode = 0
        stdout = '▲ JSON output is schema 1\n[{"branch": "a", "path": "/x"}]'

    monkeypatch.setattr(sweep, "run", lambda *a, **k: Result())
    assert sweep.worktrees() == [{"branch": "a", "path": "/x"}]


@pytest.mark.parametrize(
    "stdout", ["", "not json", "no array here", "{}"], ids=["empty", "bad", "prose", "object"]
)
def test_worktrees_returns_empty_on_junk(stdout, monkeypatch):
    class Result:
        returncode = 0

    Result.stdout = stdout
    monkeypatch.setattr(sweep, "run", lambda *a, **k: Result())
    assert sweep.worktrees() == []


def test_worktrees_returns_empty_when_wt_fails(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(sweep, "run", lambda *a, **k: Result())
    assert sweep.worktrees() == []


def test_worktrees_drops_non_dict_entries(monkeypatch):
    class Result:
        returncode = 0
        stdout = '[{"branch": "a"}, "junk", 42, null]'

    monkeypatch.setattr(sweep, "run", lambda *a, **k: Result())
    assert sweep.worktrees() == [{"branch": "a"}]
