"""Pytest fixture-free conftest: establish the runner import seam (spec 005 OQ-2).

The runner modules resolve their siblings with a plain ``import <name>`` (no more
per-file ``_load_sibling`` importlib bootstrap). For that to work when a test loads
a runner module via ``spec_from_file_location`` (the ``_load(name)`` helper each test
file defines), the runner dir and its ``sources/`` sub-package dir must be on
``sys.path``. The CLI entry (``cli.py``) does the same insert for production; the
``uv run module.py`` subprocess path is covered by the executor's PYTHONPATH
injection (spec 005 FR-001). Importing this once at collection time covers every
test module under this directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"

for _p in (str(_RUNNER), str(_RUNNER / "sources")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
