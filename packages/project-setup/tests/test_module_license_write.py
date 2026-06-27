"""End-to-end tests for the license-write module.

SC-001 carve-out: year and author lines vary at runtime. Tests exclude those
lines from byte-identical assertions and verify only the stable body portions.

Verifies:
  - manifest parses and is valid
  - apache-2.0 license: writes LICENSE, stable body matches template
  - mit license: writes LICENSE, stable body matches template
  - --inspect writes nothing
  - reconcile=false: second run skips (write-if-absent)
  - explicit author input overrides git config

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_license_write.py
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
_MODULE_REL = "modules/license-write"
_TEMPLATES = _PLUGIN_ROOT / _MODULE_REL / "templates"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, license_type: str = "apache-2.0", author: str = "") -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["license-write"],
        "modules": {
            "license-write": {
                "id": "license-write",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {"license": license_type, "author": author},
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


def _stable_lines(text: str, license_type: str) -> list[str]:
    """Return lines that are NOT the SC-001 year/author carve-out lines."""
    skip_fragments: list[str]
    if license_type in ("apache-2.0", "apache"):
        # The Apache template has "Copyright {YEAR} {AUTHOR}" line
        skip_fragments = ["Copyright "]
    else:
        # MIT has "Copyright (c) {YEAR} {AUTHOR}"
        skip_fragments = ["Copyright (c)"]
    return [
        line for line in text.splitlines()
        if not any(frag in line for frag in skip_fragments)
    ]


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "license-write"
    assert mani.default_enabled is True
    assert mani.reconcile is False
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert mani.order["requires"] == ["core-identity"]


def test_apache_license_written(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="apache-2.0", author="Test Author")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == ["LICENSE"]

    written = (project / "LICENSE").read_text()
    # SC-001 carve-out: exclude the copyright line from byte comparison.
    template_raw = (_TEMPLATES / "apache-2.0.txt").read_text()
    template_stable = _stable_lines(
        template_raw.replace("{YEAR}", "YEAR_PLACEHOLDER").replace("{AUTHOR}", "AUTHOR_PLACEHOLDER"),
        "apache-2.0",
    )
    written_stable = _stable_lines(written, "apache-2.0")
    assert written_stable == template_stable

    # Runtime substitution happened
    assert "Test Author" in written
    assert "{YEAR}" not in written
    assert "{AUTHOR}" not in written
    # Content includes the Apache header
    assert "Apache License" in written
    assert "Version 2.0" in written


def test_mit_license_written(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="mit", author="MIT Dev")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["files_written"] == ["LICENSE"]

    written = (project / "LICENSE").read_text()
    template_raw = (_TEMPLATES / "mit.txt").read_text()
    template_stable = _stable_lines(
        template_raw.replace("{YEAR}", "Y").replace("{AUTHOR}", "A"),
        "mit",
    )
    written_stable = _stable_lines(written, "mit")
    assert written_stable == template_stable

    assert "MIT Dev" in written
    assert "MIT License" in written
    assert "THE SOFTWARE IS PROVIDED" in written


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="apache-2.0")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["diffs"][0]["kind"] == "create"
    assert not (project / "LICENSE").exists()


def test_idempotent_second_run_skips(tmp_path):
    """reconcile=false: second run skips existing LICENSE."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="apache-2.0", author="Author One")
    _run(project, plan)
    first_content = (project / "LICENSE").read_text()

    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["diffs"][0]["kind"] == "skip"
    assert result["files_written"] == []
    # Content unchanged
    assert (project / "LICENSE").read_text() == first_content


def test_explicit_author_used(tmp_path):
    """Explicit author input overrides git config."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="mit", author="Explicit Corp")
    _run(project, plan)
    assert "Explicit Corp" in (project / "LICENSE").read_text()
