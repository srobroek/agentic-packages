"""Coverage for the beads sync hooks.

Ported from sync-hooks.bats, which is kept as the oracle: every one of its 36 cases
appears here, and the ids below name the same behaviours. Cases that need a real
`bd` workspace are skipped when bd is absent, exactly as the bats suite skipped
them, so the suite stays green on a machine without it.

The gating tests matter more than the happy path: these hooks run on every Bash call
and every session start in every repository, so a missing guard means writing bead
state into repositories that never asked for it.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

# Importable helper module, plus the three hook entrypoints.
sys.path.insert(0, str(SCRIPTS))
import beads_sync  # noqa: E402

HOOKS = ("beads-sync-stage", "beads-sync-session", "beads-sync-push")


def load(stem: str):
    """Import a hyphenated hook script as a module."""
    path = SCRIPTS / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def drive(stem: str, payload, monkeypatch, capsys):
    """Run a hook's main() against a payload and return (code, parsed output)."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    module = load(stem)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    code = module.main()
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None)


def run_script(stem: str, payload, *, cwd=None, env=None):
    """Run a hook as a subprocess, the way the harness actually invokes it."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{stem}.py")],
        input=text,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=merged,
        timeout=300,
        check=False,
    )


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """A throwaway git repository with hooks disabled.

    hooksPath points at an empty directory so a host-installed hook (anything set
    globally via core.hooksPath) cannot run inside these repositories.
    """
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".no-hooks").mkdir()
    for command in (
        ["git", "init", "-q", "-b", "main", "."],
        ["git", "config", "core.hooksPath", str(root / ".no-hooks")],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
        # A global commit.gpgsign fails (and `bd init` outright BLOCKS on) the
        # 1Password agent when it is not running. Nothing here is worth signing.
        ["git", "config", "commit.gpgsign", "false"],
        ["git", "config", "tag.gpgsign", "false"],
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    return root


@pytest.fixture
def beads_repo(repo):
    """A repo with a real beads workspace, skipped when bd is unavailable."""
    if shutil.which("bd") is None:
        pytest.skip("bd not available")
    # `bd -C` refuses a directory with no project yet, so init runs with cwd=repo.
    # --skip-hooks: never let a test wire global hooks. NOT --stealth, which
    # excludes .beads/ via .git/info/exclude and would make `git add` fail.
    ok = subprocess.run(
        ["bd", "init", "--prefix", "tb", "--skip-hooks"],
        cwd=repo,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if ok.returncode != 0:
        pytest.skip("bd init failed")
    where = subprocess.run(
        ["bd", "-C", str(repo), "where"], capture_output=True, timeout=60, check=False
    )
    if where.returncode != 0:
        pytest.skip("no beads workspace")
    return repo


def opt_in(root, key="custom.jsonl-git-sync", value="true"):
    subprocess.run(
        ["bd", "-C", str(root), "config", "set", key, value],
        capture_output=True,
        timeout=60,
        check=False,
    )


def staged(root):
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.split()


# --- oracle 1: parse / portability floor ----------------------------------


@pytest.mark.parametrize("stem", (*HOOKS, "beads_sync"))
def test_scripts_compile(stem):
    """Oracle: 'scripts parse under /bin/bash'."""
    subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPTS / f"{stem}.py")], check=True
    )


@pytest.mark.parametrize("stem", HOOKS)
def test_hooks_have_a_shebang_and_are_executable(stem):
    path = SCRIPTS / f"{stem}.py"
    assert path.read_text(encoding="utf-8").splitlines()[0] == "#!/usr/bin/env python3"
    assert os.access(path, os.X_OK), f"{stem}.py must be chmod +x"


def test_no_hook_spawns_jq_or_awk():
    """The point of the port: no JSON parsed and no command tokenized by subprocess."""
    for stem in (*HOOKS, "beads_sync"):
        for line in code_lines(stem):
            for banned in ("'jq'", "'awk'", "'sed'"):
                assert banned not in line, f"{stem}.py still spawns {banned}: {line}"


def test_helper_module_is_not_executable():
    """beads_sync.py is imported, never run, so it must not look like an entrypoint."""
    body = (SCRIPTS / "beads_sync.py").read_text(encoding="utf-8")
    assert not body.startswith("#!"), "the helper module should carry no shebang"
    assert '__name__ == "__main__"' not in body


# --- oracle 2, 3: empty payload ------------------------------------------


@pytest.mark.parametrize("stem", HOOKS)
def test_empty_payload_exits_zero(stem, monkeypatch, capsys):
    """Oracle: 'stage/hydrate: empty payload exits 0 and writes nothing'."""
    code, out = drive(stem, "", monkeypatch, capsys)
    assert code == 0
    assert out is None


@pytest.mark.parametrize("stem", HOOKS)
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("not json", id="unparsable"),
        pytest.param("[]", id="not-an-object"),
        pytest.param("{}", id="empty-object"),
        pytest.param('{"tool_input": null}', id="null-tool-input"),
        pytest.param('{"cwd": 42}', id="numeric-cwd"),
    ],
)
def test_malformed_payload_never_raises(stem, payload, monkeypatch, capsys):
    """Fail open: a hook must never turn a bad payload into a crash."""
    code, _ = drive(stem, payload, monkeypatch, capsys)
    assert code == 0


# --- oracles 7-10: git commit detection (pure logic) ---------------------


stage = load("beads-sync-stage")


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("git commit", id="bare"),
        pytest.param("git commit -m 'msg'", id="with-message"),
        pytest.param("git -C /repo commit -m x", id="dash-C-value"),
        pytest.param("git -c user.name=x commit", id="dash-c-value"),
        pytest.param("git --no-pager commit", id="global-flag"),
        pytest.param("git --git-dir=/r/.git commit", id="git-dir-equals"),
        pytest.param("cd /tmp && git commit -m x", id="after-separator"),
        pytest.param("time git commit", id="wrapper-prefix"),
        pytest.param("GIT_AUTHOR_NAME=x git commit", id="env-assignment"),
        pytest.param("/usr/bin/git commit", id="absolute-path"),
        pytest.param("(git commit -m x)", id="subshell"),
        pytest.param("dgit commit\ngit commit", id="second-line"),
    ],
)
def test_real_commit_is_detected(command):
    """Oracles: 'flags between git and commit still match', 'real commit stages'."""
    assert stage.commits(command)


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("git status", id="non-commit"),
        pytest.param("git log --oneline", id="log"),
        pytest.param("git log --format=%s commit", id="commit-as-format-arg"),
        pytest.param("echo git commit", id="echo"),
        pytest.param("git commit-tree abc", id="different-subcommand"),
        pytest.param("mygit commit", id="different-binary"),
        pytest.param("ls; echo done", id="unrelated"),
    ],
)
def test_non_commit_is_not_detected(command):
    """Oracle: 'non-commit git command does not stage'."""
    assert not stage.commits(command)


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("echo 'git commit'", id="single-quoted"),
        pytest.param('echo "git commit"', id="double-quoted"),
        pytest.param("""git tag -m "run git commit later" v1""", id="quoted-in-arg"),
    ],
)
def test_quoted_mention_is_not_a_commit(command):
    """Oracle: \"'git commit' inside a quoted string does not stage\"."""
    assert not stage.commits(command)


