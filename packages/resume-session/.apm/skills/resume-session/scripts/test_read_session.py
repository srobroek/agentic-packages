"""Tests for read-session.py adversarial-input handling.

Run with:  uv run --with pytest pytest test_read_session.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    path = os.path.join(_HERE, "read-session.py")
    spec = importlib.util.spec_from_file_location("read_session", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load_module()


# --- iter_json_lines: non-dict lines skipped, not crashed --------------------

@pytest.mark.parametrize(
    "line",
    ["[1, 2, 3]", '"bare string"', "42", "true", "null"],
)
def test_non_dict_line_skipped(tmp_path, line):
    p = tmp_path / "t.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    assert list(rs.iter_json_lines(str(p))) == []


def test_load_claude_survives_poison_line(tmp_path):
    """A bare-array line between turns must not abort load_claude."""
    p = tmp_path / "sess.jsonl"
    p.write_text(
        '{"type": "user", "message": {"content": "do the task"}, '
        '"timestamp": "2026-01-01T00:00:00Z"}\n'
        "[1, 2, 3]\n"  # AttributeError in the old code
        '{"type": "assistant", "message": {"content": '
        '[{"type": "text", "text": "done"}]}, '
        '"timestamp": "2026-01-01T00:01:00Z"}\n',
        encoding="utf-8",
    )
    meta, turns, _ = rs.load_claude(str(p), include_thinking=False)
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["text"] == "do the task"
    assert turns[1]["text"] == "done"


def test_load_codex_survives_poison_line(tmp_path):
    p = tmp_path / "rollout-2026.jsonl"
    p.write_text(
        '{"type": "session_meta", "payload": {"id": "x", "cwd": "/tmp"}}\n'
        "12345\n"  # bare number
        '{"type": "event_msg", "payload": {"type": "user_message", "message": "hi"}}\n',
        encoding="utf-8",
    )
    meta, turns, _ = rs.load_codex(str(p), include_thinking=False)
    assert meta["session_id"] == "x"
    assert any(t["text"] == "hi" for t in turns)


# --- --turns / --offset clamping ---------------------------------------------

def _build_claude_session(tmp_path, n_turns):
    p = tmp_path / "many.jsonl"
    lines = []
    for i in range(n_turns):
        role = "user" if i % 2 == 0 else "assistant"
        if role == "user":
            lines.append(
                '{"type": "user", "message": {"content": "u%d"}, '
                '"timestamp": "2026-01-01T00:%02d:00Z"}' % (i, i)
            )
        else:
            lines.append(
                '{"type": "assistant", "message": {"content": '
                '[{"type": "text", "text": "a%d"}]}, '
                '"timestamp": "2026-01-01T00:%02d:00Z"}' % (i, i)
            )
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _run_main(argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["read-session.py", *argv])
    return rs.main()


@pytest.mark.parametrize("turns", ["0", "-3"])
def test_nonpositive_turns_clamped(tmp_path, monkeypatch, capsys, turns):
    """--turns 0 must not yield an empty window (start==end); falls back to 8."""
    p = _build_claude_session(tmp_path, 6)
    rc = _run_main(["--file", str(p), "--agent", "claude", "--turns", turns], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Recent turns" in out
    # At least one turn rendered (the clamp produced a real window).
    assert "USER" in out or "ASSISTANT" in out


@pytest.mark.parametrize("offset", ["-1", "-100"])
def test_negative_offset_clamped(tmp_path, monkeypatch, capsys, offset):
    """A negative --offset would push `end` past `total` and slice wrong."""
    p = _build_claude_session(tmp_path, 4)
    rc = _run_main(["--file", str(p), "--agent", "claude", "--offset", offset], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    # window header must report a sane upper bound (== total), never > total.
    assert "of 4" in out


def test_offset_zero_shows_newest(tmp_path, monkeypatch, capsys):
    p = _build_claude_session(tmp_path, 4)
    rc = _run_main(["--file", str(p), "--agent", "claude", "--offset", "0"], monkeypatch)
    assert rc == 0
    assert "Recent turns" in capsys.readouterr().out


# --- cross-worktree session resolution ---------------------------------------

def test_worktree_projects_lists_all(monkeypatch):
    porcelain = (
        "worktree /repo/main\nHEAD aaaa\nbranch refs/heads/main\n\n"
        "worktree /repo/wt-x\nHEAD bbbb\nbranch refs/heads/topic\n\n"
    )
    class _R:
        returncode = 0
        stdout = porcelain
    monkeypatch.setattr(rs.subprocess, "run", lambda *a, **k: _R())
    monkeypatch.setattr(rs.os.path, "isdir", lambda p: True)
    assert rs.worktree_projects("/repo/main") == ["/repo/main", "/repo/wt-x"]


def test_worktree_projects_non_repo_falls_back(monkeypatch):
    class _R:
        returncode = 128
        stdout = ""
    monkeypatch.setattr(rs.subprocess, "run", lambda *a, **k: _R())
    assert rs.worktree_projects("/solo") == ["/solo"]


def test_resolve_finds_session_in_sibling_worktree(tmp_path, monkeypatch):
    """A bare session id is resolved from a SIBLING worktree's project dir."""
    # Two encoded project dirs under a fake CLAUDE_ROOT: main has nothing,
    # the sibling holds the target transcript.
    claude_root = tmp_path / "projects"
    main_dir = claude_root / rs.encode_project("/repo/main")
    sib_dir = claude_root / rs.encode_project("/repo/wt-x")
    main_dir.mkdir(parents=True)
    sib_dir.mkdir(parents=True)
    target = sib_dir / "deadbeef-0000-0000-0000-000000000000.jsonl"
    target.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(rs, "CLAUDE_ROOT", str(claude_root))
    monkeypatch.setattr(rs, "worktree_projects", lambda project: ["/repo/main", "/repo/wt-x"])

    class Args:
        file = None
        session = "deadbeef"
        project = "/repo/main"
        agent = "claude"

    path, agent = rs.resolve_file(Args())
    assert agent == "claude"
    assert path == str(target)
