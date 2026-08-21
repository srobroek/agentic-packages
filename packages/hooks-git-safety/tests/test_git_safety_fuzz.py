"""Fuzz the git-safety command-position lexer.

GS-2 is this guard's only DENY: a destructive op aimed at another working tree
through an unexpanded variable or `~`, where the guard cannot say which tree
would be hit. It was reachable only through the outermost command, so passing the
same op through `eval` or `sh -c` bypassed it silently.

Corpus: the five bypass classes the shell-era guards each collected a bug for --
wrapper prefixes, env assignments, leading tabs, group openers, trailing forms --
crossed into 5,760 spellings per base command, in both directions. A dressed-up
destructive op must still be found; quoted prose naming one must not be.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "git-safety-guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("git_safety_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()

WRAPPERS = ("", "sudo ", "env ", "command ", "nice ", "timeout 5 ", "nohup ", "xargs ")
ASSIGNMENTS = ("", "FOO=bar ", "A=1 B=2 ", "GIT_DIR=/x ")
LEADING = ("", " ", "\t", "\t\t", "  \t ", "\n")
OPENERS = ("", "( ", "{ ", "if true; then ", "while true; do ")
TRAILING = ("", " ", ";", " ;", " # comment", "\n")

DESTRUCTIVE = (
    "git reset --hard HEAD",
    "git clean -fdx",
    "git checkout -- .",
    "git push --force origin main",
)

BENIGN = (
    "git status",
    "git log --oneline",
    "echo 'git reset --hard'",
    "git commit -m 'never git reset --hard'",
)


def dressed(base: str):
    for lead, opener, assign, wrapper, trail in itertools.product(
        LEADING, OPENERS, ASSIGNMENTS, WRAPPERS, TRAILING
    ):
        yield f"{lead}{opener}{assign}{wrapper}{base}{trail}"


def subcommands(command: str) -> list[str]:
    """The git subcommand found at every command position."""
    try:
        commands = guard.expand_commands(command)
    except ValueError:
        return []
    found = []
    for words in commands:
        invocation = guard.git_invocation(words)
        if invocation:
            found.append(invocation[0])
    return found


@pytest.mark.parametrize("base", DESTRUCTIVE)
def test_no_dressing_hides_the_git_subcommand(base: str):
    want = base.split()[1]
    checked = 0
    for variant in dressed(base):
        checked += 1
        assert want in subcommands(variant), f"dressing hid {want}: {variant!r}"
    assert checked == (
        len(LEADING) * len(OPENERS) * len(ASSIGNMENTS) * len(WRAPPERS) * len(TRAILING)
    )


@pytest.mark.parametrize("base", BENIGN)
def test_no_dressing_invents_a_destructive_subcommand(base: str):
    for variant in dressed(base):
        for name in subcommands(variant):
            assert name not in guard.DESTRUCTIVE_SUBCOMMANDS, (
                f"dressing invented {name}: {variant!r}"
            )


def _decide(command: str) -> str:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
    )
    assert result.returncode in (0, 2), result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    if not result.stdout.strip():
        return "silent"
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize(
    "command",
    [
        "eval git -C $OTHER reset --hard",
        "sh -c 'git -C $OTHER reset --hard'",
        'bash -c "git -C $X reset --hard"',
        "eval git -C ~/other clean -fdx",
        "sh -ec 'git -C $OTHER clean -fdx'",
        "sudo eval git -C $OTHER reset --hard",
        "FOO=1 eval git -C $OTHER reset --hard",
        "\teval git -C ~/x reset --hard",
        "sudo -H sh -c 'git -C $OTHER reset --hard'",
        "timeout --preserve-status 5 sh -c 'git -C $OTHER clean -fdx'",
        "env -i sh -c 'git -C ~/x reset --hard'",
        "env -S 'git -C $OTHER reset --hard'",
        "flock -c 'git -C $OTHER reset --hard'",
    ],
)
def test_the_gs2_deny_survives_nesting(command: str):
    """Reproduction: each of these was `silent` before expand_commands re-lexed the
    nested string, while the same op spelled plainly denied."""
    assert _decide(command) == "deny", command


@pytest.mark.parametrize(
    "command",
    [
        "git -C /literal/path reset --hard",
        "eval git status",
        "echo 'git -C $OTHER reset --hard'",
        'echo "git -C $OTHER clean -fdx"',
        "echo flock -c 'git -C $OTHER reset --hard'",
        "git commit -m 'do not git -C $OTHER reset --hard'",
    ],
)
def test_a_resolvable_or_quoted_form_is_not_denied(command: str):
    """The false-positive half: GS-2 is about an UNRESOLVABLE target, and prose
    naming one is still prose."""
    assert _decide(command) != "deny", command


@pytest.mark.parametrize(
    "command",
    [
        "eval eval eval git -C $OTHER reset --hard",
        "sh -c 'sh -c \"sh -c \\'git status\\'\"'",
        "eval 'unterminated",
        "eval",
        "sh -c",
        "eval --",
        "git -C $OTHER reset --hard " + "x" * 5000,
    ],
)
def test_pathological_nesting_terminates_and_never_crashes(command: str):
    """MAX_NESTING bounds the recursion; an unparsable inner string is declined."""
    assert _decide(command) in ("deny", "allow", "silent")