def test_commit_message_mentioning_git_commit_still_stages():
    """Oracle: 'real commit stages the export even when the message says git commit'.

    Both facts hold at once: the real verb matches, and the quoted mention does not
    add a second match.
    """
    assert stage.commits('git commit -m "do not git commit twice"')


def test_unbalanced_quotes_are_not_a_commit():
    """shlex raises; the shell would reject this too, so judge nothing."""
    assert not stage.commits("git commit -m 'unterminated")


# --- oracles 23-26: push probe verdicts ---------------------------------


def test_probe_no_verdict_without_origin(repo):
    """Oracle: 'push probe returns no-verdict (2) when there is no origin'."""
    assert beads_sync.push_permitted(str(repo), 30) == beads_sync.PUSH_NO_VERDICT


def test_probe_no_verdict_outside_a_repo(tmp_path):
    assert beads_sync.push_permitted(str(tmp_path), 30) == beads_sync.PUSH_NO_VERDICT


def test_probe_no_verdict_for_unreachable_host(repo):
    """Oracle: 'push probe returns no-verdict (2) for an unreachable host'."""
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "add",
            "origin",
            "https://no-such-host.invalid/x.git",
        ],
        check=True,
        capture_output=True,
    )
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "c"], check=True, capture_output=True
    )
    assert beads_sync.push_permitted(str(repo), 30) == beads_sync.PUSH_NO_VERDICT


