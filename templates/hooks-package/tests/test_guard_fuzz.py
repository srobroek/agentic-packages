"""Fuzz the hooks-package TEMPLATE guard against the five known bypass classes.

Every new hooks package is copied from this file, so a gap here propagates into
each guard written from it. That makes the template's matcher worth more scrutiny
than any single shipped guard.

The five classes the hook contract catalogues -- wrapper prefixes, env
assignments, leading tabs and whitespace, path traversal, trailing quotes -- were
each found by fuzzing a shipped guard AFTER it shipped. The property pinned here
is that dressing a command in any COMBINATION of them never moves its verb out of
command position, and never invents a verb that was only ever quoted prose.

Corpus: the cartesian product of 6 leading forms, 5 group openers, 4 env
assignment prefixes, 9 wrappers, and 6 trailing forms -- 6,480 spellings per base
command, checked against both a positive and a negative base set.

Nesting (`eval`, `sh -c`, `bash -c`) is pinned separately: it found bypasses in
two shipped guards, and a generator does not reach it by accident.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("guard_fuzz", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()

LEADING = ("", " ", "\t", "\t\t", "  \t ", "\n")
OPENERS = ("", "( ", "{ ", "if true; then ", "while true; do ")
ASSIGNMENTS = ("", "FOO=bar ", "A=1 B=2 ", "GIT_SSH=/x/y ")
WRAPPERS = (
    "",
    "sudo ",
    "env ",
    "command ",
    "nice ",
    "timeout 5 ",
    "nohup ",
    "sudo -u git ",
    "nice -n 19 ",
)
TRAILING = ("", " ", ";", " ;", " # comment", "\n")

CORPUS_PER_BASE = (
    len(LEADING) * len(OPENERS) * len(ASSIGNMENTS) * len(WRAPPERS) * len(TRAILING)
)

# Spellings of the gated command. Each must remain in scope however it is dressed.
GATED = (
    "git push",
    "git push origin main",
    "git push --force-with-lease",
    "/usr/bin/git push",
    "git -c user.name=x push",
    "git -C /tmp push",
    "git --git-dir=/x push",
)

# Prose and neighbours that merely MENTION the gated command. A guard that denies
# these is worse than useless: it teaches the agent to route around the guard.
BENIGN = (
    "git status",
    "git pushx",
    "git push-mirror",
    "git add push",
    "echo 'git push'",
    'echo "git push"',
    "git commit -m 'do not git push'",
    "grep -r 'git push' .",
    "git log --grep='git push'",
    "gitpush",
    "git-push",
    "mygit push",
)


def dressed(base: str):
    for lead, opener, assign, wrapper, trail in itertools.product(
        LEADING, OPENERS, ASSIGNMENTS, WRAPPERS, TRAILING
    ):
        yield f"{lead}{opener}{assign}{wrapper}{base}{trail}"


@pytest.mark.parametrize("base", GATED)
def test_no_dressing_moves_the_verb_out_of_command_position(base: str):
    checked = 0
    for variant in dressed(base):
        checked += 1
        assert guard.in_scope(variant), f"dressing hid the verb: {variant!r}"
    assert checked == CORPUS_PER_BASE


@pytest.mark.parametrize("base", BENIGN)
def test_no_dressing_invents_a_verb_from_quoted_prose(base: str):
    for variant in dressed(base):
        assert not guard.in_scope(variant), f"dressing invented a verb: {variant!r}"


# --- path traversal ----------------------------------------------------------


@pytest.mark.parametrize(
    "spelling",
    [
        "/usr/bin/git push",
        "./git push",
        "../bin/git push",
        "../../usr/bin/git push",
        "/usr/local/../bin/git push",
        "'/usr/bin/git' push",
        '"/usr/bin/git" push',
        "/usr/bin/env git push",
    ],
)
def test_a_path_spelling_of_the_verb_is_still_the_verb(spelling: str):
    """Reproduction: `in_scope` compared the raw first word, so any absolute or
    relative path to git -- the documented traversal bypass class -- was unjudged."""
    assert guard.in_scope(spelling), spelling


@pytest.mark.parametrize(
    "spelling",
    ["cat ./git/push", "ls /usr/bin/git", "echo /usr/bin/git push", "cp git push"],
)
def test_a_path_in_an_ARGUMENT_is_not_the_verb(spelling: str):
    assert not guard.in_scope(spelling), spelling


# --- operators, keywords and grouping ----------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git push;",
        "(git push)",
        "{ git push; }",
        "true && git push",
        "false || git push",
        "git push | cat",
        "cd /x && git push",
        "for i in 1 2; do git push; done",
        "if true; then git push; fi",
        "while true; do git push; done",
        "echo hello\ngit push",
        "echo hello ; git push ; echo bye",
        "git \\\n  push",
    ],
)
def test_a_verb_after_an_operator_or_keyword_is_judged(command: str):
    """Reproduction: shlex.split treated `;`, `&&` and a newline as ordinary
    whitespace, so only the FIRST command's verb was ever compared and everything
    after an operator went unjudged."""
    assert guard.in_scope(command), command


# --- nesting -----------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "sh -c 'git push'",
        "bash -c 'git push'",
        "bash -ec 'git push'",
        "zsh -c 'git push'",
        "dash -c 'git push'",
        "eval git push",
        "eval 'git push'",
        "eval \"git push\"",
        "bash -c \"sh -c 'git push'\"",
        "sudo sh -c 'git push'",
        "env FOO=1 bash -c 'git push --force'",
        "sh -c 'cd /x && git push'",
    ],
)
def test_a_verb_inside_a_nested_shell_string_is_judged(command: str):
    """Reproduction: shlex hands `sh -c 'git push'` back as ONE argument token, so
    the verb inside it never reached the comparison. This class found bypasses in
    two shipped guards, which is why the template carries the re-lexer."""
    assert guard.in_scope(command), command


@pytest.mark.parametrize(
    "command",
    [
        "sh -c 'echo \"git push\"'",
        "sh /some/script.sh",
        "bash script.sh git push",
        "eval echo git",
    ],
)
def test_nesting_does_not_invent_a_verb(command: str):
    assert not guard.in_scope(command), command


def test_nesting_deeper_than_the_bound_still_returns():
    """A payload nested past MAX_NESTING must terminate rather than recurse on.

    Twelve levels, not forty: each level re-escapes every quote below it, so the
    string doubles per level and depth 40 is ~2^40 bytes. The first draft of this
    test OOM-killed the runner, which is a defect in the harness, not the guard.
    """
    nested = "git push"
    for _ in range(guard.MAX_NESTING * 3):
        nested = f"sh -c {json.dumps(nested)}"
    assert guard.in_scope(nested) in (True, False)  # the point is that it RETURNS


def test_nesting_within_the_bound_is_judged_at_every_level():
    nested = "git push"
    for _ in range(guard.MAX_NESTING - 1):
        nested = f"sh -c {json.dumps(nested)}"
        assert guard.in_scope(nested), nested


# --- trailing quotes and unparsable input -----------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git push 'unterminated",
        'git push "unterminated',
        "git push \\",
        "'git push",
        "git push '",
        '"',
        "'",
    ],
)
def test_an_unparsable_command_fails_open(command: str):
    """Not shell, so there is nothing to judge. A guard that guessed here would
    deny on a quoting typo, and a guard that crashed would wedge the agent."""
    assert guard.in_scope(command) is False
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


# --- the contract's hard rules -----------------------------------------------

HOSTILE_PAYLOADS = (
    "",
    "not json",
    "[]",
    "null",
    "0",
    '""',
    "{}",
    '{"tool_input": 5}',
    '{"tool_input": null}',
    '{"tool_input": []}',
    '{"tool_input": "git push"}',
    '{"tool_input": {"command": null}}',
    '{"tool_input": {"command": 5}}',
    '{"tool_input": {"command": []}}',
    '{"tool_input": {"no_command": "git push"}}',
    '{"tool_name": "Bash"}',
    '{"tool_input": {"command": "git push"}, "extra": ' + "[" * 400 + "]" * 400 + "}",
    '{"tool_input": {"command": "git push ' + "x" * 100_000 + '"}}',
    '{"tool_input": {"command": "\\u0000git push"}}',
    "\x00{}",
    '{"tool_input": {"command": "git ' + "push " * 2000 + '"}}',
)


@pytest.mark.parametrize("payload", HOSTILE_PAYLOADS, ids=range(len(HOSTILE_PAYLOADS)))
def test_no_payload_produces_a_nonzero_exit_a_traceback_or_an_ask(payload: str):
    """The three absolutes: fail open, never crash, never emit `ask`."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert '"ask"' not in result.stdout
    if result.stdout.strip():
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
        assert decision["permissionDecisionReason"]


