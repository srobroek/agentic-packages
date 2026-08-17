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
        "stdbuf", "nohup", "setsid", "ionice", "timeout", "unbuffer", "flock",
    }
)

# Wrappers whose first non-option word is their OWN operand rather than the
# wrapped command: `timeout 5 rm -rf /` and `nice -n 19` both put a value there.
# Without this, `5` was read as the verb and the `rm` behind it went unjudged.
WRAPPER_OPERAND = frozenset({"timeout", "flock"})

# Shells whose `-c` argument is itself a command, and builtins that run a string
# as one. The tokenizer sees that argument as a single word, so the verb inside
# it is invisible unless the string is lexed again -- `sh -c 'rm -rf /'` is one
# token to shlex and a filesystem wipe to the shell.
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "ash", "busybox"})
STRING_EVALUATORS = frozenset({"eval", "source", "."})

# Tools that fetch from the network.
DOWNLOADERS = frozenset({"curl", "wget", "fetch", "aria2c", "httpie", "http", "https"})

# Anything that executes what it is handed. A shell is the familiar sink, but a
# language interpreter runs remote code just as completely, and restricting the
# check to shells let `curl ... | python3` through.
INTERPRETERS = SHELLS | frozenset(
    {"python", "python2", "python3", "perl", "ruby", "node", "php", "osascript", "pwsh"}
)

# A download inside a command or process substitution that an interpreter consumes:
# `eval "$(curl -s ...)"`, `bash -c "$(wget -qO- ...)"`, `bash <(curl ...)`.
# Re-lexing cannot see inside a substitution, because its value does not exist until
# the shell runs it, so this is deliberately textual.
SUBSTITUTED_DOWNLOAD = re.compile(
    r"[$<]\(\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:/\S*/)?(?:" + "|".join(sorted(DOWNLOADERS)) + r")\s",
)

# How deep to follow a nested shell string. A real command nests once or twice;
# the bound only stops a pathological payload from recursing without end.
MAX_NESTING = 4

# How many further wrappers to peel once MAX_NESTING is reached. Recursion stops
# there to bound stack depth, but stopping the UNWRAPPING there made the bound an
# escape: enough `sh -c` layers and the payload was never judged at all. This
# ceiling is deliberately high -- no honest command nests 60 deep, and the cost is
# one lex per layer -- so the only payloads it fails to reach are ones already
# absurd enough that the shell itself would struggle.
UNWRAP_CEILING = 64

# Cap on the command text handed to the lexer. See split_commands for the measured
# curve; 64KB lexes in well under 50ms and is far past any hand-written command,
# while the front of the string -- where every verb and flag lives -- is preserved.
MAX_COMMAND_CHARS = 65536

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

    # shlex is quadratic in token length, and this hook runs on every Bash call, so
    # an outsized command is a stall rather than a parse. Measured on one unbroken
    # token: 50KB 31ms, 200KB 477ms, 400KB 1.4s, 800KB 4.7s, 1MB 14.5s end to end.
    # A 14-second PreToolUse hook is indistinguishable from a hang.
    #
    # Truncating is safe in the direction that matters. Every rule matches on the
    # VERB and its flags, which sit at the front; what the cap discards is the tail
    # of an argument, and a decision made on the first 64KB of `rm -rf <huge>` is
    # the same decision. The alternative -- bailing out entirely on a long command
    # -- would hand any payload a way to buy silence just by padding itself.
    if len(command) > MAX_COMMAND_CHARS:
        command = command[:MAX_COMMAND_CHARS]

    # A newline separates commands exactly like a semicolon, but shlex treats
    # it as ordinary whitespace, which merged a second line into the first and
    # hid its verb from every check. A BACKSLASH-newline is the opposite case: it
    # is a line continuation, so the two halves are one command and splitting
    # there orphaned the target of an `rm` from its flags.
    command = re.sub(r"\\\r?\n", " ", command)
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


def nested_command(words: list[str]) -> str | None:
    """Return the command string a shell invocation would run, if any.

    `sh -c '<cmd>'` and `eval '<cmd>'` pass a command as a single argument, so the
    verb inside it never reaches the tokenizer. This returns that argument for the
    caller to lex again. `xargs` deliberately does not appear here: its targets
    arrive on stdin, which no static check can see.
    """
    if not words:
        return None
    verb = Path(words[0]).name

    if verb in SHELLS:
        for index, word in enumerate(words[1:], start=1):
            # `-c` may be bundled with other short flags, as in `sh -ec`.
            if word.startswith("-") and not word.startswith("--") and "c" in word:
                return words[index + 1] if index + 1 < len(words) else None
            if not word.startswith("-"):
                # A bare word is a script path, not an inline command.
                return None
        return None

    if verb in STRING_EVALUATORS:
        # Drop only the evaluator's OWN leading options, then keep the rest
        # verbatim. Filtering every `-` word discarded the WRAPPED command's flags
        # too, so `eval rm -rf /` reconstructed as `rm /` and the recursive-force
        # check never fired -- while `eval 'rm -rf /'`, a single quoted argument,
        # denied. Real `eval` deletes in both spellings.
        rest = words[1:]
        index = 0
        while index < len(rest) and rest[index].startswith("-"):
            index += 1
        # `eval a b` concatenates its arguments into one command line.
        arguments = rest[index:]
        return " ".join(arguments) if arguments else None

    return None