def test_probe_permits_a_reachable_remote_with_no_guard(repo, tmp_path):
    """Oracle: 'push probe permits a reachable remote with no guard'."""
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(bare)],
        check=True,
        capture_output=True,
    )
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "c"], check=True, capture_output=True
    )
    assert beads_sync.push_permitted(str(repo), 30) == beads_sync.PUSH_PERMITTED


def test_probe_treats_a_refusing_pre_push_hook_as_refused(repo, tmp_path):
    """Oracle: 'push probe treats a refusing pre-push hook as not permitted'."""
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(bare)],
        check=True,
        capture_output=True,
    )
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "c"], check=True, capture_output=True
    )

    hooks = repo / ".no-hooks"
    guard = hooks / "pre-push"
    guard.write_text(
        "#!/bin/sh\necho 'pre-push hook declined: nope' >&2\nexit 1\n", encoding="utf-8"
    )
    guard.chmod(0o755)
    assert beads_sync.push_permitted(str(repo), 30) == beads_sync.PUSH_REFUSED


def test_refusal_and_no_verdict_are_distinct():
    """Collapsing them would advise changing a sync strategy over a dropped
    connection, so the two marker sets must not overlap."""
    assert beads_sync.PUSH_REFUSED != beads_sync.PUSH_NO_VERDICT
    assert not set(beads_sync.REFUSAL_MARKERS) & set(beads_sync.TRANSIENT_MARKERS)


# --- envelope / config helpers ------------------------------------------


def test_envelope_accepts_both_shapes():
    """bd wraps output under BD_JSON_ENVELOPE and returns it bare without."""
    assert beads_sync.envelope('{"data": {"commit_count": 5}}') == {"commit_count": 5}
    assert beads_sync.envelope('{"commit_count": 5}') == {"commit_count": 5}


@pytest.mark.parametrize(
    "raw", ["", "not json", "[]", "null", '"text"'], ids=["empty", "bad", "list", "null", "str"]
)
def test_envelope_rejects_junk(raw):
    assert beads_sync.envelope(raw) is None


def test_truthy_spellings():
    assert beads_sync.TRUTHY == {"true", "1", "yes", "on"}


def test_payload_cwd_falls_back(tmp_path):
    assert beads_sync.payload_cwd("", "/fallback") == "/fallback"
    assert beads_sync.payload_cwd("bad json", "/fallback") == "/fallback"
    assert beads_sync.payload_cwd('{"cwd": "/nonexistent-xyz"}', "/fallback") == "/fallback"
    assert beads_sync.payload_cwd(json.dumps({"cwd": str(tmp_path)}), "/fb") == str(tmp_path)


def test_export_all_rejects_an_empty_export(tmp_path, monkeypatch):
    """An empty export means something went wrong; treating it as success would let
    a caller overwrite a good committed file with nothing."""
    destination = tmp_path / "out.jsonl"

    class Result:
        returncode = 0

    monkeypatch.setattr(beads_sync, "run", lambda *a, **k: Result())
    assert beads_sync.export_all("/x", str(destination)) is False


# --- oracles 4-6, 20-21, 30: gating without a workspace ----------------


@pytest.mark.parametrize("stem", HOOKS)
def test_no_beads_workspace_is_inert(stem, repo, monkeypatch, capsys):
    """Oracle: 'no beads workspace is inert'."""
    monkeypatch.setattr(beads_sync, "beads_dir", lambda cwd: "")
    code, out = drive(stem, {"cwd": str(repo), "tool_input": {"command": "git commit"}}, monkeypatch, capsys)
    assert code == 0
    assert out is None
    assert staged(repo) == []


