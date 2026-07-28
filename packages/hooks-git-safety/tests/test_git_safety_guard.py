"""Coverage for the git safety guard.

The guard's value is in what it stays quiet about. Almost every git operation is
reflog-recoverable, so a warning on `branch -D` or on a clean-tree `reset --hard`
is noise that teaches the agent to skip the real ones. Most cases here assert
silence.

Each warning is gated on repository state, so the fixtures build real repositories
in three shapes: clean, dirty (tracked changes), and untracked-only. The
distinction between the last two is load-bearing: `-uno` means an untracked-only
tree is clean as far as `reset --hard` is concerned, while `clean -f` would still
delete something.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "git-safety-guard.py"


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "HOME": str(repo),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        },
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A committed repository with a clean working tree."""
    work = tmp_path / "repo"
    work.mkdir()
    git(work, "init", "-q")
    git(work, "config", "user.email", "test@example.test")
    git(work, "config", "user.name", "test")
    git(work, "config", "commit.gpgsign", "false")
    (work / "tracked.txt").write_text("original\n")
    git(work, "add", "tracked.txt")
    git(work, "commit", "-qm", "initial")
    return work


@pytest.fixture
def dirty_repo(repo: Path) -> Path:
    """Tracked file modified, so a reset or checkout would lose work."""
    (repo / "tracked.txt").write_text("modified\n")
    return repo


@pytest.fixture
def untracked_repo(repo: Path) -> Path:
    """Only untracked files, which `-uno` reports as clean."""
    (repo / "scratch.txt").write_text("new\n")
    return repo


def run(command: str, cwd: Path, *, as_string: bool = False) -> tuple[int, dict | None]:
    tool_input = command if as_string else {"command": command}
    payload = json.dumps({"cwd": str(cwd), "tool_name": "Bash", "tool_input": tool_input})
    result = subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, timeout=30
    )
    decision = json.loads(result.stdout)["hookSpecificOutput"] if result.stdout.strip() else None
    return result.returncode, decision


def verdict(command: str, cwd: Path) -> str:
    _, decision = run(command, cwd)
    return "silent" if decision is None else decision["permissionDecision"]


# --- GS-2: a target the guard cannot resolve -----------------------------------


@pytest.mark.parametrize(
    "command",
    [
        pytest.param('git -C "$DIR" reset --hard', id="dash-C-variable"),
        pytest.param("git --git-dir=$D/.git reset --hard", id="git-dir-variable"),
        pytest.param("git --work-tree=~/wt checkout -- .", id="work-tree-tilde"),
        pytest.param("git -C 'sp $D' clean -fd", id="quoted-path-with-variable"),
    ],
)
def test_unresolvable_target_is_denied(command: str, repo: Path) -> None:
    """A destructive op aimed at an unknown tree cannot be verified, so it blocks."""
    code, decision = run(command, repo)
    assert code == 0, "the decision travels in JSON, never in the exit code"
    assert decision is not None
    assert decision["permissionDecision"] == "deny"
    assert "GS-2" in decision["permissionDecisionReason"]


def test_literal_redirect_is_allowed(repo: Path) -> None:
    """A resolvable path is verifiable, so it is judged on state like any other."""
    assert verdict(f"git -C {repo} status", repo) == "silent"


# --- GS-3 / GS-5 / GS-6: warn only when work would actually be lost ------------


def test_reset_hard_warns_on_a_dirty_tree(dirty_repo: Path) -> None:
    _, decision = run("git reset --hard HEAD~1", dirty_repo)
    assert decision is not None
    assert decision["permissionDecision"] == "allow"
    assert "GS-3" in decision["additionalContext"]


def test_reset_hard_is_silent_on_a_clean_tree(repo: Path) -> None:
    assert verdict("git reset --hard HEAD~1", repo) == "silent"


def test_reset_hard_is_silent_with_only_untracked_files(untracked_repo: Path) -> None:
    """`-uno` excludes untracked files: a reset would not touch them."""
    assert verdict("git reset --hard", untracked_repo) == "silent"


def test_checkout_double_dash_warns_on_a_dirty_tree(dirty_repo: Path) -> None:
    _, decision = run("git checkout -- tracked.txt", dirty_repo)
    assert decision is not None
    assert "GS-5" in decision["additionalContext"]


def test_checkout_a_branch_is_silent(dirty_repo: Path) -> None:
    """Switching branches discards nothing, so only the `--` form is judged."""
    assert verdict("git checkout main", dirty_repo) == "silent"


def test_restore_warns_on_a_dirty_tree(dirty_repo: Path) -> None:
    _, decision = run("git restore tracked.txt", dirty_repo)
    assert decision is not None
    assert "GS-5" in decision["additionalContext"]


