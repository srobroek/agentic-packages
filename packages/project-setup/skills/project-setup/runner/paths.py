"""Path + cache resolution — the SOLE owner of every location constant.

Every subsystem imports these helpers rather than hard-coding paths, so the
plugin-root, module-root, cache, and project-file locations are defined exactly
once. See shared-contracts.md §6 (PLUGIN_ROOT resolution) and §8.

Standard library only (uv's Python >= 3.11).
"""

from __future__ import annotations

import os
from pathlib import Path

# The runner library lives at:
#   packages/project-setup/skills/project-setup/runner/   (this file's dir)
# and the plugin root is the package dir two levels up:
#   packages/project-setup/skills/project-setup/
# i.e. the dir that holds SKILL.md, runner/, and modules/.
_RUNNER_DIR = Path(__file__).resolve().parent


def plugin_root() -> Path:
    """Resolve the plugin root.

    Prefers the APM/Claude token ``$PLUGIN_ROOT`` when the runtime exports it
    (APM rewrites ``${PLUGIN_ROOT}`` in command strings; some channels also
    export it). Falls back to a ``__file__``-relative path, which is correct on
    the channels where the token is unset at runtime (e.g. plain ``uv run`` of a
    copied plugin tree, where install simply copied files).
    """

    env = os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        p = Path(env).expanduser()
        # The token may point at the package root (.../project-setup) or the
        # skill dir; normalize to the skill dir that contains runner/ + modules/.
        if (p / "runner").is_dir():
            return p
        cand = p / "skills" / "project-setup"
        if (cand / "runner").is_dir():
            return cand
        return p
    # __file__-relative fallback: runner/ -> skill dir.
    return _RUNNER_DIR.parent


def sdk_path() -> Path:
    """Absolute path to sdk.py, loaded by each module.py via importlib."""

    return _RUNNER_DIR / "sdk.py"


def bundled_modules_dir() -> Path:
    """The shipped base modules — always present, lowest discovery precedence."""

    return plugin_root() / "modules"


def cache_root() -> Path:
    """Home-global runtime cache root (NOT committed, NOT under .project-setup/).

    Overridable via ``$PROJECT_SETUP_CACHE_DIR`` for tests/CI. Holds fetched
    source checkouts and the frozen execution plan.
    """

    env = os.environ.get("PROJECT_SETUP_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "project-setup"


def sources_cache_dir() -> Path:
    """Where fetched git module sources are checked out (mirrors APM's model)."""

    return cache_root() / "git"


def frozen_plan_path() -> Path:
    """The frozen execution plan location — in the runtime cache, NEVER inside
    the committed .project-setup/ (determinism + reproducibility, FR-008/FR-019).
    """

    return cache_root() / "plan.json"


def home_config_path() -> Path:
    """The user's personal config (catalog + default answers). Not authoritative
    for any project (FR-021). ``$PROJECT_SETUP_CONFIG`` overrides the location.
    """

    env = os.environ.get("PROJECT_SETUP_CONFIG")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "project-setup" / "config.toml"


def home_modules_dir() -> Path:
    """Personal module root (third discovery precedence)."""

    return home_config_path().parent / "modules"


def project_setup_dir(project_dir: Path) -> Path:
    """The committed per-project state dir (sources.toml + answers.toml)."""

    return Path(project_dir) / ".project-setup"


def project_modules_dir(project_dir: Path) -> Path:
    """Project-local module root (second discovery precedence)."""

    return project_setup_dir(project_dir) / "modules"


def env_modules_dir() -> Path | None:
    """Highest-precedence module root from ``$PROJECT_SETUP_MODULES_DIR``."""

    env = os.environ.get("PROJECT_SETUP_MODULES_DIR")
    return Path(env).expanduser() if env else None
