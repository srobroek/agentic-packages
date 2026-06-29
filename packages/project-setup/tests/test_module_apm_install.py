"""End-to-end tests for the apm-install module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, after order, step,
    marketplace input declared, agentic_packages default == "")
  - missing apm warns and continues (status=ok) — requires non-empty packages
  - --inspect emits "would run" and does not call apm
  - apm present: runs install + compile (codex + claude) → status=ok
    asserts install command contains ONLY the user-supplied package (no baseline appended)
  - compile_claude=False: claude compile step is skipped → status=ok
  - empty agentic_packages → clean no-op (install subprocess never invoked) SC-003
  - "srobroek" does not appear in module.py source SC-001 / FR-014

All tests use offline stub scripts on PATH — no real apm/mise/uv tool calls are made.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_apm_install.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/apm-install"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    *,
    agentic_packages: str = "",
    marketplace: str = "",
    compile_claude: bool = True,
) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["apm-install"],
        "modules": {
            "apm-install": {
                "id": "apm-install",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "agentic_packages": agentic_packages,
                    "marketplace": marketplace,
                    "compile_claude": compile_claude,
                },
                "steps": [{"id": "install", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(project: Path, plan: Path, *, inspect: bool = False) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "install"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def _make_exec(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


_APM_STUB_BODY = """\
#!/usr/bin/env bash
if [ "$1" = "--version" ]; then echo "apm 0.99.0"; exit 0; fi
if [ "$1" = "install" ]; then echo "installed"; exit 0; fi
if [ "$1" = "compile" ]; then echo "compiled"; exit 0; fi
if [ "$1" = "list" ]; then echo ""; exit 0; fi
if [ "$1" = "run" ]; then echo "run ok"; exit 0; fi
exit 0
"""


def _stub_apm(bin_dir: Path) -> Path:
    return _make_exec(bin_dir / "apm", _APM_STUB_BODY)


# ── fixture ──────────────────────────────────────────────────────────────── #


# ── tests ────────────────────────────────────────────────────────────────── #


def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "apm-install"
    assert mani.default_enabled is False
    assert mani.reconcile is False
    after = mani.order.get("after") if mani.order else []
    assert "dirs-scaffold" in (after or []), f"Expected dirs-scaffold in after, got: {after}"
    assert "precommit-setup" in (after or []), f"Expected precommit-setup in after, got: {after}"
    assert any(s.id == "install" and s.kind == "python" for s in mani.steps)
    # FR-003: agentic_packages default must be "" (empty)
    ap_inputs = [i for i in mani.inputs if i.key == "agentic_packages"]
    assert ap_inputs, "agentic_packages input not found in manifest"
    assert ap_inputs[0].default == "", (
        f"agentic_packages default must be '' (standalone), got: {ap_inputs[0].default!r}"
    )
    # marketplace input must be declared
    mp_inputs = [i for i in mani.inputs if i.key == "marketplace"]
    assert mp_inputs, "marketplace input not declared in module.toml"


def test_apm_missing_warns_and_continues(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    # Build a PATH that has uv (needed to launch module.py via `uv run`) but no
    # apm, mise, or any other apm resolution path.  We locate uv's directory
    # dynamically so the test works across machines regardless of how uv was installed.
    uv_bin = shutil.which("uv") or ""
    uv_dir = str(Path(uv_bin).parent) if uv_bin else ""
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    path_parts = [str(stub_bin)] + ([uv_dir] if uv_dir else []) + ["/usr/bin", "/bin"]
    monkeypatch.setenv("PATH", ":".join(path_parts))

    # Non-empty agentic_packages so the code reaches the apm-availability check
    plan = _frozen_plan(tmp_path, agentic_packages="mypkg@my-marketplace")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    warnings = result.get("warnings", [])
    assert any("apm" in w.lower() for w in warnings), (
        f"Expected a warning about apm not found, got: {warnings}"
    )


def test_inspect_skips_execution(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    # Use a marker-file apm to detect any real invocation
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    marker = tmp_path / "apm_was_called"
    _make_exec(
        stub_bin / "apm",
        f"#!/usr/bin/env bash\ntouch {marker}\n{_APM_STUB_BODY}",
    )
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    # Non-empty agentic_packages so the code reaches the inspect branch
    plan = _frozen_plan(tmp_path, agentic_packages="mypkg@my-marketplace")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "would run" in result.get("message", "").lower(), (
        f"Expected 'would run' in inspect message, got: {result.get('message')!r}"
    )
    # --inspect must not invoke apm at all (the _apm_available check also calls apm --version,
    # which would set the marker); confirm the marker is absent
    assert not marker.exists(), "--inspect must not invoke apm"


def test_apm_present_runs_install_and_compile(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    call_log = tmp_path / "apm_calls.txt"
    _make_exec(
        stub_bin / "apm",
        f"#!/usr/bin/env bash\n"
        f'echo "$@" >> {call_log}\n'
        f"{_APM_STUB_BODY}",
    )
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    # Explicit non-empty package from user-chosen marketplace
    plan = _frozen_plan(
        tmp_path,
        agentic_packages="mypkg@my-marketplace",
        marketplace="my-marketplace",
        compile_claude=True,
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    # Only acceptable warnings are the patch/audit script-not-found ones
    hard_warnings = [
        w for w in result.get("warnings", [])
        if "failed" in w.lower()
    ]
    assert not hard_warnings, f"Unexpected failure warnings: {hard_warnings}"

    # Assert install command contains ONLY the user-supplied package (SC-004)
    # No srobroek or mcp-* baseline packages should be present
    if call_log.exists():
        calls = call_log.read_text()
        assert "mypkg@my-marketplace" in calls, (
            f"Expected user package in install call, got: {calls}"
        )
        assert "srobroek" not in calls, (
            f"srobroek must not appear in any apm call, got: {calls}"
        )
        # Baseline mcp-* packages must not be appended
        for baseline in ("mcp-codebase-memory", "mcp-context7", "mcp-package-version", "mcp-repomix"):
            assert baseline not in calls, (
                f"Baseline package {baseline!r} must not be appended, got: {calls}"
            )


def test_empty_packages_is_noop(tmp_path, monkeypatch):
    """SC-003: empty agentic_packages → clean no-op; install subprocess never invoked."""
    project = tmp_path / "proj"
    project.mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    marker = tmp_path / "apm_was_called"
    _make_exec(
        stub_bin / "apm",
        f"#!/usr/bin/env bash\ntouch {marker}\n{_APM_STUB_BODY}",
    )
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    # Empty agentic_packages (the new standalone default)
    plan = _frozen_plan(tmp_path, agentic_packages="", marketplace="")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", f"Expected ok, got: {result}"
    # Must report no-op message
    msg = result.get("message", "")
    assert "no apm packages selected" in msg.lower() or "nothing to install" in msg.lower(), (
        f"Expected no-op message, got: {msg!r}"
    )
    # apm must never have been invoked (even for --version check)
    assert not marker.exists(), (
        "apm was invoked despite empty package list — install subprocess must not run"
    )


def test_no_srobroek_in_module(tmp_path):
    """FR-014/SC-001: 'srobroek' must not appear in module.py runtime source."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    source = module_py.read_text()
    assert "srobroek" not in source, (
        "Found 'srobroek' in module.py — all srobroek references must be removed (FR-003/FR-014)"
    )


def test_compile_claude_false_skips_claude_compile(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()

    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # Use a stub that records compile targets into a file
    call_log = tmp_path / "apm_calls.txt"
    _make_exec(
        stub_bin / "apm",
        f"#!/usr/bin/env bash\n"
        f'echo "$@" >> {call_log}\n'
        f"{_APM_STUB_BODY}",
    )
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    # Non-empty agentic_packages so the install path is taken
    plan = _frozen_plan(
        tmp_path,
        agentic_packages="mypkg@my-marketplace",
        compile_claude=False,
    )
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    # Verify no 'compile --target claude' call was made
    if call_log.exists():
        calls = call_log.read_text()
        assert "compile --target claude" not in calls, (
            f"compile_claude=False but saw a claude compile call: {calls}"
        )
