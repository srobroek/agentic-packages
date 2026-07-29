"""Coverage for read-truncation-notice.py, the PostToolUse:Read silent-loss notice.

The hook exists because `Read` past its token cap returns a prefix and says
nothing. One property decides whether it is trustworthy: it must fire when, and
only when, the runtime says the read was truncated. A false positive tells the
agent to re-read a file it already holds in full; a false negative leaves the
original defect in place.

Every payload shape here is the real one, taken from a probe hook attached to a
live session rather than written from the docs: `tool_response.file` carries
`content`, `filePath`, `numLines`, `startLine`, `totalLines`, and
`truncatedByTokenCap`.

Claude-only by construction, since Codex has no `Read` tool of this shape.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "read-truncation-notice.py"


def _payload(*, truncated, seen=2860, total=4001, start=1, drop_counts=False):
    file_block = {
        "filePath": "/repo/biglog.txt",
        "content": "line 1\nline 2\n",
        "startLine": start,
    }
    if not drop_counts:
        file_block["numLines"] = seen
        file_block["totalLines"] = total
    if truncated is not None:
        file_block["truncatedByTokenCap"] = truncated
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_response": {"type": "text", "file": file_block},
    }


def _run(payload) -> str:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], input=raw, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.strip()
    if not out:
        return ""
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_a_truncated_read_is_reported_with_both_counts():
    notice = _run(_payload(truncated=True))
    assert "2860" in notice and "4001" in notice
    # The shortfall is stated outright, so the agent need not subtract.
    assert "1141" in notice


def test_the_notice_names_the_offset_that_continues_the_read():
    assert "offset=2861" in _run(_payload(truncated=True))


def test_a_complete_read_is_left_alone():
    """The flag is ABSENT on a complete read -- verified against a live session."""
    assert _run(_payload(truncated=None, seen=3, total=3)) == ""


def test_an_explicit_false_flag_is_left_alone():
    assert _run(_payload(truncated=False)) == ""


def test_the_hook_emits_additional_context_and_never_rewrites_the_result():
    """Rewriting would risk the content; appending a notice cannot lose data."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(_payload(truncated=True)),
        capture_output=True,
        text=True,
    )
    emitted = json.loads(proc.stdout)["hookSpecificOutput"]
    assert "additionalContext" in emitted
    assert "updatedToolOutput" not in emitted


def test_counts_that_describe_no_shortfall_are_left_alone():
    """A flag with counts that do not disagree is not evidence of loss."""
    assert _run(_payload(truncated=True, seen=4001, total=4001)) == ""


def test_a_missing_start_line_defaults_to_one():
    notice = _run(_payload(truncated=True, start=None))
    assert "lines 1-2860" in notice


def test_every_malformed_payload_fails_open():
    for payload in (
        "",
        "not json",
        "[]",
        "null",
        json.dumps({}),
        json.dumps({"tool_response": "a string"}),
        json.dumps({"tool_response": {"file": "not a dict"}}),
        json.dumps(_payload(truncated=True, drop_counts=True)),
    ):
        assert _run(payload) == "", payload
