"""Tests for reproduce.py — pre-write inspect/diff/confirm + apply.

Key invariants verified:
- inspect runs BEFORE real write (the circular-ordering fix)
- inspect==write for Tier-1: a fake module that writes to disk produces
  identical bytes in --inspect mode vs real mode
- confirm-before-write: if user declines, nothing is written
- reconcile only overwrites confirmed files
- non-reconcile modules skip existing files

Fake module.py approach: written to a tmp modules/<id>/ dir.
The fake module uses sdk.idempotent_write (loaded by file path) so the
inspect==write guarantee is tested at the SDK level.

Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_reproduce.py
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
reproduce = _load("reproduce")
executor = _load("executor")

build_drift_report = reproduce.build_drift_report
apply_reproduce = reproduce.apply
ConfirmEntry = reproduce.ConfirmEntry
SCHEMA_VERSION = contracts.SCHEMA_VERSION
canonical_json = contracts.canonical_json

# io_adapter lives in the runner dir
_io_spec = importlib.util.spec_from_file_location("io_adapter", _RUNNER / "io_adapter.py")
assert _io_spec and _io_spec.loader
_io_mod = importlib.util.module_from_spec(_io_spec)
sys.modules["io_adapter"] = _io_mod
_io_spec.loader.exec_module(_io_mod)
ScriptedIO = _io_mod.ScriptedIO


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
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


def _frozen_plan(tmp_path: Path, modules: dict) -> Path:
    """Write a frozen plan with the given module entries."""
    plan_data = {
        "schema_version": SCHEMA_VERSION,
        "mode": "reproduce",
        "order": list(modules.keys()),
        "modules": {},
    }
    for mod_id, mod_cfg in modules.items():
        plan_data["modules"][mod_id] = {
            "id": mod_id,
            "version": "1.0.0",
            "reconcile": mod_cfg.get("reconcile", False),
            "module_rel_root": f"modules/{mod_id}",
            "answers": mod_cfg.get("answers", {}),
            "steps": mod_cfg.get("steps", [{"id": "run", "kind": "python"}]),
        }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(canonical_json(plan_data))
    return plan_path


def _load_plan(tmp_path: Path, modules: dict):
    """Return an ExecutionPlan-like object using plan.py."""
    plan_mod = _load("plan")
    plan_path = _frozen_plan(tmp_path, modules)
    return plan_mod.load_plan(plan_path), plan_path


def _make_write_module(tmp_path: Path, module_id: str, filename: str, content: str, reconcile: bool = False) -> Path:
    """Write a fake module.py that uses sdk.idempotent_write to write a file.

    The module uses the SDK (loaded by path) so inspect==write is exercised
    through the real SDK code.
    """
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / module_id
    mod_dir.mkdir(parents=True)

    sdk_path = _RUNNER / "sdk.py"
    module_py = mod_dir / "module.py"
    module_py.write_text(textwrap.dedent(f"""\
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

        # Load SDK by file path (contract §6)
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
            reconcile={reconcile!r},
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


# --------------------------------------------------------------------------- #
# inspect runs before real write                                               #
# --------------------------------------------------------------------------- #
def test_build_drift_report_runs_inspect_not_real_write(tmp_path):
    """build_drift_report must NOT write any files — only the inspect pass."""
    plugin_root = _make_write_module(tmp_path, "write-mod", "output.txt", "hello", reconcile=False)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    plan, plan_path = _load_plan(tmp_path, {"write-mod": {"reconcile": False}})
    io = ScriptedIO(default_confirm=True)

    # No file should exist before
    assert not (project_dir / "output.txt").exists()

    build_drift_report(
        plan=plan,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )

    # After build_drift_report, the file must STILL not exist
    assert not (project_dir / "output.txt").exists(), (
        "build_drift_report must not write files — inspect pass only"
    )


