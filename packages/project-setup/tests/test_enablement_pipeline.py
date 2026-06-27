"""Pipeline-level integration tests for the module enablement layer (spec 002).

Tests cover:
  SC-001: fresh run, no selection → only base modules execute
  SC-002: agent-proposed selection recorded; reproduce replays it
  SC-003: requires closure in pipeline context
  SC-004: non-interactive, no selection → base only (safe default)

Uses the same fake-module approach as test_pipeline.py (no real bundled modules,
hermetic, offline).

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_enablement_pipeline.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import textwrap
from pathlib import Path

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"
_PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "skills" / "project-setup"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader, name
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
SCHEMA_VERSION = contracts.SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _valid_result(module_id: str, step_id: str = "run") -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "module_id": module_id,
        "step_id": step_id,
        "status": "ok",
        "files_written": [],
        "diffs": [],
        "answers_to_persist": {},
        "warnings": [],
        "message": "",
        "error": None,
    }


def _make_module(
    plugin_root: Path,
    module_id: str,
    *,
    default_enabled: bool,
    requires: list[str] | None = None,
) -> None:
    """Write a minimal bundled module under plugin_root/modules/<id>/."""
    mod_dir = plugin_root / "modules" / module_id
    mod_dir.mkdir(parents=True, exist_ok=True)

    requires_str = json.dumps(requires or [])
    toml = textwrap.dedent(f"""\
        [meta]
        repository = "github.com/test/test"
        author = "Test"

        [module]
        id = "{module_id}"
        name = "Test {module_id}"
        version = "1.0.0"
        description = "Test module {module_id}"
        reconcile = false
        default_enabled = {str(default_enabled).lower()}

        [order]
        requires = {requires_str}
        after = []
        before = []

        [tools]
        required = []

        [[steps]]
        id = "run"
        kind = "python"
    """)
    (mod_dir / "module.toml").write_text(toml)

    result_json = json.dumps(_valid_result(module_id))
    (mod_dir / "module.py").write_text(textwrap.dedent(f"""\
        # /// script
        # requires-python = ">=3.11"
        # ///
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--plan"); p.add_argument("--step"); p.add_argument("--inspect", action="store_true")
        p.parse_args()
        print({result_json!r})
    """))


def _make_plan_path(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "plan.json"


# --------------------------------------------------------------------------- #
# SC-001: base-only run                                                        #
# --------------------------------------------------------------------------- #

def test_sc001_base_only_run_no_optional_modules(tmp_path, monkeypatch):
    """SC-001: fresh run with no selection → only base modules execute."""
    plugin_root = tmp_path / "plugin"

    # 2 base modules, 2 optional
    _make_module(plugin_root, "base-a", default_enabled=True)
    _make_module(plugin_root, "base-b", default_enabled=True)
    _make_module(plugin_root, "opt-x", default_enabled=False)
    _make_module(plugin_root, "opt-y", default_enabled=False)

    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    project = tmp_path / "proj"
    project.mkdir()

    io = ScriptedIO(
        answers={},  # no "enabled" key → base-only
        default_confirm=True,
    )
    result = run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=plugin_root,
        non_interactive=True,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success, [getattr(e, "how_to_fix", str(e)) for e in result.errors]
    assert set(result.enabled_modules) == {"base-a", "base-b"}
    assert set(result.modules_executed) == {"base-a", "base-b"}
    # Optional modules must NOT have been executed
    assert "opt-x" not in result.modules_executed
    assert "opt-y" not in result.modules_executed


def test_sc001_optional_excluded_from_interview(tmp_path, monkeypatch):
    """SC-001: optional modules not enabled are excluded; pipeline succeeds cleanly."""
    plugin_root = tmp_path / "plugin"
    _make_module(plugin_root, "core-m", default_enabled=True)
    _make_module(plugin_root, "opt-m", default_enabled=False)

    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    project = tmp_path / "proj"
    project.mkdir()

    io = ScriptedIO(answers={}, default_confirm=True)
    result = run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=plugin_root,
        non_interactive=True,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success
    assert result.enabled_modules == ["core-m"]


# --------------------------------------------------------------------------- #
# Selection enables optional modules                                           #
# --------------------------------------------------------------------------- #

def test_selection_enables_optional_module(tmp_path, monkeypatch):
    """A proposed selection enables optional modules beyond base."""
    plugin_root = tmp_path / "plugin"
    _make_module(plugin_root, "base-a", default_enabled=True)
    _make_module(plugin_root, "opt-x", default_enabled=False)
    _make_module(plugin_root, "opt-y", default_enabled=False)

    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    project = tmp_path / "proj"
    project.mkdir()

    io = ScriptedIO(
        answers={"enabled": ["opt-x"]},  # propose opt-x
        default_confirm=True,
    )
    result = run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=plugin_root,
        non_interactive=True,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success
    assert set(result.enabled_modules) == {"base-a", "opt-x"}
    assert "opt-y" not in result.enabled_modules


# --------------------------------------------------------------------------- #
# SC-002: reproduce replays committed enablement                               #
# --------------------------------------------------------------------------- #

def test_sc002_reproduce_replays_committed_enabled(tmp_path, monkeypatch):
    """SC-002: reproduce mode reads [modules].enabled from answers.toml."""
    import tomllib

    plugin_root = tmp_path / "plugin"
    _make_module(plugin_root, "base-a", default_enabled=True)
    _make_module(plugin_root, "opt-x", default_enabled=False)
    _make_module(plugin_root, "opt-y", default_enabled=False)

    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    project = tmp_path / "proj"
    project.mkdir()
    psd = project / ".project-setup"
    psd.mkdir()

    # Write committed answers.toml with [modules].enabled = ["opt-x"]
    (psd / "sources.toml").write_text("[meta]\nskill_version = '0.1.0'\n")
    (psd / "answers.toml").write_text(
        "[modules]\nenabled = [\"opt-x\"]\n\n"
        "[modules.source]\nenabled = \"agent-steered\"\n"
    )

    # In reproduce mode, proposed_enabled should be ignored
    io = ScriptedIO(
        answers={"enabled": ["opt-y"]},  # propose opt-y — must be ignored
        default_confirm=True,
    )
    result = run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=plugin_root,
        non_interactive=True,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success
    assert "opt-x" in result.enabled_modules
    assert "opt-y" not in result.enabled_modules


def test_sc002_selection_persisted_to_answers_toml(tmp_path, monkeypatch):
    """SC-002: the resolved enabled set is written to [modules].enabled."""
    import tomllib

    plugin_root = tmp_path / "plugin"
    _make_module(plugin_root, "base-a", default_enabled=True)
    _make_module(plugin_root, "opt-x", default_enabled=False)

    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    project = tmp_path / "proj"
    project.mkdir()

    io = ScriptedIO(answers={"enabled": ["opt-x"]}, default_confirm=True)
    result = run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=plugin_root,
        non_interactive=True,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success
    answers_path = project / ".project-setup" / "answers.toml"
    assert answers_path.is_file()
    with open(answers_path, "rb") as fh:
        data = tomllib.load(fh)
    enabled = data.get("modules", {}).get("enabled", [])
    assert set(enabled) == {"base-a", "opt-x"}


# --------------------------------------------------------------------------- #
# SC-003: requires closure in pipeline                                         #
# --------------------------------------------------------------------------- #

def test_sc003_requires_closure_auto_enables_dep(tmp_path, monkeypatch):
    """SC-003: enabling a module auto-includes its requires dep."""
    plugin_root = tmp_path / "plugin"
    _make_module(plugin_root, "base-a", default_enabled=True)
    _make_module(plugin_root, "opt-parent", default_enabled=False, requires=["opt-dep"])
    _make_module(plugin_root, "opt-dep", default_enabled=False)

    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    project = tmp_path / "proj"
    project.mkdir()

    # Enable opt-parent only — opt-dep must be auto-pulled
    io = ScriptedIO(answers={"enabled": ["opt-parent"]}, default_confirm=True)
    result = run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=plugin_root,
        non_interactive=True,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success
    assert "opt-dep" in result.enabled_modules
    assert "opt-parent" in result.enabled_modules


def test_sc003_unknown_enabled_id_errors(tmp_path, monkeypatch):
    """SC-003: an enabled id naming an unknown module → error, pipeline aborts."""
    plugin_root = tmp_path / "plugin"
    _make_module(plugin_root, "base-a", default_enabled=True)

    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    project = tmp_path / "proj"
    project.mkdir()

    io = ScriptedIO(answers={"enabled": ["nonexistent-module"]}, default_confirm=True)
    result = run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=plugin_root,
        non_interactive=True,
        plan_path=_make_plan_path(tmp_path),
    )

    assert not result.success
    ErrorCode = contracts.ErrorCode
    assert any(
        getattr(e, "error_code", None) == ErrorCode.UNKNOWN_MODULE
        for e in result.errors
    )


# --------------------------------------------------------------------------- #
# SC-004: non-interactive base-only                                            #
# --------------------------------------------------------------------------- #

def test_sc004_noninteractive_no_selection_base_only(tmp_path, monkeypatch):
    """SC-004: non-interactive + no committed selection → base only (safe default)."""
    plugin_root = tmp_path / "plugin"
    _make_module(plugin_root, "base-a", default_enabled=True)
    _make_module(plugin_root, "opt-x", default_enabled=False)

    monkeypatch.setenv("PROJECT_SETUP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("PROJECT_SETUP_MODULES_DIR", raising=False)

    project = tmp_path / "proj"
    project.mkdir()

    # ScriptedIO with no "enabled" key; non_interactive=True
    io = ScriptedIO(answers={}, default_confirm=True)
    result = run_pipeline(
        project_dir=project,
        io=io,
        plugin_root_path=plugin_root,
        non_interactive=True,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success
    assert result.enabled_modules == ["base-a"]
    assert "opt-x" not in result.modules_executed
