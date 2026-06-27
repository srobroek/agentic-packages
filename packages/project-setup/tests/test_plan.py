"""Tests for plan.py — ExecutionPlan build, canonical freeze, and load.

Key assertions:
- Two builds from the same inputs produce BYTE-IDENTICAL JSON (canonical_json).
- No absolute paths in the frozen plan output.
- load_plan raises GateFailure on bad schema_version or missing keys.

Import-by-path pattern from test_contracts.py.
Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_plan.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
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
plan_mod = _load("plan")

build_plan = plan_mod.build_plan
freeze = plan_mod.freeze
load_plan = plan_mod.load_plan
ExecutionPlan = plan_mod.ExecutionPlan
PlanModule = plan_mod.PlanModule
GateFailure = contracts.GateFailure
ErrorCode = contracts.ErrorCode
SCHEMA_VERSION = contracts.SCHEMA_VERSION
canonical_json = contracts.canonical_json


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def make_step(id="run", kind="python"):
    return SimpleNamespace(id=id, kind=kind, steering=None, message=None)


def make_manifest(id: str, version="1.0.0", reconcile=False, steps=None, toml_path=None):
    m = SimpleNamespace(
        id=id,
        version=version,
        reconcile=reconcile,
        steps=steps or [make_step()],
        order={"requires": [], "after": [], "before": []},
        tools={"required": []},
        inputs=[],
        _toml_path=toml_path,
    )
    return m


# --------------------------------------------------------------------------- #
# Build plan                                                                   #
# --------------------------------------------------------------------------- #
def test_build_plan_basic(tmp_path):
    m = make_manifest("core-identity", version="1.0.0", reconcile=True)
    answers = {"core-identity": {"name": "acme"}}
    plan = build_plan([m], resolved_answers=answers, ordered_ids=["core-identity"])

    assert plan.schema_version == SCHEMA_VERSION
    assert plan.mode == "init"
    assert plan.order == ["core-identity"]
    assert "core-identity" in plan.modules
    pm = plan.modules["core-identity"]
    assert pm.id == "core-identity"
    assert pm.version == "1.0.0"
    assert pm.reconcile is True
    assert pm.answers == {"name": "acme"}


def test_build_plan_steps_serialized(tmp_path):
    m = make_manifest("mod", steps=[
        make_step("generate", "python"),
    ])
    plan = build_plan([m], resolved_answers={}, ordered_ids=["mod"])
    steps = plan.modules["mod"].steps
    assert len(steps) == 1
    assert steps[0]["id"] == "generate"
    assert steps[0]["kind"] == "python"


def test_build_plan_module_rel_root_uses_toml_path(tmp_path):
    """When _toml_path is set, module_rel_root is relative to plugin_root."""
    plugin_root = tmp_path / "skills" / "project-setup"
    plugin_root.mkdir(parents=True)
    mod_dir = plugin_root / "modules" / "core-identity"
    mod_dir.mkdir(parents=True)
    toml_path = mod_dir / "module.toml"
    toml_path.touch()

    m = make_manifest("core-identity", toml_path=str(toml_path))
    plan = build_plan(
        [m],
        resolved_answers={},
        ordered_ids=["core-identity"],
        plugin_root_path=plugin_root,
    )
    pm = plan.modules["core-identity"]
    # Should be relative, not absolute
    assert not pm.module_rel_root.startswith("/")
    assert "core-identity" in pm.module_rel_root


# --------------------------------------------------------------------------- #
# Freeze + byte-identical                                                      #
# --------------------------------------------------------------------------- #
def test_freeze_byte_identical_two_builds(tmp_path):
    """Two builds from the same inputs produce identical bytes (determinism)."""
    m = make_manifest("gitignore-generate", version="1.0.0", reconcile=True)
    answers = {"gitignore-generate": {"templates": ["macos", "linux"]}}
    ordered = ["gitignore-generate"]

    plan1 = build_plan([m], resolved_answers=answers, ordered_ids=ordered)
    plan2 = build_plan([m], resolved_answers=answers, ordered_ids=ordered)

    out1 = canonical_json(plan1.to_dict())
    out2 = canonical_json(plan2.to_dict())
    assert out1 == out2, "Two builds from same inputs must be byte-identical"


def test_freeze_writes_to_path(tmp_path):
    m = make_manifest("mod")
    plan = build_plan([m], resolved_answers={}, ordered_ids=["mod"])
    path = tmp_path / "plan.json"
    result_path = freeze(plan, path=path)
    assert result_path == path
    assert path.exists()


def test_freeze_output_is_valid_json(tmp_path):
    m = make_manifest("mod")
    plan = build_plan([m], resolved_answers={}, ordered_ids=["mod"])
    path = tmp_path / "plan.json"
    freeze(plan, path=path)
    data = json.loads(path.read_text())
    assert data["schema_version"] == SCHEMA_VERSION
    assert "order" in data
    assert "modules" in data


def test_freeze_creates_parent_dirs(tmp_path):
    m = make_manifest("mod")
    plan = build_plan([m], resolved_answers={}, ordered_ids=["mod"])
    path = tmp_path / "deep" / "nested" / "plan.json"
    freeze(plan, path=path)
    assert path.exists()


# --------------------------------------------------------------------------- #
# No absolute paths in frozen plan                                            #
# --------------------------------------------------------------------------- #
def test_no_absolute_paths_in_frozen_plan(tmp_path):
    """module_rel_root must not be an absolute path."""
    m = make_manifest("mod")
    plan = build_plan([m], resolved_answers={}, ordered_ids=["mod"])
    data = plan.to_dict()
    _assert_no_absolute_paths(data)


def test_freeze_rejects_absolute_paths(tmp_path, monkeypatch):
    """_check_no_absolute_paths triggers if someone injects an absolute path."""
    m = make_manifest("mod")
    plan = build_plan([m], resolved_answers={}, ordered_ids=["mod"])
    # Inject an absolute path into the plan data
    plan.modules["mod"].module_rel_root = "/absolute/path"
    with pytest.raises(ValueError, match="Absolute path"):
        freeze(plan, path=tmp_path / "plan.json")


def _assert_no_absolute_paths(data, path=""):
    if isinstance(data, dict):
        for k, v in data.items():
            _assert_no_absolute_paths(v, f"{path}.{k}")
    elif isinstance(data, list):
        for i, v in enumerate(data):
            _assert_no_absolute_paths(v, f"{path}[{i}]")
    elif isinstance(data, str):
        assert not data.startswith("/"), (
            f"Absolute path found at {path!r}: {data!r}"
        )


# --------------------------------------------------------------------------- #
# load_plan                                                                    #
# --------------------------------------------------------------------------- #
def test_load_plan_round_trip(tmp_path):
    """A frozen plan can be loaded back and matches the original."""
    m = make_manifest("core-identity", version="2.0.0", reconcile=True)
    answers = {"core-identity": {"name": "acme", "org": "acme-inc"}}
    plan = build_plan([m], resolved_answers=answers, ordered_ids=["core-identity"])
    path = tmp_path / "plan.json"
    freeze(plan, path=path)

    loaded = load_plan(path)
    assert loaded.schema_version == SCHEMA_VERSION
    assert loaded.mode == "init"
    assert loaded.order == ["core-identity"]
    assert "core-identity" in loaded.modules
    assert loaded.modules["core-identity"].answers == {"name": "acme", "org": "acme-inc"}


def test_load_plan_rejects_wrong_schema_version(tmp_path):
    path = tmp_path / "plan.json"
    bad = {"schema_version": 999, "mode": "init", "order": [], "modules": {}}
    path.write_text(canonical_json(bad), encoding="utf-8")
    with pytest.raises(GateFailure) as exc_info:
        load_plan(path)
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.PLAN_MALFORMED in codes


def test_load_plan_rejects_missing_keys(tmp_path):
    path = tmp_path / "plan.json"
    bad = {"schema_version": SCHEMA_VERSION}  # missing order, mode, modules
    path.write_text(canonical_json(bad), encoding="utf-8")
    with pytest.raises(GateFailure) as exc_info:
        load_plan(path)
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.PLAN_MALFORMED in codes


def test_load_plan_rejects_missing_file(tmp_path):
    path = tmp_path / "nonexistent.json"
    with pytest.raises(GateFailure) as exc_info:
        load_plan(path)
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.PLAN_MALFORMED in codes


def test_load_plan_rejects_invalid_json(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text("{ not valid json }", encoding="utf-8")
    with pytest.raises(GateFailure) as exc_info:
        load_plan(path)
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.PLAN_MALFORMED in codes


# --------------------------------------------------------------------------- #
# ExecutionPlan to_dict shape                                                  #
# --------------------------------------------------------------------------- #
def test_execution_plan_to_dict_shape():
    plan = ExecutionPlan(
        schema_version=1,
        mode="init",
        order=["a", "b"],
        modules={
            "a": PlanModule(
                id="a", version="1.0.0", reconcile=False,
                module_rel_root="modules/a",
                answers={"k": "v"},
                steps=[{"id": "run", "kind": "python"}],
            )
        },
    )
    d = plan.to_dict()
    assert d["schema_version"] == 1
    assert d["mode"] == "init"
    assert d["order"] == ["a", "b"]
    assert d["modules"]["a"]["id"] == "a"
    assert d["modules"]["a"]["answers"] == {"k": "v"}
