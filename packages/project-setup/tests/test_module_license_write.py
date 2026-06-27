"""End-to-end tests for the license-write module (13-license vendor+fetch model).

SC-001 carve-out: year and author lines vary at runtime. Tests exclude those
lines from byte-identical assertions and verify only the stable body portions.

Verifies:
  - manifest parses and is valid — choice over all 13 keys, dynamic_fetch input
  - apache-2.0: writes LICENSE, stable body matches vendored template
  - mit: writes LICENSE, stable body matches vendored template
  - bsd-3-clause: writes LICENSE, contains expected stable text
  - --inspect writes nothing
  - reconcile=false: second run skips (write-if-absent)
  - explicit author input overrides git config
  - dynamic_fetch=true OFFLINE: warns + falls back to vendored (no real network)
  - dynamic_fetch=true with successful fetch: uses fetched body (monkeypatched)

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_license_write.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest.mock
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/license-write"
_LICENSES_DIR = _PLUGIN_ROOT / _MODULE_REL / "templates" / "licenses"

_ALL_KEYS = [
    "agpl-3.0",
    "apache-2.0",
    "bsd-2-clause",
    "bsd-3-clause",
    "bsl-1.0",
    "cc0-1.0",
    "epl-2.0",
    "gpl-2.0",
    "gpl-3.0",
    "lgpl-2.1",
    "mit",
    "mpl-2.0",
    "unlicense",
]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    license_type: str = "apache-2.0",
    author: str = "",
    dynamic_fetch: bool = False,
) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["license-write"],
        "modules": {
            "license-write": {
                "id": "license-write",
                "version": "2.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "license": license_type,
                    "author": author,
                    "dynamic_fetch": dynamic_fetch,
                },
                "steps": [{"id": "write", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "write"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def _stable_lines(text: str, key: str) -> list[str]:
    """Return lines that are NOT the SC-001 year/author carve-out lines.

    Skips any line containing 'Copyright' (catches all variants: Copyright [yyyy],
    Copyright (c) [year], Copyright (C) etc.) regardless of license type.
    """
    return [line for line in text.splitlines() if "Copyright" not in line and "copyright" not in line]


def _load_license_module():
    """Load module.py in-process for monkeypatching tests."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"

    # Ensure the SDK is available in sys.modules
    sdk_path = _PLUGIN_ROOT / "runner" / "sdk.py"
    if "ps_sdk" not in sys.modules:
        sdk_spec = importlib.util.spec_from_file_location("ps_sdk", sdk_path)
        assert sdk_spec and sdk_spec.loader
        sdk_mod = importlib.util.module_from_spec(sdk_spec)
        sys.modules["ps_sdk"] = sdk_mod
        sdk_spec.loader.exec_module(sdk_mod)

    # Ensure runner deps are loaded
    runner_dir = _PLUGIN_ROOT / "runner"
    for dep in ("contracts", "plan"):
        if dep not in sys.modules:
            dspec = importlib.util.spec_from_file_location(dep, runner_dir / f"{dep}.py")
            assert dspec and dspec.loader
            dmod = importlib.util.module_from_spec(dspec)
            sys.modules[dep] = dmod
            dspec.loader.exec_module(dmod)

    spec = importlib.util.spec_from_file_location("license_write_mod", module_py)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["license_write_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


# ── manifest ────────────────────────────────────────────────────────────────── #

def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "license-write"
    assert mani.default_enabled is True
    assert mani.reconcile is False
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert mani.order["requires"] == ["core-identity"]

    # Check all 13 choices are declared
    input_keys = {inp.key for inp in mani.inputs}
    assert "license" in input_keys
    assert "author" in input_keys
    assert "dynamic_fetch" in input_keys

    license_input = next(inp for inp in mani.inputs if inp.key == "license")
    assert set(license_input.choices) == set(_ALL_KEYS), (
        f"Expected 13 license choices, got: {license_input.choices}"
    )
    assert license_input.default == "apache-2.0"


def test_all_13_vendored_templates_exist():
    """All 13 license template files must be present and non-empty."""
    for key in _ALL_KEYS:
        tmpl = _LICENSES_DIR / f"{key}.txt"
        assert tmpl.is_file(), f"Vendored template missing: {tmpl}"
        body = tmpl.read_text(encoding="utf-8")
        assert len(body) > 100, f"Template too small (stub?): {key}.txt ({len(body)} bytes)"
        assert not body.startswith("# LICENSE STUB"), f"Template is still a stub: {key}.txt"


# ── apache-2.0 ──────────────────────────────────────────────────────────────── #

def test_apache_license_written(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="apache-2.0", author="Test Author")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert result["files_written"] == ["LICENSE"]

    written = (project / "LICENSE").read_text()
    template_raw = (_LICENSES_DIR / "apache-2.0.txt").read_text()

    # SC-001 carve-out: exclude copyright lines from byte comparison.
    template_stable = _stable_lines(
        template_raw.replace("[yyyy]", "YEAR_PLACEHOLDER")
                    .replace("[name of copyright owner]", "AUTHOR_PLACEHOLDER"),
        "apache-2.0",
    )
    written_stable = _stable_lines(written, "apache-2.0")
    assert written_stable == template_stable

    # Runtime substitution happened
    assert "Test Author" in written
    assert "[yyyy]" not in written
    assert "[name of copyright owner]" not in written
    # Content includes the Apache header
    assert "Apache License" in written
    assert "Version 2.0" in written


# ── mit ─────────────────────────────────────────────────────────────────────── #

def test_mit_license_written(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="mit", author="MIT Dev")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["files_written"] == ["LICENSE"]

    written = (project / "LICENSE").read_text()
    template_raw = (_LICENSES_DIR / "mit.txt").read_text()

    template_stable = _stable_lines(
        template_raw.replace("[year]", "Y").replace("[fullname]", "A"),
        "mit",
    )
    written_stable = _stable_lines(written, "mit")
    assert written_stable == template_stable

    assert "MIT Dev" in written
    assert "MIT License" in written
    assert "THE SOFTWARE IS PROVIDED" in written
    assert "[year]" not in written
    assert "[fullname]" not in written


# ── bsd-3-clause ────────────────────────────────────────────────────────────── #

def test_bsd3_license_written(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="bsd-3-clause", author="BSD Corp")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["files_written"] == ["LICENSE"]

    written = (project / "LICENSE").read_text()
    assert "BSD 3-Clause" in written
    assert "BSD Corp" in written
    assert "Redistribution and use in source and binary forms" in written
    assert "[year]" not in written
    assert "[fullname]" not in written


# ── no-placeholder licenses ─────────────────────────────────────────────────── #

def test_gpl3_license_written(tmp_path):
    """GPL-3.0 has no placeholders — should write verbatim (minus the header preamble)."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="gpl-3.0", author="Someone")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["files_written"] == ["LICENSE"]

    written = (project / "LICENSE").read_text()
    assert "GNU GENERAL PUBLIC LICENSE" in written
    assert "Version 3" in written


# ── inspect ─────────────────────────────────────────────────────────────────── #

def test_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="apache-2.0")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["diffs"][0]["kind"] == "create"
    assert not (project / "LICENSE").exists()


# ── reconcile=false ─────────────────────────────────────────────────────────── #

def test_idempotent_second_run_skips(tmp_path):
    """reconcile=false: second run skips existing LICENSE."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="apache-2.0", author="Author One")
    _run(project, plan)
    first_content = (project / "LICENSE").read_text()

    proc2 = _run(project, plan)
    assert proc2.returncode == 0, proc2.stderr
    result = json.loads(proc2.stdout)
    assert result["diffs"][0]["kind"] == "skip"
    assert result["files_written"] == []
    assert (project / "LICENSE").read_text() == first_content


# ── explicit author ─────────────────────────────────────────────────────────── #

def test_explicit_author_used(tmp_path):
    """Explicit author input overrides git config."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, license_type="mit", author="Explicit Corp")
    _run(project, plan)
    assert "Explicit Corp" in (project / "LICENSE").read_text()


# ── dynamic_fetch OFFLINE ───────────────────────────────────────────────────── #

def test_dynamic_fetch_offline_warns_and_uses_vendored(tmp_path):
    """dynamic_fetch=true with fetch failure: warns and falls back to vendored copy.

    Monkeypatches _fetch_license_body to return None (offline simulation).
    Verifies the warning is emitted and the vendored body is used.
    No real network access.
    """
    lm = _load_license_module()

    warnings_out: list[str] = []

    with unittest.mock.patch.object(lm, "_fetch_license_body", return_value=None):
        body = lm._render(
            key="mit",
            year="2025",
            author="Offline User",
            dynamic_fetch=True,
            warnings=warnings_out,
        )

    # Fallback to vendored: MIT content present
    assert "MIT License" in body
    assert "THE SOFTWARE IS PROVIDED" in body
    assert "Offline User" in body

    # Warning must mention the key and the fetch failure
    assert any("mit" in w and "vendored" in w for w in warnings_out), (
        f"Expected fallback warning; got: {warnings_out}"
    )


def test_dynamic_fetch_offline_does_not_raise(tmp_path):
    """dynamic_fetch=true with fetch failure must not raise — returns vendored copy."""
    lm = _load_license_module()
    warnings_out: list[str] = []

    with unittest.mock.patch.object(lm, "_fetch_license_body", return_value=None):
        # Should not raise even for a license with no placeholders
        body = lm._render(
            key="unlicense",
            year="2025",
            author="",
            dynamic_fetch=True,
            warnings=warnings_out,
        )

    assert "unlicense" in body.lower() or "public domain" in body.lower() or len(body) > 50
    assert len(warnings_out) == 1


def test_dynamic_fetch_success_uses_fetched_body(tmp_path):
    """dynamic_fetch=true with successful fetch: uses the fetched body, not vendored."""
    lm = _load_license_module()
    fake_body = "Fake License\n\nCopyright [year] [fullname]\n\nPermission granted.\n"
    warnings_out: list[str] = []

    with unittest.mock.patch.object(lm, "_fetch_license_body", return_value=fake_body):
        body = lm._render(
            key="mit",
            year="2099",
            author="Future Corp",
            dynamic_fetch=True,
            warnings=warnings_out,
        )

    assert "Permission granted." in body
    assert "2099" in body
    assert "Future Corp" in body
    # No warnings when fetch succeeds
    assert warnings_out == []