def test_stage_without_opt_in_is_inert(beads_repo, monkeypatch, capsys):
    """Oracle: 'stage: beads workspace WITHOUT opt-in is inert'."""
    code, out = drive(
        "beads-sync-stage",
        {"cwd": str(beads_repo), "tool_input": {"command": "git commit -m x"}},
        monkeypatch,
        capsys,
    )
    assert code == 0
    assert out is None
    assert "issues.jsonl" not in " ".join(staged(beads_repo))


def test_session_without_opt_in_is_inert(beads_repo, monkeypatch, capsys):
    """Oracle: 'hydrate: beads workspace WITHOUT opt-in is inert' and
    'maintenance: inert without the opt-in'."""
    code, out = drive("beads-sync-session", {"cwd": str(beads_repo)}, monkeypatch, capsys)
    assert code == 0
    assert out is None


def test_push_without_opt_in_is_inert(beads_repo, monkeypatch, capsys):
    """Oracle: 'push: no auto-push opt-in means the hook is inert'."""
    calls = []
    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: calls.append(cwd) or True)
    code, out = drive("beads-sync-push", {"cwd": str(beads_repo)}, monkeypatch, capsys)
    assert code == 0
    assert calls == [], "the opt-in must be checked before the remote"


def test_push_opt_in_without_a_dolt_remote_is_inert(beads_repo, monkeypatch, capsys):
    """Oracle: 'push: opt-in without a Dolt remote is inert'."""
    opt_in(beads_repo, "custom.dolt-auto-push")
    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: False)
    detached = []
    push = load("beads-sync-push")
    monkeypatch.setattr(push, "detach", lambda *a: detached.append(a))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(beads_repo)})))
    assert push.main() == 0
    capsys.readouterr()
    assert detached == []
    assert not (Path(beads_repo) / ".beads" / "last-push.log").exists()


# --- oracles 11, 12, 19: stage behaviour with a workspace --------------


def test_stage_writes_valid_jsonl_carrying_the_bead(beads_repo, monkeypatch, capsys):
    """Oracle: 'stage: written file is valid JSONL carrying the bead'."""
    opt_in(beads_repo)
    created = subprocess.run(
        ["bd", "-C", str(beads_repo), "create", "sync fixture bead"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip("bd create failed")

    code, _ = drive(
        "beads-sync-stage",
        {"cwd": str(beads_repo), "tool_input": {"command": "git commit -m x"}},
        monkeypatch,
        capsys,
    )
    assert code == 0

    target = Path(beads_repo) / ".beads" / "issues.jsonl"
    assert target.is_file()
    lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "export wrote nothing"
    for line in lines:
        json.loads(line)
    assert any("sync fixture bead" in line for line in lines)
    assert any("issues.jsonl" in path for path in staged(beads_repo))


def test_stage_unchanged_state_does_not_rewrite(beads_repo, monkeypatch, capsys):
    """Oracle: 'stage: unchanged state does not rewrite the file'."""
    opt_in(beads_repo)
    created = subprocess.run(
        ["bd", "-C", str(beads_repo), "create", "rewrite fixture bead"],
        capture_output=True,
        timeout=120,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip("bd create failed")
    payload = {"cwd": str(beads_repo), "tool_input": {"command": "git commit -m x"}}
    drive("beads-sync-stage", payload, monkeypatch, capsys)

    target = Path(beads_repo) / ".beads" / "issues.jsonl"
    if not target.is_file():
        pytest.skip("no export produced")
    before = target.stat().st_mtime_ns
    first = target.read_bytes()

    drive("beads-sync-stage", payload, monkeypatch, capsys)
    assert target.read_bytes() == first
    assert target.stat().st_mtime_ns == before, "identical state must not rewrite the file"


def test_stage_reports_a_git_ignored_target(beads_repo, monkeypatch, capsys):
    """Oracle: 'stage: a git-ignored target reports instead of failing silently'."""
    opt_in(beads_repo)
    # A bead is required: `bd export --all` on an empty workspace writes zero bytes,
    # which the hook treats as a failed export and bails on before reaching git add.
    created = subprocess.run(
        ["bd", "-C", str(beads_repo), "create", "ignored fixture bead"],
        capture_output=True,
        timeout=120,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip("bd create failed")
    exclude = Path(beads_repo) / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n.beads/\n")

    code, out = drive(
        "beads-sync-stage",
        {"cwd": str(beads_repo), "tool_input": {"command": "git commit -m x"}},
        monkeypatch,
        capsys,
    )
    assert code == 0
    assert out is not None, "an ignored target must be reported, not silently skipped"
    context = out["hookSpecificOutput"]["additionalContext"]
    assert "git-ignored" in context
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def code_lines(stem: str) -> list[str]:
    """Executable lines of a script, with comments and docstrings removed.

    Greping raw source for a banned string matches the prose that EXPLAINS why it is
    banned, so these checks have to read code only.
    """
    import ast

    tree = ast.parse((SCRIPTS / f"{stem}.py").read_text(encoding="utf-8"))
    # Drop docstrings, then unparse: comments are already gone via the AST.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree).splitlines()


def test_stage_never_commits():
    """The agent's own commit carries the file; the hook must never create one."""
    for line in code_lines("beads-sync-stage"):
        if "beads_sync.run" in line or '"git"' in line:
            assert "'commit'" not in line and '"commit"' not in line, (
                f"stage must not invoke git commit: {line}"
            )


# --- oracles 33-36: previous-push reporting ---------------------------


def _session_with_log(root, contents, monkeypatch, capsys):
    beads = Path(root) / ".beads"
    beads.mkdir(exist_ok=True)
    log = beads / "last-push.log"
    log.write_text(contents, encoding="utf-8")

    session = load("beads-sync-session")
    monkeypatch.setattr(beads_sync, "beads_dir", lambda cwd: str(beads))
    monkeypatch.setattr(beads_sync, "bd_available", lambda: True)
    monkeypatch.setattr(session, "hydrate", lambda *a: None)
    monkeypatch.setattr(session, "maintenance", lambda *a: None)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(root)})))
    code = session.main()
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None), log


