"""Tests for the two-phase plan + reproduce-replay (spec 003 FR-009/010/011).

Exercises the runner-contract repair end-to-end through run_pipeline with a
synthetic Tier-2 module ('stack-mod') whose steps are:
  resolve (agent)  -> pins (gate, message carries {decision})  -> write (python)

The python write step reads the agent's decided 'framework' from the FROZEN PLAN
and writes it to a file — so if the file contains the agent's value, the
two-phase flow (Phase A agent -> fold -> freeze v2 -> Phase B python) worked.

Covered:
  - SC-004: init resolves -> freezes -> python reads the agent's pins from the plan
  - SC-002: plain reproduce makes ZERO agent calls (replay) + writes the committed value
  - SC-003: --refresh re-invokes the agent (confirmed) / a declined refresh keeps committed
  - gate-message {decision} token is composed from the resolved decision

No real network. ScriptedIO supplies agent_responses; agent calls are detected
via io.log.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_two_phase_resolver.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from pathlib import Path

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


contracts = _load("contracts")
pipeline_mod = _load("pipeline")

_io_spec = importlib.util.spec_from_file_location("io_adapter", _RUNNER / "io_adapter.py")
assert _io_spec and _io_spec.loader
_io_mod = importlib.util.module_from_spec(_io_spec)
sys.modules["io_adapter"] = _io_mod
_io_spec.loader.exec_module(_io_mod)
ScriptedIO = _io_mod.ScriptedIO

run_pipeline = pipeline_mod.run_pipeline


# --------------------------------------------------------------------------- #
# Build a synthetic Tier-2 resolver module                                     #
# --------------------------------------------------------------------------- #
def _make_resolver_plugin(tmp_path: Path) -> Path:
    """Plugin root with a 'stack-mod' module: agent -> gate -> python(write)."""
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / "stack-mod"
    (mod_dir / "steering").mkdir(parents=True)
    (mod_dir / "steering" / "resolve.md").write_text("# resolve\nDecide a framework pin.\n")

    (mod_dir / "module.toml").write_text(textwrap.dedent("""\
        [meta]
        repository = "github.com/test/test"
        author = "Test"

        [module]
        id = "stack-mod"
        name = "Stack Resolver (test)"
        version = "1.0.0"
        description = "Test Tier-2 resolver"
        reconcile = true
        default_enabled = true

        [order]
        requires = []
        after = []
        before = []

        [tools]
        required = []

        [[inputs]]
        key = "framework"
        type = "string"
        prompt = "Framework pin (agent-resolved)?"
        default = ""
        required = false

        [[steps]]
        id = "resolve"
        kind = "agent"
        steering = "steering/resolve.md"

        [[steps]]
        id = "pins"
        kind = "gate"
        message = "Stack decision:\\n{decision}\\nWrite the manifest?"

        [[steps]]
        id = "write"
        kind = "python"
    """))

    sdk_path = _RUNNER / "sdk.py"
    # The python write step reads 'framework' from the frozen plan and writes it.
    (mod_dir / "module.py").write_text(textwrap.dedent(f"""\
        # /// script
        # requires-python = ">=3.11"
        # ///
        import argparse, importlib.util, os, sys
        from pathlib import Path

        p = argparse.ArgumentParser()
        p.add_argument("--plan"); p.add_argument("--step")
        p.add_argument("--inspect", action="store_true")
        args = p.parse_args()

        spec = importlib.util.spec_from_file_location("sdk", {str(sdk_path)!r})
        sdk = importlib.util.module_from_spec(spec); sys.modules["sdk"] = sdk
        spec.loader.exec_module(sdk)

        inputs = sdk.load_frozen_inputs(args.plan, module_id="stack-mod")
        framework = inputs.get_str("framework", default="UNSET")
        project_dir = os.environ.get("PROJECT_DIR", ".")
        diff = sdk.idempotent_write(
            "MANIFEST.txt", framework + "\\n",
            project_dir=project_dir, reconcile=True, inspect=args.inspect,
        )
        result = sdk.ModuleResult(
            module_id="stack-mod", step_id=args.step or "write", status="ok",
            files_written=[diff.path] if diff.kind in ("create", "modify") else [],
            diffs=[diff],
        )
        sdk.emit_result(result)
    """))
    return plugin_root


def _plan_path(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "plan.json"


def _agent_resp(framework: str) -> dict:
    return {
        "steering/resolve.md": {
            "answers_to_persist": {
                "framework": {"value": framework, "source": "agent-steered"},
            },
            "message": f"resolved {framework}",
        }
    }


# --------------------------------------------------------------------------- #
# SC-004: init — agent decision reaches the python step via the frozen plan    #
# --------------------------------------------------------------------------- #
def test_init_agent_decision_reaches_python_step(tmp_path):
    plugin_root = _make_resolver_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("fastapi@0.115.0"))
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )

    assert result.success is True, [e.how_to_fix for e in result.errors]
    # The python step wrote the AGENT's decided value — proves Phase A -> freeze -> Phase B.
    manifest = project_dir / "MANIFEST.txt"
    assert manifest.exists()
    assert manifest.read_text().strip() == "fastapi@0.115.0"


def test_init_persists_agent_steered_provenance(tmp_path):
    import tomllib
    plugin_root = _make_resolver_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("django@5.1.4"))
    run_pipeline(
        project_dir=project_dir, io=io, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )

    answers = project_dir / ".project-setup" / "answers.toml"
    with open(answers, "rb") as fh:
        data = tomllib.load(fh)
    assert data["module"]["stack-mod"]["framework"] == "django@5.1.4"
    assert data["module"]["stack-mod"]["source"]["framework"] == "agent-steered"


def test_gate_message_composes_decision_token(tmp_path):
    plugin_root = _make_resolver_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("litestar@2.13.0"))
    run_pipeline(
        project_dir=project_dir, io=io, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )

    # The gate confirm preview must carry the composed decision (not the raw token).
    gate_confirms = [
        e for e in io.log
        if e["op"] == "confirm" and "stack-mod/pins" in str(e.get("item", e.get("path", "")))
    ]
    # ScriptedIO logs confirm with 'path'; the composed message rode in via the plan's
    # gate message. Assert the token was replaced somewhere in the frozen plan.
    plan_data = json.loads(_plan_path(tmp_path).read_text())
    pins_step = next(
        s for s in plan_data["modules"]["stack-mod"]["steps"] if s["id"] == "pins"
    )
    assert "{decision}" not in pins_step["message"]
    assert "litestar@2.13.0" in pins_step["message"]


# --------------------------------------------------------------------------- #
# SC-002: plain reproduce — zero agent calls, replays committed value          #
# --------------------------------------------------------------------------- #
def test_reproduce_replays_committed_decision_zero_agent_calls(tmp_path):
    plugin_root = _make_resolver_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # 1. init with the agent → freezes fastapi@0.115.0 into answers.toml
    io_init = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("fastapi@0.115.0"))
    r1 = run_pipeline(
        project_dir=project_dir, io=io_init, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    assert r1.success and r1.mode == "init"

    # 2. reproduce — agent_responses would return a DIFFERENT value if (wrongly) called
    io_repro = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("WRONG@9.9.9"))
    r2 = run_pipeline(
        project_dir=project_dir, io=io_repro, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    assert r2.success and r2.mode == "reproduce"

    # The agent MUST NOT have been called in plain reproduce (zero-network replay).
    agent_calls = [e for e in io_repro.log if e["op"] == "agent_step"]
    assert agent_calls == [], "reproduce re-invoked the agent — FR-009 replay violated"

    # The committed value, not the would-be re-research value, is written.
    assert (project_dir / "MANIFEST.txt").read_text().strip() == "fastapi@0.115.0"


# --------------------------------------------------------------------------- #
# SC-003: --refresh re-invokes the named module; declined refresh keeps value  #
# --------------------------------------------------------------------------- #
def test_refresh_reinvokes_agent_when_confirmed(tmp_path):
    plugin_root = _make_resolver_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io_init = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("fastapi@0.115.0"))
    run_pipeline(
        project_dir=project_dir, io=io_init, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )

    # --refresh stack-mod, confirm everything → new value applied
    io_ref = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("fastapi@0.116.0"))
    r = run_pipeline(
        project_dir=project_dir, io=io_ref, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
        refresh=["stack-mod"],
    )
    assert r.success
    agent_calls = [e for e in io_ref.log if e["op"] == "agent_step"]
    assert len(agent_calls) == 1, "refresh should re-invoke the named agent once"
    assert (project_dir / "MANIFEST.txt").read_text().strip() == "fastapi@0.116.0"


def test_refresh_declined_keeps_committed_value(tmp_path):
    plugin_root = _make_resolver_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io_init = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("fastapi@0.115.0"))
    run_pipeline(
        project_dir=project_dir, io=io_init, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )

    # Decline the refresh diff-gate specifically; confirm normal writes.
    io_ref = ScriptedIO(
        confirmations={"stack-mod/resolve": False, "all": True},
        agent_responses=_agent_resp("fastapi@0.116.0"),
    )
    run_pipeline(
        project_dir=project_dir, io=io_ref, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
        refresh=["stack-mod"],
    )
    # Declined → committed value preserved.
    assert (project_dir / "MANIFEST.txt").read_text().strip() == "fastapi@0.115.0"


# --------------------------------------------------------------------------- #
# Non-interactive reproduce: still zero agent calls (replay holds in CI)        #
# --------------------------------------------------------------------------- #
def test_non_interactive_reproduce_replays(tmp_path):
    plugin_root = _make_resolver_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io_init = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("fastapi@0.115.0"))
    run_pipeline(
        project_dir=project_dir, io=io_init, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )

    io_ci = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("WRONG@9.9.9"))
    r = run_pipeline(
        project_dir=project_dir, io=io_ci, non_interactive=True,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    assert r.success
    assert [e for e in io_ci.log if e["op"] == "agent_step"] == []
