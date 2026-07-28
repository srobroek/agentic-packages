#!/usr/bin/env python3
"""PreToolUse:Bash safety guard for destructive git operations.

Almost everything git does is recoverable from the reflog, so this guard denies
exactly one thing and otherwise only speaks when work would actually be lost.

  DENY   a destructive op aimed at another working tree through an unexpanded
         variable or `~` (GS-2). The guard cannot resolve which tree would be
         hit, so it cannot say what is at risk.
  WARN   `reset --hard`, `checkout --`, `restore`, and `clean -f` when the
         repository state says something really would go (GS-3, GS-5, GS-6), and
         `push --force` always, because the loss is on the remote where local
         state cannot answer for it (GS-4).
  ALLOW  everything else silently, including `branch -D`, `tag -d`,
         `stash drop`, and `worktree remove --force`, all reflog-recoverable.

The state checks are the expensive part, so they run only after a destructive
verb has already matched, and they run as one batched git call rather than one
per question. A warning that fires on a clean tree is noise the agent learns to
skip, which is why each one is gated on evidence.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# shlex and subprocess are imported inside the functions that use them. Together
# they add about 20ms to interpreter startup, and this hook runs on every Bash
# call, the overwhelming majority of which bail before either is needed.

# Wrappers that keep the following word in command position.
WRAPPERS = frozenset(
    {"sudo", "doas", "env", "time", "nice", "command", "exec", "xargs", "stdbuf",
     "nohup", "setsid", "ionice", "timeout", "unbuffer", "flock"}
)

# Wrappers whose first non-option word is their OWN operand rather than the wrapped
# command: `timeout 5 git ...` and `flock /tmp/lock git ...`. Adding these to
# WRAPPERS alone would leave `5` standing where the verb belongs.
WRAPPER_OPERAND = frozenset({"timeout", "flock"})
COMMAND_BOUNDARIES = frozenset(
    {"do", "then", "else", "elif", "{", "(", "!", "while", "until", "if", "for"}
)
CLOSERS = frozenset({"}", ")", "done", "fi", "esac"})
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Global git options that take a separate value, so the value is not mistaken for
# the subcommand.
GIT_OPTIONS_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})

# A redirect flag whose value carries a `$` or `~` points at a working tree the
# guard cannot resolve.
UNVERIFIABLE_REDIRECT = re.compile(
    r"""(?:^|\s)(?:-C\s+|--git-dir[\s=]|--work-tree[\s=])["']?[^"';&|]*[$~]"""
)


def emit(decision: str, message: str) -> None:
    key = "permissionDecisionReason" if decision == "deny" else "additionalContext"
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny" if decision == "deny" else "allow",
                key: message,
            }
        },
        sys.stdout,
    )


def split_commands(command: str) -> list[list[str]]:
    """Tokenize into commands. A newline separates exactly like a semicolon."""
    import shlex

    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)

    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and set(token) <= {";", "&", "|"}:
            if current:
                commands.append(current)
            current = []
        elif token in COMMAND_BOUNDARIES or token in CLOSERS:
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def git_invocation(words: list[str]) -> list[str] | None:
    """Return the git subcommand and its arguments, or None if not a git call.

    Skips wrappers, env assignments, and git's own global options so the
    subcommand is found rather than assumed to be the second word. Without this,
    `git -C /path reset --hard` looks like the subcommand is `-C`.
    """
    index = 0
    while index < len(words):
        word = words[index]
        if word in COMMAND_BOUNDARIES or ASSIGNMENT.match(word):
            index += 1
            continue
        if word in WRAPPERS:
            takes_operand = word in WRAPPER_OPERAND
            index += 1
            # Consume the wrapper's own options, plus one value for an option that
            # takes one. Skipping only the wrapper WORD left `-n` standing where the
            # verb belonged, so `nice -n 5 git ... reset --hard` was silent while the
            # bare command denied -- six wrapper forms defeated the deny this way.
            while index < len(words) and words[index].startswith("-"):
                index += 1
                if index < len(words) and not words[index].startswith("-"):
                    following = words[index + 1] if index + 1 < len(words) else None
                    if following is not None and not following.startswith("-"):
                        index += 1
            # `timeout 5 git ...`: the duration belongs to the wrapper.
            if takes_operand and index < len(words) and not words[index].startswith("-"):
                index += 1
            continue
        break
    if index >= len(words) or Path(words[index]).name != "git":
        return None

    index += 1
    while index < len(words):
        word = words[index]
        if word in GIT_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        break
    return words[index:] if index < len(words) else None