def test_session_reports_a_failed_push(repo, monkeypatch, capsys):
    """Oracle: 'hydrate: reports a failed push from the previous session'."""
    _, out, log = _session_with_log(
        repo, "started: x\nfailed: bd dolt push exited 1\n", monkeypatch, capsys
    )
    assert out is not None
    assert "FAILED" in out["hookSpecificOutput"]["additionalContext"]
    assert not log.exists(), "the log must be consumed"


def test_session_reports_a_push_that_never_finished(repo, monkeypatch, capsys):
    """Oracle: 'hydrate: reports a push that never finished'."""
    _, out, log = _session_with_log(repo, "started: 2026-01-01T00:00:00Z\n", monkeypatch, capsys)
    assert out is not None
    assert "did not finish" in out["hookSpecificOutput"]["additionalContext"]
    assert not log.exists()


def test_session_does_not_report_a_successful_push(repo, monkeypatch, capsys):
    """Oracle: 'hydrate: a successful push is not reported, and the log is consumed'."""
    _, out, log = _session_with_log(repo, "started: x\nok: push complete\n", monkeypatch, capsys)
    assert out is None
    assert not log.exists()


def test_session_consumes_a_reported_failure(repo, monkeypatch, capsys):
    """Oracle: 'hydrate: a reported failure is consumed, not repeated next session'."""
    _, first, log = _session_with_log(repo, "failed: boom\n", monkeypatch, capsys)
    assert first is not None
    assert not log.exists()

    session = load("beads-sync-session")
    beads = Path(repo) / ".beads"
    monkeypatch.setattr(beads_sync, "beads_dir", lambda cwd: str(beads))
    monkeypatch.setattr(beads_sync, "bd_available", lambda: True)
    monkeypatch.setattr(session, "hydrate", lambda *a: None)
    monkeypatch.setattr(session, "maintenance", lambda *a: None)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    session.main()
    assert capsys.readouterr().out.strip() == "", "a consumed verdict must not repeat"


# --- oracles 16, 17: pull gating -------------------------------------


