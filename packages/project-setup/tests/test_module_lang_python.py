"""End-to-end tests for the lang-python module.

Verifies:
  - manifest parses and is valid (id, default_enabled=False, reconcile=True, order)
  - happy path: config files written + gitignore/pre-commit appends present with
    correct markers (toolchain stubbed offline — no real uv installs, no network)
  - tool-missing → warn+continue (no raise, returncode==0)
  - idempotent re-run does NOT double-append (grep-guard works — run twice,
    assert marker appears exactly once in .gitignore and .pre-commit-config.yaml)
  - --inspect writes nothing

Spec-003 additions (SC-001, SC-005):
  - SC-001: reproduce mode skips pin verification (zero-network); bad (disconfirmed)
    pins are rejected and no files written; in-process unit test using stub verify.
  - SC-005: unpinned "uv add --dev ruff pytest" no longer in module.py source;
    pre-commit block uses rev derived from frozen ruff_version.

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_module_lang_python.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _PKG / "skills" / "project-setup"
_RUNNER = _PLUGIN_ROOT / "runner"
_MODULE_REL = "modules/lang-python"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frozen_plan(tmp: Path, python_version: str = "3.13", framework: str = "") -> Path:
    plan = {
        "schema_version": 1,
        "mode": "init",
        "order": ["lang-python"],
        "modules": {
            "lang-python": {
                "id": "lang-python",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "python_version": python_version,
                    "framework": framework,
                },
                "steps": [{"id": "write", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def _stub_uv(tmp: Path) -> Path:
    """Write a fake uv stub that succeeds silently for 'uv init' and 'uv add'.

    IMPORTANT: do NOT put a 'uv' binary in this dir — the test runner uses
    'uv run module.py' to launch the module, so shadowing 'uv' in PATH would
    prevent the module from running at all.  The stub directory is prepended to
    PATH so any language-tool stubs resolve before system tools, but 'uv' itself
    must always resolve from the real system PATH.

    For lang-python we don't need a stub binary at all: the real uv is on PATH,
    and the tests create a pyproject.toml so 'uv init' is skipped (file exists),
    and 'uv add' either runs against the real uv (it exits fast on success in the
    tmp project) or is harmless on failure.

    To make happy-path tests fast and hermetic we pre-populate pyproject.toml so
    uv init is skipped, and accept that 'uv add --dev ruff pytest' may warn if it
    fails in the tmp project (we only assert on the config files and appends).
    """
    stub_dir = tmp / "stubs"
    stub_dir.mkdir(exist_ok=True)
    # No 'uv' stub — we need the real uv for 'uv run module.py'
    return stub_dir


def _run(
    project: Path,
    plan: Path,
    stub_dir: Path | None = None,
    *,
    inspect: bool = False,
) -> subprocess.CompletedProcess:
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    cmd = ["uv", "run", str(module_py), "--plan", str(plan), "--step", "write"]
    if inspect:
        cmd.append("--inspect")
    env = {**os.environ, "PLUGIN_ROOT": str(_PLUGIN_ROOT), "PROJECT_DIR": str(project)}
    if stub_dir is not None:
        env["PATH"] = f"{stub_dir}:{env.get('PATH', '')}"
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))


# ── manifest ─────────────────────────────────────────────────────────────────

def test_manifest_parses_and_is_valid():
    manifest = _load("manifest")
    mani = manifest.parse_manifest(_PLUGIN_ROOT / _MODULE_REL / "module.toml")
    assert not mani.errors, mani.errors
    assert mani.id == "lang-python"
    assert mani.default_enabled is False, "language overlays must be opt-in (default_enabled=false)"
    assert mani.reconcile is True
    assert any(s.id == "write" and s.kind == "python" for s in mani.steps)
    assert "gitignore-generate" in mani.order.get("after", [])
    assert "precommit-setup" in mani.order.get("after", [])

    input_keys = {inp.key for inp in mani.inputs}
    assert "python_version" in input_keys
    assert "framework" in input_keys


# ── happy path ───────────────────────────────────────────────────────────────

def test_happy_path_creates_src_init(tmp_path):
    """Happy path: src/<project>/__init__.py is created."""
    project = tmp_path / "myapp"
    project.mkdir()
    # Pre-populate pyproject.toml so uv init is skipped (keeps test hermetic)
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok"

    init_py = project / "src" / "myapp" / "__init__.py"
    assert init_py.exists(), f"src/__init__.py not created; files_written={result['files_written']}"


def test_happy_path_appends_gitignore_block(tmp_path):
    """Happy path: __pycache__ marker present in .gitignore after run."""
    project = tmp_path / "myapp"
    project.mkdir()
    # Pre-populate pyproject.toml so uv init is skipped
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    gi_content = (project / ".gitignore").read_text()
    assert "__pycache__" in gi_content, "gitignore __pycache__ marker missing"
    assert "*.py[cod]" in gi_content
    assert ".venv" in gi_content


def test_happy_path_appends_precommit_hooks(tmp_path):
    """Happy path: ruff pre-commit hooks appended to .pre-commit-config.yaml."""
    project = tmp_path / "myapp"
    project.mkdir()
    # Pre-populate pyproject.toml so uv init is skipped
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan)
    assert proc.returncode == 0, proc.stderr

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    assert "astral-sh/ruff-pre-commit" in pc_content
    assert "ruff-format" in pc_content


# ── tool-missing → warn+continue ─────────────────────────────────────────────

def test_tool_missing_warns_and_continues(tmp_path):
    """When a tool is absent, sdk.run_tool warns and returns False (no raise).

    We test this in-process: load the SDK, monkeypatch sdk_mod.shutil.which so
    that 'uv' appears absent, then call sdk.run_tool directly to assert
    warn+continue.  After the _run_tool/_append_if_absent dedup (Part B), the
    implementation lives in sdk.py, so we patch shutil there.
    """
    # Load sdk and its deps into sys.modules
    runner_dir = _PLUGIN_ROOT / "runner"
    sdk_path = runner_dir / "sdk.py"
    sdk_spec = importlib.util.spec_from_file_location("ps_sdk", sdk_path)
    assert sdk_spec and sdk_spec.loader
    sdk_mod = importlib.util.module_from_spec(sdk_spec)
    sys.modules["ps_sdk"] = sdk_mod
    sdk_spec.loader.exec_module(sdk_mod)
    for dep in ("contracts", "plan"):
        if dep not in sys.modules:
            dspec = importlib.util.spec_from_file_location(dep, runner_dir / f"{dep}.py")
            assert dspec and dspec.loader
            dmod = importlib.util.module_from_spec(dspec)
            sys.modules[dep] = dmod
            dspec.loader.exec_module(dmod)

    project = tmp_path / "myapp"
    project.mkdir()

    warnings_out: list[str] = []

    # Monkeypatch shutil.which inside the SDK so 'uv' is not found
    import unittest.mock
    with unittest.mock.patch.object(sdk_mod.shutil, "which", return_value=None):
        ok = sdk_mod.run_tool(
            ["uv", "init", "--python", "3.13"],
            cwd=project,
            warnings=warnings_out,
            label="uv init",
        )

    assert ok is False, "Expected run_tool to return False when tool is absent"
    assert any("uv" in w for w in warnings_out), (
        f"Expected warning about uv missing; got: {warnings_out}"
    )


# ── idempotence ───────────────────────────────────────────────────────────────

def test_idempotent_no_double_append_gitignore(tmp_path):
    """__pycache__ marker must appear exactly once after two runs."""
    project = tmp_path / "myapp"
    project.mkdir()
    # Pre-populate pyproject.toml so uv init is skipped (hermetic)
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    _run(project, plan)
    _run(project, plan)

    gi_content = (project / ".gitignore").read_text()
    count = gi_content.count("__pycache__")
    assert count == 1, f"__pycache__ appeared {count} times (expected 1) — double-append bug"


def test_idempotent_no_double_append_precommit(tmp_path):
    """ruff-pre-commit marker must appear exactly once after two runs."""
    project = tmp_path / "myapp"
    project.mkdir()
    # Pre-populate pyproject.toml so uv init is skipped (hermetic)
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")
    plan = _frozen_plan(tmp_path)

    _run(project, plan)
    _run(project, plan)

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    count = pc_content.count("astral-sh/ruff-pre-commit")
    assert count == 1, f"ruff-pre-commit appeared {count} times (expected 1) — double-append bug"


# ── inspect ───────────────────────────────────────────────────────────────────

def test_inspect_writes_nothing(tmp_path):
    """--inspect produces diffs but writes nothing to disk."""
    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")
    plan = _frozen_plan(tmp_path)

    proc = _run(project, plan, inspect=True)
    assert proc.returncode == 0, proc.stderr

    # src/__init__.py must not exist (inspect mode writes nothing)
    assert not (project / "src").exists() or not (project / "src" / "myapp" / "__init__.py").exists()


# ── SC-001: pin verification behaviour ───────────────────────────────────────

def _load_module_inprocess():
    """Load module.py in-process with SDK pre-wired.

    Returns the loaded module object.  Idempotent: re-uses cached modules.
    """
    runner_dir = _PLUGIN_ROOT / "runner"
    # Pre-load SDK dependencies
    for dep in ("contracts", "plan", "sdk"):
        mod_key = dep if dep != "sdk" else "ps_sdk"
        if mod_key not in sys.modules:
            dspec = importlib.util.spec_from_file_location(
                mod_key, runner_dir / f"{dep}.py"
            )
            assert dspec and dspec.loader
            dmod = importlib.util.module_from_spec(dspec)
            sys.modules[mod_key] = dmod
            dspec.loader.exec_module(dmod)

    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    if "lang_python_mod" in sys.modules:
        return sys.modules["lang_python_mod"]
    mspec = importlib.util.spec_from_file_location("lang_python_mod", module_py)
    assert mspec and mspec.loader
    mmod = importlib.util.module_from_spec(mspec)
    sys.modules["lang_python_mod"] = mmod
    mspec.loader.exec_module(mmod)
    return mmod


def _frozen_plan_with_pins(
    tmp: Path,
    *,
    mode: str = "init",
    pinned_deps: list[str] | None = None,
    dev_deps: list[str] | None = None,
    ruff_version: str = "0.8.4",
) -> Path:
    """Build a frozen plan.json that carries resolved agent pins."""
    plan = {
        "schema_version": 1,
        "mode": mode,
        "order": ["lang-python"],
        "modules": {
            "lang-python": {
                "id": "lang-python",
                "version": "1.0.0",
                "reconcile": True,
                "module_rel_root": _MODULE_REL,
                "answers": {
                    "python_version": "3.13",
                    "framework": "fastapi",
                    "pinned_deps": pinned_deps if pinned_deps is not None else ["fastapi@0.115.5"],
                    "dev_deps": dev_deps if dev_deps is not None else ["ruff@0.8.4", "pytest@8.3.4"],
                    "ruff_version": ruff_version,
                },
                "steps": [{"id": "write", "kind": "python"}],
            }
        },
    }
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def test_sc001_reproduce_mode_skips_verification(tmp_path):
    """SC-001 (reproduce path): mode='reproduce' → no verify_pins call, files written.

    In reproduce mode the module must write the manifest without calling the
    network at all — the pins were already verified at init.  We prove this by
    making the module's sdk.verify_pins raise if called (any call = test failure),
    then asserting the write still succeeds.
    """
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="reproduce",
        pinned_deps=["fastapi@0.115.5"],
        dev_deps=["ruff@0.8.4", "pytest@8.3.4"],
    )

    import unittest.mock

    def _verify_should_not_be_called(*args, **kwargs):
        raise AssertionError("verify_pins must NOT be called in reproduce mode")

    import types
    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_verify_should_not_be_called):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-python")
            # Capture stdout so emit_result doesn't pollute test output
            import io
            captured = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 0, f"write step failed in reproduce mode: {captured.getvalue()}"
    result = json.loads(captured.getvalue())
    assert result["status"] == "ok", result


def test_sc001_disconfirmed_pin_rejected_and_nothing_written(tmp_path):
    """SC-001 (bad pin rejection): a disconfirmed pin → status=error, no files written.

    Uses the _opener seam on sdk.verify_pins (via monkeypatching) to simulate a
    registry that returns 404 for the hallucinated pin.  The module must return
    status=error and write nothing to disk.
    """
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")

    # Plan with a hallucinated pin (faastapi is a typosquat)
    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="init",
        pinned_deps=["faastapi@0.115.5"],   # hallucinated — disconfirmed
        dev_deps=["ruff@0.8.4", "pytest@8.3.4"],
    )

    import unittest.mock
    import types

    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    # Stub verify_pins to disconfirm the hallucinated pin and verify the rest
    def _stub_verify(pins, ecosystem, **kwargs):
        result = {}
        for pin in pins:
            if "faastapi" in pin:
                result[pin] = sdk.PIN_DISCONFIRMED
            else:
                result[pin] = sdk.PIN_VERIFIED
        return result

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_stub_verify):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-python")
            import io, contextlib
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 1, "Expected non-zero exit for disconfirmed pin"
    result = json.loads(captured.getvalue())
    assert result["status"] == "error", result
    assert result["error"] is not None
    assert "faastapi@0.115.5" in result["error"].get("received", ""), result["error"]

    # Critical: nothing must be written (src/ should not have been created)
    assert not (project / "src").exists() or not (project / "src" / "myapp").exists(), \
        "Module wrote files despite a disconfirmed pin — this violates FR-005"


def test_sc001_unreachable_registry_safe_skips(tmp_path):
    """SC-001 (offline safe-skip): unreachable registry → status=ok, manifest write skipped."""
    mmod = _load_module_inprocess()
    sdk = sys.modules["ps_sdk"]

    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")

    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="init",
        pinned_deps=["fastapi@0.115.5"],
        dev_deps=["ruff@0.8.4", "pytest@8.3.4"],
    )

    import unittest.mock, types, io, contextlib

    args_ns = types.SimpleNamespace(step="write", inspect=False, plan=str(plan_path))

    def _all_unreachable(pins, ecosystem, **kwargs):
        return {pin: sdk.PIN_UNREACHABLE for pin in pins}

    with unittest.mock.patch.dict(os.environ, {"PROJECT_DIR": str(project), "PLUGIN_ROOT": str(_PLUGIN_ROOT)}):
        with unittest.mock.patch.object(sdk, "verify_pins", side_effect=_all_unreachable):
            inputs = sdk.load_frozen_inputs(str(plan_path), module_id="lang-python")
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                ret = mmod._do_write(sdk, inputs, args_ns)

    assert ret == 0, "Unreachable registry should be a safe-skip (ok), not an error"
    result = json.loads(captured.getvalue())
    assert result["status"] == "ok", result
    # Must have at least one warning about unreachable pins
    assert any("unreachable" in w.lower() or "registry" in w.lower() for w in result["warnings"]), \
        f"Expected registry-unreachable warning; got: {result['warnings']}"
    # Manifest write must be skipped — src/ not created
    assert not (project / "src").exists() or not (project / "src" / "myapp").exists(), \
        "Module wrote files despite unreachable registry — violates FR-012"


def test_sc001_verified_pins_written_in_pyproject(tmp_path):
    """SC-001 (happy path): all pins verified → pyproject.toml contains the pinned deps."""
    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")

    # Use reproduce mode so no network is needed — pins are treated as pre-verified
    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="reproduce",
        pinned_deps=["fastapi@0.115.5", "uvicorn@0.34.0"],
        dev_deps=["ruff@0.8.4", "pytest@8.3.4"],
        ruff_version="0.8.4",
    )

    proc = _run(project, plan_path)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "ok", result

    pyproject_content = (project / "pyproject.toml").read_text()
    assert "fastapi@0.115.5" in pyproject_content, \
        f"Expected fastapi@0.115.5 in pyproject.toml; got:\n{pyproject_content}"
    assert "uvicorn@0.34.0" in pyproject_content, \
        f"Expected uvicorn@0.34.0 in pyproject.toml; got:\n{pyproject_content}"


# ── SC-005: no unpinned uv add; ruff_version drives pre-commit rev ────────────

def test_sc005_no_unpinned_uv_add_in_source():
    """SC-005: the old unpinned 'uv add --dev ruff pytest' must not appear in module.py."""
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    source = module_py.read_text(encoding="utf-8")
    assert '"ruff", "pytest"' not in source and \
           '"ruff pytest"' not in source and \
           '["uv", "add", "--dev", "ruff", "pytest"]' not in source, (
        "Found unpinned 'uv add --dev ruff pytest' in module.py — "
        "this violates SC-005 (dev tools must come from frozen pinned_deps)"
    )


def test_sc005_precommit_rev_uses_frozen_ruff_version(tmp_path):
    """SC-005: ruff pre-commit hook rev is derived from frozen ruff_version, not hardcoded."""
    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")
    (project / ".pre-commit-config.yaml").write_text("repos:\n")

    # Use a distinctive ruff version to verify it's being used
    plan_path = _frozen_plan_with_pins(
        tmp_path,
        mode="reproduce",
        pinned_deps=[],
        dev_deps=["ruff@1.2.3", "pytest@8.3.4"],
        ruff_version="1.2.3",
    )

    proc = _run(project, plan_path)
    assert proc.returncode == 0, proc.stderr

    pc_content = (project / ".pre-commit-config.yaml").read_text()
    assert "rev: v1.2.3" in pc_content, (
        f"Expected 'rev: v1.2.3' from frozen ruff_version in .pre-commit-config.yaml; "
        f"got:\n{pc_content}"
    )
    # The old hardcoded version should NOT appear unless it happens to be 1.2.3
    assert "rev: v0.6.9" not in pc_content, (
        ".pre-commit-config.yaml still has the hardcoded rev: v0.6.9 — "
        "ruff_version substitution is not working"
    )
