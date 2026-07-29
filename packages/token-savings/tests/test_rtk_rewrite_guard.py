"""Coverage for rtk-rewrite-guard.py, a PreToolUse:Bash rewrite hook.

The negative cases are the point. This guard makes the agent's command run
through a lossy filter, so every case it must NOT touch is a case where a
filtered rendering could change an answer rather than merely shorten it. Those
tests outnumber the positive ones deliberately.

Each refusal below was verified against rtk 0.43.0 rather than assumed:
`rtk git status --porcelain` drops the trailing newline (so `| wc -l`
under-counts), and `rtk grep` returned 25 of 400 matching lines (so `grep -c`
would be wrong). The guard cannot detect caller intent, so it refuses the whole
shape.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "rtk-rewrite-guard.py"


def _run(payload, *, with_rtk: bool = True, tmp_path: Path | None = None) -> str:
    """Run the guard, returning the rewritten command or "" when untouched.

    A stub `rtk` goes on PATH so the suite does not depend on rtk being
    installed on the machine running it.
    """
    env = dict(os.environ)
    if with_rtk:
        if tmp_path is not None:
            stub_dir = tmp_path / "bin"
            stub_dir.mkdir(exist_ok=True)
            stub = stub_dir / "rtk"
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
            env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    else:
        # An empty PATH is not enough: shutil.which falls back to os.defpath.
        env["PATH"] = str(tmp_path / "empty") if tmp_path else "/nonexistent"

    raw = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(GUARD)], input=raw, capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.strip()
    if not out:
        return ""
    return json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"]


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# --- commands that SHOULD be routed through rtk -----------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git log --oneline -20",
        "git diff HEAD~1",
        "git show HEAD",
        "git blame README.md",
        "gh pr view 799",
        "gh issue list",
        "gh run view 123",
        "cargo clippy",
        "cargo test",
        "kubectl get pods",
        "kubectl describe pod x",
        "docker ps",
        "ruff check .",
        "eslint src",
        "tsc --noEmit",
        "uv run pytest",
    ],
)
def test_allowlisted_commands_are_routed(command, tmp_path):
    assert _run(_bash(command), tmp_path=tmp_path) == f"rtk {command}"


@pytest.mark.parametrize(
    "command",
    ["uv run pytest -q", "pytest -q", "uv run --with pytest pytest tests/"],
)
def test_quiet_is_allowed_where_it_only_means_less_verbose(command, tmp_path):
    """`-q` is machine-quiet to git and merely terse to pytest, so banning it
    globally refused the single most common command in local history."""
    assert _run(_bash(command), tmp_path=tmp_path) == f"rtk {command}"


@pytest.mark.parametrize(
    "command",
    [
        "git log -q",
        "git log --quiet",
        "git log -c core.x=1",
        "gh pr view 1 -q .title",
        "gh pr view 1 --jq .title",
        "docker ps -q",
        "kubectl get pods -o json",
        "kubectl get pods --output json",
    ],
)
def test_ambiguous_flags_still_block_the_commands_they_mean_machine_output_for(command, tmp_path):
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize("command", ["uv tool install x", "uv sync", "uv pip list"])
def test_only_uv_run_is_routed(command, tmp_path):
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command",
    ["git log --oneline", "git log -5", "git log -n 20", "git log -n20", "git log --max-count=5"],
)
def test_bounded_git_log_is_routed(command, tmp_path):
    """Verified lossless on 0.44.1 over a 25-commit history."""
    assert _run(_bash(command), tmp_path=tmp_path) == f"rtk {command}"


@pytest.mark.parametrize("command", ["git log", "git log --stat", "git log --graph", "git log -p"])
def test_unbounded_git_log_is_refused(command, tmp_path):
    """These return 10 of 25 commits with NO omission marker and no tee log, so
    the agent cannot tell it is reading a prefix of the history."""
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command",
    [
        "go test ./...",
        "go build ./...",
        "go vet ./...",
        "mypy src",
        "npm run build",
        "pnpm test",
        "jest",
        "vitest run",
        "dotnet build",
        "mvn test",
        "rubocop",
        "rspec",
        "phpunit",
        "prettier --check .",
        "biome check .",
        "sbt compile",
    ],
)
def test_other_language_toolchains_are_routed(command, tmp_path):
    """rtk ships ~79 filters; these cover the other toolchains. Each was checked
    with rtk-verify.py where the toolchain is installed locally."""
    assert _run(_bash(command), tmp_path=tmp_path) == f"rtk {command}"


@pytest.mark.parametrize(
    "command", ["golangci-lint run", "golangci-lint run ./...", "curl -s https://x.test"]
)
def test_blocked_binaries_are_refused_even_though_rtk_offers_them(command, tmp_path):
    """`rtk golangci-lint` turns exit 1 into exit 0 AND drops the line number
    (`./main.go:11:6:` becomes `main.go (1 issues)`), so a linter reports clean
    while findings exist. `rtk curl` passed an 89 KB HTML page through unchanged."""
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize("command", ["find . -name '*.txt'", "find . -type f"])
def test_find_is_refused(command, tmp_path):
    """`rtk find` dropped four of six directories entirely, announcing only
    `+130 more` with no path to recover them."""
    assert _run(_bash(command), tmp_path=tmp_path) == ""


def test_env_assignments_keep_their_position(tmp_path):
    """`rtk FOO=1 cargo clippy` would make the assignment an argument to rtk
    rather than environment for cargo -- a different command."""
    assert _run(_bash("FOO=1 cargo clippy"), tmp_path=tmp_path) == "FOO=1 rtk cargo clippy"
    assert _run(_bash("A=1 B=2 git log -1"), tmp_path=tmp_path) == "A=1 B=2 rtk git log -1"


def test_absolute_paths_resolve_to_the_allowlisted_binary(tmp_path):
    assert _run(_bash("/usr/bin/git log -5"), tmp_path=tmp_path) == "rtk /usr/bin/git log -5"


# --- commands that must be LEFT ALONE --------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        # Verified defect: rtk drops the trailing newline on --porcelain.
        "git status --porcelain",
        # Machine-readable output whose shape is the caller's contract.
        "git log --format=%H",
        "git log --pretty=oneline",
        "git diff --name-only",
        "git diff --numstat",
        "gh pr list --json title",
        "git log --oneline --quiet",
        # Single-token output: nothing to save, always parsed.
        "git rev-parse HEAD",
        # rtk grep truncates to ~25 lines; fatal for a count.
        "grep -c foo x",
        "rg -n pattern",
        # The output IS a count.
        "wc -l file",
        # Not on the allowlist at all.
        "python3 -c 'print(1)'",
        "curl -s https://example.test",
        "ls -la",
        "make build",
    ],
)
def test_unsafe_or_unlisted_commands_are_untouched(command, tmp_path):
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command",
    [
        "git log > /tmp/out",
        "git log >> /tmp/out",
        "cargo clippy &> /tmp/out",
        "git diff && cargo clippy",
        "cargo clippy || true",
        "echo $(git log --oneline -1)",
        "echo `git log -1`",
        "git log < /dev/null",
    ],
)
def test_redirection_and_chaining_are_untouched(command, tmp_path):
    """A filtered rendering written to a file or feeding another command could
    change a result rather than just shorten what the model reads."""
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command,expected",
    [
        ("cargo clippy | tail -50", "rtk cargo clippy | tail -50"),
        ("cargo clippy 2>&1 | tail -50", "rtk cargo clippy 2>&1 | tail -50"),
        ("uv run pytest 2>&1 | tail -30", "rtk uv run pytest 2>&1 | tail -30"),
        ("pytest -q | head -20", "rtk pytest -q | head -20"),
        ("cargo test | tail -50 | head -5", "rtk cargo test | tail -50 | head -5"),
    ],
)
def test_piping_into_a_pure_truncator_is_routed(command, expected, tmp_path):
    """`cmd 2>&1 | tail -50` is the dominant real idiom: the agent truncating by
    hand because output is too large. rtk does it better and safely, because tail
    and head do not interpret what they read. Measured on `cargo clippy`:
    `native | tail -50` 657 bytes against `rtk | tail -50` 89, warning intact."""
    assert _run(_bash(command), tmp_path=tmp_path) == expected


@pytest.mark.parametrize(
    "command",
    [
        "cargo clippy | wc -l",
        "cargo clippy | grep ERROR",
        "cargo clippy | rg warning",
        "cargo clippy | jq .",
        "cargo clippy | sort",
        "cargo clippy | tail -5 | wc -l",
        "git log --oneline | awk '{print $1}'",
    ],
)
def test_piping_into_anything_that_interprets_is_refused(command, tmp_path):
    """rtk reformats and truncates, so a counter miscounts and a searcher can
    miss a line that was dropped."""
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command,expected",
    [
        ("timeout 600 cargo clippy", "timeout 600 rtk cargo clippy"),
        ("timeout 2m pytest -q", "timeout 2m rtk pytest -q"),
        ("gtimeout 30 cargo test", "gtimeout 30 rtk cargo test"),
        (
            "timeout 600 uv run pytest 2>&1 | tail -50",
            "timeout 600 rtk uv run pytest 2>&1 | tail -50",
        ),
    ],
)
def test_timeout_wrapper_keeps_rtk_inside_it(command, expected, tmp_path):
    """rtk goes after the wrapper so the timeout still governs the whole run."""
    assert _run(_bash(command), tmp_path=tmp_path) == expected


def test_timeout_with_a_flag_is_not_guessed_at(tmp_path):
    assert _run(_bash("timeout --preserve-status 5 pytest"), tmp_path=tmp_path) == ""


def test_timeout_does_not_launder_an_unlisted_command(tmp_path):
    assert _run(_bash("timeout 600 rm -rf /tmp/x"), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command,expected",
    [
        ("cd /tmp/x && cargo build", "cd /tmp/x && rtk cargo build"),
        ("cd ~/dev/repo && gh pr checks 5 2>&1 | tail -10", "cd ~/dev/repo && rtk gh pr checks 5 2>&1 | tail -10"),
        ("cd /a && uv run pytest", "cd /a && rtk uv run pytest"),
    ],
)
def test_a_single_leading_cd_is_stepped_over(command, expected, tmp_path):
    """`cd` is the first token of 12,393 of 24,725 local Bash calls. It neither
    filters nor consumes output, so the command after it is routable."""
    assert _run(_bash(command), tmp_path=tmp_path) == expected


@pytest.mark.parametrize(
    "command",
    [
        "cd /tmp/x && rm -rf /tmp/y",
        "cd /tmp/x && cargo build && echo done",
        "cd /a && cd /b && cargo test",
    ],
)
def test_cd_does_not_launder_a_longer_chain(command, tmp_path):
    assert _run(_bash(command), tmp_path=tmp_path) == ""


def test_a_cd_semicolon_chain_routes_the_later_segment(tmp_path):
    """`cd /x; cargo build` is two independent commands, so the second is
    routable on its own -- unlike `cd /x && cargo build && echo done`, where
    exit-status control flow links the parts."""
    assert (
        _run(_bash("cd /tmp/x; cargo build"), tmp_path=tmp_path) == "cd /tmp/x; rtk cargo build"
    )


@pytest.mark.parametrize(
    "command,expected",
    [
        ('echo "=== A ==="; cargo build 2>&1 | tail -2', 'echo "=== A ==="; rtk cargo build 2>&1 | tail -2'),
        ("cd /x; cargo test 2>&1 | tail -5", "cd /x; rtk cargo test 2>&1 | tail -5"),
        ("cargo build; cargo clippy", "rtk cargo build; rtk cargo clippy"),
        ('bd note x "a; b"; cargo build', 'bd note x "a; b"; rtk cargo build'),
    ],
)
def test_semicolon_segments_are_routed_individually(command, expected, tmp_path):
    """A `;` chain is a sequence of independent commands, not a data pipeline, so
    filtering one segment cannot affect another. This was the single biggest
    blocker in real traffic: 649 of 1,043 rtk-filterable commands."""
    assert _run(_bash(command), tmp_path=tmp_path) == expected


@pytest.mark.parametrize(
    "command", ["echo hi; rm -rf /tmp/y", "echo a; echo b", "ls; pwd"]
)
def test_a_chain_with_no_routable_segment_is_untouched(command, tmp_path):
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command,expected",
    [
        ('git log --oneline --grep="a;b" -5', 'rtk git log --oneline --grep="a;b" -5'),
        ("cargo build --features 'a;b'", "rtk cargo build --features 'a;b'"),
        ('git log --oneline --grep="fix > bug" -5', 'rtk git log --oneline --grep="fix > bug" -5'),
    ],
)
def test_markers_inside_quotes_are_data_not_shell_syntax(command, expected, tmp_path):
    """A quoted `;` or `>` is an argument. A raw substring check refused these."""
    assert _run(_bash(command), tmp_path=tmp_path) == expected


def test_unbalanced_quotes_stay_untouched(tmp_path):
    assert _run(_bash('echo "unbalanced; cargo build'), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command,expected",
    [
        (
            "gh run view --job 1 --log-failed 2>/dev/null | tail -30",
            "rtk gh run view --job 1 --log-failed 2>/dev/null | tail -30",
        ),
        ("cargo clippy 2> /dev/null | tail -5", "rtk cargo clippy 2> /dev/null | tail -5"),
    ],
)
def test_discarding_stderr_is_not_a_file_redirect(command, expected, tmp_path):
    """`2>/dev/null` discards stderr; it does not send OUTPUT to a file."""
    assert _run(_bash(command), tmp_path=tmp_path) == expected


@pytest.mark.parametrize(
    "command", ["cargo test --no-run", "cargo test --workspace --no-run"]
)
def test_cargo_test_no_run_is_refused(command, tmp_path):
    """`rtk cargo test --no-run` emits ZERO bytes and exits 0, discarding the
    built test-executable paths. Reproduced on a 4,107-file workspace (32,031
    native bytes to 0) and on a two-file fixture (151 to 0)."""
    assert _run(_bash(command), tmp_path=tmp_path) == ""


def test_already_routed_commands_are_not_double_wrapped(tmp_path):
    assert _run(_bash("rtk git log --oneline"), tmp_path=tmp_path) == ""


def test_machine_flag_with_attached_value_is_detected(tmp_path):
    """`--format=x` attaches its value, so a plain membership test misses it."""
    assert _run(_bash("git log --format=%H -5"), tmp_path=tmp_path) == ""
    assert _run(_bash("git log --pretty=short"), tmp_path=tmp_path) == ""


# --- fail-open behavior ----------------------------------------------------


def test_missing_rtk_leaves_the_command_alone(tmp_path):
    (tmp_path / "empty").mkdir()
    assert _run(_bash("git log --oneline"), with_rtk=False, tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not json",
        '{"tool_name":"Bash","tool_input":',  # truncated mid-write
        "[]",
        "null",
        '{"tool_name":"Bash"}',
        '{"tool_name":"Bash","tool_input":{}}',
        '{"tool_name":"Bash","tool_input":{"command":""}}',
        '{"tool_name":"Bash","tool_input":{"command":null}}',
        '{"tool_name":"Bash","tool_input":42}',
    ],
)
def test_malformed_payloads_fail_open(raw, tmp_path):
    assert _run(raw, tmp_path=tmp_path) == ""


def test_string_tool_input_is_accepted(tmp_path):
    """Some callers send tool_input as a bare string; reading .command off it
    would throw and silently bypass the guard."""
    payload = {"tool_name": "Bash", "tool_input": "git log --oneline"}
    assert _run(payload, tmp_path=tmp_path) == "rtk git log --oneline"


def test_unbalanced_quotes_are_untouched(tmp_path):
    assert _run(_bash('git log --grep="unterminated'), tmp_path=tmp_path) == ""


def test_emits_allow_and_never_ask(tmp_path):
    """Constitution III: no guard emits `ask`, and Codex rejects it outright.
    `updatedInput` additionally requires permissionDecision:allow on Codex."""
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "rtk"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"

    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(_bash("git log --oneline")),
        capture_output=True,
        text=True,
        env=env,
    )
    emitted = json.loads(proc.stdout)["hookSpecificOutput"]
    assert emitted["permissionDecision"] == "allow"
    assert emitted["hookEventName"] == "PreToolUse"
    assert "ask" != emitted["permissionDecision"]
    # Claude-only fields would be silent no-ops on Codex in a target: all package.
    assert "systemMessage" not in emitted
    assert "suppressOutput" not in emitted


@pytest.mark.skipif(shutil.which("rtk") is None, reason="rtk not installed")
def test_allowlisted_rewrites_preserve_content_on_real_rtk(tmp_path):
    """Guard against the allowlist drifting ahead of what rtk actually
    preserves. `git log --oneline` must return the same commit subjects, just
    possibly fewer bytes of decoration."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", "-C", str(repo), *a], capture_output=True, text=True, check=True
    )
    run("init", "-q")
    run("config", "user.email", "t@example.test")
    run("config", "user.name", "t")
    run("config", "commit.gpgsign", "false")
    (repo / "f.txt").write_text("x\n")
    run("add", "-A")
    run("commit", "-qm", "a distinctive subject line")

    native = run("log", "--oneline").stdout
    filtered = subprocess.run(
        ["rtk", "git", "log", "--oneline"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "a distinctive subject line" in native
    assert "a distinctive subject line" in filtered
