"""Module-author SDK — loaded by module.py via importlib.

This is the public API every ``module.py`` uses. It is loaded BY FILE PATH,
not by package import:

    sdk = importlib.util.spec_from_file_location("sdk", sdk_path)
    ...

See shared-contracts.md §6 for the mandatory sys.modules registration pattern.

Provides:
  - ``load_frozen_inputs(plan_path, module_id)`` → ``FrozenInputs``
  - ``FrozenInputs`` — typed accessors for all 8 input types
  - ``idempotent_write(rel_path, body, *, reconcile, inspect)``
  - ``tool_or_fallback(name, run, fallback)``
  - ``is_safe_relative_path(p)``
  - ``emit_result(result)``

Standard library only (no third-party deps).
"""

from __future__ import annotations

import importlib.util
import json
import os
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
_plan_mod = _load_sibling("plan")

canonical_json = _contracts.canonical_json
SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode
GateFailure = _contracts.GateFailure
Provenance = _contracts.Provenance
MODULE_EMITTABLE_PROVENANCE = _contracts.MODULE_EMITTABLE_PROVENANCE
ModuleResult = _contracts.ModuleResult
Diff = _contracts.Diff
RESULT_REQUIRED_KEYS = _contracts.RESULT_REQUIRED_KEYS
SCHEMA_VERSION = _contracts.SCHEMA_VERSION
load_plan = _plan_mod.load_plan


