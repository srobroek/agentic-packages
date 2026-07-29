"""Tests for the non-guard repo-local hooks.

These six hooks had no tests before the port. Each suite pins the behaviour that
made the hook worth keeping plus the fail-open contract, and several cases record a
defect the shell version carried.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(stem: str):
    """Import a hyphenated hook script as a module."""
    path = SCRIPTS / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def drive(module, payload, monkeypatch):
    """Run a hook's main() against a payload string."""
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return module.main()


ALL_STEMS = [
    "agent-metrics",
    "failure-logger",
    "session-end-prune",
    "post-merge-cleanup",
    "apm-outdated-check",
    "worktree-orphan-cleanup",
    "notify",
    "chezmoi-sync",
    "gh-rate-guard",
    "allow-chezmoi-apply",
]


# --- contract: every hook -------------------------------------------------


@pytest.mark.parametrize("stem", ALL_STEMS)
def test_every_hook_has_a_shebang(stem):
    first = (SCRIPTS / f"{stem}.py").read_text(encoding="utf-8").splitlines()[0]
    assert first == "#!/usr/bin/env python3"


@pytest.mark.parametrize("stem", ALL_STEMS)
def test_every_hook_is_executable(stem):
    assert os.access(SCRIPTS / f"{stem}.py", os.X_OK), f"{stem}.py must be chmod +x"


@pytest.mark.parametrize("stem", ALL_STEMS)
def test_every_hook_compiles(stem):
    path = SCRIPTS / f"{stem}.py"
    subprocess.run(["python3", "-m", "py_compile", str(path)], check=True)


@pytest.mark.parametrize("stem", ALL_STEMS)
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json", id="unparseable"),
        pytest.param("[]", id="not-an-object"),
        pytest.param("{}", id="empty-object"),
        pytest.param('{"tool_input": null}', id="null-tool-input"),
    ],
)
def test_no_hook_raises_on_a_malformed_payload(stem, payload, monkeypatch, capsys):
    """Fail open: a hook must never turn a bad payload into a crash."""
    module = load(stem)
    code = drive(module, payload, monkeypatch)
    capsys.readouterr()
    assert code in (0, 2)


@pytest.mark.parametrize("stem", ALL_STEMS)
def test_no_hook_shells_out_to_jq_or_awk(stem):
    """The point of the port: no hook parses JSON or tokenizes with a subprocess."""
    body = (SCRIPTS / f"{stem}.py").read_text(encoding="utf-8")
    for banned in ('"jq"', "'jq'", '"awk"', "'awk'", '"sed"', "'sed'"):
        assert banned not in body, f"{stem}.py still spawns {banned}"


# --- agent-metrics --------------------------------------------------------


def test_agent_metrics_writes_a_parseable_record(tmp_path, monkeypatch, capsys):
    module = load("agent-metrics")
    monkeypatch.setattr(module, "repo_root", lambda: str(tmp_path))
    payload = json.dumps({"agent_type": "coder", "agent_id": "a1"})
    assert drive(module, payload, monkeypatch) == 0
    capsys.readouterr()
    lines = (tmp_path / ".claude" / "metrics" / "agents.jsonl").read_text().splitlines()
    record = json.loads(lines[-1])
    assert record["agent_type"] == "coder"
    assert record["agent_id"] == "a1"
    assert record["timestamp"].endswith("Z")


def test_agent_metrics_quote_in_field_stays_parseable(tmp_path, monkeypatch, capsys):
    """The shell version interpolated fields into a hand-built JSON string, so a
    quote in agent_type produced a line no JSONL reader could parse."""
    module = load("agent-metrics")
    monkeypatch.setattr(module, "repo_root", lambda: str(tmp_path))
    payload = json.dumps({"agent_type": 'we"ird', "agent_id": "x"})
    drive(module, payload, monkeypatch)
    capsys.readouterr()
    line = (tmp_path / ".claude" / "metrics" / "agents.jsonl").read_text().splitlines()[-1]
    assert json.loads(line)["agent_type"] == 'we"ird'


