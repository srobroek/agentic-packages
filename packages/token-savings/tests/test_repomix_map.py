"""Coverage for repomix-map.py, the structure-map refresh and injection hook.

Two behaviors carry the weight. The BUDGET gate: a map that does not fit must be
referenced rather than inlined, because injecting ~31k tokens into every session
costs more than the exploration it saves. And the DEDUPE gate: a repack is
expensive, so an unchanged HEAD must not trigger one.

The positional-argument test exists because the sibling `mcp-repomix` hook
passed `--directory`, which repomix 1.11.1 rejects outright, so it silently
never packed anything on any repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "repomix-map.py"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", "-C", str(repo_dir), *a], check=True, capture_output=True
    )
    run("init", "-q")
    run("config", "user.email", "t@example.test")
    run("config", "user.name", "t")
    run("config", "commit.gpgsign", "false")
    (repo_dir / "a.py").write_text("x = 1\n")
    run("add", "-A")
    run("commit", "-qm", "initial")
    return repo_dir


@pytest.fixture
def env(tmp_path: Path):
    """Isolated XDG state plus a stub `repomix` that records its argv."""
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    argv_log = tmp_path / "argv.log"
    stub = stub_dir / "repomix"
    # Writes a small map to whatever --output names, and logs its arguments so a
    # test can assert the directory was passed positionally.
    stub.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{argv_log}"\n'
        'out=""\n'
        'while [ $# -gt 0 ]; do\n'
        '  if [ "$1" = "--output" ]; then out="$2"; fi\n'
        '  shift\n'
        "done\n"
        'if [ -n "$out" ]; then printf "<directory_structure>\\na.py\\n</directory_structure>\\n" > "$out"; fi\n'
        "exit 0\n"
    )
    stub.chmod(0o755)

    state = tmp_path / "state"
    state.mkdir()
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_dir}{os.pathsep}{environment['PATH']}"
    environment["XDG_STATE_HOME"] = str(state)
    environment.pop("TOKEN_SAVINGS_MAP_BUDGET", None)
    return environment, argv_log, state


def _run(
    command: str,
    cwd: Path,
    environment: dict,
    extra: list[str] | None = None,
    shell_command: str = "git commit -m x",
) -> str:
    """Invoke the hook with a realistic payload.

    `refresh` is bound to PostToolUse:Bash and filters on the shell command in
    the payload, so a payload carrying only `cwd` is rejected before it does
    anything -- which is correct behavior, not a test fixture detail. The
    default names a HEAD-moving command so the refresh path is exercised;
    `shell_command` overrides it to test the filter itself.
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), command, *(extra or [])],
        input=json.dumps(
            {"cwd": str(cwd), "tool_name": "Bash", "tool_input": {"command": shell_command}}
        ),
        capture_output=True,
        text=True,
        env=environment,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _maps(state: Path) -> list[Path]:
    """Full maps only. `*-repomix-map.xml` also matches `*-scoped-repomix-map.xml`,
    so exclude the scoped ones explicitly."""
    found = (state / "agentic-tools" / "token-savings").glob("*-repomix-map.xml")
    return sorted(p for p in found if "-scoped-" not in p.name)


def test_refresh_builds_a_map(repo, env):
    environment, _, state = env
    _run("refresh", repo, environment)
    assert len(_maps(state)) == 1


def test_directory_is_passed_positionally_not_as_a_flag(repo, env):
    """`--directory` does not exist in repomix 1.11.1; passing it makes every
    pack exit non-zero and write nothing."""
    environment, argv_log, _ = env
    _run("refresh", repo, environment)
    argv = argv_log.read_text()
    assert "--directory" not in argv
    assert str(repo) in argv
    assert "--no-files" in argv


def test_map_is_written_outside_the_repository(repo, env):
    """The existing repomix.xml hook refuses unless its output is gitignored,
    and it is not gitignored in any local repo -- so it never ran. A path under
    XDG state has no such dependency and cannot dirty the tree."""
    environment, _, state = env
    _run("refresh", repo, environment)
    assert _maps(state)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    )
    assert status.stdout.strip() == ""


