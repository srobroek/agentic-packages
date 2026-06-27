"""Tests for non-interactive gate resolution and init-mode confirm pass.

Covers:
- run_gate_step with non_interactive=True: returns False WITHOUT calling
  io.confirm, announces the skip (CI deadlock fix).
- run_gate_step with non_interactive=False: delegates to io.confirm.
- Pipeline init mode in non-interactive: gate safe-skips, no deadlock.
- Pipeline init mode interactive: gate is confirmed via io.
- Pipeline init mode: a declined python-step confirm skips the write
  (init now uses the inspect→confirm→write flow, same as reproduce).

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_non_interactive.py
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
executor = _load("executor")
reproduce = _load("reproduce")
pipeline_mod = _load("pipeline")

_io_spec = importlib.util.spec_from_file_location("io_adapter", _RUNNER / "io_adapter.py")
assert _io_spec and _io_spec.loader
_io_mod = importlib.util.module_from_spec(_io_spec)
sys.modules["io_adapter"] = _io_mod
_io_spec.loader.exec_module(_io_mod)
ScriptedIO = _io_mod.ScriptedIO

run_gate_step = executor.run_gate_step
SCHEMA_VERSION = contracts.SCHEMA_VERSION
canonical_json = contracts.canonical_json


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
class _ConfirmRaisesIO:
    """IO that raises if confirm() is called — proves it isn't called."""

    def __init__(self):
        self.log: list[str] = []

    def confirm(self, item):
        raise AssertionError(
            f"confirm() must NOT be called in non-interactive mode, got item={item!r}"
        )

    def notify(self, msg: str):
        self.log.append(msg)

    def ask(self, input_spec, default):
        return default

    def agent_step(self, steering_path, context):
        return {"answers_to_persist": {}, "message": "scripted-no-op"}


def _valid_result(module_id, step_id="run", files_written=None, diffs=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "module_id": module_id,
        "step_id": step_id,
        "status": "ok",
        "files_written": files_written or [],
        "diffs": diffs or [],
        "answers_to_persist": {},
        "warnings": [],
        "message": "",
        "error": None,
    }


def _make_plugin_root_with_gate_module(
    tmp_path: Path,
    module_id: str,
    *,
    default_enabled: bool = True,
) -> Path:
    """Build a minimal plugin root with a module that has a gate step then a python step."""
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / module_id
    mod_dir.mkdir(parents=True)

    enabled_str = f"default_enabled = {str(default_enabled).lower()}"
    toml_content = textwrap.dedent(f"""\
        [meta]
        repository = "github.com/test/test"
        author = "Test"

        [module]
        id = "{module_id}"
        name = "Gate Test Module"
        version = "1.0.0"
        description = "Test"
        reconcile = false
        {enabled_str}

        [order]
        requires = []
        after = []
        before = []

        [tools]
        required = []

        [[steps]]
        id = "gate-check"
        kind = "gate"
        message = "Proceed with {module_id}?"

        [[steps]]
        id = "run"
        kind = "python"
    """)
    (mod_dir / "module.toml").write_text(toml_content)

    result_json = json.dumps(_valid_result(module_id))
    (mod_dir / "module.py").write_text(textwrap.dedent(f"""\
        # /// script
        # requires-python = ">=3.11"
        # ///
        import argparse, sys
        p = argparse.ArgumentParser()
        p.add_argument("--plan"); p.add_argument("--step"); p.add_argument("--inspect", action="store_true")
        p.parse_args()
        print({result_json!r})
    """))

    return plugin_root