def test_agent_metrics_defaults_missing_fields(tmp_path, monkeypatch, capsys):
    module = load("agent-metrics")
    monkeypatch.setattr(module, "repo_root", lambda: str(tmp_path))
    drive(module, "{}", monkeypatch)
    capsys.readouterr()
    record = json.loads(
        (tmp_path / ".claude" / "metrics" / "agents.jsonl").read_text().splitlines()[-1]
    )
    assert record["agent_type"] == "unknown"


# --- failure-logger ------------------------------------------------------


def test_failure_logger_writes_one_line(tmp_path, monkeypatch, capsys):
    module = load("failure-logger")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    payload = json.dumps({"tool_name": "Bash", "error": "boom", "cwd": "/x"})
    assert drive(module, payload, monkeypatch) == 0
    capsys.readouterr()
    content = (tmp_path / ".claude" / "debug" / "tool-failures.log").read_text()
    assert content.count("\n") == 1
    assert "Bash" in content and "boom" in content


def test_failure_logger_collapses_newlines(tmp_path, monkeypatch, capsys):
    """A multi-line error must not break the one-record-per-line format."""
    module = load("failure-logger")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    payload = json.dumps({"tool_name": "Bash", "error": "line1\nline2\nline3"})
    drive(module, payload, monkeypatch)
    capsys.readouterr()
    content = (tmp_path / ".claude" / "debug" / "tool-failures.log").read_text()
    assert content.count("\n") == 1
    assert "line1 line2 line3" in content


def test_failure_logger_truncates(tmp_path, monkeypatch, capsys):
    module = load("failure-logger")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    drive(module, json.dumps({"error": "x" * 5000}), monkeypatch)
    capsys.readouterr()
    content = (tmp_path / ".claude" / "debug" / "tool-failures.log").read_text()
    assert len(content) < 400


def test_failure_logger_rotates(tmp_path, monkeypatch, capsys):
    module = load("failure-logger")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    log = tmp_path / ".claude" / "debug" / "tool-failures.log"
    log.parent.mkdir(parents=True)
    log.write_text("x" * (module.ROTATE_BYTES + 1))
    drive(module, json.dumps({"tool_name": "T", "error": "e"}), monkeypatch)
    capsys.readouterr()
    assert (tmp_path / ".claude" / "debug" / "tool-failures.log.old").is_file()
    # The record that triggered rotation must survive in the rotated file.
    assert "T" in (tmp_path / ".claude" / "debug" / "tool-failures.log.old").read_text()


# --- post-merge-cleanup --------------------------------------------------


def test_post_merge_ignores_a_failed_merge(monkeypatch):
    module = load("post-merge-cleanup")
    called = []
    monkeypatch.setattr(module, "git", lambda *a, **k: called.append(a) or None)
    payload = json.dumps(
        {
            "tool_input": {"command": "git merge worktree-worktree-123"},
            "tool_result": {"exit_code": 1},
        }
    )
    assert drive(module, payload, monkeypatch) == 0
    assert called == [], "a failed merge must not delete anything"


def test_post_merge_ignores_an_unrelated_branch(monkeypatch):
    module = load("post-merge-cleanup")
    called = []
    monkeypatch.setattr(module, "git", lambda *a, **k: called.append(a) or None)
    payload = json.dumps({"tool_input": {"command": "git merge main"}})
    drive(module, payload, monkeypatch)
    assert called == []


def test_post_merge_branch_pattern_is_anchored():
    module = load("post-merge-cleanup")
    assert module.BRANCH_PATTERN.search("git merge worktree-worktree-42")
    assert not module.BRANCH_PATTERN.search("git merge worktree-worktree-abc")
    assert not module.BRANCH_PATTERN.search("git merge feature/worktree")


def test_post_merge_parses_porcelain_records(monkeypatch):
    """The shell version used `grep -B1`, assuming the path sits one line above the
    branch line. A detached or bare entry breaks that adjacency and could return
    the wrong worktree's path -- which was then force-removed."""
    module = load("post-merge-cleanup")
    porcelain = (
        "worktree /tmp/other\n"
        "HEAD 1111111\n"
        "detached\n"
        "\n"
        "worktree /tmp/wanted\n"
        "HEAD 2222222\n"
        "branch refs/heads/worktree-worktree-9\n"
        "\n"
    )

    class Result:
        returncode = 0
        stdout = porcelain

    monkeypatch.setattr(module, "git", lambda *a, **k: Result())
    assert module.worktree_for("/repo", "worktree-worktree-9") == "/tmp/wanted"


