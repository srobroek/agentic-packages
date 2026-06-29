"""End-to-end tests for the speckit-bridge module.

Verifies:
  - manifest parses and is valid (id, default_enabled, reconcile, after order,
    step, and the new marketplace + speckit_source inputs)
  - spec_mode=none → skip, status ok
  - spec_mode=lightweight → specs/ dir created
  - spec_mode=lightweight --inspect → specs/ not created
  - spec_mode=full, speckit_source="" (default) → PUBLIC spec-kit path:
      command references github/spec-kit / specify, never srobroek
  - spec_mode=full, speckit_source non-empty → marketplace path: apm install
      uses the given locator, never srobroek
  - spec_mode=full, uv/specify absent → graceful degrade: status=ok, warning
      with manual public command, no hard error
  - inspect mode → message references public spec-kit command, no srobroek
  - no srobroek literal present in module.py source

Tests use offline stubs and subprocess env-patching to avoid network or live
tool dependencies.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_speckit_bridge.py
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
_MODULE_REL = "modules/speckit-bridge"
_MODULE_PY = _PLUGIN_ROOT / _MODULE_REL / "module.py"


def _load(name: str):
    # Use a unique key per test file to avoid sys.modules collisions across test files.
    unique_name = f"_skbridge_{name}"
    spec = importlib.util.spec_from_file_location(unique_name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(
    tmp: Path,
    spec_mode: str = "none",
    speckit_source: str = "",
    marketplace: str = "",
    speckit_version: str = "latest",
) -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["speckit-bridge"],
        "modules": {
            "speckit-bridge": {
                "id": "speckit-bridge",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "spec_mode": spec_mode,
                    "speckit_source": speckit_source,
                    "marketplace": marketplace,
                    "speckit_version": speckit_version,
                },
                "steps": [{"id": "setup", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _run(
    project: Path,
    plan: Path,
    *,
    inspect: bool = False,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "setup"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


def _make_apm_stub(bin_dir: Path, version_exit: int = 0, install_exit: int = 0) -> Path:
    """Write a bash apm stub to bin_dir/apm and make it executable."""
    stub = bin_dir / "apm"
    stub.write_text(
        f"#!/usr/bin/env bash\n"
        f'case "$1" in\n'
        f'    --version) echo "apm 0.99"; exit {version_exit} ;;\n'
        f'    install)   echo "install ok" >&2; exit {install_exit} ;;\n'
        f'    *)         exit 0 ;;\n'
        f'esac\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def _make_cmd_stub(bin_dir: Path, name: str, exit_code: int = 0, output: str = "") -> Path:
    """Write a generic bash stub that always exits exit_code."""
    stub = bin_dir / name
    stub.write_text(
        f"#!/usr/bin/env bash\n"
        f'echo "{output}"\n'
        f"exit {exit_code}\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def _make_uv_stub(bin_dir: Path, tool_install_exit: int = 0) -> Path:
    """Write a uv stub that:
    - passes 'uv run ...' through to the real uv binary (so the test harness
      can still launch the module via 'uv run module.py').
    - intercepts 'uv tool install ...' and exits with tool_install_exit.

    This avoids the stub swallowing the outer 'uv run' launch call.
    """
    real_uv = shutil.which("uv") or "uv"
    stub = bin_dir / "uv"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "run" ]; then\n'
        f'    exec "{real_uv}" "$@"\n'
        'fi\n'
        'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then\n'
        f'    exit {tool_install_exit}\n'
        'fi\n'
        'exit 0\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stub


# --------------------------------------------------------------------------- #
# Manifest                                                                      #
# --------------------------------------------------------------------------- #

def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "speckit-bridge"
    assert mani.default_enabled is False
    assert mani.reconcile is False
    assert mani.order.get("after") == ["apm-install"]
    assert any(s.id == "setup" and s.kind == "python" for s in mani.steps)
    input_keys = [i.key for i in mani.inputs]
    assert "spec_mode" in input_keys
    assert "marketplace" in input_keys
    assert "speckit_source" in input_keys
    # FR-V2: speckit_version input must be declared with default "latest"
    assert "speckit_version" in input_keys, (
        f"speckit_version input missing from manifest; got: {input_keys}"
    )
    sv_input = next(i for i in mani.inputs if i.key == "speckit_version")
    assert sv_input.default == "latest", (
        f"speckit_version default should be 'latest', got: {sv_input.default!r}"
    )


# --------------------------------------------------------------------------- #
# none / lightweight                                                            #
# --------------------------------------------------------------------------- #

def test_none_mode_skips(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="none")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert "skipped" in result.get("message", "").lower()


def test_lightweight_creates_specs_dir(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="lightweight")
    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"
    assert (project / "specs").is_dir()


def test_lightweight_inspect_writes_nothing(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="lightweight")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    assert not (project / "specs").exists()


# --------------------------------------------------------------------------- #
# full-mode — PUBLIC path (speckit_source="", default)                         #
# --------------------------------------------------------------------------- #

def test_full_mode_public_path_uses_public_speckit(tmp_path):
    """spec_mode=full with speckit_source="" → PUBLIC spec-kit path.

    Stubs uv (pass-through for 'uv run', intercepts 'uv tool install') and
    specify so install + init succeed.
    Asserts:
    - status ok
    - no srobroek reference anywhere in the result
    - message references the public pin / specify / spec-kit
    """
    project = tmp_path / "proj"
    project.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()

    # uv stub: passes 'uv run' through to real uv; intercepts 'uv tool install' (success)
    _make_uv_stub(stub_bin, tool_install_exit=0)
    # specify stub: succeeds for "specify init ."
    _make_cmd_stub(stub_bin, "specify", exit_code=0)

    patched_path = f"{stub_bin}:{os.environ.get('PATH', '')}"
    plan = _frozen_plan(tmp_path, spec_mode="full", speckit_source="")
    proc = _run(project, plan, extra_env={"PATH": patched_path})
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result
    # No srobroek anywhere in the result
    result_text = json.dumps(result)
    assert "srobroek" not in result_text, f"srobroek leaked into result: {result_text}"
    # Message should reference the public pin
    msg = result.get("message", "")
    assert "spec-kit" in msg.lower() or "specify" in msg.lower() or "public" in msg.lower(), (
        f"Expected public spec-kit reference in message, got: {msg!r}"
    )


def test_full_mode_inspect_references_public_command(tmp_path):
    """--inspect with spec_mode=full, speckit_source="" → message references public
    spec-kit URL / specify, NOT srobroek."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="full", speckit_source="")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result
    msg = result.get("message", "")
    assert "srobroek" not in msg, f"srobroek leaked into inspect message: {msg!r}"
    assert "github/spec-kit" in msg or "specify" in msg.lower(), (
        f"Expected public spec-kit reference in inspect message, got: {msg!r}"
    )


