"""Tests for the org-policy module (spec 014 FR-005..FR-010).

Verifies:
  - SC-002: frozen overrides with one entry → _do_apply emits answers_to_persist
    with the mandated value; an unrelated key is NOT in the emitted answers.
  - zero overrides ([]) → _do_apply ok, empty answers_to_persist.
  - SC-004: manifest assertions — default_enabled=false; step ids=[resolve,overrides,apply];
    overrides gate hardness=="hard", allow_flag=="allow-org-policy", init_only=True.
  - no wall-clock import/call in module.py.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_org_policy.py
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
_MODULE_REL = "modules/org-policy"


def _load(name: str):
    """Load a runner module by name."""
    if name in sys.modules:
        return sys.modules[name]
    candidates = [
        _RUNNER / f"{name}.py",
        _RUNNER / "sources" / f"{name}.py",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    assert path is not None, f"Cannot find module {name!r}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, overrides: list) -> Path:
    """Build a frozen plan.json with a canned overrides list for the apply step.

    The overrides list is stored under modules["org-policy"].answers["overrides"],
    mirroring how the runner freezes an agent-steered list value from the resolve step.
    """
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["org-policy"],
        "modules": {
            "org-policy": {
                "id": "org-policy",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    # Other answers that must NOT be touched by the apply step.
                    "project_name": "api",
                    "org": "acme",
                    # The agent-steered overrides list (frozen from the resolve step).
                    "overrides": overrides,
                },
                "steps": [
                    {"id": "resolve", "kind": "agent", "steering": "steering/resolve.md"},
                    {
                        "id": "overrides",
                        "kind": "gate",
                        "hardness": "hard",
                        "allow_flag": "allow-org-policy",
                        "init_only": True,
                        "message": "Org-policy overrides (org-mandated):\n{decision}\nApply these overrides?",
                    },
                    {"id": "apply", "kind": "python"},
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
    step: str = "apply",
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
    """SC-004: manifest must parse cleanly with correct shape."""
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, [e.to_dict() for e in mani.errors]

    assert mani.id == "org-policy"
    assert mani.default_enabled is False
    assert mani.reconcile is False

    step_ids = [s.id for s in mani.steps]
    assert step_ids == ["resolve", "overrides", "apply"], step_ids

    # resolve must be kind=agent
    resolve_step = next(s for s in mani.steps if s.id == "resolve")
    assert resolve_step.kind == "agent"

    # overrides gate must be hard, init_only, allow_flag=allow-org-policy
    gate_step = next(s for s in mani.steps if s.id == "overrides")
    assert gate_step.kind == "gate"
    assert gate_step.hardness == "hard"
    assert gate_step.allow_flag == "allow-org-policy"
    assert gate_step.init_only is True

    # apply must be kind=python
    apply_step = next(s for s in mani.steps if s.id == "apply")
    assert apply_step.kind == "python"


# --------------------------------------------------------------------------- #
# SC-002: one override → answers_to_persist has mandated value; unrelated untouched
# --------------------------------------------------------------------------- #

def test_sc002_one_override_applies_mandated_value(tmp_path):
    """SC-002: one override entry → apply step emits mandated value in answers_to_persist."""
    project = tmp_path / "proj"
    project.mkdir()

    overrides = [
        {
            "key": "project_name",
            "user_value": "api",
            "mandated_value": "com.acme.api",
            "reason": "org namespace policy",
        }
    ]
    plan = _frozen_plan(tmp_path, overrides=overrides)
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    atp = result.get("answers_to_persist", {})
    assert "project_name" in atp, f"Expected project_name in answers_to_persist, got: {atp}"
    assert atp["project_name"]["value"] == "com.acme.api"
    assert atp["project_name"]["source"] == "agent-steered"

    # The unrelated 'org' answer must NOT appear in answers_to_persist.
    assert "org" not in atp, f"Unrelated key 'org' must not be in answers_to_persist: {atp}"


def test_sc002_unrelated_key_not_touched(tmp_path):
    """SC-002: only the listed override key appears in answers_to_persist."""
    project = tmp_path / "proj"
    project.mkdir()

    overrides = [
        {
            "key": "project_name",
            "user_value": "api",
            "mandated_value": "com.acme.api",
            "reason": "ns",
        }
    ]
    plan = _frozen_plan(tmp_path, overrides=overrides)
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    atp = result.get("answers_to_persist", {})

    # Only project_name should be overridden — no other answers from the plan.
    assert set(atp.keys()) == {"project_name"}, (
        f"Expected only 'project_name' in answers_to_persist, got: {set(atp.keys())}"
    )


# --------------------------------------------------------------------------- #
# Zero overrides → no answer change, status ok                                #
# --------------------------------------------------------------------------- #

def test_zero_overrides_empty_answers_to_persist(tmp_path):
    """Zero overrides → apply step ok, answers_to_persist is empty."""
    project = tmp_path / "proj"
    project.mkdir()

    plan = _frozen_plan(tmp_path, overrides=[])
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result.get("answers_to_persist", {}) == {}, (
        f"Expected empty answers_to_persist for zero overrides, got: {result.get('answers_to_persist')}"
    )


# --------------------------------------------------------------------------- #
# Multiple overrides all applied                                               #
# --------------------------------------------------------------------------- #

def test_multiple_overrides_all_applied(tmp_path):
    """Multiple override entries → all mandated values in answers_to_persist."""
    project = tmp_path / "proj"
    project.mkdir()

    overrides = [
        {"key": "project_name", "user_value": "api", "mandated_value": "com.acme.api", "reason": "ns"},
        {"key": "license", "user_value": "MIT", "mandated_value": "Apache-2.0", "reason": "org license policy"},
    ]
    plan = _frozen_plan(tmp_path, overrides=overrides)
    proc = _run(project, plan)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    atp = result.get("answers_to_persist", {})
    assert atp.get("project_name", {}).get("value") == "com.acme.api"
    assert atp.get("license", {}).get("value") == "Apache-2.0"


# --------------------------------------------------------------------------- #
# No wall-clock import/call in module.py                                       #
# --------------------------------------------------------------------------- #

def test_no_wall_clock_in_module_py():
    """module.py must not import datetime/time or call wall-clock functions."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    source = module_py.read_text(encoding="utf-8")

    for bad in ("import datetime", "import time", "from datetime", "from time"):
        assert bad not in source, f"module.py must not use {bad!r} (no wall-clock)"

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
