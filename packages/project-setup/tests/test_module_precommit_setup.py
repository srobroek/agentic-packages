"""End-to-end tests for the precommit-setup module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, after order)
  - .pre-commit-config.yaml is created with the exact expected hooks present
    (gitleaks pre-push, cocogitto commit-msg, normalize-close-keywords local hook)
  - .pre-commit-hooks/ scripts are vendored and executable
  - --inspect writes nothing
  - reconcile=true: second run with identical content → all-skip diffs
  - reconcile=true: second run after content change → modifies the file

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_precommit_setup.py
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
_MODULE_REL = "modules/precommit-setup"
_TEMPLATES = _PLUGIN_ROOT / _MODULE_REL / "templates"


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
        "order": ["precommit-setup"],
        "modules": {
            "precommit-setup": {
                "id": "precommit-setup",
                "version": "1.0.0",
                "reconcile": True,
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
    assert mani.id == "precommit-setup"
    assert mani.default_enabled is False
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert mani.order.get("after") == ["dirs-scaffold"]


def test_creates_precommit_config(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert ".pre-commit-config.yaml" in result["files_written"]

    cfg_path = project / ".pre-commit-config.yaml"
    assert cfg_path.exists()


def test_precommit_config_has_required_hooks(tmp_path):
    """The config must contain the gitleaks pre-push hook, cocogitto commit-msg hook,
    and the normalize-close-keywords local hook."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan)

    content = (project / ".pre-commit-config.yaml").read_text()

    # gitleaks at pre-push
    assert "gitleaks/gitleaks" in content
    assert "stages: [pre-push]" in content

    # cocogitto at commit-msg
    assert "cocogitto-verify" in content
    assert "stages: [commit-msg]" in content

    # normalize-close-keywords local hook
    assert "normalize-close-keywords" in content
    assert ".pre-commit-hooks/commit-msg-rewrite.sh" in content
    assert "always_run: true" in content

    # exclude pattern
    assert "exclude:" in content
    assert r"\.specify/" in content


def test_close_keywords_scripts_vendored(tmp_path):
    """commit-msg-rewrite.sh and normalize-closes.sh must be written into .pre-commit-hooks/."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)

    rewrite = project / ".pre-commit-hooks" / "commit-msg-rewrite.sh"
    normalize = project / ".pre-commit-hooks" / "normalize-closes.sh"

    assert rewrite.exists(), f"commit-msg-rewrite.sh missing; warnings={result.get('warnings')}"
    assert normalize.exists(), f"normalize-closes.sh missing; warnings={result.get('warnings')}"

    # Scripts must be executable
    assert rewrite.stat().st_mode & stat.S_IXUSR, "commit-msg-rewrite.sh is not executable"
    assert normalize.stat().st_mode & stat.S_IXUSR, "normalize-closes.sh is not executable"

    # Content must not be empty and must start with shebang
    assert rewrite.read_text().startswith("#!/usr/bin/env bash")
    assert normalize.read_text().startswith("#!/usr/bin/env bash")


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)

    # All diffs should be "create" previews
    assert all(d["kind"] == "create" for d in result["diffs"])
    # Nothing written to disk
    assert not (project / ".pre-commit-config.yaml").exists()
    assert not (project / ".pre-commit-hooks").exists()


def test_idempotent_second_run_all_skip(tmp_path):
    """reconcile=true: second run with identical files → all diffs are skip."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["files_written"] == []
    assert all(d["kind"] == "skip" for d in result["diffs"])


def test_reconcile_overwrites_stale_config(tmp_path):
    """reconcile=true: if an existing .pre-commit-config.yaml differs, it is overwritten."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path)

    # Write a stale version
    cfg = project / ".pre-commit-config.yaml"
    cfg.write_text("# stale config\n")

    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)

    # Should have modified the file
    config_diffs = [d for d in result["diffs"] if d["path"] == ".pre-commit-config.yaml"]
    assert config_diffs, "Expected a diff for .pre-commit-config.yaml"
    assert config_diffs[0]["kind"] == "modify"

    # Content is now the real template
    assert "gitleaks" in cfg.read_text()
