"""Tests for StepSpec.reproduce_only dispatch in run_agent_phase (spec 012 FR-009).

Exercises the three-case do_invoke logic added to run_agent_phase:
  - reproduce_only=False (pre-012 default): runs at init, skips on plain reproduce
  - reproduce_only=True: skips at init, runs on plain reproduce
  - reproduce_only=True + --refresh named: runs even at init (Q2 override)

Also covers SC-009 backward-compat: existing agent steps with reproduce_only=False
behave byte-identically to pre-012 behaviour.

Strategy: run_pipeline end-to-end through a synthetic plugin (mirrors
test_two_phase_resolver.py).  A module with TWO agent steps:
  - "normal-step"  (kind=agent, reproduce_only=False) — pre-012 behaviour
  - "repro-step"   (kind=agent, reproduce_only=True)  — spec 012 new behaviour
plus a python write step to confirm successful plan execution.

Agent calls are detected via io.log entries with op=='agent_step'.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_reproduce_only.py
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

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
# Build a synthetic plugin with two agent steps: normal + reproduce_only       #
# --------------------------------------------------------------------------- #
def _make_dual_agent_plugin(tmp_path: Path) -> Path:
    """Plugin root with a 'repro-mod' module:
        normal-step  (kind=agent)                         - runs at init
        repro-step   (kind=agent, reproduce_only=true)    - runs on reproduce only
        write        (kind=python)                         - reads both answers
    """
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / "repro-mod"
    (mod_dir / "steering").mkdir(parents=True)
    (mod_dir / "steering" / "normal.md").write_text("# normal\nDecide the normal answer.\n")
    (mod_dir / "steering" / "repro.md").write_text("# repro\nAdvisory staleness check.\n")

    sdk_path = _RUNNER / "sdk.py"

    (mod_dir / "module.toml").write_text(textwrap.dedent("""\
        [meta]
        repository = "github.com/test/test"
        author = "Test"

        [module]
        id = "repro-mod"
        name = "Reproduce-Only Test Module"
        version = "1.0.0"
        description = "Tests reproduce_only agent dispatch (spec 012)"
        reconcile = true
        default_enabled = true

        [order]
        requires = []
        after = []
        before = []

        [tools]
        required = []

        [[inputs]]
        key = "normal_answer"
        type = "string"
        prompt = "Normal agent answer?"
        default = ""
        required = false

        [[inputs]]
        key = "repro_answer"
        type = "string"
        prompt = "Reproduce-only agent answer?"
        default = ""
        required = false

        [[steps]]
        id = "normal-step"
        kind = "agent"
        steering = "steering/normal.md"

        [[steps]]
        id = "repro-step"
        kind = "agent"
        steering = "steering/repro.md"
        reproduce_only = true

        [[steps]]
        id = "write"
        kind = "python"
    """))

    # The python write step reads both answers from the frozen plan and writes them.
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

        inputs = sdk.load_frozen_inputs(args.plan, module_id="repro-mod")
        normal_answer = inputs.get_str("normal_answer", default="UNSET")
        repro_answer = inputs.get_str("repro_answer", default="UNSET")
        project_dir = os.environ.get("PROJECT_DIR", ".")
        content = f"normal={{normal_answer}}\\nrepro={{repro_answer}}\\n"
        diff = sdk.idempotent_write(
            "RESULT.txt", content,
            project_dir=project_dir, reconcile=True, inspect=args.inspect,
        )
        result = sdk.ModuleResult(
            module_id="repro-mod", step_id=args.step or "write", status="ok",
            files_written=[diff.path] if diff.kind in ("create", "modify") else [],
            diffs=[diff],
        )
        sdk.emit_result(result)
    """))
    return plugin_root


def _plan_path(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "plan.json"


def _normal_resp(value: str) -> dict:
    """Agent response for normal-step (persists normal_answer)."""
    return {
        "steering/normal.md": {
            "answers_to_persist": {
                "normal_answer": {"value": value, "source": "agent-steered"},
            },
            "message": f"normal resolved {value}",
        }
    }


def _repro_resp(value: str) -> dict:
    """Agent response for repro-step (persists repro_answer)."""
    return {
        "steering/repro.md": {
            "answers_to_persist": {
                "repro_answer": {"value": value, "source": "agent-steered"},
            },
            "message": f"repro advisory {value}",
        }
    }


def _both_resp(normal: str, repro: str) -> dict:
    """Combined responses for both agent steps."""
    return {**_normal_resp(normal), **_repro_resp(repro)}


# --------------------------------------------------------------------------- #
# Helper: count agent_step calls by steering path                              #
# --------------------------------------------------------------------------- #
def _agent_calls(io, steering_path: str) -> list[dict]:
    return [
        e for e in io.log
        if e["op"] == "agent_step" and e["steering_path"] == steering_path
    ]


# --------------------------------------------------------------------------- #
# FR-009 / SC-004: init SKIPS the reproduce_only agent step                   #
# --------------------------------------------------------------------------- #
def test_init_skips_reproduce_only_agent(tmp_path):
    """At init, the reproduce_only agent step makes ZERO agent_step calls
    while the normal agent step DOES run (spec 012 FR-009, SC-004)."""
    plugin_root = _make_dual_agent_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(
        default_confirm=True,
        agent_responses=_both_resp("normal-val", "SHOULD-NOT-APPEAR"),
    )
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )
    assert result.success is True, [e.how_to_fix for e in result.errors]
    assert result.mode == "init"

    # normal-step ran at init
    normal_calls = _agent_calls(io, "steering/normal.md")
    assert len(normal_calls) == 1, "normal agent step must run exactly once at init"

    # repro-step MUST NOT run at init
    repro_calls = _agent_calls(io, "steering/repro.md")
    assert repro_calls == [], (
        f"reproduce_only agent step must be SKIPPED at init, but got calls: {repro_calls}"
    )


