"""Git source fetcher — sole owner of clone/fetch into the sources cache.

``fetch_source`` clones or updates a git repository into the path owned by
``paths.sources_cache_dir()`` and returns the path to the (optionally
subdirectoried) checkout root.  All failure modes are non-fatal: a missing
``git`` binary, an unreachable remote, an unknown ref, etc., return a
``FetchResult`` with ``ok=False`` and a human-readable ``skipped_reason``
rather than raising.  Callers proceed with whatever other roots are available
(FR-013 / SC-008).  The pipeline drives the locator list itself (one
``fetch_source`` call per source), so there is no aggregation layer here.

Standard library only (``subprocess`` for git, ``pathlib``, ``shutil``).
No third-party imports.  No network access in the module itself — the network
call is inside ``subprocess.run``.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .locator import Locator

# Runner and sources dirs are both on sys.path via cli.py / conftest.py /
# executor PYTHONPATH (spec 005 OQ-2); plain imports resolve for both.
import paths as _paths
import locator as _locator_mod

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
    else:
        # Already present — fetch latest from origin to pick up floating refs.
        ok, msg = _run_git("fetch", "--prune", "origin", cwd=repo_dir)
        if not ok:
            # Treat as a soft failure: we have a previous checkout, use it.
            # Log but don't abort — the caller gets the stale tree.
            pass

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