# --------------------------------------------------------------------------- #
# full-mode — marketplace path (speckit_source non-empty)                      #
# --------------------------------------------------------------------------- #

def test_full_mode_prefers_marketplace_speckit(tmp_path):
    """spec_mode=full with speckit_source set → installs THAT via apm, not public."""
    project = tmp_path / "proj"
    project.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # apm: --version ok, install ok
    _make_apm_stub(stub_bin, version_exit=0, install_exit=0)

    patched_path = f"{stub_bin}:{os.environ.get('PATH', '')}"
    plan = _frozen_plan(
        tmp_path,
        spec_mode="full",
        speckit_source="myspeckit@my-marketplace",
    )
    proc = _run(project, plan, extra_env={"PATH": patched_path})
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    # After apm install success the module looks for setup-speckit.sh; it won't
    # find it in tmp (no apm_modules dir), so it should emit FETCH_FAILED — that
    # is the correct marketplace-path behaviour (apm was called, not public uv).
    # The key assertion is that the error references the marketplace locator, not
    # srobroek and not the public URL.
    result_text = json.dumps(result)
    assert "srobroek" not in result_text, f"srobroek leaked: {result_text}"
    assert "myspeckit@my-marketplace" in result_text, (
        f"Expected marketplace locator in result, got: {result_text}"
    )