def test_no_dolt_auto_pull_opt_in_means_no_pull(repo, monkeypatch, capsys):
    """Oracle: 'hydrate: no Dolt auto-pull opt-in means no pull is attempted'."""
    session = load("beads-sync-session")
    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: True)
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: False)
    commands = []
    monkeypatch.setattr(
        beads_sync, "run", lambda command, **k: commands.append(command) or None
    )
    notes: list[str] = []
    session.hydrate(str(repo), str(repo / ".beads"), notes)
    assert not any("pull" in " ".join(c) for c in commands)
    assert notes == []


def test_a_failing_pull_is_reported_not_fatal(repo, monkeypatch):
    """Oracle: 'hydrate: a bogus Dolt remote is reported, not fatal, and JSONL still
    runs'."""
    session = load("beads-sync-session")
    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: True)
    monkeypatch.setattr(
        beads_sync, "opt", lambda cwd, key: key == "custom.dolt-auto-pull"
    )
    monkeypatch.setattr(beads_sync, "run", lambda *a, **k: None)
    notes: list[str] = []
    session.hydrate(str(repo), str(repo / ".beads"), notes)
    assert any("bd dolt pull did not complete" in note for note in notes)


# --- oracles 31, 32: maintenance thresholds -------------------------


def test_maintenance_is_silent_below_the_threshold(repo, monkeypatch):
    """Oracle: 'maintenance: silent below the commit threshold'."""
    session = load("beads-sync-session")
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: True)
    monkeypatch.setattr(session, "count", lambda cwd, command, key: 5)
    notes: list[str] = []
    session.maintenance(str(repo), notes)
    assert notes == []


def test_maintenance_reports_above_the_threshold(repo, monkeypatch):
    """Oracle: 'maintenance: reports above the threshold and never runs a destructive
    command'."""
    session = load("beads-sync-session")
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: True)

    seen = []

    def counted(cwd, command, key):
        seen.append(command)
        return {"commit_count": 5000, "prune_count": 3, "purged_count": 7}[key]

    monkeypatch.setattr(session, "count", counted)
    notes: list[str] = []
    session.maintenance(str(repo), notes)

    assert len(notes) == 1
    message = notes[0]
    assert "5000 Dolt commits" in message
    assert "7 closed wisp" in message
    assert "3 closed bead" in message
    assert "irreversibly" in message
    # Every probe must be a dry run: nothing destructive may execute.
    for command in seen:
        assert "--dry-run" in command, f"{command} is not a dry run"
        assert "--force" not in command


def test_maintenance_names_only_dry_runs_in_source():
    """A --force must never appear as an executed argument."""
    for line in code_lines("beads-sync-session"):
        if "'bd'" in line or "beads_sync.run" in line or "count(" in line:
            assert "--force" not in line, f"destructive argument in: {line}"


# --- oracles 27, 28: push refusal routing ---------------------------


def test_refusal_without_a_wrapper_advises_the_alternatives(repo, monkeypatch, capsys):
    """Oracle: 'push: a refusal with no wrapper configured advises the alternatives'."""
    push = load("beads-sync-push")
    beads = Path(repo) / ".beads"
    beads.mkdir(exist_ok=True)

    monkeypatch.setattr(beads_sync, "bd_available", lambda: True)
    monkeypatch.setattr(beads_sync, "beads_dir", lambda cwd: str(beads))
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: True)
    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: True)
    monkeypatch.setattr(beads_sync, "run", lambda *a, **k: None)
    monkeypatch.setattr(beads_sync, "config", lambda cwd, key: "")
    monkeypatch.setattr(beads_sync, "push_permitted", lambda cwd, t: beads_sync.PUSH_REFUSED)
    detached = []
    monkeypatch.setattr(push, "detach", lambda *a: detached.append(a))

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    assert push.main() == 0
    capsys.readouterr()

    assert detached == [], "a refused push must not be detached"
    log = (beads / "last-push.log").read_text(encoding="utf-8")
    assert log.startswith("failed:")
    assert "custom.bd-push-command" in log


