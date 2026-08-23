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
        pytest.param("git -C$DIR reset --hard", id="attached-dash-C-variable"),
        pytest.param("git -C${DIR} reset --hard", id="attached-braced-dash-C-variable"),
        pytest.param("git --git-dir=$D/.git reset --hard", id="git-dir-variable"),
        pytest.param("git --work-tree=~/wt checkout -- .", id="work-tree-tilde"),
        pytest.param("git -C 'sp $D' clean -fd", id="quoted-path-with-variable"),
        # The env-assignment spellings retarget git exactly as the flags do, and
        # were allowed while the flag form denied. This is the spelling an agent
        # reaches for when the path is already in a variable -- the case GS-2 is for.
        pytest.param("GIT_DIR=$D/.git git clean -fdx", id="env-git-dir-variable"),
        pytest.param("GIT_WORK_TREE=$D git clean -fdx", id="env-work-tree-variable"),
        pytest.param("GIT_DIR=~/other/.git git clean -fdx", id="env-git-dir-tilde"),
    ],
)
def test_unresolvable_target_is_denied(command: str, repo: Path) -> None:
    """A destructive op aimed at an unknown tree cannot be verified, so it blocks."""
    code, decision = run(command, repo)
    assert code == 0, "the decision travels in JSON, never in the exit code"
    assert decision is not None
    assert decision["permissionDecision"] == "deny"
    assert "GS-2" in decision["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("GIT_DIR=/tmp/x/.git git clean -fdx", id="env-literal-path"),
        pytest.param("GIT_DIR=$D/.git git status", id="env-variable-read-only"),
    ],
)
def test_the_env_spelling_does_not_over_deny(command: str, repo: Path) -> None:
    """Widening GS-2 to GIT_DIR= must not swallow the resolvable or the harmless.

    A literal path is verifiable, so it is not GS-2's business; and GS-2 gates
    DESTRUCTIVE ops, so a read-only `status` stays out of scope no matter how its
    target is spelled.
    """
    assert verdict(command, repo) != "deny"


def test_literal_redirect_is_allowed(repo: Path) -> None:
    """A resolvable path is verifiable, so it is judged on state like any other."""
    assert verdict(f"git -C {repo} status", repo) == "silent"


def test_a_readonly_op_elsewhere_does_not_trigger_gs2(repo: Path) -> None:
    """GS-2 applies to the destructive invocation, not to the whole command string.

    Searching the raw string denied a benign pairing, blaming a read-only `status`
    in a separate command for a tilde the destructive op never touches. A guard that
    fires on correct work is worse than no guard.
    """
    _, decision = run("git clean -fd; git -C ~/other status", repo)
    if decision is not None:
        assert decision["permissionDecision"] != "deny", (
            "a read-only op in a different command must not trigger GS-2"
        )


# --- wrapper prefixes must not defeat a denial ---------------------------------

# Each of these was silent while the bare command denied, because the prefix skip
# consumed the wrapper word but not its options, leaving `-n` or a duration where
# the verb belonged.
WRAPPED_DESTRUCTIVE = [
    pytest.param("timeout 5 ", id="timeout-with-duration"),
    pytest.param("flock /tmp/lock ", id="flock-with-lockfile"),
    pytest.param("nice -n 5 ", id="nice-with-option-value"),
    pytest.param("sudo -u me ", id="sudo-with-user"),
    pytest.param("xargs -n1 ", id="xargs-with-option"),
    pytest.param("unbuffer ", id="unbuffer"),
    pytest.param("stdbuf -o0 ", id="stdbuf-with-option"),
    pytest.param("env FOO=1 ", id="env-assignment"),
    pytest.param("nohup ", id="nohup"),
]


@pytest.mark.parametrize("prefix", WRAPPED_DESTRUCTIVE)
def test_a_wrapper_prefix_does_not_defeat_the_denial(prefix: str, repo: Path) -> None:
    _, decision = run(f'{prefix}git -C "$DIR" reset --hard', repo)
    assert decision is not None, f"no decision for wrapper prefix {prefix!r}"
    assert decision["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "prefix",
    [
        pytest.param("sudo -H ", id="sudo-flag"),
        pytest.param("env -i ", id="env-flag"),
        pytest.param("timeout --preserve-status 5 ", id="timeout-flag"),
        pytest.param("flock --nonblock /tmp/lock ", id="flock-flag"),
        pytest.param("nice -v ", id="nice-flag"),
        pytest.param("xargs -r ", id="xargs-flag"),
    ],
)
def test_wrapper_flags_do_not_hide_a_plain_destructive_call(prefix: str, dirty_repo: Path) -> None:
    """Wrapper flags are not option values, so the following git remains in command position."""
    _, decision = run(f"{prefix}git reset --hard", dirty_repo)
    assert decision is not None, f"no decision for wrapper prefix {prefix!r}"
    assert "GS-3" in decision["additionalContext"]