def _make_write_plugin_root(tmp_path: Path, module_id: str, filename: str, content: str) -> Path:
    """Build a plugin root with a module that actually writes a file (uses sdk)."""
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / module_id
    mod_dir.mkdir(parents=True)

    enabled_str = "default_enabled = true"
    toml_content = textwrap.dedent(f"""\
        [meta]
        repository = "github.com/test/test"
        author = "Test"

        [module]
        id = "{module_id}"
        name = "Write Test Module"
        version = "1.0.0"
        description = "Test"
        reconcile = false
        {enabled_str}

        [order]
        requires = []
        after = []
        before = []

        [tools]
        required = []

        [[steps]]
        id = "run"
        kind = "python"
    """)
    (mod_dir / "module.toml").write_text(toml_content)

    sdk_path = _RUNNER / "sdk.py"
    (mod_dir / "module.py").write_text(textwrap.dedent(f"""\
        # /// script
        # requires-python = ">=3.11"
        # ///
        import argparse, importlib.util, os, sys
        from pathlib import Path

        p = argparse.ArgumentParser()
        p.add_argument("--plan")
        p.add_argument("--step")
        p.add_argument("--inspect", action="store_true")
        args = p.parse_args()

        _sdk_path = {str(sdk_path)!r}
        spec = importlib.util.spec_from_file_location("sdk", _sdk_path)
        assert spec and spec.loader
        sdk_mod = importlib.util.module_from_spec(spec)
        sys.modules["sdk"] = sdk_mod
        spec.loader.exec_module(sdk_mod)

        project_dir = os.environ.get("PROJECT_DIR", ".")
        diff = sdk_mod.idempotent_write(
            {filename!r},
            {content!r},
            project_dir=project_dir,
            reconcile=False,
            inspect=args.inspect,
        )

        result = {{
            "schema_version": sdk_mod.SCHEMA_VERSION,
            "module_id": {module_id!r},
            "step_id": args.step or "run",
            "status": "ok",
            "files_written": [diff.path] if diff.kind in ("create", "modify") else [],
            "diffs": [diff.to_dict()],
            "answers_to_persist": {{}},
            "warnings": [],
            "message": "",
            "error": None,
        }}
        print(sdk_mod.canonical_json(result), end="")
    """))

    return plugin_root


