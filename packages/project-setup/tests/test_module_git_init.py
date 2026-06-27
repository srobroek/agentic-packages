"""End-to-end tests for the git-init module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, step)
  - .git/ dir is created when absent (stub git)
  - skips when .git/ already exists
  - skips entirely when init_git=False
  - --inspect writes nothing
  - missing git binary warns and continues (status=ok)
  - non-writable .git/ emits status="error" with require_escalated how_to_fix

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_git_init.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/git-init"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, *, init_git: bool = True) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["git-init"],
        "modules": {
            "git-init": {
                "id": "git-init",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {"init_git": init_git},
                "steps": [{"id": "init", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "init"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def _make_stub_git(bin_dir: Path) -> Path:
    """Write a stub git that creates a .git/ dir on 'git init' and returns 0."""
    git_stub = bin_dir / "git"
    git_stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "init" ]; then mkdir -p .git; exit 0; fi\n'
        "exit 0\n"
    )
    git_stub.chmod(git_stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return git_stub


# ── tests ────────────────────────────────────────────────────────────────── #


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "git-init"
    assert mani.default_enabled is True
    assert mani.reconcile is False
    assert any(s.id == "init" and s.kind == "python" for s in mani.steps)


def test_creates_git_dir_when_absent(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    _make_stub_git(stub_bin)
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    plan = _frozen_plan(tmp_path, init_git=True)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert (project / ".git").exists()


def test_skips_when_git_already_exists(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".git").mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    _make_stub_git(stub_bin)
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    plan = _frozen_plan(tmp_path, init_git=True)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    # .git still exists (was pre-created, not destroyed)
    assert (project / ".git").exists()


def test_skips_when_init_git_false(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, init_git=False)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "skipped" in result.get("message", "").lower()
    assert not (project / ".git").exists()


def test_inspect_writes_nothing(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    _make_stub_git(stub_bin)
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    plan = _frozen_plan(tmp_path, init_git=True)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    # --inspect must not create .git on disk
    assert not (project / ".git").exists()


def test_git_missing_warns_and_continues(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    # Provide a PATH that has no git binary
    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", f"{empty_bin}:{os.environ.get('PATH', '')}")

    plan = _frozen_plan(tmp_path, init_git=True)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    warnings = result.get("warnings", [])
    assert any("git" in w.lower() for w in warnings), (
        f"Expected a warning about git not found, got: {warnings}"
    )


def test_codex_preflight_readonly_emits_error_result(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()

    # Pre-create a .git dir then make it non-writable (simulates Codex sandbox)
    git_dir = project / ".git"
    git_dir.mkdir()
    original_mode = git_dir.stat().st_mode
    os.chmod(str(git_dir), 0o444)

    try:
        plan = _frozen_plan(tmp_path, init_git=True)
        proc = _run(project, plan)
        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["status"] == "error", (
            f"Expected status=error for read-only .git, got: {result}"
        )
        error = result.get("error", {})
        how_to_fix = error.get("how_to_fix", "")
        assert "require_escalated" in how_to_fix, (
            f"Expected 'require_escalated' in how_to_fix, got: {how_to_fix!r}"
        )
    finally:
        os.chmod(str(git_dir), original_mode)