@pytest.mark.parametrize("command", GATED)
def test_a_gated_command_denies_end_to_end(command: str):
    """Verb position is necessary but not sufficient -- assert the real decision."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
    )
    assert result.stdout.strip(), f"{command!r} produced no decision"
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert output["hookEventName"] == "PreToolUse"


@pytest.mark.parametrize("command", BENIGN)
def test_a_benign_command_produces_no_decision_end_to_end(command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stdout == "", f"{command!r} was judged: {result.stdout}"


def test_the_cheap_bail_literal_is_a_superset_of_the_real_trigger():
    """The hook bails on raw stdin lacking a literal. If that literal were not a
    strict superset of every gated spelling, the bail would hide a real match."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"push" not in payload' in source
    for command in GATED:
        assert "push" in command, f"{command!r} would be hidden by the cheap bail"


def test_every_wrapper_set_member_is_also_a_wrapper():
    """Reproduction: `flock` appeared in WRAPPER_OPERAND and OPTION_TAKES_VALUE but
    NOT in WRAPPERS, so `flock /tmp/lock git push` was never stripped and the push
    behind it went unjudged. The sets have to agree or the extra entries are dead."""
    assert guard.WRAPPER_OPERAND <= guard.WRAPPERS
    assert set(guard.OPTION_TAKES_VALUE) <= guard.WRAPPERS


@pytest.mark.parametrize(
    "command",
    [
        "flock /tmp/lock git push",
        "flock -w 5 /tmp/lock git push",
        "stdbuf -oL git push",
        "setsid git push",
        "ionice -c 3 git push",
    ],
)
def test_every_declared_wrapper_is_actually_stripped(command: str):
    assert guard.in_scope(command), command
