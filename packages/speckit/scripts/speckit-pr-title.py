#!/usr/bin/env python3
"""Remind the author that a PR title becomes a changelog entry.

Squash merge turns the PR title into the release note, so it has to read for end
users rather than for the person who wrote the branch. This is an always-on
advisory on `gh pr create` / `gh pr edit`, never a denial.

Carries the title/body-format half of the retired speckit-pr-issue-refs hook. The
issue-refs half is gone: task state lives in beads, not GitHub issues.

Silent outside a SpecKit project, and silent on any command that is not a PR
create or edit.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This is a PreToolUse:Bash hook, so it runs on every
# shell command the agent issues and the bail in main() has to come before any
# import that costs real time -- `re` alone is about 9ms on this host.

# `gh pr create|edit` directly, through the gh-api.py wrapper, or the GitLab
# equivalent. Anchoring is loose on purpose: this only ever ADDS advice, so a false
# positive costs a paragraph of context rather than a blocked command.
TRIGGER = r"gh pr (?:create|edit)|gh-api\.py.*pr create|glab mr create"

GUIDANCE = """PR TITLE = CHANGELOG ENTRY (via squash merge). Write for end users.

TITLE FORMAT:
- Minor fix: "fix: catalog refresh fails when offline"
- Minor feature: "feat: show version at startup for diagnostics"
- Major feature: "feat: automatic software detection via Windows registry and WMI"
- Breaking change: "feat!: migrate config from TOML to SQLite-backed storage"
- NEVER include spec IDs, task refs, phase names, or internal jargon

PR BODY FORMAT -- scale detail to significance:

MAJOR FEATURES (new capability, large scope):
## Summary
<2-3 sentences: what this adds and why users care>

## What's new
- Bullet points of user-visible changes
- Each bullet is a concrete capability, not an implementation detail

## Breaking changes
<only if applicable -- what breaks, what users need to do>

MINOR CHANGES & BUG FIXES (targeted fix or small enhancement):
## Summary
- Short bullet(s) describing what changed and why

BREAKING CHANGES -- always flag explicitly:
- Add `!` after type in title: "feat!: ..." or "fix!: ..."
- Include a "## Breaking changes" section explaining what breaks and migration steps

Spec context goes at the bottom under "## Spec Context" (not in the title).
The release-please draft PR will be manually curated before publish -- raw material matters."""


def extract_command(payload: str) -> str:
    """Pull the command from a hook payload.

    tool_input is an object for most callers and a bare string for some, so the
    type is checked rather than assumed: the jq idiom this replaced threw on a
    string and silently skipped the hook.
    """
    import json

    data = json.loads(payload)
    if not isinstance(data, dict):
        return ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        return command if isinstance(command, str) else ""
    return ""


def main() -> int:
    import os

    # A SpecKit project or nothing. Checked first because it is a single stat and
    # settles the whole question outside one.
    if not os.path.isdir(".specify"):
        return 0

    payload = sys.stdin.read()
    # Cheap bail on the raw bytes, before any parse or import: every trigger below
    # contains both words. A strict superset of the real trigger, so it cannot mask
    # a command the structured check would have matched.
    if "pr" not in payload or ("gh" not in payload and "glab" not in payload):
        return 0

    try:
        command = extract_command(payload)
    except (ValueError, TypeError):
        return 0
    if not command:
        return 0

    import re

    if not re.search(TRIGGER, command):
        return 0

    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": GUIDANCE,
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
        # Fail open: advice must never wedge a PR command.
        raise SystemExit(0)
