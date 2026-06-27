"""End-to-end tests for the quality-hooks module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, after order, step)
  - empty quality_languages list → skip, no file written
  - languages are sorted and deduplicated
  - --inspect writes nothing
  - second run is idempotent (all-skip diffs)
  - reconcile=true: stale file is overwritten on re-run

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_quality_hooks.py
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
_MODULE_REL = "modules/quality-hooks"


def _load(name: str):
    # Use a unique key per test file to avoid sys.modules collisions across test files.
    unique_name = f"_qhooks_{name}"
    spec = importlib.util.spec_from_file_location(unique_name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, quality_languages: list[str] | None = None) -> Path:
    if quality_languages is None:
        quality_languages = []
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["quality-hooks"],
        "modules": {
            "quality-hooks": {
                "id": "quality-hooks",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "quality_languages": quality_languages,
                },
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
    assert mani.id == "quality-hooks"
    assert mani.default_enabled is False
    assert mani.reconcile is True
    assert mani.order.get("after") == ["dirs-scaffold"]
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)


def test_empty_list_skips(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, quality_languages=[])
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result.get("files_written", []) == []
    assert "skipped" in result.get("message", "").lower()
    assert not (project / ".agents" / "hooks" / "quality-languages").exists()


def test_writes_sorted_unique_languages(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, quality_languages=["ts", "python", "ts"])
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert ".agents/hooks/quality-languages" in result.get("files_written", [])
    content = (project / ".agents" / "hooks" / "quality-languages").read_text()
    assert content == "python\nts\n"


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, quality_languages=["ts"])
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    assert not (project / ".agents" / "hooks" / "quality-languages").exists()


def test_idempotent_second_run(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, quality_languages=["ts", "python"])
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result.get("files_written", []) == []


def test_reconcile_updates_stale_file(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    hooks_dir = project / ".agents" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "quality-languages").write_text("go\n")
    plan = _frozen_plan(tmp_path, quality_languages=["ts"])
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    content = (hooks_dir / "quality-languages").read_text()
    assert content == "ts\n"
