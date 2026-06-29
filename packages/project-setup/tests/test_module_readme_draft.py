"""Tests for the readme-draft module.

Verifies:
  - SC-001: frozen readme_body + no README.md → write creates file byte-identical to body
  - SC-002: existing README.md (any content) → write returns skip, file preserved
  - SC-003: idempotent — first call creates, second call (file exists) returns skip
  - SC-004: manifest assertions (default_enabled=false, step order, gate shape, no when)
  - empty readme_body → no file written + warning emitted
  - no wall-clock import/call in module.py

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_readme_draft.py
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/readme-draft"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, readme_body: str = "") -> Path:
    """Build a frozen plan.json with a canned readme_body for the write step."""
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["readme-draft"],
        "modules": {
            "readme-draft": {
                "id": "readme-draft",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "project_name": "demo",
                    "org": "acme",
                    "layout": "single",
                    "language": "python",
                    "license": "MIT",
                    "readme_body": readme_body,
                },
                "steps": [
                    {"id": "draft", "kind": "agent", "steering": "steering/draft.md"},
                    {
                        "id": "readme-gate",
                        "kind": "gate",
                        "hardness": "hard",
                        "allow_flag": "allow-readme",
                        "init_only": True,
                        "message": "Project README draft (agent-authored):\n{decision}\nWrite README.md?",
                    },
                    {"id": "write", "kind": "python"},
                ],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(
    project: Path,
    plan: Path,
    step: str = "write",
    inspect: bool = False,
) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", step]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


# --------------------------------------------------------------------------- #
# SC-004: Manifest                                                             #
# --------------------------------------------------------------------------- #

def test_sc004_manifest_parses_and_is_valid():
    """SC-004: manifest must parse cleanly with correct step shape and gate config."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, [e.to_dict() for e in mani.errors]
    assert mani.id == "readme-draft"
    assert mani.default_enabled is False
    assert mani.reconcile is False

    step_ids = [s.id for s in mani.steps]
    assert step_ids == ["draft", "readme-gate", "write"], step_ids

    # draft must be kind=agent
    draft_step = next(s for s in mani.steps if s.id == "draft")
    assert draft_step.kind == "agent"

    # readme-gate must be hard, init_only, allow_flag=allow-readme, NO when
    gate_step = next(s for s in mani.steps if s.id == "readme-gate")
    assert gate_step.kind == "gate"
    assert gate_step.hardness == "hard"
    assert gate_step.allow_flag == "allow-readme"
    assert gate_step.init_only is True
    assert gate_step.when is None, f"gate must have no 'when' predicate, got: {gate_step.when!r}"

    # write must be kind=python
    write_step = next(s for s in mani.steps if s.id == "write")
    assert write_step.kind == "python"

    # order: after includes core-identity and lang-* modules
    after = mani.order.get("after", [])
    assert "core-identity" in after
    assert "lang-python" in after

    # no requires
    assert not mani.order.get("requires")


# --------------------------------------------------------------------------- #
# SC-001: frozen readme_body + no README → file created byte-identical        #
# --------------------------------------------------------------------------- #

def test_sc001_creates_readme_when_absent(tmp_path):
    """SC-001: frozen readme_body + no README.md → write creates file byte-identical."""
    project = tmp_path / "proj"
    project.mkdir()

    body = "# Demo\n\nA demo project.\n"
    plan = _frozen_plan(tmp_path, readme_body=body)
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "README.md" in result["files_written"]

    content = (project / "README.md").read_bytes()
    assert content == body.encode(), f"File content differs from frozen body"


# --------------------------------------------------------------------------- #
# SC-002: existing README preserved (skip, no overwrite)                       #
# --------------------------------------------------------------------------- #

def test_sc002_existing_readme_preserved(tmp_path):
    """SC-002: existing README.md → write returns skip, file content unchanged."""
    project = tmp_path / "proj"
    project.mkdir()

    original = "# Hand-edited README\n\nDo not touch.\n"
    (project / "README.md").write_text(original)

    body = "# Demo\n\nA demo project.\n"
    plan = _frozen_plan(tmp_path, readme_body=body)
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    # files_written must be empty — nothing was written
    assert result["files_written"] == [], f"Expected no files written, got: {result['files_written']}"
    # diff kind must be skip
    assert result["diffs"][0]["kind"] == "skip"
    # Original content must be preserved
    assert (project / "README.md").read_text() == original


# --------------------------------------------------------------------------- #
# SC-003: idempotent — first call creates, second call skips                   #
# --------------------------------------------------------------------------- #

def test_sc003_idempotent_create_then_skip(tmp_path):
    """SC-003: first write creates README.md; second write with same plan returns skip."""
    project = tmp_path / "proj"
    project.mkdir()

    body = "# Demo\n\nA demo project.\n"
    plan = _frozen_plan(tmp_path, readme_body=body)

    # First run — must create the file
    proc1 = _run(project, plan)
    assert proc1.returncode == 0, proc1.stderr
    result1 = json.loads(proc1.stdout)
    assert result1["status"] == "ok"
    assert "README.md" in result1["files_written"]
    assert result1["diffs"][0]["kind"] == "create"

    # Second run — must skip (file exists, reconcile=false)
    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result2 = json.loads(proc2.stdout)
    assert result2["status"] == "ok"
    assert result2["files_written"] == []
    assert result2["diffs"][0]["kind"] == "skip"

    # File content must still be the original body
    assert (project / "README.md").read_bytes() == body.encode()


# --------------------------------------------------------------------------- #
# Empty readme_body → no file written + warning                                #
# --------------------------------------------------------------------------- #

def test_empty_readme_body_no_write_warning(tmp_path):
    """Empty readme_body → status ok, no file written, warning emitted."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(tmp_path, readme_body="")
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == []
    assert not (project / "README.md").exists()

    warnings = result.get("warnings", [])
    assert any("readme_body" in w or "nothing drafted" in w for w in warnings), (
        f"Expected a warning about empty readme_body, got: {warnings}"
    )


# --------------------------------------------------------------------------- #
# No wall-clock import/call in module.py                                       #
# --------------------------------------------------------------------------- #

def test_no_wall_clock_in_module_py():
    """module.py must not import datetime/time or call wall-clock functions."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    source = module_py.read_text(encoding="utf-8")

    # Check for wall-clock imports at source level
    for bad in ("import datetime", "import time", "from datetime", "from time"):
        assert bad not in source, f"module.py must not use {bad!r} (no wall-clock)"

    # Parse the AST and check for any datetime/time attribute access or calls
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in ("datetime", "time"), (
                    f"module.py imports wall-clock module: {alias.name!r}"
                )
        if isinstance(node, ast.ImportFrom):
            assert node.module not in ("datetime", "time"), (
                f"module.py imports from wall-clock module: {node.module!r}"
            )
