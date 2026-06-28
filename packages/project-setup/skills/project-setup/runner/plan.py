"""Execution plan builder and canonical freeze.

Produces the ``ExecutionPlan`` dataclass from resolved manifests + answers,
then writes a byte-stable JSON snapshot to the runtime cache via
``canonical_json``.

On-disk shape matches shared-contracts.md §2 exactly:
  { schema_version, mode, order, modules: { id: PlanModule } }

NO absolute paths in any PlanModule field — ``module_rel_root`` is relative
to the plugin root (determinism rule).

Standard library only.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Sibling runner modules import by plain name; the runner dir is on sys.path via
# the entry point (cli.py / conftest.py / executor PYTHONPATH — spec 005 OQ-2).
import contracts as _contracts
import paths as _paths_mod
import manifest as _manifest_mod

canonical_json = _contracts.canonical_json
SCHEMA_VERSION = _contracts.SCHEMA_VERSION
ErrorCode = _contracts.ErrorCode
SetupError = _contracts.SetupError
GateFailure = _contracts.GateFailure
render_answer_block = _contracts.render_answer_block
frozen_plan_path = _paths_mod.frozen_plan_path
eval_when = _manifest_mod.eval_when  # gate `when` predicate (spec 004 FR-006)
plugin_root = _paths_mod.plugin_root


# --------------------------------------------------------------------------- #
# Dataclasses                                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class PlanModule:
    """Per-module entry in the frozen execution plan."""
    id: str
    version: str
    reconcile: bool
    module_rel_root: str    # relative to plugin root — NO absolute paths
    answers: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "reconcile": self.reconcile,
            "module_rel_root": self.module_rel_root,
            "answers": self.answers,
            "steps": self.steps,
        }


@dataclass
class ExecutionPlan:
    """The complete frozen execution plan."""
    schema_version: int
    mode: str                           # "init" | "reproduce"
    order: list[str]
    modules: dict[str, PlanModule] = field(default_factory=dict)
    written_at: str = ""                # ISO 8601 date set at freeze() time (spec 012
                                        # FR-014); advisory ADR "decided-on" date, not
                                        # an audit timestamp. Empty for pre-012 plans.

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "order": self.order,
            "modules": {k: v.to_dict() for k, v in self.modules.items()},
            "written_at": self.written_at,
        }


# --------------------------------------------------------------------------- #
# Builder                                                                      #
# --------------------------------------------------------------------------- #
def build_plan(
    manifests: list,
    resolved_answers: dict[str, dict[str, Any]],
    ordered_ids: list[str],
    mode: str = "init",
    plugin_root_path: Path | None = None,
) -> ExecutionPlan:
    """Assemble an ``ExecutionPlan`` from resolved manifests and answers.

    Parameters
    ----------
    manifests:
        Enabled ``ModuleManifest`` instances.
    resolved_answers:
        The coerced answer map from ``answers.resolve_final_answers()``.
    ordered_ids:
        The stable topological order from ``validate.validate_closed()``
        (or ``order.resolve_order()``).
    mode:
        "init" (first run) or "reproduce" (re-run from committed answers).
    plugin_root_path:
        The plugin root directory; defaults to ``paths.plugin_root()``.
        Used to compute ``module_rel_root`` as a relative path.

    Returns
    -------
    ExecutionPlan
    """
    if plugin_root_path is None:
        plugin_root_path = plugin_root()

    manifest_by_id = {m.id: m for m in manifests}
    modules: dict[str, PlanModule] = {}

    for mod_id in ordered_ids:
        m = manifest_by_id[mod_id]

        # Compute module_rel_root relative to plugin root.
        # The manifest knows its own path via module_toml_path if set;
        # otherwise we derive it from the bundled modules convention.
        # Callers may set manifest._toml_path to the actual module.toml path.
        toml_path: Path | None = getattr(m, "_toml_path", None)
        if toml_path is not None:
            module_dir = Path(toml_path).parent.resolve()
            try:
                module_rel_root = str(module_dir.relative_to(plugin_root_path.resolve()))
            except ValueError:
                # Outside plugin root — use the path as-is (relative resolution
                # is best-effort for external modules).
                module_rel_root = str(module_dir)
        else:
            # Fallback: bundled modules convention
            module_rel_root = f"modules/{mod_id}"

        # Steps as plain dicts (keep id/kind/steering/message + the spec-004 gate
        # enrichment: hardness/allow_flag/skip_flag/init_only).
        mod_answers = resolved_answers.get(mod_id, {})
        steps = []
        for s in m.steps:
            # Conditional gate (spec 004 FR-006, Decision D): a kind=gate step with a
            # `when` predicate that is FALSE against the frozen answers is DROPPED
            # from the plan here, at build time. Because answers are frozen, init and
            # reproduce drop/keep the identical set (Subtlety 3 — deterministic). This
            # is how G3 is "hard for public, none for private" without a 4th hardness.
            if s.kind == "gate" and not eval_when(s.when, mod_answers):
                continue

            step_dict: dict[str, Any] = {"id": s.id, "kind": s.kind}
            if s.steering:
                step_dict["steering"] = s.steering
            if s.message:
                # Two-phase plan (spec 003 Decision H, SUBTLETY 1): a kind=gate
                # message may contain the literal token ``{decision}``; replace it
                # with the module's resolved answers (the agent's frozen decision,
                # already folded in by the Phase-A pass) so the bare gate primitive
                # can render a Tier-2 pin table without a richer gate shape. Plain
                # messages with no token are passed through unchanged.
                msg = s.message
                if "{decision}" in msg:
                    msg = msg.replace("{decision}", render_answer_block(mod_answers))
                step_dict["message"] = msg
            # Gate enrichment fields — carried into the frozen plan so the
            # data-driven non-interactive resolver (executor.run_gate_step) reads
            # them. Only emitted for gate steps and only when non-default, to keep
            # the frozen plan minimal and pre-004 plans byte-identical.
            if s.kind == "gate":
                if s.hardness != "hard":
                    step_dict["hardness"] = s.hardness
                if s.allow_flag:
                    step_dict["allow_flag"] = s.allow_flag
                if s.skip_flag:
                    step_dict["skip_flag"] = s.skip_flag
                if s.init_only:
                    step_dict["init_only"] = True
            # reproduce_only (spec 012 FR-009): carried into the frozen plan for all
            # step kinds, serialized only when True to keep pre-012 plan dicts minimal.
            if getattr(s, "reproduce_only", False):
                step_dict["reproduce_only"] = True
            steps.append(step_dict)

        modules[mod_id] = PlanModule(
            id=mod_id,
            version=m.version,
            reconcile=m.reconcile,
            module_rel_root=module_rel_root,
            answers=resolved_answers.get(mod_id, {}),
            steps=steps,
        )

    return ExecutionPlan(
        schema_version=SCHEMA_VERSION,
        mode=mode,
        order=ordered_ids,
        modules=modules,
    )


# --------------------------------------------------------------------------- #
# Freeze / load                                                                #
# --------------------------------------------------------------------------- #
def freeze(plan: ExecutionPlan, path: Path | None = None) -> Path:
    """Serialize *plan* to disk via ``canonical_json``.

    Parameters
    ----------
    plan:
        The ``ExecutionPlan`` to freeze.
    path:
        Output path; defaults to ``paths.frozen_plan_path()``.

    Returns
    -------
    Path
        The path where the plan was written.
    """
    if path is None:
        path = frozen_plan_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # LOCAL date (spec 012 Q5): advisory ADR "decided-on" date, not an audit timestamp.
    # Set every freeze so the field reflects THIS run. The STACK.md date comes from the
    # frozen derived answer (written_at answer persisted at init), not this field — see
    # plan.md "written_at determinism subtlety". Do NOT add conditional logic here.
    plan.written_at = datetime.date.today().isoformat()
    data = plan.to_dict()
    _check_no_absolute_paths(data)
    path.write_text(canonical_json(data), encoding="utf-8")
    return path


def load_plan(path: Path) -> ExecutionPlan:
    """Read and validate a frozen plan from *path*.

    Raises
    ------
    GateFailure
        If the file is missing, unparseable, or has a mismatched schema_version.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except FileNotFoundError:
        raise GateFailure([SetupError(
            error_code=ErrorCode.PLAN_MALFORMED,
            expected=f"frozen plan at {path}",
            received="file not found",
            how_to_fix=f"Run project-setup to generate a fresh plan at {path}",
        )])
    except json.JSONDecodeError as exc:
        raise GateFailure([SetupError(
            error_code=ErrorCode.PLAN_MALFORMED,
            expected="valid JSON",
            received=str(exc),
            how_to_fix=f"Delete {path} and re-run project-setup",
        )])

    if not isinstance(data, dict):
        raise GateFailure([SetupError(
            error_code=ErrorCode.PLAN_MALFORMED,
            expected="JSON object",
            received=str(type(data)),
            how_to_fix=f"Delete {path} and re-run project-setup",
        )])

    # Validate schema_version
    got_version = data.get("schema_version")
    if got_version != SCHEMA_VERSION:
        raise GateFailure([SetupError(
            error_code=ErrorCode.PLAN_MALFORMED,
            expected=f"schema_version={SCHEMA_VERSION}",
            received=f"schema_version={got_version!r}",
            how_to_fix=(
                f"The frozen plan at {path} was created with an incompatible "
                f"schema version. Delete it and re-run project-setup."
            ),
        )])

    # Validate required top-level keys
    required = {"schema_version", "mode", "order", "modules"}
    missing = required - set(data.keys())
    if missing:
        raise GateFailure([SetupError(
            error_code=ErrorCode.PLAN_MALFORMED,
            expected=f"keys {sorted(required)}",
            received=f"missing {sorted(missing)}",
            how_to_fix=f"Delete {path} and re-run project-setup",
        )])

    # Reconstruct dataclass
    modules: dict[str, PlanModule] = {}
    for mod_id, mod_data in data["modules"].items():
        modules[mod_id] = PlanModule(
            id=mod_data.get("id", mod_id),
            version=mod_data.get("version", ""),
            reconcile=bool(mod_data.get("reconcile", False)),
            module_rel_root=mod_data.get("module_rel_root", ""),
            answers=mod_data.get("answers", {}),
            steps=mod_data.get("steps", []),
        )

    return ExecutionPlan(
        schema_version=data["schema_version"],
        mode=data["mode"],
        order=data["order"],
        modules=modules,
        written_at=data.get("written_at", ""),  # spec 012 FR-014/SC-010: default "" for pre-012 plans
    )


# --------------------------------------------------------------------------- #
# Safety helper                                                                #
# --------------------------------------------------------------------------- #
def _check_no_absolute_paths(data: Any, _path: str = "") -> None:
    """Recursively assert no absolute path strings exist in the plan data.

    Called before writing to detect determinism violations early.
    Not a user-visible error — raises ValueError if violated (programming error).
    """
    if isinstance(data, dict):
        for k, v in data.items():
            _check_no_absolute_paths(v, f"{_path}.{k}")
    elif isinstance(data, list):
        for i, v in enumerate(data):
            _check_no_absolute_paths(v, f"{_path}[{i}]")
    elif isinstance(data, str):
        if data.startswith("/") or (len(data) > 1 and data[1] == ":"):
            raise ValueError(
                f"Absolute path found in frozen plan at {_path!r}: {data!r}. "
                "Use module_rel_root relative to plugin root."
            )