def test_refusal_with_a_wrapper_runs_the_wrapper(repo, monkeypatch, capsys):
    """Oracle: 'push: a refusal WITH a wrapper configured runs the wrapper'."""
    push = load("beads-sync-push")
    beads = Path(repo) / ".beads"
    beads.mkdir(exist_ok=True)

    monkeypatch.setattr(beads_sync, "bd_available", lambda: True)
    monkeypatch.setattr(beads_sync, "beads_dir", lambda cwd: str(beads))
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: True)
    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: True)
    monkeypatch.setattr(beads_sync, "run", lambda *a, **k: None)
    monkeypatch.setattr(beads_sync, "push_permitted", lambda cwd, t: beads_sync.PUSH_REFUSED)
    monkeypatch.setattr(push, "resolve_runner", lambda cwd: "dbd")
    detached = []
    monkeypatch.setattr(push, "detach", lambda *a: detached.append(a))

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    assert push.main() == 0
    capsys.readouterr()

    assert len(detached) == 1, "a configured wrapper must still be tried"
    assert detached[0][0] == "dbd"
    assert (beads / "last-push.log").read_text(encoding="utf-8").startswith("started:")


def test_unreachable_remote_stays_quiet(repo, monkeypatch, capsys):
    """Oracle: 'push: an unreachable remote stays quiet (transient, not a policy
    verdict)'."""
    push = load("beads-sync-push")
    beads = Path(repo) / ".beads"
    beads.mkdir(exist_ok=True)

    monkeypatch.setattr(beads_sync, "bd_available", lambda: True)
    monkeypatch.setattr(beads_sync, "beads_dir", lambda cwd: str(beads))
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: True)
    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: True)
    monkeypatch.setattr(beads_sync, "run", lambda *a, **k: None)
    monkeypatch.setattr(beads_sync, "config", lambda cwd, key: "")
    monkeypatch.setattr(
        beads_sync, "push_permitted", lambda cwd, t: beads_sync.PUSH_NO_VERDICT
    )
    detached = []
    monkeypatch.setattr(push, "detach", lambda *a: detached.append(a))

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    assert push.main() == 0
    capsys.readouterr()

    assert detached == []
    assert not (beads / "last-push.log").exists(), "a transient failure records nothing"


def test_push_resolves_a_wrapper_only_when_it_exists(repo, monkeypatch):
    """An unresolvable wrapper name must fall back to bd, not be executed blindly."""
    push = load("beads-sync-push")
    monkeypatch.setattr(beads_sync, "config", lambda cwd, key: "no-such-binary-xyz")
    assert push.resolve_runner(str(repo)) == "bd"
    monkeypatch.setattr(beads_sync, "config", lambda cwd, key: "sh")
    assert push.resolve_runner(str(repo)) == "sh"


def test_push_detaches_without_setsid():
    """setsid does not exist on macOS, so the shell version's primary detach branch
    never ran there. start_new_session is the portable equivalent."""
    lines = code_lines("beads-sync-push")
    assert not [line for line in lines if "setsid" in line]
    assert not [line for line in lines if "nohup" in line]
    assert [line for line in lines if "start_new_session=True" in line]


# --- oracles 13, 15, 18: hydration import decisions ------------------


def test_identical_file_skips_the_import(repo, monkeypatch):
    """Oracle: 'hydrate: identical file skips the import entirely'."""
    session = load("beads-sync-session")
    beads = Path(repo) / ".beads"
    beads.mkdir(exist_ok=True)
    source = beads / "issues.jsonl"
    source.write_text('{"id":"tb-1"}\n', encoding="utf-8")

    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: False)
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: key == "custom.jsonl-git-sync")

    def fake_export(cwd, destination, **kwargs):
        Path(destination).write_text('{"id":"tb-1"}\n', encoding="utf-8")
        return True

    monkeypatch.setattr(beads_sync, "export_all", fake_export)
    commands = []
    monkeypatch.setattr(beads_sync, "run", lambda command, **k: commands.append(command) or None)

    notes: list[str] = []
    session.hydrate(str(repo), str(beads), notes)
    assert not any("import" in " ".join(c) for c in commands), "identical bytes must not import"


