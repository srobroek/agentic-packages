"""Fuzz the command-position lexer against the five known bypass classes.

The rm -rf guard collected one bypass apiece for wrapper prefixes, env
assignments, leading tabs, path traversal, and trailing quotes -- each found by
fuzzing AFTER the guard shipped, back when the tokenizer was hand-rolled in
shell. The port uses shlex, so the property to pin is that dressing a command up
in any combination of those five never moves its verb out of command position.

Corpus: the cartesian product of 6 leading forms, 5 group openers, 4 env
assignment prefixes, 8 wrappers, and 6 trailing forms -- 5,760 spellings per base
command. Every one must reach the same verb as the plain form.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bash-safety-guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("bash_safety_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()

WRAPPERS = ("", "sudo ", "env ", "command ", "nice ", "timeout 5 ", "nohup ", "xargs ")
ASSIGNMENTS = ("", "FOO=bar ", "A=1 B=2 ", "PATH=/x:$PATH ")
LEADING = ("", " ", "\t", "\t\t", "  \t ", "\n")
OPENERS = ("", "( ", "{ ", "if true; then ", "while true; do ")
TRAILING = ("", " ", ";", " ;", " # comment", "\n")

DANGEROUS = (
    "rm -rf /",
    "rm -rf ~",
    "rm -rf $HOME",
    "rm -fr /",
    "rm --recursive --force /",
)

# Quoted prose naming a dangerous command. The verb belongs to echo/grep, and a
# guard that reads it as an rm is worse than useless: it teaches the agent to work
# around the guard.
BENIGN = (
    "ls -la",
    "git status",
    "echo 'rm -rf /'",
    'echo "rm -rf /"',
    "grep -r 'rm -rf /' .",
    "git commit -m 'do not rm -rf /'",
)


def dressed(base: str):
    for lead, opener, assign, wrapper, trail in itertools.product(
        LEADING, OPENERS, ASSIGNMENTS, WRAPPERS, TRAILING
    ):
        yield f"{lead}{opener}{assign}{wrapper}{base}{trail}"


def verbs(command: str) -> list[str]:
    """The verb of every command position, after prefix stripping."""
    try:
        commands = guard.expand_commands(command)
    except ValueError:
        # An unterminated quote is not parseable as shell; the guard documents
        # that as nothing to judge rather than something to guess at.
        return []
    found = []
    for words in commands:
        stripped = guard.strip_prefix(words)
        if stripped:
            found.append(Path(stripped[0]).name)
    return found


@pytest.mark.parametrize("base", DANGEROUS)
def test_no_dressing_hides_the_verb(base: str):
    """5,760 spellings per base; the verb must stay in command position in all."""
    checked = 0
    for variant in dressed(base):
        checked += 1
        assert "rm" in verbs(variant), f"dressing hid the verb: {variant!r}"
    assert checked == (
        len(LEADING) * len(OPENERS) * len(ASSIGNMENTS) * len(WRAPPERS) * len(TRAILING)
    )


@pytest.mark.parametrize("base", BENIGN)
def test_no_dressing_invents_a_verb(base: str):
    """The false-positive half: quoted prose stays an argument."""
    for variant in dressed(base):
        assert "rm" not in verbs(variant), f"dressing invented a verb: {variant!r}"


# Paths that look like shell syntax or like git options, which a hand-rolled
# tokenizer historically mis-split.
HOSTILE_TARGETS = (
    "/tmp/a b",
    "/tmp/a\tb",
    "/tmp/--force",
    "/tmp/-rf",
    "/tmp/$(whoami)",
    "/tmp/`id`",
    "/tmp/a;b",
    "/tmp/a|b",
    "/tmp/a&b",
    "/tmp/../../etc",
    "/tmp/ünï",
    "/tmp/" + "x" * 2000,
    "/tmp/a#b",
    "/tmp/a'b",
)


@pytest.mark.parametrize("target", HOSTILE_TARGETS)
def test_a_hostile_target_never_crashes_the_lexer(target: str):
    for template in ("rm -rf {}", 'rm -rf "{}"', "rm -rf '{}'", "sudo rm -rf {}"):
        command = template.format(target)
        try:
            result = verbs(command)
        except Exception as error:  # noqa: BLE001 -- any raise is the defect
            pytest.fail(f"{command!r} raised {error!r}")
        assert isinstance(result, list)


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf 'unterminated",
        'rm -rf "unterminated',
        "rm -rf \\",
        "$(rm -rf /)",
        "`rm -rf /`",
        "rm -rf / &",
        "sh -c 'rm -rf /'",
        "sh -ec 'rm -rf /'",
        "eval rm -rf /",
        "bash -c \"sh -c 'rm -rf /'\"",
    ],
)
def test_pathological_forms_are_judged_or_declined_but_never_crash(command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
    )
    assert result.returncode in (0, 2), result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert '"ask"' not in result.stdout


@pytest.mark.parametrize(
    "command,expected",
    [
        ("sh -c 'rm -rf /'", "deny"),
        ("bash -c 'rm -rf $HOME'", "deny"),
        ("eval rm -rf /", "deny"),
        ("\tsudo FOO=1 rm -rf /", "deny"),
        ("( rm -rf ~ )", "deny"),
    ],
)
def test_nested_and_dressed_forms_still_deny_end_to_end(command: str, expected: str):
    """Verb position is necessary but not sufficient -- assert the real decision."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
    )
    assert result.stdout.strip(), f"{command!r} produced no decision"
    decision = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
    assert decision == expected, f"{command!r} -> {decision}"
