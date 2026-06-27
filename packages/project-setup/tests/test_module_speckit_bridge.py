"""End-to-end tests for the speckit-bridge module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, after order, step)
  - spec_mode=none → skip, status ok
  - spec_mode=lightweight → specs/ dir created
  - spec_mode=lightweight --inspect → specs/ not created
  - spec_mode=full, apm absent or --version fails → error result with MISSING_REQUIRED_TOOL
  - spec_mode=full, apm present but install fails → error result with FETCH_FAILED

Tests use offline stubs for the apm binary to avoid network or tool dependencies.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_speckit_bridge.py
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
_MODULE_REL = "modules/speckit-bridge"


def _load(name: str):
    # Use a unique key per test file to avoid sys.modules collisions across test files.
    unique_name = f"_skbridge_{name}"
    spec = importlib.util.spec_from_file_location(unique_name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, spec_mode: str = "none") -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["speckit-bridge"],
        "modules": {
            "speckit-bridge": {
                "id": "speckit-bridge",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "spec_mode": spec_mode,
                },
                "steps": [{"id": "setup", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "setup"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def _make_apm_stub(bin_dir: Path, version_exit: int = 0, install_exit: int = 0) -> Path:
    """Write a bash apm stub to bin_dir/apm and make it executable."""
    stub = bin_dir / "apm"
    stub.write_text(
        f"#!/usr/bin/env bash\n"
        f'case "$1" in\n'
        f'    --version) echo "apm 0.99"; exit {version_exit} ;;\n'
        f'    install)   echo "install failed" >&2; exit {install_exit} ;;\n'
        f'    *)         exit 0 ;;\n'
        f'esac\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "speckit-bridge"
    assert mani.default_enabled is False
    assert mani.reconcile is False
    assert mani.order.get("after") == ["apm-install"]
    assert any(s.id == "setup" and s.kind == "python" for s in mani.steps)


def test_none_mode_skips(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="none")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "skipped" in result.get("message", "").lower()


def test_lightweight_creates_specs_dir(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="lightweight")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert (project / "specs").is_dir()


def test_lightweight_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="lightweight")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    assert not (project / "specs").exists()


def test_full_mode_apm_missing_emits_error_result(tmp_path):
    """spec_mode=full with a broken apm stub (exits 1 for --version) → MISSING_REQUIRED_TOOL."""
    project = tmp_path / "proj"
    project.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # apm stub: exits 1 for --version → _run_apm returns rc=1 → error result
    _make_apm_stub(stub_bin, version_exit=1)

    plan = _frozen_plan(tmp_path, spec_mode="full")
    # Prepend stub_bin so the module finds our broken apm first
    patched_path = f"{stub_bin}:{os.environ.get('PATH', '')}"
    proc = _run(project, plan, extra_env={"PATH": patched_path})
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    assert result["error"]["error_code"] == "MISSING_REQUIRED_TOOL"


def test_full_mode_apm_present_install_fails_emits_error_result(tmp_path):
    """spec_mode=full with apm --version ok but install failing → FETCH_FAILED."""
    project = tmp_path / "proj"
    project.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # apm stub: --version exits 0, install exits 1
    _make_apm_stub(stub_bin, version_exit=0, install_exit=1)

    plan = _frozen_plan(tmp_path, spec_mode="full")
    patched_path = f"{stub_bin}:{os.environ.get('PATH', '')}"
    proc = _run(project, plan, extra_env={"PATH": patched_path})
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    assert result["error"]["error_code"] == "FETCH_FAILED"
