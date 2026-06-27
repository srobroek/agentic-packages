"""Mode detection for the project-setup runner.

Determines whether a project directory should be set up fresh (``"init"``) or
re-applied from committed state (``"reproduce"``).

The rule is simple and intentionally binary: if
``.project-setup/sources.toml`` exists in the project directory, the project
has previously been set up with this runner, so the mode is ``"reproduce"``;
otherwise it is ``"init"``.

Standard library only.
"""

from __future__ import annotations

from pathlib import Path


def detect_mode(project_dir: str | Path) -> str:
    """Return ``"init"`` or ``"reproduce"`` based on committed project state.

    Parameters
    ----------
    project_dir:
        The root directory of the project being set up.

    Returns
    -------
    str
        ``"init"`` — first run (no ``.project-setup/sources.toml`` present).
        ``"reproduce"`` — re-run (committed ``sources.toml`` found; answers and
        sources are loaded from the committed tree).
    """
    sources_toml = Path(project_dir) / ".project-setup" / "sources.toml"
    return "reproduce" if sources_toml.is_file() else "init"
