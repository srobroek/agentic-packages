"""End-to-end tests for the dirs-scaffold module.

Verifies:
  - manifest parses and is valid
  - single layout: exactly the 21 base dirs with .gitkeep, NO monorepo dirs
  - monorepo layout: base + 15 default targets, including apps/
  - custom targets: base + provided targets
  - --inspect writes nothing
  - idempotent: second run emits all-skip diffs (reconcile=true, files identical)
  - no apps/ dir in single layout (golden-fixture bats parity)

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_dirs_scaffold.py
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
_MODULE_REL = "modules/dirs-scaffold"

# Exact 21 base dirs from the legacy monolith (lines 265–286).
_BASE_DIRS = [
    ".codex",
    ".agents/hooks",
    ".github/workflows",
    "docs/architecture",
    "docs/decisions",
    "docs/research",
    "docs/runbooks",
    "docs/product",
    "docs/engineering",
    "docs/operations",
    "docs/api",
    "specs",
    "infrastructure/environments",
    "infrastructure/terraform/modules",
    "infrastructure/terraform/stacks",
    "infrastructure/terraform/environments",
    "tests",
    "scripts",
    "assets",
    "archive",
]

# 15 default monorepo targets (lines 289–305).
_MONOREPO_TARGETS = [
    "apps",
    "services",
    "functions",
    "workers",
    "libs/domain",
    "libs/application",
    "libs/adapters",
    "libs/config",
    "libs/testing",
    "libs/ui",
    "libs/types",
    "packages",
    "schemas",
    "data/shared",
    "tools",
]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, layout: str = "single", targets: list | None = None) -> Path:
    answers: dict = {"layout": layout}
    if targets is not None:
        answers["targets"] = targets
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["dirs-scaffold"],
        "modules": {
            "dirs-scaffold": {
                "id": "dirs-scaffold",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": answers,
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


def _gitkeep_paths(project: Path) -> set[str]:
    """Return all .gitkeep paths relative to project, using forward slashes."""
    return {
        str(p.relative_to(project)).replace(os.sep, "/")
        for p in project.rglob(".gitkeep")
    }


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "dirs-scaffold"
    assert mani.default_enabled is True
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert mani.order["requires"] == ["core-identity"]


def test_single_layout_creates_exact_21_dirs(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="single")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    expected = {f"{d}/.gitkeep" for d in _BASE_DIRS}
    assert _gitkeep_paths(project) == expected
    assert len(result["files_written"]) == len(_BASE_DIRS)


def test_single_layout_has_no_apps_dir(tmp_path):
    """Bats golden fixture: apps/ must not exist in single layout."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="single")
    _run(project, plan)
    assert not (project / "apps").exists()


def test_monorepo_layout_includes_default_targets(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="monorepo")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    expected = {f"{d}/.gitkeep" for d in _BASE_DIRS + _MONOREPO_TARGETS}
    assert _gitkeep_paths(project) == expected
    # apps/ is present in monorepo layout
    assert (project / "apps").exists()


def test_custom_targets_are_appended(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="single", targets=["my-custom", "another/nested"])
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    assert (project / "my-custom" / ".gitkeep").exists()
    assert (project / "another" / "nested" / ".gitkeep").exists()


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="single")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    # All diffs should be "create" previews but nothing on disk
    assert all(d["kind"] == "create" for d in result["diffs"])
    assert list(project.iterdir()) == []


def test_idempotent_second_run_all_skip(tmp_path):
    """reconcile=true: second run finds identical .gitkeep → all diffs are skip."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, layout="single")
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["files_written"] == []
    assert all(d["kind"] == "skip" for d in result["diffs"])
