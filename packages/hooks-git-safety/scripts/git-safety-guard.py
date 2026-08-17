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
verb has already matched, and each answer is cached so a repeated question costs
nothing. There are up to three distinct calls per decision -- porcelain status,
a clean dry-run, and a work-tree check -- not one batched call as this said
previously; they are separate because git has no single command that answers all
three, and each is only reached by the rule that needs it. A warning that fires on a clean tree is noise the agent learns to
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

# Invocations that carry a command as an ARGUMENT, so its git call never reaches
# the tokenizer unless the argument is lexed again.
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "ash", "busybox"})
STRING_EVALUATORS = frozenset({"eval", "source", "."})

# Depth bound on that re-lexing. Four is past any real nesting and keeps a
# self-referential string from looping.
MAX_NESTING = 4

# Per-subprocess timeout. It has to fit INSIDE the hook's own budget, which
# hooks.json sets to 10s: a 10s subprocess timeout meant one stalled git call
# consumed the entire allowance, the runtime killed the hook, and the warning was
# lost rather than merely late. Up to three calls may run for one decision, so the
# ceiling is the budget divided by that, less a margin for interpreter start.
GIT_SUBPROCESS_TIMEOUT = 3

# Cap on the command text handed to the lexer, matching the bash guard. 64KB lexes
# in well under 50ms and is far past any hand-written command.
MAX_COMMAND_CHARS = 65536

# Global git options that take a separate value, so the value is not mistaken for
# the subcommand.
GIT_OPTIONS_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})

