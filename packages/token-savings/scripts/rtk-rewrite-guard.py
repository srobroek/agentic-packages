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
        # `git log` is admitted only WITH an explicit commit-limiting or compact
        # flag, enforced by GIT_LOG_REQUIRES_LIMIT below. Verified on 0.44.1:
        # `git log --oneline` over 25 commits returned all 25, while bare
        # `git log` returned 10 of 25 with NO omission marker and NO tee-log
        # path. A silently shortened history is the worst case for this hook,
        # because the agent cannot tell it is reading a prefix.
        ("git", "log"),
        ("git", "diff"),
        ("git", "show"),
        ("git", "blame"),
        ("gh", "pr"),
        ("gh", "issue"),
        ("gh", "run"),
        # NOTE: `gh pr` and `gh issue` cover mutating verbs too (`gh pr merge`,
        # `gh pr create`), which MUTATING_SUBVERBS below removes. Found by
        # replaying real command history rather than by review.
        ("docker", "ps"),
        ("docker", "images"),
        ("kubectl", "get"),
        ("kubectl", "describe"),
        ("cargo", "build"),
        ("cargo", "clippy"),
        ("cargo", "test"),
        ("pytest", None),
        # rtk 0.44.0 added a `uv run` filter, and `uv run` was by far the most
        # common unrouted command in local history (5,064 occurrences). Verified
        # on 0.44.1 against a FAILING pytest run, the case where detail matters:
        # the assertion, the failure message, and the `1 failed, 1 passed`
        # verdict all survived at 46% fewer bytes, and a tee log path is named.
        ("uv", "run"),
        ("ruff", "check"),
        ("tsc", None),
        ("eslint", None),
    }
)

# Any of these in the command means something downstream consumes the bytes, so
# a filtered rendering could change a result rather than just shorten it.
# Checked against the raw string before tokenizing, because the cost of a false
# negative here is a wrong answer the agent cannot detect.
PIPELINE_MARKERS = (">", ">>", "<", "$(", "`", "&&", "||", ";")

# A pipe is not automatically disqualifying: it depends on what CONSUMES the
# output. `cmd 2>&1 | tail -50` is the dominant idiom in local history (8,901
# occurrences of tail/head against 2,200 of a real parser) and it is the agent
# hand-truncating because output is too big. rtk does that better: measured on
# `cargo clippy`, `native | tail -50` was 657 bytes and `rtk | tail -50` was 89,
# with the warning, file, and line intact.
#
# So a pipe is allowed when EVERY downstream stage is a pure truncator. Anything
# that counts, searches, or reparses is refused, because rtk reformats and
# truncates: `wc -l` would count summary lines, and `grep ERROR` could miss a
# line rtk dropped.
SAFE_DOWNSTREAM = frozenset({"tail", "head", "cat"})

# Flags that mean "emit a machine format" whatever the command. A filter may
# reflow these safely for a reader and still break the parser on the other end.
MACHINE_FLAGS = (
    "--porcelain",
    "--json",
    "-json",
    "--format",
    "--pretty",
    "--name-only",
    "--numstat",
    "--raw",
    "-0",
    "--null",
    "--count",
)

# Flags whose meaning depends on the command, so a global ban is wrong. `-q` is
# "machine-quiet" to git and "less verbose" to pytest; `-c` is "count" to grep
# and "config" to git. Keyed by the binary, checked only for that binary.
AMBIGUOUS_MACHINE_FLAGS = {
    "git": ("-q", "--quiet", "-c"),
    "gh": ("-q", "--jq", "-t", "--template"),
    "docker": ("-q", "--quiet"),
    "kubectl": ("-o", "--output"),
}

