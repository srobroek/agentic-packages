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

Fails open: an unparsable payload, a missing rtk, or any exception allows the
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
# BLOCKLIST, not an allowlist. rtk ships ~56 filters and an allowlist covered 32
# of them, leaving 20 as unrealised saving that drifted every time rtk added one.
# So route by default and name only what MEASURABLY breaks. The trade is explicit:
# a filter nobody has evaluated now gets routed, and the failure mode moves from
# "a saving we did not take" to "output we did not verify". `rtk-verify.py`
# re-runs the sweep that populated this list against the installed rtk version.
#
# Every entry below was reproduced, most on both a real repository and a minimal
# fixture. The comment is the reason, and a reason is required to add one.
BLOCKED_BINARIES = frozenset(
    {
        # exit 1 becomes exit 0 AND the line number is dropped
        # (`./main.go:11:6:` renders as `main.go (1 issues)`), so a linter reports
        # clean while findings exist. CI and the agent both read that exit code.
        "golangci-lint",
        # Dropped four of six directories, announcing `+130 more` with no tee log
        # and therefore no way back.
        "find",
        # The output IS the number; filtering it is either pointless or wrong.
        "wc",
        # JSON/schema-oriented: passed an 89 KB HTML page through byte for byte.
        "curl",
    }
)

