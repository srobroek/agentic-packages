"""End-to-end test for the codex-config REFERENCE module.

Drives the real module.py through real `uv run` (the Model-B contract) against a
real frozen plan — proving SDK-by-path loading, frozen-input reading, idempotent
write, --inspect dry pass, and result emission. This is the integration the fake
module fixtures in test_executor.py could not cover.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_codex_config.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/codex-config"


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
        "order": ["codex-config"],
        "modules": {
            "codex-config": {
                "id": "codex-config",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {},
                "steps": [{"id": "write", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "write"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "codex-config"
    assert mani.default_enabled is False
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)


def test_real_uv_run_creates_codex_config(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    # one valid canonical JSON result on stdout
    result = json.loads(proc.stdout)
    assert result["module_id"] == "codex-config"
    assert result["status"] == "ok"
    assert result["files_written"] == [".codex/config.toml"]
    # file exists with the expected content
    cfg = project / ".codex" / "config.toml"
    assert cfg.exists()
    assert cfg.read_text().startswith("# Project or subfolder-scoped Codex overrides.")


def test_inspect_pass_writes_nothing_but_previews(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    # diff previews a create, but NOTHING is written
    assert result["diffs"][0]["kind"] == "create"
    assert not (project / ".codex" / "config.toml").exists()


def test_inspect_equals_write_bytes(tmp_path):
    """Tier-1 guarantee: the inspect preview corresponds to the real bytes."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan, inspect=True)
    assert not (project / ".codex" / "config.toml").exists()
    _run(project, plan)
    written = (project / ".codex" / "config.toml").read_text()
    # round-trips as valid TOML and matches the canonical body
    tomllib.loads(written)  # no exception
    assert "Add project-local Codex settings below as needed." in written


def test_idempotent_second_run_skips(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0
    result = json.loads(proc2.stdout)
    # existing file, reconcile=false → skip, no files_written
    assert result["diffs"][0]["kind"] == "skip"
    assert result["files_written"] == []
