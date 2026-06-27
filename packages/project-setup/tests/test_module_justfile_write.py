"""End-to-end tests for the justfile-write module.

Verifies:
  - manifest parses and is valid
  - use_just=true (default): writes justfile with verbatim legacy content
  - use_just=false: no files written (explicit skip)
  - --inspect writes nothing
  - reconcile=false: second run skips existing justfile
  - justfile content matches the legacy heredoc verbatim

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_justfile_write.py
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
_MODULE_REL = "modules/justfile-write"

# Verbatim expected justfile content (matches legacy heredoc lines 619–641).
_EXPECTED_JUSTFILE = """\
default:
    @just --list

# Run tests
test:
    @echo "TODO: configure test command"

# Lint and format
lint:
    pre-commit run --all-files

# Build
build:
    @echo "TODO: configure build command"

# Start dev server
dev:
    @echo "TODO: configure dev command"

# Clean build artifacts
clean:
    @echo "TODO: configure clean command"
"""


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, use_just: bool = True) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["justfile-write"],
        "modules": {
            "justfile-write": {
                "id": "justfile-write",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {"use_just": use_just},
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
    assert mani.id == "justfile-write"
    assert mani.default_enabled is False
    assert mani.reconcile is False
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    # No requires — justfile is independent
    assert mani.order["requires"] == []


def test_use_just_true_writes_justfile(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, use_just=True)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == ["justfile"]

    written = (project / "justfile").read_text()
    assert written == _EXPECTED_JUSTFILE


def test_justfile_content_verbatim(tmp_path):
    """Byte-identical comparison with the expected legacy content."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, use_just=True)
    _run(project, plan)
    written = (project / "justfile").read_bytes()
    assert written == _EXPECTED_JUSTFILE.encode("utf-8")


def test_use_just_false_skips(tmp_path):
    """use_just=false: no justfile written, files_written=[]."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, use_just=False)
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == []
    assert not (project / "justfile").exists()


def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, use_just=True)
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["diffs"][0]["kind"] == "create"
    assert not (project / "justfile").exists()


def test_inspect_equals_write_bytes(tmp_path):
    """Tier-1 guarantee: inspect preview content == real written bytes."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, use_just=True)
    # Inspect first, nothing written
    _run(project, plan, inspect=True)
    assert not (project / "justfile").exists()
    # Real write
    _run(project, plan)
    written = (project / "justfile").read_text()
    assert written == _EXPECTED_JUSTFILE


def test_idempotent_second_run_skips(tmp_path):
    """reconcile=false: second run skips existing justfile."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, use_just=True)
    _run(project, plan)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["diffs"][0]["kind"] == "skip"
    assert result["files_written"] == []
    # Content unchanged
    assert (project / "justfile").read_text() == _EXPECTED_JUSTFILE