def test_full_mode_marketplace_apm_missing_emits_error(tmp_path):
    """spec_mode=full with speckit_source set but apm missing → MISSING_REQUIRED_TOOL."""
    project = tmp_path / "proj"
    project.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # apm stub: exits 1 for --version → not available
    _make_apm_stub(stub_bin, version_exit=1)

    patched_path = f"{stub_bin}:{os.environ.get('PATH', '')}"
    plan = _frozen_plan(
        tmp_path,
        spec_mode="full",
        speckit_source="myspeckit@my-marketplace",
    )
    proc = _run(project, plan, extra_env={"PATH": patched_path})
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    assert result["error"]["error_code"] == "MISSING_REQUIRED_TOOL"
    result_text = json.dumps(result)
    assert "srobroek" not in result_text


def test_full_mode_marketplace_install_fails_emits_error(tmp_path):
    """spec_mode=full with speckit_source set, apm install fails → FETCH_FAILED."""
    project = tmp_path / "proj"
    project.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # apm stub: --version ok, install fails
    _make_apm_stub(stub_bin, version_exit=0, install_exit=1)

    patched_path = f"{stub_bin}:{os.environ.get('PATH', '')}"
    plan = _frozen_plan(
        tmp_path,
        spec_mode="full",
        speckit_source="myspeckit@my-marketplace",
    )
    proc = _run(project, plan, extra_env={"PATH": patched_path})
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "error"
    assert result["error"]["error_code"] == "FETCH_FAILED"
    result_text = json.dumps(result)
    assert "srobroek" not in result_text
    assert "myspeckit@my-marketplace" in result_text


# --------------------------------------------------------------------------- #
# full-mode — graceful degrade                                                  #
# --------------------------------------------------------------------------- #

def test_full_mode_graceful_degrade_uv_absent(tmp_path):
    """spec_mode=full, speckit_source="" (public path), uv absent → status=ok with warning.

    We use a uv stub that intercepts 'uv tool install' calls and lies to the
    module that uv is absent by having the stub report exit 127 for tool install
    AND we do NOT put a real 'uv' in the module's perspective by using a stub
    that intercepts shutil.which via a wrapper that exits non-zero.

    Strategy: use a uv stub that passes 'uv run' through (so test harness works)
    but returns a non-zero exit for 'uv tool install' so the module treats
    install as failed and degrades gracefully.
    """
    project = tmp_path / "proj"
    project.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()

    # uv stub that passes 'uv run' but FAILS 'uv tool install' → module degrades
    _make_uv_stub(stub_bin, tool_install_exit=1)
    # No specify stub → specify won't be found either (secondary check)

    patched_path = f"{stub_bin}:{os.environ.get('PATH', '')}"
    plan = _frozen_plan(tmp_path, spec_mode="full", speckit_source="")
    proc = _run(project, plan, extra_env={"PATH": patched_path})
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    # Must be non-fatal: status ok
    assert result["status"] == "ok", result
    # Must carry a warning with the manual public command
    warnings = result.get("warnings") or []
    all_warnings = " ".join(warnings)
    assert "uv" in all_warnings.lower() or "specify" in all_warnings.lower(), (
        f"Expected tool reference in warning, got: {warnings!r}"
    )
    assert "github.com/github/spec-kit" in all_warnings or "specify" in all_warnings.lower(), (
        f"Expected public spec-kit command in warning, got: {warnings!r}"
    )
    assert "srobroek" not in all_warnings, f"srobroek leaked into warning: {all_warnings!r}"


def test_full_mode_graceful_degrade_specify_missing_after_install(tmp_path):
    """spec_mode=full, uv tool install succeeds but specify fails → status=ok with warning.

    The system may have a real `specify` installed; we shadow it with a stub that
    exits 0 for 'uv run' pass-through (via _make_uv_stub) but exits 1 for any
    `specify` invocation, simulating a broken/absent post-install specify.
    """
    project = tmp_path / "proj"
    project.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    # uv stub: passes 'uv run' through; 'uv tool install' succeeds (exit 0)
    _make_uv_stub(stub_bin, tool_install_exit=0)
    # specify stub that FAILS (exit 1) — shadows any real specify on PATH so the
    # module sees specify as broken/unavailable (shutil.which finds it but init fails)
    # Note: shutil.which will find the stub (non-zero exit for init call means
    # _install_public_speckit returns False); we want specify FOUND but init FAILING.
    _make_cmd_stub(stub_bin, "specify", exit_code=1)

    patched_path = f"{stub_bin}:{os.environ.get('PATH', '')}"
    plan = _frozen_plan(tmp_path, spec_mode="full", speckit_source="")
    proc = _run(project, plan, extra_env={"PATH": patched_path})
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result
    warnings = result.get("warnings") or []
    all_warnings = " ".join(warnings)
    assert "srobroek" not in all_warnings
    # Should warn about specify failing
    assert "specify" in all_warnings.lower() or "spec-kit" in all_warnings.lower(), (
        f"Expected specify reference in warning, got: {warnings!r}"
    )


