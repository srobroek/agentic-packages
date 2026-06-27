"""Tests for executor.py — Model-B subprocess driver + result gate.

Key cases:
- Invocation shape (correct uv command built + env set)
- Result-gate: rejects malformed JSON, missing keys, wrong schema_version
- PATH_ESCAPE guard: files_written outside project_dir raises
- Per-module failure isolation: subprocess non-zero → StepOutcome(ok=False), not raise
- UV_MISSING mid-run hard-fail: GateFailure raised, not soft-skip

Fake module.py: written to a tmp modules/<id>/ dir and invoked via uv run.
The fake echoes a caller-supplied JSON to stdout.

Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_executor.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

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

run_python_step = executor.run_python_step
run_gate_step = executor.run_gate_step
run_agent_step = executor.run_agent_step
StepOutcome = executor.StepOutcome
GateFailure = contracts.GateFailure
ErrorCode = contracts.ErrorCode
SCHEMA_VERSION = contracts.SCHEMA_VERSION
canonical_json = contracts.canonical_json


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _valid_result(module_id="fake-mod", step_id="run", files_written=None):
    """Return a dict that satisfies the result contract."""
    return {
        "schema_version": SCHEMA_VERSION,
        "module_id": module_id,
        "step_id": step_id,
        "status": "ok",
        "files_written": files_written or [],
        "diffs": [],
        "answers_to_persist": {},
        "warnings": [],
        "message": "",
        "error": None,
    }


def _make_module_py(tmp_path: Path, module_id: str, stdout_json: dict) -> tuple[Path, Path]:
    """Write a fake module.py that prints stdout_json and exits 0.

    Returns (plugin_root, module_rel_root) so run_python_step can be called.
    The module.py accepts --plan, --step, --inspect flags without error.
    """
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / module_id
    mod_dir.mkdir(parents=True)

    json_src = json.dumps(stdout_json)
    module_py = mod_dir / "module.py"
    module_py.write_text(textwrap.dedent(f"""\
        import argparse, json, sys
        p = argparse.ArgumentParser()
        p.add_argument("--plan")
        p.add_argument("--step")
        p.add_argument("--inspect", action="store_true")
        p.parse_args()
        print({json_src!r})
    """))
    return plugin_root, f"modules/{module_id}"


def _make_failing_module_py(tmp_path: Path, module_id: str, exit_code: int = 1) -> tuple[Path, Path]:
    """Write a fake module.py that exits with exit_code."""
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / module_id
    mod_dir.mkdir(parents=True)

    module_py = mod_dir / "module.py"
    module_py.write_text(textwrap.dedent(f"""\
        import sys
        sys.exit({exit_code})
    """))
    return plugin_root, f"modules/{module_id}"


def _frozen_plan(tmp_path: Path, module_id: str = "fake-mod") -> Path:
    """Write a minimal frozen plan and return its path."""
    plan_data = {
        "schema_version": SCHEMA_VERSION,
        "mode": "init",
        "order": [module_id],
        "modules": {
            module_id: {
                "id": module_id,
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": f"modules/{module_id}",
                "answers": {},
                "steps": [{"id": "run", "kind": "python"}],
            }
        },
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(canonical_json(plan_data))
    return plan_path


# --------------------------------------------------------------------------- #
# Invocation shape                                                             #
# --------------------------------------------------------------------------- #
def test_run_python_step_executes_module_and_returns_ok(tmp_path):
    result = _valid_result()
    plugin_root, rel_root = _make_module_py(tmp_path, "fake-mod", result)
    plan_path = _frozen_plan(tmp_path)

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root=rel_root,
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is True
    assert outcome.module_id == "fake-mod"
    assert outcome.step_id == "run"
    assert outcome.result is not None


def test_run_python_step_passes_inspect_flag(tmp_path):
    """--inspect is forwarded; module can accept it without error."""
    result = _valid_result()
    plugin_root, rel_root = _make_module_py(tmp_path, "fake-mod", result)
    plan_path = _frozen_plan(tmp_path)

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root=rel_root,
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
        inspect=True,
    )
    assert outcome.ok is True
    assert outcome.inspect is True


def test_run_python_step_sets_project_dir_env(tmp_path, monkeypatch):
    """PROJECT_DIR env var is passed to the subprocess."""
    # Module that prints the PROJECT_DIR it sees
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / "env-mod"
    mod_dir.mkdir(parents=True)

    valid = _valid_result("env-mod")
    json_src = json.dumps(valid)

    module_py = mod_dir / "module.py"
    module_py.write_text(textwrap.dedent(f"""\
        import argparse, os, json, sys
        p = argparse.ArgumentParser()
        p.add_argument("--plan"); p.add_argument("--step"); p.add_argument("--inspect", action="store_true")
        p.parse_args()
        print({json_src!r})
    """))
    plan_path = _frozen_plan(tmp_path, "env-mod")
    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root="modules/env-mod",
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is True


# --------------------------------------------------------------------------- #
# Result-gate: malformed output                                                #
# --------------------------------------------------------------------------- #
def test_result_gate_rejects_non_json_stdout(tmp_path):
    """If the module prints non-JSON, outcome is ok=False with RESULT_SHAPE."""
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / "bad-mod"
    mod_dir.mkdir(parents=True)
    (mod_dir / "module.py").write_text(textwrap.dedent("""\
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--plan"); p.add_argument("--step"); p.add_argument("--inspect", action="store_true")
        p.parse_args()
        print("this is not json")
    """))
    plan_path = _frozen_plan(tmp_path, "bad-mod")

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root="modules/bad-mod",
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is False
    assert outcome.error is not None
    assert outcome.error.error_code == ErrorCode.RESULT_SHAPE


def test_result_gate_rejects_missing_required_keys(tmp_path):
    """Missing required keys → RESULT_SHAPE error."""
    # Only partial result: missing files_written, diffs
    bad = {"schema_version": SCHEMA_VERSION, "module_id": "x", "step_id": "y", "status": "ok"}
    plugin_root, rel_root = _make_module_py(tmp_path, "partial-mod", bad)
    plan_path = _frozen_plan(tmp_path, "partial-mod")

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root=rel_root,
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is False
    assert outcome.error.error_code == ErrorCode.RESULT_SHAPE


def test_result_gate_rejects_wrong_schema_version(tmp_path):
    """schema_version mismatch → RESULT_SHAPE error."""
    bad = _valid_result()
    bad["schema_version"] = 999
    plugin_root, rel_root = _make_module_py(tmp_path, "ver-mod", bad)
    plan_path = _frozen_plan(tmp_path, "ver-mod")

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root=rel_root,
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is False
    assert outcome.error.error_code == ErrorCode.RESULT_SHAPE


def test_result_gate_rejects_json_list_not_object(tmp_path):
    """JSON array instead of object → RESULT_SHAPE."""
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / "list-mod"
    mod_dir.mkdir(parents=True)
    (mod_dir / "module.py").write_text(textwrap.dedent("""\
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--plan"); p.add_argument("--step"); p.add_argument("--inspect", action="store_true")
        p.parse_args()
        print('[1, 2, 3]')
    """))
    plan_path = _frozen_plan(tmp_path, "list-mod")

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root="modules/list-mod",
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is False
    assert outcome.error.error_code == ErrorCode.RESULT_SHAPE


# --------------------------------------------------------------------------- #
# PATH_ESCAPE guard                                                            #
# --------------------------------------------------------------------------- #
def test_path_escape_guard_rejects_files_outside_project(tmp_path):
    """files_written containing a path outside project_dir → PATH_ESCAPE."""
    # Report a file that escapes via ../
    outside_path = "../outside.txt"
    result = _valid_result(files_written=[outside_path])
    plugin_root, rel_root = _make_module_py(tmp_path, "escape-mod", result)
    plan_path = _frozen_plan(tmp_path, "escape-mod")

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root=rel_root,
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=project_dir,
    )
    assert outcome.ok is False
    assert outcome.error.error_code == ErrorCode.PATH_ESCAPE


def test_path_escape_guard_allows_nested_relative_path(tmp_path):
    """files_written with a safe nested path is accepted."""
    result = _valid_result(files_written=["src/main.py"])
    plugin_root, rel_root = _make_module_py(tmp_path, "nested-mod", result)
    plan_path = _frozen_plan(tmp_path, "nested-mod")

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root=rel_root,
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is True


# --------------------------------------------------------------------------- #
# Per-module failure isolation                                                 #
# --------------------------------------------------------------------------- #
def test_failing_module_returns_ok_false_not_exception(tmp_path):
    """A non-zero exit from module.py yields ok=False, does NOT raise."""
    plugin_root, rel_root = _make_failing_module_py(tmp_path, "fail-mod", exit_code=1)
    plan_path = _frozen_plan(tmp_path, "fail-mod")

    # Must not raise — isolation contract
    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root=rel_root,
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is False
    assert outcome.error is not None


def test_failing_module_with_exit_2_is_isolated(tmp_path):
    plugin_root, rel_root = _make_failing_module_py(tmp_path, "fail2-mod", exit_code=2)
    plan_path = _frozen_plan(tmp_path, "fail2-mod")

    outcome = run_python_step(
        plugin_root_path=plugin_root,
        module_rel_root=rel_root,
        step_id="run",
        frozen_plan_path=plan_path,
        project_dir=tmp_path,
    )
    assert outcome.ok is False


# --------------------------------------------------------------------------- #
# UV_MISSING mid-run hard-fail                                                 #
# --------------------------------------------------------------------------- #
def test_uv_missing_mid_run_raises_gate_failure(tmp_path, monkeypatch):
    """If uv vanishes mid-run, GateFailure(UV_MISSING) is raised (hard-fail)."""
    import shutil as _shutil

    # Patch shutil.which to return None for "uv" only
    orig_which = _shutil.which

    def patched_which(name, *args, **kwargs):
        if name == "uv":
            return None
        return orig_which(name, *args, **kwargs)

    monkeypatch.setattr(_shutil, "which", patched_which)

    result = _valid_result()
    plugin_root, rel_root = _make_module_py(tmp_path, "uv-gone", result)
    plan_path = _frozen_plan(tmp_path, "uv-gone")

    with pytest.raises(GateFailure) as exc_info:
        run_python_step(
            plugin_root_path=plugin_root,
            module_rel_root=rel_root,
            step_id="run",
            frozen_plan_path=plan_path,
            project_dir=tmp_path,
        )
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.UV_MISSING in codes


# --------------------------------------------------------------------------- #
# Gate step                                                                    #
# --------------------------------------------------------------------------- #
def test_run_gate_step_calls_io_notify_and_confirm(tmp_path):
    from io_adapter import ScriptedIO
    io = ScriptedIO(default_confirm=True)
    step = {"id": "checkpoint", "kind": "gate", "message": "Ready to proceed?"}
    confirmed = run_gate_step(step, "test-mod", io)
    assert confirmed is True
    assert any(e["op"] == "notify" for e in io.log)
    assert any(e["op"] == "confirm" for e in io.log)


def test_run_gate_step_returns_false_when_declined(tmp_path):
    from io_adapter import ScriptedIO
    io = ScriptedIO(default_confirm=False)
    step = {"id": "check", "kind": "gate", "message": "Proceed?"}
    confirmed = run_gate_step(step, "test-mod", io)
    assert confirmed is False


# --------------------------------------------------------------------------- #
# Agent step                                                                   #
# --------------------------------------------------------------------------- #
def test_run_agent_step_delegates_to_io(tmp_path):
    from io_adapter import ScriptedIO
    agent_resp = {
        "answers_to_persist": {"choice": {"value": "option-a", "source": "agent-steered"}},
        "message": "chose option-a",
    }
    io = ScriptedIO(agent_responses={"steering/choose.md": agent_resp})
    step = {"id": "decide", "kind": "agent", "steering": "steering/choose.md"}
    result = run_agent_step(step, "agent-mod", io)
    assert result["answers_to_persist"]["choice"]["value"] == "option-a"
    assert any(e["op"] == "agent_step" for e in io.log)


# --------------------------------------------------------------------------- #
# StepOutcome helpers                                                          #
# --------------------------------------------------------------------------- #
def test_step_outcome_files_written_empty_on_error():
    outcome = StepOutcome(ok=False, module_id="m", step_id="s")
    assert outcome.files_written() == []


def test_step_outcome_files_written_from_result():
    outcome = StepOutcome(
        ok=True,
        module_id="m",
        step_id="s",
        result=_valid_result(files_written=[".gitignore", "README.md"]),
    )
    assert outcome.files_written() == [".gitignore", "README.md"]


def test_step_outcome_diffs_empty_on_no_result():
    outcome = StepOutcome(ok=True, module_id="m", step_id="s")
    assert outcome.diffs() == []