def test_post_merge_unknown_branch_yields_no_path(monkeypatch):
    module = load("post-merge-cleanup")

    class Result:
        returncode = 0
        stdout = "worktree /tmp/a\nbranch refs/heads/main\n\n"

    monkeypatch.setattr(module, "git", lambda *a, **k: Result())
    assert module.worktree_for("/repo", "worktree-worktree-9") == ""


# --- session-end-prune --------------------------------------------------


def test_prune_skips_subagents(monkeypatch):
    module = load("session-end-prune")
    called = []
    monkeypatch.setattr(module, "git", lambda *a, **k: called.append(a) or None)
    assert drive(module, json.dumps({"agent_id": "sub"}), monkeypatch) == 0
    assert called == []


def test_prune_returns_none_when_porcelain_fails(monkeypatch):
    """None, not an empty set: an empty set would read as 'nothing checked out' and
    make every orphan branch a deletion candidate."""
    module = load("session-end-prune")

    class Failed:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(module, "git", lambda *a, **k: Failed())
    assert module.checked_out_branches("/repo") is None


def test_prune_collects_checked_out_branches(monkeypatch):
    module = load("session-end-prune")

    class Result:
        returncode = 0
        stdout = "worktree /a\nbranch refs/heads/main\n\nworktree /b\nbranch refs/heads/worktree-1\n"

    monkeypatch.setattr(module, "git", lambda *a, **k: Result())
    assert module.checked_out_branches("/repo") == {"main", "worktree-1"}


def test_prune_uses_safe_delete_only():
    """-d refuses to drop unmerged commits; -D would destroy them silently."""
    body = (SCRIPTS / "session-end-prune.py").read_text(encoding="utf-8")
    assert '"-D"' not in body


# --- apm-outdated-check -------------------------------------------------


def test_outdated_skips_subagents(monkeypatch):
    module = load("apm-outdated-check")
    assert drive(module, json.dumps({"agent_id": "sub"}), monkeypatch) == 0


def test_outdated_state_filename_is_platform_stable():
    """The shell version derived it from `md5 || md5sum | cut`, which produced a
    different filename on macOS than on Linux for the same repository."""
    import hashlib

    a = hashlib.md5(b"/repo/x", usedforsecurity=False).hexdigest()
    b = hashlib.md5(b"/repo/x", usedforsecurity=False).hexdigest()
    assert a == b and len(a) == 32


def test_outdated_exit_two_is_documented():
    """asyncRewake delivers stderr to the agent only on exit 2."""
    body = (SCRIPTS / "apm-outdated-check.py").read_text(encoding="utf-8")
    assert "return 2" in body


# --- worktree-orphan-cleanup -------------------------------------------


def test_orphan_cleanup_skips_subagents(monkeypatch):
    module = load("worktree-orphan-cleanup")
    assert drive(module, json.dumps({"agent_id": "sub"}), monkeypatch) == 0


