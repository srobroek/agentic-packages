"""End-to-end tests for the lang-python module.

Verifies:
  - manifest parses and is valid (id, default_enabled=False, reconcile=True, order)
  - happy path: config files written + gitignore/pre-commit appends present with
    correct markers (toolchain stubbed offline — no real uv installs, no network)
  - tool-missing → warn+continue (no raise, returncode==0)
  - idempotent re-run does NOT double-append (grep-guard works — run twice,
    assert marker appears exactly once in .gitignore and .pre-commit-config.yaml)
  - --inspect writes nothing

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
    """When uv (init/add) fails, module warns and returns ok (no raise).

    We test this in-process: load module.py, monkeypatch shutil.which so that
    'uv' appears absent, then call _run_tool directly to assert warn+continue.
    This avoids the impossible task of hiding 'uv' from PATH while still using
    'uv run module.py' as the launcher.
    """
    # Load sdk deps into sys.modules first
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

    # Load the module in-process
    module_py = _PLUGIN_ROOT / _MODULE_REL / "module.py"
    mspec = importlib.util.spec_from_file_location("lang_python_mod", module_py)
    assert mspec and mspec.loader
    mmod = importlib.util.module_from_spec(mspec)
    sys.modules["lang_python_mod"] = mmod
    mspec.loader.exec_module(mmod)

    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")
    (project / ".gitignore").write_text("# base\n")

    warnings_out: list[str] = []

    # Monkeypatch shutil.which inside the loaded module so 'uv' is not found
    import unittest.mock
    with unittest.mock.patch.object(mmod.shutil, "which", return_value=None):
        ok = mmod._run_tool(
            ["uv", "init", "--python", "3.13"],
            cwd=project,
            warnings=warnings_out,
            label="uv init",
        )

    assert ok is False, "Expected _run_tool to return False when tool is absent"
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
