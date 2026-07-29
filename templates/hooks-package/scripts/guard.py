#!/usr/bin/env python3
"""Example PreToolUse:Bash guard. Copy this file and replace the decision.

CRITICAL: this script lives at the PACKAGE ROOT (scripts/guard.py), NOT nested
under .apm/. Hook JSON references it as `${PLUGIN_ROOT}/scripts/guard.py`, which
resolves from the installed plugin root, so root-level scripts/ is the correct
location for HOOK scripts. Skills are the opposite: their scripts nest under the
skill directory, because SKILL.md uses file-relative paths.

SELF-GATING, no `if` filter. The hook JSON deliberately does NOT use the
`"if": "Bash(git push*)"` matcher filter. That pipe/glob filter has been observed
to SILENTLY no-match -- the hook never fires and reports no error -- so a guard
relying on it can be bypassed. The matcher is the broad tool name ("Bash") and
this script decides for itself whether a command is in scope, then exits 0
(allow) when it is not. Keep the gating logic in the script. Codex has no
equivalent of the `if` field at all, so a cross-tool guard must self-filter
regardless.

`tool_input` may be an object (`{"command": "..."}`) OR a bare string. In `jq`,
`.tool_input.command // .tool_input` THROWS on a string, because jq cannot index
one, and a guard that throws silently allows the call. Check the type first --
`isinstance(value, dict)` below.

EXIT 0 WITH A JSON DECISION. Emitting the decision on stdout and exiting 0 is
the contract; a nonzero exit is treated as a hook error. Never emit
`permissionDecision: "ask"`: it waits for a human, so it stalls an autonomous
run, and Codex marks the hook run failed and continues the call anyway. Deny
with guidance the model can act on, or allow with an `additionalContext`
advisory.
"""

from __future__ import annotations

import json
import sys

# Match on the command's VERB, not on a substring of the whole line. A
# `*"git push"*` glob matches `echo "git push"` and a commit message quoting it,
# while missing `env GIT_SSH=x git push` and `sudo git push`. Compare parsed
# words instead: shlex tokenizes, and the wrapper set below keeps the real verb
# in view. The repo's rm -rf guard collected one bypass apiece for wrapper
# prefixes, env assignments, leading tabs, path traversal, and trailing quotes,
# every one a gap in a hand-rolled matcher.
WRAPPERS = frozenset(
    {"sudo", "doas", "env", "time", "nice", "command", "exec", "nohup", "timeout"}
)

# Wrappers whose first non-option word is their OWN operand, not the wrapped
# command: `timeout 5 git push`. Without this, `5` is read as the verb and the
# command behind it goes unjudged.
WRAPPER_OPERAND = frozenset({"timeout", "flock"})

# Wrapper options that take a SEPARATE value, as in `nice -n 19 git push` and
# `sudo -u git git push`. Skipping the flag alone leaves its value in command
# position, which is the same class of gap as the operand case above.
OPTION_TAKES_VALUE = {
    "nice": {"-n"},
    "sudo": {"-u", "-g", "-p", "-C"},
    "doas": {"-u", "-C"},
    "timeout": {"-s", "-k"},
    "flock": {"-c", "-E", "-w", "--timeout"},
}

# Replace this with the verb and subcommand your guard cares about.
GATED_COMMAND = ("git", "push")

# Options of the GATED verb that take a separate value, so its subcommand can be
# located: `git -c user.name=x push` puts `push` in the fourth position, and
# skipping the flag without its value reads `user.name=x` as the subcommand.
GATED_OPTION_TAKES_VALUE = frozenset({"-c", "-C", "--git-dir", "--work-tree"})


def read_command(payload: str) -> str:
    """The shell command from a hook payload, or "" when there is none."""
    try:
        data = json.loads(payload)
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        return command if isinstance(command, str) else ""
    return ""


def verb_words(command: str) -> list[str]:
    """The command's words with wrappers and env assignments stripped.

    `env FOO=1 sudo -u git git push` reduces to `["git", "push"]`, so a verb
    comparison sees the same thing whatever prefixes the agent used.
    """
    import shlex

    try:
        words = shlex.split(command)
    except ValueError:
        # Unbalanced quotes: fail open rather than guess at the intent.
        return []
    while words:
        head = words[0]
        if "=" in head and not head.startswith("="):
            words = words[1:]          # env assignment: FOO=bar cmd
        elif head in WRAPPERS:
            takes_value = OPTION_TAKES_VALUE.get(head, frozenset())
            words = words[1:]
            while words and words[0].startswith("-"):
                option = words[0]
                words = words[1:]
                if option in takes_value and words:
                    words = words[1:]  # the option's separate value
            if head in WRAPPER_OPERAND and words:
                words = words[1:]      # the wrapper's own operand
        else:
            break
    return words


def in_scope(command: str) -> bool:
    """Whether this guard should judge `command`."""
    words = verb_words(command)
    prefix: list[str] = []
    skip_next = False
    for word in words:
        if skip_next:
            skip_next = False
            continue
        if word.startswith("-"):
            skip_next = word in GATED_OPTION_TAKES_VALUE
            continue
        prefix.append(word)
        if len(prefix) == len(GATED_COMMAND):
            break
    return prefix == list(GATED_COMMAND)


def deny(reason: str) -> None:
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
    payload = sys.stdin.read()
    if not payload:
        return 0
    # Bail on the raw bytes before parsing: this hook runs on every Bash call, so
    # the cheap path has to stay cheap. Keep the literal a strict SUPERSET of the
    # real trigger, or it hides a command the structured check would have caught.
    if "push" not in payload:
        return 0

    command = read_command(payload)
    if not command or not in_scope(command):
        return 0

    deny("example guard: git push is gated by this template")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open. An unreadable payload or an unexpected exception allows the
        # call: a guard that crashes closed wedges the agent, while one that
        # crashes open loses a single check.
        raise SystemExit(0)
