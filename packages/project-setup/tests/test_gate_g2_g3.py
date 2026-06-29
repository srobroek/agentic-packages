"""Spec 004 Phase 3 — G2 batched install + G3 public-repo gates (SC-004, SC-005).

These ride the Phase-1 foundation: declarative gate steps on the real apm-install
and github-repo manifests. Covered:
- G3 is present (hard, allow-public-repo) when public == true; DROPPED when private.
- G2 lists every package untruncated (baseline + selected), is hard + allow-install.
- The hardness/flag resolution in CI (safe-skip without the flag; perform with it)
  is already proven generically in test_gate_hardness; here we assert the wiring
  on the real manifests' frozen-plan gate steps.

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_g2_g3.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
executor = _load("executor")
run_gate_step = executor.run_gate_step


def _manifest(module_id: str):
    m = manifest.parse_manifest(_MODULES / module_id / "module.toml")
    assert not m.errors, [e.to_dict() for e in m.errors]
    m._toml_path = _MODULES / module_id / "module.toml"
    return m


def _build(m, answers):
    return plan_mod.build_plan(
        [m],
        resolved_answers={m.id: answers},
        ordered_ids=[m.id],
        mode="init",
        plugin_root_path=_RUNNER.parent,
    )


def _gate_steps(plan, mod_id):
    return [s for s in plan.modules[mod_id].steps if s.get("kind") == "gate"]


# --------------------------------------------------------------------------- #
# G3 — public-repo gate present for public, dropped for private (SC-005)       #
# --------------------------------------------------------------------------- #
def test_g3_present_when_public():
    m = _manifest("github-repo")
    plan = _build(m, {"public": True, "org": "acme", "project_name": "svc"})
    gates = _gate_steps(plan, "github-repo")
    assert len(gates) == 1
    g = gates[0]
    assert g["id"] == "confirm-public"
    assert g["allow_flag"] == "allow-public-repo"
    # hardness=hard is the default and is omitted from the frozen plan (minimal).
    assert g.get("hardness", "hard") == "hard"
    # {decision} rendered the answers into the message.
    assert "acme" in g["message"] and "svc" in g["message"]


def test_g3_dropped_when_private():
    m = _manifest("github-repo")
    plan = _build(m, {"public": False, "org": "acme", "project_name": "svc"})
    assert _gate_steps(plan, "github-repo") == []
    # the create step is still present (ungated for private)
    kinds = [(s["id"], s["kind"]) for s in plan.modules["github-repo"].steps]
    assert ("create", "python") in kinds


def test_g3_ci_safe_skips_without_flag():
    m = _manifest("github-repo")
    plan = _build(m, {"public": True, "org": "acme", "project_name": "svc"})
    g = _gate_steps(plan, "github-repo")[0]

    class _IO:
        def notify(self, msg): pass
        def confirm(self, item): raise AssertionError("must not prompt in CI")

    # No flag → safe-skip (False); with the flag → proceed (True).
    assert run_gate_step(g, "github-repo", _IO(), non_interactive=True) is False
    assert run_gate_step(
        g, "github-repo", _IO(), non_interactive=True,
        active_flags=frozenset({"allow-public-repo"}),
    ) is True


# --------------------------------------------------------------------------- #
# G2 — batched install gate, full untruncated list (SC-004)                    #
# --------------------------------------------------------------------------- #
def test_g2_present_and_lists_selected_package():
    # spec 018: standalone — the G2 gate renders ONLY the user-selected locator via
    # {decision}; there is NO hardcoded srobroek baseline block anymore.
    m = _manifest("apm-install")
    plan = _build(m, {"agentic_packages": "mypkg@my-marketplace"})
    gates = _gate_steps(plan, "apm-install")
    assert len(gates) == 1
    g = gates[0]
    assert g["id"] == "confirm-install"
    assert g["allow_flag"] == "allow-install"
    msg = g["message"]
    # the user-selected locator (rendered via {decision}) appears
    assert "mypkg@my-marketplace" in msg
    # NO srobroek baseline leaked into the gate message
    assert "srobroek" not in msg, "G2 gate message must carry no srobroek baseline"
    assert "mcp-codebase-memory" not in msg and "mcp-repomix" not in msg


def test_g2_no_baseline_constant_in_module():
    # spec 018: standalone — apm-install must NOT carry a hardcoded _BASELINE_MCP
    # constant (the old srobroek baseline). Guards against its reintroduction.
    import importlib.util as iu
    mpath = _MODULES / "apm-install" / "module.py"
    spec = iu.spec_from_file_location("apm_install_mod", mpath)
    mod = iu.module_from_spec(spec)
    sys.modules["apm_install_mod"] = mod
    spec.loader.exec_module(mod)
    assert not hasattr(mod, "_BASELINE_MCP"), (
        "_BASELINE_MCP must not exist — apm-install is standalone (spec 018)"
    )
    # and the module source carries no srobroek runtime literal
    src = mpath.read_text(encoding="utf-8")
    assert "srobroek" not in src, "apm-install/module.py must carry no srobroek literal"


def test_g2_ci_safe_skips_without_flag():
    m = _manifest("apm-install")
    plan = _build(m, {"agentic_packages": "mypkg@my-marketplace"})
    g = _gate_steps(plan, "apm-install")[0]

    class _IO:
        def notify(self, msg): pass
        def confirm(self, item): raise AssertionError("must not prompt in CI")

    assert run_gate_step(g, "apm-install", _IO(), non_interactive=True) is False
    assert run_gate_step(
        g, "apm-install", _IO(), non_interactive=True,
        active_flags=frozenset({"allow-install"}),
    ) is True