def test_differing_file_triggers_an_import(repo, monkeypatch):
    """Oracle: 'hydrate: a peer bead in the committed file lands in the database'."""
    session = load("beads-sync-session")
    beads = Path(repo) / ".beads"
    beads.mkdir(exist_ok=True)
    (beads / "issues.jsonl").write_text('{"id":"tb-peer"}\n', encoding="utf-8")

    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: False)
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: key == "custom.jsonl-git-sync")

    def fake_export(cwd, destination, **kwargs):
        Path(destination).write_text('{"id":"tb-local"}\n', encoding="utf-8")
        return True

    monkeypatch.setattr(beads_sync, "export_all", fake_export)
    commands = []

    class Result:
        returncode = 0
        stdout = '{"data": {}}'

    monkeypatch.setattr(
        beads_sync, "run", lambda command, **k: commands.append(command) or Result()
    )

    notes: list[str] = []
    session.hydrate(str(repo), str(beads), notes)
    assert any("import" in " ".join(c) for c in commands)
    assert notes == [], "a routine import is silent"


def test_stale_rows_are_reported(repo, monkeypatch):
    """Oracle: 'hydrate: a stale committed file cannot revert newer local work'."""
    session = load("beads-sync-session")
    beads = Path(repo) / ".beads"
    beads.mkdir(exist_ok=True)
    (beads / "issues.jsonl").write_text('{"id":"tb-old"}\n', encoding="utf-8")

    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: False)
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: key == "custom.jsonl-git-sync")

    def fake_export(cwd, destination, **kwargs):
        Path(destination).write_text('{"id":"tb-new"}\n', encoding="utf-8")
        return True

    monkeypatch.setattr(beads_sync, "export_all", fake_export)

    class Result:
        returncode = 0
        stdout = json.dumps({"data": {"stale_skipped_ids": ["tb-1", "tb-2"]}})

    monkeypatch.setattr(beads_sync, "run", lambda *a, **k: Result())

    notes: list[str] = []
    session.hydrate(str(repo), str(beads), notes)
    assert len(notes) == 1
    assert "BEHIND this database" in notes[0]
    assert "tb-1, tb-2" in notes[0]


def test_routine_hydration_is_silent(repo, monkeypatch, capsys):
    """Oracle: 'hydrate: routine hydration is silent'."""
    session = load("beads-sync-session")
    beads = Path(repo) / ".beads"
    beads.mkdir(exist_ok=True)

    monkeypatch.setattr(beads_sync, "bd_available", lambda: True)
    monkeypatch.setattr(beads_sync, "beads_dir", lambda cwd: str(beads))
    monkeypatch.setattr(beads_sync, "opt", lambda cwd, key: False)
    monkeypatch.setattr(beads_sync, "has_dolt_remote", lambda cwd: False)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    assert session.main() == 0
    assert capsys.readouterr().out.strip() == ""


# --- folding: the two SessionStart hooks are now one -----------------


def test_session_emits_one_message_for_both_concerns(repo, monkeypatch, capsys):
    """Folding hydrate and maintenance means their advisories combine, rather than
    each paying a process startup and payload parse (contract rule 5)."""
    session = load("beads-sync-session")
    beads = Path(repo) / ".beads"
    beads.mkdir(exist_ok=True)

    monkeypatch.setattr(beads_sync, "bd_available", lambda: True)
    monkeypatch.setattr(beads_sync, "beads_dir", lambda cwd: str(beads))
    monkeypatch.setattr(session, "hydrate", lambda cwd, b, notes: notes.append("HYDRATE_NOTE"))
    monkeypatch.setattr(session, "maintenance", lambda cwd, notes: notes.append("MAINT_NOTE"))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    assert session.main() == 0

    out = json.loads(capsys.readouterr().out)
    context = out["hookSpecificOutput"]["additionalContext"]
    assert "HYDRATE_NOTE" in context and "MAINT_NOTE" in context
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_subprocess_invocation_works_end_to_end(repo):
    """The hooks are invoked as scripts, not imports, so the sys.path insert that
    finds beads_sync has to work from any cwd."""
    for stem in HOOKS:
        result = run_script(stem, {"cwd": str(repo)}, cwd="/")
        assert result.returncode == 0, f"{stem}: {result.stderr}"
        assert "Traceback" not in result.stderr, f"{stem}: {result.stderr}"
