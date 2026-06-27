"""End-to-end tests for the package-add module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, step)
  - creates packages/<name>/ on a clean run
  - --inspect writes nothing
  - existing dir → status ok, message contains "already exists"
  - path-traversal guards (security-pinned from old bats suite): slash, backslash,
    '..', '.', empty string, embedded '..' — all must be rejected BEFORE any mkdir
  - invalid lang → status error, message lists valid langs
  - workspace guidance appears in the success message

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_package_add.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/package-add"


def _load(name: str):
    # Use a unique key per test file to avoid sys.modules collisions across test files.
    unique_name = f"_pkg_add_{name}"
    spec = importlib.util.spec_from_file_location(unique_name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    name: str = "mylib",
    lang: str = "ts",
    dir: str = "packages",
) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["package-add"],
        "modules": {
            "package-add": {
                "id": "package-add",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "name": name,
                    "lang": lang,
                    "dir": dir,
                },
                "steps": [{"id": "add", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "add"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _assert_no_traversal_artifacts(project: Path, bad_name: str) -> None:
    """After a path-traversal rejection nothing must exist under packages/."""
    packages = project / "packages"
    if packages.exists():
        # The packages dir itself may pre-exist; but the bad sub-dir must not.
        assert not (packages / bad_name).exists(), (
            f"packages/{bad_name!r} was created despite rejection"
        )


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #

def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "package-add"
    assert mani.default_enabled is False
    assert mani.reconcile is False
    assert any(s.id == "add" and s.kind == "python" for s in mani.steps)


def test_creates_package_dir(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, name="mylib", lang="ts")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert (project / "packages" / "mylib").is_dir()


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, name="mylib", lang="ts")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    assert not (project / "packages" / "mylib").exists()


def test_existing_dir_skips(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "packages" / "mylib").mkdir(parents=True)
    plan = _frozen_plan(tmp_path, name="mylib", lang="ts")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "already exists" in result.get("message", "")


# --------------------------------------------------------------------------- #
# Path-traversal guard tests (security-pinned)                                 #
# --------------------------------------------------------------------------- #

def test_rejects_slash_in_name(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    bad_name = "foo/bar"
    plan = _frozen_plan(tmp_path, name=bad_name)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    msg = result.get("message", "") + result.get("error", {}).get("how_to_fix", "")
    assert "separator" in msg.lower() or "path" in msg.lower()
    _assert_no_traversal_artifacts(project, bad_name)


def test_rejects_backslash_in_name(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    bad_name = "foo\\bar"
    plan = _frozen_plan(tmp_path, name=bad_name)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    # Nothing created under project
    assert not (project / "packages").exists() or not (project / "packages" / bad_name).exists()


def test_rejects_dotdot_name(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    bad_name = ".."
    plan = _frozen_plan(tmp_path, name=bad_name)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    _assert_no_traversal_artifacts(project, bad_name)


def test_rejects_dot_name(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    bad_name = "."
    plan = _frozen_plan(tmp_path, name=bad_name)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    _assert_no_traversal_artifacts(project, bad_name)


def test_rejects_empty_name(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, name="")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    # No packages dir should be created at all
    assert not (project / "packages").exists()


def test_rejects_embedded_dotdot(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    bad_name = "foo..bar"
    plan = _frozen_plan(tmp_path, name=bad_name)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    _assert_no_traversal_artifacts(project, bad_name)


# --------------------------------------------------------------------------- #
# Lang validation                                                               #
# --------------------------------------------------------------------------- #

def test_lang_validation(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, name="mylib", lang="ruby")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    combined = result.get("message", "") + result.get("error", {}).get("how_to_fix", "")
    assert "ts" in combined
    assert "python" in combined
    assert "go" in combined
    assert "rust" in combined


# --------------------------------------------------------------------------- #
# Workspace guidance                                                            #
# --------------------------------------------------------------------------- #

def test_workspace_guidance_in_message(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, name="mylib", lang="python")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    message = result.get("message", "")
    assert (
        "pyproject.toml" in message
        or "uv.workspace" in message
        or "members" in message
    ), f"Workspace guidance not found in message: {message!r}"
