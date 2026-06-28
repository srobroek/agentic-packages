"""Spec 004 Phase 7 — G7 cross-module conflict review (FR-017, SC-009).

Informational-only: ≥2 modules writing the same path non-trivially → one warning
naming the path + topo order; never blocks. Benign marker-append targets
(.gitignore) are excluded to avoid false-positive fatigue.

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_g7_conflicts.py
"""

from __future__ import annotations

import importlib.util
import sys
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


reproduce = _load("reproduce")
executor = _load("executor")
contracts = _load("contracts")


# --------------------------------------------------------------------------- #
# Lightweight plan + confirmation fixtures                                     #
# --------------------------------------------------------------------------- #
class _PlanModule:
    def __init__(self, mod_id, step_ids):
        self.id = mod_id
        self.module_rel_root = f"modules/{mod_id}"
        self.steps = [{"id": s, "kind": "python"} for s in step_ids]


class _Plan:
    def __init__(self, modules):
        self.order = [m.id for m in modules]
        self.modules = {m.id: m for m in modules}
        self.mode = "init"


def _entry(mod_id, step_id, diffs, skipped=False):
    outcome = executor.StepOutcome(
        ok=True, module_id=mod_id, step_id=step_id,
        result={
            "schema_version": contracts.SCHEMA_VERSION, "module_id": mod_id,
            "step_id": step_id, "status": "ok", "files_written": [],
            "diffs": diffs, "answers_to_persist": {}, "warnings": [],
            "message": "", "error": None,
        },
    )
    e = reproduce.ConfirmEntry(module_id=mod_id, step_id=step_id, inspect_outcome=outcome)
    e.skipped = skipped
    return e


def _diff(path, kind="modify"):
    return {"path": path, "kind": kind, "preview": ""}


class _IO:
    def __init__(self):
        self.log = []

    def notify(self, msg):
        self.log.append(msg)


# --------------------------------------------------------------------------- #
# Detection                                                                    #
# --------------------------------------------------------------------------- #
def test_two_modules_same_path_is_a_conflict():
    plan = _Plan([_PlanModule("lang-ts", ["write"]), _PlanModule("lang-python", ["write"])])
    confs = {
        "lang-ts/write": _entry("lang-ts", "write", [_diff("package.json")]),
        "lang-python/write": _entry("lang-python", "write", [_diff("package.json")]),
    }
    conflicts = reproduce.detect_conflicts(plan, confs)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["path"] == "package.json"
    assert c["modules"] == ["lang-ts", "lang-python"]  # topo order preserved


def test_single_writer_is_not_a_conflict():
    plan = _Plan([_PlanModule("lang-ts", ["write"]), _PlanModule("lang-python", ["write"])])
    confs = {
        "lang-ts/write": _entry("lang-ts", "write", [_diff("package.json")]),
        "lang-python/write": _entry("lang-python", "write", [_diff("pyproject.toml")]),
    }
    assert reproduce.detect_conflicts(plan, confs) == []


def test_benign_gitignore_append_excluded():
    # Both modules append to .gitignore (marker-guarded, benign) → NOT a conflict.
    plan = _Plan([_PlanModule("a", ["w"]), _PlanModule("b", ["w"])])
    confs = {
        "a/w": _entry("a", "w", [_diff(".gitignore")]),
        "b/w": _entry("b", "w", [_diff(".gitignore")]),
    }
    assert reproduce.detect_conflicts(plan, confs) == []


def test_precommit_collision_is_flagged():
    plan = _Plan([_PlanModule("lang-ts", ["w"]), _PlanModule("lang-python", ["w"])])
    confs = {
        "lang-ts/w": _entry("lang-ts", "w", [_diff(".pre-commit-config.yaml")]),
        "lang-python/w": _entry("lang-python", "w", [_diff(".pre-commit-config.yaml")]),
    }
    conflicts = reproduce.detect_conflicts(plan, confs)
    assert [c["path"] for c in conflicts] == [".pre-commit-config.yaml"]


def test_skip_diffs_and_skipped_entries_ignored():
    plan = _Plan([_PlanModule("a", ["w"]), _PlanModule("b", ["w"])])
    confs = {
        # a writes package.json for real; b only has a skip diff
        "a/w": _entry("a", "w", [_diff("package.json")]),
        "b/w": _entry("b", "w", [_diff("package.json", kind="skip")]),
    }
    assert reproduce.detect_conflicts(plan, confs) == []


# --------------------------------------------------------------------------- #
# warn_conflicts surfaces informationally, returns the records                 #
# --------------------------------------------------------------------------- #
def test_warn_conflicts_notifies_and_returns():
    plan = _Plan([_PlanModule("lang-ts", ["write"]), _PlanModule("lang-python", ["write"])])
    confs = {
        "lang-ts/write": _entry("lang-ts", "write", [_diff("package.json")]),
        "lang-python/write": _entry("lang-python", "write", [_diff("package.json")]),
    }
    io = _IO()
    conflicts = reproduce.warn_conflicts(plan, confs, io)
    assert len(conflicts) == 1
    assert any("CONFLICT" in m and "package.json" in m for m in io.log), io.log
    # informational: it returns; it does not raise or block.


def test_warn_conflicts_silent_when_none():
    plan = _Plan([_PlanModule("a", ["w"])])
    confs = {"a/w": _entry("a", "w", [_diff("only.txt")])}
    io = _IO()
    assert reproduce.warn_conflicts(plan, confs, io) == []
    assert not any("CONFLICT" in m for m in io.log)
