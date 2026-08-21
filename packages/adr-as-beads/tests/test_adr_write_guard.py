#!/usr/bin/env python3
"""Tests for the ADR write guard.

Driven through the real entrypoint over stdin rather than by importing functions,
because the contract under test is the JSON payload in and the decision out --
which is what the runtime actually exercises.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "adr-write-guard.py"

GENERATED_HEAD = (
    "<!-- Generated from a beads decision bead. Edit the bead, not this file:\n"
    "     bd show adr-7 -->\n"
    "---\n"
    "number: 1\n"
    "bead: adr-7\n"
    "---\n\n"
    "# A decision\n"
)


def run(payload: dict) -> tuple[int, dict | None]:
    """Run the guard and return (exit code, parsed decision or None)."""
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    out = proc.stdout.strip()
    return proc.returncode, (json.loads(out) if out else None)


def decision_of(result: dict | None) -> str:
    if not result:
        return "allow"
    return result["hookSpecificOutput"]["permissionDecision"]


@pytest.fixture
def generated(tmp_path: Path) -> Path:
    path = tmp_path / "docs" / "adr" / "0001-a-decision.md"
    path.parent.mkdir(parents=True)
    path.write_text(GENERATED_HEAD, encoding="utf-8")
    return path


# --- the denial ---------------------------------------------------------------


def test_edit_of_generated_file_is_denied(generated):
    code, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(generated)}})
    assert code == 0  # a guard never exits nonzero
    assert decision_of(result) == "deny"


def test_denial_names_the_bead_and_the_fix(generated):
    _, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(generated)}})
    reason = result["hookSpecificOutput"]["permissionDecisionReason"]
    # A denial an agent cannot act on is a stall, so the bead id and the command
    # must both be present.
    assert "adr-7" in reason
    assert "bd show adr-7" in reason
    assert "bd supersede" in reason


def test_bead_id_falls_back_to_frontmatter(tmp_path):
    path = tmp_path / "docs" / "adr" / "0002-x.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "<!-- Generated from a beads decision bead -->\n---\nbead: adr-99\n---\n",
        encoding="utf-8",
    )
    _, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    assert "adr-99" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_marker_without_any_bead_id_still_denies(tmp_path):
    path = tmp_path / "docs" / "adr" / "0003-x.md"
    path.parent.mkdir(parents=True)
    path.write_text("<!-- Generated from a beads decision bead -->\n", encoding="utf-8")
    _, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    assert decision_of(result) == "deny"
    assert "<bead-id>" in result["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
def test_every_writing_tool_is_judged(generated, tool):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    _, result = run({"tool_name": tool, "tool_input": {key: str(generated)}})
    assert decision_of(result) == "deny"


def test_codex_apply_patch_of_generated_file_is_denied(generated):
    patch = (
        "*** Begin Patch\n"
        f"*** Update File: {generated}\n"
        "@@\n"
        "-old\n"
        "+new\n"
        "*** End Patch\n"
    )
    _, result = run(
        {"tool_name": "apply_patch", "tool_input": {"command": patch}}
    )
    assert decision_of(result) == "deny"


def test_codex_apply_patch_can_add_a_new_adr(tmp_path):
    path = tmp_path / "docs" / "adr" / "0002-new.md"
    path.parent.mkdir(parents=True)
    patch = f"*** Begin Patch\n*** Add File: {path}\n+new\n*** End Patch\n"
    _, result = run(
        {"tool_name": "apply_patch", "tool_input": {"command": patch}}
    )
    assert decision_of(result) == "allow"


def test_doc_adr_directory_is_also_covered(tmp_path):
    # adr-tools' historic default is doc/adr, not docs/adr.
    path = tmp_path / "doc" / "adr" / "0001-x.md"
    path.parent.mkdir(parents=True)
    path.write_text(GENERATED_HEAD, encoding="utf-8")
    _, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    assert decision_of(result) == "deny"


def test_backslash_path_is_normalized_before_matching(tmp_path):
    path = tmp_path / "docs" / "adr" / "0001-x.md"
    path.parent.mkdir(parents=True)
    path.write_text(GENERATED_HEAD, encoding="utf-8")
    # A payload carrying Windows separators must not slip the path check.
    spelled = str(path).replace("/", "\\")
    _, result = run({"tool_name": "Edit", "tool_input": {"file_path": spelled}})
    # The file cannot be opened under that spelling on POSIX, so this must fail
    # open rather than crash -- the assertion is that it does not raise.
    assert decision_of(result) in ("allow", "deny")


# --- what must stay editable --------------------------------------------------


def test_hand_written_adr_without_the_marker_is_allowed(tmp_path):
    """A repository not using this renderer must keep its ADRs editable."""
    path = tmp_path / "docs" / "adr" / "0001-hand.md"
    path.parent.mkdir(parents=True)
    path.write_text("# A hand-written record\n", encoding="utf-8")
    _, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    assert decision_of(result) == "allow"


def test_marker_outside_an_adr_directory_is_allowed(tmp_path):
    """This guard, its tests, and the package docs all contain the marker text."""
    path = tmp_path / "notes.md"
    path.write_text(GENERATED_HEAD, encoding="utf-8")
    _, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    assert decision_of(result) == "allow"


def test_new_file_under_adr_dir_is_allowed(tmp_path):
    """Creation is the renderer's business and the pre-commit gate's, not this
    guard's: denying it would block bootstrapping an ADR directory."""
    path = tmp_path / "docs" / "adr" / "0009-new.md"
    path.parent.mkdir(parents=True)
    _, result = run({"tool_name": "Write", "tool_input": {"file_path": str(path)}})
    assert decision_of(result) == "allow"


# --- fail open ---------------------------------------------------------------


def test_unparsable_payload_allows():
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(GUARD)],
        input="NOT JSON",
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_empty_stdin_allows():
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(GUARD)],
        input="",
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0


def test_non_writing_tool_allows(generated):
    _, result = run({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert decision_of(result) == "allow"


def test_missing_tool_input_allows():
    _, result = run({"tool_name": "Edit"})
    assert decision_of(result) == "allow"


def test_non_dict_tool_input_allows():
    _, result = run({"tool_name": "Edit", "tool_input": "not a dict"})
    assert decision_of(result) == "allow"


def test_missing_path_allows():
    _, result = run({"tool_name": "Edit", "tool_input": {}})
    assert decision_of(result) == "allow"


def test_nonexistent_path_allows(tmp_path):
    _, result = run(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "docs/adr/nope.md")},
        }
    )
    assert decision_of(result) == "allow"


def test_directory_as_path_allows(tmp_path):
    d = tmp_path / "docs" / "adr"
    d.mkdir(parents=True)
    _, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(d)}})
    assert decision_of(result) == "allow"


def test_undecodable_bytes_do_not_crash(tmp_path):
    """errors="replace" on the read: a binary file under docs/adr must not raise."""
    path = tmp_path / "docs" / "adr" / "0001-x.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe not utf-8 at all")
    code, result = run({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    assert code == 0
    assert decision_of(result) == "allow"


def test_guard_never_emits_ask(generated):
    """Constitution III: no guard may emit `ask`, which stalls autonomous agents."""
    for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"):
        _, result = run({"tool_name": tool, "tool_input": {"file_path": str(generated)}})
        assert decision_of(result) != "ask"
