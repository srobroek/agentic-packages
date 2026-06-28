"""Spec 004 Phase 4 — G6 upgrade the lang-* pin gate (FR-014, FR-006a, SC-007).

G6 enriches the EXISTING 003 pin gate (no new step, no runner change):
- hard + allow_flag=allow-stack-write + init_only on both lang-python and lang-ts.
- the message frames the decision as agent-resolved + registry-verified and renders
  the frozen decision via {decision}.
- init_only carries into the frozen plan so run_gate_step auto-proceeds on plain
  reproduce (the end-to-end replay behavior is proven in
  test_two_phase_resolver.test_init_only_gate_non_interactive_reproduce_replays_and_writes).

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_g6_pin_review.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"
_MODULES = _RUNNER.parent / "modules"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


manifest = _load("manifest")
plan_mod = _load("plan")


@pytest.mark.parametrize("module_id", ["lang-python", "lang-ts"])
def test_g6_pin_gate_enrichment(module_id):
    m = manifest.parse_manifest(_MODULES / module_id / "module.toml")
    assert not m.errors, [e.to_dict() for e in m.errors]
    # lang-ts also has the G4 `run-generator` gate (Phase 5); select the pins gate.
    pins = [s for s in m.steps if s.kind == "gate" and s.id == "pins"]
    assert len(pins) == 1, [s.id for s in m.steps]
    g = pins[0]
    assert g.id == "pins"
    assert g.hardness == "hard"
    assert g.allow_flag == "allow-stack-write"
    assert g.init_only is True
    # message frames verification + carries the {decision} token for the pin table
    assert "{decision}" in g.message
    assert "registry-verified" in g.message


@pytest.mark.parametrize("module_id", ["lang-python", "lang-ts"])
def test_g6_init_only_serialized_into_frozen_plan(module_id):
    m = manifest.parse_manifest(_MODULES / module_id / "module.toml")
    m._toml_path = _MODULES / module_id / "module.toml"
    plan = plan_mod.build_plan(
        [m],
        resolved_answers={module_id: {"framework": "fastapi@0.115.0"}},
        ordered_ids=[module_id],
        mode="init",
        plugin_root_path=_RUNNER.parent,
    )
    gate = [s for s in plan.modules[module_id].steps
            if s.get("kind") == "gate" and s.get("id") == "pins"][0]
    assert gate["init_only"] is True
    assert gate["allow_flag"] == "allow-stack-write"
    # {decision} was composed from the frozen answers (token replaced)
    assert "{decision}" not in gate["message"]
    assert "fastapi@0.115.0" in gate["message"]