def test_orphan_cleanup_leaves_live_pids_alone(tmp_path, monkeypatch):
    module = load("worktree-orphan-cleanup")
    live = tmp_path / "repo" / f"worktree-{os.getpid()}"
    (live / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(module, "BASES", (str(tmp_path),))
    drive(module, "{}", monkeypatch)
    assert (live / "node_modules").is_dir(), "a running session must not be cleaned"


def test_orphan_cleanup_removes_dead_pid_artifacts(tmp_path, monkeypatch):
    module = load("worktree-orphan-cleanup")
    dead = tmp_path / "repo" / "worktree-999999"
    (dead / "node_modules").mkdir(parents=True)
    (dead / ".venv").mkdir()
    (dead / "keep.txt").write_text("keep")
    monkeypatch.setattr(module, "BASES", (str(tmp_path),))
    monkeypatch.setattr(module, "alive", lambda pid: False)
    drive(module, "{}", monkeypatch)
    assert not (dead / "node_modules").exists()
    assert not (dead / ".venv").exists()
    assert (dead / "keep.txt").is_file(), "only build output is removed"


def test_orphan_cleanup_ignores_non_numeric_suffix(tmp_path, monkeypatch):
    module = load("worktree-orphan-cleanup")
    odd = tmp_path / "repo" / "worktree-notapid"
    (odd / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(module, "BASES", (str(tmp_path),))
    monkeypatch.setattr(module, "alive", lambda pid: False)
    drive(module, "{}", monkeypatch)
    assert (odd / "node_modules").is_dir()


def test_prune_does_not_follow_a_symlink(tmp_path):
    """`find -exec rm -r` followed a symlinked __pycache__, so a planted link could
    delete outside the worktree. rmtree does not, and prune() refuses outright."""
    module = load("worktree-orphan-cleanup")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep")
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    module.prune(link)
    assert (outside / "precious.txt").is_file()
    assert link.is_symlink()


# --- notify -------------------------------------------------------------


def test_notify_is_a_noop_off_darwin(monkeypatch):
    module = load("notify")
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert drive(module, json.dumps({"message": "hi"}), monkeypatch) == 0


def test_notify_suppresses_when_own_app_is_frontmost(monkeypatch):
    module = load("notify")
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setenv("__CFBundleIdentifier", "com.github.wez.wezterm")
    monkeypatch.setattr(module, "frontmost", lambda: "com.github.wez.wezterm")
    calls = []
    monkeypatch.setattr("subprocess.run", lambda *a, **k: calls.append(a))
    assert drive(module, json.dumps({"message": "hi"}), monkeypatch) == 0
    assert calls == []


def test_notify_maps_term_program_to_bundle_id():
    module = load("notify")
    assert module.BUNDLE_IDS["ghostty"] == "com.mitchellh.ghostty"


# --- chezmoi-sync ------------------------------------------------------


def test_chezmoi_sync_never_runs_a_write_command():
    """ADVISORY ONLY is the whole contract: no add, commit, stage, or push."""
    body = (SCRIPTS / "chezmoi-sync.py").read_text(encoding="utf-8")
    for banned in ('"add"', '"commit"', '"push"', '"re-add"', '"apply"'):
        assert banned not in body, f"chezmoi-sync must not invoke {banned}"


def test_chezmoi_sync_recognises_a_dot_directory_file():
    """The shell version tested `[[ "$relative" == .*//* ]]`, needing a literal
    double slash, so this branch never fired and ~/.ssh/config went unrecognised."""
    module = load("chezmoi-sync")
    assert module.is_config_path(Path(".ssh/config"))
    assert module.is_config_path(Path(".config/fish/config.fish"))
    assert module.is_config_path(Path(".zshrc"))
    assert not module.is_config_path(Path("Documents/notes.txt"))


def test_chezmoi_sync_ignores_known_noise():
    module = load("chezmoi-sync")
    home = Path("/home/u")
    assert module.is_ignored(home / ".cache/x", Path(".cache/x"), "")
    assert module.is_ignored(home / ".local/share/y", Path(".local/share/y"), "")
    assert module.is_ignored(home / ".config/a.swp", Path(".config/a.swp"), "")
    assert not module.is_ignored(home / ".config/fish/config.fish", Path(".config/fish/config.fish"), "")


def test_chezmoi_sync_skips_missing_file(monkeypatch, capsys):
    module = load("chezmoi-sync")
    payload = json.dumps({"tool_input": {"file_path": "/nonexistent/nope.conf"}})
    assert drive(module, payload, monkeypatch) == 0
    assert capsys.readouterr().out == ""


def test_chezmoi_sync_skips_project_dirs(tmp_path, monkeypatch, capsys):
    module = load("chezmoi-sync")
    project = tmp_path / "personal" / "dev" / "x.toml"
    project.parent.mkdir(parents=True)
    project.write_text("x = 1")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    called = []
    monkeypatch.setattr(module, "chezmoi", lambda *a: called.append(a) or "")
    payload = json.dumps({"tool_input": {"file_path": str(project)}})
    assert drive(module, payload, monkeypatch) == 0
    assert called == [], "project files must bail before chezmoi is consulted"
    assert capsys.readouterr().out == ""


def test_chezmoi_sync_recognises_config_names():
    module = load("chezmoi-sync")
    assert module.looks_like_config("settings.json")
    assert module.looks_like_config(".gitconfig")
    assert module.looks_like_config("foo.toml")
    assert module.looks_like_config(".zshrc")
    assert not module.looks_like_config("photo.png")
