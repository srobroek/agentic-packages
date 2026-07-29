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
import re
import sys
from pathlib import Path

# Match on the command's VERB, not on a substring of the whole line. A
# `*"git push"*` glob matches `echo "git push"` and a commit message quoting it,
# while missing `env GIT_SSH=x git push` and `sudo git push`. Compare parsed
# words instead: shlex tokenizes, and the wrapper set below keeps the real verb
# in view. The repo's rm -rf guard collected one bypass apiece for wrapper
# prefixes, env assignments, leading tabs, path traversal, and trailing quotes,
# every one a gap in a hand-rolled matcher.
WRAPPERS = frozenset(
    {
        "sudo", "doas", "env", "time", "nice", "command", "exec", "nohup",
        # `flock` and the four below appeared in WRAPPER_OPERAND and
        # OPTION_TAKES_VALUE but not here, so `flock /tmp/l git push` was never
        # stripped and the push behind it went unjudged.
        "timeout", "flock", "stdbuf", "setsid", "ionice", "unbuffer",
    }
)

# Wrappers whose first non-option word is their OWN operand, not the wrapped
# command: `timeout 5 git push`. Without this, `5` is read as the verb and the
# command behind it goes unjudged.
WRAPPER_OPERAND = frozenset({"timeout", "flock"})

# Shells whose `-c` argument is itself a command, and builtins that run a string
# as one. shlex sees that argument as ONE token, so `sh -c 'git push'` is a
# single word to the tokenizer and a push to the shell. The string has to be
# lexed again or the verb inside it is invisible.
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "ash", "busybox"})
STRING_EVALUATORS = frozenset({"eval", "source", "."})

# How deep to follow a nested shell string. Real commands nest once or twice; the
# bound only stops a pathological payload from recursing without end.
MAX_NESTING = 4

# Shell keywords, group openers, and terminators. Each begins or ends a command,
# so treating one as a plain word leaves it standing where the verb belongs and
# `if true; then git push; fi` goes unjudged.
COMMAND_BOUNDARIES = frozenset(
    {"do", "then", "else", "elif", "{", "(", "!", "while", "until", "if", "for"}
)
CLOSERS = frozenset({"}", ")", "done", "fi", "esac"})

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Wrapper options that take a SEPARATE value, as in `nice -n 19 git push` and
# `sudo -u git git push`. Skipping the flag alone leaves its value in command
# position, which is the same class of gap as the operand case above.
OPTION_TAKES_VALUE = {
    "nice": {"-n"},
    "sudo": {"-u", "-g", "-p", "-C"},
    "doas": {"-u", "-C"},
    "timeout": {"-s", "-k"},
    "flock": {"-c", "-E", "-w", "--timeout"},
    # `ionice -c 3 git push` leaves the class number in command position unless
    # the option's value is consumed along with the flag.
    "ionice": {"-c", "-n", "-p", "-P", "-u"},
    "stdbuf": {"-i", "-o", "-e"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S"},
    "time": {"-f", "--format", "-o", "--output"},
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


def split_commands(command: str) -> list[list[str]]:
    """Every command position in a shell line, as word lists.

    shlex handles quoting and escapes, so a gated phrase inside a quoted argument
    stays an argument. An unterminated quote is not parseable as shell; the caller
    treats that as nothing to judge rather than guessing at the intent.
    """
    import shlex

    # A newline separates commands exactly like a semicolon, but shlex treats it
    # as ordinary whitespace, which merges the second line into the first and
    # hides its verb. A BACKSLASH-newline is the opposite: a line continuation,
    # so the two halves are one command.
    command = re.sub(r"\\\r?\n", " ", command)
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    words = list(lexer)  # raises ValueError on an unterminated quote

    commands: list[list[str]] = []
    current: list[str] = []
    for word in words:
        # `;`, `&&`, `||` and `|` each start a new command, as do keywords and
        # group delimiters. Without this, `true && git push` read `true` as the
        # only verb and the push behind the operator went unjudged.
        if (word and set(word) <= {";", "&", "|"}) or word in COMMAND_BOUNDARIES or word in CLOSERS:
            if current:
                commands.append(current)
            current = []
            continue
        current.append(word)
    if current:
        commands.append(current)
    return commands


def strip_prefix(words: list[str]) -> list[str]:
    """Drop env assignments and wrappers to reach the real verb.

    `env FOO=1 sudo -u git git push` reduces to `["git", "push"]`, so a verb
    comparison sees the same thing whatever prefixes the agent used.
    """
    while words:
        head = words[0]
        if ASSIGNMENT.match(head):
            words = words[1:]          # env assignment: FOO=bar cmd
        elif Path(head).name in WRAPPERS:
            name = Path(head).name
            takes_value = OPTION_TAKES_VALUE.get(name, frozenset())
            words = words[1:]
            while words and words[0].startswith("-"):
                option = words[0]
                words = words[1:]
                if option in takes_value and words:
                    words = words[1:]  # the option's separate value
            if name in WRAPPER_OPERAND and words:
                words = words[1:]      # the wrapper's own operand
        else:
            break
    return words


def nested_command(words: list[str]) -> str | None:
    """The command string a shell invocation would run, if any."""
    if not words:
        return None
    verb = Path(words[0]).name
    if verb in SHELLS:
        for index, word in enumerate(words[1:], start=1):
            # `-c` may be bundled with other short flags, as in `sh -ec`.
            if word.startswith("-") and not word.startswith("--") and "c" in word:
                return words[index + 1] if index + 1 < len(words) else None
            if not word.startswith("-"):
                return None  # a bare word is a script path, not an inline command
        return None
    if verb in STRING_EVALUATORS:
        # Drop only the evaluator's OWN options, then keep the rest verbatim:
        # `eval git push` and `eval 'git push'` both push, and filtering every
        # `-` word would discard the WRAPPED command's flags too.
        rest = words[1:]
        index = 0
        while index < len(rest) and rest[index].startswith("-"):
            index += 1
        return " ".join(rest[index:]) or None
    return None


def expand_commands(command: str, depth: int = 0) -> list[list[str]]:
    """Every command position, re-lexing nested shell strings so those count too."""
    commands = split_commands(command)
    if depth >= MAX_NESTING:
        return commands
    expanded: list[list[str]] = []
    for words in commands:
        expanded.append(words)
        inner = nested_command(strip_prefix(words))
        if inner:
            try:
                expanded.extend(expand_commands(inner, depth + 1))
            except ValueError:
                continue  # an unparsable inner string leaves the outer judged
    return expanded


def matches_gate(words: list[str]) -> bool:
    """Whether one command position is the gated verb and subcommand."""
    prefix: list[str] = []
    skip_next = False
    for index, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        if word.startswith("-"):
            skip_next = word in GATED_OPTION_TAKES_VALUE
            continue
        # Compare the basename of the VERB only: `/usr/bin/git push` and
        # `./git push` are the same command, while a path traversal in an
        # argument must stay an argument.
        prefix.append(Path(word).name if index == 0 else word)
        if len(prefix) == len(GATED_COMMAND):
            break
    return prefix == list(GATED_COMMAND)


def in_scope(command: str) -> bool:
    """Whether this guard should judge `command`, in any command position."""
    try:
        commands = expand_commands(command)
    except ValueError:
        # Unbalanced quotes: fail open rather than guess at the intent.
        return False
    return any(matches_gate(strip_prefix(words)) for words in commands)


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
