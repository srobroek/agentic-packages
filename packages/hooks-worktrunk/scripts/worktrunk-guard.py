#!/usr/bin/env python3
"""Deny direct worktree management and steer callers to Worktrunk."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CONTROL = {";", "&&", "||", "|", "&", "\n", "(", ")", "{", "}"}
PREFIX_KEYWORDS = {"if", "then", "elif", "while", "until", "do", "!", "{"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


@dataclass(frozen=True)
class Token:
    value: str
    quoted: bool = False


@dataclass(frozen=True)
class Violation:
    command: str
    guidance: str

    @property
    def reason(self) -> str:
        return (
            f"Blocked by WT-1: `{self.command}` bypasses Worktrunk lifecycle "
            f"management. {self.guidance}"
        )


class ShellLexer:
    """Small, non-executing lexer for command-position policy checks."""

    def __init__(self, source: str):
        self.source = source
        self.length = len(source)
        self.index = 0
        self.nested: list[str] = []

    def lex(self) -> tuple[list[Token], list[str]]:
        tokens: list[Token] = []
        word: list[str] = []
        quoted = False

        def flush() -> None:
            nonlocal quoted
            if word:
                tokens.append(Token("".join(word), quoted))
                word.clear()
                quoted = False

        while self.index < self.length:
            char = self.source[self.index]
            if char in " \t\r":
                flush()
                self.index += 1
                continue
            if char == "\n":
                flush()
                tokens.append(Token("\n"))
                self.index += 1
                continue
            if char == "#" and not word:
                while self.index < self.length and self.source[self.index] != "\n":
                    self.index += 1
                continue
            if char == "'":
                quoted = True
                word.append(self._single_quote())
                continue
            if char == '"':
                quoted = True
                word.append(self._double_quote())
                continue
            if char == "\\":
                self.index += 1
                if self.index < self.length:
                    word.append(self.source[self.index])
                    self.index += 1
                continue
            if self.source.startswith("$(", self.index):
                nested = self._command_substitution()
                self.nested.append(nested)
                word.append("$(...)")
                continue
            if char == "`":
                nested = self._backticks()
                self.nested.append(nested)
                word.append("`...`")
                continue
            if char in ";&|(){}":
                flush()
                if self.source.startswith(("&&", "||"), self.index):
                    tokens.append(Token(self.source[self.index : self.index + 2]))
                    self.index += 2
                else:
                    tokens.append(Token(char))
                    self.index += 1
                continue
            word.append(char)
            self.index += 1

        flush()
        return tokens, self.nested

    def _single_quote(self) -> str:
        self.index += 1
        start = self.index
        while self.index < self.length and self.source[self.index] != "'":
            self.index += 1
        value = self.source[start : self.index]
        if self.index < self.length:
            self.index += 1
        return value

    def _double_quote(self) -> str:
        self.index += 1
        value: list[str] = []
        while self.index < self.length:
            char = self.source[self.index]
            if char == '"':
                self.index += 1
                break
            if char == "\\":
                self.index += 1
                if self.index < self.length:
                    value.append(self.source[self.index])
                    self.index += 1
                continue
            if self.source.startswith("$(", self.index):
                nested = self._command_substitution()
                self.nested.append(nested)
                value.append("$(...)")
                continue
            if char == "`":
                nested = self._backticks()
                self.nested.append(nested)
                value.append("`...`")
                continue
            value.append(char)
            self.index += 1
        return "".join(value)

    def _command_substitution(self) -> str:
        self.index += 2
        start = self.index
        depth = 1
        quote = ""
        escaped = False
        while self.index < self.length:
            char = self.source[self.index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif quote:
                if char == quote:
                    quote = ""
            elif char in {"'", '"'}:
                quote = char
            elif self.source.startswith("$(", self.index):
                depth += 1
                self.index += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    value = self.source[start : self.index]
                    self.index += 1
                    return value
            self.index += 1
        return self.source[start:]

    def _backticks(self) -> str:
        self.index += 1
        start = self.index
        escaped = False
        while self.index < self.length:
            char = self.source[self.index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "`":
                value = self.source[start : self.index]
                self.index += 1
                return value
            self.index += 1
        return self.source[start:]


def basename(value: str) -> str:
    return os.path.basename(value).lower()


def segments(tokens: Iterable[Token]) -> Iterable[list[Token]]:
    current: list[Token] = []
    for token in tokens:
        if token.value in CONTROL:
            if current:
                yield current
                current = []
            continue
        current.append(token)
    if current:
        yield current


def skip_options(
    words: list[Token],
    index: int,
    value_options: set[str],
    *,
    assignments: bool = False,
) -> int:
    while index < len(words):
        value = words[index].value
        lowered = value.lower()
        if assignments and ASSIGNMENT.match(value):
            index += 1
            continue
        if value == "--":
            return index + 1
        if not value.startswith("-"):
            return index
        index += 1
        if lowered in value_options and index < len(words):
            index += 1
    return index


def unwrap_command(words: list[Token], index: int) -> int:
    while index < len(words):
        while index < len(words) and (
            words[index].value.lower() in PREFIX_KEYWORDS or ASSIGNMENT.match(words[index].value)
        ):
            index += 1
        if index >= len(words):
            return index

        head = basename(words[index].value)
        if head == "env":
            # `env -S`/`--split-string` turns one argument into a shell
            # command. Leave the wrapper in place so analyze_segment can
            # re-lex that command instead of treating its first word as the
            # utility name.
            if wrapper_shell_command(words, index) is not None:
                return index
            index = skip_options(
                words, index + 1, {"-u", "--unset", "-c", "--chdir"}, assignments=True
            )
        elif head in {"command", "exec", "nohup"}:
            index = skip_options(words, index + 1, set())
        elif head == "time":
            index = skip_options(words, index + 1, {"-f", "--format", "-o", "--output"})
        elif head in {"sudo", "doas"}:
            index = skip_options(
                words,
                index + 1,
                {
                    "-a",
                    "-c",
                    "-g",
                    "-h",
                    "-p",
                    "-r",
                    "-t",
                    "-u",
                    "--chdir",
                    "--group",
                    "--host",
                    "--prompt",
                    "--role",
                    "--type",
                    "--user",
                },
            )
        elif head == "nice":
            index = skip_options(words, index + 1, {"-n", "--adjustment"})
        elif head == "timeout":
            # First positional is the duration, not the wrapped command.
            index = skip_options(words, index + 1, {"-k", "--kill-after", "-s", "--signal"}) + 1
        elif head == "setsid":
            index = skip_options(words, index + 1, set())
        elif head == "flock":
            # util-linux flock -c/--command receives a shell command string,
            # not a utility plus argv. Leave it for recursive scanning.
            if wrapper_shell_command(words, index) is not None:
                return index
            # First positional is the lock file or directory.
            index = (
                skip_options(
                    words,
                    index + 1,
                    {"-w", "--wait", "--timeout", "-E", "--conflict-exit-code"},
                )
                + 1
            )
        elif head == "ionice":
            index = skip_options(words, index + 1, {"-c", "-n", "-p", "-p", "-u"})
        elif head == "stdbuf":
            index = skip_options(words, index + 1, {"-i", "-o", "-e"})
        elif head == "xargs":
            index = skip_options(
                words,
                index + 1,
                {
                    "-a",
                    "-e",
                    "-i",
                    "-l",
                    "-n",
                    "-p",
                    "-s",
                    "-e",
                    "-p",
                    "--replace",
                },
            )
        else:
            return index
    return index


def git_subcommand(words: list[Token], index: int) -> tuple[str, list[str]] | None:
    head = basename(words[index].value)
    if head == "git-worktree":
        args = [token.value for token in words[index + 1 :]]
        return (args[0].lower() if args else "", args[1:])
    if head != "git":
        return None

    index += 1
    value_options = {
        "-c",
        "-C",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--super-prefix",
        "--exec-path",
        "--config-env",
    }
    while index < len(words):
        value = words[index].value
        lowered = value.lower()
        if value == "--":
            index += 1
            break
        if not value.startswith("-"):
            break
        index += 1
        if lowered in {item.lower() for item in value_options} and "=" not in value:
            if index < len(words):
                index += 1
    if index >= len(words) or words[index].value.lower() != "worktree":
        return None
    args = [token.value for token in words[index + 1 :]]
    return (args[0].lower() if args else "", args[1:])


def positional(args: list[str]) -> list[str]:
    result: list[str] = []
    skip_next = False
    value_options = {"-b", "-B", "--reason", "--expire"}
    for value in args:
        if skip_next:
            skip_next = False
            continue
        if value in value_options:
            skip_next = True
            continue
        if value.startswith("-"):
            continue
        result.append(value)
    return result


def worktree_guidance(subcommand: str, args: list[str]) -> str:
    command = f"git worktree {subcommand}".strip()
    if subcommand == "list":
        return "Use `wt list`."
    if subcommand == "remove":
        target = positional(args)
        suffix = f" {target[0]}" if target else " <branch-or-path>"
        return f"Use `wt remove{suffix}`."
    if subcommand == "move":
        targets = positional(args)
        suffix = f" {targets[0]}" if targets else " [branch]"
        return f"Use `wt step relocate{suffix}`; Worktrunk computes the configured destination."
    if subcommand == "prune":
        return "Preview with `wt step prune --dry-run`, then use `wt step prune`."
    if subcommand == "add":
        branch = None
        base = None
        detached = "--detach" in args or "-d" in args
        for offset, value in enumerate(args):
            if value in {"-b", "-B"} and offset + 1 < len(args):
                branch = args[offset + 1]
        values = positional(args)
        if len(values) > 1:
            base = values[-1]
        if detached:
            return (
                "Worktrunk is branch-oriented; choose a branch and run "
                "`wt switch --create <branch> --base <commit>`."
            )
        if branch:
            base_part = f" --base {base}" if base else ""
            return f"Use `wt switch --create {branch}{base_part}`."
        if base:
            return f"Use `wt switch {base}` for an existing branch."
        return (
            "Use `wt switch --create <branch> --base <base>` for a new branch, "
            "or `wt switch <branch>` for an existing branch."
        )
    if subcommand in {"lock", "unlock", "repair"}:
        return (
            f"`git worktree {subcommand}` has no general Worktrunk equivalent. "
            "Use Worktrunk lifecycle commands; ask the user before a low-level repair."
        )
    if not subcommand:
        return "Use `wt list`, `wt switch`, `wt remove`, or `wt step`."
    return (
        f"`{command}` is not a supported direct operation. Use the corresponding "
        "`wt` lifecycle command."
    )


def gh_pr_checkout_target(words: list[Token], index: int) -> str | None:
    index = skip_options(words, index + 1, {"-R", "--repo", "--hostname"})
    if index + 1 >= len(words):
        return None
    if [words[index].value.lower(), words[index + 1].value.lower()] != [
        "pr",
        "checkout",
    ]:
        return None

    index += 2
    while index < len(words):
        value = words[index].value
        lowered = value.lower()
        if lowered in {"-b", "--branch"}:
            index += 2
            continue
        if value == "--":
            index += 1
            break
        if value.startswith("-"):
            index += 1
            continue
        return value
    return words[index].value if index < len(words) else "<number>"


def claude_worktree_requested(words: list[Token], index: int) -> bool:
    if basename(words[index].value) not in {"claude", "claude-code"}:
        return False
    return any(
        token.value == "-w" or token.value == "--worktree" or token.value.startswith("--worktree=")
        for token in words[index + 1 :]
    )


def wrapper_shell_command(words: list[Token], index: int) -> str | None:
    """Return a shell string carried by env/flock, if present."""
    head = basename(words[index].value)
    if head == "env":
        special = {"-S", "--split-string"}
        value_options = {"-u", "--unset", "-c", "-C", "--chdir", "-P"}
        attached_short = "-S"
    elif head == "flock":
        special = {"-c", "--command"}
        value_options = {
            "-w",
            "--wait",
            "--timeout",
            "-E",
            "--conflict-exit-code",
        }
        attached_short = ""
    else:
        return None

    offset = index + 1
    while offset < len(words):
        value = words[offset].value
        if head == "env" and ASSIGNMENT.match(value):
            offset += 1
            continue
        if value == "--":
            return None
        if value in special:
            if head == "env":
                return " ".join(token.value for token in words[offset + 1 :])
            return words[offset + 1].value if offset + 1 < len(words) else None
        for option in special:
            prefix = f"{option}="
            if value.startswith(prefix):
                if head == "env":
                    return " ".join(
                        [value[len(prefix) :]]
                        + [token.value for token in words[offset + 1 :]]
                    )
                return value[len(prefix) :]
        if attached_short and value.startswith(attached_short) and value != attached_short:
            if head == "env":
                return " ".join(
                    [value[len(attached_short) :]]
                    + [token.value for token in words[offset + 1 :]]
                )
            return value[len(attached_short) :]
        if not value.startswith("-"):
            return None
        offset += 1
        if value in value_options:
            offset += 1
    return None


def analyze_segment(words: list[Token]) -> Violation | None:
    index = unwrap_command(words, 0)
    if index >= len(words):
        return None
    head = basename(words[index].value)

    if head in {"env", "flock"}:
        command = wrapper_shell_command(words, index)
        if command is not None:
            return scan_command(command)

    if head in {"sh", "bash", "zsh", "fish"}:
        for offset in range(index + 1, len(words) - 1):
            flag = words[offset].value
            if flag == "--command" or (
                flag.startswith("-") and not flag.startswith("--") and "c" in flag[1:]
            ):
                return scan_command(words[offset + 1].value)
        return None
    if head == "eval" and index + 1 < len(words):
        return scan_command(" ".join(token.value for token in words[index + 1 :]))

    parsed = git_subcommand(words, index)
    if parsed is not None:
        subcommand, args = parsed
        shown = f"git worktree {subcommand}".strip()
        return Violation(shown, worktree_guidance(subcommand, args))

    if head == "gh":
        target = gh_pr_checkout_target(words, index)
        if target is not None:
            destination = target if target.startswith(("http://", "https://")) else f"pr:{target}"
            return Violation("gh pr checkout", f"Use `wt switch {destination}`.")

    if claude_worktree_requested(words, index):
        return Violation(
            "claude --worktree",
            "Use `wt switch --create <branch> --execute=claude -- <prompt>`, "
            "or `/wt-switch-create` inside Claude Code.",
        )
    return None


def scan_command(command: str) -> Violation | None:
    # No substring prefilter: every candidate token (worktree, pr, checkout) is
    # splittable by the quoting this lexer exists to normalise, so a prefilter is
    # itself the bypass (`git work"tree" add`, `gh pr  checkout`).
    lexer = ShellLexer(command)
    tokens, nested = lexer.lex()
    for group in segments(tokens):
        violation = analyze_segment(group)
        if violation:
            return violation
    for source in nested:
        violation = scan_command(source)
        if violation:
            return violation
    return None


def command_from_payload(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        return command if isinstance(command, str) else ""
    return ""


def worktrunk_enforceable(payload: object) -> bool:
    """Whether this environment can act on the guidance the guard would give.

    Denying `git worktree` where `wt` is absent, or outside a work tree, is a hard
    stall: the caller has no route to the suggested command. Mirrors the gates in
    worktrunk-writer.py's `hook`. Behaviour is unchanged wherever both are present.
    """
    if shutil.which("wt") is None:
        return False
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    # Type-checked rather than trusted: a non-string `cwd` reached Path() and
    # raised TypeError, which exited 1 because this script had no fail-open guard.
    repo = Path(cwd if isinstance(cwd, str) and cwd else os.getcwd())
    if not repo.exists():
        return False
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        # A git that hangs or cannot start must not hold up the tool call. This was
        # the only subprocess among the Bash guards with no timeout at all.
        return False
    return not completed.returncode


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    # No raw-substring prefilter here, deliberately: `scan_command` documents why
    # one would be a bypass, since quoting splits every candidate token
    # (`git work"tree" add`). The cost is instead cut by deciding whether the
    # guard can act at all -- which is a `which` and a `git rev-parse` -- only
    # after the cheap token scan finds something to complain about.
    violation = scan_command(command_from_payload(payload))
    if violation is None:
        return 0
    if not worktrunk_enforceable(payload):
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": violation.reason,
                }
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open, per the hook contract: an unreadable payload or an unexpected
        # exception allows rather than blocking. Without this, a payload carrying a
        # non-string `cwd` raised TypeError and exited 1 on the hot path.
        raise SystemExit(0)
