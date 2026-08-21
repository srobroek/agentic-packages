"""Unit tests for check-script-invocation.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).with_name("check-script-invocation.py")

spec = importlib.util.spec_from_file_location("check_script_invocation", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def git(root: Path, *args: str) -> None:
    # -c overrides, not `git config`, because the fixture must not inherit the
    # developer's ambient git config. A global commit.gpgsign made every commit
    # here fail with "1Password: Could not connect to socket" whenever the agent
    # was not running, and the fixture commit has nothing to sign for.
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "packages" / "demo" / "hooks").mkdir(parents=True)
    (root / "packages" / "demo" / "scripts").mkdir(parents=True)
    git(root.parent, "init", "-q", root.name)
    git(root, "config", "user.email", "t@example.test")
    git(root, "config", "user.name", "test")
    return root


def write_hook(root: Path, command: str) -> None:
    config = root / "packages" / "demo" / "hooks" / "claude-hooks.json"
    config.write_text(
        json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]}}),
        encoding="utf-8",
    )


def add_script(root: Path, name: str, *, executable: bool) -> Path:
    path = root / "packages" / "demo" / "scripts" / name
    path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    path.chmod(0o755 if executable else 0o644)
    return path


def commit(root: Path) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")


def test_bare_path_to_non_executable_is_reported(tmp_path):
    root = make_repo(tmp_path)
    add_script(root, "guard.sh", executable=False)
    write_hook(root, "${PLUGIN_ROOT}/scripts/guard.sh")
    commit(root)

    problems = module.check(root)
    assert len(problems) == 1
    assert "guard.sh" in problems[0]
    assert "100644" in problems[0]


def test_bare_path_to_executable_is_clean(tmp_path):
    root = make_repo(tmp_path)
    add_script(root, "guard.sh", executable=True)
    write_hook(root, "${PLUGIN_ROOT}/scripts/guard.sh")
    commit(root)

    assert module.check(root) == []


def test_interpreter_prefix_exempts_a_non_executable(tmp_path):
    root = make_repo(tmp_path)
    add_script(root, "guard.py", executable=False)
    write_hook(root, 'cd "${CLAUDE_PROJECT_DIR:-.}" && uv run --quiet ${PLUGIN_ROOT}/scripts/guard.py')
    commit(root)

    assert module.check(root) == []


def test_python3_prefix_exempts_a_non_executable(tmp_path):
    root = make_repo(tmp_path)
    add_script(root, "guard.py", executable=False)
    write_hook(root, "python3 ${PLUGIN_ROOT}/scripts/guard.py")
    commit(root)

    assert module.check(root) == []


def write_skill(root: Path, body: str) -> None:
    skill = root / "packages" / "demo" / ".apm" / "skills" / "demo"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(body, encoding="utf-8")


def test_markdown_runtime_path_to_non_executable_is_reported(tmp_path):
    root = make_repo(tmp_path)
    add_script(root, "bind.py", executable=False)
    write_skill(root, "Run `.claude/hooks/demo/scripts/bind.py bind {id}`.\n")
    commit(root)

    problems = module.check(root)
    assert len(problems) == 1
    assert "SKILL.md:1" in problems[0]


def test_markdown_runtime_path_under_interpreter_is_clean(tmp_path):
    root = make_repo(tmp_path)
    add_script(root, "bind.py", executable=False)
    write_skill(root, "Run `uv run --quiet .claude/hooks/demo/scripts/bind.py bind {id}`.\n")
    commit(root)

    assert module.check(root) == []


def test_untracked_source_is_ignored(tmp_path):
    root = make_repo(tmp_path)
    add_script(root, "guard.sh", executable=False)
    write_hook(root, "${PLUGIN_ROOT}/scripts/guard.sh")
    # no commit: nothing is in the index, so nothing is a shipped contract yet
    assert module.check(root) == []


def test_repo_itself_passes():
    root = Path(__file__).resolve().parents[2]
    assert module.check(root) == []
