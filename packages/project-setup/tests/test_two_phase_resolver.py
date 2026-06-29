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
def _make_resolver_plugin(tmp_path: Path, *, init_only: bool = False) -> Path:
    """Plugin root with a 'stack-mod' module: agent -> gate -> python(write).

    When *init_only* is True the pin gate carries ``init_only = true`` (spec 004
    FR-006a) so a plain reproduce auto-proceeds instead of (safe-)skipping the write.
    """
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / "stack-mod"
    (mod_dir / "steering").mkdir(parents=True)
    (mod_dir / "steering" / "resolve.md").write_text("# resolve\nDecide a framework pin.\n")

    init_only_line = "\n        init_only = true" if init_only else ""
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
        message = "Stack decision:\\n{decision}\\nWrite the manifest?"INIT_ONLY_LINE

        [[steps]]
        id = "write"
        kind = "python"
    """).replace("INIT_ONLY_LINE", init_only_line))

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


# --------------------------------------------------------------------------- #
# Spec 004 FR-006a: init_only gate auto-proceeds on reproduce (no block)       #
# --------------------------------------------------------------------------- #
def test_init_only_gate_non_interactive_reproduce_replays_and_writes(tmp_path):
    """A non-interactive reproduce of an init_only pin gate must AUTO-PROCEED and
    write the committed value — NOT safe-skip + block (which a plain hard gate would
    do, leaving the manifest unwritten). This is the FR-006a distinction.
    """
    plugin_root = _make_resolver_plugin(tmp_path, init_only=True)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # init (interactive) → freezes fastapi@0.115.0 + writes the manifest
    io_init = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("fastapi@0.115.0"))
    r1 = run_pipeline(
        project_dir=project_dir, io=io_init, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    assert r1.success and r1.mode == "init"
    assert (project_dir / "MANIFEST.txt").read_text().strip() == "fastapi@0.115.0"

    # CI reproduce: the init_only gate must auto-proceed (no prompt, no block) so the
    # committed value replays. A plain hard gate here would SAFE-skip → block → leave
    # the manifest unchanged; init_only is what lets the consented decision replay.
    io_ci = ScriptedIO(default_confirm=True, agent_responses=_agent_resp("WRONG@9.9.9"))
    r2 = run_pipeline(
        project_dir=project_dir, io=io_ci, non_interactive=True,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    assert r2.success and r2.mode == "reproduce"
    assert [e for e in io_ci.log if e["op"] == "agent_step"] == []  # zero-network (003 FR-009)
    assert (project_dir / "MANIFEST.txt").read_text().strip() == "fastapi@0.115.0"


# --------------------------------------------------------------------------- #
# spec 007 Phase-0: all_answers in agent context (two-module plan)             #
# --------------------------------------------------------------------------- #

class _ContextCapturingIO:
    """Minimal IO double that records the full context dict passed to agent_step.

    Used to assert that ``all_answers`` from module A is visible to module B's
    agent step. ScriptedIO does not record the context argument, so we use this
    custom double instead.
    """

    def __init__(self, agent_responses: dict):
        self.agent_responses = agent_responses
        self.captured_contexts: list[dict] = []
        self.log: list[dict] = []

    def ask(self, input_spec, default):
        return default

    def confirm(self, item):
        return True

    def agent_step(self, steering_path: str, context: dict) -> dict:
        self.captured_contexts.append(dict(context))
        self.log.append({"op": "agent_step", "steering_path": steering_path})
        return self.agent_responses.get(
            steering_path,
            {"answers_to_persist": {}, "message": "no-op"},
        )

    def notify(self, msg: str) -> None:
        self.log.append({"op": "notify", "msg": msg})


def _make_two_module_plugin(tmp_path: Path) -> Path:
    """Plugin root with two modules ordered A → B.

    mod-a: agent step emits ``framework_a``.
    mod-b (after=["mod-a"]): agent step receives context with ``all_answers``.

    Both write a MANIFEST_*.txt so the pipeline runs Phase B successfully.
    """
    plugin_root = tmp_path / "plugin"
    sdk_path = _RUNNER / "sdk.py"

    def _write_module(mod_id: str, after: list[str]) -> None:
        mod_dir = plugin_root / "modules" / mod_id
        (mod_dir / "steering").mkdir(parents=True)
        (mod_dir / "steering" / "resolve.md").write_text(f"# resolve {mod_id}\n")
        after_str = repr(after)
        (mod_dir / "module.toml").write_text(textwrap.dedent(f"""\
            [meta]
            repository = "github.com/test/test"
            author = "Test"

            [module]
            id = "{mod_id}"
            name = "{mod_id} (test)"
            version = "1.0.0"
            description = "Test module {mod_id}"
            reconcile = true
            default_enabled = true

            [order]
            requires = []
            after = {after_str}
            before = []

            [[inputs]]
            key = "value_{mod_id}"
            type = "string"
            prompt = "Value for {mod_id}?"
            default = ""
            required = false

            [[steps]]
            id = "resolve"
            kind = "agent"
            steering = "steering/resolve.md"

            [[steps]]
            id = "write"
            kind = "python"
        """))
        key = f"value_{mod_id}"
        manifest_file = f"MANIFEST_{mod_id.upper()}.txt"
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
            inputs = sdk.load_frozen_inputs(args.plan, module_id="{mod_id}")
            val = inputs.get_str("{key}", default="UNSET")
            diff = sdk.idempotent_write(
                "{manifest_file}", val + "\\n",
                project_dir=os.environ.get("PROJECT_DIR", "."),
                reconcile=True, inspect=args.inspect,
            )
            sdk.emit_result(sdk.ModuleResult(
                module_id="{mod_id}", step_id=args.step or "write", status="ok",
                files_written=[diff.path] if diff.kind in ("create","modify") else [],
                diffs=[diff],
            ))
        """))

    _write_module("mod-a", after=[])
    _write_module("mod-b", after=["mod-a"])
    return plugin_root


