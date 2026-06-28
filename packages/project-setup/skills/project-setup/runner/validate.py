"""Validate-closed gate — the ONLY place that raises.

Accumulates ALL problems from:
  1. Order errors from order.py (DEPENDENCY_CYCLE, MISSING_REQUIRES)
  2. Missing required inputs (MISSING_ANSWER)
  3. Missing required tools via shutil.which (MISSING_REQUIRED_TOOL)

Then raises ``GateFailure`` with every collected error at once if there are any
problems; otherwise returns the ordered module id list.

This is the exclusive raise site. manifest.py and order.py return errors
without raising.

Standard library only.
"""

from __future__ import annotations

import shutil

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts
import order as _order_mod

SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode
GateFailure = _contracts.GateFailure
resolve_order = _order_mod.resolve_order


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #
def validate_closed(
    manifests: list,
    answers: dict[str, dict[str, object]],
) -> list[str]:
    """Run the validate-closed gate over *manifests* and *answers*.

    Parameters
    ----------
    manifests:
        Enabled ``ModuleManifest`` instances (from manifest.py).
    answers:
        The resolved answer map keyed by module id, then by input key.
        Produced by ``answers.resolve_final_answers()``.

    Returns
    -------
    ordered_ids: list[str]
        Stable topological order of enabled module ids.

    Raises
    ------
    GateFailure
        If ANY problem is found. Carries EVERY accumulated error so the caller
        sees the full picture at once (FR-017).
    """
    all_errors: list[SetupError] = []

    # ── 1. Topological order + dependency errors ─────────────────────────── #
    ordered_ids, order_errors = resolve_order(manifests)
    all_errors.extend(order_errors)

    # ── 2. Missing required inputs ─────────────────────────────────────────── #
    for m in manifests:
        mod_answers = answers.get(m.id, {})
        for inp in m.inputs:
            if inp.required and inp.key not in mod_answers:
                all_errors.append(SetupError(
                    error_code=ErrorCode.MISSING_ANSWER,
                    module_id=m.id,
                    expected=f"answer for required input '{inp.key}'",
                    received="missing",
                    how_to_fix=(
                        f"Provide a value for '{inp.key}' in module '{m.id}' "
                        f"(prompt: {getattr(inp, 'prompt', inp.key)!r})"
                    ),
                ))

    # ── 3. Missing required tools ─────────────────────────────────────────── #
    # Deduplicate tool checks across all modules for efficiency; but report
    # the specific module(s) that need each tool.
    tool_to_modules: dict[str, list[str]] = {}
    for m in manifests:
        for tool in m.tools.get("required", []):
            tool_to_modules.setdefault(tool, []).append(m.id)

    for tool, requiring_modules in sorted(tool_to_modules.items()):
        if shutil.which(tool) is None:
            for mod_id in requiring_modules:
                all_errors.append(SetupError(
                    error_code=ErrorCode.MISSING_REQUIRED_TOOL,
                    module_id=mod_id,
                    expected=f"'{tool}' on PATH",
                    received="not found",
                    how_to_fix=(
                        f"Install '{tool}' and ensure it is on your PATH "
                        f"(required by module '{mod_id}')"
                    ),
                ))

    # ── Raise if any problems found ─────────────────────────────────────────── #
    if all_errors:
        raise GateFailure(all_errors)

    return ordered_ids