def test_restore_staged_only_is_silent(dirty_repo: Path) -> None:
    """`--staged` unstages and leaves the working tree alone, so it is reversible."""
    assert verdict("git restore --staged tracked.txt", dirty_repo) == "silent"


def test_restore_staged_and_worktree_warns(dirty_repo: Path) -> None:
    """`--worktree` puts the working tree back in scope."""
    _, decision = run("git restore --staged --worktree tracked.txt", dirty_repo)
    assert decision is not None
    assert "GS-5" in decision["additionalContext"]


def test_clean_force_warns_when_untracked_files_exist(untracked_repo: Path) -> None:
    _, decision = run("git clean -fd", untracked_repo)
    assert decision is not None
    assert "GS-6" in decision["additionalContext"]


def test_clean_force_is_silent_with_nothing_to_delete(repo: Path) -> None:
    assert verdict("git clean -fd", repo) == "silent"


def test_clean_dry_run_is_silent(untracked_repo: Path) -> None:
    """`clean -nd` only lists, so there is nothing to warn about."""
    assert verdict("git clean -nd", untracked_repo) == "silent"


# --- GS-4: force push always warns --------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("git push --force origin main", id="force"),
        pytest.param("git push -f origin main", id="short-force"),
        pytest.param("git push --force-with-lease origin main", id="force-with-lease"),
    ],
)
def test_force_push_always_warns(command: str, repo: Path) -> None:
    """The loss would be on the remote, which local state cannot report on."""
    _, decision = run(command, repo)
    assert decision is not None
    assert decision["permissionDecision"] == "allow"
    assert "GS-4" in decision["additionalContext"]


def test_plain_push_is_silent(repo: Path) -> None:
    assert verdict("git push origin main", repo) == "silent"


# --- reflog-recoverable operations stay silent --------------------------------


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("git branch -D feature", id="branch-delete"),
        pytest.param("git tag -d v1.0.0", id="tag-delete"),
        pytest.param("git stash drop", id="stash-drop"),
        pytest.param("git stash clear", id="stash-clear"),
        pytest.param("git worktree remove --force wt", id="worktree-remove"),
        pytest.param("git reset --soft HEAD~1", id="reset-soft"),
        pytest.param("git reset HEAD~1", id="reset-mixed"),
        pytest.param("git status --short", id="status"),
        pytest.param("git log --oneline", id="log"),
        pytest.param("rg --files | head -5", id="not-git-at-all"),
    ],
)
def test_recoverable_and_read_only_commands_are_silent(command: str, dirty_repo: Path) -> None:
    assert verdict(command, dirty_repo) == "silent", f"unexpected finding on: {command!r}"


# --- structure: the verb must be found wherever it sits -----------------------


def test_global_options_do_not_hide_the_subcommand(dirty_repo: Path) -> None:
    """`git -c key=v reset --hard` still resolves `reset`, not `-c`."""
    _, decision = run("git -c core.pager=cat reset --hard", dirty_repo)
    assert decision is not None
    assert "GS-3" in decision["additionalContext"]


def test_second_command_in_a_chain_is_judged(dirty_repo: Path) -> None:
    _, decision = run("echo hi && git reset --hard", dirty_repo)
    assert decision is not None
    assert "GS-3" in decision["additionalContext"]


def test_quoted_prose_is_not_a_command(dirty_repo: Path) -> None:
    """The same text inside an argument stays an argument."""
    assert verdict('git commit -m "do not git reset --hard here"', dirty_repo) == "silent"


def test_string_form_tool_input_is_read(dirty_repo: Path) -> None:
    """A bare-string tool_input must not silently bypass the guard."""
    _, decision = run("git reset --hard", dirty_repo, as_string=True)
    assert decision is not None
    assert "GS-3" in decision["additionalContext"]


# --- never block on an inconclusive read -------------------------------------


def test_unreadable_state_warns_rather_than_staying_silent(tmp_path: Path) -> None:
    """Outside a repository the guard cannot confirm a clean tree, so it speaks.

    Not being able to prove a loss is exactly when the agent should look, and the
    cost of being wrong is one advisory rather than a block.
    """
    _, decision = run("git reset --hard", tmp_path)
    assert decision is not None
    assert decision["permissionDecision"] == "allow"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json", id="malformed"),
        pytest.param('{"tool_input": {"command": "git reset \'unterminated"}}', id="unparsable"),
    ],
)
def test_inconclusive_payload_fails_open(payload: str) -> None:
    result = subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0
    assert not result.stdout.strip()


def test_never_emits_ask(dirty_repo: Path) -> None:
    """`ask` waits for a human, which stalls an autonomous run."""
    for command in ("git reset --hard", "git push --force", 'git -C "$D" clean -fd'):
        _, decision = run(command, dirty_repo)
        if decision is not None:
            assert decision["permissionDecision"] != "ask"
