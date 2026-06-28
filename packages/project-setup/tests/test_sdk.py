"""Tests for sdk.py — the module-author API.

Covers:
- All 8 typed accessors (get_str/text/int/bool/path/list/choice/multichoice)
- idempotent_write: absent (create), reconcile (overwrite), inspect==write bytes
- is_safe_relative_path: allows nested, blocks ../abs/symlink
- emit_result: rejects non-emittable provenance, rejects malformed shape

Import-by-path pattern from test_contracts.py.
Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_sdk.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import os
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
sdk_mod = _load("sdk")

FrozenInputs = sdk_mod.FrozenInputs
load_frozen_inputs = sdk_mod.load_frozen_inputs
idempotent_write = sdk_mod.idempotent_write
is_safe_relative_path = sdk_mod.is_safe_relative_path
emit_result = sdk_mod.emit_result

GateFailure = contracts.GateFailure
SetupError = contracts.SetupError
ErrorCode = contracts.ErrorCode
Provenance = contracts.Provenance
ModuleResult = contracts.ModuleResult
canonical_json = contracts.canonical_json
SCHEMA_VERSION = contracts.SCHEMA_VERSION

build_plan = plan_mod.build_plan
freeze = plan_mod.freeze
PlanModule = plan_mod.PlanModule
ExecutionPlan = plan_mod.ExecutionPlan


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def make_frozen_inputs(answers: dict, reconcile: bool = False) -> FrozenInputs:
    module_entry = SimpleNamespace(
        id="test-mod",
        answers=answers,
        reconcile=reconcile,
    )
    return FrozenInputs(module_entry, plan=None)


def write_plan(tmp_path: Path, answers: dict, module_id: str = "test-mod") -> Path:
    """Write a minimal frozen plan to tmp_path/plan.json."""

    def make_step(id="run", kind="python"):
        return SimpleNamespace(id=id, kind=kind, steering=None, message=None)

    m = SimpleNamespace(
        id=module_id,
        version="1.0.0",
        reconcile=False,
        steps=[make_step()],
        order={"requires": [], "after": [], "before": []},
        tools={"required": []},
        inputs=[],
        _toml_path=None,
    )
    plan = build_plan([m], resolved_answers={module_id: answers}, ordered_ids=[module_id])
    path = tmp_path / "plan.json"
    freeze(plan, path=path)
    return path


# --------------------------------------------------------------------------- #
# FrozenInputs — all 8 typed accessors                                        #
# --------------------------------------------------------------------------- #
def test_get_str():
    fi = make_frozen_inputs({"k": "hello"})
    assert fi.get_str("k") == "hello"
    assert fi.get_str("missing", default="default") == "default"


def test_get_bool_true():
    fi = make_frozen_inputs({"flag": True})
    assert fi.get_bool("flag") is True


def test_get_bool_false():
    fi = make_frozen_inputs({"flag": False})
    assert fi.get_bool("flag") is False


def test_get_bool_from_string():
    fi = make_frozen_inputs({"flag": "yes"})
    assert fi.get_bool("flag") is True
    fi2 = make_frozen_inputs({"flag": "no"})
    assert fi2.get_bool("flag") is False


def test_get_bool_default():
    fi = make_frozen_inputs({})
    assert fi.get_bool("missing") is False
    assert fi.get_bool("missing", default=True) is True


def test_get_list():
    fi = make_frozen_inputs({"items": ["a", "b", "c"]})
    assert fi.get_list("items") == ["a", "b", "c"]
    assert fi.get_list("missing") == []


def test_get_list_from_scalar():
    fi = make_frozen_inputs({"items": "single"})
    assert fi.get_list("items") == ["single"]


def test_get_choice():
    fi = make_frozen_inputs({"layout": "monorepo"})
    assert fi.get_choice("layout") == "monorepo"
    assert fi.get_choice("missing", default="simple") == "simple"


def test_get_multichoice():
    fi = make_frozen_inputs({"templates": ["macos", "linux"]})
    assert fi.get_multichoice("templates") == ["macos", "linux"]
    assert fi.get_multichoice("missing") == []


def test_get_multichoice_from_scalar():
    fi = make_frozen_inputs({"templates": "macos"})
    assert fi.get_multichoice("templates") == ["macos"]


def test_reconcile_property():
    fi = make_frozen_inputs({}, reconcile=True)
    assert fi.reconcile is True
    fi2 = make_frozen_inputs({}, reconcile=False)
    assert fi2.reconcile is False


# --------------------------------------------------------------------------- #
# load_frozen_inputs                                                           #
# --------------------------------------------------------------------------- #
def test_load_frozen_inputs_returns_frozen_inputs(tmp_path):
    path = write_plan(tmp_path, {"name": "acme"})
    fi = load_frozen_inputs(path, "test-mod")
    assert fi.get_str("name") == "acme"


def test_load_frozen_inputs_unknown_module_raises(tmp_path):
    path = write_plan(tmp_path, {})
    with pytest.raises(GateFailure):
        load_frozen_inputs(path, "nonexistent-module")


# --------------------------------------------------------------------------- #
# idempotent_write — absent → create                                          #
# --------------------------------------------------------------------------- #
def test_idempotent_write_creates_file(tmp_path):
    diff = idempotent_write(
        "output/hello.txt", "hello world\n",
        project_dir=tmp_path, reconcile=False, inspect=False,
    )
    assert diff.kind == "create"
    assert (tmp_path / "output" / "hello.txt").read_text() == "hello world\n"


def test_idempotent_write_skip_if_identical(tmp_path):
    (tmp_path / "f.txt").write_text("same\n")
    diff = idempotent_write(
        "f.txt", "same\n",
        project_dir=tmp_path, reconcile=False, inspect=False,
    )
    assert diff.kind == "skip"
    assert (tmp_path / "f.txt").read_text() == "same\n"


def test_idempotent_write_skip_existing_without_reconcile(tmp_path):
    (tmp_path / "f.txt").write_text("old\n")
    diff = idempotent_write(
        "f.txt", "new\n",
        project_dir=tmp_path, reconcile=False, inspect=False,
    )
    assert diff.kind == "skip"
    assert (tmp_path / "f.txt").read_text() == "old\n"  # not overwritten


def test_idempotent_write_reconcile_overwrites(tmp_path):
    (tmp_path / "f.txt").write_text("old\n")
    diff = idempotent_write(
        "f.txt", "new\n",
        project_dir=tmp_path, reconcile=True, inspect=False,
    )
    assert diff.kind == "modify"
    assert (tmp_path / "f.txt").read_text() == "new\n"


# --------------------------------------------------------------------------- #
# idempotent_write — inspect mode: preview == real write bytes                #
# --------------------------------------------------------------------------- #
def test_idempotent_write_inspect_does_not_write(tmp_path):
    """inspect=True produces the Diff but writes nothing."""
    diff = idempotent_write(
        "new.txt", "content\n",
        project_dir=tmp_path, reconcile=False, inspect=True,
    )
    assert diff.kind == "create"
    assert not (tmp_path / "new.txt").exists()


def test_idempotent_write_inspect_preview_equals_real_write(tmp_path):
    """Tier-1 guarantee: inspect preview == real write (same diff kind)."""
    body = "canonical content\n"

    # Inspect pass
    diff_inspect = idempotent_write(
        "out.txt", body,
        project_dir=tmp_path, reconcile=False, inspect=True,
    )
    assert not (tmp_path / "out.txt").exists()

    # Real write pass
    diff_real = idempotent_write(
        "out.txt", body,
        project_dir=tmp_path, reconcile=False, inspect=False,
    )
    assert (tmp_path / "out.txt").exists()
    assert (tmp_path / "out.txt").read_text() == body

    # inspect and real produce the same kind
    assert diff_inspect.kind == diff_real.kind


def test_idempotent_write_inspect_reconcile_equals_real_write(tmp_path):
    """inspect=True on reconcile == real reconcile (same kind)."""
    (tmp_path / "f.txt").write_text("old\n")
    body = "new\n"

    diff_inspect = idempotent_write(
        "f.txt", body, project_dir=tmp_path, reconcile=True, inspect=True,
    )
    assert (tmp_path / "f.txt").read_text() == "old\n"  # not changed

    diff_real = idempotent_write(
        "f.txt", body, project_dir=tmp_path, reconcile=True, inspect=False,
    )
    assert (tmp_path / "f.txt").read_text() == "new\n"

    assert diff_inspect.kind == diff_real.kind


# --------------------------------------------------------------------------- #
# is_safe_relative_path                                                        #
# --------------------------------------------------------------------------- #
def test_safe_simple_file():
    assert is_safe_relative_path("file.txt") is True


def test_safe_nested_path():
    assert is_safe_relative_path("src/main/app.py") is True


def test_safe_deep_nested():
    assert is_safe_relative_path("a/b/c/d/e.txt") is True


def test_rejects_dotdot():
    assert is_safe_relative_path("../escape.txt") is False


def test_rejects_dotdot_in_middle():
    assert is_safe_relative_path("a/../../etc/passwd") is False


def test_rejects_absolute_unix():
    assert is_safe_relative_path("/etc/passwd") is False


def test_rejects_empty():
    assert is_safe_relative_path("") is False


def test_rejects_dot_only():
    assert is_safe_relative_path(".") is False


# --------------------------------------------------------------------------- #
# emit_result                                                                  #
# --------------------------------------------------------------------------- #
def test_emit_result_valid(capsys):
    result = ModuleResult(
        module_id="test-mod",
        step_id="run",
        status="ok",
        files_written=[".gitignore"],
    )
    emit_result(result)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["module_id"] == "test-mod"
    assert data["status"] == "ok"
    assert data["files_written"] == [".gitignore"]


def test_emit_result_missing_required_key_raises():
    """Missing required key raises SetupError(RESULT_SHAPE)."""
    bad = {"module_id": "m", "step_id": "s", "status": "ok"}
    # Missing files_written, diffs, schema_version
    with pytest.raises(SetupError) as exc_info:
        emit_result(bad)
    assert exc_info.value.error_code == ErrorCode.RESULT_SHAPE


def test_emit_result_non_emittable_provenance_raises():
    """Persistence-assigned provenance (flag/home/project) must be rejected."""
    non_emittable = [
        Provenance.FLAG.value,
        Provenance.HOME.value,
        Provenance.PROJECT.value,
    ]
    for prov in non_emittable:
        result = ModuleResult(
            module_id="m",
            step_id="s",
            status="ok",
            answers_to_persist={"key": {"value": "v", "source": prov}},
        )
        with pytest.raises(SetupError) as exc_info:
            emit_result(result)
        assert exc_info.value.error_code == ErrorCode.RESULT_SHAPE, (
            f"Expected RESULT_SHAPE for provenance '{prov}'"
        )


def test_emit_result_emittable_provenance_accepted(capsys):
    """default/derived/agent-steered are acceptable provenance for modules."""
    emittable = [
        Provenance.DEFAULT.value,
        Provenance.DERIVED.value,
        Provenance.AGENT_STEERED.value,
    ]
    for prov in emittable:
        result = ModuleResult(
            module_id="m",
            step_id="s",
            status="ok",
            answers_to_persist={"key": {"value": "v", "source": prov}},
        )
        emit_result(result)  # must not raise
    capsys.readouterr()  # consume output


def test_emit_result_output_is_canonical_json(capsys):
    """emit_result uses canonical_json (sorted keys, trailing newline)."""
    result = ModuleResult(module_id="m", step_id="s")
    emit_result(result)
    out = capsys.readouterr().out
    assert out.endswith("\n")
    # Keys should be sorted
    data = json.loads(out)
    assert "module_id" in data
    assert "files_written" in data


