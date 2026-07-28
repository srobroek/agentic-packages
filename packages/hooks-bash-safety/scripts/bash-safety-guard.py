#!/usr/bin/env python3
"""PreToolUse:Bash safety guard for autonomous agents.

Blocks only what cannot be undone, and says why in terms the model can act on.

  DENY   unrecoverable: `rm -rf` on the filesystem root, a home root, or a
         system-critical tree; `mkfs`; `dd` onto a real block device; the
         sandbox-bypass flag; and an `rm -rf` whose target hides behind an
         unexpanded variable, because the guard cannot see what would go.
  WARN   recoverable but worth naming: `curl | sh`, `sudo` with a destructive
         verb, and `rm -rf` on a path outside the git working tree.
  ALLOW  everything else, silently. A path inside the working tree is assumed
         recoverable because it is in git, so wiping node_modules or a build
         directory says nothing at all.

`ask` is never emitted: it waits for a human, which stalls an autonomous run.

This replaces two shell guards that each hand-rolled the same
command-position anchoring with regexes. Every bypass they accumulated was a gap
in that hand-rolled tokenizer -- a wrapper prefix, an env assignment, a leading
tab, a quoted target, path traversal, flags after the target. A real tokenizer
removes the whole class rather than patching instances, which is the reason this
is one Python module instead of two shell scripts.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# shlex and subprocess are imported inside the functions that use them. Together
# they add about 20ms to interpreter startup, and this hook runs on every Bash
# call, the overwhelming majority of which bail before either is needed.

# Command wrappers that keep the next word in command position. Each may carry
# options, and an option may take a separate value (`nice -n 19`, `sudo -u root`).
WRAPPERS = frozenset(
    {
        "sudo", "doas", "env", "time", "nice", "command", "exec", "xargs",
        "stdbuf", "nohup", "setsid", "ionice",
    }
)

# Shell keywords and openers after which a command starts.
OPENERS = frozenset({"do", "then", "else", "elif", "{", "(", "!", "while", "until", "if"})

# Words that begin a new command rather than continue the current one.
COMMAND_BOUNDARIES = frozenset(
    {"do", "then", "else", "elif", "{", "(", "!", "while", "until", "if", "for"}
)
# Group and block terminators, which end a command without starting one.
CLOSERS = frozenset({"}", ")", "done", "fi", "esac"})

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Whole-tree deletion of any of these is unrecoverable regardless of git.
CRITICAL = (
    "/usr", "/etc", "/bin", "/sbin", "/lib", "/lib64", "/var", "/opt", "/root",
    "/boot", "/dev", "/proc", "/sys", "/System", "/Library", "/Applications",
    "/private", "/Users",
)

# Roots and home spellings whose deletion is catastrophic on sight.
CATASTROPHIC_TARGETS = frozenset(
    {"/", "//", "/*", "~", "~/", "$HOME", "${HOME}", "$home", "${home}"}
)

# Scratch roots: outside the working tree, but always safe to wipe.
TEMP_ROOTS = ("/tmp", "/private/tmp", "/var/folders", "/private/var/folders")

# `dd` onto these is a normal redirect, not a disk overwrite.
PSEUDO_DEVICES = frozenset(
    {"/dev/null", "/dev/zero", "/dev/random", "/dev/urandom", "/dev/stdout", "/dev/stdin"}
)

# Elevated verbs worth a nudge. Read-only subcommands are excluded below.
DESTRUCTIVE_VERBS = frozenset(
    {
        "rm", "rmdir", "dd", "mkfs", "fdisk", "parted", "shutdown", "reboot",
        "halt", "poweroff", "kill", "killall", "pkill", "chown", "chmod",
        "userdel", "groupdel", "dscl", "diskutil", "systemctl", "service",
        "launchctl", "apt", "apt-get", "dnf", "yum", "pacman", "brew",
    }
)
# Subcommands that read or install rather than destroy. Installing under sudo is
# routine, and warning on it would teach the agent to ignore the warning.
READ_ONLY_SUBCOMMANDS = frozenset(
    {
        "status", "show", "list", "list-units", "list-unit-files", "is-active",
        "is-enabled", "is-failed", "cat", "get-default", "install", "update",
        "upgrade", "info", "search", "reinstall", "add-apt-repository",
    }
)


def emit(decision: str, message: str) -> None:
    """Print one hook decision. Claude reads the JSON; Codex reads exit 0."""
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
    """Tokenize into a list of commands, each a list of words.

    shlex handles quoting, escapes, and comments, so a dangerous phrase inside a
    quoted argument stays an argument. Unbalanced quotes mean the string is not
    parseable as shell, and the caller treats that as nothing to judge rather
    than guessing.
    """
    import shlex

    # A newline separates commands exactly like a semicolon, but shlex treats
    # it as ordinary whitespace, which merged a second line into the first and
    # hid its verb from every check.
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)  # raises ValueError on an unterminated quote

    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and set(token) <= {";", "&", "|"}:
            if current:
                commands.append(current)
            current = []
            continue
        # A keyword or group opener also begins a command, and a terminator ends
        # one. Treating either as a plain word left it standing where the verb
        # belonged, so a guarded verb inside a loop or subshell went unseen.
        if token in COMMAND_BOUNDARIES or token in CLOSERS:
            if current:
                commands.append(current)
            current = []
            continue
        current.append(token)
    if current:
        commands.append(current)
    return commands


def strip_prefix(words: list[str]) -> list[str]:
    """Drop openers, env assignments, and wrappers to reach the real verb."""
    index = 0
    while index < len(words):
        word = words[index]
        if word in OPENERS or ASSIGNMENT.match(word):
            index += 1
            continue
        if word in WRAPPERS:
            index += 1
            # Consume the wrapper's own options, plus one value for an option
            # that takes one. A bare word here is the wrapped command.
            while index < len(words) and words[index].startswith("-"):
                index += 1
                if index < len(words) and not words[index].startswith("-"):
                    following = words[index + 1] if index + 1 < len(words) else None
                    if following is not None and not following.startswith("-"):
                        index += 1
            continue
        break
    return words[index:]


def has_recursive_force(flags: list[str]) -> bool:
    """True when the flags request both recursion and force, in any spelling."""
    recursive = force = False
    for flag in flags:
        if flag == "--recursive":
            recursive = True
        elif flag == "--force":
            force = True
        elif flag.startswith("--"):
            continue
        elif flag.startswith("-"):
            recursive = recursive or "r" in flag or "R" in flag
            force = force or "f" in flag
    return recursive and force


def find_repo_root(start: Path) -> Path | None:
    """Walk parents for a `.git` entry.

    An entry rather than a directory: `.git` is a file in a linked worktree.
    This avoids spawning `git rev-parse`, which costs two orders of magnitude
    more for the same answer.
    """
    try:
        resolved = start.resolve()
    except OSError:
        return None
    for directory in (resolved, *resolved.parents):
        if (directory / ".git").exists():
            return directory
    return None


def normalize(target: str, cwd: Path) -> str:
    """Resolve a target to an absolute, lexically-normalized path.

    Purely textual: the target may be about to be deleted, and following a
    symlink could resolve somewhere it does not point. `..` and `.` collapse
    here, so `/usr/../etc` cannot dodge a literal comparison.
    """
    path = target if target.startswith("/") else f"{cwd}/{target}"
    parts: list[str] = []
    for component in path.split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            if parts:
                parts.pop()
            continue
        parts.append(component)
    return "/" + "/".join(parts) if parts else "/"


def classify_rm_target(target: str, cwd: Path, root: Path | None) -> str:
    """Rank one `rm -rf` target: deny-critical, deny-var, warn, or allow."""
    if not target:
        return "allow"

    if target in CATASTROPHIC_TARGETS:
        return "deny-root"

    # A relative target is as bad as an absolute one when the directory it
    # resolves against is itself critical: `cd / && rm -rf *` deletes exactly
    # what `rm -rf /*` deletes.
    if not target.startswith(("/", "~")) and "$" not in target:
        if str(cwd) == "/":
            return "deny-root"
        if str(cwd) in CRITICAL:
            return "deny-critical"

    for critical in CRITICAL:
        if target in (critical, f"{critical}/", f"{critical}/*"):
            return "deny-critical"

    # Traversal and redundant syntax that normalizes onto a critical path.
    if "$" not in target and (
        ".." in target or target.endswith("/.") or "/./" in target or "//" in target
    ):
        absolute = normalize(target, cwd)
        if absolute == "/" or absolute in CRITICAL:
            return "deny-critical"

    # An unexpanded variable hides the target. An empty variable even collapses
    # `$DIR/x` toward `/`, so the guard cannot verify what would be removed.
    if "$" in target:
        return "deny-var"

    if target.startswith("~/"):
        return "warn"

    absolute = normalize(target, cwd)

    if root is not None:
        # The repo root or its .git destroys the very git state that makes
        # everything else in the tree recoverable.
        if absolute == str(root) or absolute == f"{root}/.git" or absolute.startswith(f"{root}/.git/"):
            return "warn"
        if absolute.startswith(f"{str(root).rstrip('/')}/"):
            return "allow"

    for temp in TEMP_ROOTS:
        if absolute == temp or absolute.startswith(f"{temp}/"):
            return "allow"

    return "warn"


def check_rm(words: list[str], cwd: Path, root: Path | None) -> tuple[str, str] | None:
    """Judge one `rm` invocation."""
    flags = [word for word in words[1:] if word.startswith("-")]
    if not has_recursive_force(flags):
        return None
    targets = [word for word in words[1:] if not word.startswith("-")]
    if not targets:
        return None

    ranking = {"deny-root": 4, "deny-critical": 3, "deny-var": 2, "warn": 1, "allow": 0}
    worst = "allow"
    for target in targets:
        verdict = classify_rm_target(target, cwd, root)
        if ranking[verdict] > ranking[worst]:
            worst = verdict

    shown = " ".join(targets)
    if worst == "deny-root":
        return (
            "deny",
            f"blocked by BS-4 (no rm -rf on the filesystem or home root): rm -rf "
            f"targets '{shown}', which wipes the root filesystem or the whole home "
            f"directory. This is unrecoverable. Name the specific subdirectory you "
            f"meant instead.",
        )
    if worst == "deny-critical":
        return (
            "deny",
            f"blocked by BS-8 (no rm -rf on a system-critical path): rm -rf targets "
            f"'{shown}', which is a system-critical or home path. This is "
            f"unrecoverable. Name the specific subdirectory you meant instead.",
        )
    if worst == "deny-var":
        return (
            "deny",
            f"blocked by BS-9 (no rm -rf with an unexpanded variable): rm -rf "
            f"'{shown}' hides its target behind a shell variable, so the guard "
            f"cannot verify what would be deleted (an unset variable collapses the "
            f"path toward /). Resolve it to a literal path first, then re-run.",
        )
    if worst == "warn":
        return (
            "warn",
            f"BS-10 (warn on rm -rf outside the working tree): rm -rf '{shown}' is "
            f"not inside the project's git working tree, or is the repo root or its "
            f".git, so it is not git-recoverable. Confirm the target is intended. "
            f"Proceeding.",
        )
    return None


def check_command(words: list[str], cwd: Path, root: Path | None) -> tuple[str, str] | None:
    """Judge one command, already stripped to its verb."""
    if not words:
        return None
    verb = Path(words[0]).name

    if verb == "rm":
        return check_rm(words, cwd, root)

    if verb == "mkfs" or verb.startswith("mkfs."):
        return (
            "deny",
            "blocked by BS-5 (no mkfs): mkfs formats a filesystem and destroys "
            "every file on it.",
        )

    if verb == "dd":
        for word in words[1:]:
            if word.startswith("of=/dev/") and word[3:] not in PSEUDO_DEVICES:
                return (
                    "deny",
                    "blocked by BS-6 (no dd to a block device): this writes over a "
                    "raw disk, which is unrecoverable. Writing to /dev/null, "
                    "/dev/zero, /dev/random, /dev/urandom, /dev/stdout, or "
                    "/dev/stdin is allowed.",
                )
        return None

    if verb in ("curl", "wget"):
        return None  # the pipe form is judged across the whole command below

    return None


def check_sudo(words: list[str]) -> tuple[str, str] | None:
    """Warn when sudo runs a destructive verb, ignoring read-only subcommands."""
    if not words or words[0] not in ("sudo", "doas"):
        return None
    inner = strip_prefix(words)
    if not inner:
        return None
    verb = Path(inner[0]).name
    if verb not in DESTRUCTIVE_VERBS:
        return None
    following = [word for word in inner[1:] if not word.startswith("-")]
    # The subcommand is not always the first argument: `systemctl status nginx`
    # leads with it while `service nginx status` trails it. Checking every bare
    # word covers both without needing a per-tool argument grammar.
    if any(word in READ_ONLY_SUBCOMMANDS for word in following):
        return None
    return (
        "warn",
        "BS-7 (warn on sudo with a destructive command): this runs a destructive "
        "or disruptive command with elevated privileges. Confirm the target is "
        "correct and the change is recoverable before proceeding.",
    )


def check_pipe_to_shell(commands: list[list[str]]) -> tuple[str, str] | None:
    """Warn when a download is piped into a shell."""
    verbs = [Path(strip_prefix(words)[0]).name for words in commands if strip_prefix(words)]
    for index, verb in enumerate(verbs[:-1]):
        if verb in ("curl", "wget") and verbs[index + 1] in ("sh", "bash", "zsh"):
            return (
                "warn",
                "BS-7 (warn on a curl-to-shell pipe): piping a download into a "
                "shell runs remote code without inspecting it. Prefer downloading, "
                "reading, then running. Proceeding.",
            )
    return None


def extract(payload: str) -> tuple[str, str]:
    """Return the command and the directory it runs in."""
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


def resolve_cwd(raw: str, command: str) -> Path:
    """Resolve where the command runs, honouring a leading absolute `cd`.

    A `cd` earlier in the same chain relocates every relative target after it,
    so the payload directory is not where an `rm` lands. Only an absolute literal
    `cd` is followed: guessing at a relative or variable-bearing one would be
    worse than leaving it, and a variable target is denied anyway.
    """
    base = Path(raw) if raw and Path(raw).is_dir() else Path.cwd()
    try:
        base = base.resolve()
    except OSError:
        pass

    match = re.search(r"(?:^|[;&|])\s*cd\s+(/[^\s;&|]*)", command)
    if match and "$" not in match.group(1):
        candidate = match.group(1).rstrip("/") or "/"
        return Path(candidate)
    return base


def main() -> int:
    payload = sys.stdin.read()
    if not payload.strip():
        return 0

    try:
        command, raw_cwd = extract(payload)
    except (ValueError, TypeError):
        return 0
    if not command:
        return 0

    if "--dangerously-bypass-approvals-and-sandbox" in command.lower():
        emit(
            "deny",
            "blocked by BS-3 (no sandbox-bypass flag): "
            "--dangerously-bypass-approvals-and-sandbox disables the safety "
            "envelope for the whole session.",
        )
        return 0

    try:
        commands = split_commands(command)
    except ValueError:
        # Not parseable as shell. Nothing reliable to judge, so allow rather than
        # block on a quoting quirk.
        return 0

    cwd = resolve_cwd(raw_cwd, command)
    root = find_repo_root(cwd)

    pipe = check_pipe_to_shell(commands)
    findings: list[tuple[str, str]] = []

    for words in commands:
        sudo_finding = check_sudo(words)
        if sudo_finding:
            findings.append(sudo_finding)
        finding = check_command(strip_prefix(words), cwd, root)
        if finding:
            findings.append(finding)

    if pipe:
        findings.append(pipe)

    # A denial outranks every advisory: report the blocking reason, not a nudge.
    for decision, message in findings:
        if decision == "deny":
            emit("deny", message)
            return 0
    if findings:
        emit("warn", findings[0][1])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: a guard that crashes closed wedges the agent.
        raise SystemExit(0)
