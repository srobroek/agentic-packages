#!/usr/bin/env python3
"""PostToolUse:Bash -- move oversized shell output to disk and leave the agent a
retrieval handle instead of the whole dump.

WHAT THIS IS. `rtk` shrinks output it has a filter for. This catches what is left:
a 200 KB test log, a dependency tree, an unrecognized tool's verbose run. The
full text goes to a file, and what enters the transcript is a head, a tail, and
the exact commands to retrieve any part of it.

WHY THE HEAD AND TAIL MATTER. A pure pointer would force a second tool call to
learn anything, so the truncation would just be deferred cost. For the shapes
that actually blow up -- a test run, a build, a stack trace -- the verdict is in
the last lines and the invocation is in the first, so a head plus tail answers
most questions with no retrieval at all. Retrieval is the fallback, not the plan.

ORDERING, since it decides whether this works at all. `PostToolUse` fires after
the tool has run, and `updatedToolOutput` replaces the result "before it is sent
to Claude" (Claude Code hook docs). So the model never sees the original: the
side effects have already happened and cannot be undone, but the OUTPUT is
substituted before it reaches context. That is the whole mechanism.

THE SHAPE IS MANDATORY AND FAILS SILENTLY. Built-in tools return structured
objects, not strings: `Bash` returns `{stdout, stderr, interrupted, isImage}`.
Per the docs, "for built-in tools, a value that doesn't match the tool's output
schema is ignored and the original output is used" -- no error, no warning. An
earlier version of this hook emitted a bare string and was therefore a complete
no-op that looked like it worked. Emit the object.

CLAUDE ONLY. Codex's `PostToolUse` wire struct carries `hookEventName`,
`additionalContext`, and `updatedMCPToolOutput`, and rejects the last one, so it
cannot replace a tool result at all. This ships in the Claude manifest only.
(`updatedMCPToolOutput` is deprecated upstream in favour of `updatedToolOutput`,
which covers every tool.)

WHERE THE NATIVE CAP TAKES OVER. Claude Code truncates oversized Bash output on
its own, into a `<persisted-output>` block with a HEAD-ONLY preview, and it runs
FIRST -- when it fires, this hook never sees the result. Bracketed by reading
transcript `tool_result` blocks: 23,892 B untouched, 31,393 B truncated, so the
native default sits between 24 KB and 31 KB. This hook owns 2 KB to about 30 KB.
Any coverage figure derived by replaying transcript results against this logic
ALONE is an upper bound, because it counts the largest results too.

WHY `BASH_MAX_OUTPUT_LENGTH=2000` IS NOT A SUBSTITUTE. It moves the native cap
down over this same range, and the result is worse, because native keeps the head
while this keeps head 20 AND tail 30. On a 20,704-byte test log whose only failure
sits on the second-to-last line, asked which test failed: native needed 4 tool
calls (it followed up with `Read`) and put 26,456 bytes of tool results in context,
MORE than the untruncated output. This hook answered from the summary in 2 calls
and 1,798 bytes. A test run, a build, and a stack trace all put the verdict last.

Deliberately conservative. Output under the threshold is untouched, a failing
command is never truncated (the agent needs the error), and anything unparsable
fails open. Spill files are pruned by age and count so this cannot fill a disk.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope: this runs after every Bash call.

# Below this, truncation is not worth a retrieval handle. Re-tuned against 32,957
# real tool results harvested across 651 local repositories, excluding results
# already shaped by a hook or the native cap, and counting only the sub-native
# band this hook can actually claim:
#
#   threshold   head/tail   spilled   bytes saved   share of sub-native bytes
#      2 KB         20/30      3,487     8,578,237                      25.6%
#      1 KB         15/25      6,165    10,614,207                      31.7%
#      1 KB         10/20      6,791    12,379,880                      37.0%
#    500 B          10/15      7,994    12,898,559                      38.6%
#
# 1 KB at 15/25 is the choice, and the last two rows are why it is not 500 B or a
# narrower window. Saved bytes keep rising, so bytes alone would pick the bottom
# row; what stops it is how much of a result stays READABLE. At 15/25 the median
# spill leaves 62% of its lines visible and the 10th percentile 38%; at 10/20 that
# falls to 50% and 29%, so a third of spills become mostly-hidden for another five
# points. 500 B buys 0.9 points over 1 KB/10-20 and spills 1,200 more results.
#
# The window must shrink WITH the threshold: a 40/60 window is wider than most
# 1 KB results, so it spills them for no gain. Below 500 B the window stops being
# useful rather than merely smaller: 1,069 spilled results fit ENTIRELY inside a
# 20/30 window at that threshold, so the hook would rewrite them, add a retrieval
# footer, and hide nothing.
#
# Lowering this to 1 KB only became worthwhile once the footer shrank. Overhead is
# FIXED per spill, so it sets the floor: the summary used to repeat the spill path
# four times, 555 bytes against a 2,000-byte threshold. Binding the path once to
# `$F` cut that to 206, which is what makes 1 KB pay.
#
# Still a floor rather than a solved problem: results under 1 KB hold 7.9 MB of the
# corpus's 33.5 MB, and no size threshold reaches them.
SPILL_THRESHOLD_BYTES = 1_000

# Kept from each end. Enough for a test summary, a stack trace tail, or a build
# verdict without reproducing the body. Narrowed with the threshold, since a
# window wider than the results it sees spills them for no gain.
HEAD_LINES = 15
TAIL_LINES = 25

# Prune: keep the store bounded without a background process.
MAX_SPILL_FILES = 200
MAX_SPILL_AGE_SECONDS = 7 * 24 * 60 * 60


def spill_dir() -> str:
    import os

    base = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state"
    )
    return os.path.join(base, "agentic-tools", "token-savings", "spill")


def prune(directory: str) -> None:
    """Bound the store by age and count. Never raises."""
    import os
    import time

    try:
        entries = []
        now = time.time()
        with os.scandir(directory) as scanner:
            for entry in scanner:
                if not entry.is_file():
                    continue
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                if now - mtime > MAX_SPILL_AGE_SECONDS:
                    try:
                        os.unlink(entry.path)
                    except OSError:
                        pass
                    continue
                entries.append((mtime, entry.path))
        if len(entries) > MAX_SPILL_FILES:
            entries.sort()
            for _, path in entries[: len(entries) - MAX_SPILL_FILES]:
                try:
                    os.unlink(path)
                except OSError:
                    pass
    except OSError:
        pass


def extract_output(payload: dict) -> str | None:
    """Pull the textual result out of the several shapes callers send."""
    for key in ("tool_response", "tool_result", "result"):
        container = payload.get(key)
        if isinstance(container, str):
            return container
        if isinstance(container, dict):
            for field in ("stdout", "output", "content", "text"):
                value = container.get(field)
                if isinstance(value, str) and value:
                    # A dict carrying stderr as well: keep both, in order, so a
                    # spilled result is the whole story.
                    stderr = container.get("stderr")
                    if field == "stdout" and isinstance(stderr, str) and stderr:
                        return value + stderr
                    return value
        if isinstance(container, list):
            parts = []
            for block in container:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                elif isinstance(block, str):
                    parts.append(block)
            if parts:
                return "\n".join(parts)
    return None


def failed(payload: dict) -> bool:
    """A nonzero exit means the agent needs the error text intact."""
    for key in ("tool_response", "tool_result", "result"):
        container = payload.get(key)
        if isinstance(container, dict):
            for field in ("exit_code", "exitCode", "returncode"):
                code = container.get(field)
                if isinstance(code, int) and code != 0:
                    return True
                if isinstance(code, str) and code.strip().lstrip("-").isdigit() and int(code) != 0:
                    return True
            if container.get("is_error") is True or container.get("isError") is True:
                return True
    return False


def build_summary(text: str, path: str, command: str, line_offset: int = 0) -> str:
    """Render the head/tail summary.

    `line_offset` is how many lines the spill file carries BEFORE the output
    itself (the `$ command` header and its blank line). Without it the `sed`
    range printed here is off by that much, and an agent following the
    instruction silently re-reads lines it already has.

    THE PATH APPEARS ONCE. An earlier version repeated it in the header and in
    all three retrieval commands: 4 x 85 bytes on a real spill path, against a
    threshold of 2,000. Bound to `$F` instead, the footer costs 85 bytes plus one
    short line per command, which is what makes a threshold below 2 KB viable at
    all -- the overhead is fixed, so it is the whole reason a small result cannot
    be usefully spilled.
    """
    lines = text.splitlines()
    head = lines[:HEAD_LINES]
    tail = lines[-TAIL_LINES:] if len(lines) > HEAD_LINES + TAIL_LINES else []
    hidden = len(lines) - len(head) - len(tail)
    first_hidden = len(head) + 1 + line_offset

    parts = [
        f"[token-savings] {len(text)}B/{len(lines)}L",
        "",
        f"--- first {len(head)} ---",
        *head,
    ]
    if tail:
        parts += [
            "",
            f"--- {hidden} omitted ---",
            "",
            f"--- last {len(tail)} ---",
            *tail,
        ]
    # "do not re-run" stays despite the byte cost: re-running is the failure this
    # replaces, and the side effects have already happened once.
    parts += [
        "",
        f'F="{path}"  # do not re-run',
        f"sed -n '{first_hidden},{first_hidden + 199}p' \"$F\"  # rg <pat> \"$F\"",
    ]
    return "\n".join(parts)


def main() -> int:
    raw = sys.stdin.buffer.read()
    # Cheap bail: nothing under the threshold can need spilling, and the payload
    # is always larger than the output it carries.
    if len(raw) < SPILL_THRESHOLD_BYTES:
        return 0

    import json

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    if failed(payload):
        return 0

    text = extract_output(payload)
    if not isinstance(text, str) or len(text) < SPILL_THRESHOLD_BYTES:
        return 0

    # Already spilled by a previous pass: never nest.
    if text.startswith("[token-savings]"):
        return 0

    import os

    directory = spill_dir()
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        return 0

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    command = ""
    if isinstance(tool_input, dict):
        candidate = tool_input.get("command")
        command = candidate if isinstance(candidate, str) else ""
    elif isinstance(tool_input, str):
        command = tool_input

    import hashlib

    # Name by content hash plus the tool_use_id, so a repeated identical command
    # reuses one file and two different calls never collide.
    digest = hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()[:12]
    use_id = payload.get("tool_use_id")
    suffix = use_id[-8:] if isinstance(use_id, str) and use_id else "nocall"
    path = os.path.join(directory, f"{digest}-{suffix}.txt")

    # The header occupies two lines ahead of the output, which the summary's
    # `sed` range has to account for.
    line_offset = 2 if command else 0

    # Decide BEFORE writing. The summary can exceed a short result, and a hook that
    # writes the spill file and then declines to use it leaves an orphan the prune
    # has to collect -- pure disk churn for a result the agent reads in full anyway.
    if len(build_summary(text, path, command, line_offset)) >= len(text):
        return 0
    try:
        # Write via a temp file and rename so a concurrent reader never sees a
        # partial spill.
        temporary = path + ".part"
        with open(temporary, "w", encoding="utf-8", errors="replace") as handle:
            if command:
                handle.write(f"$ {command}\n\n")
            handle.write(text)
        os.replace(temporary, path)
    except OSError:
        return 0

    summary = build_summary(text, path, command, line_offset)

    # Never make a result BIGGER. The head/tail window plus the retrieval footer
    # can exceed a short result, and rewriting one then costs tokens and hides
    # nothing. Measured at a 500-byte threshold this affected 1,069 results; the
    # check makes the threshold safe to lower without auditing the window again.
    if len(summary) >= len(text):
        return 0

    prune(directory)

    # Mirror the tool's own output shape. `Bash` returns a structured object, and
    # a mismatched shape is silently discarded in favour of the original.
    replacement: object
    if tool_name == "Bash":
        replacement = {
            "stdout": summary,
            "stderr": "",
            "interrupted": False,
            "isImage": False,
        }
    else:
        # An MCP tool's output is passed through without schema validation, so a
        # string is accepted there.
        replacement = summary

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "updatedToolOutput": replacement,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        raise SystemExit(0)