@pytest.mark.parametrize(
    "command",
    [
        pytest.param('sudo -u root -- git -C "$D" reset --hard', id="option-value-then-dashdash"),
        pytest.param('nice -n 5 -- git -C "$D" clean -fd', id="nice-then-dashdash"),
        pytest.param('sudo -- git -C "$D" reset --hard', id="bare-dashdash"),
        pytest.param('/usr/bin/sudo git -C "$D" reset --hard', id="absolute-path-wrapper"),
    ],
)
def test_a_dashdash_or_absolute_wrapper_does_not_hide_the_git_call(command: str, repo: Path) -> None:
    """Two shared defects with the bash guard, fixed in both.

    `--` ends the wrapper's options, but the option-value lookahead consumed it and
    then the `git` behind it, so the invocation was discarded before any rule ran.
    And WRAPPERS was matched against the raw word, so an absolute path defeated the
    set entirely.
    """
    assert verdict(command, repo) == "deny", f"{command!r} hid the git call"


def test_a_line_continuation_keeps_one_command_together(repo: Path) -> None:
    """A backslash-newline is a continuation, not a separator.

    Without the rewrite the two halves became separate commands, so
    `git reset \\<newline>--hard` lost its own flag and every rule with it. The bash
    guard already did this; the git guard did not.
    """
    assert verdict('git -C "$D" reset \\\n--hard', repo) == "deny"


def test_a_comment_does_not_swallow_the_following_line(repo: Path) -> None:
    """shlex read `#` as a comment and discarded the rest of the STRING.

    The newline went with it, so a git call on the next line vanished -- verified
    against bash that the second line really does execute.
    """
    assert verdict('ls -la # list\ngit -C "$D" reset --hard', repo) == "deny"
    assert verdict('git commit -m "fix #123"', repo) != "deny", "a # inside quotes is data"


# --- the redirect target decides which repository is judged -------------------


@pytest.fixture
def other_dirty_repo(tmp_path: Path) -> Path:
    """A SECOND repository, dirty, distinct from the fixture the payload cwd names."""
    work = tmp_path / "other"
    work.mkdir()
    git(work, "init", "-q")
    git(work, "config", "user.email", "test@example.test")
    git(work, "config", "user.name", "test")
    git(work, "config", "commit.gpgsign", "false")
    (work / "tracked.txt").write_text("original\n")
    git(work, "add", "tracked.txt")
    git(work, "commit", "-qm", "initial")
    (work / "tracked.txt").write_text("modified\n")
    return work


@pytest.mark.parametrize(
    "template",
    [
        pytest.param("git -C {t} reset --hard", id="dash-C"),
        pytest.param("git --work-tree={t} reset --hard", id="work-tree-equals"),
        pytest.param("git --git-dir={t}/.git reset --hard", id="git-dir-equals"),
        pytest.param("GIT_WORK_TREE={t} git reset --hard", id="env-work-tree"),
        pytest.param("GIT_DIR={t}/.git git reset --hard", id="env-git-dir"),
    ],
)
def test_state_is_read_from_the_tree_git_actually_acts_on(
    template: str, repo: Path, other_dirty_repo: Path
) -> None:
    """Every warning here is gated on repository state, so reading the WRONG repo's
    state silently drops the warning.

    The redirect value was parsed and thrown away, and RepoState was built from the
    payload cwd alone. So a `reset --hard` aimed at a dirty tree from a CLEAN one
    reported nothing -- the destructive case the rule exists for.
    """
    command = template.format(t=other_dirty_repo)
    _, decision = run(command, repo)
    assert decision is not None, f"{command!r} lost the warning entirely"
    assert "GS-3" in (decision.get("additionalContext") or ""), f"{command!r} missed GS-3"


def test_a_redirect_to_a_clean_tree_stays_quiet(repo: Path, tmp_path: Path) -> None:
    """The converse: resolving the target must not invent a warning.

    A clean target has nothing to lose, so pointing at it is not worth a word --
    otherwise the rule fires on correct work and gets ignored.
    """
    other = tmp_path / "clean-other"
    other.mkdir()
    git(other, "init", "-q")
    git(other, "config", "user.email", "test@example.test")
    git(other, "config", "user.name", "test")
    git(other, "config", "commit.gpgsign", "false")
    (other / "t.txt").write_text("a\n")
    git(other, "add", "t.txt")
    git(other, "commit", "-qm", "i")
    assert verdict(f"git -C {other} reset --hard", repo) == "silent"


def test_an_unresolvable_redirect_still_denies_rather_than_resolving(repo: Path) -> None:
    """GS-2 outranks target resolution.

    A target behind a variable cannot be resolved, and guessing could only move the
    warning onto the wrong repository, so the deny has to win.
    """
    assert verdict('git -C "$DIR" reset --hard', repo) == "deny"
    assert verdict("GIT_DIR=$D/.git git clean -fdx", repo) == "deny"


