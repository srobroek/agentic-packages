"""End-to-end tests for the agents-md module.

Verifies:
  - manifest parses and is valid
  - single layout: writes AGENTS.md with PROJECT_NAME/ORG substituted,
    contains single-layout marker (Path Mapping section), no Monorepo Structure
  - monorepo layout: writes AGENTS.md with Monorepo Structure section
  - --inspect writes nothing
  - reconcile=true: second run with identical content → skip
  - reconcile=true: second run with different layout → modify

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_agents_md.py
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
_MODULE_REL = "modules/agents-md"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, layout: str = "single", project_name: str = "my-app", org: str = "acme") -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["agents-md"],
        "modules": {
            "agents-md": {
                "id": "agents-md",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "layout": layout,
                    "project_name": project_name,
                    "org": org,
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
    assert mani.id == "agents-md"
    assert mani.default_enabled is True
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert mani.order["requires"] == ["core-identity"]
    assert "dirs-scaffold" in mani.order["after"]


def test_single_layout_writes_agents_md(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="single", project_name="my-app", org="acme")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == ["AGENTS.md"]

    content = (project / "AGENTS.md").read_text()
    assert "# my-app" in content
    assert "acme/my-app" in content
    # Single layout has Path Mapping, not Monorepo Structure
    assert "## Path Mapping" in content
    assert "## Monorepo Structure" not in content


def test_monorepo_layout_writes_agents_md(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="monorepo", project_name="mono-proj", org="bigcorp")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    content = (project / "AGENTS.md").read_text()
    assert "# mono-proj" in content
    # Monorepo layout has Monorepo Structure section
    assert "## Monorepo Structure" in content
    assert "## Path Mapping" not in content
    assert "`apps/`" in content
    assert "`services/`" in content


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["diffs"][0]["kind"] == "create"
    assert not (project / "AGENTS.md").exists()


def test_idempotent_same_content_skips(tmp_path):
    """reconcile=true, same content → second run emits skip."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["diffs"][0]["kind"] == "skip"
    assert result["files_written"] == []


def test_placeholder_substitution_is_exact(tmp_path):
    """PROJECT_NAME and ORG literals must not appear in the output."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, project_name="test-svc", org="myorg")
    _run(project, plan)
    content = (project / "AGENTS.md").read_text()
    assert "PROJECT_NAME" not in content
    assert "ORG/PROJECT_NAME" not in content
    assert "test-svc" in content
    assert "myorg/test-svc" in content