def _make_plan_path(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "plan.json"


# --------------------------------------------------------------------------- #
# run_gate_step: non_interactive=True never calls io.confirm                  #
# --------------------------------------------------------------------------- #
def test_gate_non_interactive_does_not_call_confirm():
    """With non_interactive=True, run_gate_step returns False without calling confirm."""
    io = _ConfirmRaisesIO()
    step = {"id": "checkpoint", "kind": "gate", "message": "Ready to proceed?"}

    # Must not raise (_ConfirmRaisesIO.confirm would raise if called)
    result = run_gate_step(step, "test-mod", io, non_interactive=True)

    assert result is False, "non-interactive gate must return False (safe-skip)"


def test_gate_non_interactive_announces_skip():
    """With non_interactive=True, run_gate_step notifies about the skip."""
    io = _ConfirmRaisesIO()
    step = {"id": "checkpoint", "kind": "gate", "message": "Ready to proceed?"}
    run_gate_step(step, "test-mod", io, non_interactive=True)

    skip_msgs = [m for m in io.log if "non-interactive" in m.lower() or "safe-skip" in m.lower()]
    assert skip_msgs, f"Expected a skip announcement in io.log, got: {io.log!r}"


def test_gate_non_interactive_returns_false():
    """Regardless of io state, non_interactive=True always returns False."""
    io = ScriptedIO(default_confirm=True)  # would return True if confirm were called
    step = {"id": "g", "kind": "gate", "message": "Go?"}
    result = run_gate_step(step, "m", io, non_interactive=True)
    assert result is False


# --------------------------------------------------------------------------- #
# run_gate_step: non_interactive=False delegates to io.confirm                #
# --------------------------------------------------------------------------- #
def test_gate_interactive_true_delegates_to_confirm_and_returns_true():
    """With non_interactive=False and io confirming, returns True."""
    io = ScriptedIO(default_confirm=True)
    step = {"id": "g", "kind": "gate", "message": "Go?"}
    result = run_gate_step(step, "m", io, non_interactive=False)
    assert result is True
    confirm_ops = [e for e in io.log if e["op"] == "confirm"]
    assert confirm_ops, "confirm() must be called in interactive mode"


def test_gate_interactive_false_delegates_to_confirm_and_returns_false():
    """With non_interactive=False and io declining, returns False."""
    io = ScriptedIO(default_confirm=False)
    step = {"id": "g", "kind": "gate", "message": "Go?"}
    result = run_gate_step(step, "m", io, non_interactive=False)
    assert result is False
    confirm_ops = [e for e in io.log if e["op"] == "confirm"]
    assert confirm_ops, "confirm() must be called in interactive mode"


# --------------------------------------------------------------------------- #
# Pipeline init mode: non-interactive gate safe-skips, no deadlock            #
# --------------------------------------------------------------------------- #
def test_pipeline_init_non_interactive_gate_safe_skips(tmp_path, monkeypatch):
    """A non-interactive init run with a gate step does not deadlock and completes."""
    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    plugin_root = _make_plugin_root_with_gate_module(tmp_path, "gate-mod")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    result = pipeline_mod.run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    # Must complete without hanging
    assert result is not None
    assert result.success is True

    # The gate should have been safe-skipped, not caused a confirm prompt
    confirm_ops = [e for e in io.log if e.get("op") == "confirm"]
    gate_confirms = [
        e for e in confirm_ops
        if e.get("path", "").endswith("gate-check") or e.get("item", {}).get("kind") == "gate"
    ]
    # In non-interactive mode the gate code path must not call io.confirm
    # (it returns False immediately). Any confirms in the log are for python steps.
    gate_skips = [
        e for e in io.log
        if e.get("op") == "notify" and "non-interactive" in e.get("msg", "").lower()
    ]
    assert gate_skips, "Expected a non-interactive safe-skip notify for the gate step"


# --------------------------------------------------------------------------- #
# Pipeline init mode: interactive gate confirms via io                        #
# --------------------------------------------------------------------------- #
def test_pipeline_init_interactive_gate_calls_confirm(tmp_path, monkeypatch):
    """An interactive init run with a gate step calls io.confirm for the gate."""
    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    plugin_root = _make_plugin_root_with_gate_module(tmp_path, "gate-mod-interactive")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    result = pipeline_mod.run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result is not None
    assert result.success is True

    # In interactive mode, the gate must call io.confirm
    confirm_ops = [e for e in io.log if e.get("op") == "confirm"]
    gate_confirms = [
        e for e in confirm_ops
        if "gate" in e.get("path", "") or e.get("item", {}).get("kind") == "gate"
    ]
    assert gate_confirms, (
        f"Expected a confirm() call for the gate step in interactive mode. "
        f"confirm ops: {confirm_ops!r}"
    )


# --------------------------------------------------------------------------- #
# Pipeline init mode: declined confirm skips the write (inspect→confirm flow) #
# --------------------------------------------------------------------------- #
def test_pipeline_init_declined_confirm_skips_write(tmp_path, monkeypatch):
    """With default_confirm=False, a file-write step is skipped in init mode."""
    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    plugin_root = _make_write_plugin_root(tmp_path, "write-mod", "output.txt", "hello\n")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Decline all confirms
    io = ScriptedIO(default_confirm=False)
    result = pipeline_mod.run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result is not None
    assert result.success is True
    # The file must NOT have been written because confirm was declined
    assert not (project_dir / "output.txt").exists(), (
        "output.txt must not exist when all confirms are declined in init mode"
    )


def test_pipeline_init_accepted_confirm_writes_file(tmp_path, monkeypatch):
    """With default_confirm=True, a file-write step proceeds in init mode."""
    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    plugin_root = _make_write_plugin_root(tmp_path, "write-mod2", "result.txt", "written\n")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Confirm all
    io = ScriptedIO(default_confirm=True)
    result = pipeline_mod.run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=False,
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result is not None
    assert result.success is True
    assert (project_dir / "result.txt").exists(), (
        "result.txt must exist when confirm is accepted in init mode"
    )
    assert (project_dir / "result.txt").read_text(encoding="utf-8") == "written\n"
