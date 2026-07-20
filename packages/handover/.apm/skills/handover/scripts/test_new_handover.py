"""Tests for new-handover.py frontmatter quoting and write-failure handling.

Run with:  uv run --with pytest pytest test_new_handover.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    path = os.path.join(_HERE, "new-handover.py")
    spec = importlib.util.spec_from_file_location("new_handover", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nh = _load_module()


def _frontmatter(content):
    """Return the raw text between the leading --- fences."""
    assert content.startswith("---\n")
    end = content.index("\n---\n", 4)
    return content[4:end]


# --- YAML-safe scalar quoting ------------------------------------------------

def test_newline_in_repo_root_does_not_inject_keys():
    """A newline in repo_root must stay inside the value, not start a new key."""
    content = nh.build_content(
        project="proj",
        repo_root="/legit\ninjected: pwned\nmalicious: true",
        worktree="/wt",
        branch="main",
        task="t",
    )
    fm = _frontmatter(content)
    # The injected pseudo-keys must NOT appear as top-level frontmatter keys.
    for line in fm.splitlines():
        key = line.split(":", 1)[0].strip()
        assert key in {"project", "repo_root", "worktree", "branch", "task", "updated"}, \
            f"unexpected frontmatter key from injection: {line!r}"
    # The newline survives inside the quoted repo_root value (as \n escape).
    assert "repo_root: " in fm
    assert "\\ninjected" in fm  # json-escaped newline kept the data on one line


def test_newline_in_branch_single_key():
    content = nh.build_content(
        project="p", repo_root="/r", worktree="/w",
        branch="feature\nupdated: 1999-01-01T00:00:00Z",
        task="t",
    )
    fm = _frontmatter(content)
    branch_lines = [ln for ln in fm.splitlines() if ln.startswith("branch:")]
    updated_lines = [ln for ln in fm.splitlines() if ln.startswith("updated:")]
    assert len(branch_lines) == 1
    # Exactly one real `updated:` (the script's own), not a smuggled one.
    assert len(updated_lines) == 1


def test_frontmatter_parses_with_pyyaml_if_available():
    yaml = pytest.importorskip("yaml")
    content = nh.build_content(
        project="p",
        repo_root='/r"quote\ninjected: x',
        worktree="/w", branch="b", task="t",
    )
    fm = _frontmatter(content)
    data = yaml.safe_load(fm)
    assert set(data.keys()) == {"project", "repo_root", "worktree", "branch", "task", "updated"}
    assert data["repo_root"] == '/r"quote\ninjected: x'


# --- beads layout --------------------------------------------------------------

def test_beads_layout_lists_ids_and_omits_state_sections():
    content = nh.build_content(
        project="p", repo_root="/r", worktree="/w", branch="b", task="t",
        beads=["bd-1", "bd-2"],
    )
    fm = _frontmatter(content)
    assert 'beads: ["bd-1", "bd-2"]' in fm
    assert "## Active Beads" in content
    assert "- bd-1:" in content and "- bd-2:" in content
    assert "bd ready" in content
    # Task-state sections are bead state, not file content.
    for omitted in ("## Complete", "## Incomplete", "## Blockers", "## Changed Areas", "## Verification"):
        assert omitted not in content, f"{omitted} must be omitted in beads layout"
    # Narrative sections stay.
    for kept in ("## Summary", "## Decisions", "## Avoid / Do Not Redo", "## Next Session Prompt", "## Runtime State"):
        assert kept in content


def test_no_beads_keeps_full_layout():
    content = nh.build_content(
        project="p", repo_root="/r", worktree="/w", branch="b", task="t",
    )
    assert "beads:" not in _frontmatter(content)
    for section in ("## Complete", "## Incomplete", "## Blockers", "## Verification / Commands"):
        assert section in content
    assert "## Active Beads" not in content


def test_beads_frontmatter_parses_with_pyyaml_if_available():
    yaml = pytest.importorskip("yaml")
    content = nh.build_content(
        project="p", repo_root="/r", worktree="/w", branch="b", task="t",
        beads=['bd-1"\ninjected: x'],
    )
    data = yaml.safe_load(_frontmatter(content))
    assert data["beads"] == ['bd-1"\ninjected: x']


def test_cli_beads_flag_writes_beads_layout(tmp_path, monkeypatch, capsys):
    out = tmp_path / "handovers"
    monkeypatch.setattr(sys, "argv", [
        "new-handover.py",
        "--out-dir", str(out),
        "--project", "proj",
        "--branch", "main",
        "--task", "task",
        "--repo-root", str(tmp_path),
        "--worktree", str(tmp_path),
        "--cwd", str(tmp_path),
        "--beads", "bd-7, bd-8,",
    ])
    rc = nh.main(sys.argv[1:])
    assert rc == 0
    written = list(out.glob("*.md"))
    assert len(written) == 1
    text = written[0].read_text(encoding="utf-8")
    assert 'beads: ["bd-7", "bd-8"]' in text
    assert "## Active Beads" in text


# --- out-dir-is-a-file handling ----------------------------------------------

def test_out_dir_is_a_file_exits_cleanly(tmp_path, monkeypatch, capsys):
    """If --out-dir is an existing regular file, exit non-zero, no traceback."""
    blocker = tmp_path / "store"
    blocker.write_text("i am a file, not a directory\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "new-handover.py",
        "--out-dir", str(blocker),
        "--project", "proj",
        "--branch", "main",
        "--task", "task",
        "--repo-root", str(tmp_path),
        "--worktree", str(tmp_path),
        "--cwd", str(tmp_path),
    ])
    rc = nh.main(sys.argv[1:])
    assert rc == 1
    err = capsys.readouterr().err
    assert "error:" in err


def test_write_private_raises_handover_error_for_file_parent(tmp_path):
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / "child.md"  # parent is a regular file
    with pytest.raises(nh.HandoverWriteError):
        nh.write_private(target, "content")


def test_happy_path_writes_file(tmp_path, monkeypatch, capsys):
    out = tmp_path / "handovers"
    monkeypatch.setattr(sys, "argv", [
        "new-handover.py",
        "--out-dir", str(out),
        "--project", "proj",
        "--branch", "main",
        "--task", "task",
        "--repo-root", str(tmp_path),
        "--worktree", str(tmp_path),
        "--cwd", str(tmp_path),
    ])
    rc = nh.main(sys.argv[1:])
    assert rc == 0
    written = list(out.glob("*.md"))
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8").startswith("---\n")
