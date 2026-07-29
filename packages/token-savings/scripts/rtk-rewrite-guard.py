#!/usr/bin/env python3
"""PreToolUse:Bash -- route selected read-only commands through `rtk` to shrink
their output, and leave everything else alone.

WHY NOT `rtk hook claude`. rtk ships its own PreToolUse handler that rewrites
every command it recognizes. Measured against 0.43.0 on this repository's own
traffic, that handler rewrites cases where the output is machine-parsed rather
than model-read, and rtk's filters are not byte-faithful:

  - `git status --porcelain` is rewritten to `rtk git status --porcelain`. The
    content survives, but rtk drops the TRAILING NEWLINE, so a
    `| wc -l` pipeline silently under-counts by one and `read -r` in a shell
    loop loses the last record.
  - `rtk grep` truncates: 400 matching lines came back as 25 plus a pointer to
    a tee log. That is the right trade for a model reading matches and the
    wrong one for `grep -c` or a pipeline that counts them.

Both are correct behavior for a token filter and wrong for a parsed pipeline,
and rtk cannot tell the two apart because the distinction is in the CALLER'S
intent, not the command text. So this guard inverts rtk's default: rewrite only
what an allowlist names, and bail whenever the command shows any sign that its
output is consumed by something other than the model.

Savings are real but bounded, and the bound is worth stating plainly: the hook
sees only `Bash`. Claude's native `Read`, `Grep`, and `Glob` never reach it, and
`rtk discover` over 30 days of local history found the biggest misses to be
`rg -n` and `cat -n` -- shell spellings of tools the agent is separately steered
to use natively. Do not expect this to be the dominant lever; measure it with
`tokenmeter.py` before believing any number, including this package's.

Fails open: an unparseable payload, a missing rtk, or any exception allows the
command through untouched.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This runs on every Bash call the agent makes, and
# the repository's hook contract puts a per-call budget ahead of tidy imports;
# `json`, `re`, `os`, and `shutil` are imported inside the functions that reach
# them, after the cheap bail below has already returned for most payloads.

# Subcommand allowlist: `rtk <verb>` forms whose filtered output was checked to
# be a faithful, merely-shorter rendering for a model reader. Each entry is a
# (command, first-arg) pair so `git log` can be allowed while `git rev-parse`
# and `git status` are not.
#
# Deliberately absent, with reasons:
#   git status      -- trailing newline dropped; `--porcelain` is parsed
#   git rev-parse   -- single-token output, nothing to save, always parsed
#   grep / rg       -- truncates to ~25 lines; correct for reading, fatal for -c
#   wc              -- the output IS a count; filtering it is nonsense
#   curl            -- response bodies are parsed as often as read
#   jq / python3    -- output shape is the caller's contract
ALLOWED = frozenset(
    {
        ("git", "log"),
        ("git", "diff"),
        ("git", "show"),
        ("git", "blame"),
        ("gh", "pr"),
        ("gh", "issue"),
        ("gh", "run"),
        ("docker", "ps"),
        ("docker", "images"),
        ("kubectl", "get"),
        ("kubectl", "describe"),
        ("cargo", "build"),
        ("cargo", "clippy"),
        ("cargo", "test"),
        ("pytest", None),
        ("ruff", "check"),
        ("tsc", None),
        ("eslint", None),
    }
)

# Any of these in the command means something downstream consumes the bytes, so
# a filtered rendering could change a result rather than just shorten it.
# Checked against the raw string before tokenizing, because the cost of a false
# negative here is a wrong answer the agent cannot detect.
PIPELINE_MARKERS = ("|", ">", ">>", "<", "$(", "`", "&&", "||", ";")

# Flags that mean "emit a machine format". A filter may reflow these safely for
# a reader and still break the parser on the other end.
MACHINE_FLAGS = (
    "--porcelain",
    "--json",
    "-json",
    "--format",
    "--pretty",
    "--quiet",
    "-q",
    "--name-only",
    "--numstat",
    "--raw",
    "-0",
    "--null",
    "--count",
    "-c",
)


def _bail_early(raw: bytes) -> bool:
    """Cheapest possible reject, before any JSON parse.

    Every command this guard can act on names an allowlisted binary, so a
    payload mentioning none of them cannot be rewritten. Kept a strict superset
    of the real trigger: it tests only for the command names, never for the
    subcommand, so it cannot mask a case the structured check would have caught.
    """
    return not any(name.encode() in raw for name, _ in ALLOWED)


def _rewrite(command: str) -> str | None:
    """Return the rtk-prefixed command, or None to leave it untouched."""
    import shlex

    if command.strip().startswith("rtk "):
        return None  # already routed; never double-wrap

    if any(marker in command for marker in PIPELINE_MARKERS):
        return None

    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unbalanced quotes. Whatever this is, it is not a command this guard
        # understands well enough to rewrite.
        return None
    if not tokens:
        return None

    # Skip leading env assignments (FOO=bar cmd ...) so the real verb is found,
    # matching the command-position anchoring the other guards in this repo use.
    index = 0
    while index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("-"):
        index += 1
    if index >= len(tokens):
        return None

    import os

    binary = os.path.basename(tokens[index])
    argument = tokens[index + 1] if index + 1 < len(tokens) else None

    if (binary, argument) not in ALLOWED and (binary, None) not in ALLOWED:
        return None

    if any(flag in tokens for flag in MACHINE_FLAGS):
        return None
    # `--format=x` and `--pretty=y` attach their value with `=`, so the
    # membership test above misses them.
    if any(token.split("=", 1)[0] in MACHINE_FLAGS for token in tokens if "=" in token):
        return None

    # Insert `rtk` at the command position, NOT at the front of the string.
    # Prefixing `FOO=1 cargo clippy` produces `rtk FOO=1 cargo clippy`, where
    # the assignment becomes an argument to rtk instead of environment for
    # cargo -- a different command with a different result.
    if index:
        prefix = " ".join(tokens[:index])
        return f"{prefix} rtk {' '.join(tokens[index:])}"
    return f"rtk {command.strip()}"


def main() -> int:
    raw = sys.stdin.buffer.read()
    if not raw.strip() or _bail_early(raw):
        return 0

    import json

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_input = payload.get("tool_input")
    if isinstance(tool_input, str):
        # Some callers send tool_input as a bare string. Reading `.command` off
        # it would throw and bypass the guard.
        command = tool_input
    elif isinstance(tool_input, dict):
        command = tool_input.get("command")
    else:
        return 0
    if not isinstance(command, str) or not command.strip():
        return 0

    import shutil

    if shutil.which("rtk") is None:
        return 0

    rewritten = _rewrite(command)
    if rewritten is None:
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "token-savings: routed through rtk to shrink output",
                    "updatedInput": {"command": rewritten},
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
        # Fail open: a guard that crashes closed wedges the agent.
        raise SystemExit(0)
