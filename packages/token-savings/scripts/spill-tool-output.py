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

CLAUDE ONLY. This rewrites a tool result via
`hookSpecificOutput.updatedToolOutput`, which Codex does not implement: its
`PostToolUse` wire struct carries `hookEventName`, `additionalContext`, and
`updatedMCPToolOutput`, and it rejects the last one. So this ships in the Claude
hook manifest only, and the Codex manifest omits it rather than installing a
hook that would silently do nothing.

Deliberately conservative. Output under the threshold is untouched, a failing
command is never truncated (the agent needs the error), and anything unparseable
fails open. Spill files are pruned by age and count so this cannot fill a disk.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope: this runs after every Bash call.

# Below this, truncation is not worth a retrieval handle. Tuned against 4,417
# real tool results from a 4,107-file repository's transcripts, where `Bash`
# owns 69% of all transcript bytes:
#
#   threshold   results hit   bytes saved   share of all transcript bytes
#      12 KB             24       300,922                              8%
#       8 KB             48       377,012                             10%
#       4 KB            146       464,193                             12%
#       2 KB            344       524,763                             14%
#
# 4 KB is the knee. Going to 2 KB adds two points while spilling 198 more
# results, and a 2 KB result is often small enough that the head/tail plus the
# retrieval instructions is barely a saving at all.
#
# Do not expect more than this: 48% of transcript bytes live in results UNDER
# 2 KB, a long tail no size threshold can reach.
SPILL_THRESHOLD_BYTES = 4_000

# Kept from each end. Enough for a test summary, a stack trace tail, or a build
# verdict without reproducing the body.
HEAD_LINES = 40
TAIL_LINES = 60

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
    """
    lines = text.splitlines()
    head = lines[:HEAD_LINES]
    tail = lines[-TAIL_LINES:] if len(lines) > HEAD_LINES + TAIL_LINES else []
    hidden = len(lines) - len(head) - len(tail)
    first_hidden = len(head) + 1 + line_offset

    parts = [
        f"[token-savings] Output was {len(text)} bytes across {len(lines)} lines. "
        f"Full text saved to:\n  {path}",
        "",
        f"--- first {len(head)} lines ---",
        *head,
    ]
    if tail:
        parts += [
            "",
            f"--- {hidden} lines omitted ---",
            "",
            f"--- last {len(tail)} lines ---",
            *tail,
        ]
    parts += [
        "",
        "To see the omitted part, DO NOT re-run the command. Read the file:",
        f"  rg <pattern> {path}",
        f"  sed -n '{first_hidden},{first_hidden + 199}p' {path}",
        f"  wc -l {path}",
    ]
    if command:
        parts.append(f"Command was: {command}")
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

    prune(directory)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "updatedToolOutput": build_summary(text, path, command, line_offset),
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
