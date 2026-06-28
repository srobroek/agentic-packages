"""Spec 004 Phase 2 — G1 whole-plan preview (FR-007/008/009, SC-003).

Covers:
- The init run renders ONE aggregate plan preview (from the inspect pass) with a
  side-effect class per line, BEFORE any write.
- TTY: a declined preview writes nothing (decline = abort).
- TTY: an accepted preview proceeds (no per-file prompts — anti-pattern #1).
- --non-interactive: the preview prints and the run proceeds (G1 never blocks CI).
- The side-effect classifier maps gate enrichment → preview tags (FR-008, OQ-3).

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_whole_plan_preview.py
"""

from __future__ import annotations

import importlib.util
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


reproduce = _load("reproduce")
pipeline_mod = _load("pipeline")
_io_mod = _load("io_adapter")
ScriptedIO = _io_mod.ScriptedIO
run_pipeline = pipeline_mod.run_pipeline


# --------------------------------------------------------------------------- #
# Unit: the side-effect classifier (FR-008, no per-module table)              #
# --------------------------------------------------------------------------- #
def test_classify_install_gate():
    step = {"kind": "gate", "allow_flag": "allow-install"}
    classes = reproduce._side_effect_classes(step, None)
    assert "[installs N pkgs]" in classes and "[network]" in classes


def test_classify_public_repo_gate():
    step = {"kind": "gate", "allow_flag": "allow-public-repo"}
    classes = reproduce._side_effect_classes(step, None)
    assert "[creates remote]" in classes and "[network]" in classes


def test_classify_generator_gate():
    step = {"kind": "gate", "skip_flag": "no-external-generators"}
    classes = reproduce._side_effect_classes(step, None)
    assert "[runs external generator]" in classes


def test_classify_agent_step():
    assert reproduce._side_effect_classes({"kind": "agent"}, None) == ["[agent decision]"]


# --------------------------------------------------------------------------- #
# Plugin: a single python write step                                           #
# --------------------------------------------------------------------------- #
def _make_write_plugin(tmp_path: Path) -> Path:
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / "w"
    mod_dir.mkdir(parents=True)
    (mod_dir / "module.toml").write_text(textwrap.dedent("""\
        [meta]
        repository = "github.com/test/test"
        author = "Test"
        [module]
        id = "w"
        name = "W"
        version = "1.0.0"
        description = "d"
        reconcile = false
        default_enabled = true
        [[steps]]
        id = "write"
        kind = "python"
    """))
    sdk_path = _RUNNER / "sdk.py"
    (mod_dir / "module.py").write_text(textwrap.dedent(f"""\
        # /// script
        # requires-python = ">=3.11"
        # ///
        import argparse, importlib.util, os, sys
        p = argparse.ArgumentParser()
        p.add_argument("--plan"); p.add_argument("--step")
        p.add_argument("--inspect", action="store_true")
        args = p.parse_args()
        spec = importlib.util.spec_from_file_location("sdk", {str(sdk_path)!r})
        sdk = importlib.util.module_from_spec(spec); sys.modules["sdk"] = sdk
        spec.loader.exec_module(sdk)
        project_dir = os.environ.get("PROJECT_DIR", ".")
        diff = sdk.idempotent_write("out.txt", "hi\\n", project_dir=project_dir,
                                    reconcile=False, inspect=args.inspect)
        r = sdk.ModuleResult(module_id="w", step_id=args.step or "write", status="ok",
            files_written=[diff.path] if diff.kind in ("create","modify") else [], diffs=[diff])
        sdk.emit_result(r)
    """))
    return plugin_root


def _plan_path(tmp_path):
    return tmp_path / "cache" / "plan.json"


# --------------------------------------------------------------------------- #
# SC-003 — preview before writes; decline aborts; CI prints + proceeds         #
# --------------------------------------------------------------------------- #
def test_init_renders_preview_before_write(tmp_path):
    plugin_root = _make_write_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    r = run_pipeline(
        project_dir=project_dir, io=io, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    assert r.success
    # A preview was emitted (notify with the plan-preview header) BEFORE the write.
    notifies = [e["msg"] for e in io.log if e["op"] == "notify"]
    assert any("Plan preview" in m for m in notifies), notifies
    assert (project_dir / "out.txt").exists()


def test_init_decline_writes_nothing(tmp_path):
    plugin_root = _make_write_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Decline the single whole-plan confirm.
    io = ScriptedIO(confirmations={"<whole-plan>": False, "all": True})
    r = run_pipeline(
        project_dir=project_dir, io=io, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    assert r.success  # a declined plan is a clean no-op, not a failure
    assert not (project_dir / "out.txt").exists()


def test_init_single_confirm_not_per_file(tmp_path):
    # G1 is ONE confirm for the whole plan; there must be no per-file write prompt
    # (anti-pattern #1). The only confirm is the <whole-plan> one.
    plugin_root = _make_write_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    run_pipeline(
        project_dir=project_dir, io=io, non_interactive=False,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    confirm_paths = [e["path"] for e in io.log if e["op"] == "confirm"]
    assert confirm_paths == ["<whole-plan>"], confirm_paths


def test_init_non_interactive_prints_and_proceeds(tmp_path):
    plugin_root = _make_write_plugin(tmp_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    r = run_pipeline(
        project_dir=project_dir, io=io, non_interactive=True,
        plugin_root_path=plugin_root, plan_path=_plan_path(tmp_path),
    )
    assert r.success
    # No confirm() at all in CI; the preview is printed and the run proceeds.
    assert [e for e in io.log if e["op"] == "confirm"] == []
    assert (project_dir / "out.txt").exists()
    notifies = [e["msg"] for e in io.log if e["op"] == "notify"]
    assert any("Plan preview" in m for m in notifies)