# Third-position verbs that CHANGE something. The allowlist is keyed on the
# first two tokens, so `("gh", "pr")` admits `gh pr view` and `gh pr merge`
# alike. Filtering the output of a merge or a create is never worth it: the
# result is short, and it is the record of a side effect the agent must read
# exactly. Replaying real history surfaced `gh pr merge 249 --squash` and
# `gh pr create --draft ...` being routed, which review had missed.
MUTATING_SUBVERBS = frozenset(
    {
        "create",
        "merge",
        "close",
        "reopen",
        "edit",
        "delete",
        "comment",
        "review",
        "ready",
        "checkout",
        "rerun",
        "cancel",
        "lock",
        "unlock",
        "transfer",
        "pin",
        "unpin",
        "develop",
        "sync",
        "update-branch",
    }
)


def os_basename(path: str) -> str:
    import os

    return os.path.basename(path)


def _is_duration(token: str) -> bool:
    """`600`, `600s`, `2m`: a `timeout` duration rather than a flag or a command."""
    return bool(token) and token[0].isdigit() and token.rstrip("smhd").isdigit()


def _is_count_flag(token: str) -> bool:
    """`-5`, `-n5`, `-n 5`, `--max-count=5`: the caller bounded the commit count."""
    if token.startswith("--max-count"):
        return True
    if token.startswith("-n"):
        return True
    return len(token) > 1 and token[0] == "-" and token[1:].isdigit()


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

    # `2>&1` is a stderr merge, not a redirection to a file, and it appears on
    # nearly every real build/test command. Neutralize that exact form before the
    # redirection check so `cmd 2>&1 | tail -50` is reachable. `&>` is NOT
    # neutralized: `&> file` redirects both streams to a file, so stripping it
    # made `cargo clippy &> /tmp/out` look routable when its output goes to disk.
    probe = command.replace("2>&1", "")

    if any(marker in probe for marker in PIPELINE_MARKERS):
        return None

    # Split on pipes: rewrite the FIRST stage, keep the rest verbatim, and only
    # when every later stage is a pure truncator.
    head, *downstream = command.split("|")
    for stage in downstream:
        words = stage.strip().split()
        if not words or words[0] not in SAFE_DOWNSTREAM:
            return None
    if downstream:
        rewritten_head = _rewrite_simple(head.strip())
        if rewritten_head is None:
            return None
        return " | ".join([rewritten_head] + [s.strip() for s in downstream])

    return _rewrite_simple(command)


def _rewrite_simple(command: str) -> str | None:
    """Rewrite one pipe-free command, or None to leave it alone."""
    import shlex

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

    # Skip a `timeout <seconds>` wrapper, which prefixes a large share of real
    # build and test commands. rtk goes AFTER it, so the timeout still governs the
    # whole pipeline: `timeout 600 rtk uv run pytest`. Only the numeric-argument
    # form is skipped, so `timeout --foo` is left alone rather than guessed at.
    while (
        index + 1 < len(tokens)
        and os_basename(tokens[index]) in ("timeout", "gtimeout")
        and _is_duration(tokens[index + 1])
    ):
        index += 2
    if index >= len(tokens):
        return None

    import os

    binary = os.path.basename(tokens[index])
    argument = tokens[index + 1] if index + 1 < len(tokens) else None

    if (binary, argument) not in ALLOWED and (binary, None) not in ALLOWED:
        return None

    subverb = tokens[index + 2] if index + 2 < len(tokens) else None
    if subverb in MUTATING_SUBVERBS:
        return None

    # `git log` truncates to 10 commits silently unless the caller bounded it.
    # Measured on 0.44.1 over a 25-commit history: `--oneline` returned all 25,
    # while bare `git log`, `--stat`, and `--graph` each returned 10 with no
    # omission marker and no tee-log path. `--stat` and `--graph` were on this
    # list until that measurement removed them, so verify a flag before adding
    # one rather than reasoning about which forms "look compact".
    if binary == "git" and argument == "log":
        bounded = any(
            token == "--oneline" or _is_count_flag(token) for token in tokens[index + 2 :]
        )
        if not bounded:
            return None

    if any(flag in tokens for flag in MACHINE_FLAGS):
        return None
    if any(flag in tokens for flag in AMBIGUOUS_MACHINE_FLAGS.get(binary, ())):
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
