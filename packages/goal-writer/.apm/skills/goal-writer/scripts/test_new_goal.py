"""Tests for new-goal.py frontmatter quoting, body handling, and write failures.

Run with:  uv run --with pytest pytest test_new_goal.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    path = os.path.join(_HERE, "new-goal.py")
    spec = importlib.util.spec_from_file_location("new_goal", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ng = _load_module()


def _frontmatter(content):
    """Return the raw text between the leading --- fences."""
    assert content.startswith("---\n")
    end = content.index("\n---\n", 4)
    return content[4:end]


# --- YAML-safe scalar quoting ------------------------------------------------

def test_newline_in_source_prompt_does_not_inject_keys():
    """A newline in source_prompt must stay inside the value, not start a key."""
    content = ng.build_content(
        project="proj",
        goal="ship it",
        repo_root="/r",
        source_prompt="make it fast\ninjected: pwned\nmalicious: true",
        body="## Goal\n\nx",
    )
    fm = _frontmatter(content)
    for line in fm.splitlines():
        key = line.split(":", 1)[0].strip()
        assert key in {"project", "goal", "repo_root", "source_prompt", "created"}, \
            f"unexpected frontmatter key from injection: {line!r}"
    assert "\\ninjected" in fm  # json-escaped newline kept the data on one line


def test_frontmatter_parses_with_pyyaml_if_available():
    yaml = pytest.importorskip("yaml")
    content = ng.build_content(
        project="p",
        goal="g",
        repo_root='/r"quote\ninjected: x',
        source_prompt='make "it" fast\nkey: val',
        body="## Goal\n\nbody",
    )
    fm = _frontmatter(content)
    data = yaml.safe_load(fm)
    assert set(data.keys()) == {"project", "goal", "repo_root", "source_prompt", "created"}
    assert data["repo_root"] == '/r"quote\ninjected: x'


# --- body handling -----------------------------------------------------------

def test_empty_body_falls_back_to_scaffold():
    content = ng.build_content(
        project="p", goal="g", repo_root="/r", source_prompt="", body="",
    )
    assert "## Exit conditions" in content
    assert "## KPIs" in content


def test_provided_body_is_used_verbatim():
    body = "## Goal\n\nReduce latency\n\n## Exit conditions\n\n- [ ] p95 < 200ms"
    content = ng.build_content(
        project="p", goal="g", repo_root="/r", source_prompt="x", body=body,
    )
    assert "Reduce latency" in content
    assert "p95 < 200ms" in content


# --- slug / filename ---------------------------------------------------------

def test_slug_normalizes():
    assert ng.slug("Ship Goal-Writer!") == "ship-goal-writer"
    assert ng.slug("   ") == "goal"


def test_keep_multiple_distinct_titles_distinct_files(tmp_path, monkeypatch):
    out = tmp_path / "goals"
    for title in ("first goal", "second goal"):
        monkeypatch.setattr(sys, "argv", [
            "new-goal.py",
            "--out-dir", str(out),
            "--title", title,
            "--project", "proj",
            "--repo-root", str(tmp_path),
            "--cwd", str(tmp_path),
            "--body-file", os.devnull,
        ])
        assert ng.main(sys.argv[1:]) == 0
    written = sorted(p.name for p in out.glob("*.md"))
    assert written == ["proj__first-goal.md", "proj__second-goal.md"]


# --- out-dir-is-a-file handling ----------------------------------------------

def test_out_dir_is_a_file_exits_cleanly(tmp_path, monkeypatch, capsys):
    blocker = tmp_path / "store"
    blocker.write_text("i am a file, not a directory\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "new-goal.py",
        "--out-dir", str(blocker),
        "--title", "g",
        "--project", "proj",
        "--repo-root", str(tmp_path),
        "--cwd", str(tmp_path),
        "--body-file", os.devnull,
    ])
    assert ng.main(sys.argv[1:]) == 1
    assert "error:" in capsys.readouterr().err


def test_write_private_raises_goal_error_for_file_parent(tmp_path):
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / "child.md"  # parent is a regular file
    with pytest.raises(ng.GoalWriteError):
        ng.write_private(target, "content")


def test_happy_path_writes_private_file(tmp_path, monkeypatch):
    out = tmp_path / "goals"
    monkeypatch.setattr(sys, "argv", [
        "new-goal.py",
        "--out-dir", str(out),
        "--title", "ship it",
        "--project", "proj",
        "--repo-root", str(tmp_path),
        "--cwd", str(tmp_path),
        "--body-file", os.devnull,
    ])
    assert ng.main(sys.argv[1:]) == 0
    written = list(out.glob("*.md"))
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8").startswith("---\n")
    # private file perms where supported
    mode = written[0].stat().st_mode & 0o777
    assert mode in (0o600, 0o644)  # 0o644 fallback if chmod unsupported