def test_unchanged_head_does_not_repack(repo, env):
    environment, argv_log, _ = env
    _run("refresh", repo, environment)
    first = argv_log.read_text().count("\n")
    _run("refresh", repo, environment)
    assert argv_log.read_text().count("\n") == first


def test_moved_head_repacks(repo, env):
    environment, argv_log, _ = env
    _run("refresh", repo, environment)
    first = argv_log.read_text().count("\n")
    (repo / "b.py").write_text("y = 2\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "second"], check=True, capture_output=True
    )
    _run("refresh", repo, environment)
    assert argv_log.read_text().count("\n") > first


def test_force_repacks_regardless_of_head(repo, env):
    environment, argv_log, _ = env
    _run("refresh", repo, environment)
    first = argv_log.read_text().count("\n")
    _run("refresh", repo, environment, extra=["--force"])
    assert argv_log.read_text().count("\n") > first


def test_inject_inlines_a_map_within_budget(repo, env):
    environment, _, _ = env
    _run("refresh", repo, environment)
    out = _run("inject", repo, environment)
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "<directory_structure>" in context
    assert "a.py" in context


def test_inject_references_an_oversized_map_instead_of_inlining_it(repo, env):
    """The gate that stops this costing more than it saves."""
    environment, _, _ = env
    _run("refresh", repo, environment)
    environment = dict(environment)
    environment["TOKEN_SAVINGS_MAP_BUDGET"] = "1"
    out = _run("inject", repo, environment)
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "<directory_structure>" not in context
    assert "too large to inline" in context
    assert "repomix-map.xml" in context


def test_inject_is_silent_without_a_map(repo, env):
    environment, _, _ = env
    assert _run("inject", repo, environment) == ""


def test_inject_emits_the_session_start_event_name(repo, env):
    environment, _, _ = env
    _run("refresh", repo, environment)
    emitted = json.loads(_run("inject", repo, environment))["hookSpecificOutput"]
    assert emitted["hookEventName"] == "SessionStart"
    # Claude-only fields would be silent no-ops on Codex in a target: all package.
    assert "systemMessage" not in emitted
    assert "suppressOutput" not in emitted


def test_missing_repomix_fails_open(repo, tmp_path):
    environment = dict(os.environ)
    empty = tmp_path / "empty"
    empty.mkdir()
    environment["PATH"] = str(empty)
    environment["XDG_STATE_HOME"] = str(tmp_path / "state2")
    assert _run("refresh", repo, environment) == ""


def test_outside_a_repository_is_a_noop(tmp_path, env):
    environment, _, state = env
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _run("refresh", plain, environment) == ""
    assert _maps(state) == []


def test_linked_worktree_resolves_head(repo, env):
    """In a linked worktree `.git` is a FILE, so treating it as a directory
    would skip the repository entirely."""
    environment, _, state = env
    worktree = repo.parent / "wt"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(worktree), "-b", "wt"],
        check=True,
        capture_output=True,
    )
    assert (worktree / ".git").is_file()
    _run("refresh", worktree, environment)
    assert _maps(state)


@pytest.mark.parametrize("raw", ["", "   ", "not json", "[]", "null", '{"cwd":"/nonexistent/xyz"}'])
def test_malformed_payloads_fail_open(raw, repo, env, tmp_path):
    environment, _, _ = env
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "inject"],
        input=raw,
        capture_output=True,
        text=True,
        env=environment,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0


def test_forget_removes_this_checkouts_map(repo, env):
    """Maps are keyed by the ROOT PATH, so a removed worktree leaves one nothing
    will read again. Worktrunk `post-remove` calls this."""
    environment, _, state = env
    _run("refresh", repo, environment)
    assert len(_maps(state)) == 1
    _run("forget", repo, environment)
    assert _maps(state) == []


def test_forget_is_silent_when_there_is_no_map(repo, env):
    environment, _, state = env
    assert _run("forget", repo, environment) == ""
    assert _maps(state) == []