# A redirect flag whose value carries a `$` or `~` points at a working tree the
# guard cannot resolve.
#
# THE ENV-ASSIGNMENT SPELLINGS COUNT TOO. `GIT_DIR` and `GIT_WORK_TREE` retarget
# git exactly as `--git-dir` and `--work-tree` do, so matching only the flag form
# left `GIT_DIR=$D/.git git clean -fdx` allowed while the flag form denied --
# verified against this guard before the fix. The env form is the more natural
# thing for an agent to write when a path is already in a variable, which is
# precisely the case GS-2 exists to stop.
UNVERIFIABLE_REDIRECT = re.compile(
    r"""(?:^|\s)(?:-C\s+|--git-dir[\s=]|--work-tree[\s=]|GIT_DIR=|GIT_WORK_TREE=)"""
    # A `~` is a home reference only at the START of the value (or right after the
    # opening quote). Mid-path it is an ordinary character -- `/tmp/has~tilde/x` is a
    # real directory name, and denying it was a false positive on a path the guard
    # could have resolved perfectly well. `$` stays unrestricted: a variable anywhere
    # in the value makes the whole path unresolvable.
    r"""["']?(?:~|[^"';&|]*\$)"""
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
    # Flush HERE, inside the guard, so a broken pipe surfaces as a caught error
    # rather than as an interpreter-shutdown failure. Deferred to shutdown, the write
    # exited 120 with nothing written and the fail-open wrapper never saw it, so the
    # decision was lost instead of merely undelivered.
    try:
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        pass


def split_commands(command: str) -> list[list[str]]:
    """Tokenize into commands. A newline separates exactly like a semicolon.

    Both rewrites below exist in the bash guard for reasons that apply identically
    here, and their absence was two live holes: `git reset \\<newline>--hard` was
    silent because the continuation split one command into two, and `ls # note<newline>
    git -C "$D" reset --hard` was silent because shlex read `#` as a comment and
    discarded the rest of the STRING, newline included, so the git call vanished.
    """
    import shlex

    # Cap the lexer input, as the sibling bash guard does. Measured on one unbroken
    # token: 200KB 614ms, 500KB 2.7s, 2MB past 25s -- and this hook has a 10s budget,
    # so a padded argument was a stall rather than a parse. Truncating is safe in the
    # direction that matters: every rule matches the git verb and its flags, which sit
    # at the FRONT, and bailing out entirely would let any payload buy silence by
    # padding itself.
    if len(command) > MAX_COMMAND_CHARS:
        command = command[:MAX_COMMAND_CHARS]

    # A backslash-newline is a line continuation: the two halves are ONE command.
    command = re.sub(r"\\\r?\n", " ", command)

    # A real shell starts a comment only where a word could start, so a `#` glued to
    # a word (`file#1`) is data. Cut at a word-initial `#` and disable shlex's own
    # comment handling, which would otherwise eat the following lines.
    command = re.sub(r"(?:(?<=\s)|^)#[^\n]*", "", command)

    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.commenters = ""
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


def nested_command(words: list[str]) -> str | None:
    """The command string a shell invocation would run, if any.

    `sh -c '<cmd>'` and `eval <cmd>` pass a command through as arguments, so the
    git call inside never reached the tokenizer: `eval git -C $OTHER reset --hard`
    was allowed silently while the bare form denied under GS-2.
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
        # Drop the evaluator's own leading options only: filtering every `-` word
        # would discard the WRAPPED command's flags too, which is how the sibling
        # bash-safety guard lost the `-rf` from `eval rm -rf /`.
        rest = words[1:]
        index = 0
        while index < len(rest) and rest[index].startswith("-"):
            index += 1
        # `eval a b` concatenates its arguments into one command line.
        return " ".join(rest[index:]) if rest[index:] else None

    return None


def expand_commands(command: str, depth: int = 0) -> list[list[str]]:
    """Tokenize, then re-lex any nested shell string so its git call is judged too.

    The outer invocation is kept as well as its expansion, so a rule keyed on the
    outer form still sees it.
    """
    commands = split_commands(command)
    if depth >= MAX_NESTING:
        return commands

    expanded: list[list[str]] = []
    for words in commands:
        expanded.append(words)
        # Reach past openers, env assignments, and wrappers to the real verb, the
        # same prefixes git_invocation skips.
        index = 0
        while index < len(words) and (
            words[index] in COMMAND_BOUNDARIES
            or words[index] in WRAPPERS
            or ASSIGNMENT.match(words[index])
        ):
            index += 1
        inner = nested_command(words[index:])
        if inner:
            try:
                expanded.extend(expand_commands(inner, depth + 1))
            except ValueError:
                # An unparsable inner string leaves the outer command judged.
                continue
    return expanded


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
        # Wrappers by BASENAME: matched against the raw word, an absolute path
        # defeated the set and left `/usr/bin/sudo` in command position.
        name = Path(word).name
        if name in WRAPPERS:
            takes_operand = name in WRAPPER_OPERAND
            index += 1
            # Consume the wrapper's own options, plus one value for an option that
            # takes one. Skipping only the wrapper WORD left `-n` standing where the
            # verb belonged, so `nice -n 5 git ... reset --hard` was silent while the
            # bare command denied -- six wrapper forms defeated the deny this way.
            # `--` STOPS THE SCAN. It ends the wrapper's options, so the next word
            # is the command. Treated as just another option, the lookahead below
            # swallowed it AND the verb: `sudo -u root -- git -C "$D" reset --hard`
            # was silent while the same line without `--` denied under GS-2.
            while index < len(words) and words[index].startswith("-"):
                if words[index] == "--":
                    index += 1
                    break
                index += 1
                if index < len(words) and not words[index].startswith("-"):
                    following = words[index + 1] if index + 1 < len(words) else None
                    if following is not None and not following.startswith("-"):
                        index += 1
            # A `--` reached after an option VALUE still ends the options. Without
            # this, `sudo -u root -- git -C "$D" reset --hard` left `root` in command
            # position: `-u` consumed `root`, the loop saw `--` was not a bare word,
            # and stopped one word short of the verb.
            if index < len(words) and words[index] == "--":
                index += 1
            elif (
                index + 1 < len(words)
                and words[index + 1] == "--"
                and not words[index].startswith("-")
                and Path(words[index]).name not in WRAPPERS
                and not takes_operand
            ):
                index += 2
            # `timeout 5 git ...`: the duration belongs to the wrapper.
            if takes_operand and index < len(words) and not words[index].startswith("-"):
                index += 1
                # `timeout 5 -- git ...`: the marker follows the operand.
                if index < len(words) and words[index] == "--":
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


def redirect_target(words: list[str], cwd: Path) -> Path:
    """Return the working tree a git invocation actually acts on.

    `git -C <other> reset --hard` performs the reset in <other>, but the state the
    warnings are gated on was read from the payload cwd -- so a destructive op in a
    dirty repo went unwarned whenever it was aimed there from a clean one. The
    redirect value was parsed and thrown away.

    All five spellings redirect: `-C`, `--work-tree`, `--git-dir` (both `=` and
    space forms), and the GIT_WORK_TREE / GIT_DIR env assignments. A `--git-dir`
    pointing at `<tree>/.git` names the tree one level up, which is the form
    `git -C` would have produced anyway.

    An unresolvable value is NOT guessed at: a target carrying `$`, a backtick or
    `~` returns the cwd unchanged, because GS-2 already denies a destructive op
    behind an unexpanded variable and guessing here could only move a warning onto
    the wrong repository.
    """
    target = ""
    index = 0
    while index < len(words):
        word = words[index]
        for prefix in ("--work-tree=", "--git-dir=", "GIT_WORK_TREE=", "GIT_DIR="):
            if word.startswith(prefix):
                target = word[len(prefix) :]
                break
        else:
            if word in ("-C", "--work-tree", "--git-dir") and index + 1 < len(words):
                target = words[index + 1]
                index += 1
        index += 1
        if target:
            break

    if not target or any(ch in target for ch in "$`~"):
        return cwd
    target = target.strip("\"'")
    if target.endswith("/.git"):
        target = target[: -len("/.git")]
    elif target.endswith(".git") and "/" not in target:
        return cwd
    try:
        resolved = Path(target) if target.startswith("/") else cwd / target
        return resolved.resolve()
    except (OSError, ValueError):
        return cwd


def _git_binary() -> str:
    """Absolute path to git, so the state read cannot follow a planted PATH entry.

    The guard's verdict depends on what this subprocess reports, so a `git` earlier
    on PATH could lie about whether a tree is dirty and turn a warning off. Falls
    back to the bare name when git is somewhere unusual: a guard that cannot find
    git at all should still try rather than fail closed.
    """
    import shutil

    for candidate in ("/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git"):
        if Path(candidate).is_file():
            return candidate
    return shutil.which("git") or "git"


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
                [
                    _git_binary(),
                    "-C",
                    str(self._cwd),
                    # A repo-local core.fsmonitor is a COMMAND git runs, so reading
                    # the state of an untrusted checkout would execute whatever that
                    # repository configured. The guard exists to gate destructive
                    # commands, so it must not become an execution path itself.
                    "-c",
                    "core.fsmonitor=",
                    # Same reasoning for the pager and any alias expansion: neither is
                    # needed to read porcelain output, and both can run a command.
                    "-c",
                    "core.pager=cat",
                    "--no-optional-locks",
                    *args,
                ],
                capture_output=True,
                text=True,
                timeout=GIT_SUBPROCESS_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout if result.returncode == 0 else None

    def tracks_path(self, candidate: str) -> bool:
        """True when git tracks this path, so it is a pathspec and not a start-point.

        The distinction is what keeps `git checkout -b feat main` quiet: `main` is a
        branch, not a tracked file, so it is not a path being discarded.
        """
        output = self._run(["ls-files", "--error-unmatch", "--", candidate])
        return bool(output is not None and output.strip())

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


def checkout_discards_a_path(rest: list[str], state: RepoState) -> bool:
    """True for `git checkout <commit> <path>`, which discards work without a `--`.

    GS-5 keyed on a literal `--`, so `git checkout HEAD t.txt` was silent while
    `git checkout -- t.txt` warned. Verified against a real repository: the first form
    really does overwrite the file, so the silence lost the warning on a spelling that
    is just as destructive.

    THE FALSE-POSITIVE RISK IS THE WHOLE DIFFICULTY. `git checkout -b feat main` and
    `git checkout -B feat origin/main` also carry two bare words and are entirely
    harmless -- they carry changes across rather than discarding them. So a branch
    flag disqualifies the call outright, and the trailing word has to be an existing
    TRACKED path before this returns True: a start-point that merely looks like a
    filename cannot trip it.
    """
    if any(flag in rest for flag in ("-b", "-B", "--orphan", "--detach", "--track", "-t")):
        return False
    operands = [word for word in rest if not word.startswith("-")]
    if len(operands) < 2:
        return False
    return state.tracks_path(operands[-1])



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

    if subcommand == "checkout" and (
        "--" in rest or checkout_discards_a_path(rest, state)
    ):
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
    # Read BYTES and decode leniently. `sys.stdin.read()` raises UnicodeDecodeError
    # on one undecodable byte anywhere in the payload -- including in a field this
    # guard never looks at -- and the fail-open wrapper then swallowed the error, so
    # a single stray byte silenced the guard on a command it would otherwise deny.
    payload = sys.stdin.buffer.read().decode("utf-8", "replace")
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
        commands = expand_commands(command)
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

    # Resolved, matching the sibling bash guard's base_cwd. The two hooks judge the
    # same payload, so an unresolved cwd here meant a relative redirect target and a
    # symlinked path could be compared against a differently-spelled tree.
    cwd = Path(raw_cwd) if raw_cwd and Path(raw_cwd).is_dir() else Path.cwd()
    try:
        cwd = cwd.resolve()
    except OSError:
        pass

    # One RepoState PER TARGET TREE, not one for the payload cwd. Every warning here
    # is gated on repository state -- reset --hard only warns when the tree is dirty,
    # clean -f only when something untracked would go -- so reading the state of the
    # wrong repository silently drops the warning. `git -C <dirty> reset --hard` run
    # from a clean tree reported nothing at all.
    #
    # Cached by resolved path, because two invocations in one command line usually
    # name the same tree and each RepoState costs git subprocesses.
    states: dict[Path, RepoState] = {}

    for words, invocation in destructive:
        target = redirect_target(words, cwd)
        if target not in states:
            states[target] = RepoState(target)
        finding = judge(invocation, states[target])
        if finding:
            emit(finding[0], finding[1])
            return 0
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
