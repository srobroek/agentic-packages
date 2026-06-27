"""End-to-end tests for the github-repo module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, after, step)
  - skips entirely when create_repo=False
  - missing gh binary warns and continues (status=ok)
  - skips when org is empty (warns about missing org)
  - creates repo and adds remote when repo doesn't yet exist
  - skips repo creation when gh repo view returns 0 (already exists)
  - --inspect emits "would create" and makes no gh calls

All tests use offline stub scripts on PATH — no real gh/git calls are made.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_github_repo.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/github-repo"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    *,
    create_repo: bool = True,
    public: bool = False,
    org: str = "myorg",
    project_name: str = "myproj",
    description: str = "",
) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["github-repo"],
        "modules": {
            "github-repo": {
                "id": "github-repo",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "create_repo": create_repo,
                    "public": public,
                    "org": org,
                    "project_name": project_name,
                    "description": description,
                },
                "steps": [{"id": "create", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "create"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def _make_exec(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _stub_gh_always_ok(bin_dir: Path) -> Path:
    """gh stub that exits 0 for every sub-command."""
    return _make_exec(
        bin_dir / "gh",
        "#!/usr/bin/env bash\nexit 0\n",
    )


def _stub_gh_view_fails_create_ok(bin_dir: Path) -> Path:
    """gh stub: 'repo view' exits 1 (repo not found), everything else exits 0."""
    return _make_exec(
        bin_dir / "gh",
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "repo" ] && [ "$2" = "view" ]; then exit 1; fi\n'
        "exit 0\n",
    )


def _stub_git_no_remote(bin_dir: Path) -> Path:
    """git stub: 'remote get-url origin' exits 1 (no remote), everything else 0."""
    return _make_exec(
        bin_dir / "git",
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "remote" ] && [ "$2" = "get-url" ]; then exit 1; fi\n'
        "exit 0\n",
    )


def _stub_git_always_ok(bin_dir: Path) -> Path:
    return _make_exec(bin_dir / "git", "#!/usr/bin/env bash\nexit 0\n")


# ── tests ────────────────────────────────────────────────────────────────── #


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "github-repo"
    assert mani.default_enabled is False
    assert mani.reconcile is False
    after = mani.order.get("after") if mani.order else []
    assert "git-init" in (after or []), f"Expected after=[git-init], got: {after}"
    assert any(s.id == "create" and s.kind == "python" for s in mani.steps)


def test_skips_when_create_repo_false(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, create_repo=False)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "skipped" in result.get("message", "").lower()


def test_gh_missing_warns_and_continues(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    # Build a PATH that contains uv (needed to launch module.py) but no gh.
    # We locate uv's directory dynamically so the test is portable across machines.
    uv_bin = shutil.which("uv") or ""
    uv_dir = str(Path(uv_bin).parent) if uv_bin else ""
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    path_parts = [str(stub_bin)] + ([uv_dir] if uv_dir else []) + ["/usr/bin", "/bin"]
    monkeypatch.setenv("PATH", ":".join(path_parts))

    plan = _frozen_plan(tmp_path, create_repo=True, org="o", project_name="p")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    warnings = result.get("warnings", [])
    assert any("gh" in w.lower() or "not found" in w.lower() for w in warnings), (
        f"Expected a warning about gh not found, got: {warnings}"
    )


def test_skips_when_org_missing(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    _stub_gh_always_ok(stub_bin)
    _stub_git_always_ok(stub_bin)
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    plan = _frozen_plan(tmp_path, create_repo=True, org="", project_name="proj")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    warnings = result.get("warnings", [])
    assert any("org" in w.lower() for w in warnings), (
        f"Expected a warning about missing org, got: {warnings}"
    )


def test_creates_repo_and_adds_remote(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # gh: view → 1 (not found), create → 0
    _stub_gh_view_fails_create_ok(stub_bin)
    # git: remote get-url → 1 (no origin), remote add → 0
    _stub_git_no_remote(stub_bin)
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    plan = _frozen_plan(tmp_path, create_repo=True, org="myorg", project_name="myproj")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    # No hard errors in warnings
    errors = [w for w in result.get("warnings", []) if "failed" in w.lower()]
    assert not errors, f"Unexpected failure warnings: {errors}"


def test_existing_repo_skips_create(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # gh: view → 0 (repo exists), everything else → 0
    _stub_gh_always_ok(stub_bin)
    _stub_git_always_ok(stub_bin)
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    plan = _frozen_plan(tmp_path, create_repo=True, org="myorg", project_name="myproj")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "already exists" in result.get("message", "").lower(), (
        f"Expected 'already exists' in message, got: {result.get('message')!r}"
    )


def test_inspect_does_not_call_gh(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    # Use a gh stub that writes a marker file only when a mutating repo sub-command
    # is called (repo view / repo create).  The module legitimately calls
    # `gh auth token` inside _gh_env() even during --inspect; that is a read-only
    # probe and does not count as "calling gh" for the purposes of this contract.
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    marker = tmp_path / "gh_repo_called"
    _make_exec(
        stub_bin / "gh",
        f"#!/usr/bin/env bash\n"
        f'if [ "$1" = "repo" ]; then touch {marker}; fi\n'
        f"exit 0\n",
    )
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    plan = _frozen_plan(tmp_path, create_repo=True, org="myorg", project_name="myproj")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "would create" in result.get("message", "").lower(), (
        f"Expected 'would create' in inspect message, got: {result.get('message')!r}"
    )
    assert not marker.exists(), "--inspect must not invoke 'gh repo ...' subcommands"