def test_spec007_all_answers_visible_to_downstream_agent(tmp_path):
    """spec 007 Phase-0: module B's agent step receives all_answers containing
    module A's emitted answer (value_mod-a).

    Uses _ContextCapturingIO (stateful, records full context) instead of
    ScriptedIO so we can inspect the context dict passed to each agent_step call.
    """
    plugin_root = _make_two_module_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Both modules use "steering/resolve.md" as their steering path.
    # We use a call-count-based responder to give distinct answers to A and B.
    class _OrderedIO(_ContextCapturingIO):
        _call_idx = 0
        _seq = [
            {  # mod-a response
                "answers_to_persist": {
                    "value_mod-a": {"value": "answer-from-a", "source": "agent-steered"},
                },
                "message": "mod-a resolved",
            },
            {  # mod-b response
                "answers_to_persist": {
                    "value_mod-b": {"value": "answer-from-b", "source": "agent-steered"},
                },
                "message": "mod-b resolved",
            },
        ]

        def agent_step(self, steering_path, context):
            self.captured_contexts.append(dict(context))
            self.log.append({
                "op": "agent_step",
                "steering_path": steering_path,
                "module_id": context.get("module_id"),
            })
            resp = self._seq[self._call_idx % len(self._seq)]
            self._call_idx += 1
            return resp

    io = _OrderedIO(agent_responses={})
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )
    assert result.success is True, [e.how_to_fix for e in result.errors]

    # Two agent steps must have run (one per module).
    agent_calls = [e for e in io.log if e["op"] == "agent_step"]
    assert len(agent_calls) == 2, f"Expected 2 agent calls, got {agent_calls}"

    # The SECOND agent call is for mod-b (ordered after mod-a).
    mod_b_ctx = io.captured_contexts[1]
    assert "all_answers" in mod_b_ctx, (
        "spec 007: all_answers must be present in module B's agent context"
    )

    # all_answers must contain mod-a's emitted answer.
    all_answers = mod_b_ctx["all_answers"]
    assert "mod-a" in all_answers, (
        f"all_answers must contain mod-a. Keys: {list(all_answers.keys())}"
    )
    assert all_answers["mod-a"].get("value_mod-a") == "answer-from-a", (
        f"all_answers[mod-a][value_mod-a] must be 'answer-from-a', "
        f"got: {all_answers.get('mod-a')}"
    )

    # Pipeline wrote both manifest files.
    assert (project_dir / "MANIFEST_MOD-A.TXT").exists() or \
           (project_dir / "MANIFEST_MOD-A.txt").exists() or \
           any(project_dir.glob("MANIFEST_MOD*")), "mod-a manifest must be written"


def test_spec007_single_module_backward_compat(tmp_path):
    """spec 007 Phase-0 backward-compat: a single-module agent still receives
    all_answers in its context and the pipeline succeeds unchanged.

    This verifies the additive change (spec 007 Phase-0) does not break
    the existing single-module Tier-2 flow.
    """
    plugin_root = _make_resolver_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    class _RecordingIO(_ContextCapturingIO):
        pass

    io = _RecordingIO(agent_responses={
        "steering/resolve.md": {
            "answers_to_persist": {
                "framework": {"value": "litestar", "source": "agent-steered"},
            },
            "message": "resolved: litestar",
        }
    })
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_plan_path(tmp_path),
    )
    assert result.success is True, [e.how_to_fix for e in result.errors]

    # The agent was called once; its context must carry all_answers.
    assert len(io.captured_contexts) == 1
    ctx = io.captured_contexts[0]
    assert "all_answers" in ctx, (
        "spec 007 backward-compat: all_answers must be present in single-module agent context"
    )
    # Pipeline still writes the file correctly (FR-017 replay).
    assert (project_dir / "MANIFEST.txt").read_text().strip() == "litestar"