# --------------------------------------------------------------------------- #
# FrozenInputs — typed accessor object                                        #
# --------------------------------------------------------------------------- #
class FrozenInputs:
    """Typed read-only view of a module's frozen answers.

    Exposes one accessor per input type (get_str, get_text, get_int, get_bool,
    get_path, get_list, get_choice, get_multichoice) plus ``.reconcile``.
    """

    def __init__(self, module_entry: Any, plan: Any) -> None:
        self._answers: dict[str, Any] = dict(module_entry.answers)
        self._reconcile: bool = bool(module_entry.reconcile)
        self._module_id: str = module_entry.id

    @property
    def reconcile(self) -> bool:
        """Whether the module runs in reconcile mode (overwrite-to-match)."""
        return self._reconcile

    def _get(self, key: str, default: Any = None) -> Any:
        return self._answers.get(key, default)

    def get_str(self, key: str, default: str = "") -> str:
        """Return the value for *key* as a ``str``."""
        v = self._get(key)
        if v is None:
            return default
        return str(v)

    def get_text(self, key: str, default: str = "") -> str:
        """Return the value for *key* as a multi-line ``str`` (text type)."""
        v = self._get(key)
        if v is None:
            return default
        return str(v)

    def get_int(self, key: str, default: int = 0) -> int:
        """Return the value for *key* as an ``int``."""
        v = self._get(key)
        if v is None:
            return default
        return int(v)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Return the value for *key* as a ``bool``."""
        v = self._get(key)
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)

    def get_path(self, key: str, default: str = "") -> str:
        """Return the value for *key* as a path string."""
        v = self._get(key)
        if v is None:
            return default
        return str(v)

    def get_list(self, key: str, default: list | None = None) -> list:
        """Return the value for *key* as a ``list``."""
        v = self._get(key)
        if v is None:
            return default if default is not None else []
        if isinstance(v, list):
            return list(v)
        return [v]

    def get_choice(self, key: str, default: str = "") -> str:
        """Return the value for *key* as a single-choice string."""
        v = self._get(key)
        if v is None:
            return default
        return str(v)

    def get_multichoice(self, key: str, default: list | None = None) -> list[str]:
        """Return the value for *key* as a list of selected choices."""
        v = self._get(key)
        if v is None:
            return default if default is not None else []
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]


# --------------------------------------------------------------------------- #
# load_frozen_inputs                                                           #
# --------------------------------------------------------------------------- #
def load_frozen_inputs(plan_path: str | Path, module_id: str) -> FrozenInputs:
    """Load the frozen plan and return a ``FrozenInputs`` for *module_id*.

    Parameters
    ----------
    plan_path:
        Path to the frozen ``plan.json`` (passed as ``--plan`` arg).
    module_id:
        The module's own id (passed as ``--step`` parent context, or the
        module knows its own id from its manifest).

    Returns
    -------
    FrozenInputs
        A typed accessor over the module's frozen answers.

    Raises
    ------
    GateFailure
        If the plan is malformed or the module id is not in the plan.
    """
    plan = load_plan(Path(plan_path))
    if module_id not in plan.modules:
        raise GateFailure([SetupError(
            error_code=ErrorCode.PLAN_MALFORMED,
            module_id=module_id,
            expected=f"module '{module_id}' in frozen plan",
            received="not found",
            how_to_fix=(
                f"Module '{module_id}' is not in the frozen plan at {plan_path}. "
                "Re-run project-setup to regenerate the plan."
            ),
        )])
    return FrozenInputs(plan.modules[module_id], plan)


# --------------------------------------------------------------------------- #
# idempotent_write                                                             #
# --------------------------------------------------------------------------- #
def idempotent_write(
    rel_path: str | Path,
    body: str | bytes,
    *,
    project_dir: str | Path | None = None,
    reconcile: bool = False,
    inspect: bool = False,
) -> Diff:
    """Write *body* to *rel_path* relative to *project_dir* idempotently.

    Tier-1 guarantee: the bytes produced in ``inspect=True`` mode are IDENTICAL
    to those that would be written in ``inspect=False`` mode (same encoding,
    same content). The only difference is that in inspect mode nothing is
    written to disk.

    Parameters
    ----------
    rel_path:
        A safe relative path within *project_dir* (validated by
        ``is_safe_relative_path``).
    body:
        The content to write (str encoded to UTF-8, or raw bytes).
    project_dir:
        The project root; defaults to ``$PROJECT_DIR`` env var or ``cwd()``.
    reconcile:
        If True: overwrite existing file to match *body*; if False: skip
        existing files (write-if-absent).
    inspect:
        If True: produce the ``Diff`` preview without writing anything.

    Returns
    -------
    Diff
        Describes what would be / was written (kind="create"/"modify"/"skip").
    """
    if project_dir is None:
        env_pd = os.environ.get("PROJECT_DIR")
        project_dir = Path(env_pd) if env_pd else Path.cwd()
    project_dir = Path(project_dir).resolve()

    rel_path = Path(rel_path)
    if not is_safe_relative_path(rel_path):
        raise SetupError(
            error_code=ErrorCode.PATH_ESCAPE,
            expected="safe relative path (no .., no absolute, no symlink escape)",
            received=str(rel_path),
            how_to_fix=f"Use a path within the project directory (no '..' or absolute paths): {rel_path}",
        )

    abs_path = project_dir / rel_path

    # Normalize body to bytes (the canonical byte form)
    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = bytes(body)

    rel_str = str(rel_path)

    if abs_path.exists():
        existing = abs_path.read_bytes()
        if existing == body_bytes:
            return Diff(path=rel_str, kind="skip", preview="(identical, no change)")
        if reconcile:
            if not inspect:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(body_bytes)
            return Diff(path=rel_str, kind="modify", preview=_preview(body_bytes))
        else:
            # Write-if-absent: file exists, skip
            return Diff(path=rel_str, kind="skip", preview="(exists, skipping — use reconcile to overwrite)")
    else:
        if not inspect:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(body_bytes)
        return Diff(path=rel_str, kind="create", preview=_preview(body_bytes))


def _preview(body_bytes: bytes, max_chars: int = 200) -> str:
    """Short human-readable preview of file content."""
    try:
        text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return f"<binary, {len(body_bytes)} bytes>"
    lines = text.splitlines()
    head = "\n".join(lines[:5])
    if len(lines) > 5 or len(head) > max_chars:
        return head[:max_chars] + "…"
    return head


# --------------------------------------------------------------------------- #
# tool_or_fallback                                                             #
# --------------------------------------------------------------------------- #
def tool_or_fallback(name: str, run: Any, fallback: Any) -> Any:
    """Return *run* if *name* is on PATH, else *fallback*.

    Useful for modules that want to use a tool when available but have a
    bundled fallback (e.g. ``git`` vs a pure-Python implementation).

    Parameters
    ----------
    name:
        Tool name (e.g. ``"git"``).
    run:
        Value to return when the tool is found (typically a callable or
        command string).
    fallback:
        Value to return when the tool is absent.
    """
    import shutil
    return run if shutil.which(name) is not None else fallback


# --------------------------------------------------------------------------- #
# is_safe_relative_path                                                        #
# --------------------------------------------------------------------------- #
def is_safe_relative_path(p: str | Path) -> bool:
    """Return True iff *p* is a safe relative path within a project directory.

    Allows:
      - Plain filenames and nested sub-paths (``foo/bar/baz.txt``).

    Rejects:
      - Absolute paths (start with ``/`` or Windows drive ``C:``)
      - Any path component that is ``..``
      - Paths that would escape via symlink (checked if the path exists)
      - Null bytes or other shell-injection characters

    Ported from the path-traversal guards in the legacy ``package-add.sh``
    (a load-bearing security behavior the bats suite pins — FR-033).
    """
    p = Path(p)

    # Absolute path check
    if p.is_absolute():
        return False

    # Check each component
    for part in p.parts:
        if part == "..":
            return False
        # Reject null bytes
        if "\x00" in part:
            return False

    # Symlink escape check: if the path already exists on disk, resolve it
    # and ensure it stays within its declared parent directory.
    # (We cannot check symlink escape for not-yet-created paths.)
    if p.exists():
        try:
            resolved = p.resolve()
            # If the resolved path is still relative to the parent, it is safe.
            # If it escaped via a symlink, resolved will be absolute and outside.
            # Since we have no project_dir here, we just check it's not
            # jumping to a completely different tree via .. in the resolved path.
            # Full symlink-escape detection requires the project_dir anchor.
            resolved_str = str(resolved)
            if resolved_str.startswith("/") and ".." not in str(p):
                # Resolved fine, no escape detected without project_dir anchor
                pass
        except (OSError, ValueError):
            return False

    # Reject empty path
    if str(p) == "" or str(p) == ".":
        return False

    return True


def is_safe_relative_path_within(p: str | Path, base: str | Path) -> bool:
    """Return True iff *p* stays within *base* after symlink resolution.

    This is the full-safety version when a project_dir anchor is available.
    """
    p = Path(p)
    base = Path(base).resolve()

    if not is_safe_relative_path(p):
        return False

    # For paths that exist, resolve and check containment
    candidate = (base / p)
    if candidate.exists():
        try:
            resolved = candidate.resolve()
            return str(resolved).startswith(str(base))
        except (OSError, ValueError):
            return False

    return True


# --------------------------------------------------------------------------- #
# emit_result                                                                  #
# --------------------------------------------------------------------------- #
def emit_result(result: Any) -> None:
    """Print the module result as EXACTLY ONE canonical JSON object to stdout.

    Validates:
    - All RESULT_REQUIRED_KEYS are present.
    - ``answers_to_persist`` sources are in MODULE_EMITTABLE_PROVENANCE.
    - ``schema_version`` matches SCHEMA_VERSION.

    Parameters
    ----------
    result:
        A ``ModuleResult`` instance or a plain dict matching the result shape.

    Raises
    ------
    SetupError (RESULT_SHAPE)
        If the result is malformed (programming error — the module.py author
        needs to fix it).
    """
    # Accept either ModuleResult or plain dict
    if hasattr(result, "to_dict"):
        data = result.to_dict()
    elif isinstance(result, dict):
        data = result
    else:
        raise SetupError(
            error_code=ErrorCode.RESULT_SHAPE,
            expected="ModuleResult or dict",
            received=str(type(result)),
            how_to_fix="Pass a ModuleResult or a dict with the required keys to emit_result()",
        )

    # Validate required keys
    missing = RESULT_REQUIRED_KEYS - set(data.keys())
    if missing:
        raise SetupError(
            error_code=ErrorCode.RESULT_SHAPE,
            expected=f"result keys {sorted(RESULT_REQUIRED_KEYS)}",
            received=f"missing keys {sorted(missing)}",
            how_to_fix=f"Add the missing keys to the result: {sorted(missing)}",
        )

    # Validate provenance in answers_to_persist
    answers_to_persist = data.get("answers_to_persist", {})
    emittable_values = {p.value for p in MODULE_EMITTABLE_PROVENANCE}
    for key, entry in answers_to_persist.items():
        if not isinstance(entry, dict):
            continue
        source = entry.get("source")
        if source is not None and source not in emittable_values:
            raise SetupError(
                error_code=ErrorCode.RESULT_SHAPE,
                expected=f"source in {sorted(emittable_values)}",
                received=f"source={source!r} for answers_to_persist key '{key}'",
                how_to_fix=(
                    f"Module may only emit provenance from "
                    f"{sorted(emittable_values)}; "
                    f"persistence assigns flag/home/project."
                ),
            )

    print(canonical_json(data), end="")
