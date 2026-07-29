#!/usr/bin/env python3
"""Refresh and stage .beads/issues.jsonl when the agent commits (PreToolUse:Bash).

Keeps bead state travelling with the branch in repositories that cannot use Dolt
sync. The commit half of a pair; beads-sync-session.py handles session start.

WHY THIS EXISTS AT ALL -- bd already has most of it natively:
`bd config set export.auto true` exports after every write command, throttled by
export.interval. Prefer that; this hook does not duplicate it. Two gaps keep it
necessary:
  1. `export.git-add: true` does not stage the file (verified: the export lands and
     shows as modified in git status, but never enters the index), so the commit
     would not carry it.
  2. Auto-export is throttled, so the file can lag the database at commit time.
This hook closes both: refresh, then stage. It never commits -- the agent's own
commit carries the file.

NATIVE SYNC WINS. Where a Dolt remote is configured and reachable, `bd dolt push`
is the sync path and JSONL is redundant: it carries issue rows only, not Dolt
branches or history. So this stays off unless the repository opts in with
custom.jsonl-git-sync, which is how a repository declares Dolt sync unavailable.

Ported from shell, where a `git commit` was detected by stripping quoted text with
a 24-line awk state machine and then matching a 130-character `grep -E` against the
result. That is a shell tokenizer, the exact construct that collected five separate
bypasses in this repository's rm -rf guard. `shlex` is the shell's own lexer, so
`git commit` inside a message stays an argument instead of becoming a verb.

Fail open (exit 0) on everything unverifiable: no bd, no workspace, opt-in unset.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This is a PreToolUse:Bash hook, so it runs on every
# shell command the agent issues; every other import happens after the bail below.

# Punctuation that can precede a verb. A substitution, subshell, or assignment
# leaves it attached to the token, so reducing to the text after the last such
# character recovers the verb -- `$(git`, `` `git ``, `(git`, and `x=$(git` all
# become `git`.
VERB_SEPARATORS = ("=", "$(", "`", "(", "{", ";", "&", "|")

# Tokens that end one command and start another, so the next token is a verb.
# Grouping punctuation counts: `(git commit)` puts git in verb position, and with
# punctuation_chars the lexer emits the bracket as its own token.
COMMAND_SEPARATORS = frozenset(
    {";", "&&", "||", "|", "&", "|&", "(", ")", "{", "}", "((", "))"}
)

# Commands that run another command, so the verb they precede is still a verb. Kept
# deliberately small: a name not listed here consumes the verb position, which fails
# toward not staging rather than toward staging on a mention.
WRAPPERS = frozenset(
    {"time", "env", "nohup", "nice", "ionice", "stdbuf", "sudo", "doas", "xargs", "command"}
)

# Git's own options that take a separate value. Skipping the value as well as the
# flag is what keeps `git -C path commit` matching while `git log --format=%s
# commit` does not -- the shell version needed a bespoke regex group for this and
# still missed the forms dgit and CI actually use.
GIT_VALUE_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})


def extract(payload: str) -> tuple[str, str]:
    """Return the command and the directory it runs in."""
    import json

    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        command = tool_input
    elif isinstance(tool_input, dict):
        raw = tool_input.get("command")
        command = raw if isinstance(raw, str) else ""
    else:
        command = ""
    cwd = data.get("cwd")
    return command, cwd if isinstance(cwd, str) else ""


def commits(command: str) -> bool:
    """Whether the command runs `git commit` as a command, not as text.

    Lexing rather than pattern-matching is what keeps a quoted mention -- `git
    commit -m "do not git commit yet"` -- from matching twice. A wrapper prefix, an
    env assignment, a substitution, and a separator all still match, because the
    tokens they yield put `git` where a verb goes.

    `git` is only accepted in COMMAND POSITION: first token, or first after a
    separator, an assignment, or a wrapper. The shell version matched anywhere its
    regex could anchor, so `echo git commit` staged and committed bead state on a
    command that only PRINTED those words -- verified against the shell oracle.
    """
    # A newline separates commands to the shell but is only whitespace to `shlex`,
    # so lines are split before lexing. Without this, `dgit commit\ngit commit`
    # lexes as one flat token run and the real `git` never lands in verb position.
    return any(_line_commits(line) for line in command.splitlines() if line.strip())


def _line_commits(line: str) -> bool:
    """Whether one line runs `git commit` in command position."""
    import shlex

    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes: the shell would reject this too, so judge nothing.
        return False

    expecting_verb = True
    for index, token in enumerate(tokens):
        if token in COMMAND_SEPARATORS:
            expecting_verb = True
            continue
        if not expecting_verb:
            continue

        verb = token
        for separator in VERB_SEPARATORS:
            if separator in verb:
                verb = verb.rsplit(separator, 1)[-1]

        # An assignment prefix (FOO=bar git commit) or a wrapper (time git commit)
        # keeps the NEXT token in verb position; anything else consumes it.
        if verb != "git" and not verb.endswith("/git"):
            if "=" in token or token in WRAPPERS:
                continue
            expecting_verb = False
            continue

        # Walk past git's global options to the subcommand.
        position = index + 1
        while position < len(tokens):
            word = tokens[position]
            if word in GIT_VALUE_OPTIONS:
                position += 2
                continue
            if word.startswith("-"):
                position += 1
                continue
            break
        if position < len(tokens) and tokens[position] == "commit":
            return True
        expecting_verb = False
    return False


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0

    # Cheap pre-parse bail: only `git commit` is of interest, and the overwhelming
    # majority of Bash calls mention neither word.
    if "commit" not in payload or "git" not in payload:
        return 0

    command, cwd = extract(payload)
    if not command or not commits(command):
        return 0

    import os

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import beads_sync

    if not beads_sync.bd_available():
        return 0

    directory = cwd if cwd and os.path.isdir(cwd) else os.getcwd()
    beads = beads_sync.beads_dir(directory)
    if not beads:
        return 0

    # Opt-in per repository: this is how a repository declares that Dolt sync is
    # unavailable to it. Absent, the hook does nothing, so installing the package
    # cannot start committing bead state in a repository that syncs natively.
    if not beads_sync.opt(directory, "custom.jsonl-git-sync"):
        return 0

    target = os.path.join(beads, "issues.jsonl")

    # Export to a temp file first: a failed export must not truncate a good
    # committed file.
    temporary = f"{target}.hook-tmp.{os.getpid()}"
    if not beads_sync.export_all(directory, temporary):
        _unlink(temporary)
        return 0

    # Skip the write when nothing changed, so an unrelated commit does not carry a
    # spurious one-line diff. bd's export is deterministic, so equal bytes mean
    # equal state.
    import filecmp

    try:
        unchanged = os.path.exists(target) and filecmp.cmp(temporary, target, shallow=False)
    except OSError:
        unchanged = False
    if unchanged:
        _unlink(temporary)
        return 0

    try:
        os.replace(temporary, target)
    except OSError:
        _unlink(temporary)
        return 0

    # Stage it so the agent's own `git commit` picks it up. Never commit here: that
    # would create a commit the agent did not ask for.
    staged = beads_sync.run(["git", "-C", directory, "add", "--", target], timeout=30)
    if staged is not None and staged.returncode == 0:
        return 0

    # `git add` on an ignored path exits non-zero WITHOUT staging, and a stealth
    # `bd init` writes `.beads/` into .git/info/exclude -- so the whole sync can
    # look healthy while nothing is ever committed. Say so rather than failing
    # silently: it is unfixable from inside the hook and invisible from outside.
    ignored = beads_sync.run(
        ["git", "-C", directory, "check-ignore", "-q", "--", target], timeout=15
    )
    if ignored is not None and ignored.returncode == 0:
        beads_sync.emit(
            "PreToolUse",
            f"custom.jsonl-git-sync is on, but {target} is git-ignored, so bead "
            "state will never be committed. A stealth 'bd init' excludes .beads/ "
            "via .git/info/exclude. Un-ignore the file (or drop that pattern) "
            "before relying on JSONL sync.",
        )
    return 0


def _unlink(path: str) -> None:
    import os

    try:
        os.unlink(path)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())
