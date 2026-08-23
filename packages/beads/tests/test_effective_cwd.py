"""Coverage for `effective_cwd`, which decides WHICH repository a guard judges.

A guard that resolves beads state against the session directory instead of the
directory the command runs in judges the wrong repository, and the failure is not
theoretical: a live `gh pr create` for a repo with no beads workspace was blocked
by the merge-bead guard, which demanded a bead that repo could not have. An agent
reading that message would reasonably try to create one there, which is worse than
the block.

So the contract has two halves. Resolve the directory when the command names one
plainly, and return "" -- unknown, do not judge -- when shell expansion puts it out
of reach. `beads_active("")` is False, so unknown makes every caller stand down.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import beads_hooks  # noqa: E402


SESSION = "/tmp"


@pytest.fixture
def target(tmp_path: Path) -> str:
    """A real directory that is not the session directory."""
    directory = tmp_path / "other-repo"
    directory.mkdir()
    return os.path.realpath(str(directory))


@pytest.mark.parametrize(
    "template",
    [
        "cd {t} && gh pr create",
        "cd {t} && timeout 200 gh pr create",
        "cd {t}; gh pr create",
        "cd -- {t} && gh pr create",
        "cd '{t}' && gh pr create",
        "{{ cd {t}\ngh pr create\n}} > /tmp/out",
        "( cd {t} && gh pr create )",
    ],
)
def test_a_plainly_named_directory_resolves(template: str, target: str) -> None:
    """`;` and a newline separate commands as surely as `&&` does.

    `shlex.split` treats neither as a separator, so `cd /x; gh` lexed the path and
    the semicolon as one token and the `cd` prefix went unseen.
    """
    command = template.format(t=target)
    assert beads_hooks.effective_cwd(command, SESSION) == target


@pytest.mark.parametrize(
    "command",
    [
        "cd $(cat /tmp/path.txt) && gh pr create",
        "cd `cat /tmp/path.txt` && gh pr create",
        'cd "$HOME/repo" && gh pr create',
        "cd /tmp/*/repo && gh pr create",
        "{ cd $(cat /tmp/path.txt)\ngh pr create\n} > /tmp/out",
    ],
)
def test_expansion_the_hook_cannot_perform_is_unknown(command: str) -> None:
    """Substitution, a variable and a glob name a real directory unknowably.

    Answering with the session directory would have a caller judge a repository the
    command never touched, so the answer is "" and the caller stands down.
    """
    assert beads_hooks.effective_cwd(command, SESSION) == ""


def test_a_directory_that_does_not_exist_is_unknown() -> None:
    assert beads_hooks.effective_cwd("cd /nonexistent-xyz && gh pr create", SESSION) == ""


def test_an_unreadable_command_is_unknown() -> None:
    """An unbalanced quote means the command cannot be read at all."""
    assert beads_hooks.effective_cwd('cd "unterminated && gh pr create', SESSION) == ""


@pytest.mark.parametrize(
    "command",
    [
        "gh pr create",
        "cd && gh pr create",
        "cd - && gh pr create",
    ],
)
def test_no_usable_cd_prefix_keeps_the_session_directory(command: str) -> None:
    """Absent or argument-less `cd` is not uncertainty: the session is correct."""
    assert beads_hooks.effective_cwd(command, SESSION) == SESSION


def test_beads_active_treats_unknown_as_not_active() -> None:
    """The half that makes "" safe.

    Were this to fall back to the current process, a guard would judge the
    session's repository -- exactly the bug the "" return exists to prevent.
    """
    assert beads_hooks.beads_active("") is False
