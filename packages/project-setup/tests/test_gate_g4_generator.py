"""Spec 004 Phase 5 — G4 external-generator gate + lang-ts scaffold split (FR-013, SC-006).

The scaffolder is split out of `write` into a separate, soft-gated `scaffold` step,
ordered AFTER the deterministic write so a declined G4 gate skips ONLY the generator
(Subtlety 1). Covered:
- the lang-ts manifest declares the G4 gate (soft, no-external-generators) between
  `write` and `scaffold`, in the right order.
- runner-level: a declined `run-generator` gate blocks ONLY `scaffold`, not `write`
  (reuses the module-scoped gate_blocked latch).
- CI: --no-external-generators flips the soft gate to safe-skip; default proceeds.

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_gate_g4_generator.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"
_MODULES = _RUNNER.parent / "modules"
_PLUGIN_ROOT = _RUNNER.parent


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


manifest = _load("manifest")
executor = _load("executor")
run_gate_step = executor.run_gate_step


# --------------------------------------------------------------------------- #
# Manifest: the G4 gate sits between write and scaffold, soft + skip_flag       #
# --------------------------------------------------------------------------- #
def test_lang_ts_step_order_and_g4_gate():
    m = manifest.parse_manifest(_MODULES / "lang-ts" / "module.toml")
    assert not m.errors, [e.to_dict() for e in m.errors]
    order = [(s.id, s.kind) for s in m.steps]
    # Full step order as of spec 013 Phase 1 (FR-019).
    assert order == [
        ("resolve", "agent"),
        ("pins", "gate"),
        ("write", "python"),
        ("run-generator", "gate"),
        ("scaffold", "python"),
        ("ui-kit-init", "gate"),
        ("ui-kit-scaffold", "python"),
    ], order
    g4 = [s for s in m.steps if s.id == "run-generator"][0]
    assert g4.hardness == "soft"
    assert g4.skip_flag == "no-external-generators"
    # write precedes the generator gate → a declined gate cannot un-write the pins.
    assert order.index(("write", "python")) < order.index(("run-generator", "gate"))


def test_g4_ci_proceeds_by_default_skips_with_flag():
    g4 = {"id": "run-generator", "kind": "gate", "hardness": "soft",
          "skip_flag": "no-external-generators", "message": "m"}

    class _IO:
        def notify(self, msg): pass
        def confirm(self, item): raise AssertionError("must not prompt in CI")

    # soft default: proceed in CI
    assert run_gate_step(g4, "lang-ts", _IO(), non_interactive=True) is True
    # --no-external-generators → safe-skip
    assert run_gate_step(
        g4, "lang-ts", _IO(), non_interactive=True,
        active_flags=frozenset({"no-external-generators"}),
    ) is False


# --------------------------------------------------------------------------- #
# Runner-level: a declined G4 gate blocks ONLY scaffold, not write              #
# --------------------------------------------------------------------------- #
class _PlanModule:
    def __init__(self, steps):
        self.id = "lang-ts"
        self.module_rel_root = "modules/lang-ts"
        self.steps = steps


class _Plan:
    def __init__(self, steps):
        self.order = ["lang-ts"]
        self.modules = {"lang-ts": _PlanModule(steps)}
        self.mode = "init"


class _SpyIO:
    def __init__(self, gate_result: bool):
        self.gate_result = gate_result
        self.log = []

    def notify(self, msg):
        self.log.append(("notify", msg))

    def confirm(self, item):
        self.log.append(("confirm", item.get("path")))
        return self.gate_result


def _run_apply(monkeypatch, gate_confirmed: bool):
    """Drive reproduce.apply over write → run-generator(gate) → scaffold, recording
    which python steps actually execute. run_python_step is stubbed so no subprocess
    runs; we only care about which steps are dispatched vs gate-blocked.
    """
    reproduce = _load("reproduce")
    executed: list[str] = []

    def _fake_run_python_step(*, step_id, **kwargs):
        executed.append(step_id)
        # minimal successful outcome
        return executor.StepOutcome(
            ok=True, module_id="lang-ts", step_id=step_id,
            result={"schema_version": _load("contracts").SCHEMA_VERSION,
                    "module_id": "lang-ts", "step_id": step_id, "status": "ok",
                    "files_written": [], "diffs": [], "answers_to_persist": {},
                    "warnings": [], "message": "", "error": None},
        )

    monkeypatch.setattr(reproduce, "run_python_step", _fake_run_python_step)

    steps = [
        {"id": "write", "kind": "python"},
        {"id": "run-generator", "kind": "gate", "hardness": "soft",
         "skip_flag": "no-external-generators", "message": "run gen?"},
        {"id": "scaffold", "kind": "python"},
    ]
    plan = _Plan(steps)
    # Pre-build confirmations for the two python steps (inspect pass result):
    # both have "no diffs" so they auto-proceed when not gate-blocked.
    confirmations = {}
    for sid in ("write", "scaffold"):
        entry = reproduce.ConfirmEntry(
            module_id="lang-ts", step_id=sid,
            inspect_outcome=executor.StepOutcome(
                ok=True, module_id="lang-ts", step_id=sid,
                result={"schema_version": _load("contracts").SCHEMA_VERSION,
                        "module_id": "lang-ts", "step_id": sid, "status": "ok",
                        "files_written": [], "diffs": [], "answers_to_persist": {},
                        "warnings": [], "message": "", "error": None},
            ),
        )
        confirmations[f"lang-ts/{sid}"] = entry

    io = _SpyIO(gate_result=gate_confirmed)
    reproduce.apply(
        plan=plan,
        confirmations=confirmations,
        plugin_root_path=Path("/tmp"),
        project_dir=Path("/tmp/proj"),
        io=io,
        frozen_plan_path=Path("/tmp/plan.json"),
        non_interactive=False,
    )
    return executed


def test_declined_g4_blocks_only_scaffold(monkeypatch):
    # Decline the run-generator gate → write ran, scaffold blocked.
    executed = _run_apply(monkeypatch, gate_confirmed=False)
    assert "write" in executed, "deterministic write must run before the gate"
    assert "scaffold" not in executed, "declined G4 must block the scaffold step"


def test_accepted_g4_runs_scaffold(monkeypatch):
    executed = _run_apply(monkeypatch, gate_confirmed=True)
    assert "write" in executed and "scaffold" in executed


# --------------------------------------------------------------------------- #
# Subprocess: the scaffold step runs the generator + re-merges pins (SC-006)   #
# --------------------------------------------------------------------------- #
def _stub_pkg_managers(tmp: Path) -> Path:
    stub_dir = tmp / "stubs"
    stub_dir.mkdir(exist_ok=True)
    for name in ("bun", "bunx", "pnpm"):
        stub = stub_dir / name
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    return stub_dir


def test_scaffold_step_runs_and_remerges_pins(tmp_path):
    """The scaffold step (plain framework) runs the generator stub then re-merges
    the frozen pins into package.json — proving the pin re-merge after the generator
    (which may have clobbered the file). Scaffolder is stubbed (offline)."""
    project = tmp_path / "app"
    project.mkdir()
    stub_dir = _stub_pkg_managers(tmp_path)
    plan = {
        "schema_version": 1, "mode": "init", "order": ["lang-ts"],
        "modules": {"lang-ts": {
            "id": "lang-ts", "version": "1.0.0", "reconcile": True,
            "module_rel_root": "modules/lang-ts",
            "answers": {"package_manager": "bun", "framework": "plain",
                        "pinned_deps": ["vue@3.5.13"], "dev_deps": [],
                        "package_manager_pin": "bun@1.1.38"},
            "steps": [{"id": "scaffold", "kind": "python"}],
        }},
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    module_py = _PLUGIN_ROOT / "modules" / "lang-ts" / "module.py"
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project),
           "PATH": f"{stub_dir}:{os.environ.get('PATH', '')}"}
    proc = subprocess.run(
        ["uv", "run", str(module_py), "--plan", str(plan_path), "--step", "scaffold"],
        capture_output=True, text=True, env=env, cwd=str(project),
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    # package.json carries the re-merged pin
    pkg = project / "package.json"
    assert pkg.exists(), f"package.json not written; files={result['files_written']}"
    data = json.loads(pkg.read_text())
    assert data.get("dependencies", {}).get("vue") == "3.5.13"
    assert data.get("packageManager") == "bun@1.1.38"
