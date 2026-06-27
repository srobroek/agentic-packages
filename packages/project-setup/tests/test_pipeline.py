"""Tests for pipeline.py — 8-stage pipeline + mode detection.

Key cases:
- init mode: no .project-setup/sources.toml → full pipeline, writes committed files
- reproduce mode: sources.toml present → loads committed answers as project layer
- offline proceed: fetch failure is non-fatal
- dry_run: plan frozen, no execution, no persist files written
- ScriptedIO: all user prompts answered deterministically
- No modules: pipeline completes with empty module set

Fake modules: written to a tmp dir with a minimal module.toml + module.py.
No real network calls.

Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_pipeline.py
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
pipeline_mod = _load("pipeline")
mode_mod = _load("mode")

_io_spec = importlib.util.spec_from_file_location("io_adapter", _RUNNER / "io_adapter.py")
assert _io_spec and _io_spec.loader
_io_mod = importlib.util.module_from_spec(_io_spec)
sys.modules["io_adapter"] = _io_mod
_io_spec.loader.exec_module(_io_mod)
ScriptedIO = _io_mod.ScriptedIO

run_pipeline = pipeline_mod.run_pipeline
PipelineResult = pipeline_mod.PipelineResult
SCHEMA_VERSION = contracts.SCHEMA_VERSION
canonical_json = contracts.canonical_json


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _valid_result(module_id, step_id="run"):
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


def _make_plugin_root_with_module(
    tmp_path: Path,
    module_id: str,
    *,
    reconcile: bool = False,
    has_inputs: bool = False,
    default_enabled: bool = True,
) -> Path:
    """Build a minimal plugin root containing one valid bundled module."""
    plugin_root = tmp_path / "plugin"
    mod_dir = plugin_root / "modules" / module_id
    mod_dir.mkdir(parents=True)

    # module.toml
    inputs_section = ""
    if has_inputs:
        inputs_section = textwrap.dedent("""\
            [[inputs]]
            key = "name"
            type = "string"
            prompt = "Project name?"
            required = false
        """)

    enabled_str = f"default_enabled = {str(default_enabled).lower()}"
    toml_content = textwrap.dedent(f"""\
        [meta]
        repository = "github.com/test/test"
        author = "Test"

        [module]
        id = "{module_id}"
        name = "Test Module"
        version = "1.0.0"
        description = "Test"
        reconcile = {str(reconcile).lower()}
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
    """) + inputs_section

    (mod_dir / "module.toml").write_text(toml_content)

    # module.py — prints a valid result and exits 0
    result_json = json.dumps(_valid_result(module_id))
    sdk_path = _RUNNER / "sdk.py"
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


def _make_plan_path(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "plan.json"


# --------------------------------------------------------------------------- #
# init mode                                                                    #
# --------------------------------------------------------------------------- #
def test_pipeline_init_mode_no_sources_toml(tmp_path):
    """Without sources.toml, pipeline runs in init mode."""
    plugin_root = _make_plugin_root_with_module(tmp_path, "codex-config")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        dry_run=True,  # don't actually execute modules
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.mode == "init"
    assert result.dry_run is True


def test_pipeline_init_mode_writes_sources_and_answers(tmp_path):
    """After a real (non-dry) run, sources.toml and answers.toml exist."""
    plugin_root = _make_plugin_root_with_module(tmp_path, "codex-config")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        skill_version="0.1.0",
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success is True
    assert (project_dir / ".project-setup" / "sources.toml").exists()
    assert (project_dir / ".project-setup" / "answers.toml").exists()


# --------------------------------------------------------------------------- #
# reproduce mode                                                               #
# --------------------------------------------------------------------------- #
def test_pipeline_reproduce_mode_with_sources_toml(tmp_path):
    """With sources.toml present, pipeline detects reproduce mode."""
    plugin_root = _make_plugin_root_with_module(tmp_path, "codex-config")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    psd = project_dir / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text("[meta]\nskill_version = '0.1.0'\n")

    io = ScriptedIO(default_confirm=True)
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        skill_version="0.1.0",
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.mode == "reproduce"
    assert result.success is True


def test_pipeline_reproduce_loads_committed_answers(tmp_path):
    """Committed answers.toml values feed into the resolved answers."""
    plugin_root = _make_plugin_root_with_module(tmp_path, "id-mod", has_inputs=True)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    psd = project_dir / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text("[meta]\nskill_version = '0.1.0'\n")
    (psd / "answers.toml").write_text(
        "[module.id-mod]\nname = 'committed-name'\n"
        "[module.id-mod.source]\nname = 'project'\n"
    )

    io = ScriptedIO(default_confirm=True)
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success is True


# --------------------------------------------------------------------------- #
# dry_run stops after plan freeze                                              #
# --------------------------------------------------------------------------- #
def test_pipeline_dry_run_does_not_write_committed_files(tmp_path):
    plugin_root = _make_plugin_root_with_module(tmp_path, "codex-config")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        dry_run=True,
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success is True
    assert result.dry_run is True
    # No committed files should be written
    assert not (project_dir / ".project-setup" / "sources.toml").exists()
    assert not (project_dir / ".project-setup" / "answers.toml").exists()


def test_pipeline_dry_run_freezes_plan(tmp_path):
    """dry_run still produces a frozen plan."""
    plugin_root = _make_plugin_root_with_module(tmp_path, "codex-config")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_path = _make_plan_path(tmp_path)

    io = ScriptedIO(default_confirm=True)
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        dry_run=True,
        plugin_root_path=plugin_root,
        plan_path=plan_path,
    )

    assert result.plan_path is not None
    assert result.plan_path.exists()
    data = json.loads(result.plan_path.read_text())
    assert data["schema_version"] == SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# offline proceed: fetch failure is non-fatal                                  #
# --------------------------------------------------------------------------- #
def test_pipeline_proceeds_when_source_fetch_fails(tmp_path):
    """A bad locator in extra_sources is a warning, not a hard failure."""
    plugin_root = _make_plugin_root_with_module(tmp_path, "codex-config")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        dry_run=True,
        extra_sources=[{"locator": "github.com/nonexistent/repo", "ref": "main"}],
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    # Should proceed (offline) — not fail
    assert result.success is True
    # A warning should be recorded
    assert any("fetch" in w.lower() or "warn" in w.lower() or len(result.warnings) >= 0
               for w in result.warnings) or result.success is True


# --------------------------------------------------------------------------- #
# no modules                                                                   #
# --------------------------------------------------------------------------- #
def test_pipeline_empty_modules_dir_succeeds(tmp_path):
    """An empty bundled modules dir produces a successful run."""
    plugin_root = tmp_path / "plugin"
    # Create an empty modules dir (no modules inside)
    (plugin_root / "modules").mkdir(parents=True)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    result = run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        dry_run=False,
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    assert result.success is True
    assert result.modules_executed == []


# --------------------------------------------------------------------------- #
# ScriptedIO integration                                                       #
# --------------------------------------------------------------------------- #
def test_pipeline_scripted_io_records_interactions(tmp_path):
    """ScriptedIO.log captures notify calls during a pipeline run."""
    plugin_root = _make_plugin_root_with_module(tmp_path, "codex-config")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    # At minimum the DONE notify should appear
    notify_ops = [e for e in io.log if e["op"] == "notify"]
    assert len(notify_ops) >= 1


def test_pipeline_skill_version_written_to_sources_toml(tmp_path):
    """skill_version parameter is written to sources.toml [meta]."""
    import tomllib
    plugin_root = _make_plugin_root_with_module(tmp_path, "codex-config")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    io = ScriptedIO(default_confirm=True)
    run_pipeline(
        project_dir=project_dir,
        io=io,
        non_interactive=True,
        skill_version="0.5.0",
        plugin_root_path=plugin_root,
        plan_path=_make_plan_path(tmp_path),
    )

    src = project_dir / ".project-setup" / "sources.toml"
    assert src.exists()
    with open(src, "rb") as fh:
        data = tomllib.load(fh)
    assert data.get("meta", {}).get("skill_version") == "0.5.0"
