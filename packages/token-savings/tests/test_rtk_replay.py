"""Regression coverage for the replay helper's package-relative guard path."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".apm"
    / "skills"
    / "token-savings"
    / "scripts"
    / "rtk-replay.py"
)
VERIFY_SCRIPT = SCRIPT.with_name("rtk-verify.py")


def _module(path=SCRIPT, name="token_savings_script"):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_replay_resolves_the_package_root_guard():
    module = _module()
    expected = SCRIPT.resolve().parents[4] / "scripts" / "rtk-rewrite-guard.py"
    assert module.GUARD == expected
    assert module.GUARD.is_file()


def test_replay_resolves_the_codex_deployment_guard(tmp_path):
    module = _module()
    deployed_script = tmp_path / ".agents" / "skills" / "token-savings" / "scripts" / "rtk-replay.py"
    deployed_script.parent.mkdir(parents=True)
    deployed_script.touch()
    guard = tmp_path / ".codex" / "hooks" / "token-savings" / "scripts" / "rtk-rewrite-guard.py"
    guard.parent.mkdir(parents=True)
    guard.touch()
    assert module.guard_path(deployed_script) == guard


def test_verify_resolves_the_codex_deployment_guard(tmp_path):
    module = _module(VERIFY_SCRIPT, "token_savings_rtk_verify")
    deployed_script = tmp_path / ".agents" / "skills" / "token-savings" / "scripts" / "rtk-verify.py"
    deployed_script.parent.mkdir(parents=True)
    deployed_script.touch()
    guard = tmp_path / ".codex" / "hooks" / "token-savings" / "scripts" / "rtk-rewrite-guard.py"
    guard.parent.mkdir(parents=True)
    guard.touch()
    assert module.guard_path(deployed_script) == guard
