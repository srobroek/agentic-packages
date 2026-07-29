"""Coverage for spill-tool-output.py, the PostToolUse archive-and-retrieve hook.

Two properties decide whether this is safe. The retrieval instructions must be
CORRECT -- a `sed` range off by the header's two lines sends the agent back over
lines it already has, which is worse than not spilling. And a FAILING command
must never be truncated, because the error text is the thing the agent needs.

Claude-only by construction: `updatedToolOutput` is not in Codex's PostToolUse
wire struct, so the Codex hook manifest does not install this.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "spill-tool-output.py"


def _big(lines: int = 600, filler: str = " some content here to pad this line out") -> str:
    return "\n".join(f"line {i}{filler}" for i in range(1, lines + 1))


def _raw(payload, state: Path):
    """The `updatedToolOutput` value exactly as emitted, shape included."""
    environment = dict(os.environ)
    environment["XDG_STATE_HOME"] = str(state)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], input=raw, capture_output=True, text=True, env=environment
    )
    out = proc.stdout.strip()
    return None if not out else json.loads(out)["hookSpecificOutput"]["updatedToolOutput"]


def _run(payload, state: Path) -> str:
    """Return the rewritten tool output, or "" when untouched."""
    environment = dict(os.environ)
    environment["XDG_STATE_HOME"] = str(state)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], input=raw, capture_output=True, text=True, env=environment
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.strip()
    if not out:
        return ""
    value = json.loads(out)["hookSpecificOutput"]["updatedToolOutput"]
    # Bash output is a structured object; the tests below read its stdout.
    return value["stdout"] if isinstance(value, dict) else value


def _payload(text: str, *, exit_code: int = 0, command: str = "pytest -v") -> dict:
    return {
        "tool_name": "Bash",
        "tool_use_id": "toolu_abcdef123456",
        "tool_input": {"command": command},
        "tool_response": {"stdout": text, "exit_code": exit_code},
    }


def _spill_files(state: Path) -> list[Path]:
    return sorted((state / "agentic-tools" / "token-savings" / "spill").glob("*.txt"))


def test_large_output_is_spilled_and_summarized(tmp_path):
    text = _big()
    summary = _run(_payload(text), tmp_path)
    assert summary
    assert len(summary) < len(text)
    assert "[token-savings]" in summary
    assert len(_spill_files(tmp_path)) == 1


def test_spill_file_holds_the_complete_output(tmp_path):
    """The saving is only acceptable because nothing is lost."""
    text = _big()
    _run(_payload(text), tmp_path)
    saved = _spill_files(tmp_path)[0].read_text()
    assert text in saved
    assert saved.startswith("$ pytest -v")


def test_sed_instruction_points_at_the_first_hidden_line(tmp_path):
    """The header occupies two lines, so an unadjusted range re-reads what the
    agent already has."""
    text = _big()
    summary = _run(_payload(text), tmp_path)
    match = re.search(r"sed -n '(\d+),(\d+)p' (\S+)", summary)
    assert match, summary
    start, path = int(match.group(1)), match.group(3)
    line = subprocess.run(
        ["sed", "-n", f"{start},{start}p", path], capture_output=True, text=True
    ).stdout.strip()
    assert line.startswith("line 41 "), f"sed points at {line!r}, expected output line 41"


def test_head_and_tail_are_both_retained(tmp_path):
    """The verdict of a test run is in the tail and the invocation in the head,
    so a head-only summary would force a retrieval for the common case."""
    text = _big()
    summary = _run(_payload(text), tmp_path)
    assert "line 1 " in summary
    assert "line 600" in summary
    assert "lines omitted" in summary


def test_failing_command_output_is_never_truncated(tmp_path):
    """The error text is what the agent needs."""
    assert _run(_payload(_big(), exit_code=1), tmp_path) == ""
    assert _spill_files(tmp_path) == []


@pytest.mark.parametrize("flag", ["is_error", "isError"])
def test_error_flagged_results_are_untouched(flag, tmp_path):
    payload = _payload(_big())
    payload["tool_response"][flag] = True
    assert _run(payload, tmp_path) == ""


def test_small_output_is_untouched(tmp_path):
    assert _run(_payload("short output\n"), tmp_path) == ""
    assert _spill_files(tmp_path) == []


def test_output_just_under_the_threshold_is_untouched(tmp_path):
    """Read the threshold from the script rather than hardcoding it, so tuning
    the constant cannot leave this test asserting the old value."""
    threshold = int(
        re.search(r"^SPILL_THRESHOLD_BYTES = ([\d_]+)", SCRIPT.read_text(), re.M)
        .group(1)
        .replace("_", "")
    )
    assert _run(_payload("x" * (threshold - 200)), tmp_path) == ""


def test_an_already_spilled_result_is_not_nested(tmp_path):
    payload = _payload("[token-savings] Output was ... \n" + _big())
    assert _run(payload, tmp_path) == ""


def test_identical_output_reuses_one_file(tmp_path):
    text = _big()
    _run(_payload(text), tmp_path)
    _run(_payload(text), tmp_path)
    assert len(_spill_files(tmp_path)) == 1


def test_different_calls_do_not_collide(tmp_path):
    _run(_payload(_big(), command="a"), tmp_path)
    _run(_payload(_big(500), command="b"), tmp_path)
    assert len(_spill_files(tmp_path)) == 2


def test_stderr_is_preserved_alongside_stdout(tmp_path):
    payload = _payload(_big())
    payload["tool_response"]["stderr"] = "a distinctive warning line\n"
    _run(payload, tmp_path)
    assert "a distinctive warning line" in _spill_files(tmp_path)[0].read_text()


def test_string_tool_response_is_handled(tmp_path):
    payload = {
        "tool_name": "Bash",
        "tool_use_id": "toolu_x",
        "tool_input": {"command": "ls"},
        "tool_response": _big(),
    }
    assert _run(payload, tmp_path)


def test_list_content_blocks_are_handled(tmp_path):
    payload = {
        "tool_name": "Bash",
        "tool_use_id": "toolu_x",
        "tool_input": {"command": "ls"},
        "tool_response": [{"type": "text", "text": _big()}],
    }
    assert _run(payload, tmp_path)


def test_no_partial_files_are_left_behind(tmp_path):
    _run(_payload(_big()), tmp_path)
    spill = tmp_path / "agentic-tools" / "token-savings" / "spill"
    assert list(spill.glob("*.part")) == []


def test_bash_output_is_replaced_with_the_tools_own_object_shape(tmp_path):
    """The trap this guards: built-in tools return structured objects, and per the
    hook docs "a value that doesn't match the tool's output schema is ignored and
    the original output is used" -- silently. An earlier version emitted a bare
    string, so the hook was a complete no-op that looked like it worked."""
    value = _raw(_payload(_big()), tmp_path)
    assert isinstance(value, dict), f"Bash needs an object, got {type(value).__name__}"
    assert set(value) == {"stdout", "stderr", "interrupted", "isImage"}
    assert isinstance(value["interrupted"], bool)
    assert isinstance(value["isImage"], bool)
    assert "[token-savings]" in value["stdout"]


def test_an_mcp_tool_may_receive_a_string(tmp_path):
    """MCP output is passed through without schema validation."""
    payload = {
        "tool_name": "mcp__example__run",
        "tool_use_id": "toolu_x",
        "tool_input": {"command": "x"},
        "tool_response": _big(),
    }
    assert isinstance(_raw(payload, tmp_path), str)


def test_emits_only_fields_claude_accepts(tmp_path):
    environment = dict(os.environ)
    environment["XDG_STATE_HOME"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(_payload(_big())),
        capture_output=True,
        text=True,
        env=environment,
    )
    emitted = json.loads(proc.stdout)["hookSpecificOutput"]
    assert emitted["hookEventName"] == "PostToolUse"
    assert "updatedToolOutput" in emitted
    # Codex rejects this field outright; it must never be emitted.
    assert "updatedMCPToolOutput" not in emitted
    assert "permissionDecision" not in emitted


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not json at all but long enough " * 500,
        "[]",
        "null",
        '{"tool_name":"Bash"}',
        '{"tool_name":"Bash","tool_response":' + '"x' * 8000,
    ],
)
def test_malformed_payloads_fail_open(raw, tmp_path):
    assert _run(raw, tmp_path) == ""


def test_unwritable_state_dir_fails_open(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    assert _run(_payload(_big()), blocked) == ""


def test_a_result_the_summary_would_not_shrink_is_untouched(tmp_path):
    """The head/tail window plus the retrieval footer can exceed a short result.
    Rewriting one would cost tokens and hide nothing."""
    # Over the threshold in BYTES but only a few lines, so head+tail covers it
    # all and the footer is pure overhead.
    text = ("x" * 700 + "\n") * 4
    assert _run(_payload(text), tmp_path) == ""
    assert _spill_files(tmp_path) == []


def test_head_tail_window_matches_the_threshold(tmp_path):
    """A window larger than typical results at the threshold spills them for no
    gain, so the two constants must be tuned together."""
    body = SCRIPT.read_text()
    threshold = int(
        re.search(r"^SPILL_THRESHOLD_BYTES = ([\d_]+)", body, re.M).group(1).replace("_", "")
    )
    head = int(re.search(r"^HEAD_LINES = (\d+)", body, re.M).group(1))
    tail = int(re.search(r"^TAIL_LINES = (\d+)", body, re.M).group(1))
    # A typical line is ~40 bytes, so the window must not span more bytes than
    # the threshold admits, or every borderline result is spilled pointlessly.
    assert (head + tail) * 40 <= threshold * 2, (
        f"window {head}+{tail} lines is too wide for a {threshold}-byte threshold"
    )


def test_prune_bounds_the_store(tmp_path):
    """A spill store must not grow without limit."""
    spill = tmp_path / "agentic-tools" / "token-savings" / "spill"
    spill.mkdir(parents=True)
    for i in range(210):
        (spill / f"old{i:04d}.txt").write_text("x")
    _run(_payload(_big()), tmp_path)
    assert len(list(spill.glob("*.txt"))) <= 201
