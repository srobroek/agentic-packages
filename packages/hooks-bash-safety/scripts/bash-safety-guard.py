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
        "coproc",
    }
)

# Wrappers whose first non-option word is their OWN operand rather than the
# wrapped command: `timeout 5 rm -rf /` and `nice -n 19` both put a value there.
# Without this, `5` was read as the verb and the `rm` behind it went unjudged.
WRAPPER_OPERAND = frozenset({"timeout", "flock"})

# Options with a separate value. Keeping this small table explicit avoids the
# old "look one word ahead" heuristic, which could consume a wrapper's command
# after an option that does not take a value (`flock -n lock rm ...`).
WRAPPER_OPTION_VALUES = {
    "sudo": frozenset({"-u", "--user", "-g", "--group", "-h", "--host", "-C", "--chdir"}),
    "doas": frozenset({"-u", "--user", "-C", "--chdir"}),
    "env": frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "ionice": frozenset({"-c", "--class", "-n", "--classdata", "-p", "--pid"}),
    "timeout": frozenset({"-k", "--kill-after", "-s", "--signal"}),
    "flock": frozenset({"-w", "--timeout", "-E", "--conflict-exit-code"}),
    "xargs": frozenset(
        {
            "-a", "--arg-file", "-E", "--eof", "-I", "--replace", "-L", "--max-lines",
            "-n", "--max-args", "-P", "--max-procs", "-s", "--max-chars",
            "--process-slot-var",
        }
    ),
    "stdbuf": frozenset({"-i", "-o", "-e"}),
}

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
BACKTICK_DOWNLOAD = re.compile(
    r"`\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*(?:/\S*/)?"
    r"(?:" + "|".join(sorted(DOWNLOADERS)) + r")\s",
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
    # Flush HERE, inside the guard, so a broken pipe surfaces as a caught error
    # rather than as an interpreter-shutdown failure. Deferred to shutdown, the write
    # exited 120 with nothing written and the fail-open wrapper never saw it, so the
    # decision was lost instead of merely undelivered.
    try:
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        pass


def _lex_tokens(command: str) -> list[str]:
    """Lex shell text once, preserving punctuation for the command splitter."""
    import shlex

    # shlex is quadratic in token length, and this hook runs on every Bash call, so
    # an outsized command is a stall rather than a parse. Measured on one unbroken
    # token: 50KB 31ms, 200KB 477ms, 400KB 1.4s, 800KB 4.7s, 1MB 14.5s end to end.
    if len(command) > MAX_COMMAND_CHARS:
        command = command[:MAX_COMMAND_CHARS]

    # A newline separates commands exactly like a semicolon, but shlex treats
    # it as ordinary whitespace, which merged a second line into the first and
    # hid its verb from every check. A BACKSLASH-newline is the opposite case: it
    # is a line continuation, so the two halves are one command.
    command = re.sub(r"\\\r?\n", " ", command)

    # shlex treats `#` as a comment opener even mid-line and discards everything
    # after it, so `echo hi # rm -rf /` lexed to just `echo hi` and the rm vanished.
    # A real shell only starts a comment where a word could start, so a `#` glued to
    # the end of a word (`file#1`) is data. Disabling shlex's comment handling and
    # cutting at a `#` that begins a word matches the shell for a trailing comment.
    command = re.sub(r"(?:(?<=\s)|^)#.*$", "", command)

    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.commenters = ""
    lexer.whitespace_split = True
    return list(lexer)  # raises ValueError on an unterminated quote


def _token_parts(token: str) -> list[str]:
    """Split punctuation runs that combine a group closer and a separator."""
    # shlex keeps `);` and `};` together. Those are two shell operators, not one
    # argument: leaving them fused lets `(cd /tmp); rm ...` carry the cd into the
    # following command and hide the rm.
    if (
        len(token) > 1
        and ";" in token
        and set(token) <= {";", "&", "|", "(", ")", "{", "}"}
    ):
        return list(token)
    return [token]


def _split_command_records(command: str) -> list[tuple[list[str], int]]:
    """Split commands and retain parenthesized-subshell depth for cwd tracking."""
    commands: list[tuple[list[str], int]] = []
    current: list[str] = []
    subshell_depth = 0

    def flush() -> None:
        nonlocal current
        if current:
            commands.append((current, subshell_depth))
            current = []

    for raw_token in _lex_tokens(command):
        for token in _token_parts(raw_token):
            if token == "(":
                flush()
                subshell_depth += 1
                continue
            if token == ")":
                flush()
                subshell_depth = max(0, subshell_depth - 1)
                continue
            if token and set(token) <= {";", "&", "|"}:
                flush()
                continue
            # A keyword or group opener also begins a command, and a terminator ends
            # one. Treating either as a plain word left it standing where the verb
            # belonged, so a guarded verb inside a loop or block went unseen.
            if token in COMMAND_BOUNDARIES or token in CLOSERS:
                flush()
                continue
            current.append(token)
    flush()
    return commands


def split_commands(command: str) -> list[list[str]]:
    """Tokenize into a list of commands, each a list of words.

    shlex handles quoting, escapes, and comments, so a dangerous phrase inside a
    quoted argument stays an argument. Unbalanced quotes mean the string is not
    parseable as shell, and the caller treats that as nothing to judge rather
    than guessing.
    """
    return [words for words, _ in _split_command_records(command)]


def split_pipeline_groups(command: str) -> list[list[list[str]]]:
    """Split literal commands into pipelines without joining `;` or `&&` chains."""
    groups: list[list[list[str]]] = []
    pipeline: list[list[str]] = []
    current: list[str] = []

    def flush_command() -> None:
        nonlocal current
        if current:
            pipeline.append(current)
            current = []

    def flush_pipeline() -> None:
        flush_command()
        if pipeline:
            groups.append(pipeline.copy())
            pipeline.clear()

    for raw_token in _lex_tokens(command):
        for token in _token_parts(raw_token):
            if token in ("|", "|&"):
                flush_command()
                continue
            if token and set(token) <= {";", "&", "|"}:
                flush_pipeline()
                continue
            if token in COMMAND_BOUNDARIES or token in CLOSERS:
                flush_pipeline()
                continue
            current.append(token)
    flush_pipeline()
    return groups


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

    def inline_command(value: str) -> str:
        # shlex leaves the `$` marker from Bash ANSI-C quoting (`$'rm ...'`).
        # It is a literal command string, not a variable named `rm`.
        return (
            value[1:]
            if value.startswith("$")
            and not value.startswith("$(")
            and any(c.isspace() for c in value)
            else value
        )

    if verb in SHELLS:
        for index, word in enumerate(words[1:], start=1):
            # `-c` may be bundled with other short flags, as in `sh -ec`.
            if word.startswith("-") and not word.startswith("--") and "c" in word:
                suffix = word.split("c", 1)[1]
                return inline_command(
                    suffix or (words[index + 1] if index + 1 < len(words) else "")
                ) or None
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

    if verb == "env":
        for index, word in enumerate(words[1:], start=1):
            option = word.split("=", 1)[0]
            if option in ("-S", "--split-string"):
                if "=" in word:
                    return inline_command(word.split("=", 1)[1])
                return (
                    inline_command(words[index + 1])
                    if index + 1 < len(words)
                    else None
                )

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
                inner = nested_payload(current)
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
        inner = nested_payload(words)
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
        # Wrappers by BASENAME. The set was matched against the raw word, so an
        # absolute path defeated it: `/usr/bin/sudo rm -rf /` left `/usr/bin/sudo`
        # in command position and the rm behind it unjudged. Every other verb read
        # in this module already uses Path(word).name.
        name = Path(word).name
        if name in WRAPPERS:
            takes_operand = name in WRAPPER_OPERAND
            index += 1
            if name == "coproc" and index + 1 < len(words):
                # Bash permits `coproc NAME command`; distinguish the optional
                # name from a command we know how to inspect.
                starters = (
                    WRAPPERS
                    | SHELLS
                    | STRING_EVALUATORS
                    | DESTRUCTIVE_VERBS
                    | INTERPRETERS
                    | {"cd", "find", "curl", "wget"}
                )
                if Path(words[index]).name not in starters and Path(words[index + 1]).name in starters:
                    index += 1
            # Consume options and only the values declared by that wrapper. The
            # previous lookahead assumed every option might take a value; for an
            # operand-taking wrapper that skipped its real command:
            # `flock -n /tmp/l rm -rf /` and `timeout --preserve-status 5 rm -rf /`.
            while index < len(words) and words[index].startswith("-"):
                if words[index] == "--":
                    index += 1
                    break
                option = words[index]
                index += 1
                option_name = option.split("=", 1)[0]
                if (
                    "=" not in option
                    and option_name in WRAPPER_OPTION_VALUES.get(name, ())
                    and index < len(words)
                    and not words[index].startswith("-")
                ):
                    index += 1
            # `timeout 5 rm ...` and `flock /tmp/l rm ...`: the first bare word is
            # the wrapper's operand, not the command.
            if takes_operand and index < len(words) and not words[index].startswith("-"):
                index += 1
            # `--` ends wrapper options either before or after the operand.
            if index < len(words) and words[index] == "--":
                index += 1
            continue
        # `--` ends the wrapper's own options; the verb is whatever follows. It was
        # left in place, so `timeout 5 -- rm -rf /` presented `--` as the verb and
        # every rule missed the rm behind it. An end-of-options marker is never
        # itself a command.
        if word == "--":
            index += 1
            continue
        break
    return words[index:]


def nested_payload(words: list[str]) -> str | None:
    """Find an inline command after wrappers, including `sudo env -S ...`."""
    for candidate in (strip_prefix(words), words):
        inner = nested_command(candidate)
        if inner:
            return inner
    for index, word in enumerate(words):
        if Path(word).name == "env":
            inner = nested_command(words[index:])
            if inner:
                return inner
    return None


def has_recursive_force(flags: list[str]) -> bool:
    """True when the flags request both recursion and force, in any spelling."""
    recursive = force = False
    for flag in flags:
        # GNU accepts any unambiguous ABBREVIATION of a long option, so `rm --rec
        # --fo /` really deletes -- verified with GNU rm, which removed the tree while
        # the exact-match test read it as two unknown flags and returned False. BSD rm
        # rejects them, so the honest-mistake path is Linux, but the guard has to
        # judge the command it is handed rather than the platform it happens to be on.
        #
        # `--r` is deliberately enough for recursive: no other rm long option starts
        # with r, so the abbreviation is unambiguous exactly as GNU treats it.
        if flag.startswith("--") and len(flag) > 2:
            name = flag[2:].split("=", 1)[0]
            if "recursive".startswith(name):
                recursive = True
                continue
            if "force".startswith(name):
                force = True
                continue
            continue
        if flag.startswith("-"):
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



def expand_braces(target: str) -> list[str]:
    """Expand one level of `a{b,c}d` into the paths a shell would produce.

    One level is enough for the judgement: `/{etc,usr}` and `/etc/{a,b}` both put a
    critical path in at least one branch, and a nested case still yields a branch
    containing the outer prefix. Bounded output, because a hostile
    `{a,b}{a,b}{a,b}...` should not become a combinatorial expansion inside a hook.
    """
    start = target.find("{")
    end = target.find("}", start + 1)
    if start < 0 or end < 0:
        return [target]
    prefix, body, suffix = target[:start], target[start + 1 : end], target[end + 1 :]
    return [f"{prefix}{piece}{suffix}" for piece in body.split(",")[:16] if piece]


def traverses_critical_symlink(target: str, cwd: Path) -> bool:
    """Return whether a non-final path component links directly to a critical root."""
    import os.path

    if target.startswith(("~", "$", "`")):
        return False
    path = Path(target if target.startswith("/") else os.path.join(str(cwd), target))
    try:
        resolved_target = os.path.realpath(path)
    except OSError:
        resolved_target = ""
    # /var is a platform symlink to /private/var on macOS; scratch paths beneath it
    # are explicitly safe and must not inherit the critical-root classification.
    if resolved_target and any(
        resolved_target == temp or resolved_target.startswith(f"{temp}/")
        for temp in TEMP_ROOTS
    ):
        return False
    # `rm -rf link` unlinks the link; only inspect components before the final one.
    for parent in path.parents:
        # On macOS `/var` itself resolves to `/private/var`; it is an ancestor
        # alias, not the user-created link that the target may traverse.
        if str(path).startswith(("/var/folders/", "/private/var/folders/")) and str(
            parent
        ) in {"/var", "/private/var"}:
            continue
        try:
            if parent.is_symlink() and os.path.realpath(parent) in resolved_critical():
                return True
        except OSError:
            continue
    return False


def is_critical_descendant(path: str) -> bool:
    """Match system-critical descendants without classifying user homes wholesale."""
    for critical in resolved_critical():
        if critical in {"/Users", "/root", "/private"}:
            continue
        if path == critical or path.startswith(f"{critical}/"):
            if any(path == temp or path.startswith(f"{temp}/") for temp in TEMP_ROOTS):
                continue
            return True
    return False



def classify_rm_target(target: str, cwd: Path, root: Path | None) -> str:
    """Rank one `rm -rf` target: deny-critical, deny-var, warn, or allow."""
    if not target:
        return "allow"

    if target in CATASTROPHIC_TARGETS:
        return "deny-root"

    # BRACE EXPANSION is one token to the lexer but many paths to the shell, so
    # `rm -rf /{etc,usr}` carried no unresolvable marker and ranked warn. Expanding
    # it and judging the worst branch is what the shell would actually do.
    if "{" in target and "," in target and "}" in target:
        worst = "allow"
        order = {"deny-root": 4, "deny-critical": 3, "deny-var": 2, "warn": 1, "allow": 0}
        for branch in expand_braces(target):
            if branch == target:
                continue
            ranked = classify_rm_target(branch, cwd, root)
            if order[ranked] > order[worst]:
                worst = ranked
        if worst != "allow":
            return worst

    # A relative target is as bad as an absolute one when the directory it
    # resolves against is itself critical: `cd / && rm -rf *` deletes exactly
    # what `rm -rf /*` deletes.
    if not target.startswith(("/", "~")) and "$" not in target:
        if str(cwd) == "/":
            return "deny-root"
        # Resolved form too: on macOS a shell sitting in /etc reports /private/etc,
        # so the literal-only test lost the relative-target deny for exactly the
        # directories it most needed to cover.
        if str(cwd) in CRITICAL or str(cwd) in resolved_critical():
            return "deny-critical"

    # Both spellings of every critical entry, because the platform's own symlinks
    # mean a user may legitimately write either: /etc and /private/etc name one
    # directory, and only the first was denied.
    for critical in resolved_critical():
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

    # `~other` is expanded by the shell to another user's home root, which the
    # guard cannot safely infer from the spelling. Treat it like an unresolved
    # variable; `~/child` remains a recoverable path in the current home.
    if target.startswith("~") and not target.startswith("~/"):
        return "deny-var"

    if target.startswith("~/"):
        return "warn"

    absolute = normalize(target, cwd)

    # A path below a symlink to /etc (for example `/tmp/etclink/passwd`) follows
    # into the critical tree even though its literal spelling does not name it.
    if traverses_critical_symlink(target, cwd):
        return "deny-critical"
    if is_critical_descendant(absolute):
        return "deny-critical"

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
        # `of=` is the familiar spelling, but a REDIRECT reaches the same device:
        # `dd if=/dev/zero > /dev/disk0` overwrites the disk with no `of=` operand
        # anywhere, and the scan for one missed it entirely.
        for index, word in enumerate(words[1:], start=1):
            # An operand behind a variable cannot be checked, and dd is LESS
            # recoverable than the `rm -rf $VAR` that BS-9 already denies: writing
            # over the wrong block device destroys a partition table. Same reasoning,
            # same verdict, so the two rules stop disagreeing.
            if (word.startswith("of=") or word in (">", ">>")) and any(
                ch in word for ch in "$`"
            ):
                return (
                    "deny",
                    "blocked by BS-6 (no dd to an unresolvable target): the output "
                    "operand hides behind a shell variable or command substitution, so "
                    "the guard cannot tell a file from a raw block device. Resolve it "
                    "to a literal path first, then re-run.",
                )
            if word in (">", ">>") and index + 1 < len(words):
                nxt = words[index + 1]
                if any(ch in nxt for ch in "$`"):
                    return (
                        "deny",
                        "blocked by BS-6 (no dd to an unresolvable target): the redirect "
                        "target hides behind a shell variable or command substitution, so "
                        "the guard cannot tell a file from a raw block device. Resolve it "
                        "to a literal path first, then re-run.",
                    )
            device = ""
            if word.startswith("of=/dev/"):
                device = word[3:]
            elif word in (">", ">>") and index + 1 < len(words):
                candidate = words[index + 1]
                if candidate.startswith("/dev/"):
                    device = candidate
            # Normalize before the compare: `/dev/./null` and `/dev/../dev/null` are
            # /dev/null, and comparing the literal denied a harmless redirect.
            if device:
                import posixpath

                device = posixpath.normpath(device)
            if device and device not in PSEUDO_DEVICES:
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
    # Path(...).name, because every other verb read in this module does the same:
    # `/usr/bin/sudo rm -f ...` lost the advisory on a bare string comparison.
    #
    # The caller passes words that strip_prefix has ALREADY walked, which removes
    # wrappers -- and sudo is a wrapper. So sudo is detected on the raw words here
    # and the verb is read from the stripped remainder, which is what the caller
    # supplies. Passing the pre-stripped list to strip_prefix again dropped the
    # advisory for the plain `sudo rm -f` case entirely.
    if not words:
        return None
    # Scan the leading run of env assignments and wrappers rather than a fixed
    # window: `FOO=1 nohup /usr/bin/sudo rm ...` puts sudo third, and any fixed
    # index either misses it or hard-codes an ordering the shell does not require.
    if not any(
        Path(word).name in ("sudo", "doas")
        for word in words
        if not ASSIGNMENT.match(word) or Path(word).name in ("sudo", "doas")
    ):
        return None
    inner = strip_prefix(words)
    if not inner:
        return None
    verb = Path(inner[0]).name
    if verb in SHELLS | STRING_EVALUATORS:
        nested = nested_command(inner)
        if nested:
            for nested_words in expand_commands(nested):
                nested_inner = strip_prefix(nested_words)
                if nested_inner and Path(nested_inner[0]).name in DESTRUCTIVE_VERBS:
                    verb = Path(nested_inner[0]).name
                    break
    if verb not in DESTRUCTIVE_VERBS:
        return None
    # Verbs that take no subcommand at all: for these, every bare word is an
    # operand, so consulting READ_ONLY_SUBCOMMANDS silenced the advisory whenever a
    # PATH happened to be named like one -- `sudo rm -rf install` went quiet.
    if verb not in ("rm", "rmdir", "dd", "shred", "truncate"):
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


def substitution_reaches_interpreter(commands: list[list[str]], command: str) -> bool:
    """Check substitutions only when an interpreter consumes their output."""
    if not (SUBSTITUTED_DOWNLOAD.search(command) or BACKTICK_DOWNLOAD.search(command)):
        return False

    for words in commands:
        stripped = strip_prefix(words)
        if not stripped:
            continue
        verb = Path(stripped[0]).name
        text = " ".join(stripped[1:])
        if verb in STRING_EVALUATORS:
            if SUBSTITUTED_DOWNLOAD.search(text) or BACKTICK_DOWNLOAD.search(text):
                return True
        if verb in INTERPRETERS:
            if "<(" in text:
                return True
            if verb in SHELLS and nested_command(stripped):
                inner = nested_command(stripped) or ""
                if SUBSTITUTED_DOWNLOAD.search(inner) or BACKTICK_DOWNLOAD.search(inner):
                    return True
    return False


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
    # Only stages in the SAME pipeline are connected. The old flat command list
    # joined `curl URL; python3 local.py` and warned on unrelated sequential work.
    for pipeline in split_pipeline_groups(command):
        verbs = [
            Path(strip_prefix(words)[0]).name
            for words in pipeline
            if strip_prefix(words)
        ]
        downloaders = [index for index, verb in enumerate(verbs) if verb in DOWNLOADERS]
        for start in downloaders:
            if any(verb in INTERPRETERS for verb in verbs[start + 1 :]):
                return ("warn", REMOTE_CODE_ADVICE)

    # A download inside a substitution that a shell/evaluator consumes.
    if substitution_reaches_interpreter(commands, command):
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


def cd_target(words: list[str], cwd: Path) -> str | None:
    """Return the literal directory a `cd` moves to, resolved against `cwd`.

    A variable-bearing `cd` is still not followed: it would have to be guessed at,
    and guessing wrong is how a guard denies correct work; a variable-bearing `rm`
    target is denied on its own account anyway.

    A RELATIVE hop is followed, because dropping it left the carried cwd stale and
    the deny was lost: `cd /tmp && cd ../etc && rm -rf *` reported nothing, while
    the shell really does land in /etc and wipe it. The result is normalized for the
    same reason -- `cd /usr/../etc` and `cd //etc` both land in /etc, and comparing
    the unnormalized text against CRITICAL matched neither.
    """
    if not words or Path(words[0]).name != "cd":
        return None
    operands = [word for word in words[1:] if not word.startswith("-")]
    if len(operands) != 1:
        return None
    target = operands[0]
    if "$" in target or "`" in target or target.startswith("~"):
        return None
    candidate = Path(normalize(target, cwd))
    # A failed `cd` leaves the shell in its previous directory. Following a
    # nonexistent target changed the guard's cwd anyway and let `cd /missing;
    # rm -rf *` evade a critical cwd. Existing directories are resolved through
    # symlinks so `cd etclink && rm -rf *` is judged as a removal under /etc.
    if not candidate.is_dir():
        return None
    try:
        return str(candidate.resolve())
    except OSError:
        return str(candidate)


def extract_substitution_commands(command: str, depth: int = 0) -> list[str]:
    """Extract executable `$()` and backtick bodies while respecting shell quotes."""
    if depth >= UNWRAP_CEILING:
        return []
    substitutions: list[str] = []

    def backtick_body(start: int) -> tuple[str | None, int]:
        index = start + 1
        while index < len(command):
            if command[index] == "\\":
                index += 2
                continue
            if command[index] == "`":
                return command[start + 1 : index], index + 1
            index += 1
        return None, len(command)

    def dollar_body(start: int) -> tuple[str | None, int]:
        depth = 1
        index = start + 2
        quote = ""
        while index < len(command):
            char = command[index]
            if quote == "'":
                if char == "'":
                    quote = ""
                index += 1
                continue
            if quote == '"':
                if char == "\\":
                    index += 2
                    continue
                if char == '"':
                    quote = ""
                    index += 1
                    continue
                if command.startswith("$(", index):
                    depth += 1
                    index += 2
                    continue
                if char == "`":
                    _, index = backtick_body(index)
                    continue
            elif char in ("'", '"'):
                quote = char
                index += 1
                continue
            elif char == "\\":
                index += 2
                continue
            elif command.startswith("$(", index):
                depth += 1
                index += 2
                continue
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return command[start + 2 : index], index + 1
            index += 1
        return None, len(command)

    index = 0
    quote = ""
    while index < len(command):
        char = command[index]
        if quote == "'":
            if char == "'":
                quote = ""
            index += 1
            continue
        if quote == '"':
            if char == "\\":
                index += 2
                continue
            if char == '"':
                quote = ""
                index += 1
                continue
            if command.startswith("$(", index):
                body, index = dollar_body(index)
                if body is None:
                    break
                substitutions.append(body)
                substitutions.extend(extract_substitution_commands(body, depth + 1))
                continue
            if char == "`":
                body, index = backtick_body(index)
                if body is None:
                    break
                substitutions.append(body)
                substitutions.extend(extract_substitution_commands(body, depth + 1))
                continue
        elif char in ("'", '"'):
            quote = char
            index += 1
            continue
        elif char == "\\":
            index += 2
            continue
        elif command.startswith("$(", index):
            body, index = dollar_body(index)
            if body is None:
                break
            substitutions.append(body)
            substitutions.extend(extract_substitution_commands(body, depth + 1))
            continue
        elif char == "`":
            body, index = backtick_body(index)
            if body is None:
                break
            substitutions.append(body)
            substitutions.extend(extract_substitution_commands(body, depth + 1))
            continue
        index += 1
    return substitutions


def inspect_sequence(
    command: str,
    cwd: Path,
    roots: dict[Path, Path | None],
    findings: list[tuple[str, str]],
    depth: int = 0,
) -> None:
    """Judge a command sequence while keeping subshell and nested-shell cwd local."""
    if depth >= UNWRAP_CEILING:
        return

    # Command substitutions execute even when embedded in an otherwise harmless
    # argument (`echo "$(rm -rf /)"`). Parse them separately so quoting the whole
    # argument cannot hide a destructive nested command; single-quoted prose is
    # ignored by the extractor.
    for substitution in extract_substitution_commands(command):
        inspect_sequence(substitution, cwd, roots, findings, depth + 1)

    scope_cwds: dict[int, Path] = {0: cwd}
    active_scope = 0
    for words, scope in _split_command_records(command):
        if scope > active_scope:
            for level in range(active_scope + 1, scope + 1):
                scope_cwds[level] = scope_cwds[level - 1]
        elif scope < active_scope:
            for level in range(active_scope, scope, -1):
                scope_cwds.pop(level, None)
        active_scope = scope
        current_cwd = scope_cwds[scope]
        stripped = strip_prefix(words)

        moved = cd_target(stripped, current_cwd)
        if moved is not None:
            current_cwd = Path(moved)
            scope_cwds[scope] = current_cwd
            if current_cwd not in roots:
                roots[current_cwd] = find_repo_root(current_cwd)
            continue

        sudo_finding = check_sudo(words)
        if sudo_finding:
            findings.append(sudo_finding)
        finding = check_command(stripped, current_cwd, roots[current_cwd])
        if finding:
            findings.append(finding)

        # A nested shell/evaluator has its own working-directory scope. Its cd
        # must not leak into the parent sequence, while its destructive commands
        # still need to be judged in the child scope.
        inner = nested_payload(words)
        if inner:
            inspect_sequence(inner, current_cwd, roots, findings, depth + 1)


def main() -> int:
    # Read BYTES and decode leniently. `sys.stdin.read()` raises UnicodeDecodeError
    # on one undecodable byte anywhere in the payload -- including in a field this
    # guard never looks at -- and the fail-open wrapper then swallowed the error, so
    # a single stray byte silenced the guard on a command it would otherwise deny.
    payload = _read_stdin_text()
    if not payload.strip():
        return 0

    try:
        command, raw_cwd = extract(payload)
    except (ValueError, TypeError):
        return 0
    if not command:
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

    # BS-3 IS JUDGED ON LEXED WORDS, not on the raw string. The substring test that
    # ran before tokenization was wrong in both directions at once:
    #   * it MISSED `'--dangerously-bypass-approvals'-and-sandbox`, which the shell
    #     rejoins into the single flag word, because the raw text contains a quote.
    #   * it DENIED any command that merely NAMED the flag -- `grep -rn -- <flag> .`,
    #     `echo "never pass <flag>"`, a commit message documenting it. It blocked
    #     this repository's own test harness for quoting the flag in a heredoc.
    # A lexed word is the flag or it is data, and the shell has already decided which.
    # After `--` the shell stops treating words as options, so the same text there is
    # an operand -- `grep -rn -- <flag> .` searches FOR the flag rather than passing
    # it. Everything before `--` is judged.
    for words in commands:
        for word in words:
            if word == "--":
                break
            if word.lower() == "--dangerously-bypass-approvals-and-sandbox":
                emit(
                    "deny",
                    "blocked by BS-3 (no sandbox-bypass flag): "
                    "--dangerously-bypass-approvals-and-sandbox disables the safety "
                    "envelope for the whole session.",
                )
                return 0

    cwd = base_cwd(raw_cwd)
    roots: dict[Path, Path | None] = {cwd: find_repo_root(cwd)}

    pipe = check_remote_code(literal, command)
    findings: list[tuple[str, str]] = []

    inspect_sequence(command, cwd, roots, findings)

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
    # Python flushes stdout again at interpreter shutdown, AFTER this block, and on a
    # closed pipe that flush exits 120 with the fail-open wrapper long since past. So
    # the stream is detached here once the decision is written: the caller has already
    # gone away, and a guard must not turn a delivered verdict into a 120.
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: a guard that crashes closed wedges the agent.
        raise SystemExit(0)
    finally:
        try:
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            import os

            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
