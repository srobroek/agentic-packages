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

import importlib.util
import json
import sys
from dataclasses import dataclass, field
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
_paths_mod = _load_sibling("paths")

canonical_json = _contracts.canonical_json
SCHEMA_VERSION = _contracts.SCHEMA_VERSION
ErrorCode = _contracts.ErrorCode
SetupError = _contracts.SetupError
GateFailure = _contracts.GateFailure
frozen_plan_path = _paths_mod.frozen_plan_path
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "order": self.order,
            "modules": {k: v.to_dict() for k, v in self.modules.items()},
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

        # Steps as plain dicts (keep only id/kind/steering/message)
        steps = []
        for s in m.steps:
            step_dict: dict[str, Any] = {"id": s.id, "kind": s.kind}
            if s.steering:
                step_dict["steering"] = s.steering
            if s.message:
                step_dict["message"] = s.message
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