def test_checkout_without_dashdash_still_warns_when_it_discards(dirty_repo: Path) -> None:
    """GS-5 keyed on a literal `--`, so `git checkout HEAD t.txt` was silent.

    Verified against a real repository: that form really does overwrite the file, so
    the silence lost the warning on a spelling as destructive as the one that warned.
    """
    for spelling in (
        "git checkout -- tracked.txt",
        "git checkout HEAD tracked.txt",
        "git checkout HEAD -- tracked.txt",
    ):
        _, decision = run(spelling, dirty_repo)
        assert decision is not None, f"{spelling!r} lost the warning"
        assert "GS-5" in (decision.get("additionalContext") or ""), f"{spelling!r} missed GS-5"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("git checkout -b feat main", id="new-branch-from-start-point"),
        pytest.param("git checkout -B feat origin/main", id="force-branch-from-start-point"),
        pytest.param("git checkout main", id="switch-branch"),
        pytest.param("git checkout --detach HEAD", id="detach"),
    ],
)
def test_branch_operations_are_not_mistaken_for_discarding_a_path(
    command: str, dirty_repo: Path
) -> None:
    """This is the whole difficulty of the fix above.

    `git checkout -b feat main` carries two bare words exactly as the destructive
    form does, and it CARRIES changes across rather than discarding them. A branch
    flag disqualifies the call, and the trailing word must be an existing tracked
    path -- a start-point that merely looks like a filename cannot trip it.
    """
    assert verdict(command, dirty_repo) == "silent", f"{command!r} is harmless"


def test_a_literal_tilde_mid_path_is_not_treated_as_a_home_reference(repo: Path) -> None:
    """`~` means home only at the START of a value; mid-path it is an ordinary
    character.

    `/tmp/has~tilde/x` is a real directory name, and denying it was a false positive
    on a path the guard could resolve perfectly well. A guard that fires on correct
    work gets ignored, so the over-deny matters as much as a miss.
    """
    for literal in ("git -C /tmp/has~tilde/x reset --hard", "git -C /tmp/a~b clean -fd"):
        assert verdict(literal, repo) != "deny", f"{literal!r} names a literal path"
    for home in ('git -C ~/other reset --hard', 'git -C "~/other" clean -fd'):
        assert verdict(home, repo) == "deny", f"{home!r} is an unresolvable home reference"
    assert verdict("git -C /tmp/$X reset --hard", repo) == "deny", "a variable anywhere still denies"


def test_an_outsized_command_does_not_stall_the_hook(repo: Path) -> None:
    """UNVERIFIABLE_REDIRECT degrades badly on one long token, and this hook has a
    10s budget in hooks.json.

    Measured before the cap: 200KB 614ms, 500KB 2.7s, 2MB past 25s -- a padded
    argument was a stall rather than a parse. Padding must not buy silence either,
    since the verb and its flags sit at the front of the string.
    """
    import time

    start = time.monotonic()
    verdict('git -C "' + "a" * 2_000_000 + '" reset --hard', repo)
    assert time.monotonic() - start < 5.0, "a padded command still stalls the hook"

    padded = 'git -C "$D" reset --hard # ' + "a" * 200_000
    assert verdict(padded, repo) == "deny", "padding hid a GS-2 target"


def test_the_subprocess_timeout_fits_inside_the_hook_budget() -> None:
    """A 10s subprocess timeout inside a 10s hook budget meant one stalled git call
    consumed the whole allowance, the runtime killed the hook, and the warning was
    lost rather than late. Up to three calls may run for one decision.
    """
    import json as _json

    sys.path.insert(0, str(GUARD.parent))
    source = GUARD.read_text(encoding="utf-8")
    assert "GIT_SUBPROCESS_TIMEOUT" in source, "the timeout is not named"

    budget = _json.loads((GUARD.parent.parent / "hooks" / "hooks.json").read_text())
    declared = _json.dumps(budget)
    assert '"timeout": 10' in declared, "hook budget changed; revisit the subprocess bound"

    import re as _re

    value = int(_re.search(r"GIT_SUBPROCESS_TIMEOUT = (\d+)", source).group(1))
    assert value * 3 <= 10, f"three calls at {value}s each can exceed the 10s budget"


def test_a_non_string_cwd_fails_open() -> None:
    """The contract requires fail-open; this raised TypeError and exited 1."""
    payload = json.dumps({"cwd": ["/tmp"], "tool_input": {"command": "git status"}})
    result = subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, f"must not fail closed: {result.stderr}"


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