def test_a_worktree_gets_its_own_map(repo, env, tmp_path):
    """Keyed by root path, so a linked worktree cannot collide with its parent."""
    environment, _, state = env
    worktree = repo.parent / "wt2"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(worktree), "-b", "wt2"],
        check=True,
        capture_output=True,
    )
    _run("refresh", repo, environment)
    _run("refresh", worktree, environment)
    assert len(_maps(state)) == 2


def _scoped(state: Path) -> list[Path]:
    return sorted((state / "agentic-tools" / "token-savings").glob("*-scoped-*.xml"))


def test_scoped_map_is_keyed_separately_from_the_full_map(repo, env):
    """Building a scoped map must not clobber the full one: an orchestrated run
    scoping a subagent to one crate should not blind the parent session."""
    environment, _, state = env
    _run("refresh", repo, environment)
    _run("refresh", repo, environment, extra=["--scope", "src/**"])
    assert len(_maps(state)) == 1
    assert len(_scoped(state)) == 1


def test_scope_replaces_the_default_allowlist(repo, env):
    """A caller naming `crates/foo/**` means that subtree, not its intersection
    with a language list."""
    environment, argv_log, _ = env
    _run("refresh", repo, environment, extra=["--scope", "src/**"])
    argv = argv_log.read_text()
    assert "src/**" in argv
    assert "**/*.rs" not in argv


def test_two_scopes_coexist(repo, env):
    environment, _, state = env
    _run("refresh", repo, environment, extra=["--scope", "src/**"])
    _run("refresh", repo, environment, extra=["--scope", "tests/**"])
    assert len(_scoped(state)) == 2


def test_forget_scope_leaves_the_full_map(repo, env):
    environment, _, state = env
    _run("refresh", repo, environment)
    _run("refresh", repo, environment, extra=["--scope", "src/**"])
    _run("forget", repo, environment, extra=["--scope", "src/**"])
    assert _scoped(state) == []
    assert len(_maps(state)) == 1


def test_inject_reads_the_scoped_map_when_scoped(repo, env):
    environment, _, _ = env
    _run("refresh", repo, environment, extra=["--scope", "src/**"])
    out = _run("inject", repo, environment, extra=["--scope", "src/**"])
    assert "<directory_structure>" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_unknown_subcommand_is_a_noop(repo, env):
    environment, _, _ = env
    assert _run("bogus", repo, environment) == ""


@pytest.mark.parametrize(
    "shell_command",
    ["ls -la", "cargo build", "rg pattern .", "echo hello", "python3 x.py", "git status"],
)
def test_commands_that_cannot_move_head_do_not_repack(shell_command, repo, env):
    """refresh runs on EVERY Bash call, so the common case must cost one
    interpreter start and no filesystem work."""
    environment, argv_log, state = env
    _run("refresh", repo, environment, shell_command=shell_command)
    assert _maps(state) == []
    assert not argv_log.exists()


@pytest.mark.parametrize(
    "shell_command",
    [
        "git commit -m x",
        "git merge feature",
        "git rebase main",
        "git pull",
        "git checkout -b x",
        "git switch -c x",
        "git worktree add ../wt",
        "git reset --hard HEAD~1",
    ],
)
def test_head_moving_commands_trigger_a_repack(shell_command, repo, env):
    environment, _, state = env
    _run("refresh", repo, environment, shell_command=shell_command)
    assert len(_maps(state)) == 1


def test_force_bypasses_the_command_filter(repo, env):
    """SessionStart and manual runs have no shell command to inspect."""
    environment, _, state = env
    _run("refresh", repo, environment, extra=["--force"], shell_command="ls")
    assert len(_maps(state)) == 1


def test_concurrent_refresh_dedupes_via_lockdir(repo, env):
    """Several SessionStart hooks can fire at once across worktrees."""
    environment, argv_log, state = env
    _run("refresh", repo, environment)
    maps = _maps(state)
    assert maps
    # Hold the lock the way a live sibling process would.
    lock = Path(str(maps[0]) + ".lock")
    lock.mkdir()
    before = argv_log.read_text().count("\n")
    (repo / "c.py").write_text("z = 3\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "third"], check=True, capture_output=True
    )
    _run("refresh", repo, environment)
    assert argv_log.read_text().count("\n") == before
    lock.rmdir()