def expand_commands(command: str, depth: int = 0) -> list[list[str]]:
    """Tokenize, then re-lex any nested shell string so its verb is judged too.

    The outer invocation is kept as well as its expansion: `sudo sh -c '...'`
    still deserves the elevated-privilege warning on the outer form.

    AT THE DEPTH BOUND THE PAYLOAD IS STILL SPLIT, not dropped. Returning only the
    outer words there made the bound an escape hatch: five `sh -c` wrappers around
    `rm -rf /` reached depth 5, the recursion stopped, and the only words ever
    judged were `sh -c <string>` -- a verb no rule matches -- so the guard fell
    silent on the one command it exists to deny. Verified by walking depths 0..6:
    0-4 denied, 5 and 6 silent. The bound exists to stop unbounded recursion on a
    pathological payload, so it now keeps splitting the innermost string it has
    reached and judges those words instead of discarding them.
    """
    commands = split_commands(command)
    if depth >= MAX_NESTING:
        # Unwrap iteratively rather than recursively: a bound that merely shifts by
        # one still lets a deeper payload through, so drain every remaining wrapper
        # here. The loop is bounded by UNWRAP_CEILING, so a hostile payload cannot
        # spin, and it costs one lex per wrapper rather than one stack frame.
        deepest: list[list[str]] = []
        for words in commands:
            deepest.append(words)
            current = words
            for _ in range(UNWRAP_CEILING):
                inner = nested_command(strip_prefix(current))
                if not inner:
                    break
                try:
                    peeled = split_commands(inner)
                except ValueError:
                    break
                deepest.extend(peeled)
                if len(peeled) != 1:
                    break
                current = peeled[0]
        return deepest

    expanded: list[list[str]] = []
    for words in commands:
        expanded.append(words)
        inner = nested_command(strip_prefix(words))
        if inner:
            try:
                expanded.extend(expand_commands(inner, depth + 1))
            except ValueError:
                # An unparsable inner string leaves the outer command judged.
                continue
    return expanded


def strip_prefix(words: list[str]) -> list[str]:
    """Drop openers, env assignments, and wrappers to reach the real verb."""
    index = 0
    while index < len(words):
        word = words[index]
        if word in OPENERS or ASSIGNMENT.match(word):
            index += 1
            continue
        if word in WRAPPERS:
            takes_operand = word in WRAPPER_OPERAND
            index += 1
            # Consume the wrapper's own options, plus one value for an option
            # that takes one. A bare word here is the wrapped command.
            while index < len(words) and words[index].startswith("-"):
                index += 1
                if index < len(words) and not words[index].startswith("-"):
                    following = words[index + 1] if index + 1 < len(words) else None
                    if following is not None and not following.startswith("-"):
                        index += 1
            # `timeout 5 rm ...`: the duration belongs to the wrapper.
            if takes_operand and index < len(words) and not words[index].startswith("-"):
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


def resolved_critical() -> frozenset[str]:
    """CRITICAL with each entry passed through realpath, computed once.

    The platform's own symlinks are the problem: on macOS realpath("/etc") is
    "/private/etc", so a resolved path could never match the literal set and a
    symlink aimed at /etc was ranked `allow`. Both spellings are kept, because a
    target may arrive already resolved.
    """
    import os.path

    global _RESOLVED_CRITICAL
    if _RESOLVED_CRITICAL is None:
        entries = set(CRITICAL)
        for path in CRITICAL:
            try:
                entries.add(os.path.realpath(path))
            except OSError:
                continue
        _RESOLVED_CRITICAL = frozenset(entries)
    return _RESOLVED_CRITICAL