# --------------------------------------------------------------------------- #
# Version policy (FR-V1 / FR-V2)                                               #
# --------------------------------------------------------------------------- #

def test_full_mode_latest_uses_unpinned_ref(tmp_path):
    """spec_mode=full, speckit_version='latest' → --from ref has no @tag (unpinned).

    Uses --inspect so no actual uv/specify calls are made; the message must
    reference the unpinned git URL without any @v... tag.
    """
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="full", speckit_source="", speckit_version="latest")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result
    msg = result.get("message", "")
    # The --from ref must NOT contain a @v... version pin
    assert "github/spec-kit" in msg, f"Expected git URL in inspect message, got: {msg!r}"
    # "latest" → no @vX.Y.Z in the git URL portion
    import re
    assert not re.search(r"spec-kit\.git@v\S+", msg), (
        f"Unpinned install expected (no @v tag) but found one in: {msg!r}"
    )


def test_full_mode_pinned_version_uses_pinned_ref(tmp_path):
    """spec_mode=full, speckit_version='v0.0.61' → --from ref is pinned @v0.0.61."""
    project = tmp_path / "proj"
    project.mkdir()
    plan = _frozen_plan(tmp_path, spec_mode="full", speckit_source="", speckit_version="v0.0.61")
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result
    msg = result.get("message", "")
    assert "v0.0.61" in msg, f"Expected pinned version in inspect message, got: {msg!r}"
    assert "spec-kit.git@v0.0.61" in msg, (
        f"Expected pinned ref 'spec-kit.git@v0.0.61' in message, got: {msg!r}"
    )


def test_full_mode_default_version_is_latest(tmp_path):
    """spec_mode=full with no speckit_version answer → defaults to 'latest' (unpinned)."""
    project = tmp_path / "proj"
    project.mkdir()
    # Build plan WITHOUT speckit_version in answers (omit key entirely)
    plan_data = {
        "schema_version": 1,
        "mode": "init",
        "order": ["speckit-bridge"],
        "modules": {
            "speckit-bridge": {
                "id": "speckit-bridge",
                "version": "1.0.0",
                "reconcile": False,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "spec_mode": "full",
                    "speckit_source": "",
                    "marketplace": "",
                    # speckit_version intentionally absent → module default "latest"
                },
                "steps": [{"id": "setup", "kind": "python"}],
            }
        },
    }
    plan = tmp_path / "plan_noversion.json"
    plan.write_text(json.dumps(plan_data))
    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result
    msg = result.get("message", "")
    # Should not have @v... in the git URL — defaults to unpinned
    import re
    assert not re.search(r"spec-kit\.git@v\S+", msg), (
        f"Default (no speckit_version) should be unpinned, but found pin in: {msg!r}"
    )


# --------------------------------------------------------------------------- #
# Source-code audit                                                              #
# --------------------------------------------------------------------------- #

def test_no_srobroek_in_module():
    """module.py must contain zero 'srobroek' literals (Phase 5 will clean module.toml)."""
    source = _MODULE_PY.read_text()
    assert "srobroek" not in source, (
        "srobroek literal found in module.py — all srobroek refs must be removed"
    )


def test_no_speckit_pin_constant_in_module():
    """FR-V1: module.py must NOT contain _SPECKIT_PIN or 'v0.0.55' (the old hardcoded pin)."""
    source = _MODULE_PY.read_text()
    assert "_SPECKIT_PIN" not in source, (
        "_SPECKIT_PIN constant found in module.py — hardcoded pins must be removed (FR-V1)"
    )
    assert "v0.0.55" not in source, (
        "'v0.0.55' literal found in module.py — hardcoded pins must be removed (FR-V1)"
    )
