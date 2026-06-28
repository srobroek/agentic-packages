"""Spec 004 Phase 8 — G5 destructive-overwrite gate (FR-015/016, SC-008).

In reproduce mode a kind="modify" diff means the on-disk content diverges from the
deterministic re-render (the file has local edits a write would clobber). G5:
- TTY: escalate the confirm to a hard OVERWRITE gate (kind="overwrite").
- --non-interactive: SAFE-skip the file (preserve local edits), continue (FR-016).
- create / append-if-absent (kind="create") and clean re-renders (kind="skip") are
  unaffected.

These exercise build_drift_report directly with a synthetic module whose inspect
pass yields a controlled diff, so no real subprocess is needed.

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_g5_overwrite.py
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
# Fixtures: a plan with one python step whose inspect yields a chosen diff      #
# --------------------------------------------------------------------------- #
class _PlanModule:
    def __init__(self, diff_kind):
        self.id = "m"
        self.module_rel_root = "modules/m"
        self.steps = [{"id": "write", "kind": "python"}]
        self._diff_kind = diff_kind


class _Plan:
    def __init__(self, diff_kind, mode="reproduce"):
        self.order = ["m"]
        self.modules = {"m": _PlanModule(diff_kind)}
        self.mode = mode


class _RecordIO:
    def __init__(self, confirm_result=True):
        self.confirm_result = confirm_result
        self.confirms = []
        self.log = []

    def confirm(self, item):
        self.confirms.append(item)
        return self.confirm_result

    def notify(self, msg):
        self.log.append(msg)


def _patch_inspect(monkeypatch, diff_kind):
    """Stub run_python_step's inspect to emit one diff of the chosen kind."""
    def _fake(*, step_id, inspect, **kwargs):
        diff = {"path": "config.yaml", "kind": diff_kind, "preview": "new content"}
        return executor.StepOutcome(
            ok=True, module_id="m", step_id=step_id,
            result={"schema_version": contracts.SCHEMA_VERSION, "module_id": "m",
                    "step_id": step_id, "status": "ok", "files_written": [],
                    "diffs": [diff], "answers_to_persist": {}, "warnings": [],
                    "message": "", "error": None},
        )
    monkeypatch.setattr(reproduce, "run_python_step", _fake)


def _drift(monkeypatch, diff_kind, *, non_interactive, confirm_result=True):
    _patch_inspect(monkeypatch, diff_kind)
    io = _RecordIO(confirm_result=confirm_result)
    confs = reproduce.build_drift_report(
        plan=_Plan(diff_kind),
        plugin_root_path=Path("/tmp"),
        project_dir=Path("/tmp/proj"),
        io=io,
        frozen_plan_path=Path("/tmp/plan.json"),
        interactive_per_diff=True,   # reproduce mode
        non_interactive=non_interactive,
    )
    return confs["m/write"], io


# --------------------------------------------------------------------------- #
# CI: a destructive modify SAFE-skips (preserves the file); create proceeds    #
# --------------------------------------------------------------------------- #
def test_ci_modify_is_safe_skipped(monkeypatch):
    entry, io = _drift(monkeypatch, "modify", non_interactive=True)
    # the file was NOT confirmed for writing (safe-skip), and the entry is skipped
    assert "config.yaml" not in entry.confirmed_paths
    assert entry.skipped
    assert any("OVERWRITE" in m and "SAFE-skip" in m for m in io.log), io.log
    # CI must not prompt
    assert io.confirms == []


def test_ci_create_proceeds(monkeypatch):
    # a create is not destructive — CI (no per-file confirm needed) proceeds.
    entry, io = _drift(monkeypatch, "create", non_interactive=True)
    assert "config.yaml" in entry.confirmed_paths
    assert not entry.skipped


# --------------------------------------------------------------------------- #
# TTY: a destructive modify escalates to the hard overwrite gate               #
# --------------------------------------------------------------------------- #
def test_tty_modify_escalates_to_overwrite_gate(monkeypatch):
    entry, io = _drift(monkeypatch, "modify", non_interactive=False, confirm_result=True)
    # the confirm was presented as an OVERWRITE gate
    assert len(io.confirms) == 1
    item = io.confirms[0]
    assert item["kind"] == "overwrite"
    assert "OVERWRITE" in item["preview"] and "local changes" in item["preview"]
    # confirmed → the path is accepted for writing
    assert "config.yaml" in entry.confirmed_paths


def test_tty_modify_declined_preserves_file(monkeypatch):
    entry, io = _drift(monkeypatch, "modify", non_interactive=False, confirm_result=False)
    assert "config.yaml" not in entry.confirmed_paths
    assert entry.skipped


def test_tty_create_is_plain_confirm_not_overwrite(monkeypatch):
    entry, io = _drift(monkeypatch, "create", non_interactive=False, confirm_result=True)
    assert len(io.confirms) == 1
    assert io.confirms[0]["kind"] == "create"  # not escalated
    assert "config.yaml" in entry.confirmed_paths
