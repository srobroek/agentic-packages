"""Thin wrapper: runs the multi-step-python example module tests.

The authoritative test file lives at:
  skills/project-setup/examples/multi-step-python/test_multi_step_python.py

This wrapper imports it so the standard test suite command
  uv run --with pytest pytest -q packages/project-setup/tests/
picks it up without duplicating test logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_EXAMPLE_TEST = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "project-setup"
    / "examples"
    / "multi-step-python"
    / "test_multi_step_python.py"
)

_spec = importlib.util.spec_from_file_location("test_multi_step_python", _EXAMPLE_TEST)
assert _spec and _spec.loader, f"cannot locate example test at {_EXAMPLE_TEST}"
_mod = importlib.util.module_from_spec(_spec)
sys.modules["test_multi_step_python"] = _mod
_spec.loader.exec_module(_mod)

# Re-export all test_* names so pytest collects them from this module.
for _name, _obj in list(_mod.__dict__.items()):
    if _name.startswith("test"):
        globals()[_name] = _obj