# --------------------------------------------------------------------------- #
# FR-009 / SC-005: plain reproduce INVOKES the reproduce_only agent step      #
# --------------------------------------------------------------------------- #
def test_plain_reproduce_invokes_reproduce_only_agent(tmp_path):
    """On plain reproduce, the reproduce_only agent step IS invoked
    (spec 012 FR-009). The normal step is NOT re-invoked (FR-009 replay)."""
    plugin_root = _make_dual_agent_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Init: only normal-step runs
    io_init = ScriptedIO(
        default_confirm=True,
        agent_responses=_normal_resp("normal-committed"),
    )
    r1 = run_pipeline(
        project_dir=project_dir,
        io=io_init,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )
    assert r1.success and r1.mode == "init"

    # Reproduce: repro-step runs; normal-step replays from committed answers (no call)
    io_repro = ScriptedIO(
        default_confirm=True,
        agent_responses=_repro_resp("repro-advisory"),
    )
    r2 = run_pipeline(
        project_dir=project_dir,
        io=io_repro,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )
    assert r2.success and r2.mode == "reproduce"

    # repro-step WAS invoked on reproduce
    repro_calls = _agent_calls(io_repro, "steering/repro.md")
    assert len(repro_calls) == 1, (
        f"reproduce_only agent step must be invoked on plain reproduce, got: {repro_calls}"
    )

    # normal-step was NOT re-invoked (plain reproduce replay)
    normal_calls = _agent_calls(io_repro, "steering/normal.md")
    assert normal_calls == [], (
        f"normal agent step must NOT be re-invoked on plain reproduce, got: {normal_calls}"
    )


# --------------------------------------------------------------------------- #
# Q2 override: --refresh at init INVOKES the reproduce_only step               #
# --------------------------------------------------------------------------- #
def test_refresh_overrides_reproduce_only_at_init(tmp_path):
    """--refresh naming the module re-invokes reproduce_only at init (Q2 resolved).
    Precedence: --refresh named > reproduce_only skip-at-init rule (spec 012 Q2)."""
    plugin_root = _make_dual_agent_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # First init: both normal-step runs, repro-step is skipped
    io_init = ScriptedIO(
        default_confirm=True,
        agent_responses=_normal_resp("normal-v1"),
    )
    r1 = run_pipeline(
        project_dir=project_dir,
        io=io_init,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )
    assert r1.success and r1.mode == "init"
    assert _agent_calls(io_init, "steering/repro.md") == []

    # --refresh repro-mod at init (reproduce=False mode but with refresh named):
    # This is a reproduce run that names the module, so mode="reproduce" and
    # module_named=True. Both conditions satisfy do_invoke for repro-step.
    io_refresh = ScriptedIO(
        default_confirm=True,
        agent_responses=_both_resp("normal-v2", "repro-forced"),
    )
    r2 = run_pipeline(
        project_dir=project_dir,
        io=io_refresh,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
        refresh=["repro-mod"],
    )
    assert r2.success

    # repro-step IS invoked when --refresh names the module (Q2 override)
    repro_calls = _agent_calls(io_refresh, "steering/repro.md")
    assert len(repro_calls) == 1, (
        f"--refresh must override reproduce_only skip, causing repro-step to run. "
        f"Got: {repro_calls}"
    )


# --------------------------------------------------------------------------- #
# SC-009 backward-compat: reproduce_only=False step unaffected                #
# --------------------------------------------------------------------------- #
def test_normal_agent_step_unaffected_by_reproduce_only_feature(tmp_path):
    """A reproduce_only=False (default) agent step behaves exactly as before:
    runs at init, replays on plain reproduce with zero agent calls (SC-009)."""
    plugin_root = _make_dual_agent_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Init: normal-step runs once
    io_init = ScriptedIO(
        default_confirm=True,
        agent_responses=_normal_resp("my-framework"),
    )
    r1 = run_pipeline(
        project_dir=project_dir,
        io=io_init,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )
    assert r1.success and r1.mode == "init"
    normal_init_calls = _agent_calls(io_init, "steering/normal.md")
    assert len(normal_init_calls) == 1, "normal step must run once at init"

    # Plain reproduce: normal-step is NOT re-invoked (replay, SC-009 / 003 FR-009)
    io_repro = ScriptedIO(
        default_confirm=True,
        # Would produce a WRONG value if the agent were re-invoked
        agent_responses=_normal_resp("WRONG-IF-INVOKED"),
    )
    r2 = run_pipeline(
        project_dir=project_dir,
        io=io_repro,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )
    assert r2.success and r2.mode == "reproduce"

    # Normal step: zero calls on plain reproduce
    normal_repro_calls = _agent_calls(io_repro, "steering/normal.md")
    assert normal_repro_calls == [], (
        f"SC-009: normal step (reproduce_only=False) must NOT be re-invoked on plain reproduce. "
        f"Got: {normal_repro_calls}"
    )

    # Verify the committed value was preserved (not overwritten by WRONG-IF-INVOKED)
    result_file = project_dir / "RESULT.txt"
    assert result_file.exists()
    content = result_file.read_text()
    assert "normal=my-framework" in content, (
        f"Committed normal value must replay unchanged. Got: {content!r}"
    )
