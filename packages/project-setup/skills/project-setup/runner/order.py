"""Topological ordering — pure, non-raising.

Accepts the enabled ``ModuleManifest`` list and returns
``(ordered_ids: list[str], errors: list[SetupError])``.

Rules (shared-contracts.md §1, plan.md Phase 1 §4):
- ``requires`` is a hard dependency: absent/disabled target → MISSING_REQUIRES.
- ``after``/``before`` are soft: absent/disabled target → silently dropped.
- Cycles produce DEPENDENCY_CYCLE with the cycle path in ``module_ids``.
- Tie-break: deterministic by id (alphabetical within a generation).
- Never raises.

Standard library only (graphlib, Python >= 3.8; included in >= 3.9 stdlib).
"""

from __future__ import annotations

from graphlib import CycleError, TopologicalSorter

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts

SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #
def resolve_order(manifests: list) -> tuple[list[str], list[SetupError]]:
    """Return a deterministic topological order over *manifests*.

    Parameters
    ----------
    manifests:
        The enabled ``ModuleManifest`` instances (must expose ``.id``,
        ``.order["requires"]``, ``.order["after"]``, ``.order["before"]``).

    Returns
    -------
    (ordered_ids, errors):
        ``ordered_ids`` is empty when any error prevents ordering (cycles).
        ``errors`` is a list of ``SetupError``; never raises.
    """
    errors: list[SetupError] = []
    id_set = {m.id for m in manifests}

    # Build predecessor graph: id -> set of ids that must come before it.
    predecessors: dict[str, set[str]] = {m.id: set() for m in manifests}

    for m in manifests:
        mod_id = m.id
        order = m.order

        # Hard dependencies (requires)
        for req in order.get("requires", []):
            if req not in id_set:
                errors.append(SetupError(
                    error_code=ErrorCode.MISSING_REQUIRES,
                    module_id=mod_id,
                    module_ids=[mod_id, req],
                    expected=f"module '{req}' enabled",
                    received="absent or disabled",
                    how_to_fix=(
                        f"Enable module '{req}' or remove it from "
                        f"'{mod_id}' requires list"
                    ),
                ))
            else:
                predecessors[mod_id].add(req)

        # Soft: after (silently drop absent/disabled)
        for dep in order.get("after", []):
            if dep in id_set:
                predecessors[mod_id].add(dep)

        # Soft: before — means dep must come before us → dep is a predecessor
        # of mod_id, equivalently: add mod_id as a successor of dep.
        # We express "X before Y" as: Y has X as predecessor.
        for succ in order.get("before", []):
            if succ in id_set:
                # succ must come AFTER mod_id → mod_id is a predecessor of succ
                predecessors[succ].add(mod_id)

    if errors:
        # Missing-requires errors are non-fatal for ordering (we still attempt
        # the sort with the edges we have); but we return them alongside the
        # order. Cycles are the only case that blocks ordering.
        pass

    # ── Topological sort with deterministic tie-break ────────────────────── #
    # graphlib.TopologicalSorter does not guarantee a deterministic order among
    # nodes that are ready at the same time. We enforce alphabetical tie-break
    # by sorting the ready-set at each step.
    try:
        ts = TopologicalSorter(predecessors)
        ts.prepare()
        ordered: list[str] = []
        while ts.is_active():
            ready = sorted(ts.get_ready())  # alphabetical tie-break
            for node in ready:
                ordered.append(node)
                ts.done(node)
    except CycleError as exc:
        # exc.args[1] is the cycle sequence (list of node ids)
        cycle_path: list[str] = list(exc.args[1]) if len(exc.args) > 1 else []
        errors.append(SetupError(
            error_code=ErrorCode.DEPENDENCY_CYCLE,
            module_ids=cycle_path,
            expected="acyclic dependency graph",
            received=f"cycle: {' -> '.join(str(n) for n in cycle_path)}",
            how_to_fix="Break the dependency cycle by removing or reordering the requires/after/before edges",
        ))
        return [], errors

    return ordered, errors
