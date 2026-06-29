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

from pathlib import Path
from typing import Any

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts
import executor as _executor_mod

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
    interactive_per_diff: bool = True,
    non_interactive: bool = False,
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

                if interactive_per_diff:
                    # Reproduce mode: per-file write-confirm loop (the 001 behavior).
                    # G5 (spec 004 FR-015/016): a kind="modify" diff means the on-disk
                    # content DIVERGES from the deterministic re-render — i.e. the file
                    # has local edits this write would clobber (destructive overwrite).
                    # create / append-if-absent are NOT destructive (kind="create").
                    is_destructive = diff_kind == "modify"
                    if is_destructive and non_interactive:
                        # CI never silently destroys local work: SAFE-skip this file,
                        # preserve the local edits, record it skipped, continue (FR-016).
                        io.notify(
                            f"[OVERWRITE] {diff_path} has local changes that would be "
                            f"lost — non-interactive SAFE-skip (file preserved). Re-run "
                            f"interactively to overwrite."
                        )
                        confirmed = False
                    elif is_destructive:
                        # Escalated hard overwrite gate (TTY): name the data-loss hazard.
                        confirmed = io.confirm({
                            "path": diff_path,
                            "kind": "overwrite",
                            "preview": (
                                f"OVERWRITE — {diff_path} has local changes that will be "
                                f"lost.\n{diff.get('preview', '')}"
                            ),
                        })
                    else:
                        confirmed = io.confirm({
                            "path": diff_path,
                            "kind": diff_kind,
                            "preview": diff.get("preview", ""),
                        })
                else:
                    # Init mode: the single whole-plan preview (G1) is the one
                    # aggregate confirm; per-file prompts here would be the
                    # gates-analysis anti-pattern #1 (per-file init confirm). Auto-
                    # confirm every proposed write — G1 already governed the batch.
                    confirmed = True
                if confirmed:
                    entry.confirmed_paths.add(diff_path)

            # Skipped only if NO path was confirmed
            entry.skipped = len(entry.confirmed_paths) == 0
            confirmations[key] = entry

    return confirmations


# --------------------------------------------------------------------------- #
# G1 — whole-plan preview (spec 004 FR-007/008/009)                            #
# --------------------------------------------------------------------------- #
def _side_effect_classes(step: dict[str, Any], inspect_entry: "ConfirmEntry | None") -> list[str]:
    """Classify a step's side effects for the G1 preview line (FR-008).

    Derived from the step kind + its gate enrichment + the inspect outcome — NEVER
    a hand-maintained per-module table (the gates-analysis G1 failure mode, OQ-3):

      - allow-install gate         → ``[installs N pkgs]`` / ``[network]``
      - allow-public-repo gate     → ``[creates remote]`` / ``[network]``
      - external-generator gate    → ``[runs external generator]`` / ``[network]``
      - kind=python with diffs     → ``[writes file]``
      - kind=agent                 → ``[agent decision]``
    """
    kind = step.get("kind")
    classes: list[str] = []
    if kind == "gate":
        allow = step.get("allow_flag") or ""
        skip = step.get("skip_flag") or ""
        if allow == "allow-install":
            classes += ["[installs N pkgs]", "[network]"]
        elif allow == "allow-public-repo":
            classes += ["[creates remote]", "[network]"]
        elif skip == "no-external-generators":
            classes += ["[runs external generator]", "[network]"]
        elif allow == "allow-stack-write":
            classes += ["[writes pinned manifest]"]
    elif kind == "agent":
        classes.append("[agent decision]")
    elif kind == "python":
        if inspect_entry is not None and not inspect_entry.skipped:
            real = [d for d in inspect_entry.inspect_outcome.diffs()
                    if d.get("kind") != "skip"]
            if real:
                classes.append("[writes file]")
    return classes