@pytest.fixture
def ignored_repo(repo: Path) -> Path:
    """Tracked ignore rule plus an ignored file, which `clean -x` deletes."""
    (repo / ".gitignore").write_text("build/\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-qm", "ignore build output")
    (repo / "build").mkdir()
    (repo / "build" / "out.txt").write_text("generated\n")
    return repo


@pytest.mark.parametrize("flag", ["-fdx", "-fdX"])
def test_clean_force_warns_when_ignored_files_exist(ignored_repo: Path, flag: str) -> None:
    _, decision = run(f"git clean {flag}", ignored_repo)
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


def test_force_push_in_a_short_option_bundle_always_warns(repo: Path) -> None:
    _, decision = run("git push -fu origin main", repo)
    assert decision is not None
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


def test_literal_c_redirect_uses_the_target_repository_state(repo: Path, tmp_path: Path) -> None:
    """A literal redirect is verifiable, so state must come from that tree, not outer cwd."""
    target = tmp_path / "target"
    target.mkdir()
    git(target, "init", "-q")
    git(target, "config", "user.email", "test@example.test")
    git(target, "config", "user.name", "test")
    git(target, "config", "commit.gpgsign", "false")
    (target / "tracked.txt").write_text("original\n")
    git(target, "add", "tracked.txt")
    git(target, "commit", "-qm", "initial")

    (repo / "tracked.txt").write_text("outer dirty\n")
    assert verdict(f"git -C {target} reset --hard", repo) == "silent"

    (target / "tracked.txt").write_text("target dirty\n")
    _, decision = run(f"git -C {target} reset --hard", repo)
    assert decision is not None
    assert "GS-3" in decision["additionalContext"]


def test_literal_git_environment_redirect_uses_the_target_repository_state(
    repo: Path, tmp_path: Path
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    git(target, "init", "-q")
    git(target, "config", "user.email", "test@example.test")
    git(target, "config", "user.name", "test")
    git(target, "config", "commit.gpgsign", "false")
    (target / "tracked.txt").write_text("original\n")
    git(target, "add", "tracked.txt")
    git(target, "commit", "-qm", "initial")
    (target / "tracked.txt").write_text("target dirty\n")

    command = f"GIT_DIR={target}/.git GIT_WORK_TREE={target} git reset --hard"
    _, decision = run(command, repo)
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


# --- the effective repository is the command's, not the session's ---------------


def test_a_cd_prefix_moves_the_state_read_to_the_named_repo(
    repo: Path, dirty_repo: Path
) -> None:
    """`cd <dirty> && git reset --hard` warns even though the session repo is clean."""
    clean = repo.parent / "clean"
    subprocess.run(["cp", "-R", str(repo), str(clean)], check=True, capture_output=True)
    git(clean, "checkout", "--", "tracked.txt")
    assert verdict(f"cd {dirty_repo} && git reset --hard", clean) == "allow"


def test_a_cd_prefix_silences_a_clean_repo_the_session_cannot_see(
    repo: Path, dirty_repo: Path, tmp_path: Path
) -> None:
    """The session repo being dirty must not warn about a clean repo the cd names."""
    clean = tmp_path / "elsewhere"
    clean.mkdir()
    git(clean, "init", "-q")
    git(clean, "config", "user.email", "test@example.test")
    git(clean, "config", "user.name", "test")
    git(clean, "config", "commit.gpgsign", "false")
    (clean / "f.txt").write_text("x\n")
    git(clean, "add", "f.txt")
    git(clean, "commit", "-qm", "initial")
    assert verdict(f"cd {clean} && git reset --hard", dirty_repo) == "silent"


@pytest.mark.parametrize(
    "prefix",
    [
        pytest.param("cd $TARGET", id="variable"),
        pytest.param("cd $(cat p)", id="substitution"),
        pytest.param("cd /nonexistent-xyz-123", id="missing-directory"),
        pytest.param("cd /tmp /var", id="two-operands"),
    ],
)
def test_an_unresolvable_cd_stands_down(prefix: str, dirty_repo: Path) -> None:
    """An unresolvable cd must not fall back to judging the session repository."""
    assert verdict(f"{prefix} && git reset --hard", dirty_repo) == "silent"


@pytest.mark.parametrize(
    "prefix",
    [
        pytest.param("cd", id="bare-cd-goes-home"),
        pytest.param("cd -", id="cd-dash-goes-back"),
    ],
)
def test_a_cd_naming_no_path_keeps_the_session_repo(prefix: str, dirty_repo: Path) -> None:
    assert verdict(f"{prefix} && git reset --hard", dirty_repo) == "allow"


def test_a_literal_dash_C_is_honoured_while_a_variable_one_is_refused(
    repo: Path, dirty_repo: Path
) -> None:
    """GS-2 must keep denying an unresolvable `-C`, and only that spelling."""
    assert verdict(f'git -C "{dirty_repo}" reset --hard', repo) == "allow"
    assert verdict("git -C $D reset --hard", repo) == "deny"
