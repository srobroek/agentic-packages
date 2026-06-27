"""Module discovery — precedence-ordered search across all roots.

``discover_modules`` walks a set of root directories in descending precedence
order (highest wins) and finds every directory containing a ``module.toml``
file at depth 1.  It applies the collision rule from
shared-contracts.md §7:

* Two modules with the same ``id`` **in the same root kind** → hard
  ``ID_COLLISION`` :class:`~contracts.SetupError` naming both manifest paths
  via ``module_ids``.
* Same ``id`` **across precedence levels** → reported shadow (higher-
  precedence entry wins, the shadow is recorded in the report — NOT an
  error).

Additionally, ``default_enabled=true`` on any module whose root is NOT the
bundled root is rejected with a ``FORBIDDEN_FIELD``
:class:`~contracts.SetupError` (FR-035).

``build_discovery_roots`` assembles the canonical precedence list from the
environment, a given project dir, and the caller-supplied fetched roots so
that callers only need to pass the fetched roots (everything else is
resolved internally).

Standard library only.  No network access.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Import runner siblings by file path (contract §6)
# ---------------------------------------------------------------------------

_SOURCES_DIR = Path(__file__).resolve().parent
_RUNNER_DIR = _SOURCES_DIR.parent


def _load_runner(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER_DIR / f"{name}.py")
    assert spec and spec.loader, f"Cannot find runner module: {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_contracts = _load_runner("contracts")
_paths = _load_runner("paths")

SetupError = _contracts.SetupError
ErrorCode = _contracts.ErrorCode


# ---------------------------------------------------------------------------
# Root-kind enum
# ---------------------------------------------------------------------------

class RootKind(str, Enum):
    """Symbolic name for each discovery-root tier."""

    ENV = "env"
    PROJECT = "project"
    HOME = "home"
    FETCHED = "fetched"
    BUNDLED = "bundled"


# ---------------------------------------------------------------------------
# DiscoveredModule dataclass
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredModule:
    """A single module found during discovery."""

    id: str
    root_path: Path         # absolute path to the module directory
    root_kind: RootKind
    manifest_path: Path     # absolute path to the module.toml


# ---------------------------------------------------------------------------
# DiscoveryReport
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryReport:
    """Summary of a discovery pass."""

    shadows: list[dict[str, Any]] = field(default_factory=list)
    """Cross-level id collisions where the higher-precedence entry won.

    Each entry: ``{"id": str, "winner": Path, "shadow": Path,
    "winner_kind": str, "shadow_kind": str}``
    """

    parse_errors: list[SetupError] = field(default_factory=list)
    """Non-fatal: manifests that could not be parsed are skipped and logged."""

    hard_errors: list[SetupError] = field(default_factory=list)
    """Fatal: same-root-kind ID_COLLISION and default_enabled violations.

    Callers should check this list and surface all errors to the user before
    proceeding.
    """


# ---------------------------------------------------------------------------
# Internal TOML mini-reader
# ---------------------------------------------------------------------------

def _read_module_id_and_default_enabled(
    toml_path: Path,
    errors: list[SetupError],
) -> tuple[str | None, bool | None]:
    """Read just [module].id and [module].default_enabled from *toml_path*.

    Returns ``(None, None)`` and appends a ``MANIFEST_MALFORMED`` error on
    failure.  Never raises.
    """
    try:
        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:  # noqa: BLE001
        errors.append(SetupError(
            error_code=ErrorCode.MANIFEST_MALFORMED,
            expected="valid TOML",
            received=str(exc),
            how_to_fix=f"Fix TOML syntax in {toml_path}",
        ))
        return None, None

    module_section = data.get("module")
    if not isinstance(module_section, dict):
        errors.append(SetupError(
            error_code=ErrorCode.MANIFEST_MALFORMED,
            expected="[module] table",
            received=str(type(module_section)),
            how_to_fix=f"Add a [module] table with an 'id' key in {toml_path}",
        ))
        return None, None

    mod_id = module_section.get("id")
    if not mod_id or not isinstance(mod_id, str):
        errors.append(SetupError(
            error_code=ErrorCode.MANIFEST_MALFORMED,
            expected="string [module].id",
            received=str(mod_id),
            how_to_fix=f"Add a string 'id' to [module] in {toml_path}",
        ))
        return None, None

    default_enabled = module_section.get("default_enabled")
    # Coerce to Optional[bool]: only accept actual booleans.
    if default_enabled is not None and not isinstance(default_enabled, bool):
        default_enabled = None  # treat as absent; manifest.py will reject it

    return mod_id, default_enabled


# ---------------------------------------------------------------------------
# Root assembly
# ---------------------------------------------------------------------------

@dataclass
class _RootEntry:
    path: Path
    kind: RootKind


def build_discovery_roots(
    fetched_roots: list[Path],
    project_dir: Path | None = None,
    bundled_dir: Path | None = None,
) -> list[_RootEntry]:
    """Build the precedence-ordered list of discovery roots.

    Order (highest → lowest):
    1. ``$PROJECT_SETUP_MODULES_DIR`` env override
    2. Project-local: ``<project_dir>/.project-setup/modules/``
    3. Home: ``~/.config/project-setup/modules/``
    4. Each fetched source root (in the order supplied by the caller)
    5. Bundled: ``${PLUGIN_ROOT}/.../modules/``

    *bundled_dir* lets a caller (e.g. the pipeline with an injected
    ``plugin_root_path``) override the bundled root rather than resolving the
    global ``__file__``-relative one — essential for tests and for honoring an
    explicitly-passed plugin root. Defaults to ``paths.bundled_modules_dir()``.

    Entries whose path does not exist on disk are silently omitted (they
    simply contribute no modules).
    """
    entries: list[_RootEntry] = []

    # 1. Env override
    env_dir = _paths.env_modules_dir()
    if env_dir is not None:
        entries.append(_RootEntry(path=env_dir, kind=RootKind.ENV))

    # 2. Project-local
    if project_dir is not None:
        proj_mod_dir = _paths.project_modules_dir(project_dir)
        entries.append(_RootEntry(path=proj_mod_dir, kind=RootKind.PROJECT))

    # 3. Home
    home_dir = _paths.home_modules_dir()
    entries.append(_RootEntry(path=home_dir, kind=RootKind.HOME))

    # 4. Fetched sources (caller-ordered)
    for p in fetched_roots:
        entries.append(_RootEntry(path=p, kind=RootKind.FETCHED))

    # 5. Bundled (caller-injected override, else the global resolver)
    bundled = bundled_dir if bundled_dir is not None else _paths.bundled_modules_dir()
    entries.append(_RootEntry(path=bundled, kind=RootKind.BUNDLED))

    return entries


# ---------------------------------------------------------------------------
# Core discovery logic
# ---------------------------------------------------------------------------

def _scan_root(
    entry: _RootEntry,
    parse_errors: list[SetupError],
) -> list[DiscoveredModule]:
    """Return all ``DiscoveredModule`` instances found under *entry.path*.

    Walks exactly one level deep (``<root>/<name>/module.toml``).  Malformed
    manifests are logged to *parse_errors* and skipped.
    """
    modules: list[DiscoveredModule] = []
    root = entry.path

    if not root.is_dir():
        return modules

    for candidate in sorted(root.iterdir()):  # sorted for determinism
        if not candidate.is_dir():
            continue
        toml_path = candidate / "module.toml"
        if not toml_path.is_file():
            continue

        id_, default_enabled = _read_module_id_and_default_enabled(toml_path, parse_errors)
        if id_ is None:
            continue

        modules.append(DiscoveredModule(
            id=id_,
            root_path=candidate,
            root_kind=entry.kind,
            manifest_path=toml_path,
        ))

    return modules


def discover_modules(
    roots_in_precedence_order: list[_RootEntry],
    bundled_root: Path | None = None,
) -> tuple[dict[str, DiscoveredModule], DiscoveryReport]:
    """Discover modules across all roots and apply collision rules.

    Parameters
    ----------
    roots_in_precedence_order:
        Ordered list of root entries (index 0 = highest precedence).  Use
        :func:`build_discovery_roots` to construct this list.
    bundled_root:
        The path that corresponds to the bundled modules root.  Used to
        enforce FR-035: ``default_enabled=true`` is only allowed for modules
        whose root is the bundled root.  If ``None``, defaults to
        ``paths.bundled_modules_dir()``.

    Returns
    -------
    modules:
        ``{id: DiscoveredModule}`` — the winning module for each id, after
        applying precedence and collision rules.
    report:
        :class:`DiscoveryReport` with shadows, parse errors, and hard errors.
    """
    report = DiscoveryReport()
    bundled = bundled_root if bundled_root is not None else _paths.bundled_modules_dir()

    # Map from root_kind → {id: list[DiscoveredModule]}
    # Used to detect same-root-kind ID_COLLISION.
    per_kind: dict[RootKind, dict[str, list[DiscoveredModule]]] = {}

    # Collect all discovered modules, grouped by root_kind.
    for entry in roots_in_precedence_order:
        found = _scan_root(entry, report.parse_errors)
        bucket = per_kind.setdefault(entry.kind, {})
        for mod in found:
            bucket.setdefault(mod.id, []).append(mod)

    # Apply same-root-kind collision rule: any bucket with >1 module for the
    # same id is a hard ID_COLLISION error (names both paths).
    # Collect all hard-error ids so they are excluded from the final map.
    collision_ids: set[str] = set()

    for kind, id_map in per_kind.items():
        for mod_id, mods in id_map.items():
            if len(mods) > 1:
                collision_ids.add(mod_id)
                report.hard_errors.append(SetupError(
                    error_code=ErrorCode.ID_COLLISION,
                    expected=f"unique id '{mod_id}' within {kind.value} roots",
                    received=f"{len(mods)} modules with id '{mod_id}' in {kind.value} roots",
                    how_to_fix=(
                        f"Rename one of the conflicting modules in "
                        f"{kind.value} root(s) so ids are unique"
                    ),
                    module_ids=[str(m.manifest_path) for m in mods],
                ))

    # Build the winning map by iterating roots in precedence order.
    # We process entries highest→lowest; first time we see an id wins.
    # Track (kind, id) pairs already processed so that multiple entries of the
    # same kind (e.g. two FETCHED roots) don't re-process the merged bucket
    # on every iteration — each (kind, id) pair is handled exactly once.
    winning: dict[str, DiscoveredModule] = {}
    # rejected ids (default_enabled violation) — excluded from winning map
    rejected_ids: set[str] = set()
    # (kind, id) pairs we have already visited in the second loop
    visited: set[tuple[RootKind, str]] = set()

    for entry in roots_in_precedence_order:
        bucket = per_kind.get(entry.kind, {})
        for mod_id, mods in bucket.items():
            pair = (entry.kind, mod_id)
            if pair in visited:
                continue  # already handled this (kind, id) combination
            visited.add(pair)

            if mod_id in collision_ids:
                continue  # hard same-root-kind error already recorded; skip

            # Take the representative module (collision guarantees exactly one
            # by here — if there were multiple they'd be in collision_ids).
            winner = mods[0]

            # Validate default_enabled constraint (FR-035).
            _, default_enabled = _read_module_id_and_default_enabled(
                winner.manifest_path, []
            )
            if default_enabled is True and winner.root_kind != RootKind.BUNDLED:
                report.hard_errors.append(SetupError(
                    error_code=ErrorCode.FORBIDDEN_FIELD,
                    module_id=mod_id,
                    expected="default_enabled=true only on bundled modules",
                    received=(
                        f"default_enabled=true on non-bundled module "
                        f"'{mod_id}' ({winner.root_kind.value} root)"
                    ),
                    how_to_fix=(
                        f"Remove 'default_enabled = true' from "
                        f"{winner.manifest_path} — this field is only "
                        f"allowed in the bundled module root"
                    ),
                ))
                rejected_ids.add(mod_id)
                continue  # do not insert this module

            if mod_id in rejected_ids:
                continue  # a higher-precedence entry already rejected this id

            if mod_id in winning:
                # Cross-level shadow: higher-precedence entry already won.
                existing = winning[mod_id]
                report.shadows.append({
                    "id": mod_id,
                    "winner": existing.root_path,
                    "shadow": winner.root_path,
                    "winner_kind": existing.root_kind.value,
                    "shadow_kind": winner.root_kind.value,
                })
            else:
                winning[mod_id] = winner

    return winning, report