_RESOLVED_CRITICAL: frozenset[str] | None = None



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

    # A SYMLINK INTO A CRITICAL PATH, but only in the spellings that traverse it.
    # `rm -rf link` unlinks the link and leaves the target alone -- that is why the
    # bare form is deliberately not caught here. `rm -rf link/`, `link/.` and
    # `link/*` do follow into the target, so a link to /etc deleted /etc while the
    # literal comparison above saw only an unremarkable path under /tmp.
    #
    # Resolution is best-effort and read-only: a link that does not exist yet cannot
    # be judged, and os.path.realpath does not touch the filesystem contents.
    if target.endswith(("/", "/.", "/*")) and not target.startswith("~") and "$" not in target:
        import os.path

        base = target.rstrip("*").rstrip("/").removesuffix("/.")
        try:
            resolved = os.path.realpath(os.path.join(str(cwd), base))
        except OSError:
            resolved = ""
        # Compare the RESOLVED form against resolved CRITICAL entries. On macOS
        # realpath("/etc") is "/private/etc", so matching the literal set let a link
        # to /etc through: the resolution and the comparison have to agree on which
        # side of the platform's own symlinks they live.
        if resolved and (resolved == "/" or resolved in resolved_critical()):
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
    #
    # A BACKTICK hides it just as well. Testing only `$` meant `rm -rf $(echo /)`
    # denied while `rm -rf ` + backtick + `echo /` + backtick was silent -- the same
    # substitution in the older spelling, which shlex leaves intact as one token.
    if "$" in target or "`" in target:
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

    if verb == "find":
        return check_find(words, cwd)

    if verb in DESTRUCTIVE_BY_OTHER_MEANS:
        return check_other_destructive(verb, words, cwd)

    return None


# Verbs that destroy without being `rm`. The guard judged only rm/mkfs/dd/curl, so
# `find / -delete`, `truncate -s0 /etc/passwd` and `shred -u /etc/hosts` were all
# silent -- each as unrecoverable as the `rm -rf` spelling that denies. Only the
# CRITICAL-target case is judged here; the same verb aimed at a project path is
# ordinary work and stays silent.
DESTRUCTIVE_BY_OTHER_MEANS = frozenset({"truncate", "shred", "mv", "chmod", "chown"})


def targets_a_critical_path(words: list[str], cwd: Path, *, inside: bool = False) -> str:
    """Return the first argument resolving onto a critical path, or "".

    `inside=True` also matches a path UNDER a critical tree, which is the right
    question for a verb that destroys one file: truncating /etc/passwd is
    unrecoverable even though /etc/passwd is not itself in CRITICAL. For a verb that
    acts on a whole tree, the stricter tree-identity test is what is wanted, so that
    `mv build /tmp` is not judged by where build happens to live.
    """
    import os.path

    critical = resolved_critical()
    for word in words[1:]:
        if word.startswith("-") or "=" in word or "$" in word or "`" in word:
            continue
        candidate = word.rstrip("*").rstrip("/") or "/"
        try:
            absolute = os.path.realpath(os.path.join(str(cwd), candidate))
        except OSError:
            continue
        if absolute == "/" or absolute in critical:
            return word
        if inside and any(absolute.startswith(f"{entry}/") for entry in critical):
            # A scratch root wins over the critical tree containing it. /private is
            # critical and macOS resolves /tmp to /private/tmp, so without this every
            # temp file looked like a system file: `truncate -s0 /tmp/log.txt` denied.
            if any(absolute == temp or absolute.startswith(f"{temp}/") for temp in TEMP_ROOTS):
                continue
            return word
    return ""


def check_find(words: list[str], cwd: Path) -> tuple[str, str] | None:
    """Deny a `find` that deletes, when it is rooted at a critical path.

    `find / -delete` and `find / -exec rm -rf {} +` wipe the filesystem exactly as
    `rm -rf /` does, and neither reached a check before: the verb is `find`, and the
    `rm` inside `-exec` is an argument rather than a command position.
    """
    deletes = "-delete" in words or "-exec" in words or "-execdir" in words or "-ok" in words
    if not deletes:
        return None
    target = targets_a_critical_path(words, cwd)
    if not target:
        return None
    return (
        "deny",
        f"blocked by BS-10 (no find that deletes under a critical path): this find "
        f"is rooted at '{target}', which resolves onto the filesystem root or a "
        f"system-critical tree, and it carries -delete or -exec. That is as "
        f"unrecoverable as rm -rf on the same path. Narrow the search root to the "
        f"specific directory you meant.",
    )