def render_plan_preview(plan: Any, confirmations: dict[str, ConfirmEntry]) -> str:
    """Render the frozen *plan* as an ordered, per-module checklist (G1, FR-007/008).

    Reuses the inspect outcomes already gathered in *confirmations* (the modules'
    own ``would …`` preview strings) — it does NOT generate a parallel literal.
    """
    lines: list[str] = ["", "── Plan preview — the following will run ──"]
    for mod_id in plan.order:
        mod_entry = plan.modules.get(mod_id)
        if mod_entry is None:
            continue
        lines.append(f"\n▸ {mod_id}")
        for step in mod_entry.steps:
            kind = step.get("kind") if isinstance(step, dict) else getattr(step, "kind", None)
            step_id = step.get("id") if isinstance(step, dict) else getattr(step, "id", None)
            entry = confirmations.get(f"{mod_id}/{step_id}")
            classes = " ".join(_side_effect_classes(step, entry))
            # Reuse the module's own would-… preview for python steps; gates show
            # their message head; agents are named.
            detail = ""
            if kind == "python" and entry is not None and not entry.skipped:
                previews = [d.get("preview", "") for d in entry.inspect_outcome.diffs()
                            if d.get("kind") != "skip" and d.get("preview")]
                detail = previews[0] if previews else ""
            elif kind == "gate":
                detail = str(step.get("message", "")).splitlines()[0] if step.get("message") else ""
            tail = f" — {detail}" if detail else ""
            suffix = f"  {classes}" if classes else ""
            lines.append(f"    • {step_id} ({kind}){tail}{suffix}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# G7 — cross-module conflict review (spec 004 FR-017)                          #
# --------------------------------------------------------------------------- #
# Paths where a marker-guarded append-if-absent collision is benign (every writer
# only appends behind a marker, so last-writer-wins is harmless) — excluded to
# avoid the gates-analysis G7 false-positive ("both append to gitignore"). Other
# shared files (package.json, .pre-commit-config.yaml) ARE surfaced: gates-analysis
# explicitly wants those collisions flagged. The Diff shape does not carry an
# idempotency hint (OQ-3), so this exclusion is by-path, not by-write-kind.
_G7_BENIGN_APPEND_PATHS = frozenset({".gitignore"})


def detect_conflicts(plan: Any, confirmations: dict[str, ConfirmEntry]) -> list[dict[str, Any]]:
    """Find shared-file write collisions across enabled modules (G7, informational).

    Returns one record per contended path: ``{path, modules: [ids in topo order]}``
    for paths that ≥2 DISTINCT modules write (create/modify, not skip) in the inspect
    pass, excluding benign marker-append targets. Detection only — the caller warns
    and proceeds (deterministic topo order); it never blocks. A destructive overwrite
    is G5's concern, not G7's.
    """
    # path → ordered list of module ids that write it (topo order preserved via plan.order)
    writers: dict[str, list[str]] = {}
    for mod_id in plan.order:
        mod_entry = plan.modules.get(mod_id)
        if mod_entry is None:
            continue
        seen_here: set[str] = set()  # one vote per module per path
        for step in mod_entry.steps:
            step_id = step.get("id") if isinstance(step, dict) else getattr(step, "id", None)
            entry = confirmations.get(f"{mod_id}/{step_id}")
            if entry is None or entry.skipped:
                continue
            for diff in entry.inspect_outcome.diffs():
                if diff.get("kind") == "skip":
                    continue
                path = diff.get("path", "")
                if not path or path in _G7_BENIGN_APPEND_PATHS:
                    continue
                if path not in seen_here:
                    seen_here.add(path)
                    writers.setdefault(path, []).append(mod_id)
    return [
        {"path": path, "modules": mods}
        for path, mods in writers.items()
        if len(mods) >= 2
    ]


def warn_conflicts(plan: Any, confirmations: dict[str, ConfirmEntry], io: Any) -> list[dict[str, Any]]:
    """Surface G7 collisions informationally (warn + proceed; never blocks)."""
    conflicts = detect_conflicts(plan, confirmations)
    for c in conflicts:
        order = " → ".join(c["modules"])
        io.notify(
            f"[CONFLICT] {c['path']} is written by multiple modules ({order}). "
            f"Resolved in deterministic topo order (last writer wins). Review if the "
            f"merge is not what you intend; reorder or disable a module to change it."
        )
    return conflicts


def whole_plan_gate(
    plan: Any,
    confirmations: dict[str, ConfirmEntry],
    io: Any,
    *,
    non_interactive: bool = False,
) -> bool:
    """Show the G1 whole-plan preview and capture ONE aggregate confirm (FR-009).

    G1 is soft/informational: in a TTY it asks a single "proceed?" (decline = abort,
    nothing written); in ``--non-interactive`` it prints the plan and proceeds (it
    never blocks CI — the consequential sub-actions G2/G3/G4/G6 carry their own hard
    gate policy). It does NOT auto-confirm those hard sub-gates (Subtlety 2).
    """
    io.notify(render_plan_preview(plan, confirmations))
    if non_interactive:
        io.notify("[PLAN] non-interactive — proceeding (per-action gates still apply).")
        return True
    return io.confirm({
        "path": "<whole-plan>",
        "kind": "gate",
        "preview": "Proceed with the plan above?",
        "default_yes": True,
    })


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
    _executor = _executor_mod
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
    _executor = _executor_mod
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
            # spec 012 FR-009: reproduce_only steps invert the normal rule —
            # they fire on plain reproduce and are skipped at init unless
            # --refresh names them (Q2 override takes precedence over both flags).
            repro_only = getattr(step, "reproduce_only", False)
            module_named = mod_id in refresh_set
            key_named = any(t.startswith(f"{mod_id}.") for t in refresh_set)
            if repro_only:
                # reproduce_only: INVOKE on plain reproduce; SKIP at init unless
                # --refresh named it explicitly (Q2 override).
                do_invoke = (mode == "reproduce") or module_named or key_named
            else:
                do_invoke = (mode != "reproduce") or module_named or key_named
            if not do_invoke:
                # Plain reproduce: committed decision already in `answers`. No
                # agent call, no network. (FR-009 replay.)
                continue

            # Answer-driven IO (FileAnswersIO): all answers are pre-frozen by the
            # agent up front. Skip the live agent call entirely — the agent-steered
            # answers are already in resolved_answers (or will be supplied via
            # io.ask). (FR-004 / spec 019 SC-003)
            if getattr(io, "is_answer_driven", False):
                continue

            step_dict = {"id": step_id, "kind": "agent", "steering": steering}
            context = {
                "module_id": mod_id,
                "step_id": step_id,
                "answers": dict(answers.get(mod_id, {})),
                # spec 007: a read-only snapshot of ALL answers resolved so far (every
                # module folded in topo order before this one). Lets a cross-cutting
                # agent (e.g. ci-github-actions, ordered `after` the lang-* overlays)
                # size its decision to the actual resolved stack. Additive + a COPY —
                # agents persist ONLY via `answers_to_persist`, never by mutating context;
                # existing single-module agents ignore this key.
                "all_answers": {m: dict(a) for m, a in answers.items()},
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
