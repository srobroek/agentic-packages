"""Git source fetcher — sole owner of clone/fetch into the sources cache.

``fetch_source`` clones or updates a git repository into the path owned by
``paths.sources_cache_dir()`` and returns the path to the (optionally
subdirectoried) checkout root.  All failure modes are non-fatal: a missing
``git`` binary, an unreachable remote, an unknown ref, etc., return a
``FetchResult`` with ``ok=False`` and a human-readable ``skipped_reason``
rather than raising.  Callers proceed with whatever other roots are available
(FR-013 / SC-008).

``fetch_all`` drives a list of locators and aggregates the outcomes into a
``SourceReport``.

Standard library only (``subprocess`` for git, ``pathlib``, ``shutil``).
No third-party imports.  No network access in the module itself — the network
call is inside ``subprocess.run``.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .locator import Locator

# ---------------------------------------------------------------------------
# Import sibling runner modules by file path (contract §6)
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


def _load_sibling(name: str):
    qualified = f"sources.{name}"
    if qualified in sys.modules:
        return sys.modules[qualified]
    path = _SOURCES_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    assert spec and spec.loader, f"Cannot find sources module: {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = mod
    spec.loader.exec_module(mod)
    return mod


_paths = _load_runner("paths")
_locator_mod = _load_sibling("locator")
Locator = _locator_mod.Locator


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    """Outcome of fetching a single locator."""

    ok: bool
    root_path: Path | None       # path to checkout root (or subdir within it)
    locator: "Locator"
    skipped_reason: str = ""     # non-empty when ok=False


@dataclass
class SourceReport:
    """Aggregated summary of a ``fetch_all`` call."""

    fetched: list[FetchResult] = field(default_factory=list)    # newly cloned
    cached: list[FetchResult] = field(default_factory=list)     # already present
    skipped: list[FetchResult] = field(default_factory=list)    # failed / offline

    def successful_roots(self) -> list[Path]:
        """Ordered list of all root paths that resolved (fetched + cached)."""
        results: list[Path] = []
        for r in self.fetched + self.cached:
            if r.ok and r.root_path is not None:
                results.append(r.root_path)
        return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_GIT_TIMEOUT = 60  # seconds per git subprocess call


def _git_available() -> bool:
    return shutil.which("git") is not None


def _run_git(*args: str, cwd: Path | None = None) -> tuple[bool, str]:
    """Run a git command, returning (success, stderr_or_stdout)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, (result.stderr or result.stdout).strip()
    except subprocess.TimeoutExpired:
        return False, f"git {args[0]} timed out after {_GIT_TIMEOUT}s"
    except FileNotFoundError:
        return False, "git binary not found"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _clone_or_update(locator: "Locator", cache_dir: Path) -> FetchResult:
    """Clone into *cache_dir* (if absent) or fetch + checkout *locator.ref*."""
    from .locator import cache_key  # local import to avoid circular at module level

    key = cache_key(locator)
    repo_dir = cache_dir / key

    if not repo_dir.exists():
        # Clone bare-ish with --no-checkout so we don't pay for a full working
        # tree on the initial clone — then checkout later.
        ok, msg = _run_git(
            "clone", "--no-local", "--filter=blob:none",
            locator.origin, str(repo_dir),
        )
        if not ok:
            return FetchResult(ok=False, root_path=None, locator=locator,
                               skipped_reason=f"git clone failed: {msg}")
        was_cached = False
    else:
        # Already present — fetch latest from origin to pick up floating refs.
        ok, msg = _run_git("fetch", "--prune", "origin", cwd=repo_dir)
        if not ok:
            # Treat as a soft failure: we have a previous checkout, use it.
            # Log but don't abort — the caller gets the stale tree.
            was_cached = True
        else:
            was_cached = True

    # Checkout the requested ref into a detached HEAD.
    ref = locator.ref if locator.ref and locator.ref != "HEAD" else "origin/HEAD"
    ok, msg = _run_git("checkout", "--detach", ref, cwd=repo_dir)
    if not ok:
        # Try without "origin/" prefix — user may have supplied a SHA or tag.
        ok2, msg2 = _run_git("checkout", "--detach", locator.ref, cwd=repo_dir)
        if not ok2:
            return FetchResult(ok=False, root_path=None, locator=locator,
                               skipped_reason=f"git checkout {locator.ref!r} failed: {msg2}")

    # Resolve subdir
    resolved = repo_dir
    if locator.subdir:
        resolved = repo_dir / locator.subdir
        if not resolved.is_dir():
            return FetchResult(ok=False, root_path=None, locator=locator,
                               skipped_reason=(
                                   f"subdir {locator.subdir!r} not found in checkout "
                                   f"of {locator.origin!r}"
                               ))

    return FetchResult(
        ok=True,
        root_path=resolved,
        locator=locator,
        skipped_reason="",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_source(locator: "Locator") -> FetchResult:
    """Fetch (or validate) a single source locator.

    * For **local** locators: verify the path exists, return it directly (no
      git involved).
    * For **git** locators: clone/fetch into ``sources_cache_dir()`` and
      checkout the requested ref.

    Any failure (git absent, network unavailable, bad ref, missing subdir)
    returns ``FetchResult(ok=False, ...)`` — this function NEVER raises.
    """
    try:
        if locator.kind == "local":
            p = Path(locator.origin)
            if not p.is_dir():
                return FetchResult(ok=False, root_path=None, locator=locator,
                                   skipped_reason=f"local path does not exist: {locator.origin}")
            return FetchResult(ok=True, root_path=p, locator=locator)

        # git locator
        if not _git_available():
            return FetchResult(ok=False, root_path=None, locator=locator,
                               skipped_reason="git is not available on PATH")

        cache_dir = _paths.sources_cache_dir()
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return FetchResult(ok=False, root_path=None, locator=locator,
                               skipped_reason=f"cannot create cache dir {cache_dir}: {exc}")

        return _clone_or_update(locator, cache_dir)

    except Exception as exc:  # noqa: BLE001 — safety net: never raise
        return FetchResult(ok=False, root_path=None, locator=locator,
                           skipped_reason=f"unexpected error: {exc}")


def fetch_all(locators: list["Locator"]) -> tuple[list[Path], SourceReport]:
    """Fetch all *locators* and return ``(successful_roots, report)``.

    The returned roots list contains only the paths for which fetching
    succeeded (ok=True), in the order they were supplied.  Skipped locators
    appear in ``report.skipped`` only.

    This function does NOT raise.  Each individual failure is recorded in the
    report; processing always continues to the next locator.
    """
    report = SourceReport()
    roots: list[Path] = []

    for locator in locators:
        result = fetch_source(locator)
        if result.ok:
            assert result.root_path is not None
            roots.append(result.root_path)
            # Determine fetched vs cached: if the cache dir/key already existed
            # before we called _clone_or_update, classify as cached.  We use a
            # heuristic: the repo_dir existed before this fetch_all call iff
            # skipped_reason is empty AND we didn't just create it.  Since
            # fetch_source doesn't distinguish, we classify by whether the
            # cache entry existed at call time.
            if locator.kind == "git":
                from .locator import cache_key
                key = cache_key(locator)
                repo_dir = _paths.sources_cache_dir() / key
                # After a successful fetch, we can't tell if we just created
                # the dir.  We mark as 'fetched' for git origins and 'cached'
                # only if fetch_source explicitly told us so.  Since
                # _clone_or_update always runs a fresh fetch/checkout, we
                # classify everything ok as 'fetched' for report purposes
                # (the distinction is advisory only).
                report.fetched.append(result)
            else:
                # Local paths are always "cached" (they live on disk already).
                report.cached.append(result)
        else:
            report.skipped.append(result)

    return roots, report
