"""End-to-end tests for the core-identity module.

core-identity has no filesystem work. Its single step "record" is a no-op
confirmation that validates frozen inputs are loadable and emits a
files_written=[] result. Tests verify:
  - manifest parses and is valid
  - module runs successfully and emits empty files_written
  - --inspect also returns empty files_written (consistent with no work done)
  - idempotent: second run emits the same empty result

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_core_identity.py
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
_MODULE_REL = "modules/core-identity"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["core-identity"],
        "modules": {
            "core-identity": {
                "id": "core-identity",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "project_name": "my-project",
                    "org": "acme",
                    "description": "Test project",
                    "layout": "single",
                    "license": "apache-2.0",
                    "public": False,
                    "create_repo": True,
                    "init_git": True,
                },
                "steps": [{"id": "record", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "record"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "core-identity"
    assert mani.default_enabled is True
    assert mani.reconcile is False
    assert any(s.id == "record" and s.kind == "python" for s in mani.steps)
    # All 8 declared inputs present
    input_keys = {i.key for i in mani.inputs}
    assert input_keys == {
        "project_name", "org", "description", "layout",
        "license", "public", "create_repo", "init_git",
    }


def test_real_uv_run_no_files_written(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["module_id"] == "core-identity"
    assert result["status"] == "ok"
    assert result["files_written"] == []
    assert result["diffs"] == []
    # Nothing written to disk
    assert list(project.iterdir()) == []


def test_inspect_pass_also_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["files_written"] == []
    assert list(project.iterdir()) == []


def test_idempotent_second_run(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == []
