"""Module enablement resolution (FR-001 through FR-008).

Computes the set of module ids to execute from:
  - base defaults  (manifests with default_enabled=True)
  - committed selection  (reproduce mode — authoritative; read from answers.toml
                          [modules].enabled)
  - proposed selection   (init mode — agent-supplied; may be None → base-only)

Also closes the enabled set over each module's ``requires`` edges so that a
module you enable automatically drags in its hard dependencies.

Standard library only.
"""

from __future__ import annotations

from typing import Any

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts

SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def resolve_enabled_modules(
    manifests: list[Any],
    *,
    committed_enabled: list[str] | None,
    proposed_enabled: list[str] | None,
    mode: str,
) -> tuple[set[str], list[SetupError]]:
    """Compute the enabled module id set.

    Parameters
    ----------
    manifests:
        All discovered ``ModuleManifest`` instances (the full set).
    committed_enabled:
        The ``[modules].enabled`` list read from ``.project-setup/answers.toml``
        (None if absent).  In ``"reproduce"`` mode this is authoritative; in
        ``"init"`` mode it is ignored.
    proposed_enabled:
        The agent-proposed list of optional module ids to enable in ``"init"``
        mode (None = base-only, safe default per FR-007).
    mode:
        ``"init"`` or ``"reproduce"``.

    Returns
    -------
    (enabled_ids, errors)
        ``enabled_ids`` is the resolved set (base ∪ selection, closed over
        ``requires``).  ``errors`` is a list of ``SetupError`` with code
        ``UNKNOWN_MODULE``; never raises.
    """
    errors: list[SetupError] = []
    all_ids = {m.id for m in manifests}

    # Build requires map: id -> list[required_id]
    requires_map: dict[str, list[str]] = {}
    for m in manifests:
        requires_map[m.id] = list(m.order.get("requires", []))

    # Base: all manifests whose default_enabled is exactly True
    base: set[str] = {m.id for m in manifests if m.default_enabled is True}

    # Selection: reproduce uses committed (authoritative); init uses proposed
    if mode == "reproduce":
        raw_selection: list[str] | None = committed_enabled
    else:
        raw_selection = proposed_enabled

    # Validate selection ids
    explicit_selection: set[str] = set()
    if raw_selection is not None:
        for mid in raw_selection:
            if mid not in all_ids:
                errors.append(SetupError(
                    error_code=ErrorCode.UNKNOWN_MODULE,
                    module_id=mid,
                    expected=f"a discovered module id (one of: {sorted(all_ids)})",
                    received=f"unknown module id '{mid}'",
                    how_to_fix=(
                        f"Remove or correct '{mid}' from the enabled modules list — "
                        f"it does not match any discovered module. "
                        f"Available ids: {sorted(all_ids)}"
                    ),
                ))
            else:
                explicit_selection.add(mid)

    # Combined: base ∪ explicit
    enabled = base | explicit_selection

    # Close over requires transitively (BFS)
    enabled = _close_requires(enabled, requires_map, all_ids, errors)

    return enabled, errors


def _close_requires(
    enabled: set[str],
    requires_map: dict[str, list[str]],
    all_ids: set[str],
    errors: list[SetupError],
) -> set[str]:
    """BFS-expand ``enabled`` to include all transitive ``requires`` targets.

    Unknown required ids (not in all_ids) are reported as UNKNOWN_MODULE errors
    and skipped (the validate-closed gate will also catch MISSING_REQUIRES for
    the enabled set, so we report here and let the pipeline surface them).
    """
    result = set(enabled)
    queue = list(enabled)
    visited: set[str] = set()

    while queue:
        mid = queue.pop(0)
        if mid in visited:
            continue
        visited.add(mid)
        for req in requires_map.get(mid, []):
            if req not in all_ids:
                errors.append(SetupError(
                    error_code=ErrorCode.UNKNOWN_MODULE,
                    module_id=mid,
                    expected=f"a discovered module id for requires target",
                    received=f"unknown requires target '{req}' from module '{mid}'",
                    how_to_fix=(
                        f"Module '{mid}' requires '{req}' but '{req}' was not "
                        f"discovered. Check that the source providing '{req}' is "
                        f"configured and reachable."
                    ),
                ))
                continue
            if req not in result:
                result.add(req)
                queue.append(req)

    return result
