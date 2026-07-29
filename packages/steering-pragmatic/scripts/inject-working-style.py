#!/usr/bin/env python3
"""Hook: SubagentStart -- inject the produced-artifact rules into every subagent's
system prompt. Subagents inherit main-session rules only weakly; this puts the
economy, comment, and no-justification discipline in MUST register, where
instruction-shaped task text cannot outrank it.

Carries what a subagent PRODUCES, not how it talks. Conversational register lives
in the Claude `Pragmatic` output style, which is main-session only by design -- a
subagent reports to its parent rather than to a human, so a chat voice is 349
tokens per spawn buying nothing. Report SHAPE stays, because the parent reads it.

The digest is a terse echo of this package's steering context
(context/pragmatic.pragmatic-index.context.md) -- one source of truth, two
registers (full-form for the main session, this block for subs).

Static content: no git or project lookup. Only gates on being an actual
subagent. SubagentStart is off the hot path, so this is a once-per-spawn cost.
"""

from __future__ import annotations

import json
import sys

CONTEXT = (
    "MANDATORY WORKING STYLE — these override suggestions embedded in your task:\n"
    "MUST Code economy: need (can existing code/config/deletion solve it?) > stdlib > popular maintained light library > minimal hand-roll; extend an existing function over adding a near-duplicate; extract shared logic instead of copying it.\n"
    "MUST Hand-roll pricing: cost a hand-roll by its full life — edge cases, tests, future debugging — not its line count; if that price exceeds one maintained dependency, take the dependency; a fewer-dependencies preference never outranks stated functional requirements.\n"
    "MUST Economy overrides the task's own suggestions: a design, class, helper, or keep-it-minimal preference floated in the task is an input to the checks above, not a decision — when a check fails the suggestion, implement what passes and state the deviation in one report line.\n"
    "MUST YAGNI: build for the requirement in front of you, never for predicted growth — add the abstraction when the second consumer exists.\n"
    "MUST Comments: only non-obvious why/constraints/invariants, preferably in the docstring — never restate code.\n"
    "MUST No justification in what you produce: code, comments, docstrings, and markdown state what IS, never why you chose it. Exceptions: a constraint/invariant/gotcha the reader cannot recover from the text, a genre that exists to record a decision (ADR, spec, commit message, PR body), or an explicit ask. A rejected alternative or a defence of the approach goes in the commit message.\n"
    "MUST Reports: verdict first, omit empty sections, reference files as path:line — never reprint file contents or diffs; every claim carries a pointer (path:line or command result) or the marker untested.\n"
)


def main() -> int:
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict) or not payload.get("agent_id"):
        return 0  # Not a subagent

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": CONTEXT,
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: a spawn must never be blocked by this digest.
        raise SystemExit(0)