class RepoState:
    """Repository facts, fetched once and only when a warning depends on them."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd
        self._dirty: bool | None = None
        self._untracked: bool | None = None
        self._in_tree: bool | None = None

    def _run(self, args: list[str]) -> str | None:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "-C", str(self._cwd), *args],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout if result.returncode == 0 else None

    def has_uncommitted_tracked_changes(self) -> bool:
        """True when tracked files carry staged or unstaged changes.

        `-uno` excludes untracked files, so a directory holding only untracked
        files reports clean: nothing a reset or checkout would discard.

        Unreadable state answers True. Not being able to confirm a clean tree is
        exactly when the agent should look, and the cost of being wrong here is
        one advisory rather than a block.
        """
        if self._dirty is None:
            if not self._inside_work_tree():
                self._dirty = True
            else:
                output = self._run(["status", "--porcelain", "-uno"])
                self._dirty = True if output is None else bool(output.strip())
        return self._dirty

    def has_untracked_files(self) -> bool:
        """True when `clean -f` would delete something, or when that is unknown."""
        if self._untracked is None:
            if not self._inside_work_tree():
                self._untracked = True
            else:
                output = self._run(["clean", "-nd"])
                self._untracked = True if output is None else bool(output.strip())
        return self._untracked

    def _inside_work_tree(self) -> bool:
        if self._in_tree is None:
            output = self._run(["rev-parse", "--is-inside-work-tree"])
            self._in_tree = bool(output and output.strip() == "true")
        return self._in_tree


def has_flag(args: list[str], *names: str) -> bool:
    return any(arg in names or arg.split("=", 1)[0] in names for arg in args)


def restore_is_staged_only(args: list[str]) -> bool:
    """`git restore --staged` only unstages, leaving the working tree alone.

    That is the reverse of `git add` and fully reversible. The working tree is
    touched when `--worktree` is present, or when `--staged` is absent, since the
    working tree is restore's default.
    """
    return has_flag(args, "--staged") and not has_flag(args, "--worktree")


def judge(args: list[str], state: RepoState) -> tuple[str, str] | None:
    """Judge one git subcommand."""
    subcommand, rest = args[0], args[1:]

    if subcommand == "reset" and has_flag(rest, "--hard"):
        if state.has_uncommitted_tracked_changes():
            return (
                "warn",
                "GS-3 (warn: reset --hard discards uncommitted tracked changes): the "
                "working tree has staged or unstaged changes to tracked files that "
                "will be permanently discarded and are NOT in the reflog. Commit or "
                "stash them first if you need them. Proceeding.",
            )
        return None

    if subcommand == "push" and has_flag(rest, "--force", "-f", "--force-with-lease"):
        # Always warn: the loss would be on the remote, and local state says
        # nothing about what another author pushed there.
        return (
            "warn",
            "GS-4 (warn: force push rewrites remote history): this rewrites the "
            "remote branch and can overwrite commits pushed by someone else. Verify "
            "the remote ref is what you expect before proceeding. Proceeding.",
        )

    if subcommand == "checkout" and "--" in rest:
        if state.has_uncommitted_tracked_changes():
            return (
                "warn",
                "GS-5 (warn: checkout -- discards uncommitted changes): this discards "
                "uncommitted working-tree changes to the named paths, which are not "
                "recoverable from the reflog. Proceeding.",
            )
        return None

    if subcommand == "restore":
        if not restore_is_staged_only(rest) and state.has_uncommitted_tracked_changes():
            return (
                "warn",
                "GS-5 (warn: restore discards uncommitted changes): git restore "
                "discards uncommitted changes to the named paths, which are not "
                "recoverable from the reflog. Proceeding.",
            )
        return None

    if subcommand == "clean" and (
        has_flag(rest, "--force")
        or any(a.startswith("-") and not a.startswith("--") and "f" in a for a in rest)
    ):
        if state.has_untracked_files():
            return (
                "warn",
                "GS-6 (warn: clean -f deletes untracked files): this permanently "
                "deletes untracked files, which were never in git and cannot be "
                "recovered. Run `git clean -nd` first to see the list. Proceeding.",
            )
        return None

    return None


DESTRUCTIVE_SUBCOMMANDS = frozenset({"reset", "push", "checkout", "restore", "clean"})


def extract(payload: str) -> tuple[str, str]:
    data = json.loads(payload)
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


def main() -> int:
    payload = sys.stdin.read()
    # Cheap bail on the raw bytes before any parse: every rule needs a git call.
    # A strict superset of the real trigger, so it cannot hide a match.
    if "git" not in payload:
        return 0

    try:
        command, raw_cwd = extract(payload)
    except (ValueError, TypeError):
        return 0
    if not command:
        return 0

    try:
        commands = split_commands(command)
    except ValueError:
        # Not parseable as shell, so there is nothing reliable to judge.
        return 0

    destructive = [
        (words, inv)
        for words, inv in ((w, git_invocation(w)) for w in commands)
        if inv and inv[0] in DESTRUCTIVE_SUBCOMMANDS
    ]
    if not destructive:
        return 0

    # Scoped to the destructive invocation's own words. Searching the whole
    # command string denied `git clean -fd; git -C ~/other status`, blaming a
    # read-only `status` in a separate command for a tree the destructive op never
    # touches. Re-joined with spaces so the `-C <path>` shape the pattern expects
    # survives tokenization; `$` and `~` are still literal after posix lexing
    # because the shell has not expanded them yet.
    for words, _ in destructive:
        if UNVERIFIABLE_REDIRECT.search(" ".join(words)):
            emit(
                "deny",
                "blocked by GS-2 (no destructive op via an unexpanded variable): this "
                "points git at another working tree through a shell variable or `~`, so "
                "the guard cannot resolve which tree would be affected or what would be "
                "lost. Resolve it to a literal path first, then re-run.",
            )
            return 0

    cwd = Path(raw_cwd) if raw_cwd and Path(raw_cwd).is_dir() else Path.cwd()
    state = RepoState(cwd)

    for _, invocation in destructive:
        finding = judge(invocation, state)
        if finding:
            emit(finding[0], finding[1])
            return 0
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: a guard that crashes closed wedges the agent.
        raise SystemExit(0)
