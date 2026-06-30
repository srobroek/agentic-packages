"""Tests for list-sessions.py adversarial-input handling.

Run with:  uv run --with pytest pytest test_list_sessions.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    """Import list-sessions.py despite the hyphen in its filename."""
    path = os.path.join(_HERE, "list-sessions.py")
    spec = importlib.util.spec_from_file_location("list_sessions", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lst = _load_module()


# --- iter_json_lines: non-dict JSONL lines must be skipped, not crash --------

@pytest.mark.parametrize(
    "line",
    [
        "[1, 2, 3]",        # bare JSON array
        '"just a string"',  # bare JSON string
        "42",               # bare JSON number
        "true",             # bare JSON bool
        "null",             # JSON null
    ],
)
def test_non_dict_line_skipped(tmp_path, line):
    """A single non-dict JSONL line used to raise AttributeError in scan_*."""
    p = tmp_path / "rollout.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    records = list(lst.iter_json_lines(str(p)))
    assert records == []  # the non-dict line is dropped


def test_dicts_kept_non_dicts_dropped(tmp_path):
    p = tmp_path / "mixed.jsonl"
    p.write_text(
        '{"type": "user", "a": 1}\n'
        "[1, 2, 3]\n"           # poison line between two good ones
        '"a bare string"\n'
        '{"type": "assistant", "b": 2}\n',
        encoding="utf-8",
    )
    records = list(lst.iter_json_lines(str(p)))
    assert records == [{"type": "user", "a": 1}, {"type": "assistant", "b": 2}]


def test_scan_claude_survives_poison_line(tmp_path):
    """End-to-end: a poison line must not abort metadata extraction."""
    p = tmp_path / "abc12345-0000-0000-0000-000000000000.jsonl"
    p.write_text(
        '{"type": "user", "message": {"content": "hello goal"}, '
        '"timestamp": "2026-01-01T00:00:00Z", "gitBranch": "main"}\n'
        "[1, 2, 3]\n"  # would crash the old code with AttributeError
        '{"type": "assistant", "message": {"content": '
        '[{"type": "text", "text": "did the thing"}]}, '
        '"timestamp": "2026-01-01T00:01:00Z"}\n',
        encoding="utf-8",
    )
    meta = lst.scan_claude(str(p))
    assert meta["goal"] == "hello goal"
    assert meta["last"] == "did the thing"
    assert meta["branch"] == "main"


def test_malformed_json_line_skipped(tmp_path):
    p = tmp_path / "broken.jsonl"
    p.write_text('{"not closed": \nbananas\n{"type": "user"}\n', encoding="utf-8")
    # Should not raise; the two broken lines are dropped, the dict survives.
    records = list(lst.iter_json_lines(str(p)))
    assert {"type": "user"} in records


# --- --limit clamping --------------------------------------------------------

def _run_main(argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["list-sessions.py", *argv])
    return lst.main()


@pytest.mark.parametrize("limit", ["0", "-5", "-1"])
def test_nonpositive_limit_does_not_crash(tmp_path, monkeypatch, capsys, limit):
    """A non-positive --limit must not produce a reversed/empty negative slice."""
    rc = _run_main(["--project", str(tmp_path), "--limit", limit], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    # Empty project -> the "no prior sessions" message, never a traceback.
    assert "No prior sessions" in out


def test_negative_limit_keeps_entries(tmp_path, monkeypatch):
    """With entries present, limit=-1 must not silently drop the last entry.

    The old code did entries[:-1]; the clamp falls back to the default of 20.
    """
    entries = [{"last_ts": float(i), "title": f"t{i}", "branch": "", "agent": "claude",
                "session_id": f"id{i}", "turns": 1, "last": "", "path": ""} for i in range(3)]
    monkeypatch.setattr(lst, "collect_claude_worktrees", lambda wts: entries)
    monkeypatch.setattr(lst, "collect_codex", lambda wts: [])
    monkeypatch.setattr(lst, "list_worktrees", lambda project: [])
    monkeypatch.setattr(sys, "argv",
                        ["list-sessions.py", "--project", str(tmp_path), "--limit", "-1", "--json"])
    rc = lst.main()
    assert rc == 0


# --- worktree discovery ------------------------------------------------------

_PORCELAIN = (
    "worktree /repo/main\n"
    "HEAD aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111\n"
    "branch refs/heads/main\n"
    "\n"
    "worktree /repo/wt-feature\n"
    "HEAD bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222\n"
    "branch refs/heads/feature/nested/name\n"
    "\n"
    "worktree /repo/wt-detached\n"
    "HEAD cccc3333cccc3333cccc3333cccc3333cccc3333\n"
    "detached\n"
    "\n"
    "worktree /repo/wt-gone\n"
    "HEAD dddd4444dddd4444dddd4444dddd4444dddd4444\n"
    "branch refs/heads/dead\n"
    "prunable gitdir file points to non-existent location\n"
)


def _fake_git(stdout, returncode=0):
    class _R:
        pass
    def run(cmd, capture_output=True, text=True, timeout=None):
        r = _R()
        r.returncode = returncode
        r.stdout = stdout
        return r
    return run


def test_list_worktrees_parses_porcelain(monkeypatch):
    monkeypatch.setattr(lst.subprocess, "run", _fake_git(_PORCELAIN))
    # All listed paths "exist" except the pruned one; the gone one is skipped
    # both by prunable AND by the isdir check, so cover both.
    monkeypatch.setattr(lst.os.path, "isdir",
                        lambda p: p in ("/repo/main", "/repo/wt-feature", "/repo/wt-detached"))
    wts = lst.list_worktrees("/repo/main")
    paths = [w["path"] for w in wts]
    assert paths == ["/repo/main", "/repo/wt-feature", "/repo/wt-detached"]
    assert wts[0]["is_main"] is True
    assert wts[1]["is_main"] is False
    # Multi-segment branch name preserved, refs/heads/ stripped.
    assert wts[1]["branch"] == "feature/nested/name"
    assert wts[2]["detached"] is True
    # The prunable worktree is dropped entirely.
    assert "/repo/wt-gone" not in paths


def test_list_worktrees_non_repo_returns_empty(monkeypatch):
    monkeypatch.setattr(lst.subprocess, "run", _fake_git("", returncode=128))
    assert lst.list_worktrees("/not/a/repo") == []


def test_commit_info_batches_heads(monkeypatch):
    out = (
        "aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111\x001700000000\x00first subject\n"
        "bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222\x001700000500\x00second subject\n"
    )
    monkeypatch.setattr(lst.subprocess, "run", _fake_git(out))
    wts = [{"head": "aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"},
           {"head": "bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222"}]
    info = lst.commit_info(wts, "/repo/main")
    assert info["aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"] == (1700000000.0, "first subject")
    assert info["bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222"][1] == "second subject"


def test_sessions_tagged_with_worktree(tmp_path, monkeypatch, capsys):
    """A session from a sibling worktree is listed and labeled with it."""
    monkeypatch.setattr(lst, "list_worktrees", lambda project: [
        {"path": "/repo/main", "head": "h1", "branch": "main",
         "detached": False, "is_main": True},
        {"path": "/repo/wt-x", "head": "h2", "branch": "topic",
         "detached": False, "is_main": False},
    ])
    monkeypatch.setattr(lst, "commit_info", lambda wts, project: {
        "h1": (1700000000.0, "main commit"),
        "h2": (1700000500.0, "topic commit"),
    })
    monkeypatch.setattr(lst, "is_dirty", lambda path: False)

    def fake_collect_claude(project):
        if project == "/repo/wt-x":
            return [{"agent": "claude", "session_id": "sib123", "title": "sibling task",
                     "goal": "", "last": "did sibling work", "branch": "topic",
                     "last_ts": 1700000400.0, "turns": 5, "path": "x.jsonl"}]
        return []

    monkeypatch.setattr(lst, "collect_claude", fake_collect_claude)
    monkeypatch.setattr(lst, "collect_codex", lambda wts: [])
    monkeypatch.setattr(sys, "argv", ["list-sessions.py", "--project", "/repo/main"])
    rc = lst.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "across 2 worktrees" in out
    assert "Worktree git activity" in out
    assert "topic commit" in out  # git-activity overview rendered
    assert "worktree: wt-x" in out  # session tagged with its worktree
    assert "sib123" in out


def test_no_worktrees_flag_scans_only_project(tmp_path, monkeypatch, capsys):
    """--no-worktrees must not call list_worktrees; scans the project alone."""
    def boom(project):
        raise AssertionError("list_worktrees called under --no-worktrees")
    monkeypatch.setattr(lst, "list_worktrees", boom)
    monkeypatch.setattr(lst, "collect_claude", lambda project: [])
    monkeypatch.setattr(lst, "collect_codex", lambda wts: [])
    monkeypatch.setattr(sys, "argv",
                        ["list-sessions.py", "--project", str(tmp_path), "--no-worktrees"])
    rc = lst.main()
    assert rc == 0
    assert "No prior sessions" in capsys.readouterr().out