def check_other_destructive(verb: str, words: list[str], cwd: Path) -> tuple[str, str] | None:
    """Deny truncate/shred/mv/chmod/chown aimed at a critical path.

    Each is unrecoverable in its own way -- truncate and shred destroy contents in
    place, mv makes the tree unreachable at its expected path, and a recursive mode
    or owner change on /usr breaks the system as thoroughly as deleting it. All were
    silent because the guard only ever looked for rm.
    """
    if verb in ("chmod", "chown") and not any(
        word.startswith("-") and ("R" in word or word == "--recursive") for word in words[1:]
    ):
        # A single-file mode change is ordinary work, even on a system path.
        return None
    # truncate and shred destroy one file's contents, so a path INSIDE a critical
    # tree is the case that matters -- /etc/passwd is not itself in CRITICAL. The
    # tree-acting verbs keep the stricter identity test.
    target = targets_a_critical_path(words, cwd, inside=verb in ("truncate", "shred"))
    if not target:
        return None
    return (
        "deny",
        f"blocked by BS-11 (no destructive {verb} on a critical path): '{target}' "
        f"resolves onto the filesystem root or a system-critical tree, and {verb} "
        f"there is unrecoverable or breaks the system. Name the specific path inside "
        f"your project that you meant instead.",
    )


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


REMOTE_CODE_ADVICE = (
    "BS-7 (warn on running a download without reading it): this executes code "
    "fetched from the network without inspecting it first, so nothing has "
    "verified what it does. Download it to a file, read it, then run it. "
    "Proceeding."
)


def check_remote_code(commands: list[list[str]], command: str) -> tuple[str, str] | None:
    """Warn when downloaded code reaches an interpreter without being read.

    Three routes, because the pipe was only the most recognisable one:

    The classic pipe, now to ANY interpreter and across intermediate stages.
    Restricting the sink to `sh`/`bash` missed `| python3`, `| perl`, `| ruby` and
    `| node`, which execute remote code just as completely, and requiring the shell
    to sit immediately after the download missed
    `curl ... | tee /tmp/x | sh`.

    Command substitution feeding a shell, as in `eval "$(curl -s ...)"` or
    `bash -c "$(curl ...)"`. Re-lexing cannot reach inside a substitution, since
    its value only exists once the shell runs, so this is a textual check.

    Process substitution, as in `bash <(curl -s ...)`, for the same reason.
    """
    verbs = [Path(strip_prefix(words)[0]).name for words in commands if strip_prefix(words)]
    downloaders = [index for index, verb in enumerate(verbs) if verb in DOWNLOADERS]

    # Any interpreter downstream of a download in the same pipeline, adjacent or not.
    for start in downloaders:
        if any(verb in INTERPRETERS for verb in verbs[start + 1 :]):
            return ("warn", REMOTE_CODE_ADVICE)

    # A download inside a substitution that a shell or `eval` consumes.
    if SUBSTITUTED_DOWNLOAD.search(command):
        return ("warn", REMOTE_CODE_ADVICE)

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


def base_cwd(raw: str) -> Path:
    """The directory the payload says the command runs in."""
    base = Path(raw) if raw and Path(raw).is_dir() else Path.cwd()
    try:
        return base.resolve()
    except OSError:
        return base


def cd_target(words: list[str]) -> str | None:
    """Return the absolute literal directory a `cd` moves to, if it is one.

    Only an absolute literal target is followed. A relative or variable-bearing
    `cd` would have to be guessed at, and guessing wrong is how a guard denies
    correct work; a variable-bearing `rm` target is denied on its own account
    anyway.
    """
    if not words or Path(words[0]).name != "cd":
        return None
    operands = [word for word in words[1:] if not word.startswith("-")]
    if len(operands) != 1:
        return None
    target = operands[0]
    if not target.startswith("/") or "$" in target:
        return None
    return target.rstrip("/") or "/"


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
        # The pipe check needs commands in their original adjacency, because
        # expansion splices a nested command in between two pipe stages and the
        # curl-to-shell pair stops being neighbours.
        literal = split_commands(command)
        commands = expand_commands(command)
    except ValueError:
        # Not parseable as shell. Nothing reliable to judge, so allow rather than
        # block on a quoting quirk.
        return 0

    cwd = base_cwd(raw_cwd)
    roots: dict[Path, Path | None] = {cwd: find_repo_root(cwd)}

    pipe = check_remote_code(literal, command)
    findings: list[tuple[str, str]] = []

    # Walk the chain in order, carrying the working directory forward. A `cd`
    # governs only the commands that FOLLOW it, which is the whole point of doing
    # this in sequence: matching the first `cd` anywhere in the string blamed
    # `rm -rf build; cd /etc` on a benign relative target, and let
    # `cd /tmp && cd /etc && rm -rf *` past because the first match won.
    for words in commands:
        stripped = strip_prefix(words)

        moved = cd_target(stripped)
        if moved is not None:
            cwd = Path(moved)
            if cwd not in roots:
                roots[cwd] = find_repo_root(cwd)
            continue

        sudo_finding = check_sudo(words)
        if sudo_finding:
            findings.append(sudo_finding)
        finding = check_command(stripped, cwd, roots[cwd])
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
