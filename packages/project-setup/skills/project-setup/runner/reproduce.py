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

            # Skipped only if NO path was confirmed
            entry.skipped = len(entry.confirmed_paths) == 0
            confirmations[key] = entry

    return confirmations


def _module_refreshed(module_id: str, refresh: list[str] | None) -> bool:
    """True if *module_id* is named by a ``--refresh`` token (whole-module or a key).

    Mirrors the matching in ``run_agent_phase`` (``mod_id`` or ``mod_id.<key>``) so a
    refreshed module re-arms its ``init_only`` gate (spec 004 FR-006a) — the decision
    is being re-researched, so the user must re-review it.
    """
    if not refresh:
        return False
    refresh_set = set(refresh)
    return module_id in refresh_set or any(t.startswith(f"{module_id}.") for t in refresh_set)


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
    non_interactive: bool = False,
    active_flags: frozenset[str] | None = None,
    refresh: list[str] | None = None,
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
    non_interactive:
        When True, gate steps resolve to the SAFE action (skip) without
        calling ``io.confirm`` — prevents CI deadlock.

    Returns
    -------
    list[StepOutcome]
        One entry per executed step (in execution order).
    """
    # Lazy import to avoid circular at module level
    _executor = _load_sibling("executor")
    run_gate = _executor.run_gate_step

    outcomes: list[StepOutcome] = []

    for mod_id in plan.order:
        mod_entry = plan.modules.get(mod_id)
        if mod_entry is None:
            continue

        # A declined/skipped gate blocks the python WRITE steps that FOLLOW it
        # within the same module (spec 003 FR-012/FR-013: the pin-table gate must
        # actually gate the manifest write). The block is module-scoped — a gate
        # only governs its own module's later writes, and resets per module.
        gate_blocked = False
        for step in mod_entry.steps:
            kind = step.get("kind") if isinstance(step, dict) else getattr(step, "kind", None)
            step_id = step.get("id") if isinstance(step, dict) else getattr(step, "id", None)
            key = f"{mod_id}/{step_id}"

            if kind == "python":
                if gate_blocked:
                    io.notify(
                        f"[SKIP] {mod_id}/{step_id}: a preceding gate in this module "
                        f"was not confirmed — skipping the gated write."
                    )
                    continue

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
                # init_only gate on a plain reproduce (spec 004 FR-006a): the frozen
                # decision is already consented, so the gate auto-proceeds (it does
                # NOT prompt and does NOT block the byte-identical replay). --refresh
                # on this module re-arms the gate (the decision is being re-researched).
                init_only_bypass = (
                    bool(step_dict.get("init_only"))
                    and plan.mode == "reproduce"
                    and not _module_refreshed(mod_id, refresh)
                )
                confirmed = run_gate(
                    step_dict, mod_id, io,
                    non_interactive=non_interactive,
                    active_flags=active_flags,
                    init_only_bypass=init_only_bypass,
                )
                if not confirmed:
                    # Block subsequent python writes in this module (FR-012).
                    gate_blocked = True
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
                # Phase B does NOT run agent steps. They are executed in Phase A
                # (``run_agent_phase`` below), BEFORE the plan is frozen, so their
                # decisions are baked into the frozen plan a Tier-1 python step
                # reads. Re-running the agent here would (a) re-research on a plain
                # reproduce — the FR-009 zero-network violation — and (b) be too
                # late to feed a same-run python step. So: skip.
                continue

    return outcomes


# --------------------------------------------------------------------------- #
# Phase A — agent research/decision pass (runs BEFORE the plan is frozen)       #
# --------------------------------------------------------------------------- #
_render_decision = _contracts.render_answer_block  # shared renderer (one source)


def run_agent_phase(
    manifests: list[Any],
    ordered_ids: list[str],
    resolved_answers: dict[str, dict[str, Any]],
    provenance_map: dict[str, dict[str, str]],
    io: Any,
    *,
    mode: str,
    refresh: list[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    """Run every ``kind=agent`` step BEFORE the plan is frozen (the two-phase
    plan, option B). Folds each agent decision into ``resolved_answers`` +
    ``provenance_map`` so the single subsequent ``build_plan``/``freeze`` bakes
    the pins into the frozen plan that Phase-B python steps read.

    Determinism contract (spec FR-009/FR-010, Settled Decision F/G):

    - **init**: invoke the agent for every agent step; fold its
      ``agent-steered`` decision in.
    - **reproduce (plain)**: do NOT invoke the agent and do NOT touch the network.
      The committed ``agent-steered`` answers are ALREADY present in
      ``resolved_answers`` (the 001 reproduce machinery loads committed
      answers.toml as the project layer), so the decision replays through the
      frozen plan with zero agent calls. This function is a no-op for such steps.
    - **--refresh <module|module.key>**: in reproduce mode, re-invoke the agent
      ONLY for the named modules/keys, show an old-vs-new diff, and fold the new
      decision only on confirm. A declined refresh leaves the committed value.

    The agent receives the module's CURRENT resolved answers as ``context``
    (an in-process dict — NOT the frozen plan; the frozen-plan-only-input rule of
    shared-contracts §6 binds ``module.py`` subprocesses, not the in-process
    agent hand-off). The agent never reads another module's Phase-B file writes
    (global-phasing invariant): all agent steps run before any python step.

    Returns the updated ``(resolved_answers, provenance_map)``.
    """
    _executor = _load_sibling("executor")
    run_agent = _executor.run_agent_step

    refresh_set = set(refresh or [])
    manifest_by_id = {m.id: m for m in manifests}

    # Work on copies so the caller's originals are replaced wholesale.
    answers = {k: dict(v) for k, v in resolved_answers.items()}
    prov = {k: dict(v) for k, v in provenance_map.items()}

    for mod_id in ordered_ids:
        manifest = manifest_by_id.get(mod_id)
        if manifest is None:
            continue
        for step in manifest.steps:
            kind = getattr(step, "kind", None)
            if kind != "agent":
                continue
            step_id = getattr(step, "id", "agent")
            steering = getattr(step, "steering", "") or ""

            # Decide whether to invoke the agent this run.
            module_named = mod_id in refresh_set
            key_named = any(t.startswith(f"{mod_id}.") for t in refresh_set)
            do_invoke = (mode != "reproduce") or module_named or key_named
            if not do_invoke:
                # Plain reproduce: committed decision already in `answers`. No
                # agent call, no network. (FR-009 replay.)
                continue

            step_dict = {"id": step_id, "kind": "agent", "steering": steering}
            context = {
                "module_id": mod_id,
                "step_id": step_id,
                "answers": dict(answers.get(mod_id, {})),
            }
            response = run_agent(step_dict, mod_id, io, context)
            atp = response.get("answers_to_persist", {}) if isinstance(response, dict) else {}
            if not atp:
                continue

            # --refresh diff-gate: show old-vs-new for the named keys, confirm.
            if mode == "reproduce" and (module_named or key_named):
                new_vals = {k: v.get("value") for k, v in atp.items() if isinstance(v, dict)}
                old_block = _render_decision(answers.get(mod_id, {}))
                new_block = _render_decision({**answers.get(mod_id, {}), **new_vals})
                confirmed = io.confirm({
                    "path": f"{mod_id}/{step_id}",
                    "kind": "refresh",
                    "preview": (
                        f"--refresh re-researched {mod_id}.\n"
                        f"OLD:\n{old_block}\nNEW:\n{new_block}\n"
                        f"Apply the re-researched values?"
                    ),
                })
                if not confirmed:
                    io.notify(f"[REFRESH] {mod_id}/{step_id}: declined — keeping committed values.")
                    continue

            # Fold the agent decision into the resolved maps.
            answers.setdefault(mod_id, {})
            prov.setdefault(mod_id, {})
            for key, entry in atp.items():
                if not isinstance(entry, dict):
                    continue
                answers[mod_id][key] = entry.get("value")
                source = entry.get("source")
                if source:
                    prov[mod_id][key] = str(source)

    return answers, prov