# Subcommands and flag shapes that break even though the binary is fine.
BLOCKED_SUBCOMMANDS = frozenset(
    {
        # `git log` unbounded returns 10 of 25 commits with NO omission marker and
        # no tee log, so the agent cannot tell it is reading a prefix of history.
        # `--oneline` and an explicit count are lossless; `--stat` and `--graph`
        # truncate the same way, which is why the check below is a flag allowlist
        # rather than a flag blocklist.
        ("git", "log"),
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
    # `rtk cargo test --no-run` emits ZERO bytes and exits 0, discarding the
    # "Finished" line and every built test-executable path. Reproduced on 0.44.1
    # both on a 4,107-file workspace (32,031 native bytes to 0) and on a
    # two-file fixture (151 to 0). rtk's test filter looks for a result tally
    # that a compile-only run never prints, and emits nothing rather than
    # falling back. Total silent loss, so never route it.
    "--no-run",
)

# Flags whose meaning depends on the command, so a global ban is wrong. `-q` is
# "machine-quiet" to git and "less verbose" to pytest; `-c` is "count" to grep
# and "config" to git. Keyed by the binary, checked only for that binary.
AMBIGUOUS_MACHINE_FLAGS = {
    # A count is the whole output, so filtering it is either pointless or wrong.
    # `-l`/`--files-with-matches` is a short file list that rtk passes through
    # unchanged, so there is nothing to gain and a parser may consume it.
    "rg": ("-c", "--count", "--count-matches", "-l", "--files-with-matches", "--json"),
    "grep": ("-c", "--count", "-l", "--files-with-matches"),
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


def _rtk_would_filter(command: str) -> bool:
    """Does rtk have a filter for this command?

    `rtk rewrite <cmd>` prints the rewritten form when rtk recognises the command
    and nothing when it does not, so it answers the question authoritatively for
    the INSTALLED version. That is the point of consulting it instead of copying
    a list of filter names: rtk 0.44 added `uv run` and `git checkout`, and a
    hardcoded list would have gone stale silently.

    A subprocess on the hot path is affordable here because this runs only after
    the byte-level bail and the blocklist, so the common command never reaches it.
    Fails CLOSED on error: if rtk cannot answer, do not route.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["rtk", "rewrite", command],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(result.stdout.strip())


def _bail_early(raw: bytes) -> bool:
    """Cheapest possible reject, before any JSON parse.

    With a blocklist there is no short list of names to test for, so this can only
    reject what is structurally unroutable: a payload with no `tool_input` at all.
    The real filtering happens in `_rewrite`, and `_rtk_would_filter` is the
    expensive step -- it sits behind the pipeline, redirect, and flag checks so a
    compound command never pays for it.
    """
    return b"tool_input" not in raw


def _rewrite(command: str) -> str | None:
    """Rewrite whatever segments of a `;`-separated command are safely routable.

    A `;` chain is a SEQUENCE of independent commands sharing one Bash call, not
    a data pipeline: `echo "=== A ==="; cargo build | tail -2` runs two unrelated
    things, and filtering the second cannot affect the first. This is the single
    biggest blocker in real traffic (649 of 1,043 rtk-filterable commands in one
    repository's history), so each segment is considered on its own and only the
    routable ones are rewritten. `&&` and `||` are NOT split here: they carry
    exit-status control flow between the parts.
    """
    if ";" in command:
        segments = _split_unquoted(command, ";")
        if segments is None:
            # Unbalanced quotes, or a `;` that only appears inside a quoted
            # string: nothing to split, so judge the whole command as one.
            return _rewrite_segment(command)
        rewritten_any = False
        results = []
        for segment in segments:
            candidate = _rewrite_segment(segment.strip())
            if candidate is None:
                results.append(segment)
            else:
                # Preserve the segment's original leading whitespace so the
                # reassembled command reads the same as the author wrote it.
                lead = segment[: len(segment) - len(segment.lstrip())]
                results.append(lead + candidate)
                rewritten_any = True
        return ";".join(results) if rewritten_any else None
    return _rewrite_segment(command)


def _has_unquoted(text: str, markers: tuple[str, ...]) -> bool:
    """Is any marker present outside quotes? Markers may be multi-character."""
    stripped: list[str] = []
    quote: str | None = None
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            continue
        stripped.append(char)
    bare = "".join(stripped)
    return any(marker in bare for marker in markers)


def _split_unquoted(text: str, sep: str) -> list[str] | None:
    """Split on `sep` only where it is OUTSIDE quotes and not backslash-escaped.

    A naive `str.split(";")` corrupts `git log --grep="a;b"` and every `bd note x
    "step one; step two"`, which real history is full of. Returns None when the
    separator never occurs unquoted (so there is nothing to split) or when the
    quoting is unbalanced (so the guard should not guess).
    """
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char == sep:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if quote is not None:
        return None
    parts.append("".join(current))
    return parts if len(parts) > 1 else None


def _rewrite_segment(command: str) -> str | None:
    """Return the rtk-prefixed command, or None to leave it untouched."""
    import shlex

    if command.strip().startswith("rtk "):
        return None  # already routed; never double-wrap

    # `2>&1` merges stderr into stdout and `2>/dev/null` discards it; neither
    # sends the command's OUTPUT to a file, and between them they appear on most
    # real build and test commands. Neutralize both exact forms before the
    # redirection check, so `cmd 2>&1 | tail -50` and
    # `gh run view --log-failed 2>/dev/null | tail -30` are reachable.
    #
    # `&>` is deliberately NOT neutralized: `&> file` redirects both streams to a
    # file, so stripping it made `cargo clippy &> /tmp/out` look routable when its
    # output goes to disk rather than to the model.
    def _strip_stderr_forms(text: str) -> str:
        return text.replace("2>&1", "").replace("2>/dev/null", "").replace("2> /dev/null", "")

    probe = _strip_stderr_forms(command)

    # `cd <dir> && <cmd>` is the single most common real shape (12,393 of 24,725
    # local Bash calls start with `cd`). The `cd` is not something rtk would
    # filter and it does not consume the command's output, so rewrite what
    # follows and keep the prefix verbatim: `cd X && rtk cargo build` is
    # equivalent to `cd X && cargo build`, verified. Only a SINGLE leading
    # `cd <one-token> &&` is unwrapped; anything more complex falls through to
    # the chain rejection below.
    prefix = ""
    stripped = command.strip()
    import re

    cd_match = re.match(r"^(cd\s+[^\s&;|<>]+\s*&&\s*)(.+)$", stripped, re.S)
    if cd_match:
        prefix = cd_match.group(1)
        command = cd_match.group(2).strip()
        probe = _strip_stderr_forms(command)

    # Test the markers OUTSIDE quotes only. A quoted `;` or `>` is data, not
    # shell syntax: `git log --grep="a;b" -5` and `cargo build --features 'a;b'`
    # were both refused while a raw substring check ran the show.
    if _has_unquoted(probe, PIPELINE_MARKERS):
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
        return prefix + " | ".join([rewritten_head] + [s.strip() for s in downstream])

    rewritten = _rewrite_simple(command)
    return None if rewritten is None else prefix + rewritten


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

    if binary in BLOCKED_BINARIES:
        return None

    # rtk only filters commands it has a filter for; prefixing anything else just
    # adds a process. `rtk rewrite` is rtk's own answer to "would you touch this",
    # so ask it rather than maintaining a parallel list of 56 filter names.
    # Consult rtk with the command as IT would see it: after the env assignments
    # and the `timeout <n>` wrapper are stripped. rtk declines
    # `timeout 600 cargo clippy` outright while claiming `cargo clippy`, so asking
    # with the wrapper attached would refuse every wrapped build and test command,
    # which is most of them in real history.
    if not _rtk_would_filter(" ".join(tokens[index:])):
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
