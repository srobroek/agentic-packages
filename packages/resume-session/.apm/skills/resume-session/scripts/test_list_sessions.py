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
    monkeypatch.setattr(lst, "collect_claude", lambda project: entries)
    monkeypatch.setattr(lst, "collect_codex", lambda project: [])
    monkeypatch.setattr(sys, "argv",
                        ["list-sessions.py", "--project", str(tmp_path), "--limit", "-1", "--json"])
    rc = lst.main()
    assert rc == 0