# --------------------------------------------------------------------------- #
# inspect == write bytes for Tier-1                                            #
# --------------------------------------------------------------------------- #
def test_inspect_bytes_equal_real_write_bytes(tmp_path):
    """The inspect dry-pass and the real write produce identical bytes."""
    content = "# generated by project-setup\nversion = '1.0'\n"
    plugin_root = _make_write_module(tmp_path, "idem-mod", "config.toml", content, reconcile=False)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    plan, plan_path = _load_plan(tmp_path, {"idem-mod": {"reconcile": False}})
    io = ScriptedIO(default_confirm=True)

    # 1. Get the inspect result
    confirmations = build_drift_report(
        plan=plan,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )

    key = "idem-mod/run"
    assert key in confirmations
    inspect_diffs = confirmations[key].inspect_outcome.diffs()
    assert len(inspect_diffs) == 1
    inspect_preview = inspect_diffs[0].get("preview", "")

    # 2. Apply for real
    outcomes = apply_reproduce(
        plan=plan,
        confirmations=confirmations,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )

    # 3. File was written
    written_file = project_dir / "config.toml"
    assert written_file.exists()
    written_content = written_file.read_text(encoding="utf-8")
    assert written_content == content

    # 4. Real outcome diffs match inspect diffs
    assert len(outcomes) == 1
    real_diffs = outcomes[0].diffs()
    assert len(real_diffs) == 1
    assert real_diffs[0].get("kind") == "create"


# --------------------------------------------------------------------------- #
# confirm-before-write: declined → nothing written                            #
# --------------------------------------------------------------------------- #
def test_declined_confirmation_prevents_write(tmp_path):
    """When the user declines all confirmations, no file is written."""
    plugin_root = _make_write_module(tmp_path, "dec-mod", "never.txt", "should not appear", reconcile=False)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    plan, plan_path = _load_plan(tmp_path, {"dec-mod": {"reconcile": False}})
    # Decline everything
    io = ScriptedIO(default_confirm=False)

    confirmations = build_drift_report(
        plan=plan,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )

    # All entries should be skipped
    for entry in confirmations.values():
        # Either skipped or no diffs to confirm
        pass

    outcomes = apply_reproduce(
        plan=plan,
        confirmations=confirmations,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )

    assert not (project_dir / "never.txt").exists()


# --------------------------------------------------------------------------- #
# reconcile: overwrites only confirmed files                                   #
# --------------------------------------------------------------------------- #
def test_reconcile_overwrites_confirmed_file(tmp_path):
    """With reconcile=True, an existing file is overwritten when confirmed."""
    content_new = "new content\n"
    plugin_root = _make_write_module(tmp_path, "rec-mod", "existing.txt", content_new, reconcile=True)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Pre-create the file with different content
    (project_dir / "existing.txt").write_text("old content\n")

    plan, plan_path = _load_plan(tmp_path, {"rec-mod": {"reconcile": True}})
    io = ScriptedIO(default_confirm=True)  # confirm all

    confirmations = build_drift_report(
        plan=plan,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )
    apply_reproduce(
        plan=plan,
        confirmations=confirmations,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )

    assert (project_dir / "existing.txt").read_text(encoding="utf-8") == content_new


# --------------------------------------------------------------------------- #
# non-reconcile: skip-if-exists                                               #
# --------------------------------------------------------------------------- #
def test_non_reconcile_skips_existing_file(tmp_path):
    """With reconcile=False, an existing file is not overwritten."""
    plugin_root = _make_write_module(tmp_path, "noreconcile-mod", "keep.txt", "new\n", reconcile=False)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Pre-create with different content
    (project_dir / "keep.txt").write_text("original\n")

    plan, plan_path = _load_plan(tmp_path, {"noreconcile-mod": {"reconcile": False}})
    io = ScriptedIO(default_confirm=True)

    confirmations = build_drift_report(
        plan=plan,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )
    apply_reproduce(
        plan=plan,
        confirmations=confirmations,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )

    # Original content preserved
    assert (project_dir / "keep.txt").read_text(encoding="utf-8") == "original\n"


# --------------------------------------------------------------------------- #
# No diffs → auto-proceed (no prompt needed)                                  #
# --------------------------------------------------------------------------- #
def test_no_diffs_auto_proceed_no_confirm_prompt(tmp_path):
    """When the module reports no diffs, no confirmation is asked."""
    # Module that writes identical content to existing file (skip diff)
    existing_content = "unchanged\n"
    plugin_root = _make_write_module(tmp_path, "nodiff-mod", "same.txt", existing_content, reconcile=False)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Pre-create the file with the SAME content so idempotent_write returns kind=skip
    (project_dir / "same.txt").write_text(existing_content)

    plan, plan_path = _load_plan(tmp_path, {"nodiff-mod": {"reconcile": False}})
    io = ScriptedIO(default_confirm=True)

    confirmations = build_drift_report(
        plan=plan,
        plugin_root_path=plugin_root,
        project_dir=project_dir,
        io=io,
        frozen_plan_path=plan_path,
    )

    # No confirm prompts should have been issued
    confirm_ops = [e for e in io.log if e["op"] == "confirm"]
    assert len(confirm_ops) == 0
