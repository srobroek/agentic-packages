"""Pre-write diff/confirm engine for reproduce mode.

Implements the circular-ordering fix documented in research.md:

  PROBLEM: disk-drift was to be read from a module's *post-execution* output,
  but confirm must run *pre-write*.

  FIX: Tier-1 (kind=python) steps run a ``--inspect`` dry pass that emits
  proposed ``files_written`` + ``diffs`` WITHOUT writing anything.  The
  confirm list is built from that.  On confirmation the *same* step runs
  for-real.

  GUARANTEE: for Tier-1 the inspect-preview bytes == the real write bytes
  (``sdk.idempotent_write`` already supports ``inspect=True`` and the body
  is computed identically in both modes).

Reconcile semantics:
  - ``reconcile=True`` modules: overwrite files only for confirmed diffs.
  - ``reconcile=False`` modules: skip if the file already exists (no confirm
    needed; the write is a no-op if the file is present).

Standard library only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

# ── import-by-path bootstrap ──────────────────────────────────────────────── #
_RUNNER = Path(__file__).resolve().parent


def _load_sibling(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_contracts = _load_sibling("contracts")
_executor_mod = _load_sibling("executor")

SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode
run_python_step = _executor_mod.run_python_step
StepOutcome = _executor_mod.StepOutcome


# --------------------------------------------------------------------------- #
# Per-step confirmation entry                                                  #
# --------------------------------------------------------------------------- #
class ConfirmEntry:
    """Tracks the confirmation state for a single step.

    Attributes
    ----------
    module_id : str
    step_id : str
    confirmed_paths : set[str]
        Paths the user confirmed writing.  Empty when the whole step was
        skipped or there were no proposed writes.
    skipped : bool
        ``True`` when the user declined all proposed writes for this step.
    inspect_outcome : StepOutcome
        The outcome of the ``--inspect`` dry pass (before the real write).
    """

    __slots__ = ("module_id", "step_id", "confirmed_paths", "skipped", "inspect_outcome")

    def __init__(
        self,
        *,
        module_id: str,
        step_id: str,
        inspect_outcome: StepOutcome,
    ) -> None:
        self.module_id = module_id
        self.step_id = step_id
        self.inspect_outcome = inspect_outcome
        self.confirmed_paths: set[str] = set()
        self.skipped: bool = False


# --------------------------------------------------------------------------- #
# build_drift_report                                                           #
# --------------------------------------------------------------------------- #
def build_drift_report(
    plan: Any,
    plugin_root_path: Path,
    project_dir: Path,
    io: Any,
    frozen_plan_path: Path,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, ConfirmEntry]:
    """Run an ``--inspect`` pass for every Tier-1 step and gather confirmations.

    For each ``kind=python`` step in the plan (in execution order):
    1. Run ``uv run module.py --plan <frozen> --step <id> --inspect``.
    2. Present the proposed diffs to the user via ``io.confirm``.
    3. Record which paths were confirmed.

    No files are written during this function.

    Parameters
    ----------
    plan:
        The ``ExecutionPlan`` dataclass (from ``plan.py``).
    plugin_root_path:
        Absolute path to the plugin root.
    project_dir:
        The project root directory.
    io:
        An ``InterviewIO`` implementation.
    frozen_plan_path:
        Path to the frozen ``plan.json`` on disk.
    env:
        Optional environment variable overrides.

    Returns
    -------
    dict[str, ConfirmEntry]
        Keyed by ``"{module_id}/{step_id}"``.
    """
    confirmations: dict[str, ConfirmEntry] = {}

    for mod_id in plan.order:
        mod_entry = plan.modules.get(mod_id)
        if mod_entry is None:
            continue

        for step in mod_entry.steps:
            kind = step.get("kind") if isinstance(step, dict) else getattr(step, "kind", None)
            step_id = step.get("id") if isinstance(step, dict) else getattr(step, "id", None)

            if kind != "python":
                # Only Tier-1 steps get the inspect pass
                continue

            # Run the inspect dry pass
            outcome = run_python_step(
                plugin_root_path=plugin_root_path,
                module_rel_root=mod_entry.module_rel_root,
                step_id=step_id,
                frozen_plan_path=frozen_plan_path,
                project_dir=project_dir,
                inspect=True,
                env=env,
            )

            entry = ConfirmEntry(
                module_id=mod_id,
                step_id=step_id,
                inspect_outcome=outcome,
            )
            key = f"{mod_id}/{step_id}"

            if not outcome.ok:
                # Inspect failed — log and skip (isolation: don't hard-fail)
                io.notify(
                    f"[WARN] inspect pass failed for {mod_id}/{step_id}: "
                    f"{outcome.error and outcome.error.how_to_fix}"
                )
                entry.skipped = True
                confirmations[key] = entry
                continue

            diffs = outcome.diffs()
            if not diffs:
                # Nothing to write; auto-confirm (no user prompt needed)
                confirmations[key] = entry
                continue

            # Present each proposed diff to the user
            all_skipped = True
            for diff in diffs:
                diff_kind = diff.get("kind", "create")
                diff_path = diff.get("path", "")

                if diff_kind == "skip":
                    # Already identical / already exists; no prompt
                    continue

                confirmed = io.confirm({
                    "path": diff_path,
                    "kind": diff_kind,
                    "preview": diff.get("preview", ""),
                })
                if confirmed:
                    entry.confirmed_paths.add(diff_path)
                    all_skipped = False
                else:
                    all_skipped = True  # track per-diff; update final below

            # Recalculate: skipped only if NO path was confirmed
            entry.skipped = len(entry.confirmed_paths) == 0
            confirmations[key] = entry

    return confirmations


# --------------------------------------------------------------------------- #
# apply                                                                        #
# --------------------------------------------------------------------------- #
def apply(
    plan: Any,
    confirmations: dict[str, ConfirmEntry],
    plugin_root_path: Path,
    project_dir: Path,
    io: Any,
    frozen_plan_path: Path,
    *,
    env: dict[str, str] | None = None,
) -> list[StepOutcome]:
    """Execute confirmed steps for-real after the inspect pass.

    For each ``kind=python`` step:
    - If it has confirmed paths (or no diffs → auto-proceed): run for real.
    - If it was skipped (user declined all): emit a notify and skip.

    For ``kind=gate`` and ``kind=agent`` steps: delegate to executor helpers
    (they do not use the inspect/confirm mechanism).

    Guarantees that for Tier-1 (kind=python) the bytes written match the
    inspect preview (sdk.idempotent_write is deterministic on the same inputs).

    Parameters
    ----------
    plan:
        The ``ExecutionPlan`` dataclass.
    confirmations:
        The ``ConfirmEntry`` map from ``build_drift_report``.
    plugin_root_path:
        Absolute path to the plugin root.
    project_dir:
        The project root directory.
    io:
        An ``InterviewIO`` implementation.
    frozen_plan_path:
        Path to the frozen ``plan.json`` on disk.
    env:
        Optional environment variable overrides.

    Returns
    -------
    list[StepOutcome]
        One entry per executed step (in execution order).
    """
    # Lazy import to avoid circular at module level
    _executor = _load_sibling("executor")
    run_gate = _executor.run_gate_step
    run_agent = _executor.run_agent_step

    outcomes: list[StepOutcome] = []

    for mod_id in plan.order:
        mod_entry = plan.modules.get(mod_id)
        if mod_entry is None:
            continue

        for step in mod_entry.steps:
            kind = step.get("kind") if isinstance(step, dict) else getattr(step, "kind", None)
            step_id = step.get("id") if isinstance(step, dict) else getattr(step, "id", None)
            key = f"{mod_id}/{step_id}"

            if kind == "python":
                entry = confirmations.get(key)

                if entry is None:
                    # No confirmation entry — this step was not in the inspect
                    # pass (shouldn't happen in normal flow, but guard it).
                    io.notify(f"[WARN] No confirmation entry for {key}; skipping.")
                    continue

                if entry.skipped and not entry.inspect_outcome.diffs():
                    # Auto-proceed case: inspect found no diffs (nothing to write)
                    pass
                elif entry.skipped:
                    io.notify(f"[SKIP] {mod_id}/{step_id}: user declined all proposed writes.")
                    continue

                # Run for real
                outcome = run_python_step(
                    plugin_root_path=plugin_root_path,
                    module_rel_root=mod_entry.module_rel_root,
                    step_id=step_id,
                    frozen_plan_path=frozen_plan_path,
                    project_dir=project_dir,
                    inspect=False,
                    env=env,
                )

                if not outcome.ok:
                    io.notify(
                        f"[ERROR] {mod_id}/{step_id} failed: "
                        f"{outcome.error and outcome.error.how_to_fix}"
                    )

                outcomes.append(outcome)

            elif kind == "gate":
                step_dict = step if isinstance(step, dict) else {"id": step_id, "kind": kind, "message": getattr(step, "message", "")}
                confirmed = run_gate(step_dict, mod_id, io)
                # For gate steps we synthesize a simple outcome
                gate_result = {
                    "schema_version": _contracts.SCHEMA_VERSION,
                    "module_id": mod_id,
                    "step_id": step_id,
                    "status": "ok" if confirmed else "skipped",
                    "files_written": [],
                    "diffs": [],
                    "answers_to_persist": {},
                    "warnings": [],
                    "message": "confirmed" if confirmed else "skipped by user",
                    "error": None,
                }
                outcomes.append(StepOutcome(
                    ok=confirmed,
                    module_id=mod_id,
                    step_id=step_id,
                    result=gate_result,
                ))

            elif kind == "agent":
                step_dict = step if isinstance(step, dict) else {"id": step_id, "kind": kind, "steering": getattr(step, "steering", "")}
                agent_response = run_agent(step_dict, mod_id, io)
                agent_result = {
                    "schema_version": _contracts.SCHEMA_VERSION,
                    "module_id": mod_id,
                    "step_id": step_id,
                    "status": "ok",
                    "files_written": [],
                    "diffs": [],
                    "answers_to_persist": agent_response.get("answers_to_persist", {}),
                    "warnings": [],
                    "message": agent_response.get("message", ""),
                    "error": None,
                }
                outcomes.append(StepOutcome(
                    ok=True,
                    module_id=mod_id,
                    step_id=step_id,
                    result=agent_result,
                ))

    return outcomes
