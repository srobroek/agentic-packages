#!/usr/bin/env python3
"""PreToolUse:Agent deny gate for Codex fork_turns.

Problem: Codex `spawn_agent` DEFAULTS to a full-history fork -- the released
binary documents "Full-history forks (`fork_turns` omitted or \"all\")".
Copying the entire parent thread into a subagent burns tokens quadratically
across a fan-out and leaks parent context into roles designed to receive a
bounded brief. Subagents in this fleet are written to work from their spawn
prompt alone.

Policy (deny + self-correction guidance, per constitution III -- no "ask"),
applied only to Codex-shaped spawn payloads (Claude Agent calls carry no
task_name/agent_type/fork_turns fields and pass through untouched):
  * fork_turns omitted             -> deny (omitted == "all" upstream)
  * fork_turns == "all"            -> deny
  * numeric fork_turns > FORK_MAX  -> deny (default 3)
  * "none" or number <= FORK_MAX   -> allow

Default 3, not 5: the cap counts turns but cost lives in turn content the
hook cannot see, so it is a heuristic backstop. The legitimate "recent
thread context explicitly required" case is the immediately preceding
exchange (1-3 turns); needing more is the signal to write a complete spawn
brief instead. A false deny costs one self-correcting retry; a false allow
can fork a huge context tail -- asymmetric costs favor the stricter default.
SUBAGENT_FORK_GUARD_MAX relaxes it per-project without a release.

Fail-open: empty stdin or malformed JSON exits 0 with no output. A broken
guard must never block all delegation.
"""

from __future__ import annotations

import sys

# json and os are imported inside main() -- module-scope imports are a fixed
# cost paid on every spawn even when the tool name check bails immediately.

FORMAT_HINT = 'Format: spawn_agent(task_name="code-reviewer", fork_turns="none").'


def _read_stdin_text() -> str:
    """Read the payload as bytes and decode leniently.

    `sys.stdin.read()` raises UnicodeDecodeError on one undecodable byte anywhere in
    the payload -- including in a field the guard never looks at -- and the fail-open
    wrapper then swallowed the error, so a stray byte turned a decision into silence.
    Reproduced on the attribution guard: it denied a valid payload and went silent
    with the same payload plus one bad byte.

    Falls back to a plain read when stdin has no buffer, which is how the tests inject
    a StringIO.
    """
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is None:
        return sys.stdin.read()
    return buffer.read().decode("utf-8", "replace")


def fork_max() -> int:
    import os

    raw = os.environ.get("SUBAGENT_FORK_GUARD_MAX", "3")
    return int(raw) if raw.isdigit() else 3


def deny(reason: str) -> None:
    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


def main() -> int:
    raw = _read_stdin_text()
    if not raw.strip():
        return 0

    import json

    try:
        payload = json.loads(raw)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    if payload.get("tool_name") not in ("Agent", "Task"):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        # A bare-string tool_input (or absent) carries no Codex spawn fields.
        return 0

    # Claude Agent/Task spawns never carry Codex spawn fields; leave them alone.
    is_codex_spawn = any(
        key in tool_input for key in ("task_name", "agent_type", "fork_turns", "fork_context")
    )
    if not is_codex_spawn:
        return 0

    has_fork_turns = "fork_turns" in tool_input
    fork_turns = tool_input.get("fork_turns")

    max_turns = fork_max()

    if not has_fork_turns or fork_turns is None:
        deny(
            "Subagent spawn blocked: fork_turns was omitted, and Codex defaults an "
            "omitted fork_turns to \"all\" (full-history fork of the parent thread). "
            "Re-issue with an explicit fork_turns=\"none\" and put everything the "
            f"subagent needs into the spawn prompt. {FORMAT_HINT} Use a small number "
            f"(<= {max_turns}) only when recent thread context is explicitly required."
        )
        return 0

    if fork_turns == "all":
        deny(
            "Subagent spawn blocked: fork_turns=\"all\" copies the entire parent "
            "thread into the subagent. Re-issue with fork_turns=\"none\" and put "
            f"everything the subagent needs into the spawn prompt. {FORMAT_HINT} Use "
            f"a small number (<= {max_turns}) only when recent thread context is "
            "explicitly required."
        )
        return 0

    # fork_turns may arrive as a JSON number or a numeric string.
    if isinstance(fork_turns, (int, float)) and not isinstance(fork_turns, bool):
        numeric = int(fork_turns)
    elif isinstance(fork_turns, str) and fork_turns.isdigit():
        numeric = int(fork_turns)
    else:
        numeric = None

    if numeric is not None and numeric > max_turns:
        deny(
            f"Subagent spawn blocked: fork_turns={fork_turns} exceeds the maximum of "
            f"{max_turns}. Re-issue with fork_turns=\"none\" (preferred -- pass needed "
            f"context in the spawn prompt) or a value <= {max_turns} when recent "
            f"thread context is explicitly required. {FORMAT_HINT}"
        )
        return 0

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: a broken guard must never block all delegation.
        raise SystemExit(0)
